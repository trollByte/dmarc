# DMARC Aggregate Report Processor

A production-ready MVP that ingests DMARC aggregate reports (RUA) from an email inbox, parses them, stores normalized results, and serves a dashboard with API.

## Features

- 📧 Automated DMARC report ingestion from IMAP inbox
- 📤 Bulk file upload (50-200 reports via drag-and-drop)
- 🔄 Idempotent processing (avoids duplicates)
- 💾 PostgreSQL storage for parsed reports
- 🔒 API key authentication & rate limiting
- 🚀 RESTful API with FastAPI
- 📊 Interactive dashboard with visualizations
- ✅ Comprehensive test coverage (70%+ enforced)
- 🐳 Single-command deployment with Docker Compose
- 🔔 Multi-channel alerting (Email, Slack, Discord, Teams)

## Tech Stack

- **Backend**: Python 3.11 + FastAPI
- **Database**: PostgreSQL 15
- **Frontend**: Vanilla HTML/JS + Chart.js
- **Web Server**: Nginx
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
   docker compose up
   ```

4. **Access the application**
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
```

**Note**: For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833).

## API Endpoints

### Core Endpoints
- `GET /api/domains` - List all domains with report counts
- `GET /api/reports` - List all reports with pagination
- `GET /api/rollup/summary` - Aggregate summary statistics
- `GET /api/rollup/sources` - Top source IPs analysis
- `GET /api/rollup/alignment` - DKIM/SPF alignment statistics

### Upload & Triggers
- `POST /api/upload` - Bulk upload DMARC report files (requires API key)
- `POST /api/trigger/email-ingestion` - Manually trigger email ingestion (requires API key)
- `POST /api/trigger/process-reports` - Process pending reports (requires API key)

### Utilities
- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

**Note**: Protected endpoints require `X-API-Key` header in production.

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

# Reset database
docker compose down -v
docker compose up
```

## Project Structure

```
dmarc/
├── backend/
│   ├── app/                  # FastAPI application
│   ├── tests/                # Test suite
│   ├── DEPLOYMENT.md         # Production deployment guide
│   └── TESTING.md            # Testing documentation
├── frontend/                 # Dashboard UI
├── nginx/                    # Web server config
├── .github/workflows/        # CI/CD pipelines
├── docker-compose.yml        # Service orchestration
└── .env.sample              # Environment template
```

## Production Deployment

For production deployment with security hardening, SSL/TLS, backups, and monitoring:

**See [`backend/DEPLOYMENT.md`](backend/DEPLOYMENT.md)** for the complete production deployment guide.

Key production features:
- 🔐 API key authentication
- ⏱️ Rate limiting (upload: 20/hour, API: 100/min)
- 🔒 SSL/TLS with Let's Encrypt
- 🛡️ Security headers and CORS configuration
- 🔔 Multi-channel alerting
- 💾 Automated database backups
- 📊 Health monitoring
- 🔑 Optional basic auth for dashboard

## Documentation

- **[DEPLOYMENT.md](backend/DEPLOYMENT.md)** - Production deployment guide
- **[TESTING.md](backend/TESTING.md)** - Testing and QA documentation
- **[API Docs](http://localhost:8000/docs)** - Interactive API documentation (when running)

## License

MIT
