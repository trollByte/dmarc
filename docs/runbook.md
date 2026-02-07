# DMARC Dashboard Operations Runbook

Comprehensive operational procedures for running, monitoring, and troubleshooting the DMARC Dashboard.

## Table of Contents

1. [Service Management](#service-management)
2. [Backup & Restore](#backup--restore)
3. [Scaling Services](#scaling-services)
4. [Secret Rotation](#secret-rotation)
5. [Monitoring & Alerts](#monitoring--alerts)
6. [Common Troubleshooting](#common-troubleshooting)

---

## Service Management

### Starting Services

**Development Mode:**
```bash
docker compose up -d
```

**Production Mode:**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**With Monitoring (Prometheus/Grafana):**
```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

### Stopping Services

**Graceful Shutdown:**
```bash
docker compose down
```

**Force Stop (if hung):**
```bash
docker compose kill
docker compose down
```

**Stop Single Service:**
```bash
docker compose stop backend
```

### Restarting Services

**All Services:**
```bash
docker compose restart
```

**Single Service:**
```bash
docker compose restart backend
docker compose restart celery-worker
docker compose restart celery-beat
```

**Zero-Downtime Backend Restart:**
```bash
# Scale up new instance
docker compose up -d --scale backend=2 --no-recreate

# Wait for health check
sleep 10

# Remove old instance
docker compose up -d --scale backend=1
```

### Viewing Service Status

**List Running Services:**
```bash
docker compose ps
```

**Detailed Status:**
```bash
docker compose ps -a
docker stats
```

**Service Health Checks:**
```bash
# Backend health
curl http://localhost:8000/health

# Database
docker compose exec db pg_isready -U dmarc

# Redis
docker compose exec redis redis-cli ping

# Celery workers
docker compose exec celery-worker celery -A celery_worker inspect active
```

### Viewing Logs

**All Services (Live):**
```bash
docker compose logs -f
```

**Single Service:**
```bash
docker compose logs -f backend
docker compose logs -f celery-worker --tail=100
```

**Filter by Time:**
```bash
docker compose logs --since 1h backend
docker compose logs --since 2026-02-06T12:00:00 backend
```

**Search Logs:**
```bash
docker compose logs backend | grep ERROR
docker compose logs celery-worker | grep -i "task.*failed"
```

---

## Backup & Restore

### Database Backup

**Quick Backup (SQL Format):**
```bash
docker compose exec db pg_dump -U dmarc dmarc > backups/dmarc_$(date +%Y%m%d_%H%M%S).sql
```

**Compressed Backup:**
```bash
docker compose exec db pg_dump -U dmarc dmarc | gzip > backups/dmarc_$(date +%Y%m%d_%H%M%S).sql.gz
```

**Custom Format (Parallel Restore, Smaller):**
```bash
docker compose exec db pg_dump -U dmarc -Fc dmarc > backups/dmarc_$(date +%Y%m%d_%H%M%S).dump
```

**Using Makefile:**
```bash
make backup
```

**Backup Script (Recommended):**

Create `scripts/backup.sh`:
```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="./backups"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"
FILENAME="dmarc_$(date +%Y%m%d_%H%M%S).sql.gz"

echo "Creating backup: $FILENAME"
docker compose exec -T db pg_dump -U dmarc dmarc | gzip > "$BACKUP_DIR/$FILENAME"

echo "Cleaning up backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name "dmarc_*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup complete: $BACKUP_DIR/$FILENAME"
ls -lh "$BACKUP_DIR/$FILENAME"
```

### Database Restore

**From SQL File:**
```bash
./scripts/restore.sh backups/dmarc_20260206_120000.sql
```

**Manual Restore:**
```bash
# Stop services accessing the database
docker compose stop backend celery-worker celery-beat flower

# Drop and recreate database
docker compose exec db psql -U dmarc -c "DROP DATABASE IF EXISTS dmarc;"
docker compose exec db psql -U dmarc -c "CREATE DATABASE dmarc;"

# Restore from backup
cat backups/dmarc_20260206_120000.sql | docker compose exec -T db psql -U dmarc dmarc

# Or for gzipped backup
gunzip -c backups/dmarc_20260206_120000.sql.gz | docker compose exec -T db psql -U dmarc dmarc

# Start services
docker compose start backend celery-worker celery-beat flower

# Run migrations (if schema changed)
docker compose exec backend alembic upgrade head
```

**From Custom Format:**
```bash
docker compose exec -T db pg_restore -U dmarc -d dmarc -c < backups/dmarc_20260206_120000.dump
```

### Automated Backups

**Cron Job (Daily at 2 AM):**

Add to crontab (`crontab -e`):
```cron
# Daily DMARC database backup
0 2 * * * cd /path/to/dmarc && ./scripts/backup.sh >> /var/log/dmarc-backup.log 2>&1
```

**Systemd Timer:**

Create `/etc/systemd/system/dmarc-backup.timer`:
```ini
[Unit]
Description=DMARC Database Backup Timer

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Create `/etc/systemd/system/dmarc-backup.service`:
```ini
[Unit]
Description=DMARC Database Backup

[Service]
Type=oneshot
WorkingDirectory=/path/to/dmarc
ExecStart=/path/to/dmarc/scripts/backup.sh
User=dmarc
Group=dmarc
```

Enable:
```bash
sudo systemctl enable dmarc-backup.timer
sudo systemctl start dmarc-backup.timer
sudo systemctl status dmarc-backup.timer
```

### Backup Verification

**Test Restore (Isolated):**
```bash
# Start temporary database
docker run -d --name dmarc-restore-test \
  -e POSTGRES_USER=dmarc \
  -e POSTGRES_PASSWORD=test \
  -e POSTGRES_DB=dmarc \
  postgres:15

# Restore backup
gunzip -c backups/dmarc_latest.sql.gz | docker exec -i dmarc-restore-test psql -U dmarc dmarc

# Verify data
docker exec -it dmarc-restore-test psql -U dmarc dmarc -c "SELECT COUNT(*) FROM dmarc_reports;"

# Cleanup
docker rm -f dmarc-restore-test
```

---

## Scaling Services

### Horizontal Scaling (Multiple Instances)

**Scale Celery Workers:**
```bash
# Increase to 3 workers
docker compose up -d --scale celery-worker=3

# Note: Remove 'container_name' from docker-compose.yml for celery-worker
```

**Scale Backend API:**
```bash
# Use Nginx load balancer (already configured)
docker compose up -d --scale backend=3
```

**Verify Scaling:**
```bash
docker compose ps | grep celery-worker
docker compose ps | grep backend
```

### Vertical Scaling (Resource Limits)

**Edit docker-compose.yml:**
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'      # Increase from 1.0
          memory: 2G       # Increase from 1G
        reservations:
          cpus: '1.0'
          memory: 1G
```

**Apply Changes:**
```bash
docker compose up -d --force-recreate backend
```

### Celery Worker Concurrency

**Edit docker-compose.yml:**
```yaml
celery-worker:
  command: celery -A celery_worker worker --loglevel=info --concurrency=8
```

Or set via environment variable:
```yaml
celery-worker:
  environment:
    - CELERY_CONCURRENCY=8
```

**Restart:**
```bash
docker compose restart celery-worker
```

### Database Connection Pooling

**Edit .env:**
```bash
DATABASE_POOL_SIZE=20       # Default: 10
DATABASE_MAX_OVERFLOW=40    # Default: 20
```

**Verify Connections:**
```bash
docker compose exec db psql -U dmarc -c "SELECT count(*) FROM pg_stat_activity;"
```

### Monitor Worker Load

**Flower Dashboard:**
```
http://localhost:5555
```

**CLI Inspection:**
```bash
# Active tasks
docker compose exec celery-worker celery -A celery_worker inspect active

# Reserved tasks
docker compose exec celery-worker celery -A celery_worker inspect reserved

# Worker stats
docker compose exec celery-worker celery -A celery_worker inspect stats
```

---

## Secret Rotation

### JWT Secret Key

**1. Generate New Secret:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

**2. Update .env:**
```bash
JWT_SECRET_KEY=NEW_SECRET_HERE
```

**3. Restart Services:**
```bash
docker compose restart backend celery-worker celery-beat
```

**4. Impact:**
- All existing JWT tokens invalidated
- Users must re-login
- API keys unaffected

**5. Notify Users:**
```bash
# Broadcast notification via API
curl -X POST http://localhost:8000/api/notifications/broadcast \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "severity": "warning",
    "message": "Security maintenance: Please log in again."
  }'
```

### Database Password

**1. Update .env:**
```bash
POSTGRES_PASSWORD=NEW_PASSWORD_HERE
DATABASE_URL=postgresql://dmarc:NEW_PASSWORD_HERE@db:5432/dmarc
```

**2. Update Database:**
```bash
docker compose exec db psql -U dmarc -c "ALTER USER dmarc WITH PASSWORD 'NEW_PASSWORD_HERE';"
```

**3. Restart Services:**
```bash
docker compose restart backend celery-worker celery-beat flower
```

### Redis Password

**1. Update .env:**
```bash
REDIS_PASSWORD=NEW_PASSWORD_HERE
```

**2. Update Redis Config:**
```bash
docker compose exec redis redis-cli CONFIG SET requirepass "NEW_PASSWORD_HERE"
```

**3. Restart Services:**
```bash
docker compose restart backend celery-worker celery-beat flower
```

### Flower Basic Auth

**1. Update .env:**
```bash
FLOWER_BASIC_AUTH=admin:NEW_PASSWORD_HERE
```

**2. Restart Flower:**
```bash
docker compose restart flower
```

### API Key Rotation

**User Self-Service:**

Users can regenerate their API keys via UI or API:
```bash
curl -X POST http://localhost:8000/api/users/api-keys \
  -H "Authorization: Bearer ${USER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"key_name": "Rotated Key"}'
```

**Admin-Forced Rotation:**

```bash
# Revoke all API keys for a user
curl -X DELETE http://localhost:8000/api/users/{user_id}/api-keys \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

### SMTP Password

**1. Update .env:**
```bash
SMTP_PASSWORD=NEW_PASSWORD_HERE
EMAIL_PASSWORD=NEW_PASSWORD_HERE
```

**2. Restart Services:**
```bash
docker compose restart backend celery-worker celery-beat
```

**3. Test:**
```bash
# Trigger test alert
curl -X POST http://localhost:8000/api/alerts/test \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

---

## Monitoring & Alerts

### Health Checks

**Application Health:**
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "ok",
  "redis": "ok",
  "timestamp": "2026-02-06T12:00:00Z"
}
```

**Database Health:**
```bash
docker compose exec db pg_isready -U dmarc
# Output: /var/run/postgresql:5432 - accepting connections
```

**Redis Health:**
```bash
docker compose exec redis redis-cli ping
# Output: PONG
```

### Prometheus Metrics

**Metrics Endpoint:**
```
http://localhost:8000/metrics
```

**Key Metrics:**
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `database_connections_active` - Active DB connections
- `celery_tasks_total` - Total Celery tasks
- `celery_task_duration_seconds` - Task execution time

**Grafana Dashboard:**
```
http://localhost:3000
```

Login: `admin` / `admin`

### Celery Task Monitoring

**Flower Dashboard:**
```
http://localhost:5555
```

**API Task Stats:**
```bash
curl http://localhost:8000/api/task-stats \
  -H "Authorization: Bearer ${TOKEN}"
```

### Log Aggregation

**ELK Stack (if configured):**
```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

Access Kibana: `http://localhost:5601`

**CloudWatch Logs (AWS):**
```bash
# Configure in backend/app/config.py
CLOUDWATCH_LOG_GROUP=/aws/dmarc/production
CLOUDWATCH_LOG_STREAM=backend
```

### Alert Configuration

**Configure Alert Rules:**

See `docs/USER_GUIDE.md` for UI-based alert configuration.

**Example Alert Rules:**
- High failure rate (>25%)
- Volume spike (>50% increase)
- Volume drop (>30% decrease)
- New source IP detected

**Alert Delivery Channels:**
- Email (SMTP)
- Slack webhook
- Discord webhook
- Microsoft Teams webhook
- Generic HTTP webhook

### System Resource Monitoring

**Container Stats:**
```bash
docker stats
```

**Disk Usage:**
```bash
df -h
docker system df
```

**Database Size:**
```bash
docker compose exec db psql -U dmarc -c "
  SELECT pg_size_pretty(pg_database_size('dmarc'));
"
```

**Redis Memory:**
```bash
docker compose exec redis redis-cli INFO memory | grep used_memory_human
```

---

## Common Troubleshooting

### Backend Fails to Start

**Symptoms:**
- Container exits immediately
- Restarts in loop

**Diagnostic Steps:**

1. **Check logs:**
```bash
docker compose logs backend --tail=50
```

2. **Verify database connectivity:**
```bash
docker compose exec db pg_isready -U dmarc
docker compose exec backend env | grep DATABASE_URL
```

3. **Verify Redis connectivity:**
```bash
docker compose exec redis redis-cli ping
docker compose exec backend env | grep REDIS
```

4. **Check environment variables:**
```bash
docker compose exec backend env | grep -E 'DATABASE_URL|REDIS|JWT_SECRET_KEY'
```

5. **Run migrations:**
```bash
docker compose exec backend alembic upgrade head
```

**Common Causes:**
- Missing `JWT_SECRET_KEY`
- Wrong `DATABASE_URL`
- Database not ready
- Redis not available
- Missing environment variables

### Database Connection Refused

**Symptoms:**
- `connection refused` errors
- `could not connect to server`

**Diagnostic Steps:**

1. **Check database status:**
```bash
docker compose ps db
docker compose logs db --tail=20
```

2. **Verify database is listening:**
```bash
docker compose exec db netstat -an | grep 5432
```

3. **Check disk space:**
```bash
df -h
# PostgreSQL stops when disk is full
```

4. **Verify volume exists:**
```bash
docker volume ls | grep postgres
```

5. **Test connection from backend:**
```bash
docker compose exec backend python -c "
from app.database import engine
print(engine.connect())
"
```

**Common Causes:**
- Database container not running
- Disk full
- Network isolation
- Wrong credentials in `DATABASE_URL`

### Celery Workers Not Processing Tasks

**Symptoms:**
- Tasks stuck in PENDING state
- No task execution

**Diagnostic Steps:**

1. **Check worker status:**
```bash
docker compose logs celery-worker --tail=30
docker compose ps celery-worker
```

2. **Verify Redis connectivity:**
```bash
docker compose exec redis redis-cli ping
docker compose exec celery-worker redis-cli -h redis ping
```

3. **Inspect active tasks:**
```bash
docker compose exec celery-worker celery -A celery_worker inspect active
```

4. **Check for stuck tasks:**
```bash
docker compose exec celery-worker celery -A celery_worker inspect reserved
```

5. **Verify Celery Beat:**
```bash
docker compose logs celery-beat --tail=20
docker compose ps celery-beat
```

**Common Causes:**
- Redis connection lost
- Worker crashed
- Celery Beat not running
- Task queue full

**Solutions:**
```bash
# Restart workers and beat
docker compose restart celery-worker celery-beat

# Purge task queue (caution: loses pending tasks)
docker compose exec celery-worker celery -A celery_worker purge

# Clear Redis (caution: loses all cache)
docker compose exec redis redis-cli FLUSHDB
```

### High Memory Usage

**Symptoms:**
- Container OOM killed
- Slow performance
- Swap usage high

**Diagnostic Steps:**

1. **Check container stats:**
```bash
docker stats
```

2. **Check Redis memory:**
```bash
docker compose exec redis redis-cli INFO memory
```

3. **Check database connections:**
```bash
docker compose exec db psql -U dmarc -c "
  SELECT count(*), state FROM pg_stat_activity GROUP BY state;
"
```

4. **Check Python process memory:**
```bash
docker compose exec backend ps aux | grep python
```

**Common Causes:**
- Redis cache too large
- Database connection leak
- Celery worker memory leak
- Too many concurrent requests

**Solutions:**
```bash
# Clear Redis cache
docker compose exec redis redis-cli FLUSHDB

# Kill idle database connections
docker compose exec db psql -U dmarc -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE state = 'idle'
  AND state_change < NOW() - INTERVAL '1 hour';
"

# Restart services
docker compose restart backend celery-worker

# Increase memory limits (docker-compose.yml)
```

### Reports Not Being Ingested

**Symptoms:**
- No new reports appearing
- Email ingestion not working

**Diagnostic Steps:**

1. **Check Celery Beat:**
```bash
docker compose ps celery-beat
docker compose logs celery-beat | grep -i ingest
```

2. **Check import directory:**
```bash
ls -la import_reports/
```

3. **Check ingestion logs:**
```bash
docker compose logs celery-worker --tail=100 | grep -i ingest
```

4. **Manually trigger ingestion:**
```bash
curl -X POST http://localhost:8000/api/tasks/trigger/email-ingestion \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

5. **Test email connection:**
```bash
docker compose exec backend python -c "
from app.services.email_ingestion import EmailIngestionService
service = EmailIngestionService()
service.test_connection()
"
```

**Common Causes:**
- Email credentials wrong
- Celery Beat not running
- Email folder empty
- Import directory permissions

### Frontend Not Loading

**Symptoms:**
- Blank page
- JavaScript errors
- Assets not loading

**Diagnostic Steps:**

1. **Check Nginx logs:**
```bash
docker compose logs nginx --tail=50
```

2. **Check browser console:**
```
Open DevTools → Console
```

3. **Verify Nginx is running:**
```bash
docker compose ps nginx
curl -I http://localhost
```

4. **Check file permissions:**
```bash
docker compose exec nginx ls -la /usr/share/nginx/html/
```

**Common Causes:**
- Nginx not running
- CORS errors
- CSP blocking scripts
- File permissions

### SSL/TLS Certificate Errors

**Symptoms:**
- `certificate verify failed` errors
- HTTPS not working

**Diagnostic Steps:**

1. **Check certificate files:**
```bash
ls -la /etc/letsencrypt/live/yourdomain.com/
```

2. **Verify Nginx config:**
```bash
docker compose exec nginx nginx -t
```

3. **Check certificate expiry:**
```bash
openssl x509 -in /etc/letsencrypt/live/yourdomain.com/fullchain.pem -noout -dates
```

**Solutions:**

Renew certificates:
```bash
certbot renew
docker compose restart nginx
```

## Emergency Procedures

### Complete System Reset

**WARNING: Destroys all data**

```bash
# Stop all services
docker compose down

# Remove volumes
docker volume rm dmarc_postgres_data dmarc_redis_data

# Remove containers
docker compose rm -f

# Restart
docker compose up -d

# Run migrations
docker compose exec backend alembic upgrade head

# Create default admin user
docker compose exec backend python -c "
from app.database import SessionLocal
from app.models import User
from passlib.context import CryptContext

db = SessionLocal()
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
admin = User(
    username='admin',
    email='admin@example.com',
    hashed_password=pwd_context.hash('admin'),
    role='admin',
    is_active=True
)
db.add(admin)
db.commit()
print('Admin user created: admin/admin')
"
```

### Disaster Recovery

See [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) for complete DR procedures.

## See Also

- [Deployment Guide](DEPLOYMENT.md)
- [Configuration Guide](CONFIGURATION.md)
- [Disaster Recovery](DISASTER_RECOVERY.md)
- [Security Guide](../security/README.md)
