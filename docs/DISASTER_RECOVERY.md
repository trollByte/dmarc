# DMARC Dashboard - Disaster Recovery Plan

## Overview

This document outlines the disaster recovery (DR) procedures for the DMARC Dashboard application. It defines Recovery Time Objective (RTO) and Recovery Point Objective (RPO) targets, and provides step-by-step procedures for various disaster scenarios.

## Recovery Objectives

| Metric | Target | Description |
|--------|--------|-------------|
| **RTO** | 4 hours | Maximum acceptable downtime |
| **RPO** | 24 hours | Maximum acceptable data loss |

## Backup Strategy

### Automated Backups

| Component | Frequency | Retention | Location |
|-----------|-----------|-----------|----------|
| PostgreSQL (full) | Daily 2 AM | 30 days | `/var/backups/dmarc/` |
| PostgreSQL (schema) | Weekly | 90 days | `/var/backups/dmarc/` |
| Redis (AOF) | Continuous | N/A | Docker volume |
| Configuration | On change | Git history | Git repository |
| ML Models | After training | 5 versions | Database BLOB |

### Backup Verification

Backups are verified through multiple methods to ensure recoverability:

#### Automated Verification (Daily)

1. **Integrity Check**
   ```bash
   # Run after each backup
   pg_restore --list /var/backups/dmarc/dmarc_backup_latest.dump > /dev/null
   echo $? # Should return 0 for valid backup
   ```

2. **Backup Size Validation**
   ```bash
   # Verify backup size is within expected range (50MB - 10GB)
   SIZE=$(stat -f%z /var/backups/dmarc/dmarc_backup_latest.dump)
   if [ $SIZE -lt 52428800 ] || [ $SIZE -gt 10737418240 ]; then
     echo "WARNING: Backup size outside expected range"
     # Send alert
   fi
   ```

3. **Metadata Verification**
   ```bash
   # Extract and verify backup metadata
   pg_restore -l /var/backups/dmarc/dmarc_backup_latest.dump | grep -c "TABLE DATA"
   # Should show expected number of tables
   ```

#### Weekly Test Restore

Every Sunday at 3 AM, perform test restore to staging environment:

```bash
#!/bin/bash
# Weekly backup verification script
# Location: /opt/dmarc/scripts/verify-backup.sh

set -e

BACKUP_FILE="/var/backups/dmarc/dmarc_backup_latest.dump"
TEST_DB="dmarc_test_restore"

# Create test database
psql -U postgres -c "DROP DATABASE IF EXISTS ${TEST_DB};"
psql -U postgres -c "CREATE DATABASE ${TEST_DB};"

# Restore backup to test database
pg_restore -U postgres -d ${TEST_DB} ${BACKUP_FILE}

# Verify critical tables exist and have data
REPORT_COUNT=$(psql -U postgres -d ${TEST_DB} -t -c "SELECT COUNT(*) FROM dmarc_reports;")
DOMAIN_COUNT=$(psql -U postgres -d ${TEST_DB} -t -c "SELECT COUNT(*) FROM domains;")
USER_COUNT=$(psql -U postgres -d ${TEST_DB} -t -c "SELECT COUNT(*) FROM users;")

echo "Restore verification results:"
echo "  - Reports: ${REPORT_COUNT}"
echo "  - Domains: ${DOMAIN_COUNT}"
echo "  - Users: ${USER_COUNT}"

# Cleanup
psql -U postgres -c "DROP DATABASE ${TEST_DB};"

# Send success notification
if [ $? -eq 0 ]; then
  echo "Backup verification PASSED"
  # Send success metric to monitoring
else
  echo "Backup verification FAILED"
  # Send alert to ops team
  exit 1
fi
```

#### Monthly DR Drill

Full disaster recovery exercise to staging environment:
- Test complete server recovery procedure
- Verify all services start correctly
- Test data integrity and application functionality
- Document time to recovery
- Update procedures based on findings

#### Quarterly Production DR Test

- Schedule during maintenance window
- Perform limited test in production-like environment
- Validate all recovery procedures
- Test failover to secondary region (if applicable)
- Conduct post-drill review

## Disaster Scenarios

### Scenario 1: Single Service Failure

**Impact:** Partial functionality loss
**Recovery Time:** 15-30 minutes

#### Procedure

1. **Identify failed service**
   ```bash
   docker-compose ps
   docker-compose logs <service> --tail=50
   ```

2. **Restart service**
   ```bash
   docker-compose restart <service>
   ```

3. **Verify recovery**
   ```bash
   curl http://localhost:8000/health
   ```

4. **If restart fails, recreate**
   ```bash
   docker-compose up -d --force-recreate <service>
   ```

---

### Scenario 2: Database Corruption/Loss

**Impact:** Complete data loss risk
**Recovery Time:** 1-2 hours

#### Procedure

1. **Stop application services**
   ```bash
   docker-compose stop backend celery-worker celery-beat
   ```

2. **Assess database state**
   ```bash
   docker exec dmarc-db pg_isready -U dmarc
   docker exec dmarc-db psql -U dmarc -c "SELECT 1;"
   ```

3. **If database accessible, create emergency backup**
   ```bash
   ./scripts/backup/backup.sh --type full
   ```

4. **Restore from latest backup**
   ```bash
   # List available backups
   ./scripts/backup/restore.sh --list

   # Restore latest
   ./scripts/backup/restore.sh --latest

   # Or specific backup
   ./scripts/backup/restore.sh /var/backups/dmarc/dmarc_backup_20240101_020000.dump
   ```

5. **Run migrations (if needed)**
   ```bash
   docker exec dmarc-backend alembic upgrade head
   ```

6. **Restart application services**
   ```bash
   docker-compose up -d backend celery-worker celery-beat
   ```

7. **Verify data integrity**
   ```bash
   curl http://localhost:8000/api/domains
   curl http://localhost:8000/api/rollup/summary
   ```

---

### Scenario 3: Complete Server/Host Failure

**Impact:** Complete system unavailability
**Recovery Time:** 2-4 hours

#### Prerequisites
- Access to backup storage
- New server provisioned
- Docker and Docker Compose installed

#### Procedure

1. **Provision new server**
   ```bash
   # Minimum requirements:
   # - Ubuntu 22.04 LTS or later
   # - 8GB RAM, 4 CPU cores
   # - 100GB disk space
   # - Docker 24.0+ and Docker Compose v2

   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh

   # Verify installation
   docker --version
   docker compose version
   ```

2. **Configure network and firewall**
   ```bash
   # Open required ports
   sudo ufw allow 22/tcp   # SSH
   sudo ufw allow 80/tcp   # HTTP
   sudo ufw allow 443/tcp  # HTTPS
   sudo ufw enable

   # Set hostname
   sudo hostnamectl set-hostname dmarc-prod
   ```

3. **Clone application repository**
   ```bash
   # Create application directory
   sudo mkdir -p /opt/dmarc
   sudo chown $(whoami):$(whoami) /opt/dmarc

   # Clone repository
   git clone https://github.com/your-org/dmarc-dashboard.git /opt/dmarc
   cd /opt/dmarc

   # Checkout specific production tag/commit
   git checkout tags/v1.0.0  # or specific commit
   ```

4. **Restore configuration**
   ```bash
   # Option 1: Copy from backup server
   scp backup-server:/backups/config/.env.production /opt/dmarc/.env

   # Option 2: Recreate from template
   cp .env.production.example .env

   # Edit critical variables
   nano .env
   # Required variables:
   # - DATABASE_URL
   # - JWT_SECRET_KEY
   # - JWT_REFRESH_SECRET_KEY
   # - REDIS_PASSWORD
   # - SMTP_* (if notifications enabled)
   # - MAXMIND_LICENSE_KEY
   ```

5. **Create required directories**
   ```bash
   mkdir -p /var/backups/dmarc
   mkdir -p /opt/dmarc/import_reports
   mkdir -p /opt/dmarc/backend/data
   chmod 755 /var/backups/dmarc
   ```

6. **Download GeoIP database**
   ```bash
   # Download MaxMind GeoLite2 database
   cd /opt/dmarc
   ./scripts/setup/download-geoip.sh --license-key $MAXMIND_KEY

   # Verify download
   ls -lh backend/data/GeoLite2-*.mmdb
   ```

7. **Start infrastructure services**
   ```bash
   # Start database and cache first
   docker compose up -d db redis

   # Wait for services to be healthy
   echo "Waiting for database..."
   while ! docker exec dmarc-db pg_isready -U dmarc; do
     sleep 2
   done
   echo "Database ready!"

   echo "Waiting for Redis..."
   while ! docker exec dmarc-redis redis-cli ping; do
     sleep 2
   done
   echo "Redis ready!"
   ```

8. **Restore database**
   ```bash
   # Fetch latest backup from backup server
   scp backup-server:/backups/dmarc_backup_latest.dump /var/backups/dmarc/

   # Verify backup file integrity
   pg_restore --list /var/backups/dmarc/dmarc_backup_latest.dump > /dev/null

   # Restore database
   docker exec -i dmarc-db pg_restore -U dmarc -d dmarc --clean --if-exists < /var/backups/dmarc/dmarc_backup_latest.dump

   # Verify restore
   docker exec dmarc-db psql -U dmarc -c "SELECT COUNT(*) FROM dmarc_reports;"
   docker exec dmarc-db psql -U dmarc -c "SELECT COUNT(*) FROM domains;"
   docker exec dmarc-db psql -U dmarc -c "SELECT COUNT(*) FROM users;"
   ```

9. **Start application services**
   ```bash
   # Start all remaining services
   docker compose up -d

   # Wait for services to stabilize
   sleep 30

   # Check all containers are running
   docker compose ps
   ```

10. **Verify recovery**
    ```bash
    # Health check
    curl -f http://localhost:8000/health || echo "Health check FAILED"

    # Test authentication
    curl -X POST http://localhost:8000/api/auth/login \
      -H "Content-Type: application/json" \
      -d '{"username":"admin","password":"admin"}'

    # Test API endpoints
    curl http://localhost:8000/api/domains

    # Check Celery workers
    docker exec dmarc-celery-worker celery -A celery_worker inspect ping
    docker exec dmarc-celery-worker celery -A celery_worker inspect stats

    # Check logs for errors
    docker compose logs --tail=50 backend
    docker compose logs --tail=50 celery-worker
    ```

11. **Configure SSL/TLS (if using)**
    ```bash
    # Install certbot
    sudo apt install certbot python3-certbot-nginx

    # Obtain certificate
    sudo certbot --nginx -d dmarc.example.com

    # Update nginx config to use SSL
    ```

12. **Update DNS/Load Balancer**
    ```bash
    # Update DNS A record to point to new server IP
    # Example using AWS Route53 CLI:
    aws route53 change-resource-record-sets \
      --hosted-zone-id ZXXXXXXXXXXXXX \
      --change-batch '{
        "Changes": [{
          "Action": "UPSERT",
          "ResourceRecordSet": {
            "Name": "dmarc.example.com",
            "Type": "A",
            "TTL": 300,
            "ResourceRecords": [{"Value": "NEW.SERVER.IP.ADDRESS"}]
          }
        }]
      }'

    # Or update load balancer backend
    # Wait for DNS propagation (up to TTL duration)
    ```

13. **Post-recovery monitoring**
    ```bash
    # Watch logs in real-time
    docker compose logs -f

    # Monitor metrics
    watch -n 5 'docker stats --no-stream'

    # Check error rates
    watch -n 10 'curl -s http://localhost:8000/metrics | grep http_requests_total'
    ```

14. **Notify stakeholders**
    ```bash
    # Send recovery notification
    cat <<EOF | mail -s "DMARC Dashboard Recovery Complete" ops@example.com
    The DMARC Dashboard has been successfully recovered.

    Recovery Details:
    - New server IP: $(hostname -I | awk '{print $1}')
    - Recovery time: $(date)
    - Services status: All operational
    - Data restored from: $(basename /var/backups/dmarc/dmarc_backup_latest.dump)

    Please verify functionality at: https://dmarc.example.com
    EOF
    ```

15. **Document incident**
    - Record timeline of events
    - Note any issues encountered
    - Update runbooks based on experience
    - Schedule post-incident review

---

### Scenario 4: Ransomware/Security Breach

**Impact:** Potential data compromise
**Recovery Time:** 4-8 hours

#### Procedure

1. **Isolate affected systems**
   ```bash
   # Stop all services immediately
   docker-compose down

   # Block network access (if possible)
   iptables -I INPUT -j DROP
   iptables -I OUTPUT -j DROP
   ```

2. **Notify security team**
   - Contact: security@example.com
   - Document initial findings

3. **Preserve evidence**
   ```bash
   # Create forensic copies of logs
   cp -r /var/log/dmarc /forensics/logs_$(date +%Y%m%d)
   docker-compose logs > /forensics/docker_logs_$(date +%Y%m%d).txt
   ```

4. **Assess breach scope**
   - Review audit logs
   - Check for unauthorized access
   - Identify affected data

5. **Recovery on clean infrastructure**
   - Provision new server (air-gapped from compromised)
   - Use verified clean backups (before breach)
   - Follow Scenario 3 procedure

6. **Post-recovery hardening**
   - Rotate all secrets and credentials
   - Update JWT secret keys
   - Reset all user passwords
   - Review and update firewall rules

7. **Post-incident review**
   - Conduct root cause analysis
   - Update security controls
   - Document lessons learned

---

### Scenario 5: Data Center/Cloud Region Failure

**Impact:** Complete unavailability
**Recovery Time:** 4-8 hours

#### Prerequisites
- Off-site backup replication
- Secondary region infrastructure ready

#### Procedure

1. **Activate secondary region**
   - Provision infrastructure in DR region
   - Ensure backups are accessible

2. **Follow Scenario 3 procedure**
   - Use most recent off-site backup

3. **Update DNS**
   - Lower TTL in advance (if planned)
   - Update A/CNAME records to DR region

4. **Verify functionality**
   - Test all critical paths
   - Monitor for errors

---

## Failover Procedures

### Automated Failover (High Availability Setup)

For production environments with HA configuration:

#### Database Failover

1. **Monitor primary database health**
   ```bash
   # Check replication lag
   psql -U postgres -c "SELECT NOW() - pg_last_xact_replay_timestamp() AS replication_lag;"
   ```

2. **Promote standby to primary** (if primary fails)
   ```bash
   # On standby server
   pg_ctl promote -D /var/lib/postgresql/data

   # Verify promotion
   psql -U postgres -c "SELECT pg_is_in_recovery();"  # Should return 'f' (false)
   ```

3. **Update application database connection**
   ```bash
   # Update DATABASE_URL to point to new primary
   # Restart backend services
   docker compose restart backend celery-worker celery-beat
   ```

#### Redis Failover (Sentinel)

1. **Configure Redis Sentinel** (setup)
   ```bash
   # sentinel.conf
   sentinel monitor dmarc-redis redis-primary 6379 2
   sentinel down-after-milliseconds dmarc-redis 5000
   sentinel parallel-syncs dmarc-redis 1
   sentinel failover-timeout dmarc-redis 10000
   ```

2. **Monitor failover**
   ```bash
   # Check sentinel status
   redis-cli -p 26379 SENTINEL masters
   redis-cli -p 26379 SENTINEL slaves dmarc-redis
   ```

3. **Automatic failover** is handled by Sentinel
   - Applications should use Sentinel-aware Redis client
   - Update connection string to use Sentinel endpoints

#### Application Failover

1. **Load balancer health checks**
   ```nginx
   # nginx upstream configuration
   upstream dmarc_backend {
     server backend1:8000 max_fails=3 fail_timeout=30s;
     server backend2:8000 max_fails=3 fail_timeout=30s backup;
   }
   ```

2. **Automatic traffic routing**
   - Load balancer automatically removes unhealthy backends
   - Traffic routes to healthy instances
   - Monitor via load balancer metrics

### Manual Failover

When automated failover is not available or fails:

#### Step 1: Assess Current State

```bash
# Check service status
docker compose ps

# Check resource usage
docker stats --no-stream

# Check logs for errors
docker compose logs --tail=100
```

#### Step 2: Initiate Failover

```bash
# Stop services on failing server
docker compose down

# Update DNS to point to backup server
# Or update load balancer configuration

# Start services on backup server
ssh backup-server
cd /opt/dmarc
docker compose up -d
```

#### Step 3: Verify Failover

```bash
# Test endpoints
curl https://dmarc.example.com/health
curl https://dmarc.example.com/api/domains

# Check database connectivity
docker exec dmarc-backend python -c "from app.database import test_connection; test_connection()"

# Monitor metrics
watch -n 5 'curl -s http://localhost:8000/metrics | grep -E "(http_requests|db_connections)"'
```

### Rollback Procedures

If failover causes issues:

```bash
# 1. Stop services on new primary
docker compose down

# 2. Revert DNS changes
# Update DNS records back to original server

# 3. Restart services on original server
ssh original-server
cd /opt/dmarc
docker compose up -d

# 4. Verify rollback
curl https://dmarc.example.com/health
```

---

## Data Recovery Procedures

### Point-in-Time Recovery (PITR)

Recover database to specific point in time using WAL archives:

```bash
# 1. Stop database
docker compose stop db

# 2. Clear existing data directory
docker volume rm dmarc_postgres_data

# 3. Restore base backup
docker run --rm -v dmarc_postgres_data:/var/lib/postgresql/data \
  postgres:15-alpine \
  pg_basebackup -h backup-server -U replication -D /var/lib/postgresql/data

# 4. Configure recovery
cat > recovery.conf <<EOF
restore_command = 'cp /var/lib/postgresql/wal_archive/%f %p'
recovery_target_time = '2026-02-06 12:00:00'
EOF

docker cp recovery.conf dmarc-db:/var/lib/postgresql/data/

# 5. Start database in recovery mode
docker compose up -d db

# 6. Wait for recovery to complete
docker logs -f dmarc-db | grep "recovery complete"
```

### Selective Data Recovery

Recover specific tables or data:

```bash
# 1. Restore to temporary database
createdb dmarc_temp
pg_restore -U postgres -d dmarc_temp /var/backups/dmarc/dmarc_backup_latest.dump

# 2. Extract specific data
pg_dump -U postgres -d dmarc_temp -t dmarc_reports --data-only > reports_data.sql

# 3. Import to production
psql -U postgres -d dmarc < reports_data.sql

# 4. Cleanup
dropdb dmarc_temp
rm reports_data.sql
```

### Corrupted Data Recovery

If data corruption is detected:

```bash
# 1. Identify affected tables
psql -U dmarc -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public';" | while read table; do
  echo "Checking $table..."
  psql -U dmarc -c "SELECT COUNT(*) FROM $table;" || echo "CORRUPTED: $table"
done

# 2. Restore affected tables from backup
pg_restore -U postgres -d dmarc -t dmarc_reports --data-only /var/backups/dmarc/dmarc_backup_latest.dump

# 3. Verify data integrity
psql -U dmarc -c "SELECT COUNT(*) FROM dmarc_reports;"
psql -U dmarc -c "SELECT MAX(created_at) FROM dmarc_reports;"
```

### Configuration Recovery

Recover lost configuration files:

```bash
# 1. Restore from git repository
cd /opt/dmarc
git checkout HEAD -- .env nginx/nginx.conf

# 2. Or restore from backup
scp backup-server:/backups/config/.env /opt/dmarc/
scp backup-server:/backups/config/nginx.conf /opt/dmarc/nginx/

# 3. Verify configuration
docker compose config

# 4. Apply configuration
docker compose up -d
```

---

## Recovery Verification Checklist

After any disaster recovery, verify:

- [ ] Health endpoint returns healthy status
- [ ] Database connection successful
- [ ] Redis cache operational
- [ ] Celery workers processing tasks
- [ ] Celery beat scheduler running
- [ ] Email ingestion working (if configured)
- [ ] Report processing functional
- [ ] Alert notifications working
- [ ] User authentication working
- [ ] API endpoints responding correctly
- [ ] Frontend accessible and functional
- [ ] SSL certificates valid
- [ ] Monitoring/alerting reconnected

## Communication Plan

### During Incident

| Audience | Channel | Frequency |
|----------|---------|-----------|
| Ops Team | Slack #incidents | Real-time |
| Management | Email | Every 30 min |
| Stakeholders | Status page | Every hour |

### Post Recovery

- Send "All Clear" notification
- Provide incident summary
- Schedule post-mortem (within 48 hours)

## Testing Schedule

| Test Type | Frequency | Scope |
|-----------|-----------|-------|
| Backup verification | Weekly | Automated |
| Restore test | Monthly | Staging |
| Failover drill | Quarterly | Production-like |
| Full DR exercise | Annually | Complete |

## Document Maintenance

- **Owner:** Operations Team
- **Review Frequency:** Quarterly
- **Last Updated:** [DATE]
- **Next Review:** [DATE + 3 months]

## Appendix: Emergency Contacts

| Role | Name | Phone | Email |
|------|------|-------|-------|
| Primary On-Call | [Name] | [Phone] | [Email] |
| Secondary On-Call | [Name] | [Phone] | [Email] |
| Database Admin | [Name] | [Phone] | [Email] |
| Security Lead | [Name] | [Phone] | [Email] |
| Management | [Name] | [Phone] | [Email] |

## Appendix A: Critical Credentials Location

| Credential | Location | Access |
|------------|----------|--------|
| Database passwords | Secrets Manager | Ops team |
| JWT secret | Secrets Manager | Ops team |
| API keys | Secrets Manager | Ops team |
| Backup encryption | Secrets Manager | Ops team |
| Cloud provider | IAM | Ops team |

---

## Appendix B: Backup Automation Scripts

### Daily Backup Script

Location: `/opt/dmarc/scripts/backup/daily-backup.sh`

```bash
#!/bin/bash
# Daily automated backup script
# Cron: 0 2 * * * /opt/dmarc/scripts/backup/daily-backup.sh

set -e

# Configuration
BACKUP_DIR="/var/backups/dmarc"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/dmarc_backup_${DATE}.dump"
LOG_FILE="${BACKUP_DIR}/backup_${DATE}.log"

# Logging function
log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting daily backup..."

# Create backup directory if not exists
mkdir -p "$BACKUP_DIR"

# Perform database backup
log "Creating database backup..."
docker exec dmarc-db pg_dump -U dmarc -Fc -f /tmp/backup.dump dmarc

# Copy backup from container
docker cp dmarc-db:/tmp/backup.dump "$BACKUP_FILE"

# Verify backup
log "Verifying backup integrity..."
pg_restore --list "$BACKUP_FILE" > /dev/null 2>&1
if [ $? -eq 0 ]; then
  log "Backup verification PASSED"
else
  log "ERROR: Backup verification FAILED"
  exit 1
fi

# Calculate backup size
SIZE=$(stat -c%s "$BACKUP_FILE")
SIZE_MB=$((SIZE / 1024 / 1024))
log "Backup size: ${SIZE_MB}MB"

# Create latest symlink
ln -sf "$BACKUP_FILE" "${BACKUP_DIR}/dmarc_backup_latest.dump"

# Backup configuration files
log "Backing up configuration..."
tar -czf "${BACKUP_DIR}/config_${DATE}.tar.gz" \
  /opt/dmarc/.env \
  /opt/dmarc/nginx/nginx.conf \
  /opt/dmarc/docker-compose.yml

# Sync to remote backup server (optional)
if [ -n "$BACKUP_REMOTE_SERVER" ]; then
  log "Syncing to remote backup server..."
  rsync -avz "$BACKUP_FILE" "${BACKUP_REMOTE_SERVER}:/backups/dmarc/"
fi

# Cleanup old backups
log "Cleaning up old backups (retention: ${RETENTION_DAYS} days)..."
find "$BACKUP_DIR" -name "dmarc_backup_*.dump" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -name "config_*.tar.gz" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -name "backup_*.log" -mtime +${RETENTION_DAYS} -delete

log "Backup completed successfully"

# Send metrics to monitoring (optional)
if command -v curl &> /dev/null && [ -n "$PUSHGATEWAY_URL" ]; then
  echo "dmarc_backup_size_bytes ${SIZE}" | curl --data-binary @- ${PUSHGATEWAY_URL}/metrics/job/dmarc-backup
  echo "dmarc_backup_success 1" | curl --data-binary @- ${PUSHGATEWAY_URL}/metrics/job/dmarc-backup
fi
```

### Restore Script

Location: `/opt/dmarc/scripts/backup/restore.sh`

```bash
#!/bin/bash
# Database restore script
# Usage: ./restore.sh <backup_file>

set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file>"
  echo "Example: $0 /var/backups/dmarc/dmarc_backup_latest.dump"
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Error: Backup file not found: $BACKUP_FILE"
  exit 1
fi

echo "WARNING: This will replace the current database with backup from:"
echo "  $BACKUP_FILE"
read -p "Are you sure? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
  echo "Restore cancelled"
  exit 0
fi

echo "Stopping application services..."
docker compose stop backend celery-worker celery-beat

echo "Copying backup to database container..."
docker cp "$BACKUP_FILE" dmarc-db:/tmp/restore.dump

echo "Restoring database..."
docker exec dmarc-db pg_restore -U dmarc -d dmarc --clean --if-exists /tmp/restore.dump

echo "Running migrations (if any)..."
docker compose run --rm backend alembic upgrade head

echo "Starting application services..."
docker compose up -d backend celery-worker celery-beat

echo "Restore completed successfully"
echo "Verifying..."
sleep 5
curl -f http://localhost:8000/health && echo "Health check PASSED" || echo "Health check FAILED"
```

### Backup Verification Cron

Add to crontab:

```cron
# Daily backup at 2 AM
0 2 * * * /opt/dmarc/scripts/backup/daily-backup.sh

# Weekly backup verification at 3 AM on Sundays
0 3 * * 0 /opt/dmarc/scripts/backup/verify-backup.sh

# Monthly full DR test (first Saturday at 4 AM)
0 4 1-7 * 6 [ $(date +\%u) -eq 6 ] && /opt/dmarc/scripts/backup/dr-test.sh
```

---

## Appendix C: Monitoring and Alerting Setup

### Prometheus Alerts for DR

```yaml
# alerts/disaster-recovery.yml
groups:
  - name: disaster_recovery
    interval: 1m
    rules:
      # Backup failure alert
      - alert: BackupFailed
        expr: time() - dmarc_backup_last_success_timestamp > 86400
        for: 1h
        labels:
          severity: critical
        annotations:
          summary: "Database backup failed"
          description: "No successful backup in last 24 hours"

      # Backup size anomaly
      - alert: BackupSizeAnomaly
        expr: |
          abs(dmarc_backup_size_bytes - avg_over_time(dmarc_backup_size_bytes[7d]))
          / avg_over_time(dmarc_backup_size_bytes[7d]) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Backup size anomaly detected"
          description: "Backup size differs significantly from average"

      # Replication lag (for HA setups)
      - alert: DatabaseReplicationLag
        expr: pg_replication_lag_seconds > 300
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Database replication lag detected"
          description: "Replication lag is {{ $value }}s"

      # Disk space for backups
      - alert: BackupDiskSpaceLow
        expr: |
          (node_filesystem_avail_bytes{mountpoint="/var/backups"}
          / node_filesystem_size_bytes{mountpoint="/var/backups"}) < 0.15
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Backup disk space low"
          description: "Only {{ $value | humanizePercentage }} space remaining"
```

### Grafana Dashboard for DR Metrics

```json
{
  "title": "Disaster Recovery Monitoring",
  "panels": [
    {
      "title": "Last Successful Backup",
      "targets": [{
        "expr": "time() - dmarc_backup_last_success_timestamp"
      }],
      "type": "stat"
    },
    {
      "title": "Backup Size Trend",
      "targets": [{
        "expr": "dmarc_backup_size_bytes"
      }],
      "type": "timeseries"
    },
    {
      "title": "Backup Success Rate",
      "targets": [{
        "expr": "rate(dmarc_backup_success[24h])"
      }],
      "type": "gauge"
    }
  ]
}
```

---

## Appendix D: DR Test Checklist

### Monthly DR Test Checklist

- [ ] Review and update DR documentation
- [ ] Verify backup files exist and are accessible
- [ ] Test backup file integrity
- [ ] Perform test restore to staging environment
- [ ] Verify all services start correctly after restore
- [ ] Test critical application functionality
- [ ] Verify data integrity (record counts, latest entries)
- [ ] Test authentication and authorization
- [ ] Measure time to recovery (TTR)
- [ ] Document any issues or improvements needed
- [ ] Update runbooks based on findings
- [ ] Send DR test report to stakeholders

### Quarterly DR Drill Checklist

- [ ] Schedule maintenance window
- [ ] Notify all stakeholders
- [ ] Simulate complete infrastructure failure
- [ ] Execute full recovery procedure
- [ ] Test failover to secondary region (if applicable)
- [ ] Verify DNS/load balancer updates
- [ ] Test monitoring and alerting
- [ ] Conduct post-drill review meeting
- [ ] Update SLOs based on measured recovery time
- [ ] Create action items for improvements

---

## Appendix E: Contact Information Template

### Emergency Contact Tree

```
Level 1: On-Call Engineer
├── Primary: [Name] [Phone] [Email]
└── Secondary: [Name] [Phone] [Email]

Level 2: Team Lead
├── DevOps Lead: [Name] [Phone] [Email]
└── Engineering Manager: [Name] [Phone] [Email]

Level 3: Management
├── CTO: [Name] [Phone] [Email]
└── VP Engineering: [Name] [Phone] [Email]

External Contacts:
├── Cloud Provider Support: [Phone] [Account ID]
├── Database Vendor Support: [Phone] [Contract #]
└── Backup Service Provider: [Phone] [Account ID]
```

### Escalation Matrix

| Time Since Incident | Action |
|---------------------|--------|
| 0 min | Alert on-call engineer |
| 15 min | If unresolved, escalate to secondary on-call |
| 30 min | Escalate to team lead |
| 1 hour | Escalate to management |
| 2 hours | Engage external support if needed |
| 4 hours | Executive notification |
