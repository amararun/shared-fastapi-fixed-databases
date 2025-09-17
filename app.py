from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import FileResponse
import os
import tempfile
import logging
import io
 
from dotenv import load_dotenv
import secrets
import aiomysql
import asyncpg
import asyncio
from typing import Union
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from fastapi.responses import JSONResponse
import json
import datetime
from decimal import Decimal

# Custom JSON encoder to handle date/datetime/decimal objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        elif isinstance(obj, datetime.time):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# Configure logging from environment variables
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
MULTIPART_LOG_LEVEL = "INFO"

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)
# Add this line to reduce multipart logging
logging.getLogger("multipart.multipart").setLevel(getattr(logging, MULTIPART_LOG_LEVEL))

# Add these debug logs right before load_dotenv()
logger.debug(f"Current working directory: {os.getcwd()}")
logger.debug(f"Looking for .env file in: {os.path.join(os.getcwd(), '.env')}")
logger.debug(f".env file exists: {os.path.exists(os.path.join(os.getcwd(), '.env'))}")

# Then load the env vars
load_dotenv()

# Do not log all environment variables to avoid leaking secrets

# Database type mappings (unused)

# Starlette BaseHTTPMiddleware not required anymore

# Initialize FastAPI and add middlewares in correct order
app = FastAPI()

# Rate limiting configuration
RATE_LIMIT = os.getenv("RATE_LIMIT", "100/hour")
RATE_LIMIT_MESSAGE = "Rate limit exceeded. Please try again later or contact your administrator."
logger.info(f"Using rate limit: {RATE_LIMIT}")

# Initialize SlowAPI limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Custom 429 handler
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": RATE_LIMIT_MESSAGE}
    )


# Upload size middleware removed (no upload endpoints)

# CORS configuration from environment variables
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
CORS_ALLOW_METHODS = os.getenv("CORS_ALLOW_METHODS", "*").split(",")
CORS_ALLOW_HEADERS = os.getenv("CORS_ALLOW_HEADERS", "*").split(",")
CORS_EXPOSE_HEADERS = os.getenv("CORS_EXPOSE_HEADERS", "*").split(",")

# Simplify CORS middleware (fixed syntax)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
    expose_headers=CORS_EXPOSE_HEADERS,
)

from urllib.parse import urlparse

# Load environment variables
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY env var not set")

# Database connection pool configuration
DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "4"))
DB_POOL_MAX_INACTIVE_LIFETIME = int(os.getenv("DB_POOL_MAX_INACTIVE_LIFETIME", "300"))
DB_POOL_RECYCLE_TIME = int(os.getenv("DB_POOL_RECYCLE_TIME", "1800"))
DB_STATEMENT_CACHE_SIZE = int(os.getenv("DB_STATEMENT_CACHE_SIZE", "0"))

# Database timeout configuration (in milliseconds)
DB_STATEMENT_TIMEOUT_MS = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "180000"))
DB_EXECUTION_TIMEOUT_MS = int(os.getenv("DB_EXECUTION_TIMEOUT_MS", "180000"))

# Default database ports
DEFAULT_MYSQL_PORT = 3306

# File and response configuration
CSV_FILENAME = os.getenv("CSV_FILENAME", "results.csv")
CSV_FILE_SUFFIX = os.getenv("CSV_FILE_SUFFIX", ".csv")
CSV_ENCODING = os.getenv("CSV_ENCODING", "utf-8")

# Authentication error messages
AUTH_MISSING_HEADER_MSG = "Missing Authorization header"
AUTH_INVALID_SCHEME_MSG = "Invalid auth scheme, use 'Bearer <token>'"
AUTH_INVALID_KEY_MSG = "Invalid API key"

# Query execution messages
QUERY_SUCCESS_MSG = "Query executed successfully"

# Server configuration
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# ---------- Connection pool management ----------
async def _pg_pool_init(conn: asyncpg.Connection) -> None:
    # Enforce read-only transactions on PostgreSQL connections
    await conn.execute("SET default_transaction_read_only=on")
    # Set statement timeout from environment variable (milliseconds)
    await conn.execute(f"SET statement_timeout = {DB_STATEMENT_TIMEOUT_MS}")

@app.on_event("startup")
async def startup_create_pools() -> None:
    app.state.db_pools = {}
    db_uri_env_map = {
        "aiven_postgres": "AIVEN_POSTGRES",
        "aiven_mysql": "AIVEN_MYSQL",
        "neon_postgres": "NEON_POSTGRES",
        "supabase_postgres": "SUPABASE_POSTGRES",
    }

    for cloud, env_var_name in db_uri_env_map.items():
        db_uri = os.getenv(env_var_name)
        if not db_uri:
            logger.warning(f"Env var {env_var_name} not set; skipping pool for {cloud}")
            continue

        parsed = urlparse(db_uri)
        scheme = parsed.scheme.lower()
        try:
            if "postgres" in scheme:
                pool = await asyncpg.create_pool(
                    dsn=db_uri,
                    min_size=DB_POOL_MIN_SIZE,
                    max_size=DB_POOL_MAX_SIZE,
                    max_inactive_connection_lifetime=DB_POOL_MAX_INACTIVE_LIFETIME,
                    init=_pg_pool_init,
                    statement_cache_size=DB_STATEMENT_CACHE_SIZE,  # Disable prepared statements for pgbouncer compatibility
                )
                app.state.db_pools[cloud] = {"pool": pool, "db_type": "postgresql"}
                logger.info(f"PostgreSQL pool created for {cloud}")
            elif "mysql" in scheme:
                pool = await aiomysql.create_pool(
                    host=parsed.hostname,
                    user=parsed.username,
                    password=parsed.password,
                    db=parsed.path.lstrip('/'),
                    port=parsed.port or DEFAULT_MYSQL_PORT,
                    minsize=DB_POOL_MIN_SIZE,
                    maxsize=DB_POOL_MAX_SIZE,
                    pool_recycle=DB_POOL_RECYCLE_TIME,
                    autocommit=True,
                )
                app.state.db_pools[cloud] = {"pool": pool, "db_type": "mysql"}
                logger.info(f"MySQL pool created for {cloud}")
            else:
                logger.error(f"Unsupported scheme in {env_var_name}: {scheme}")
        except Exception as e:
            logger.exception(f"Failed to create pool for {cloud} from {env_var_name}: {e}")

@app.on_event("shutdown")
async def shutdown_close_pools() -> None:
    pools = getattr(app.state, "db_pools", {})
    for cloud, meta in pools.items():
        try:
            if meta["db_type"] == "postgresql":
                await meta["pool"].close()
                logger.info(f"Closed PostgreSQL pool for {cloud}")
            else:
                meta["pool"].close()
                await meta["pool"].wait_closed()
                logger.info(f"Closed MySQL pool for {cloud}")
        except Exception as e:
            logger.warning(f"Error while closing pool for {cloud}: {e}")

# Removed unused synchronous get_connection

async def create_async_connection(cloud: str):
    """Acquire a connection from the appropriate pool based on cloud provider."""
    pools = getattr(app.state, "db_pools", {})
    if cloud not in pools:
        raise HTTPException(status_code=500, detail=f"No pool configured for cloud '{cloud}'")

    meta = pools[cloud]
    if meta["db_type"] == "mysql":
        # aiomysql returns a pooled connection via acquire()
        conn = await meta["pool"].acquire()
        try:
            # Set per-statement timeout from environment variable in milliseconds (MySQL/MariaDB)
            async with conn.cursor() as cur:
                await cur.execute(f"SET SESSION MAX_EXECUTION_TIME={DB_EXECUTION_TIMEOUT_MS}")
        except Exception:
            # Some MySQL variants may not support MAX_EXECUTION_TIME; continue without failing
            logger.debug("MAX_EXECUTION_TIME not supported; continuing without per-statement timeout")
        return conn, "mysql"
    else:
        # asyncpg returns a connection via acquire()
        conn = await meta["pool"].acquire()
        return conn, "postgresql"

async def verify_api_key(request: Request):
    auth = request.headers.get("Authorization")
    if not auth:
        raise HTTPException(
            status_code=401,
            detail=AUTH_MISSING_HEADER_MSG,
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail=AUTH_INVALID_SCHEME_MSG,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not secrets.compare_digest(token, API_KEY):
        raise HTTPException(status_code=403, detail=AUTH_INVALID_KEY_MSG)

@app.get("/sqlquery/", dependencies=[Depends(verify_api_key)])
@limiter.limit(RATE_LIMIT)
async def sqlquery(sqlquery: str, cloud: str, request: Request, format: str = "json"):
    """Execute SQL query using async database connections.

    - Default returns JSON with up to 10,000 rows and a truncated flag.
    - If format=csv, stream CSV up to 1,000,000 rows with proper headers.
    """
    logger.debug(f"Received API call: {request.url} with cloud parameter: {cloud}")

    fmt = (format or "json").lower()
    if fmt not in {"json", "csv"}:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'json' or 'csv'.")

    max_json_rows = int(os.getenv("MAX_JSON_ROWS", "10000"))
    max_csv_rows = int(os.getenv("MAX_CSV_ROWS", "1000000"))

    connection = None
    try:
        # Acquire pooled connection
        connection, db_type = await create_async_connection(cloud)

        # Check if query returns data (SELECT, SHOW, DESCRIBE, EXPLAIN, etc.)
        query_lower = sqlquery.strip().lower()
        is_data_query = (
            query_lower.startswith("select") or 
            query_lower.startswith("show") or 
            query_lower.startswith("describe") or 
            query_lower.startswith("explain") or
            query_lower.startswith("with")
        )
        if not is_data_query:
            if db_type == "mysql":
                async with connection.cursor() as cursor:
                    await cursor.execute(sqlquery)
                    await connection.commit()
            else:
                await connection.execute(sqlquery)
            return {"status": QUERY_SUCCESS_MSG}

        # Fetch data - simplified approach for both databases
        if db_type == "mysql":
            from aiomysql.cursors import DictCursor
            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute(sqlquery)
                rows = await cursor.fetchall()
        else:
            rows_pg = await connection.fetch(sqlquery)
            rows = [dict(r) for r in rows_pg]

        # Apply row limits
        if fmt == "json":
            truncated = len(rows) > max_json_rows
            if truncated:
                rows = rows[:max_json_rows]
            
            # Use custom encoder to handle dates/decimals
            response_data = {"rows": rows, "truncated": truncated}
            json_content = json.dumps(response_data, cls=DateTimeEncoder, ensure_ascii=False)
            return JSONResponse(content=json.loads(json_content), media_type="application/json")
        
        # CSV format - simplified
        import csv
        import io
        
        # Limit rows for CSV
        csv_rows = rows[:max_csv_rows] if len(rows) > max_csv_rows else rows
        
        # Create CSV content in memory first
        csv_buffer = io.StringIO()
        if csv_rows:
            writer = csv.DictWriter(csv_buffer, fieldnames=csv_rows[0].keys())
            writer.writeheader()
            writer.writerows(csv_rows)
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(delete=False, mode='w', newline='', suffix=CSV_FILE_SUFFIX, encoding=CSV_ENCODING) as temp_csv:
            temp_csv.write(csv_buffer.getvalue())
            temp_file_path = temp_csv.name
        
        return FileResponse(
            path=temp_file_path, 
            filename=CSV_FILENAME, 
            media_type='text/csv',
            headers={"Content-Disposition": f"attachment; filename={CSV_FILENAME}"}
        )

    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if connection:
            pools = getattr(app.state, "db_pools", {})
            meta = pools.get(cloud)
            if meta:
                logger.debug(f"Releasing pooled connection for cloud: {cloud}")
                try:
                    if meta["db_type"] == "mysql":
                        meta["pool"].release(connection)
                    else:
                        await meta["pool"].release(connection)
                except Exception as close_exc:
                    logger.error(f"Error while releasing connection for {cloud}: {close_exc}")

@app.middleware("http")
async def log_request_headers(request: Request, call_next):
    """Log important request headers for monitoring and security purposes."""
    # Get client IP (considering proxies)
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.headers.get("x-real-ip", "")
    if not client_ip:
        client_ip = getattr(request.client, "host", "unknown") if request.client else "unknown"
    
    # Get important headers
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    user_agent = request.headers.get("user-agent", "")
    accept = request.headers.get("accept", "")
    accept_language = request.headers.get("accept-language", "")
    accept_encoding = request.headers.get("accept-encoding", "")
    content_type = request.headers.get("content-type", "")
    authorization = "Bearer ***" if request.headers.get("authorization") else ""
    
    # Log the headers (truncate long values to prevent log spam)
    def truncate(value: str, max_len: int = 100) -> str:
        return value[:max_len] + "..." if len(value) > max_len else value
    
    logger.info(
        f"Request: {request.method} {request.url.path} | "
        f"IP={client_ip} | "
        f"Origin={truncate(origin)} | "
        f"Referer={truncate(referer)} | "
        f"User-Agent={truncate(user_agent)} | "
        f"Accept={truncate(accept)} | "
        f"Accept-Lang={truncate(accept_language)} | "
        f"Accept-Enc={truncate(accept_encoding)} | "
        f"Content-Type={truncate(content_type)} | "
        f"Auth={authorization}"
    )
    
    response = await call_next(request)
    return response

@app.middleware("http")
async def remove_temp_file(request, call_next):
    logger.debug(f"Processing request: {request.url}")
    response = await call_next(request)
    if isinstance(response, FileResponse) and os.path.exists(response.path):
        try:
            os.remove(response.path)
            logger.debug(f"Temporary file {response.path} removed successfully")
        except Exception as e:
            logger.error(f"Error removing temp file: {e}")
    return response

# Removed unused generate_table_name

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)

