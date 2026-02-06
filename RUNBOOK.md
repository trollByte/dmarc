# DMARC Dashboard - Operations Runbook

## Starting and Stopping Services

### Start All Services
```bash
docker compose up -d
```

### Stop All Services
```bash
docker compose down
```

### Start in Production Mode
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Restart a Single Service
```bash
docker compose restart backend
docker compose restart celery-worker
```

### View Service Status
```bash
docker compose ps
```

### View Logs
```bash
# All services
docker compose logs -f

# Single service
docker compose logs -f backend
docker compose logs -f celery-worker --tail=100
```

---

## Database Backup and Restore

### Manual Backup
```bash
# SQL dump (recommended for portability)
docker compose exec db pg_dump -U dmarc dmarc > backups/dmarc_$(date +%Y%m%d_%H%M%S).sql

# Custom format (supports parallel restore, smaller)
docker compose exec db pg_dump -U dmarc -Fc dmarc > backups/dmarc_$(date +%Y%m%d_%H%M%S).dump

# Compressed SQL
docker compose exec db pg_dump -U dmarc dmarc | gzip > backups/dmarc_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Using the Makefile
```bash
make backup
```

### Restore from Backup
```bash
./scripts/restore.sh backups/dmarc_20260101_120000.sql
```

The restore script auto-detects format (.sql, .dump, .sql.gz) and prompts for confirmation before overwriting.

### Automated Backups (cron)
Add to crontab (`crontab -e`):
```
# Daily backup at 2 AM
0 2 * * * cd /path/to/dmarc && docker compose exec -T db pg_dump -U dmarc dmarc | gzip > backups/dmarc_$(date +\%Y\%m\%d).sql.gz

# Retain last 30 days
0 3 * * * find /path/to/dmarc/backups -name "*.sql.gz" -mtime +30 -delete
```

---

## Scaling Workers

### Increase Celery Worker Concurrency
Edit `docker-compose.yml` and change the concurrency flag:
```yaml
command: celery -A celery_worker worker --loglevel=info --concurrency=8
```
Then restart:
```bash
docker compose restart celery-worker
```

### Run Multiple Worker Containers
```bash
docker compose up -d --scale celery-worker=3
```

Note: When scaling, remove the `container_name` from the celery-worker service definition to avoid conflicts.

### Monitor Worker Load
- Flower dashboard: http://localhost:5555
- Check active tasks: `docker compose exec celery-worker celery -A celery_worker inspect active`
- Check reserved tasks: `docker compose exec celery-worker celery -A celery_worker inspect reserved`

---

## Troubleshooting Common Issues

### Backend Fails to Start

**Symptom:** Backend container exits immediately or restarts in a loop.

**Steps:**
1. Check logs: `docker compose logs backend --tail=50`
2. Verify database is healthy: `docker compose exec db pg_isready -U dmarc`
3. Verify Redis is healthy: `docker compose exec redis redis-cli ping`
4. Check environment variables: `docker compose exec backend env | grep DATABASE_URL`
5. Run migrations: `docker compose exec backend alembic upgrade head`

### Database Connection Refused

**Symptom:** `connection refused` or `could not connect to server` errors.

**Steps:**
1. Check if db container is running: `docker compose ps db`
2. Check db logs: `docker compose logs db --tail=20`
3. Check disk space: `df -h` (PostgreSQL stops when disk is full)
4. Verify the volume exists: `docker volume ls | grep postgres`

### Celery Worker Not Processing Tasks

**Symptom:** Tasks remain in pending state.

**Steps:**
1. Check worker status: `docker compose logs celery-worker --tail=30`
2. Verify Redis connectivity: `docker compose exec redis redis-cli ping`
3. Inspect active tasks: `docker compose exec celery-worker celery -A celery_worker inspect active`
4. Check for stuck tasks: `docker compose exec celery-worker celery -A celery_worker inspect reserved`
5. Restart workers: `docker compose restart celery-worker celery-beat`

### High Memory Usage

**Symptom:** Container OOM killed or slow performance.

**Steps:**
1. Check container stats: `docker stats`
2. Check Redis memory: `docker compose exec redis redis-cli info memory`
3. Check PostgreSQL connections: `docker compose exec db psql -U dmarc -c "SELECT count(*) FROM pg_stat_activity;"`
4. Clear Redis cache: `docker compose exec redis redis-cli FLUSHDB`

### Reports Not Being Ingested

**Symptom:** No new reports appearing in the dashboard.

**Steps:**
1. Check celery-beat is running: `docker compose ps celery-beat`
2. Manually trigger ingestion: `curl -X POST http://localhost:8000/tasks/trigger/email-ingestion -H "Authorization: Bearer <token>"`
3. Check import directory: `ls -la import_reports/`
4. Check ingestion logs: `docker compose logs celery-worker --tail=50 | grep -i ingest`

---

## Secret Rotation

### Rotate JWT Secret Key

1. Generate a new secret:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
2. Update `JWT_SECRET_KEY` in `.env`
3. Restart backend and workers:
   ```bash
   docker compose restart backend celery-worker celery-beat
   ```
4. Note: All existing JWT tokens are invalidated. Users must re-authenticate.

### Rotate Database Password

1. Update `POSTGRES_PASSWORD` in `.env`
2. Update the password in PostgreSQL:
   ```bash
   docker compose exec db psql -U dmarc -c "ALTER USER dmarc WITH PASSWORD 'new-password-here';"
   ```
3. Restart all services that connect to the database:
   ```bash
   docker compose restart backend celery-worker celery-beat flower
   ```

### Rotate Redis Password

1. Update `REDIS_PASSWORD` in `.env`
2. Set the new password in the running Redis instance:
   ```bash
   docker compose exec redis redis-cli CONFIG SET requirepass "new-password-here"
   ```
3. Restart all services that connect to Redis:
   ```bash
   docker compose restart backend celery-worker celery-beat flower
   ```

### Rotate Flower Basic Auth

1. Update `FLOWER_BASIC_AUTH` in `.env` (format: `user:password`)
2. Restart Flower:
   ```bash
   docker compose restart flower
   ```

### Rotate API Keys

Users can regenerate their API keys through the API:
```bash
curl -X POST http://localhost:8000/users/api-keys \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json"
```

Old API keys are automatically invalidated when new ones are generated.
