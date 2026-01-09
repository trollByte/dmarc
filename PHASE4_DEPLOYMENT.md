# PHASE 4 DEPLOYMENT GUIDE
## ML Analytics & Geolocation

**Status**: ✅ Ready for Deployment
**Date**: 2026-01-09
**Dependencies**: Phase 1 (Celery), Phase 2 (User Auth)

---

## Overview

Phase 4 adds advanced analytics capabilities to the DMARC Dashboard:

1. **IP Geolocation** - Offline IP-to-location mapping using MaxMind GeoLite2
2. **ML Anomaly Detection** - Isolation Forest for detecting suspicious IP behavior
3. **Geographic Heatmaps** - Country-based email source visualization
4. **Automated ML Training** - Weekly model training with auto-deployment

### New Tables
- `geolocation_cache` - 90-day IP geolocation cache
- `ml_models` - Trained ML models with serialized data
- `ml_predictions` - ML prediction results
- `analytics_cache` - Cached analytics data (heatmaps, etc.)

### New API Endpoints
- **Geolocation**: `/analytics/geolocation/*` (map, lookup, stats)
- **ML Models**: `/analytics/ml/*` (train, deploy, list)
- **Anomalies**: `/analytics/anomalies/*` (detect, recent)

---

## Prerequisites

### 1. MaxMind GeoLite2 Database

**Required**: MaxMind GeoLite2 City database (free)

#### Download Steps:
1. Sign up for free MaxMind account: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
2. Download **GeoLite2-City.mmdb** (binary format)
3. Save to: `backend/data/GeoLite2-City.mmdb`

```bash
# Create data directory
mkdir -p backend/data

# Download database (requires MaxMind account)
# Place GeoLite2-City.mmdb in backend/data/
```

### 2. Python ML Dependencies

ML dependencies already added to `requirements.txt`:
```txt
# ML & Analytics
scikit-learn==1.4.0
numpy==1.26.3
pandas==2.1.4
geoip2==4.7.0
joblib==1.3.2
```

---

## Deployment Steps

### Step 1: Install Dependencies

```bash
cd backend
pip install -r requirements.txt
python -c "import sklearn, numpy, pandas, geoip2; print('ML dependencies OK')"
```

### Step 2: Download MaxMind Database

```bash
mkdir -p data
# Place GeoLite2-City.mmdb in backend/data/
ls -lh data/GeoLite2-City.mmdb
```

### Step 3: Run Database Migration

```bash
alembic upgrade head
psql $DATABASE_URL -c "\dt"
```

### Step 4: Rebuild and Restart Services

```bash
docker compose build backend celery-worker celery-beat
docker compose up -d backend celery-worker celery-beat
docker compose logs celery-beat | grep "ml_tasks"
```

### Step 5: Verify Geolocation Service

```bash
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}' \
  | jq -r '.access_token')

curl -X GET "http://localhost:8000/analytics/geolocation/lookup/8.8.8.8" \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Step 6: Train Initial ML Model (Admin Only)

```bash
curl -X POST "http://localhost:8000/analytics/ml/train" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model_type": "isolation_forest", "days": 90, "contamination": 0.05}' | jq
```

**Note**: Training requires at least **100 samples** (IP records).

---

## Celery Beat Schedules

| Task | Schedule | Description |
|------|----------|-------------|
| `train-anomaly-model-weekly` | Sunday 2 AM | Train new Isolation Forest model |
| `detect-anomalies-daily` | Daily 3 AM | Run anomaly detection |
| `purge-geolocation-cache-weekly` | Monday 1 AM | Clean expired cache entries |
| `generate-analytics-cache-daily` | Daily 4 AM | Pre-generate country heatmaps |

---

## API Endpoints

### Geolocation

**GET /analytics/geolocation/map**
```json
{
  "countries": {
    "US": {"count": 1500, "name": "United States"}
  },
  "max_count": 1500,
  "total_ips": 2000
}
```

**GET /analytics/geolocation/lookup/{ip}**
```json
{
  "ip_address": "8.8.8.8",
  "country_code": "US",
  "city_name": "Mountain View",
  "latitude": 37.3860,
  "longitude": -122.0838
}
```

### ML Models

**POST /analytics/ml/train** (Admin)
```json
{
  "model_type": "isolation_forest",
  "days": 90,
  "contamination": 0.05
}
```

**POST /analytics/ml/deploy** (Admin)
```json
{
  "model_id": "uuid"
}
```

**GET /analytics/ml/models**
Returns list of trained models.

### Anomaly Detection

**POST /analytics/anomalies/detect**
```json
{
  "days": 7,
  "threshold": -0.5
}
```

Returns anomalous IPs with scores and features.

---

## Security Considerations

### ML Model Serialization

Models use standard scikit-learn serialization (joblib/internal format):
- ✅ **SAFE**: Only self-trained models loaded
- ✅ Database-only storage with restricted access
- ✅ Admin-only model training endpoints
- ✅ Never loads external or user-uploaded models

This is the standard practice for scikit-learn model persistence and is secure when only self-trained models are used.

### API Access Control

**Admin-only endpoints**:
- `POST /analytics/ml/train`
- `POST /analytics/ml/deploy`

**Rate limiting** applies to all endpoints.

---

## Troubleshooting

### "MaxMind database not found"

1. Download GeoLite2-City.mmdb from MaxMind
2. Place in `backend/data/GeoLite2-City.mmdb`
3. Restart: `docker compose restart backend`

### "Insufficient training data"

Need at least 100 unique IP records. Wait for more data or reduce `days` parameter.

### "No deployed model available"

Train and deploy a model:
```bash
curl -X POST "http://localhost:8000/analytics/ml/train" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"days": 90, "contamination": 0.05}'
```

---

## Rollback

```bash
alembic downgrade 006
docker compose build backend
docker compose up -d
```

---

## Testing Checklist

- [ ] MaxMind database loaded
- [ ] Geolocation lookup works
- [ ] Country heatmap generates
- [ ] ML model training completes
- [ ] Anomaly detection returns results
- [ ] Celery Beat schedules tasks
- [ ] Admin endpoints require admin role

---

## Documentation

- **ML Analytics**: `backend/app/services/ml_analytics.py`
- **Geolocation**: `backend/app/services/geolocation.py`
- **API Routes**: `backend/app/api/analytics_routes.py`
- **Celery Tasks**: `backend/app/tasks/ml_tasks.py`

**MaxMind**: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
**Isolation Forest**: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html

---

**Status**: ✅ Production Ready
