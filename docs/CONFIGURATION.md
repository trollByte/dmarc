# DMARC Dashboard Configuration Reference

Complete reference for all configuration options available in the DMARC Dashboard.

## Environment Variables

All configuration is done through environment variables. Create a `.env` file in the backend directory or set variables in your deployment environment.

### Core Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APP_NAME` | string | `DMARC Report Processor` | Application name displayed in UI |
| `DEBUG` | bool | `false` | Enable debug mode (enables docs, verbose logging) |
| `LOG_LEVEL` | string | `INFO` | Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `LOG_DIR` | string | `/app/logs` | Directory for log files |
| `LOG_JSON` | bool | `false` | Output logs in JSON format |
| `ENABLE_REQUEST_LOGGING` | bool | `true` | Log all HTTP requests |

### Database

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DATABASE_URL` | string | `postgresql://dmarc:dmarc@db:5432/dmarc` | PostgreSQL connection string |

**Format:** `postgresql://user:password@host:port/database`

**Examples:**
```bash
# Local development
DATABASE_URL=postgresql://dmarc:dmarc@localhost:5432/dmarc

# Docker
DATABASE_URL=postgresql://dmarc:dmarc@db:5432/dmarc

# Production with SSL
DATABASE_URL=postgresql://dmarc:secure_pass@db.example.com:5432/dmarc?sslmode=require
```

### Redis Cache

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REDIS_URL` | string | `redis://redis:6379/0` | Redis connection string |
| `CACHE_ENABLED` | bool | `true` | Enable caching |
| `CACHE_DEFAULT_TTL` | int | `300` | Default cache TTL in seconds |

### Celery (Background Tasks)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CELERY_BROKER_URL` | string | `redis://redis:6379/1` | Celery broker URL |
| `CELERY_RESULT_BACKEND` | string | (database) | Celery result backend |
| `CELERY_TASK_TRACK_STARTED` | bool | `true` | Track task start times |
| `CELERY_TASK_TIME_LIMIT` | int | `1800` | Task timeout in seconds |
| `USE_CELERY` | bool | `false` | Use Celery instead of APScheduler |

### JWT Authentication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `JWT_SECRET_KEY` | string | **REQUIRED** | Secret key for JWT signing |
| `JWT_ALGORITHM` | string | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | int | `15` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | int | `7` | Refresh token lifetime |

**Generate a secure secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### API Key Authentication (Legacy)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REQUIRE_API_KEY` | bool | `false` | Require API key for protected endpoints |
| `API_KEYS` | string | | Comma-separated list of valid API keys |

### Password Policy

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PASSWORD_MIN_LENGTH` | int | `12` | Minimum password length |
| `PASSWORD_REQUIRE_UPPERCASE` | bool | `true` | Require uppercase letters |
| `PASSWORD_REQUIRE_LOWERCASE` | bool | `true` | Require lowercase letters |
| `PASSWORD_REQUIRE_DIGIT` | bool | `true` | Require digits |
| `PASSWORD_REQUIRE_SPECIAL` | bool | `true` | Require special characters |

### Account Security

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MAX_FAILED_LOGIN_ATTEMPTS` | int | `5` | Max failed logins before lockout |
| `ACCOUNT_LOCKOUT_DURATION_MINUTES` | int | `30` | Lockout duration |

### Security Headers

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CORS_ORIGINS` | string | | Allowed CORS origins (comma-separated) |
| `ALLOWED_HOSTS` | string | | Allowed Host headers (comma-separated) |
| `ENABLE_HSTS` | bool | `true` | Enable HTTP Strict Transport Security |
| `MAX_REQUEST_SIZE` | int | `52428800` | Max request body size (50MB) |

### Email Ingestion (IMAP)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `EMAIL_HOST` | string | | IMAP server hostname |
| `EMAIL_PORT` | int | `993` | IMAP server port |
| `EMAIL_USER` | string | | Email username |
| `EMAIL_PASSWORD` | string | | Email password or app password |
| `EMAIL_FOLDER` | string | `INBOX` | Folder to check for reports |
| `EMAIL_USE_SSL` | bool | `true` | Use SSL/TLS connection |

**Gmail Setup:**
1. Enable IMAP in Gmail settings
2. Create an App Password (requires 2FA)
3. Use the app password, not your account password

```bash
EMAIL_HOST=imap.gmail.com
EMAIL_PORT=993
EMAIL_USER=your-dmarc@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_USE_SSL=true
```

### Alerting

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_ALERTS` | bool | `false` | Enable alerting system |
| `ALERT_FAILURE_WARNING` | float | `10.0` | Warning threshold (%) |
| `ALERT_FAILURE_CRITICAL` | float | `25.0` | Critical threshold (%) |
| `ALERT_VOLUME_SPIKE` | float | `50.0` | Volume increase alert (%) |
| `ALERT_VOLUME_DROP` | float | `-30.0` | Volume decrease alert (%) |

### SMTP (Alert Emails)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SMTP_HOST` | string | | SMTP server hostname |
| `SMTP_PORT` | int | `587` | SMTP server port |
| `SMTP_USER` | string | | SMTP username |
| `SMTP_PASSWORD` | string | | SMTP password |
| `SMTP_FROM` | string | | From email address |
| `SMTP_USE_TLS` | bool | `true` | Use TLS |
| `ALERT_EMAIL_TO` | string | | Default alert recipient |

### Webhook Notifications

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SLACK_WEBHOOK_URL` | string | | Slack incoming webhook URL |
| `DISCORD_WEBHOOK_URL` | string | | Discord webhook URL |
| `TEAMS_WEBHOOK_URL` | string | | Microsoft Teams webhook URL |
| `WEBHOOK_URL` | string | | Generic webhook URL |

### Threat Intelligence

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ABUSEIPDB_API_KEY` | string | | AbuseIPDB API key |
| `VIRUSTOTAL_API_KEY` | string | | VirusTotal API key |

### OAuth / SSO

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OAUTH_ENABLED` | bool | `false` | Enable OAuth authentication |
| `OAUTH_BASE_URL` | string | | Base URL for OAuth redirects |

### Google OAuth

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `GOOGLE_CLIENT_ID` | string | | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | string | | Google OAuth client secret |

### Microsoft OAuth (Azure AD)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MICROSOFT_CLIENT_ID` | string | | Azure AD application ID |
| `MICROSOFT_CLIENT_SECRET` | string | | Azure AD client secret |
| `MICROSOFT_TENANT_ID` | string | `common` | Azure AD tenant ID |

### Storage

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RAW_REPORTS_PATH` | string | `/app/storage/raw_reports` | Path for raw report storage |

### Frontend

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FRONTEND_URL` | string | `http://localhost:3000` | Frontend URL (for links in emails) |

## Example Configurations

### Development

```bash
# .env
DEBUG=true
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://dmarc:dmarc@localhost:5432/dmarc
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=dev-secret-key-change-in-production
REQUIRE_API_KEY=false
```

### Production

```bash
# .env
DEBUG=false
LOG_LEVEL=INFO
LOG_JSON=true

DATABASE_URL=postgresql://dmarc:secure_password@db.internal:5432/dmarc?sslmode=require
REDIS_URL=redis://:redis_password@redis.internal:6379/0

JWT_SECRET_KEY=your-64-char-secure-random-key-here
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ORIGINS=https://dmarc.yourdomain.com
ALLOWED_HOSTS=dmarc.yourdomain.com
ENABLE_HSTS=true

ENABLE_ALERTS=true
ALERT_FAILURE_WARNING=10.0
ALERT_FAILURE_CRITICAL=25.0

SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_FROM=dmarc@yourdomain.com
ALERT_EMAIL_TO=security@yourdomain.com

EMAIL_HOST=imap.gmail.com
EMAIL_PORT=993
EMAIL_USER=dmarc-reports@yourdomain.com
EMAIL_PASSWORD=app-specific-password
EMAIL_USE_SSL=true

FRONTEND_URL=https://dmarc.yourdomain.com
```

### Kubernetes (via ConfigMap/Secret)

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: dmarc-config
data:
  DEBUG: "false"
  LOG_LEVEL: "INFO"
  LOG_JSON: "true"
  ENABLE_ALERTS: "true"
  ALERT_FAILURE_WARNING: "10.0"
  CORS_ORIGINS: "https://dmarc.yourdomain.com"

---
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: dmarc-secrets
type: Opaque
stringData:
  DATABASE_URL: "postgresql://..."
  JWT_SECRET_KEY: "your-secure-key"
  EMAIL_PASSWORD: "your-email-password"
```

## Rate Limiting

Default rate limits are configured in the application:

| Endpoint Pattern | Limit |
|------------------|-------|
| Global default | 100/minute |
| `/auth/*` | 10/minute |
| `/api/upload` | 20/minute |

To customize, modify `app/middleware/rate_limit.py`.

## Logging

### Log Levels

| Level | Description |
|-------|-------------|
| `DEBUG` | Detailed debugging information |
| `INFO` | General operational information |
| `WARNING` | Warning messages |
| `ERROR` | Error messages |
| `CRITICAL` | Critical errors |

### Log Rotation

Logs are automatically rotated:
- Max file size: 10MB
- Backup count: 5 files
- Location: `LOG_DIR` setting

### JSON Logging

Enable `LOG_JSON=true` for production. JSON logs include:
- Timestamp
- Log level
- Logger name
- Message
- Extra context fields
