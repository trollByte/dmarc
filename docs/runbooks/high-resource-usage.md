# Runbook: High Resource Usage

## Overview

**Alert Names:** `HighCPUUsage`, `HighMemoryUsage`, `DiskSpaceLow`, `DiskSpaceCritical`
**Severity:** Warning/Critical
**Response Time:** 15-30 minutes

This runbook covers procedures for resource exhaustion scenarios.

## Symptoms

- Slow application response times
- Services becoming unresponsive
- High CPU/memory alerts from monitoring
- Disk space warnings

## Diagnosis

### Step 1: Identify Resource Bottleneck

```bash
# Container resource usage
docker stats --no-stream

# Host system resources
top -b -n 1 | head -20
free -h
df -h

# IO statistics
iostat -x 1 5
```

### Step 2: Identify Resource-Heavy Processes

```bash
# Top CPU consumers
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}" | sort -k2 -rh

# Top memory consumers
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | sort -k2 -rh

# Check for memory leaks
docker exec dmarc-backend ps aux --sort=-%mem | head -10
```

### Step 3: Check Application-Specific Metrics

```bash
# Celery queue length
docker exec dmarc-celery-worker celery -A celery_worker inspect stats

# Active tasks
docker exec dmarc-celery-worker celery -A celery_worker inspect active

# Database connections
docker exec dmarc-db psql -U dmarc -c "
SELECT count(*) FROM pg_stat_activity;
"

# Redis memory
docker exec dmarc-redis redis-cli INFO memory | grep used_memory_human
```

## Resolution

### Scenario 1: High CPU - Backend

```bash
# Check what's consuming CPU
docker exec dmarc-backend ps aux --sort=-%cpu | head -5

# Check for expensive queries
docker exec dmarc-db psql -U dmarc -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC
LIMIT 5;
"

# If ML training is running, it's expected - wait for completion
# Otherwise, restart the backend
docker-compose restart backend
```

### Scenario 2: High CPU - Celery Workers

```bash
# Check active tasks
docker exec dmarc-celery-worker celery -A celery_worker inspect active

# If too many tasks, scale up workers temporarily
docker-compose up -d --scale celery-worker=4

# Or reduce concurrency and restart
# Edit docker-compose.yml: --concurrency=2
docker-compose restart celery-worker
```

### Scenario 3: High Memory

```bash
# Clear Python object caches
docker-compose restart backend

# Clear Redis cache (may impact performance temporarily)
docker exec dmarc-redis redis-cli FLUSHDB

# If memory leak suspected, check application logs
docker-compose logs backend | grep -i "memory\|oom"

# Increase memory limits if needed (docker-compose.yml)
# deploy:
#   resources:
#     limits:
#       memory: 2G
```

### Scenario 4: Disk Space Low

```bash
# Find large files
du -h /var/lib/docker/volumes/ | sort -rh | head -20

# Clean Docker resources
docker system prune -f
docker volume prune -f

# Clean old logs
find /var/log -name "*.log" -mtime +30 -delete

# Clean old backups (keep last 7)
ls -t /var/backups/dmarc/*.gz | tail -n +8 | xargs rm -f

# Vacuum PostgreSQL
docker exec dmarc-db psql -U dmarc -c "VACUUM FULL;"

# Run data retention cleanup
curl -X POST http://localhost:8000/retention/execute \
  -H "Authorization: Bearer $TOKEN"
```

### Scenario 5: Redis Memory High

```bash
# Check memory usage
docker exec dmarc-redis redis-cli INFO memory

# Check key count by pattern
docker exec dmarc-redis redis-cli --scan --pattern '*' | wc -l

# Clear specific cache patterns
docker exec dmarc-redis redis-cli --scan --pattern 'cache:*' | xargs -r docker exec -i dmarc-redis redis-cli DEL

# Clear all caches (temporary performance impact)
docker exec dmarc-redis redis-cli FLUSHALL
```

## Verification

```bash
# 1. Check resources are back to normal
docker stats --no-stream

# 2. Application responding normally
time curl -s http://localhost:8000/health

# 3. Disk space acceptable
df -h | grep -E "/$|/var"

# 4. Check Grafana metrics show improvement
```

## Prevention

1. **Set resource limits**: Configure memory/CPU limits in docker-compose.yml
2. **Implement data retention**: Configure automatic cleanup policies
3. **Monitor trends**: Review resource usage trends weekly
4. **Scale appropriately**: Adjust resources based on load
5. **Log rotation**: Configure log rotation for all services

## Capacity Planning

| Resource | Warning | Critical | Action |
|----------|---------|----------|--------|
| CPU | 70% | 90% | Scale horizontally |
| Memory | 80% | 95% | Increase limits or scale |
| Disk | 80% | 95% | Clean up or expand |
| Connections | 80% | 95% | Optimize or increase pool |

## Escalation

- CPU/Memory at critical: Escalate immediately
- Disk critical (<5%): Escalate immediately
- Unable to free resources: Escalate to infrastructure team
