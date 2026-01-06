# DMARC Aggregate Report Processor

A production-ready MVP that ingests DMARC aggregate reports (RUA) from an email inbox, parses them, stores normalized results, and serves a dashboard with API.

## Features

- 📧 Automated DMARC report ingestion from IMAP inbox
- 🔄 Idempotent processing (avoids duplicates)
- 💾 PostgreSQL storage for parsed reports
- 🚀 RESTful API with FastAPI
- 📊 Interactive dashboard with visualizations
- ✅ Comprehensive test coverage
- 🐳 Single-command deployment with Docker Compose

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

- `GET /api/reports` - List all reports with pagination
- `GET /api/reports/{id}` - Get specific report details
- `GET /api/stats/by-domain` - Statistics grouped by domain
- `GET /api/stats/by-date` - Statistics grouped by date
- `GET /api/stats/by-source-ip` - Top source IPs
- `POST /api/ingest/trigger` - Manually trigger email ingest

## Running Tests

```bash
# Run all tests
docker compose exec backend pytest

# Run with coverage
docker compose exec backend pytest --cov=app

# Run specific test types
docker compose exec backend pytest tests/unit/
docker compose exec backend pytest tests/integration/
```

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
├── backend/           # FastAPI application
├── frontend/          # Dashboard UI
├── nginx/             # Web server config
├── docker-compose.yml # Service orchestration
└── .env.sample        # Environment template
```

## License

MIT
