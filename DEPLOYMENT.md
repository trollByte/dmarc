# Deployment Guide

## Local Development

### Prerequisites
- Docker Desktop (Windows/Mac) or Docker + Docker Compose (Linux)
- Git

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd dmarc
   ```

2. **Configure environment**
   ```bash
   cp .env.sample .env
   ```

   Edit `.env` and add your email credentials:
   ```env
   EMAIL_HOST=imap.gmail.com
   EMAIL_PORT=993
   EMAIL_USER=your-email@example.com
   EMAIL_PASSWORD=your-app-password
   ```

   **For Gmail:**
   - Enable 2FA on your Google account
   - Generate an [App Password](https://support.google.com/accounts/answer/185833)
   - Use the app password in the `.env` file

3. **Start the application**
   ```bash
   docker compose up -d
   ```

4. **Verify services are running**
   ```bash
   docker compose ps
   ```

   You should see three services running:
   - `dmarc-db` (PostgreSQL)
   - `dmarc-backend` (FastAPI)
   - `dmarc-nginx` (Web server)

5. **Access the application**
   - Dashboard: http://localhost
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost/health

### Development Commands

```bash
# View logs
docker compose logs -f

# View logs for specific service
docker compose logs -f backend

# Restart services
docker compose restart

# Rebuild after code changes
docker compose up --build -d

# Stop services
docker compose down

# Stop services and remove volumes (reset database)
docker compose down -v

# Run tests
docker compose exec backend pytest

# Access backend shell
docker compose exec backend /bin/bash

# Access database
docker compose exec db psql -U dmarc -d dmarc
```

## Production Deployment

### Production Features

The application includes built-in production-ready features:

#### 1. Background Job Scheduler
- **Automatic report processing**: Every 5 minutes
- **Email ingestion**: Every 15 minutes (when configured)
- Managed by APScheduler, starts automatically with the application

#### 2. Production Logging
- **Rotating file logs**: 10MB max per file, 5 backups kept
- **JSON logging**: Enable with `LOG_JSON=true` for log aggregation
- **Request logging**: Track all API requests with duration and status
- **Error logging**: Separate error log file for critical issues

#### 3. API Authentication
- **API key validation**: Protect endpoints with `X-API-Key` header
- **Configurable**: Enable with `REQUIRE_API_KEY=true`
- **Multi-key support**: Comma-separated list in `API_KEYS` env var

#### 4. Comprehensive Error Handling
- **Standardized error responses**: Consistent JSON error format
- **Database error handling**: Graceful handling of DB issues
- **Validation errors**: Clear error messages for invalid requests

#### 5. Enhanced Health Checks
- **Database connectivity**: Verifies PostgreSQL connection
- **Scheduler status**: Confirms background jobs are running
- **File system access**: Checks logs and storage directories

### Security Checklist

Before deploying to production:

1. **Environment Variables**
   - [ ] Use strong database passwords
   - [ ] Never commit `.env` file
   - [ ] Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
   - [ ] Copy `.env.production.example` to `.env.production`
   - [ ] Generate secure API keys with `python -c "import secrets; print(secrets.token_urlsafe(32))"`

2. **API Authentication**
   - [ ] Set `REQUIRE_API_KEY=true` in `.env.production`
   - [ ] Generate and configure API keys in `API_KEYS`
   - [ ] Distribute API keys securely to authorized clients
   - [ ] Never include API keys in source code or client-side JavaScript

3. **Database**
   - [ ] Use managed PostgreSQL (AWS RDS, Google Cloud SQL, etc.)
   - [ ] Enable SSL connections
   - [ ] Regular automated backups
   - [ ] Connection pooling (built-in via SQLAlchemy)

4. **Logging**
   - [ ] Enable JSON logging: `LOG_JSON=true`
   - [ ] Set appropriate log level: `LOG_LEVEL=INFO` or `WARNING`
   - [ ] Monitor log files: `/app/logs/dmarc-api.log` and `/app/logs/dmarc-api-error.log`
   - [ ] Set up log aggregation (ELK, Splunk, CloudWatch, etc.)

5. **Email Security**
   - [ ] Use OAuth2 instead of passwords where possible
   - [ ] Restrict email account permissions
   - [ ] Use dedicated email account for DMARC reports

6. **HTTPS/TLS**
   - [ ] Use HTTPS only in production
   - [ ] Configure SSL certificates (Let's Encrypt recommended)
   - [ ] Update nginx configuration for HTTPS

### Docker Compose Production

For simple production deployment with Docker Compose:

1. **Update `docker-compose.yml`**

   ```yaml
   version: '3.8'

   services:
     db:
       image: postgres:15-alpine
       restart: always
       environment:
         POSTGRES_USER: ${DB_USER}
         POSTGRES_PASSWORD: ${DB_PASSWORD}
         POSTGRES_DB: dmarc
       volumes:
         - postgres_data:/var/lib/postgresql/data
         - ./backups:/backups
       networks:
         - internal

     backend:
       build: ./backend
       restart: always
       env_file:
         - .env.production
       depends_on:
         - db
       networks:
         - internal
       healthcheck:
         test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
         interval: 30s
         timeout: 10s
         retries: 3

     nginx:
       image: nginx:alpine
       restart: always
       volumes:
         - ./frontend:/usr/share/nginx/html
         - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
         - ./nginx/ssl:/etc/nginx/ssl:ro
       ports:
         - "80:80"
         - "443:443"
       depends_on:
         - backend
       networks:
         - internal

   networks:
     internal:
       driver: bridge

   volumes:
     postgres_data:
   ```

2. **Enable HTTPS with Let's Encrypt**

   Update `nginx/nginx.conf`:
   ```nginx
   server {
       listen 80;
       listen 443 ssl http2;
       server_name yourdomain.com;

       ssl_certificate /etc/nginx/ssl/fullchain.pem;
       ssl_certificate_key /etc/nginx/ssl/privkey.pem;

       # Redirect HTTP to HTTPS
       if ($scheme != "https") {
           return 301 https://$server_name$request_uri;
       }

       # ... rest of config
   }
   ```

3. **Database Backups**

   Create `backup.sh`:
   ```bash
   #!/bin/bash
   docker compose exec -T db pg_dump -U dmarc dmarc | gzip > backups/dmarc-$(date +%Y%m%d-%H%M%S).sql.gz

   # Keep only last 30 days of backups
   find backups/ -name "dmarc-*.sql.gz" -mtime +30 -delete
   ```

   Add to crontab:
   ```bash
   0 2 * * * /path/to/backup.sh
   ```

### Cloud Deployment Options

#### AWS

1. **Using ECS + RDS**
   - Deploy backend container on ECS Fargate
   - Use RDS PostgreSQL for database
   - Store secrets in AWS Secrets Manager
   - Use Application Load Balancer
   - S3 for static frontend files + CloudFront

2. **Using EC2**
   - Launch EC2 instance (t3.medium or larger)
   - Install Docker and Docker Compose
   - Clone repository and configure
   - Use Elastic IP for stable address
   - Enable security groups (ports 80, 443)

#### Google Cloud

1. **Using Cloud Run + Cloud SQL**
   - Deploy backend on Cloud Run
   - Use Cloud SQL for PostgreSQL
   - Store secrets in Secret Manager
   - Use Cloud Storage + CDN for frontend

#### DigitalOcean

1. **Using App Platform**
   - Connect GitHub repository
   - Deploy as Docker container
   - Use Managed PostgreSQL database
   - Enable automatic deployments

2. **Using Droplet**
   - Create Docker Droplet
   - Install docker-compose
   - Follow local deployment steps
   - Configure firewall

### Monitoring & Logging

1. **Application Logs**
   ```bash
   # Configure log aggregation
   docker compose logs backend | tee -a /var/log/dmarc/app.log
   ```

2. **Database Monitoring**
   - Monitor connection pool usage
   - Track query performance
   - Set up alerts for slow queries

3. **Health Checks**
   - Set up uptime monitoring (UptimeRobot, Pingdom)
   - Monitor `/health` endpoint
   - Alert on failures

### Automated Processing

The application includes built-in automatic processing:

#### Background Scheduler (Built-in)
- **Automatic**: Starts with the application
- **Report processing**: Every 5 minutes
- **Email ingestion**: Every 15 minutes (when email is configured)
- **No cron required**: Managed by APScheduler

#### Manual Triggers

You can also manually trigger processing via API:

```bash
# Manually trigger report processing
curl -X POST http://localhost/api/process/trigger

# Response:
# {
#   "message": "Processing complete: 5 reports processed successfully, 0 failed",
#   "reports_processed": 5,
#   "reports_failed": 0
# }
```

If API authentication is enabled:
```bash
curl -X POST -H "X-API-Key: your_api_key" https://yourdomain.com/api/process/trigger
```

#### Adjusting Schedule

To change processing frequency, edit `backend/app/services/scheduler.py`:

```python
# Process reports every 10 minutes instead of 5
self.scheduler.add_job(
    func=self._process_reports_job,
    trigger=IntervalTrigger(minutes=10),  # Changed from 5
    ...
)
```

### Scaling Considerations

For high volume:

1. **Database**
   - Use connection pooling (already configured)
   - Add read replicas for statistics queries
   - Partition tables by date

2. **Backend**
   - Run multiple backend instances
   - Use load balancer
   - Add Redis for caching statistics

3. **Frontend**
   - Serve from CDN
   - Enable browser caching
   - Minify assets

### Troubleshooting

**Database connection issues:**
```bash
# Check database is running
docker compose exec db psql -U dmarc -d dmarc -c "SELECT 1"

# Check connection from backend
docker compose exec backend python -c "from app.database import engine; print(engine.execute('SELECT 1').scalar())"
```

**Email connection issues:**
```bash
# Test IMAP connection
docker compose exec backend python -c "
from app.ingest.email_client import EmailClient
client = EmailClient()
client.connect()
print('Connected successfully!')
"
```

**Permission issues:**
```bash
# Fix file permissions
chmod -R 755 frontend/
chmod 600 .env
```

## Rollback

If deployment fails:

```bash
# View available images
docker images

# Rollback to previous version
docker compose down
docker tag dmarc-backend:previous dmarc-backend:latest
docker compose up -d
```

## Maintenance

1. **Update Dependencies**
   ```bash
   # Update Python packages
   docker compose exec backend pip list --outdated

   # Update in requirements.txt and rebuild
   docker compose up --build -d
   ```

2. **Database Maintenance**
   ```bash
   # Vacuum and analyze
   docker compose exec db psql -U dmarc -d dmarc -c "VACUUM ANALYZE"
   ```

3. **Clean Docker**
   ```bash
   # Remove unused images
   docker image prune -a

   # Remove unused volumes
   docker volume prune
   ```
