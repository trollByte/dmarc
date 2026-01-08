# DMARC Aggregate Report Processor

A production-ready MVP that ingests DMARC aggregate reports (RUA) from an email inbox, parses them, stores normalized results, and serves a dashboard with API.

## Features

### Core Functionality
- 📧 Automated DMARC report ingestion from IMAP inbox
- 📤 Bulk file upload (50-200 reports via drag-and-drop)
- 🔄 Idempotent processing (avoids duplicates)
- 💾 PostgreSQL storage for parsed reports
- 🔒 API key authentication & rate limiting
- 🚀 RESTful API with FastAPI
- ✅ Comprehensive test coverage (70%+ enforced)
- 🐳 Single-command deployment with Docker Compose
- 🔔 Multi-channel alerting (Email, Slack, Discord, Teams)

### Performance & Caching
- ⚡ Redis caching with 90%+ hit rate
- 🔧 Optimized database queries (N+1 query elimination)
- 📈 Sub-200ms API response times with caching
- 🔄 Automatic cache invalidation on new data

### Visualizations
- 📊 Interactive dashboard with 8 chart types:
  - DMARC results timeline (line chart)
  - Results by domain (bar chart)
  - Top source IPs (bar chart)
  - Disposition breakdown (pie chart)
  - **SPF/DKIM alignment breakdown (stacked bar)**
  - **Policy compliance (doughnut chart)**
  - **Failure rate trend with moving average (line chart)**
  - **Top sending organizations (horizontal bar)**

### Advanced Filtering
- 🔍 Filter by source IP (exact match or CIDR ranges)
- 🔐 Filter by authentication results (DKIM/SPF pass/fail)
- 📋 Filter by disposition (none/quarantine/reject)
- 🏢 Filter by sending organization
- 📅 Date range filtering (custom or preset)
- 🌐 Domain filtering

### Export Capabilities
- 📄 **CSV exports** (reports, records, sources)
- 📑 **PDF summary reports** with charts and tables
- 🔒 Rate-limited export endpoints (10/min CSV, 5/min PDF)
- 🛡️ CSV formula injection prevention
- 📊 Exports respect all active filters

## Tech Stack

- **Backend**: Python 3.11 + FastAPI
- **Database**: PostgreSQL 15
- **Cache**: Redis 7 (Alpine)
- **Frontend**: Vanilla HTML/JS + Chart.js v4.4.0
- **Web Server**: Nginx
- **PDF Generation**: ReportLab
- **Orchestration**: Docker Compose

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd dmarc
   ```

2. **Configure environment**
   ```bash
   cp .env.sample .env
   # Edit .env with your email credentials
   ```

3. **Start the application**
   ```bash
   docker compose up -d
   ```

4. **Run database migrations** (required for first-time setup)
   ```bash
   docker compose exec backend alembic upgrade head
   ```

   This creates all necessary database tables and indexes. You should see:
   ```
   INFO  [alembic.runtime.migration] Running upgrade -> 001
   INFO  [alembic.runtime.migration] Running upgrade 001 -> 002
   INFO  [alembic.runtime.migration] Running upgrade 002 -> 003
   ```

5. **Access the application**
   - Dashboard: http://localhost
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost/health

## Configuration

Edit `.env` file with your settings:

```env
# Email IMAP Configuration
EMAIL_HOST=imap.gmail.com
EMAIL_PORT=993
EMAIL_USER=your-email@example.com
EMAIL_PASSWORD=your-app-password
EMAIL_FOLDER=INBOX

# Database (default works with docker-compose)
DATABASE_URL=postgresql://dmarc:dmarc@db:5432/dmarc

# Redis Cache (default works with docker-compose)
REDIS_URL=redis://redis:6379/0
CACHE_ENABLED=true
CACHE_DEFAULT_TTL=300
```

**Note**: For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833).

## API Endpoints

### Core Endpoints
- `GET /api/domains` - List all domains with report counts
- `GET /api/reports` - List all reports with pagination
- `GET /api/reports/{id}` - Get detailed report information

### Rollup & Analytics
- `GET /api/rollup/summary` - Aggregate summary statistics
- `GET /api/rollup/sources` - Top source IPs analysis
- `GET /api/rollup/alignment` - DKIM/SPF alignment statistics
- `GET /api/rollup/timeline` - Time-series data for trend charts
- `GET /api/rollup/alignment-breakdown` - Authentication alignment breakdown (both pass, DKIM only, SPF only, both fail)
- `GET /api/rollup/failure-trend` - Daily failure rates with moving average
- `GET /api/rollup/top-organizations` - Top sending organizations by volume

### Export Endpoints
- `GET /api/export/reports/csv` - Export reports to CSV (requires API key, rate: 10/min)
- `GET /api/export/records/csv` - Export detailed records to CSV (requires API key, rate: 10/min, max 10K records)
- `GET /api/export/sources/csv` - Export source IP statistics to CSV (requires API key, rate: 10/min)
- `GET /api/export/report/pdf` - Generate comprehensive PDF summary report (requires API key, rate: 5/min)

### Upload & Triggers
- `POST /api/upload` - Bulk upload DMARC report files (requires API key)
- `POST /api/trigger/email-ingestion` - Manually trigger email ingestion (requires API key)
- `POST /api/trigger/process-reports` - Process pending reports (requires API key)

### Utilities
- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

**Note**: Protected endpoints require `X-API-Key` header. All endpoints support advanced filtering via query parameters (domain, date ranges, source IP, CIDR ranges, DKIM/SPF results, disposition, organization).

## Performance Optimizations

The system includes several performance optimizations for handling large datasets:

### Redis Caching
- **Cache hit rate**: 90%+ after warmup
- **TTL**: 5 minutes (configurable)
- **Strategy**: Pattern-based key generation with automatic invalidation
- **Graceful degradation**: System continues working if Redis is unavailable
- **Memory limit**: 256MB with LRU eviction policy

### Query Optimization
- **N+1 query elimination**: Timeline and alerting endpoints optimized
- **Aggregation queries**: Single JOIN queries replace iterative record loops
- **Expected performance**:
  - Timeline endpoint: ~800ms → <200ms
  - Alerting checks: ~1200ms → <300ms
  - Dashboard load: <1s with active cache

### Cache Invalidation
Automatic cache clearing on:
- New report uploads
- Report processing completion
- Data modifications

## Advanced Filtering

The dashboard and API support comprehensive filtering options:

### Filter Types
1. **Source IP Filtering**
   - Exact IP match: `?source_ip=192.168.1.100`
   - CIDR range: `?source_ip_range=192.168.1.0/24`

2. **Authentication Filters**
   - DKIM result: `?dkim_result=pass` or `fail`
   - SPF result: `?spf_result=pass` or `fail`

3. **Disposition Filter**
   - `?disposition=none|quarantine|reject`

4. **Organization Filter**
   - Case-insensitive search: `?org_name=google.com`

5. **Date Range Filters**
   - Preset ranges: `?days=7` (last 7 days)
   - Custom range: `?start=2024-01-01T00:00:00&end=2024-12-31T23:59:59`

6. **Domain Filter**
   - `?domain=example.com`

### Filter Combinations
All filters can be combined for precise queries:
```bash
# Example: Gmail IPs with failed SPF in last 30 days
GET /api/rollup/summary?org_name=google.com&spf_result=fail&days=30

# Example: Specific IP range with quarantine disposition
GET /api/rollup/sources?source_ip_range=10.0.0.0/8&disposition=quarantine
```

## Export Features

### CSV Exports
Three export types available:
- **Reports CSV**: Aggregated report metadata (report ID, org, domain, dates, message counts)
- **Records CSV**: Detailed record-level data (max 10,000 records per export)
- **Sources CSV**: Aggregated source IP statistics (total messages, pass/fail counts, percentages)

**Security**: CSV formula injection prevention (special characters prefixed with `'`)

### PDF Reports
Comprehensive summary reports including:
- Executive summary table (total reports, messages, pass/fail rates)
- Policy compliance pie chart (compliant vs non-compliant)
- Authentication alignment breakdown table
- Top source IPs table (top 10 by volume)
- Professional styling with ReportLab

**Features**:
- Respects all active filters
- Includes metadata (domain, date range, generation timestamp)
- Rate-limited to prevent abuse (5 requests/minute)

### Export Usage
```bash
# Export reports to CSV
curl -H "X-API-Key: your-key" "http://localhost:8000/api/export/reports/csv?days=30" -o reports.csv

# Generate PDF summary for specific domain
curl -H "X-API-Key: your-key" "http://localhost:8000/api/export/report/pdf?domain=example.com&days=90" -o summary.pdf
```

## Testing

The project includes comprehensive test coverage (70%+ enforced) with unit and integration tests.

### Quick Test Commands

```bash
# Run all tests with coverage
docker compose exec backend pytest -v --cov=app

# Run only unit tests (fast)
docker compose exec backend pytest tests/unit/ -v

# Run only integration tests
docker compose exec backend pytest tests/integration/ -v

# Generate HTML coverage report
docker compose exec backend pytest --cov=app --cov-report=html
```

### CI/CD

Tests run automatically on GitHub Actions for:
- All pushes to `main` and `develop` branches
- All pull requests
- Includes linting, security scans, and Docker builds

**For detailed testing documentation, see [`backend/TESTING.md`](backend/TESTING.md)**

## Development

```bash
# View logs
docker compose logs -f backend

# Rebuild after changes
docker compose up --build

# Stop services
docker compose down

# Reset database (WARNING: deletes all data)
docker compose down -v
docker compose up -d
docker compose exec backend alembic upgrade head

# Create a new migration (after model changes)
docker compose exec backend alembic revision --autogenerate -m "description"

# Check current migration version
docker compose exec backend alembic current

# View migration history
docker compose exec backend alembic history
```

### Database Migrations

The project uses Alembic for database schema management. Three migrations are included:

1. **001_create_ingested_reports.py** - Creates table for tracking ingested email reports
2. **002_create_dmarc_tables.py** - Creates main DMARC report and record tables
3. **003_add_performance_indexes.py** - Adds indexes for query optimization

**Important**: Always run migrations after:
- Fresh deployment
- Pulling updates that include new migrations
- Resetting the database

## Project Structure

```
dmarc/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py           # API endpoints (core, rollup, exports)
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── services/
│   │   │   ├── cache.py            # Redis caching service
│   │   │   ├── export_csv.py       # CSV export service
│   │   │   ├── export_pdf.py       # PDF generation service
│   │   │   ├── processing.py       # DMARC report processing
│   │   │   ├── email_ingestion.py  # IMAP email fetching
│   │   │   └── alerting.py         # Multi-channel alerting
│   │   ├── utils/
│   │   │   └── ip_utils.py         # IP address utilities (CIDR parsing)
│   │   └── config.py               # Application configuration
│   ├── tests/                      # Test suite
│   ├── DEPLOYMENT.md               # Production deployment guide
│   └── TESTING.md                  # Testing documentation
├── frontend/
│   ├── index.html                  # Dashboard HTML
│   ├── js/
│   │   └── app.js                  # Dashboard logic (8 charts, filters, exports)
│   └── css/
│       └── styles.css              # Dashboard styling
├── nginx/                          # Web server config
├── .github/workflows/              # CI/CD pipelines
├── docker-compose.yml              # Service orchestration (backend, db, redis, nginx)
└── .env.sample                     # Environment template
```

## Production Deployment

For production deployment with security hardening, SSL/TLS, backups, and monitoring:

**See [`backend/DEPLOYMENT.md`](backend/DEPLOYMENT.md)** for the complete production deployment guide.

### Key Production Features
- 🔐 API key authentication
- ⏱️ Rate limiting (upload: 20/hour, API: 100/min, exports: 5-10/min)
- 🔒 SSL/TLS with Let's Encrypt
- 🛡️ Security headers and CORS configuration
- 🔔 Multi-channel alerting (Email, Slack, Discord, Teams)
- 💾 Automated database backups
- 📊 Health monitoring
- 🔑 Optional basic auth for dashboard
- ⚡ Redis caching for performance
- 🛡️ CSV formula injection prevention
- 📊 Export rate limiting and API key validation

### System Requirements
- **CPU**: 2+ cores recommended
- **RAM**: 4GB minimum (database + Redis + backend)
- **Storage**: 10GB+ (depends on report volume)
- **Network**: HTTPS/TLS (Let's Encrypt or custom certificate)

### Container Architecture
```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│   Nginx     │────▶│   Backend    │────▶│ PostgreSQL │
│   (Port 80) │     │  (FastAPI)   │     │    (DB)    │
└─────────────┘     └──────┬───────┘     └────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Redis    │
                    │   (Cache)   │
                    └─────────────┘
```

## Documentation

- **[DEPLOYMENT.md](backend/DEPLOYMENT.md)** - Production deployment guide
- **[TESTING.md](backend/TESTING.md)** - Testing and QA documentation
- **[API Docs](http://localhost:8000/docs)** - Interactive API documentation (when running)

## License

MIT
