# ADR 003: Celery with APScheduler Fallback

**Status:** Accepted

**Date:** 2026-01-10

**Context:**
The DMARC Dashboard needs to run background tasks for email ingestion, report processing, alerting, and ML model training. We needed to choose a distributed task processing system.

**Options Considered:**

1. **Celery + Redis** - Distributed task queue
2. **APScheduler** - In-process task scheduler
3. **RQ (Redis Queue)** - Lightweight Redis-based queue
4. **Celery with APScheduler Fallback** - Hybrid approach

---

## Decision

We chose **Celery + Redis as primary, with APScheduler as fallback** for development and small deployments.

---

## Rationale

### 1. Production vs Development Needs

**Production Requirements:**
- Distributed task processing across multiple workers
- Horizontal scaling (add more worker containers)
- Task retry with exponential backoff
- Priority queues for critical tasks
- Monitoring via Flower dashboard

**Development Requirements:**
- Simple setup (single command)
- No external dependencies (Redis optional)
- Fast iteration (no container restarts)
- Works on developer laptops

**Our Solution:**
```python
# backend/app/config.py
use_celery: bool = False  # Set to True for production
```

**If `use_celery=False`:** APScheduler runs tasks in-process
**If `use_celery=True`:** Celery distributes tasks to workers via Redis

### 2. Celery: For Production Scale

**Why Celery?**

**Proven at Scale:**
- Used by Instagram, Reddit, Mozilla
- Handles millions of tasks per day
- Battle-tested for 10+ years

**Features Needed:**
- **Distributed execution:** Multiple worker containers
- **Task routing:** Different queues for high/low priority
- **Retries:** Automatic retry with exponential backoff
- **Result backend:** Store task results in PostgreSQL
- **Monitoring:** Flower web UI for live task inspection

**Example Task Definition:**
```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def ingest_email_reports(self):
    try:
        service = EmailIngestionService()
        service.ingest_reports()
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

**Deployment:**
```yaml
# docker-compose.yml
celery-worker:
  command: celery -A celery_worker worker --concurrency=4
  deploy:
    replicas: 3  # Scale to 3 workers

celery-beat:
  command: celery -A celery_worker beat --loglevel=info
```

### 3. APScheduler: For Development Simplicity

**Why APScheduler?**

**Zero Setup:**
- No Redis required
- No separate worker containers
- Runs inside FastAPI process

**Development Workflow:**
```bash
# Start development server
uvicorn app.main:app --reload

# Tasks automatically start in background threads
# No docker compose, no Redis, no Celery
```

**Example Task Definition:**
```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=ingest_email_reports,
    trigger='interval',
    minutes=15,
    id='email_ingestion'
)
scheduler.start()
```

**When to Use:**
- Local development
- Small deployments (<100 reports/day)
- Single-server setups
- Docker-free environments

### 4. Unified Task Interface

**Abstraction Layer:**

Both Celery and APScheduler use the same task functions:

```python
# backend/app/tasks/email_ingestion.py

def ingest_email_reports():
    """
    Ingest DMARC reports from email.

    Called by Celery OR APScheduler depending on config.
    """
    service = EmailIngestionService()
    return service.ingest_reports()

# Register with Celery
celery_app.task(name='tasks.ingest_email_reports')(ingest_email_reports)

# Register with APScheduler
if not settings.use_celery:
    scheduler.add_job(ingest_email_reports, trigger='interval', minutes=15)
```

**Benefits:**
- Task logic is framework-agnostic
- Easy to switch between Celery and APScheduler
- Test tasks without Celery infrastructure

### 5. Graceful Degradation

**Feature Matrix:**

| Feature | Celery | APScheduler |
|---------|--------|-------------|
| Distributed execution | ✅ Yes | ❌ No |
| Scheduled tasks | ✅ Yes (beat) | ✅ Yes |
| Task retries | ✅ Yes (configurable) | ⚠️ Manual |
| Priority queues | ✅ Yes | ❌ No |
| Result backend | ✅ PostgreSQL | ⚠️ In-memory |
| Monitoring UI | ✅ Flower | ❌ No |
| Horizontal scaling | ✅ Yes | ❌ No |
| Zero dependencies | ❌ Needs Redis | ✅ Yes |

**Deployment Decision Tree:**

```
Is use_celery=True?
├─ Yes → Use Celery + Redis
│   ├─ Start celery-worker containers
│   ├─ Start celery-beat for scheduling
│   └─ Start Flower for monitoring
└─ No → Use APScheduler
    └─ Tasks run in FastAPI process
```

---

## Trade-offs and Limitations

### Celery Complexity

**Cons:**
- Additional infrastructure (Redis, worker containers)
- Configuration complexity (queues, routing, serializers)
- Debugging distributed tasks is harder
- Flower monitoring adds another service

**Example:** Setting up Celery requires:
- Redis running
- Worker containers
- Beat scheduler
- Proper task routing
- Result backend configuration

**Mitigation:** APScheduler fallback for simple deployments

### APScheduler Limitations

**Cons:**
- No distributed execution (single process)
- No task routing or priorities
- Limited retry logic
- No web UI for monitoring
- Tasks block FastAPI worker threads

**Example:** If email ingestion takes 10 minutes, one FastAPI worker thread is blocked for 10 minutes.

**Mitigation:**
- Use ThreadPoolExecutor for long-running tasks
- Set `max_instances=1` to prevent concurrent runs
- Monitor via logs (no Flower)

### Configuration Overhead

**Current Setup:**

Two separate implementations:
```python
# Celery tasks (backend/celery_worker.py)
@celery_app.task
def task_email_ingestion():
    ingest_email_reports()

# APScheduler tasks (backend/app/scheduler.py)
scheduler.add_job(ingest_email_reports, trigger='interval', minutes=15)
```

**Maintenance:** Keep both implementations in sync

---

## Implementation Details

### Celery Configuration

**Broker:** Redis (task queue)
```python
CELERY_BROKER_URL = "redis://:password@redis:6379/0"
```

**Result Backend:** PostgreSQL (task results)
```python
CELERY_RESULT_BACKEND = "db+postgresql://dmarc:password@db:5432/dmarc"
```

**Task Routing:**
```python
CELERY_TASK_ROUTES = {
    'tasks.ingest_email': {'queue': 'default'},
    'tasks.process_report': {'queue': 'default'},
    'tasks.generate_alerts': {'queue': 'alerts'},
    'tasks.train_ml_model': {'queue': 'ml'},
}
```

**Scheduled Tasks (Celery Beat):**
```python
CELERY_BEAT_SCHEDULE = {
    'ingest-email-every-15min': {
        'task': 'tasks.ingest_email_reports',
        'schedule': crontab(minute='*/15'),
    },
    'process-reports-every-5min': {
        'task': 'tasks.process_pending_reports',
        'schedule': crontab(minute='*/5'),
    },
    'generate-alerts-hourly': {
        'task': 'tasks.generate_alerts',
        'schedule': crontab(minute=0),
    },
    'train-ml-weekly': {
        'task': 'tasks.train_ml_models',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),
    },
}
```

### APScheduler Configuration

**Scheduler Type:** BackgroundScheduler
```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

executors = {
    'default': ThreadPoolExecutor(max_workers=4)
}

scheduler = BackgroundScheduler(executors=executors)
```

**Job Configuration:**
```python
scheduler.add_job(
    func=ingest_email_reports,
    trigger='interval',
    minutes=15,
    id='email_ingestion',
    max_instances=1,  # Prevent concurrent runs
    replace_existing=True
)

scheduler.add_job(
    func=generate_alerts,
    trigger='cron',
    hour=0,
    id='generate_alerts',
    max_instances=1
)
```

### Startup Logic

**Backend Initialization (backend/app/main.py):**
```python
from app.config import get_settings

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not settings.use_celery:
        # Start APScheduler for development
        from app.scheduler import scheduler
        scheduler.start()
        logger.info("APScheduler started (development mode)")
    else:
        logger.info("Celery mode enabled (tasks run in worker containers)")

    yield

    # Shutdown
    if not settings.use_celery:
        from app.scheduler import scheduler
        scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
```

---

## Task Inventory

**Current Background Tasks:**

| Task | Trigger | Queue | Description |
|------|---------|-------|-------------|
| `ingest_email_reports` | Every 15 min | default | Fetch reports from IMAP |
| `process_pending_reports` | Every 5 min | default | Parse XML reports |
| `generate_alerts` | Hourly | alerts | Check for anomalies |
| `train_ml_models` | Weekly (Sun 2am) | ml | Retrain ML models |
| `cleanup_old_reports` | Daily (3am) | default | Retention policy |
| `update_geolocation` | Daily (4am) | default | Refresh IP geolocation |
| `send_scheduled_reports` | Hourly | default | Email scheduled reports |

**Estimated Load:**
- Default queue: ~1000 tasks/day
- Alerts queue: ~24 tasks/day
- ML queue: ~1 task/week

**Resource Needs:**
- 1-3 Celery workers (depending on volume)
- 1 Celery beat scheduler
- 1 Redis instance

---

## Monitoring

### Celery (Production)

**Flower Dashboard:**
```
http://localhost:5555
```

**Features:**
- Live task monitoring
- Worker status
- Task history
- Task retry/revoke
- Broker status

**CLI Inspection:**
```bash
# Active tasks
docker compose exec celery-worker celery -A celery_worker inspect active

# Worker stats
docker compose exec celery-worker celery -A celery_worker inspect stats

# Registered tasks
docker compose exec celery-worker celery -A celery_worker inspect registered
```

### APScheduler (Development)

**Logging Only:**
```python
import logging
logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.DEBUG)
```

**Check Job Status:**
```python
from app.scheduler import scheduler

# List all jobs
jobs = scheduler.get_jobs()
for job in jobs:
    print(f"{job.id}: next run at {job.next_run_time}")
```

---

## When to Use Which

### Use Celery When:

1. **Production deployment**
2. **>100 reports per day**
3. **Multiple server instances**
4. **Need task monitoring (Flower)**
5. **Critical task reliability (retries, persistence)**

### Use APScheduler When:

1. **Local development**
2. **Small deployments (<100 reports/day)**
3. **Single server**
4. **Quick prototyping**
5. **Docker-free environment**

---

## When to Reconsider

This decision should be revisited if:

1. **APScheduler becomes unreliable:**
   - Tasks failing silently
   - Memory leaks in scheduler
   - FastAPI workers blocked by long tasks

2. **Celery overhead too high:**
   - Redis becomes a bottleneck
   - Too many moving parts
   - Flower monitoring not used

3. **New options emerge:**
   - Temporal.io (workflow orchestration)
   - Prefect (data pipeline framework)
   - Cloud-native task queues (AWS SQS, Google Cloud Tasks)

---

## Alternatives Rejected

### Why Not RQ (Redis Queue)?

**Pros:**
- Simpler than Celery
- Python-first design
- Good for small/medium workloads

**Cons:**
- Less mature than Celery
- No APScheduler fallback (always needs Redis)
- Smaller ecosystem

**Verdict:** Celery more proven for production

### Why Not Temporal/Prefect?

**Pros:**
- Modern workflow orchestration
- Better debugging
- Durable execution

**Cons:**
- Heavyweight (additional infrastructure)
- Overkill for simple periodic tasks
- Steeper learning curve

**Verdict:** Too complex for our use case

### Why Not Cloud Task Queues (SQS, Cloud Tasks)?

**Pros:**
- Managed service (no infrastructure)
- Auto-scaling
- High reliability

**Cons:**
- Vendor lock-in
- Requires cloud deployment
- Costs scale with usage

**Verdict:** Self-hosted preferred for flexibility

---

## Success Metrics

After 6 months of production use:

**Celery (Production):**
- ✅ Processing 500-2000 tasks/day
- ✅ Zero task loss due to worker crashes
- ✅ Flower monitoring used weekly
- ✅ Horizontal scaling tested (1-3 workers)

**APScheduler (Development):**
- ✅ Used by all developers
- ✅ Zero setup friction
- ✅ Fast iteration (no Redis needed)

---

## Conclusion

The hybrid Celery + APScheduler approach was the right choice because:

1. **Production scale:** Celery provides distributed task processing for high-volume deployments
2. **Development simplicity:** APScheduler removes Redis dependency for local dev
3. **Flexibility:** Easy to switch between modes via config flag
4. **Gradual adoption:** Start with APScheduler, migrate to Celery as needed

The decision prioritized **developer experience and operational flexibility** while maintaining a clear production-ready path.

---

## References

- [Celery Documentation](https://docs.celeryq.dev/)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- Celery setup: `backend/celery_worker.py`
- APScheduler setup: `backend/app/scheduler.py`
- Configuration: `backend/app/config.py`

---

**Authors:** DMARC Dashboard Team
**Last Updated:** 2026-02-06
