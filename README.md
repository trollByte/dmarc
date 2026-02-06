# DMARC Aggregate Report Processor
## Enterprise-Grade DMARC Analytics Platform

A production-ready enterprise platform that ingests, processes, and analyzes DMARC aggregate reports with advanced ML-powered threat detection, distributed task processing, and comprehensive security features.

---

## 🚀 Features

### Core Functionality
- 📧 **Automated DMARC Report Ingestion** - IMAP inbox monitoring with Celery task queue
- 📤 **Bulk File Upload** - Drag-and-drop 50-200 reports simultaneously
- 🔄 **Idempotent Processing** - SHA256-based duplicate prevention
- 💾 **PostgreSQL Storage** - Production-grade relational database
- 🔐 **JWT Authentication** - Role-based access control (Admin/Analyst/Viewer)
- 🚀 **RESTful API** - FastAPI with auto-generated documentation
- ✅ **Comprehensive Testing** - 70%+ code coverage enforced
- 🐳 **Docker Deployment** - Single-command orchestration
- 🔔 **Multi-Channel Alerting** - Email, Slack, Discord, Microsoft Teams

### 🎯 Enterprise Features (NEW)

#### Phase 1: Distributed Task Processing
- ⚡ **Celery + Redis Queue** - Asynchronous background job processing
- 📅 **Celery Beat Scheduler** - Automated periodic tasks
  - Email ingestion every 15 minutes
  - Report processing every 5 minutes
  - Alert checks hourly
  - ML model training weekly
- 🌸 **Flower Dashboard** - Real-time task monitoring at `:5555`
- 🔄 **Retry Logic** - Exponential backoff with 3 attempts
- 📊 **Task Tracking** - PostgreSQL result backend

#### Phase 2: Authentication & Authorization
- 🔑 **JWT Authentication** - Access tokens (15min) + refresh tokens (7 days)
- 👥 **Role-Based Access Control** - Admin, Analyst, Viewer roles
- 🔐 **API Key Management** - Per-user API keys with SHA256 hashing
- 🛡️ **Password Security** - bcrypt hashing (12 rounds)
- 📝 **User Management** - Admin-only user creation (no self-registration)
- 🔄 **Token Refresh** - Seamless token renewal
- 📋 **Audit Trail** - User action tracking

#### Phase 3: Enhanced Alerting
- 🎯 **Alert Lifecycle** - Created → Acknowledged → Resolved
- 🔕 **Deduplication** - SHA256 fingerprinting with cooldown periods
- ⏰ **Alert Suppressions** - Time-based muting for maintenance windows
- 📊 **Alert History** - Persistent storage with full lifecycle tracking
- 📏 **Configurable Rules** - UI-based threshold management
- 🔔 **Teams Priority** - Microsoft Teams notifications sent first
- 📈 **Alert Analytics** - Trends, resolution times, acknowledgment rates

#### Phase 4: ML Analytics & Geolocation
- 🤖 **Anomaly Detection** - Isolation Forest ML model for suspicious IPs
- 🌍 **IP Geolocation** - MaxMind GeoLite2 offline mapping
- 🗺️ **Country Heatmaps** - Geographic visualization of email sources
- 📊 **Model Management** - Training, versioning, deployment
- 🔄 **Automated Training** - Weekly ML model updates (Sunday 2 AM)
- 🎯 **Daily Detection** - Automatic anomaly scanning (3 AM)
- 💾 **90-Day Caching** - Efficient geolocation data caching
- 📈 **Prediction History** - ML prediction tracking and analytics

### Performance & Caching
- ⚡ **Redis Caching** - 90%+ hit rate, sub-200ms response times
- 🔧 **Query Optimization** - N+1 query elimination, indexed lookups
- 📈 **Auto-Invalidation** - Cache clearing on new data
- 🔄 **Connection Pooling** - Optimized database and cache connections

### Visualizations
- 📊 **8 Interactive Charts**:
  - DMARC results timeline (line chart)
  - Results by domain (bar chart)
  - Top source IPs (bar chart)
  - Disposition breakdown (pie chart)
  - SPF/DKIM alignment breakdown (stacked bar)
  - Policy compliance (doughnut chart)
  - Failure rate trend with moving average (line chart)
  - Top sending organizations (horizontal bar)

### Advanced Filtering
- 🔍 **Source IP** - Exact match or CIDR ranges
- 🔐 **Authentication** - DKIM/SPF pass/fail
- 📋 **Disposition** - None/Quarantine/Reject
- 🏢 **Organization** - Sending organization filter
- 📅 **Date Range** - Custom or preset ranges
- 🌐 **Domain** - Multi-domain filtering

### Export Capabilities
- 📄 **CSV Exports** - Reports, records, sources
- 📑 **PDF Reports** - Professional summary with charts
- 🔒 **Rate Limiting** - 10/min CSV, 5/min PDF
- 🛡️ **Security** - CSV formula injection prevention

---

## 🛠️ Tech Stack

### Backend
- **Framework**: Python 3.11 + FastAPI
- **Task Queue**: Celery + Redis
- **ML/Analytics**: scikit-learn, NumPy, pandas
- **Geolocation**: MaxMind GeoLite2 + geoip2
- **Auth**: JWT (PyJWT), bcrypt
- **Database**: PostgreSQL 15 + SQLAlchemy 2.0
- **Cache**: Redis 7 (Alpine)
- **PDF**: ReportLab

### Frontend
- **Stack**: Vanilla HTML/CSS/JS + Chart.js v4.4.0
- **Charts**: Chart.js for visualizations
- **Web Server**: Nginx (reverse proxy)

### Infrastructure
- **Orchestration**: Docker Compose
- **Services**: Backend, Celery Worker, Celery Beat, PostgreSQL, Redis, Nginx, Flower
- **Monitoring**: Flower dashboard for Celery tasks

---

## 📋 Prerequisites

### Required
- Docker & Docker Compose
- MaxMind GeoLite2 database (free account)

### Optional
- Email account with IMAP access (for automated ingestion)
- Microsoft Teams/Slack webhooks (for alerts)

---

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone <repo-url>
cd dmarc
```

### 2. Download MaxMind Database
1. Sign up at: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
2. Download **GeoLite2-City.mmdb**
3. Place at: `backend/data/GeoLite2-City.mmdb`

```bash
mkdir -p backend/data
# Copy GeoLite2-City.mmdb to backend/data/
```

### 3. Configure Environment
```bash
cp .env.sample .env
# Edit .env with your settings
```

**Required Settings**:
```env
# JWT Secret (generate with: python -c "import secrets; print(secrets.token_urlsafe(64))")
JWT_SECRET_KEY=your-secret-key-here

# Celery + Redis
USE_CELERY=true
CELERY_BROKER_URL=redis://redis:6379/0

# Database
DATABASE_URL=postgresql://dmarc:dmarc@db:5432/dmarc

# Email (optional - for automated ingestion)
EMAIL_HOST=imap.gmail.com
EMAIL_PORT=993
EMAIL_USER=your-email@example.com
EMAIL_PASSWORD=your-app-password

# Alerts (optional)
TEAMS_WEBHOOK_URL=https://your-teams-webhook
```

### 4. Start Services
```bash
docker compose up -d --build
```

**Services**:
- `backend` - FastAPI application (port 8000)
- `celery-worker` - Background task processor
- `celery-beat` - Scheduled task scheduler
- `flower` - Celery monitoring UI (port 5555)
- `db` - PostgreSQL database
- `redis` - Cache & message broker
- `nginx` - Web server (port 80)

### 5. Run Database Migrations
```bash
docker compose exec backend alembic upgrade head
```

**Migrations Applied**:
- `001` - Ingested reports table
- `002` - DMARC reports & records tables
- `003` - Performance indexes
- `004` - Celery task tracking
- `005` - User authentication
- `006` - Enhanced alerting
- `007` - ML analytics & geolocation

### 6. Create Admin User
```bash
docker compose exec backend python scripts/create_admin_user.py
```

Follow the prompts to create your first admin user.

### 7. Access the Platform
- **Dashboard**: http://localhost
- **API Docs**: http://localhost:8000/docs
- **Flower (Tasks)**: http://localhost:5555
- **Health Check**: http://localhost/health

### 8. Login
Use the admin credentials you created to login via the dashboard or API.

---

## 🔐 Authentication

The platform uses JWT-based authentication. Access tokens expire after 15 minutes, and refresh tokens last 7 days.

### Login (Get JWT Token)
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "your-password"
  }'
```

**Response**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Use the Bearer Token in API Calls
Include the access token in the `Authorization` header for all protected endpoints:
```bash
curl -H "Authorization: Bearer <access_token>" http://localhost:8000/api/reports

# Example: Get report summary
curl -H "Authorization: Bearer <access_token>" http://localhost:8000/api/rollup/summary

# Example: Upload a report
curl -X POST http://localhost:8000/api/upload \
  -H "Authorization: Bearer <access_token>" \
  -F "files=@report.xml.gz"
```

### Refresh an Expired Token
When your access token expires (after 15 minutes), use the refresh token to obtain a new one without re-entering credentials:
```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<refresh_token>"
  }'
```

**Response** (new access token):
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### API Key Authentication
For automated scripts and integrations, API keys provide long-lived authentication without token refresh.

**Generate an API key:**
```bash
curl -X POST http://localhost:8000/users/api-keys \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-script"}'
```

**Use the API key:**
```bash
curl -H "X-API-Key: <api_key>" http://localhost:8000/api/reports
```

### Logout
Invalidate your tokens:
```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer <access_token>"
```

---

## 📡 API Endpoints

### Authentication (`/auth`)
- `POST /auth/login` - Login with email/password
- `POST /auth/refresh` - Refresh access token
- `POST /auth/logout` - Logout (invalidate tokens)

### Users (`/users`)
- `GET /users/me` - Get current user profile
- `GET /users` - List all users (admin)
- `POST /users` - Create user (admin)
- `PATCH /users/{id}` - Update user (admin)
- `DELETE /users/{id}` - Delete user (admin)
- `POST /users/api-keys` - Generate API key

### Core DMARC (`/api`)
- `GET /api/domains` - List domains
- `GET /api/reports` - List reports (paginated)
- `GET /api/reports/{id}` - Get report details
- `POST /api/upload` - Bulk file upload

### Analytics & Rollup (`/api/rollup`)
- `GET /api/rollup/summary` - Aggregate statistics
- `GET /api/rollup/sources` - Top source IPs
- `GET /api/rollup/alignment` - DKIM/SPF alignment
- `GET /api/rollup/timeline` - Time-series data
- `GET /api/rollup/failure-trend` - Failure rate trends

### Exports (`/api/export`)
- `GET /api/export/reports/csv` - Export reports CSV
- `GET /api/export/records/csv` - Export records CSV
- `GET /api/export/sources/csv` - Export sources CSV
- `GET /api/export/report/pdf` - Generate PDF summary

### Alerts (`/alerts`)
- `GET /alerts/history` - Alert history
- `GET /alerts/rules` - Alert rules
- `POST /alerts/rules` - Create rule (admin)
- `PATCH /alerts/{id}/acknowledge` - Acknowledge alert
- `PATCH /alerts/{id}/resolve` - Resolve alert
- `POST /alerts/suppressions` - Create suppression

### ML Analytics (`/analytics`)
- `GET /analytics/geolocation/map` - Country heatmap
- `GET /analytics/geolocation/lookup/{ip}` - IP geolocation
- `GET /analytics/ml/models` - List ML models
- `POST /analytics/ml/train` - Train model (admin)
- `POST /analytics/ml/deploy` - Deploy model (admin)
- `POST /analytics/anomalies/detect` - Detect anomalies
- `GET /analytics/anomalies/recent` - Recent predictions

### Tasks (`/tasks`)
- `POST /tasks/trigger/email-ingestion` - Trigger email fetch
- `POST /tasks/trigger/process-reports` - Process pending reports
- `GET /tasks/status/{task_id}` - Get task status

---

## 🎯 Role-Based Access

| Role | Permissions |
|------|-------------|
| **Admin** | Full access: users, models, rules, all data |
| **Analyst** | Read/write: reports, alerts, analytics |
| **Viewer** | Read-only: dashboards, reports, analytics |

---

## 📊 Monitoring

### Flower Dashboard (Celery Tasks)
Access at http://localhost:5555

**Monitors**:
- Active tasks
- Task history
- Worker status
- Task schedules (Beat)

### Scheduled Tasks
```bash
# View all schedules
docker compose exec celery-beat celery -A app.celery_app inspect scheduled

# Force run a task
docker compose exec celery-worker celery -A app.celery_app call \
  app.tasks.ml_tasks.train_anomaly_model_task
```

---

## 🧪 Testing

```bash
# Run all tests with coverage
docker compose exec backend pytest -v --cov=app

# Run specific test suite
docker compose exec backend pytest tests/unit/ -v
docker compose exec backend pytest tests/integration/ -v

# Generate HTML coverage report
docker compose exec backend pytest --cov=app --cov-report=html
```

**Coverage**: 70%+ enforced in CI/CD

---

## 📚 Documentation

- **[FEATURES.md](FEATURES.md)** - Complete feature list
- **[PHASE1_DEPLOYMENT.md](PHASE1_DEPLOYMENT.md)** - Celery setup
- **[PHASE2_DEPLOYMENT.md](PHASE2_DEPLOYMENT.md)** - Authentication setup
- **[PHASE3_DEPLOYMENT.md](PHASE3_DEPLOYMENT.md)** - Enhanced alerting setup
- **[PHASE4_DEPLOYMENT.md](PHASE4_DEPLOYMENT.md)** - ML analytics setup
- **[DEPLOYMENT.md](backend/DEPLOYMENT.md)** - Production deployment
- **[TESTING.md](backend/TESTING.md)** - Testing documentation
- **[API Docs](http://localhost:8000/docs)** - Interactive Swagger UI

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│   Nginx     │────▶│   Backend    │────▶│ PostgreSQL │
│   (Port 80) │     │  (FastAPI)   │     │    (DB)    │
└─────────────┘     └──────┬───────┘     └────────────┘
                           │
                           ▼
                    ┌─────────────┐     ┌──────────────┐
                    │    Redis    │◀───▶│Celery Worker │
                    │   (Broker)  │     │   + Beat     │
                    └─────────────┘     └──────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Flower    │
                    │  (Monitor)  │
                    └─────────────┘
```

---

## 🔧 Development

```bash
# View logs
docker compose logs -f backend
docker compose logs -f celery-worker

# Rebuild after code changes
docker compose up --build -d backend

# Create new migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Reset database (WARNING: deletes all data)
docker compose down -v
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/create_admin_user.py
```

---

## 🚢 Production Deployment

See **[backend/DEPLOYMENT.md](backend/DEPLOYMENT.md)** for:
- SSL/TLS with Let's Encrypt
- Database backups
- Security hardening
- Performance tuning
- Monitoring setup

---

## 📈 System Requirements

**Minimum**:
- CPU: 2 cores
- RAM: 4GB
- Storage: 10GB

**Recommended**:
- CPU: 4+ cores
- RAM: 8GB
- Storage: 50GB+ (depends on volume)

---

## 📄 License

MIT

---

**Version**: 2.0.0 (Enterprise Edition)
**Last Updated**: January 2026
**Status**: ✅ Production Ready
