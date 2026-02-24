# FastAPI Database Connector

A FastAPI server that provides secure, pooled database connections to multiple cloud providers. Supports both JSON and CSV response formats with built-in rate limiting, connection pooling, and comprehensive security features.

## Features

- **Multi-Database Support**: Connect to Aiven (PostgreSQL/MySQL), Supabase, and Neon databases
- **Connection Pooling**: Efficient connection management with configurable pool sizes
- **Rate Limiting**: Built-in request throttling (100/hour default, configurable)
- **API Key Authentication**: Secure Bearer token authentication
- **Dual Response Formats**: JSON (10k rows) and CSV (1M rows) with configurable limits
- **Query Timeouts**: 30-second statement timeout protection
- **Header Logging**: Comprehensive request monitoring and security logging
- **Read-Only Mode**: PostgreSQL connections enforce read-only transactions
- **CORS Support**: Configurable cross-origin resource sharing
- **File Downloads**: CSV export with proper headers and cleanup

## AI Analyst Platform
For additional data analysis capabilities, visit my AI Analyst Platform at [app.tigzig.com](https://app.tigzig.com). For any questions, reach out to me at amar@harolikar.com

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/amararun/shared-fastapi-fixed-databases.git
cd shared-fastapi-fixed-databases
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the example environment file and configure your settings:

```bash
cp .envExample .env
```

Edit `.env` with your actual values:

```bash
# Required
API_KEY=your-secure-api-key-here

# Database connections (at least one required)
AIVEN_POSTGRES=postgresql://user:pass@host:port/db?sslmode=require
AIVEN_MYSQL=mysql://user:pass@host:port/db?ssl-mode=REQUIRED
NEON_POSTGRES=postgresql://user:pass@host:port/db?sslmode=require
SUPABASE_POSTGRES=postgresql://user:pass@host:port/db?sslmode=require

# Optional configuration
RATE_LIMIT=100/hour
MAX_JSON_ROWS=10000
MAX_CSV_ROWS=1000000
```

### 3. Deploy the Server

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Your API will be available at: `http://localhost:8000`

## API Usage

### Endpoint
`GET /sqlquery/`

### Authentication
Include Bearer token in Authorization header:
```bash
Authorization: Bearer your-api-key
```

### Parameters
- `sqlquery` (required): SQL query to execute
- `cloud` (required): Database provider (`aiven_postgres`, `aiven_mysql`, `neon_postgres`, `supabase_postgres`)
- `format` (optional): Response format (`json` default, `csv`)

### Example API Calls

**JSON Response:**
```bash
curl -H "Authorization: Bearer your-api-key" \
     "http://localhost:8000/sqlquery/?sqlquery=SELECT * FROM users LIMIT 10&cloud=supabase_postgres"
```

**CSV Download:**
```bash
curl -H "Authorization: Bearer your-api-key" \
     "http://localhost:8000/sqlquery/?sqlquery=SELECT * FROM users&cloud=supabase_postgres&format=csv" \
     --output data.csv
```

### Response Formats

**JSON Response:**
```json
{
  "rows": [
    {"id": 1, "name": "John", "email": "john@example.com"},
    {"id": 2, "name": "Jane", "email": "jane@example.com"}
  ],
  "truncated": false
}
```

**CSV Response:**
- Downloadable file with proper headers
- Content-Type: `text/csv`
- Filename: `results.csv` (configurable)

## Frontend Integration

### JavaScript/TypeScript
```javascript
const response = await fetch('/sqlquery/?sqlquery=SELECT * FROM users&cloud=supabase_postgres', {
  headers: {
    'Authorization': 'Bearer your-api-key',
    'Content-Type': 'application/json'
  }
});
const data = await response.json();
```

### Python
```python
import requests

response = requests.get(
    'http://localhost:8000/sqlquery/',
    params={'sqlquery': 'SELECT * FROM users', 'cloud': 'supabase_postgres'},
    headers={'Authorization': 'Bearer your-api-key'}
)
data = response.json()
```

### React/Next.js
```jsx
const fetchData = async () => {
  const response = await fetch('/api/sqlquery', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer your-api-key',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      sqlquery: 'SELECT * FROM users',
      cloud: 'supabase_postgres',
      format: 'json'
    })
  });
  return response.json();
};
```

## Custom GPT Integration

This API is designed to work seamlessly with Custom GPTs for data analysis and querying.

### Setup Steps

1. **Deploy your API server** using the steps above
2. **Configure Custom GPT Actions** using the provided schema
3. **Upload semantic layer files** as knowledge base
4. **Set up system instructions** for data analysis

### Required Files

- **Action Schema**: `DOCS/CUSTOM_GPT_ACTION_SCHEMA.json`
- **System Instructions**: `DOCS/CUSTOM_GPT_SYSTEM_INSTRUCTIONS.md`
- **Cricket Data Schema**: `DOCS/CRICKET_ODI_T20_DATA_SCHEMA.yaml`
- **Cycling Data Schema**: `DOCS/CYCLING_TOUR_DE_FRANCE_SCHEMA.yaml`

### Custom GPT Configuration

1. **Create New Action**:
   - Use `CUSTOM_GPT_ACTION_SCHEMA.json` as the action schema
   - Update the server URL in the schema to your deployed endpoint
   - Set authentication method to "API Key" with "Bearer" type
   - Use the same API key from your `.env` file

2. **Upload Knowledge Base**:
   - Upload `CRICKET_ODI_T20_DATA_SCHEMA.yaml` for cricket data analysis
   - Upload `CYCLING_TOUR_DE_FRANCE_SCHEMA.yaml` for cycling data analysis

3. **Set System Instructions**:
   - Use `CUSTOM_GPT_SYSTEM_INSTRUCTIONS.md` as the system prompt
   - This enables natural language querying of your databases

### Available Datasets

- **Cricket Data**: ODI and T20 match data (ball-by-ball)
- **Cycling Data**: Tour de France rider and stage history
- **Custom Tables**: Any tables in your connected databases

## Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `API_KEY` | Yes | Bearer token for API authentication | - |
| `AIVEN_POSTGRES` | No | Aiven PostgreSQL connection string | - |
| `AIVEN_MYSQL` | No | Aiven MySQL connection string | - |
| `NEON_POSTGRES` | No | Neon PostgreSQL connection string | - |
| `SUPABASE_POSTGRES` | No | Supabase PostgreSQL connection string | - |
| `RATE_LIMIT` | No | Rate limit (e.g., "100/hour") | "100/hour" |
| `MAX_JSON_ROWS` | No | JSON response row limit | 10000 |
| `MAX_CSV_ROWS` | No | CSV response row limit | 1000000 |
| `LOG_LEVEL` | No | Logging level (DEBUG, INFO, WARNING, ERROR) | DEBUG |
| `CORS_ALLOW_ORIGINS` | No | Allowed CORS origins | "*" |
| `DB_POOL_MIN_SIZE` | No | Minimum connection pool size | 1 |
| `DB_POOL_MAX_SIZE` | No | Maximum connection pool size | 4 |

## Architecture

### Database Connection Management
- **Direct connections** using `asyncpg` (PostgreSQL) and `aiomysql` (MySQL)
- **Connection pooling** with configurable pool sizes
- **Read-only mode** for PostgreSQL connections
- **Statement cache disabled** for PgBouncer compatibility

### Security Features
- **Bearer token authentication** with constant-time comparison
- **Rate limiting** with SlowAPI (per-IP + global)
- **Per-IP and global concurrency controls** with asyncio.shield leak protection
- **Full SQL validation stack**: prefix allowlist, keyword blocklist, system catalog blocking (PostgreSQL + MySQL), subquery depth limit, ORDER BY function validation
- **Auto-append LIMIT** if query doesn't have one
- **Read-only enforcement** on all PostgreSQL connections
- **Statement timeout** (30 seconds)
- **Error sanitization** — no stack traces or internal details leaked
- **Global exception handler** as safety net
- **Cloudflare-aware IP extraction** for accurate rate limiting

### Response Handling
- **JSON responses** with custom serialization for dates/decimals
- **CSV responses** with temporary file generation and cleanup
- **Row limits** to prevent memory issues
- **Truncation flags** when limits are exceeded

## Production Deployment

### Environment-Specific Configuration
- Use `.env.production` for production settings
- Set `LOG_LEVEL=INFO` in production
- Configure proper CORS origins
- Use strong, unique API keys
- Monitor connection pool usage

### Security Considerations
- Restrict CORS origins to your actual domains
- Use read-only database users when possible
- Monitor logs for suspicious activity
- Set appropriate rate limits based on usage
- Enable HTTPS in production

## Security Hardening

| # | Layer | What It Does |
|---|-------|-------------|
| 1 | Bearer token auth | All endpoints require `Authorization: Bearer` header with timing-safe comparison |
| 2 | Fail-closed auth | If `API_KEY` env var is missing, app refuses to start |
| 3 | SQL prefix allowlist | Only SELECT, SHOW, DESCRIBE, EXPLAIN, WITH queries allowed |
| 4 | SQL keyword blocklist | INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, EXEC, COPY, and 15+ more blocked |
| 5 | SQL comment rejection | Block `--` and `/*` to prevent comment-based injection bypass |
| 6 | Postgres catalog blocking | pg_catalog, information_schema, pg_shadow, pg_stat, system functions blocked |
| 7 | MySQL catalog blocking | mysql.user, INFORMATION_SCHEMA, performance_schema blocked |
| 8 | Auto-append LIMIT | Queries without an outer LIMIT automatically get LIMIT 1000 |
| 9 | Subquery depth limit | Max 3 SELECT keywords per query (main + 2 subqueries) |
| 10 | ORDER BY validation | Function calls in ORDER BY blocked except whitelisted aggregates |
| 11 | Per-IP rate limiting | 30 requests/minute per IP via SlowAPI |
| 12 | Global rate limiting | 200 requests/minute across all IPs combined |
| 13 | Per-IP concurrency cap | Max 3 simultaneous in-flight queries per IP |
| 14 | Global concurrency cap | Max 6 simultaneous queries server-wide |
| 15 | Concurrency leak protection | `asyncio.shield` on counter release prevents permanent lockout |
| 16 | Read-only sessions | PostgreSQL connections enforce read-only transactions |
| 17 | Statement timeout | 30-second timeout on all database connections |
| 18 | CORS credentials disabled | `allow_origins=["*"]` with `allow_credentials=False` |
| 19 | Error sanitization | Internal errors return generic messages — no stack traces leaked |
| 20 | Global exception handler | Catches unhandled exceptions as safety net |
| 21 | Cloudflare IP extraction | Real client IP from `cf-connecting-ip`, `x-forwarded-for` for accurate rate limiting |

## API Monitoring

All requests are logged via [tigzig-api-monitor](https://pypi.org/project/tigzig-api-monitor/), an open-source centralized logging middleware for FastAPI. The middleware captures request metadata including client IP addresses and request bodies for API monitoring and error tracking.

**Data Retention**: The middleware captures data but does not manage its lifecycle. It is the deployer's responsibility to implement appropriate data retention and deletion policies in accordance with their own compliance requirements (GDPR, CCPA, etc.).

**Graceful Degradation**: If the logging service is unavailable, API calls proceed normally — logging fails silently without affecting functionality.

## License

See [LICENSE](LICENSE) file for details.

## Author

Built by [Amar Harolikar](https://www.linkedin.com/in/amarharolikar/)

Explore 30+ open source AI tools for analytics, databases & automation at [tigzig.com](https://tigzig.com)
