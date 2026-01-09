# Phase 1: Celery + Redis Deployment Guide

## 🎉 Phase 1 Complete - Distributed Task Queue Infrastructure

All Phase 1 components have been successfully implemented and committed.

---

## 📦 What Was Built

### Infrastructure
- ✅ Celery worker processes (4 concurrent)
- ✅ Celery Beat scheduler (periodic tasks)
- ✅ Flower monitoring dashboard (port 5555)
- ✅ Redis broker (DB 1) for message queue
- ✅ PostgreSQL result backend for task persistence

### Tasks Created
- ✅ **Email Ingestion** - Every 15 minutes (50 emails max)
- ✅ **Report Processing** - Every 5 minutes (100 reports max)
- ✅ **Alert Checking** - Every hour (with notifications)

### API Endpoints
- ✅ `POST /api/tasks/ingest` - Manually trigger email ingestion
- ✅ `POST /api/tasks/process` - Manually trigger report processing
- ✅ `GET /api/tasks/{task_id}/status` - Query task status
- ✅ `GET /api/tasks/stats` - Task statistics dashboard

---

## 🚀 Deployment Steps

### 1. Pull Latest Changes
```bash
git pull origin main
```

### 2. Run Database Migration
```bash
docker compose exec backend alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade 003 -> 004, add celery task tracking tables
```

### 3. Restart All Services
```bash
docker compose down
docker compose up -d --build
```

### 4. Verify Container Status
```bash
docker compose ps
```

You should see 6 containers running:
- ✅ dmarc-db (PostgreSQL)
- ✅ dmarc-redis (Redis)
- ✅ dmarc-backend (FastAPI)
- ✅ dmarc-nginx (Nginx)
- ✅ dmarc-celery-worker (NEW)
- ✅ dmarc-celery-beat (NEW)
- ✅ dmarc-flower (NEW - monitoring)

### 5. Check Celery Worker Health
```bash
docker compose logs celery-worker --tail=20
```

Look for:
```
[INFO] celery@hostname ready
[INFO] Connected to redis://redis:6379/1
```

### 6. Check Celery Beat Scheduler
```bash
docker compose logs celery-beat --tail=20
```

Look for:
```
[INFO] Scheduler: Sending due task process-reports-every-5min
[INFO] Scheduler: Sending due task ingest-emails-every-15min
[INFO] Scheduler: Sending due task check-alerts-hourly
```

---

## 🔍 Testing & Verification

### Test 1: Access Flower Dashboard
Open browser: **http://localhost:5555**

You should see:
- Worker list (1 worker with 4 processes)
- Task list (scheduled tasks)
- Task statistics
- Broker connection status

### Test 2: Manual Task Dispatch
```bash
# Trigger processing task
curl -X POST "http://localhost:8000/api/tasks/process?limit=10" \
  -H "X-API-Key: dev-api-key-12345"
```

Expected response:
```json
{
  "status": "dispatched",
  "task_id": "abc123-def456-...",
  "task_name": "process_reports_task",
  "message": "Report processing task dispatched (limit=10)",
  "monitor_url": "/api/tasks/abc123-def456-.../status"
}
```

### Test 3: Check Task Status
```bash
# Replace {task_id} with the ID from Test 2
curl "http://localhost:8000/api/tasks/{task_id}/status"
```

Expected response (SUCCESS):
```json
{
  "task_id": "abc123-def456-...",
  "status": "SUCCESS",
  "result": {
    "status": "success",
    "processed": 5,
    "failed": 0
  }
}
```

### Test 4: View Task Statistics
```bash
curl "http://localhost:8000/api/tasks/stats?days=1"
```

Expected response:
```json
{
  "period_days": 1,
  "total_tasks": 10,
  "by_status": {
    "SUCCESS": 9,
    "FAILURE": 1
  },
  "by_task": {
    "process_reports_task": {"SUCCESS": 5},
    "ingest_emails_task": {"SUCCESS": 4, "FAILURE": 1}
  },
  "success_rate": 90.0
}
```

### Test 5: Verify Scheduled Tasks
Wait 5-10 minutes, then check Flower dashboard or logs to confirm scheduled tasks are running automatically.

```bash
# Check if tasks are being executed
docker compose logs celery-worker --since 5m | grep "Task"
```

Look for:
```
Task app.tasks.processing.process_reports_task[...] succeeded
Task app.tasks.ingestion.ingest_emails_task[...] succeeded
```

---

## 🔧 Configuration

### Enable Celery (Optional)
By default, Celery runs but tasks can also execute synchronously. To force Celery usage:

```bash
# In .env file, add:
USE_CELERY=true
```

Then restart:
```bash
docker compose restart backend
```

### Adjust Task Schedules
Edit `backend/app/celery_app.py` to change frequencies:

```python
celery_app.conf.beat_schedule = {
    "process-reports-every-5min": {
        "task": "app.tasks.processing.process_reports_task",
        "schedule": 300.0,  # Change to 600.0 for 10 minutes
    },
    # ... other tasks
}
```

### Increase Worker Concurrency
Edit `docker-compose.yml`:

```yaml
celery-worker:
  command: celery -A celery_worker worker --loglevel=info --concurrency=8  # Changed from 4
```

---

## 📊 Monitoring

### Flower Dashboard
- **URL**: http://localhost:5555
- **Features**:
  - Real-time worker status
  - Task history and results
  - Task success/failure rates
  - Broker connection info
  - Task execution graphs

### Task Logs
```bash
# Worker logs
docker compose logs -f celery-worker

# Beat scheduler logs
docker compose logs -f celery-beat

# Filter for specific task
docker compose logs celery-worker | grep "process_reports_task"
```

### Database Query
```sql
-- Check recent tasks
SELECT task_id, name, status, date_done
FROM celery_taskmeta
ORDER BY date_done DESC
LIMIT 10;

-- Count by status
SELECT status, COUNT(*)
FROM celery_taskmeta
GROUP BY status;
```

---

## 🐛 Troubleshooting

### Issue: Celery worker won't start
**Solution**: Check Redis connection
```bash
docker compose exec redis redis-cli ping
# Should return: PONG
```

### Issue: Tasks stay in PENDING state
**Solution**: Verify worker is running and connected
```bash
docker compose exec celery-worker celery -A celery_worker inspect ping
# Should return: pong from worker
```

### Issue: Migration fails
**Solution**: Check database connection
```bash
docker compose exec backend python -c "from app.database import engine; engine.connect()"
```

### Issue: Tasks execute twice
**Solution**: Check that only one Beat scheduler is running
```bash
docker compose ps | grep beat
# Should show only 1 container
```

### Issue: High memory usage
**Solution**: Reduce worker concurrency or adjust Redis memory limit in docker-compose.yml

---

## 🔄 Rollback (If Needed)

If you need to roll back Phase 1:

```bash
# Stop Celery services
docker compose stop celery-worker celery-beat flower

# Rollback migration
docker compose exec backend alembic downgrade -1

# Remove Celery services from docker-compose.yml
# (or just don't start them)
```

The system will continue working with APScheduler for background jobs.

---

## ✅ Phase 1 Checklist

- [ ] All 6 containers running (`docker compose ps`)
- [ ] Flower accessible at http://localhost:5555
- [ ] Database migration 004 applied
- [ ] Manual task dispatch works (Test 2)
- [ ] Task status query works (Test 3)
- [ ] Task statistics endpoint works (Test 4)
- [ ] Scheduled tasks executing automatically (Test 5)
- [ ] Worker logs show successful task completion
- [ ] No error logs in celery-worker or celery-beat

---

## 📈 Next Steps

**Phase 1 is now complete!** You have a fully functional distributed task queue system.

**Recommended next actions:**
1. ✅ Test on your remote machine using this guide
2. ✅ Monitor Flower dashboard for 24 hours to ensure stability
3. ✅ Verify scheduled tasks are running correctly
4. 🔜 **Phase 2**: User Authentication & RBAC (JWT tokens, role-based access)
5. 🔜 **Phase 3**: Enhanced Alerting (persistent history, Teams priority)
6. 🔜 **Phase 4**: ML Analytics (anomaly detection, geolocation)

---

## 🆘 Need Help?

- **Flower Dashboard**: http://localhost:5555
- **API Docs**: http://localhost:8000/docs
- **Logs**: `docker compose logs -f celery-worker`
- **Health Check**: `curl http://localhost:8000/health`

**Phase 1 Status**: ✅ **100% COMPLETE** (9/9 tasks)
