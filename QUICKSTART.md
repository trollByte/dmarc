# Quick Start Guide

Get the DMARC Report Processor running in under 5 minutes!

## Prerequisites

- Docker Desktop installed and running
- Git (optional, for cloning)
- Email account with DMARC reports (Gmail, Outlook, etc.)

## Step-by-Step Setup

### 1. Get the Code

```bash
# If you have the code already
cd dmarc

# Or clone from repository
git clone <repository-url>
cd dmarc
```

### 2. Configure Email Credentials

```bash
# Copy the sample environment file
cp .env.sample .env
```

Edit `.env` file with your email details:

```env
# For Gmail
EMAIL_HOST=imap.gmail.com
EMAIL_PORT=993
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_FOLDER=INBOX

# For Outlook/Office 365
EMAIL_HOST=outlook.office365.com
EMAIL_PORT=993
EMAIL_USER=your-email@outlook.com
EMAIL_PASSWORD=your-password
EMAIL_FOLDER=INBOX
```

#### Gmail Setup
1. Enable 2-Factor Authentication
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Use the 16-character app password in `.env`

#### Outlook/Office 365 Setup
1. Use your regular email password
2. If using 2FA, generate an app password

### 3. Start the Application

```bash
docker compose up -d
```

This will:
- Download required Docker images
- Build the backend application
- Start PostgreSQL database
- Start FastAPI backend
- Start Nginx web server

Wait about 30-60 seconds for all services to start.

### 4. Verify It's Running

```bash
# Check service status
docker compose ps

# You should see three services running:
# - dmarc-db (PostgreSQL)
# - dmarc-backend (FastAPI)
# - dmarc-nginx (Nginx)
```

### 5. Access the Dashboard

Open your browser and go to:

**Dashboard**: http://localhost

You should see the DMARC Report Dashboard.

### 6. Ingest Your First Reports

Click the **"🔄 Trigger Ingest"** button in the dashboard.

This will:
1. Connect to your email inbox
2. Search for DMARC report emails
3. Download and parse attachments
4. Store reports in the database
5. Update the dashboard

### 7. Explore the Data

After ingestion completes:

- View summary statistics in the cards at top
- Check the time series chart for trends
- See domain breakdown
- View top source IPs
- Browse the reports table

## What's Next?

### View API Documentation

Interactive API docs with all endpoints:

**Swagger UI**: http://localhost:8000/docs

Try out the API endpoints directly in your browser!

### Run Tests

Verify everything is working correctly:

```bash
docker compose exec backend pytest -v
```

You should see all 20 tests passing (13 unit + 7 integration).

### View Logs

Monitor what's happening:

```bash
# All services
docker compose logs -f

# Just backend
docker compose logs -f backend

# Just database
docker compose logs -f db
```

### Schedule Automatic Ingest

For automatic processing every 6 hours:

**Linux/Mac:**
```bash
# Add to crontab
0 */6 * * * curl -X POST http://localhost/api/ingest/trigger
```

**Windows:**
Create a scheduled task or use PowerShell:
```powershell
Invoke-WebRequest -Method POST -Uri "http://localhost/api/ingest/trigger"
```

## Common Issues

### Port Already in Use

If port 80 is already in use, edit `docker-compose.yml`:

```yaml
nginx:
  ports:
    - "8080:80"  # Use port 8080 instead
```

Then access dashboard at http://localhost:8080

### Email Connection Failed

1. Check your credentials in `.env`
2. Verify IMAP is enabled in your email account
3. For Gmail, make sure you're using an App Password
4. Check the logs: `docker compose logs backend`

### No Reports Found

Make sure you have DMARC reports in your inbox. Subject lines typically contain:
- "Report Domain:"
- "DMARC"

Create a folder and set up email filters to collect DMARC reports.

### Database Issues

Reset the database:

```bash
docker compose down -v
docker compose up -d
```

This will remove all data and start fresh.

## Stopping the Application

```bash
# Stop but keep data
docker compose down

# Stop and remove all data
docker compose down -v
```

## Getting Help

1. Check the logs: `docker compose logs -f`
2. Read the full documentation:
   - [README.md](README.md) - Overview
   - [API.md](API.md) - API reference
   - [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment
   - [TESTING.md](TESTING.md) - Testing guide
3. Open an issue on GitHub

## Updating

Pull the latest changes:

```bash
git pull
docker compose up --build -d
```

## Backup Your Data

```bash
# Create backup
docker compose exec db pg_dump -U dmarc dmarc > backup.sql

# Restore backup
docker compose exec -T db psql -U dmarc dmarc < backup.sql
```

## Summary of Commands

```bash
# Start
docker compose up -d

# View logs
docker compose logs -f

# Run tests
docker compose exec backend pytest

# Stop
docker compose down

# Reset everything
docker compose down -v && docker compose up -d

# Backup database
docker compose exec db pg_dump -U dmarc dmarc > backup.sql
```

That's it! You now have a fully functional DMARC report processor running locally.
