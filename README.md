# Lyftr AI — Backend Assignment

A production-ready FastAPI webhook service that ingests WhatsApp-like messages with HMAC-SHA256 signature verification, provides paginated message retrieval, analytics, and comprehensive observability.

## 🎯 Features

### Core Functionality
- ✅ **POST /webhook** - HMAC-SHA256 verified message ingestion
  - Signature verification using `X-Signature` header
  - Idempotent ingestion (SQLite PRIMARY KEY on `message_id`)
  - E.164 phone number validation
  - Returns 401 for invalid signature, 422 for validation errors
  - Structured JSON logging with `message_id`, `dup`, and `result` fields

- ✅ **GET /messages** - Paginated message retrieval
  - Pagination: `limit` (1-100, default 50), `offset` (0+, default 0)
  - Filters: `from` (exact match), `since` (ISO timestamp), `q` (text search)
  - Deterministic ordering: `ORDER BY ts ASC, message_id ASC` (oldest first)
  - Returns `data`, `total`, `limit`, `offset`

- ✅ **GET /stats** - Analytics endpoint
  - `total_messages`: Total message count
  - `senders_count`: Unique senders count
  - `messages_per_sender`: Top 10 senders (sorted by count DESC, from ASC)
  - `first_message_ts` and `last_message_ts`

- ✅ **Health Endpoints**
  - `GET /health/live` - Always 200 when server is running
  - `GET /health/ready` - 200 only if DB reachable and `WEBHOOK_SECRET` set, else 503

- ✅ **GET /metrics** - Prometheus metrics
  - `http_requests_total{path,status}` - HTTP request counter
  - `webhook_requests_total{result}` - Webhook processing counter
  - `request_latency_ms` - Request latency histogram

### Infrastructure
- ✅ 12-factor app configuration (environment variables)
- ✅ Structured JSON logging (one line per request)
- ✅ SQLite with volume persistence at `/data/app.db`
- ✅ Docker + Docker Compose deployment
- ✅ Comprehensive test suite

## 📁 Project Structure

```
/app
    main.py              # FastAPI app, middleware, routes
    models.py            # Pydantic models with E.164 validation
    storage.py           # SQLite operations
    logging_utils.py     # JSON logger with webhook-specific fields
    metrics.py           # Prometheus metrics helpers
    config.py            # Environment variable loading
/tests
    test_webhook.py      # Webhook tests (signature, idempotency)
    test_messages.py     # Pagination + filters tests
    test_stats.py        # Stats correctness tests
Dockerfile
docker-compose.yml
Makefile
README.md
```

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# Set environment variable
export WEBHOOK_SECRET="testsecret"

# Start the service
make up

# Check health
curl http://localhost:8000/health/ready

# View logs
make logs

# Stop the service
make down
```

### Manual Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export WEBHOOK_SECRET="testsecret"
export DATABASE_PATH="/data/app.db"

# Run the application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📚 API Documentation

### POST /webhook

Ingest messages with HMAC-SHA256 signature verification.

**Headers:**
- `Content-Type: application/json`
- `X-Signature: <hex HMAC-SHA256 of raw request body>`

**Request Body:**
```json
{
  "message_id": "m1",
  "from": "+919876543210",
  "to": "+14155550100",
  "ts": "2025-01-15T10:00:00Z",
  "text": "Hello"
}
```

**Validation:**
- `message_id`: Non-empty string
- `from` / `to`: E.164 format (starts with `+`, then digits only)
- `ts`: ISO-8601 UTC string with Z suffix
- `text`: Optional, max 4096 characters

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

**Error Responses:**
- `401` - Invalid or missing signature: `{"detail": "invalid signature"}`
- `422` - Validation error (invalid payload)

**Idempotency:**
- First valid request: Inserts row, returns 200
- Duplicate requests (same `message_id`): No insert, still returns 200

### GET /messages

List stored messages with pagination and filters.

**Query Parameters:**
- `limit` (optional, int): Default 50, Min 1, Max 100
- `offset` (optional, int): Default 0, Min 0
- `from` (optional, string): Filter by sender (exact match)
- `since` (optional, string): ISO-8601 UTC timestamp filter
- `q` (optional, string): Free-text search in `text` field

**Ordering:** `ORDER BY ts ASC, message_id ASC` (oldest first, deterministic)

**Response (200 OK):**
```json
{
  "data": [
    {
      "message_id": "m1",
      "from": "+919876543210",
      "to": "+14155550100",
      "ts": "2025-01-15T09:00:00Z",
      "text": "Earlier message",
      "created_at": "2025-01-15T09:00:01Z"
    }
  ],
  "total": 4,
  "limit": 50,
  "offset": 0
}
```

### GET /stats

Provide message-level analytics.

**Response (200 OK):**
```json
{
  "total_messages": 123,
  "senders_count": 10,
  "messages_per_sender": [
    { "from": "+919876543210", "count": 50 },
    { "from": "+911234567890", "count": 30 }
  ],
  "first_message_ts": "2025-01-10T09:00:00Z",
  "last_message_ts": "2025-01-15T10:00:00Z"
}
```

**Notes:**
- `messages_per_sender`: Top 10 senders, sorted by count DESC, then from ASC
- Timestamps are null if no messages exist

### GET /health/live

Liveness probe - always returns 200 when server is running.

**Response (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2025-01-15T10:00:00Z"
}
```

### GET /health/ready

Readiness probe - returns 200 only if DB is reachable and `WEBHOOK_SECRET` is set.

**Response (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2025-01-15T10:00:00Z",
  "database": "connected"
}
```

**Response (503 Service Unavailable):**
```json
{
  "detail": "WEBHOOK_SECRET not set"
}
```
or
```json
{
  "detail": "Database not ready"
}
```

### GET /metrics

Prometheus-style metrics endpoint.

**Response (200 OK):**
```
# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total{path="/webhook",status="200"} 15
http_requests_total{path="/webhook",status="401"} 2

# HELP webhook_requests_total Total number of webhook requests
# TYPE webhook_requests_total counter
webhook_requests_total{result="created"} 10
webhook_requests_total{result="duplicate"} 5
webhook_requests_total{result="invalid_signature"} 2
webhook_requests_total{result="validation_error"} 1

# HELP request_latency_ms Request latency in milliseconds
# TYPE request_latency_ms histogram
request_latency_ms_bucket{path="/webhook",le="100"} 20
request_latency_ms_bucket{path="/webhook",le="500"} 25
...
```

## 🔐 Security: HMAC-SHA256 Signature

### Signature Generation

```python
import hmac
import hashlib
import json

payload = {"message_id": "m1", "from": "+919876543210", ...}
secret = "testsecret"

signature = hmac.new(
    secret.encode(),
    json.dumps(payload, separators=(',', ':')).encode(),
    hashlib.sha256
).hexdigest()
```

### Sending Request

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: <computed_signature>" \
  -d '{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
```

## 📊 Structured JSON Logs

Every request produces a JSON log line with:

**Standard fields:**
- `ts`: Server time (ISO-8601)
- `level`: Log level
- `request_id`: Unique per request
- `method`: HTTP method
- `path`: Request path
- `status`: HTTP status code
- `latency_ms`: Request duration

**Webhook-specific fields:**
- `message_id`: Message identifier
- `dup`: Boolean (true if duplicate)
- `result`: One of `"created"`, `"duplicate"`, `"invalid_signature"`, `"validation_error"`

**Example:**
```json
{
  "ts": "2025-01-15T10:00:00.123Z",
  "level": "INFO",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "POST",
  "path": "/webhook",
  "status": 200,
  "latency_ms": 45.23,
  "message_id": "m1",
  "dup": false,
  "result": "created"
}
```

## 🗄️ Database Schema

```sql
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    from_msisdn TEXT NOT NULL,
    to_msisdn TEXT NOT NULL,
    ts TEXT NOT NULL,
    text TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_from_msisdn ON messages(from_msisdn);
CREATE INDEX idx_ts ON messages(ts);
CREATE INDEX idx_created_at ON messages(created_at);
```

## ⚙️ Configuration

All configuration via environment variables (12-factor app):

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBHOOK_SECRET` | *(required)* | HMAC secret for signature verification |
| `DATABASE_PATH` | `/data/app.db` | SQLite database file path |
| `DATABASE_URL` | `sqlite:////data/app.db` | Database URL |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMAT` | `json` | Log format (json or text) |
| `DEFAULT_PAGE_LIMIT` | `50` | Default pagination limit |
| `MAX_PAGE_LIMIT` | `100` | Maximum pagination limit |
| `ENABLE_METRICS` | `true` | Enable Prometheus metrics endpoint |

## 🧪 Testing

```bash
# Run all tests
make test

# Or directly with pytest
pytest tests/ -v

# Run specific test file
pytest tests/test_webhook.py -v
```

**Test Coverage:**
- Webhook: Signature verification, E.164 validation, idempotency
- Messages: Pagination, filtering, ordering
- Stats: Counts, top senders, timestamps

## 🛠️ Makefile Targets

```bash
make up     # Start services with Docker Compose (docker compose up -d --build)
make down   # Stop services and remove volumes (docker compose down -v)
make logs   # View service logs (docker compose logs -f api)
make test   # Run tests (pytest tests/ -v)
```

## 📈 Design Decisions

### 1. HMAC Signature Implementation

**Approach:** HMAC-SHA256 with constant-time comparison

**Rationale:**
- Industry-standard webhook security
- `hmac.compare_digest()` prevents timing attacks
- Signature computed on raw request body bytes (exact match)

**Trade-offs:**
- ✅ Secure against unauthorized requests
- ✅ Prevents replay attacks (when combined with timestamp validation)
- ❌ Requires shared secret management

### 2. Pagination Model

**Approach:** Offset-based pagination with deterministic ordering

**Ordering:** `ORDER BY ts ASC, message_id ASC`
- Primary sort: `ts` (timestamp) in ascending order (oldest first)
- Secondary sort: `message_id` for deterministic ordering when timestamps are equal

**Rationale:**
- Simple to implement and understand
- Stateless (no cursor state to manage)
- Deterministic ordering prevents duplicates/missing items during pagination

**Trade-offs:**
- ✅ Jump to arbitrary page
- ✅ Consistent results
- ❌ Slower for large offsets (use cursor-based for >100K records)

### 3. Stats Computation

**Approach:** SQL aggregation with in-database sorting

**Implementation:**
```sql
SELECT from_msisdn, COUNT(*) as count
FROM messages
GROUP BY from_msisdn
ORDER BY count DESC, from_msisdn ASC
LIMIT 10
```

**Rationale:**
- Efficient for moderate datasets (<1M messages)
- Deterministic ordering (count DESC, then from ASC)
- Single query for all stats

**Trade-offs:**
- ✅ Fast for <100K messages
- ✅ Accurate real-time stats
- ❌ May need caching for >1M messages

### 4. Metrics Names

**Chosen metrics:**
- `http_requests_total{path,status}` - Standard HTTP metric
- `webhook_requests_total{result}` - Domain-specific metric
- `request_latency_ms` - Latency histogram in milliseconds

**Rationale:**
- Follows Prometheus naming conventions
- `result` label enables tracking of business outcomes
- Millisecond buckets match typical API latencies

## 🐳 Docker Deployment

### Build and Run

```bash
# Build image
docker build -t lyftr-webhook .

# Run container
docker run -d \
  -p 8000:8000 \
  -e WEBHOOK_SECRET=testsecret \
  -v webhook-data:/data \
  lyftr-webhook
```

### Docker Compose

```bash
# Start
docker compose up -d --build

# Check logs
docker compose logs -f api

# Stop
docker compose down -v
```

## 📝 Setup Used

**Development Environment:**
- VSCode + Cursor
- ChatGPT + Antigravity AI for code generation and assistance
- Docker Desktop for containerization
- pytest for testing

## 🎯 Requirements Compliance

✅ **All PDF requirements implemented:**
- POST /webhook with HMAC-SHA256 verification
- E.164 phone number validation
- Idempotent ingestion (SQLite PRIMARY KEY)
- GET /messages with pagination and filters
- Deterministic ordering (ts ASC, message_id ASC)
- GET /stats with top 10 senders
- Health endpoints (/health/live, /health/ready)
- Prometheus /metrics endpoint
- Structured JSON logging with webhook-specific fields
- 12-factor configuration
- Docker + Docker Compose deployment
- Comprehensive test suite

## 📞 Support

For issues or questions:
1. Check logs: `make logs`
2. Verify health: `curl http://localhost:8000/health/ready`
3. Run tests: `make test`
4. Review this README for API details

## 📄 License

Created for the Lyftr AI Backend Assignment.

---

**Author:** Pratham Jindal - Submission for Lyftr AI Backend Assignment
**Date:** December 2025
**Version:** 1.0.0
