# DMARC Report Processor - Production Deployment Guide

This guide provides comprehensive instructions for deploying the DMARC Report Processor in production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Security Configuration](#security-configuration)
4. [Database Setup](#database-setup)
5. [SSL/TLS Configuration](#ssltls-configuration)
6. [Monitoring & Health Checks](#monitoring--health-checks)
7. [Backup & Restore](#backup--restore)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04/22.04 LTS recommended)
- **Docker**: Version 20.10+
- **Docker Compose**: Version 2.0+
- **RAM**: Minimum 2GB, recommended 4GB
- **Disk**: Minimum 10GB free space
- **Ports**: 80, 443 (nginx), 5432 (PostgreSQL - internal only)

### Domain & DNS
- Domain name pointed to your server's IP address
- SSL certificate (Let's Encrypt recommended)

---

## Quick Start

### 1. Clone Repository

\`\`\`bash
cd /opt
git clone https://github.com/yourusername/dmarc.git
cd dmarc
\`\`\`

### 2. Copy Production Environment File

\`\`\`bash
cp .env.production.example .env.production
\`\`\`

### 3. Generate Secure Credentials

\`\`\`bash
# Generate API keys
python3 -c "import secrets; print('API_KEY_1=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('API_KEY_2=' + secrets.token_urlsafe(32))"

# Generate database password
python3 -c "import secrets; print('DB_PASSWORD=' + secrets.token_urlsafe(24))"
\`\`\`

### 4. Configure Environment

Edit \`.env.production\` and update:
- \`DATABASE_URL\` with strong password
- \`API_KEYS\` with generated keys
- \`EMAIL_*\` settings for your IMAP provider
- \`SMTP_*\` settings for alerting
- Webhook URLs for Slack/Discord/Teams

### 5. Build and Start

\`\`\`bash
docker-compose up -d --build
\`\`\`

### 6. Verify Deployment

\`\`\`bash
# Check health
curl http://localhost/health

# View logs
docker-compose logs -f backend
\`\`\`

---

## Security Configuration

### API Key Authentication

**Enable in production:**

\`\`\`env
# .env.production
REQUIRE_API_KEY=true
API_KEYS=your-secret-key-1,your-secret-key-2
\`\`\`

**Using API keys:**

\`\`\`bash
# Upload reports
curl -X POST https://dmarc.yourdomain.com/api/upload \
  -H "X-API-Key: your-secret-key-1" \
  -F "files=@report.xml.gz"
\`\`\`

### Rate Limiting

Automatically enforced:
- **Upload**: 20 requests/hour
- **Triggers**: 10 requests/minute
- **General API**: 100 requests/minute

Configure in \`backend/app/middleware/rate_limit.py\`.

### CORS Configuration

\`\`\`env
DEBUG=false  # Disables wildcard CORS
\`\`\`

### Dashboard Basic Auth (Optional)

\`\`\`bash
# Generate credentials
./scripts/generate_htpasswd.sh

# Enable in nginx.conf (uncomment auth_basic lines)
# Restart: docker-compose restart nginx
\`\`\`

---

## Database Setup

### PostgreSQL Configuration

\`\`\`yaml
# docker-compose.yml (production)
db:
  image: postgres:15-alpine
  restart: always
  environment:
    POSTGRES_PASSWORD: \${DB_PASSWORD}
  ports:
    - "127.0.0.1:5432:5432"  # Localhost only
\`\`\`

### Run Migrations

\`\`\`bash
docker-compose exec backend alembic upgrade head
\`\`\`

---

## SSL/TLS Configuration

### Let's Encrypt Setup

\`\`\`bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot certonly --standalone -d dmarc.yourdomain.com

# Certificates location:
# /etc/letsencrypt/live/dmarc.yourdomain.com/
\`\`\`

### Update nginx

Use \`nginx/nginx-auth.conf.example\` as template and add SSL configuration.

---

## Monitoring & Health Checks

### Health Endpoint

\`\`\`bash
curl https://dmarc.yourdomain.com/health
\`\`\`

### Alerting

Configure in \`.env.production\`:

\`\`\`env
ENABLE_ALERTS=true
ALERT_FAILURE_WARNING=10.0
ALERT_EMAIL_TO=admin@yourdomain.com
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
\`\`\`

---

## Backup & Restore

### Database Backup

\`\`\`bash
# Backup
docker-compose exec -T db pg_dump -U dmarc_prod dmarc_prod | \
  gzip > backups/dmarc_\$(date +%Y%m%d).sql.gz

# Restore
gunzip < backups/dmarc_20260107.sql.gz | \
  docker-compose exec -T db psql -U dmarc_prod dmarc_prod
\`\`\`

### Automated Backups

\`\`\`bash
# Create backup script
cat > /opt/dmarc/backup.sh << 'EOF'
#!/bin/bash
DATE=\$(date +%Y%m%d)
docker-compose exec -T db pg_dump -U dmarc_prod dmarc_prod | \
  gzip > /opt/dmarc/backups/dmarc_\${DATE}.sql.gz
find /opt/dmarc/backups -name "*.sql.gz" -mtime +30 -delete
EOF

chmod +x /opt/dmarc/backup.sh

# Add to cron (daily at 3am)
echo "0 3 * * * /opt/dmarc/backup.sh" | crontab -
\`\`\`

---

## Troubleshooting

### Backend Won't Start

\`\`\`bash
# Check logs
docker-compose logs backend

# Common issues:
# 1. Database not ready - wait for healthcheck
# 2. Missing env vars - check .env.production
# 3. Port conflicts - check if 8000 is in use
\`\`\`

### Email Ingestion Errors

\`\`\`bash
# Test email connection
docker-compose exec backend python -c "
from app.services.email_client import IMAPClient
from app.config import get_settings
settings = get_settings()
client = IMAPClient(settings)
print('Connected successfully')
"
\`\`\`

### Database Issues

\`\`\`bash
# Test connection
docker-compose exec db psql -U dmarc_prod -d dmarc_prod

# Check database size
docker-compose exec db psql -U dmarc_prod -c "\l+"
\`\`\`

---

## Security Checklist

- [ ] Changed all default passwords
- [ ] Generated secure API keys  
- [ ] Enabled \`REQUIRE_API_KEY=true\`
- [ ] Configured HTTPS/TLS
- [ ] Restricted database to localhost
- [ ] Set up firewall (UFW/iptables)
- [ ] Enabled basic auth for dashboard (optional)
- [ ] Set \`DEBUG=false\`
- [ ] Configured automated backups
- [ ] Set up monitoring/alerting
- [ ] Reviewed nginx security headers

---

## Performance Tips

1. **Database Indexing**: Already optimized in migrations
2. **Caching**: Add Redis for dashboard caching (future enhancement)
3. **CDN**: Use Cloudflare for static assets
4. **Compression**: Enabled in nginx
5. **Rate Limiting**: Adjust limits in \`rate_limit.py\` if needed

---

For more information, see:
- \`README.md\` - General overview
- \`EMAIL_SETUP.md\` - Email ingestion setup
- \`.env.production.example\` - All configuration options

