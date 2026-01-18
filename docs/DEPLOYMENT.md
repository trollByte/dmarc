# DMARC Dashboard Deployment Guide

This guide covers deployment options for the DMARC Dashboard, from local development to production Kubernetes clusters.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (Docker Compose)](#quick-start-docker-compose)
- [Configuration](#configuration)
- [Production Deployment](#production-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Security Considerations](#security-considerations)
- [Monitoring Setup](#monitoring-setup)
- [Backup and Recovery](#backup-and-recovery)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- Docker 20.10+ and Docker Compose 2.0+
- PostgreSQL 14+ (or use containerized version)
- Redis 6+ (for caching and Celery)

### Optional Software

- Kubernetes 1.25+ (for K8s deployment)
- Helm 3.0+ (for K8s deployment)
- kubectl configured for your cluster

## Quick Start (Docker Compose)

### 1. Clone and Configure

```bash
git clone https://github.com/your-org/dmarc.git
cd dmarc

# Copy environment template
cp backend/.env.example backend/.env

# Edit configuration
nano backend/.env
```

### 2. Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://dmarc:dmarc@db:5432/dmarc

# JWT Authentication (REQUIRED - generate your own)
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")

# Email Ingestion (optional but recommended)
EMAIL_HOST=imap.gmail.com
EMAIL_PORT=993
EMAIL_USER=your-dmarc-inbox@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_USE_SSL=true

# Frontend URL
FRONTEND_URL=http://localhost:3000
```

### 3. Start Services

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f backend
```

### 4. Initialize Database

```bash
# Run migrations
docker compose exec backend alembic upgrade head

# Create admin user
docker compose exec backend python -c "
from app.database import SessionLocal
from app.models.user import User, UserRole
from passlib.hash import bcrypt
import uuid

db = SessionLocal()
admin = User(
    id=uuid.uuid4(),
    username='admin',
    email='admin@example.com',
    hashed_password=bcrypt.hash('changeme123!'),
    role=UserRole.ADMIN.value,
    is_active=True
)
db.add(admin)
db.commit()
print('Admin user created')
"
```

### 5. Access Dashboard

- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Configuration

### Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://dmarc:dmarc@db:5432/dmarc` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | JWT signing key (required) | - |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `15` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` |
| `DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `*` (dev only) |
| `REQUIRE_API_KEY` | Require API key for protected endpoints | `false` |

### Email Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `EMAIL_HOST` | IMAP server hostname | - |
| `EMAIL_PORT` | IMAP server port | `993` |
| `EMAIL_USER` | Email username | - |
| `EMAIL_PASSWORD` | Email password/app password | - |
| `EMAIL_FOLDER` | Folder to check for reports | `INBOX` |
| `EMAIL_USE_SSL` | Use SSL/TLS | `true` |

### Alerting Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_ALERTS` | Enable alerting system | `false` |
| `ALERT_FAILURE_WARNING` | Warning threshold (%) | `10.0` |
| `ALERT_FAILURE_CRITICAL` | Critical threshold (%) | `25.0` |
| `SMTP_HOST` | SMTP server for alerts | - |
| `SLACK_WEBHOOK_URL` | Slack webhook for alerts | - |

## Production Deployment

### Docker Compose (Production)

1. Use production compose file:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

2. Production `.env` settings:

```bash
DEBUG=false
LOG_JSON=true
REQUIRE_API_KEY=true
CORS_ORIGINS=https://your-domain.com
ENABLE_HSTS=true
```

### Reverse Proxy (nginx)

```nginx
upstream dmarc_backend {
    server localhost:8000;
}

upstream dmarc_frontend {
    server localhost:3000;
}

server {
    listen 443 ssl http2;
    server_name dmarc.yourdomain.com;

    ssl_certificate /etc/ssl/certs/dmarc.crt;
    ssl_certificate_key /etc/ssl/private/dmarc.key;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # API routes
    location /api/ {
        proxy_pass http://dmarc_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Rate limiting
        limit_req zone=api burst=20 nodelay;
    }

    # Frontend
    location / {
        proxy_pass http://dmarc_frontend;
        proxy_set_header Host $host;
    }
}
```

## Kubernetes Deployment

### Using Kustomize

```bash
# Review base configuration
ls k8s/base/

# Deploy to development
kubectl apply -k k8s/overlays/dev/

# Deploy to production
kubectl apply -k k8s/overlays/prod/
```

### Using Helm

```bash
# Add values
cat > values-prod.yaml <<EOF
backend:
  replicaCount: 3
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 1Gi

postgresql:
  enabled: true
  auth:
    postgresPassword: your-secure-password
    database: dmarc

redis:
  enabled: true
  auth:
    enabled: true
    password: your-redis-password

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: dmarc.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: dmarc-tls
      hosts:
        - dmarc.yourdomain.com
EOF

# Install/upgrade
helm upgrade --install dmarc ./helm/dmarc \
  -f values-prod.yaml \
  --namespace dmarc \
  --create-namespace
```

### Scaling

```bash
# Scale backend
kubectl scale deployment dmarc-backend --replicas=5 -n dmarc

# Scale Celery workers
kubectl scale deployment dmarc-celery-worker --replicas=3 -n dmarc

# Enable HPA
kubectl autoscale deployment dmarc-backend \
  --cpu-percent=70 \
  --min=2 \
  --max=10 \
  -n dmarc
```

## Security Considerations

### Required Security Steps

1. **Generate secure JWT secret:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

2. **Set secure database password**

3. **Configure CORS origins** - Don't use `*` in production

4. **Enable HTTPS** - Use valid TLS certificates

5. **Set up network policies** (K8s):
   ```bash
   kubectl apply -f k8s/base/network-policies.yaml
   ```

### Security Headers

The application automatically adds these headers in production:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: default-src 'self'; ...`

### Rate Limiting

Default rate limits:
- Global: 100 requests/minute per IP
- Auth endpoints: 10 requests/minute per IP
- Upload endpoints: 20 requests/minute per IP

## Monitoring Setup

### Prometheus + Grafana

1. Deploy monitoring stack:
   ```bash
   docker compose -f docker-compose.monitoring.yml up -d
   ```

2. Access dashboards:
   - Grafana: http://localhost:3001 (admin/admin)
   - Prometheus: http://localhost:9090

3. Import dashboards:
   - DMARC Operations: `monitoring/grafana/dashboards/dmarc-dashboard.json`
   - DMARC Analytics: `monitoring/grafana/dashboards/dmarc-analytics.json`

### Metrics Endpoint

```bash
curl http://localhost:8000/metrics
```

Available metrics:
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `dmarc_reports_processed_total` - Reports processed
- `dmarc_records_ingested_total` - Records ingested
- `alerts_triggered_total` - Alerts triggered

## Backup and Recovery

### Database Backup

```bash
# Backup
docker compose exec db pg_dump -U dmarc dmarc > backup.sql

# Restore
docker compose exec -T db psql -U dmarc dmarc < backup.sql
```

### Automated Backups

See `docs/DISASTER_RECOVERY.md` for automated backup procedures.

## Troubleshooting

### Common Issues

**Database Connection Failed**
```bash
# Check database is running
docker compose ps db

# Check logs
docker compose logs db

# Verify connection string
docker compose exec backend python -c "from app.database import check_db_connection; print(check_db_connection())"
```

**Email Ingestion Not Working**
```bash
# Check email configuration
docker compose exec backend python -c "
from app.services.email_client import EmailClient
client = EmailClient()
print(client.test_connection())
"

# Check logs
docker compose logs backend | grep -i email
```

**High Memory Usage**
```bash
# Check container stats
docker stats

# Restart workers
docker compose restart celery-worker
```

### Getting Help

- Check logs: `docker compose logs -f backend`
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- GitHub Issues: https://github.com/your-org/dmarc/issues
