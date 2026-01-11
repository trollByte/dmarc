# Runbook: Database Issues

## Overview

**Alert Names:** `PostgreSQLDown`, `DatabaseConnectionPoolExhausted`
**Severity:** Critical
**Response Time:** 5 minutes

This runbook covers procedures for PostgreSQL database issues.

## Symptoms

- Backend health check shows database disconnected
- "connection refused" or "too many connections" errors in logs
- Slow query responses or timeouts
- Application errors related to database operations

## Diagnosis

### Step 1: Check PostgreSQL Status

```bash
# Container status
docker-compose ps db

# PostgreSQL logs
docker-compose logs --tail=100 db

# Check if PostgreSQL is accepting connections
docker exec dmarc-db pg_isready -U dmarc

# Check PostgreSQL process
docker exec dmarc-db ps aux | grep postgres
```

### Step 2: Check Connections

```bash
# Current connections
docker exec dmarc-db psql -U dmarc -c "
SELECT count(*) as total_connections,
       state,
       usename
FROM pg_stat_activity
GROUP BY state, usename;
"

# Check for blocking queries
docker exec dmarc-db psql -U dmarc -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
AND state != 'idle';
"

# Check for locks
docker exec dmarc-db psql -U dmarc -c "
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.usename AS blocked_user,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement,
       blocking_activity.query AS current_statement_in_blocking_process
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
"
```

### Step 3: Check Disk Space and Resources

```bash
# Database size
docker exec dmarc-db psql -U dmarc -c "
SELECT pg_size_pretty(pg_database_size('dmarc')) as db_size;
"

# Table sizes
docker exec dmarc-db psql -U dmarc -c "
SELECT relname as table_name,
       pg_size_pretty(pg_total_relation_size(relid)) as total_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
"

# Disk space on host
df -h

# Container disk usage
docker system df
```

## Resolution

### Scenario 1: PostgreSQL Container Down

```bash
# Check why it stopped
docker-compose logs db | tail -50

# Restart PostgreSQL
docker-compose restart db

# Wait for it to be ready
sleep 10
docker exec dmarc-db pg_isready -U dmarc

# Restart dependent services
docker-compose restart backend celery-worker
```

### Scenario 2: Too Many Connections

```bash
# Kill idle connections
docker exec dmarc-db psql -U dmarc -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND query_start < now() - interval '10 minutes'
AND usename = 'dmarc';
"

# Increase max_connections (requires restart)
# Edit docker-compose.yml:
# db:
#   command: postgres -c max_connections=200

docker-compose restart db
```

### Scenario 3: Long-Running Queries

```bash
# Identify long queries
docker exec dmarc-db psql -U dmarc -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC
LIMIT 5;
"

# Cancel a specific query (graceful)
docker exec dmarc-db psql -U dmarc -c "SELECT pg_cancel_backend(PID_HERE);"

# Terminate a specific query (force)
docker exec dmarc-db psql -U dmarc -c "SELECT pg_terminate_backend(PID_HERE);"
```

### Scenario 4: Disk Space Full

```bash
# Check what's using space
docker exec dmarc-db psql -U dmarc -c "
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
"

# Vacuum to reclaim space
docker exec dmarc-db psql -U dmarc -c "VACUUM FULL ANALYZE;"

# If data retention is the issue, run cleanup
curl -X POST http://localhost:8000/retention/execute \
  -H "Authorization: Bearer $TOKEN"
```

### Scenario 5: Database Corruption

```bash
# Check for corruption
docker exec dmarc-db psql -U dmarc -c "
SELECT datname, checksum_failures
FROM pg_stat_database
WHERE datname = 'dmarc';
"

# If corrupted, restore from backup
./scripts/backup/restore.sh --latest
```

## Verification

```bash
# 1. PostgreSQL is running
docker exec dmarc-db pg_isready -U dmarc

# 2. Application can connect
curl -s http://localhost:8000/health | jq .database

# 3. Queries are working
curl -s http://localhost:8000/api/domains | head

# 4. Check connection count is normal
docker exec dmarc-db psql -U dmarc -c "
SELECT count(*) FROM pg_stat_activity WHERE usename = 'dmarc';
"
```

## Prevention

1. **Monitor connection pool**: Set alerts for >80% pool usage
2. **Regular vacuuming**: Schedule `VACUUM ANALYZE` weekly
3. **Query optimization**: Review slow query logs monthly
4. **Backup verification**: Test restore procedure monthly
5. **Capacity planning**: Monitor growth trends

## Escalation

- If database corruption suspected: Escalate to DBA immediately
- If data loss possible: Escalate to management
- If unable to restore within 30 minutes: Escalate to infrastructure team
