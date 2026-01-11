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

Backups are verified:
- **Automatically**: Integrity check after each backup
- **Monthly**: Test restore to staging environment
- **Quarterly**: Full DR drill

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
   - Ensure Docker and Docker Compose are installed
   - Configure network and firewall rules
   - Mount backup storage

2. **Clone application repository**
   ```bash
   git clone https://github.com/your-org/dmarc-dashboard.git /opt/dmarc
   cd /opt/dmarc
   ```

3. **Restore configuration**
   ```bash
   # Copy production environment file
   cp /backup/config/.env.production .env

   # Or recreate from template
   cp .env.production.example .env
   # Edit .env with production values
   ```

4. **Download GeoIP database**
   ```bash
   ./scripts/setup/download-geoip.sh --license-key $MAXMIND_KEY
   ```

5. **Start infrastructure services**
   ```bash
   docker-compose up -d db redis
   sleep 30  # Wait for services
   ```

6. **Restore database**
   ```bash
   # Copy backup to new server
   scp backup-server:/backups/dmarc_backup_latest.dump /var/backups/dmarc/

   # Restore
   ./scripts/backup/restore.sh /var/backups/dmarc/dmarc_backup_latest.dump
   ```

7. **Start application services**
   ```bash
   docker-compose up -d
   ```

8. **Verify recovery**
   ```bash
   # Health check
   curl http://localhost:8000/health

   # Test API
   curl http://localhost:8000/api/domains

   # Check Celery
   docker exec dmarc-celery-worker celery -A celery_worker inspect ping
   ```

9. **Update DNS/Load Balancer**
   - Point DNS to new server IP
   - Update load balancer backend

10. **Notify stakeholders**
    - Send recovery notification
    - Document incident timeline

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

## Appendix: Critical Credentials Location

| Credential | Location | Access |
|------------|----------|--------|
| Database passwords | Secrets Manager | Ops team |
| JWT secret | Secrets Manager | Ops team |
| API keys | Secrets Manager | Ops team |
| Backup encryption | Secrets Manager | Ops team |
| Cloud provider | IAM | Ops team |
