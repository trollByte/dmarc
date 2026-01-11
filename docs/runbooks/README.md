# DMARC Dashboard - Operational Runbooks

This directory contains operational runbooks for the DMARC Dashboard. Each runbook provides step-by-step procedures for handling specific operational scenarios.

## Runbook Index

| Runbook | Description | Severity |
|---------|-------------|----------|
| [Service Down](./service-down.md) | Backend/Worker not responding | Critical |
| [Database Issues](./database-issues.md) | PostgreSQL problems | Critical |
| [High Resource Usage](./high-resource-usage.md) | CPU/Memory alerts | Warning |
| [Alert Storm](./alert-storm.md) | Too many DMARC alerts | Warning |
| [Backup Failure](./backup-failure.md) | Backup job failed | Warning |
| [SSL Certificate](./ssl-certificate.md) | Certificate expiry | Warning |

## Quick Reference

### Service Health Checks

```bash
# Check all services
docker-compose ps

# Backend health
curl http://localhost:8000/health

# Database connection
docker exec dmarc-backend python -c "from app.database import check_db_connection; print(check_db_connection())"

# Redis connection
docker exec dmarc-redis redis-cli ping

# Celery workers
docker exec dmarc-celery-worker celery -A celery_worker inspect ping
```

### Common Commands

```bash
# View logs
docker-compose logs -f backend
docker-compose logs -f celery-worker

# Restart services
docker-compose restart backend
docker-compose restart celery-worker

# Database backup
./scripts/backup/backup.sh --type full

# Run migrations
docker exec dmarc-backend alembic upgrade head
```

### Escalation Contacts

| Role | Contact | When to Escalate |
|------|---------|------------------|
| On-Call Engineer | oncall@example.com | First response |
| Database Admin | dba@example.com | Database issues |
| Security Team | security@example.com | Security incidents |
| Management | manager@example.com | Extended outages (>30min) |

## Alert Response Matrix

| Alert | Severity | Response Time | Runbook |
|-------|----------|---------------|---------|
| DMARCBackendDown | Critical | 5 min | [Service Down](./service-down.md) |
| PostgreSQLDown | Critical | 5 min | [Database Issues](./database-issues.md) |
| RedisDown | Critical | 5 min | [Service Down](./service-down.md) |
| HighErrorRate | Warning | 15 min | [Service Down](./service-down.md) |
| HighCPUUsage | Warning | 30 min | [High Resource Usage](./high-resource-usage.md) |
| DiskSpaceLow | Warning | 30 min | [High Resource Usage](./high-resource-usage.md) |
