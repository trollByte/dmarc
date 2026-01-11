# Runbook: Service Down

## Overview

**Alert Names:** `DMARCBackendDown`, `RedisDown`, `CeleryWorkerDown`
**Severity:** Critical
**Response Time:** 5 minutes

This runbook covers procedures for when DMARC Dashboard services are unresponsive.

## Symptoms

- Health check endpoint (`/health`) returns error or timeout
- Grafana dashboard shows service as DOWN
- Users report application errors
- No new DMARC reports being processed

## Diagnosis

### Step 1: Identify Affected Services

```bash
# Check all container statuses
docker-compose ps

# Expected output shows all services as "Up"
# Look for "Exit" or "Restarting" status
```

### Step 2: Check Service Logs

```bash
# Backend logs
docker-compose logs --tail=100 backend

# Celery worker logs
docker-compose logs --tail=100 celery-worker

# Redis logs
docker-compose logs --tail=100 redis

# All logs
docker-compose logs --tail=200 --timestamps
```

### Step 3: Check Resource Usage

```bash
# Container resource usage
docker stats --no-stream

# Check for OOM kills
dmesg | grep -i "out of memory" | tail -10

# Disk space
df -h
```

### Step 4: Check Dependencies

```bash
# Database connectivity
docker exec dmarc-backend python -c "
from app.database import check_db_connection
print('DB Connected:', check_db_connection())
"

# Redis connectivity
docker exec dmarc-redis redis-cli ping

# Check DNS resolution
docker exec dmarc-backend nslookup db
```

## Resolution

### Scenario 1: Container Crashed (Exit Status)

```bash
# View exit reason
docker-compose logs backend | tail -50

# Restart the service
docker-compose restart backend

# Verify it's running
docker-compose ps backend
curl http://localhost:8000/health
```

### Scenario 2: Out of Memory

```bash
# Check memory limits
docker stats --no-stream

# Increase memory limit in docker-compose.yml
# deploy:
#   resources:
#     limits:
#       memory: 2G

# Restart with new limits
docker-compose up -d backend
```

### Scenario 3: Database Connection Issues

See [Database Issues Runbook](./database-issues.md)

### Scenario 4: Redis Connection Issues

```bash
# Check Redis status
docker-compose logs redis

# Restart Redis
docker-compose restart redis

# Clear Redis if corrupted (WARNING: loses cache)
docker exec dmarc-redis redis-cli FLUSHALL

# Restart dependent services
docker-compose restart backend celery-worker
```

### Scenario 5: Celery Worker Not Processing

```bash
# Check worker status
docker exec dmarc-celery-worker celery -A celery_worker inspect ping

# Check queue length
docker exec dmarc-celery-worker celery -A celery_worker inspect active

# Restart workers
docker-compose restart celery-worker celery-beat

# If tasks are stuck, purge the queue (WARNING: loses pending tasks)
docker exec dmarc-celery-worker celery -A celery_worker purge -f
```

## Verification

After resolution, verify services are healthy:

```bash
# 1. Health endpoint
curl -s http://localhost:8000/health | jq .

# 2. API endpoint test
curl -s http://localhost:8000/api/domains | head

# 3. Check Celery is processing
docker exec dmarc-celery-worker celery -A celery_worker inspect active

# 4. Check Grafana dashboard
# Navigate to http://localhost:3000 and verify metrics

# 5. Test report processing
curl -X POST http://localhost:8000/api/trigger/process-reports
```

## Post-Incident

1. Document the incident in your incident management system
2. Review logs for root cause
3. Update monitoring if needed
4. Schedule post-mortem if extended outage

## Escalation

If unable to resolve within 15 minutes:
- Escalate to Database Admin if database related
- Escalate to Infrastructure team if resource related
- Notify management for extended outages
