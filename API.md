# API Documentation

Base URL: `http://localhost/api` (or `http://localhost:8000/api` for direct backend access)

## Interactive API Documentation

FastAPI provides automatic interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Endpoints

### Health Check

#### `GET /health`
Check if the service is running

**Response:**
```json
{
  "status": "healthy",
  "service": "DMARC Report Processor"
}
```

---

### Reports

#### `GET /api/reports`
Get paginated list of reports with optional filters

**Query Parameters:**
- `page` (int, default: 1) - Page number (1-indexed)
- `page_size` (int, default: 20, max: 100) - Results per page
- `domain` (string, optional) - Filter by domain
- `start_date` (datetime, optional) - Filter reports starting from this date
- `end_date` (datetime, optional) - Filter reports ending before this date

**Example Request:**
```bash
curl "http://localhost/api/reports?page=1&page_size=10&domain=example.com"
```

**Response:**
```json
{
  "reports": [
    {
      "id": 1,
      "report_id": "12345678901234567890",
      "org_name": "Google Inc.",
      "email": "noreply-dmarc-support@google.com",
      "date_begin": "2021-01-01T00:00:00",
      "date_end": "2021-01-02T00:00:00",
      "domain": "example.com",
      "p": "quarantine",
      "total_records": 2,
      "pass_count": 1,
      "fail_count": 1
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 10
}
```

#### `GET /api/reports/{id}`
Get detailed report by ID including all records

**Path Parameters:**
- `id` (int) - Report database ID

**Example Request:**
```bash
curl "http://localhost/api/reports/1"
```

**Response:**
```json
{
  "id": 1,
  "report_id": "12345678901234567890",
  "org_name": "Google Inc.",
  "domain": "example.com",
  "records": [
    {
      "id": 1,
      "source_ip": "192.0.2.1",
      "count": 5,
      "disposition": "none",
      "dkim_result": "pass",
      "spf_result": "pass"
    }
  ]
}
```

---

### Statistics

#### `GET /api/stats/summary`
Get overall statistics summary

**Query Parameters:**
- `start_date` (datetime, optional) - Filter from this date
- `end_date` (datetime, optional) - Filter to this date

**Example Request:**
```bash
curl "http://localhost/api/stats/summary"
```

**Response:**
```json
{
  "total_reports": 150,
  "total_messages": 50000,
  "pass_rate": 85.5,
  "fail_rate": 14.5
}
```

#### `GET /api/stats/by-date`
Get statistics grouped by date

**Query Parameters:**
- `start_date` (datetime, optional) - Start date
- `end_date` (datetime, optional) - End date
- `limit` (int, default: 30, max: 365) - Number of days

**Example Request:**
```bash
curl "http://localhost/api/stats/by-date?limit=7"
```

**Response:**
```json
[
  {
    "date": "2021-01-01",
    "pass_count": 1000,
    "fail_count": 100,
    "total_count": 1100
  },
  {
    "date": "2021-01-02",
    "pass_count": 1200,
    "fail_count": 80,
    "total_count": 1280
  }
]
```

#### `GET /api/stats/by-domain`
Get statistics grouped by domain

**Query Parameters:**
- `start_date` (datetime, optional) - Start date
- `end_date` (datetime, optional) - End date
- `limit` (int, default: 10, max: 100) - Number of domains

**Example Request:**
```bash
curl "http://localhost/api/stats/by-domain?limit=5"
```

**Response:**
```json
[
  {
    "domain": "example.com",
    "pass_count": 5000,
    "fail_count": 500,
    "total_count": 5500
  },
  {
    "domain": "test.com",
    "pass_count": 3000,
    "fail_count": 200,
    "total_count": 3200
  }
]
```

#### `GET /api/stats/by-source-ip`
Get top source IPs by message count

**Query Parameters:**
- `start_date` (datetime, optional) - Start date
- `end_date` (datetime, optional) - End date
- `limit` (int, default: 10, max: 100) - Number of IPs

**Example Request:**
```bash
curl "http://localhost/api/stats/by-source-ip?limit=10"
```

**Response:**
```json
[
  {
    "source_ip": "192.0.2.1",
    "count": 10000
  },
  {
    "source_ip": "203.0.113.5",
    "count": 5000
  }
]
```

---

### Ingest

#### `POST /api/ingest/trigger`
Manually trigger email ingest process

**Query Parameters:**
- `limit` (int, default: 50, max: 200) - Max emails to check

**Example Request:**
```bash
curl -X POST "http://localhost/api/ingest/trigger?limit=50"
```

**Response:**
```json
{
  "message": "Ingest completed successfully",
  "reports_processed": 5,
  "emails_checked": 10
}
```

**Error Responses:**
- `400` - Email credentials not configured
- `503` - Email server connection failed
- `500` - Ingest process failed

---

## Date Format

All datetime fields use ISO 8601 format:
```
2021-01-01T00:00:00
```

Query parameters can be passed as:
```
?start_date=2021-01-01T00:00:00
```

## Error Responses

All errors follow this format:
```json
{
  "detail": "Error message description"
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `404` - Not Found (resource doesn't exist)
- `422` - Validation Error (invalid data format)
- `500` - Internal Server Error
- `503` - Service Unavailable (e.g., email server unreachable)

## Rate Limiting

Currently no rate limiting is implemented. For production, consider adding:
- API key authentication
- Rate limiting middleware
- Request throttling

## CORS

CORS is enabled for all origins (`*`) for development. For production, configure specific allowed origins in `.env`:

```env
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```
