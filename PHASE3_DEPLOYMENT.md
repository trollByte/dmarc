# Phase 3: Enhanced Alerting Deployment Guide

## ✅ Phase 3 Complete - Persistent Alerts with Lifecycle Management

All Phase 3 components have been successfully implemented and are ready for deployment.

---

## 📦 What Was Built

### Core Features
- ✅ **Alert Persistence** - All alerts stored in database with full history
- ✅ **Alert Lifecycle** - Track alerts: created → acknowledged → resolved
- ✅ **Alert Deduplication** - SHA256 fingerprinting prevents alert spam
- ✅ **Cooldown Periods** - Configurable per alert type (default 1-24 hours)
- ✅ **Microsoft Teams Priority** - Teams notifications sent first

### Alert Management
- ✅ **Configurable Rules** - UI-based threshold configuration (no env vars)
- ✅ **Alert Suppressions** - Time-based muting (maintenance windows)
- ✅ **Bulk Operations** - Acknowledge/resolve multiple alerts at once
- ✅ **Alert Statistics** - Trends, resolution times, breakdown by severity/type

### Database Schema
- ✅ `alert_history` - Persistent alert records with lifecycle
- ✅ `alert_rules` - Configurable alert thresholds
- ✅ `alert_suppressions` - Time-based suppression rules

### API Endpoints

**Alert History & Lifecycle:**
- ✅ `GET /alerts/active` - Get active alerts
- ✅ `GET /alerts/history` - Get historical alerts
- ✅ `GET /alerts/stats` - Alert statistics
- ✅ `POST /alerts/{id}/acknowledge` - Acknowledge alert
- ✅ `POST /alerts/{id}/resolve` - Resolve alert
- ✅ `POST /alerts/bulk/acknowledge` - Bulk acknowledge
- ✅ `POST /alerts/bulk/resolve` - Bulk resolve

**Alert Rules (Admin Only):**
- ✅ `GET /alerts/rules` - List alert rules
- ✅ `POST /alerts/rules` - Create alert rule
- ✅ `PATCH /alerts/rules/{id}` - Update alert rule
- ✅ `DELETE /alerts/rules/{id}` - Delete alert rule

**Alert Suppressions (Analyst/Admin):**
- ✅ `GET /alerts/suppressions` - List suppressions
- ✅ `POST /alerts/suppressions` - Create suppression
- ✅ `PATCH /alerts/suppressions/{id}` - Update suppression
- ✅ `DELETE /alerts/suppressions/{id}` - Delete suppression

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
INFO  [alembic.runtime.migration] Running upgrade 005 -> 006, add enhanced alerting
```

### 3. Restart Backend Service

```bash
docker compose restart backend
```

### 4. Verify Migration

```bash
docker compose exec backend alembic current
```

Should show: `006 (head)`

---

## 🔍 Testing & Verification

### Test 1: Create Alert Rule

```bash
curl -X POST "http://localhost:8000/alerts/rules" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Failure Rate Warning",
    "description": "Warn when DMARC failure rate exceeds 10%",
    "alert_type": "failure_rate",
    "is_enabled": true,
    "severity": "warning",
    "conditions": {
      "failure_rate": {
        "warning": 10.0,
        "critical": 25.0
      }
    },
    "domain_pattern": null,
    "cooldown_minutes": 60,
    "notify_teams": true,
    "notify_email": true,
    "notify_slack": false,
    "notify_webhook": false
  }'
```

**Expected response:**

```json
{
  "id": "uuid",
  "name": "High Failure Rate Warning",
  "alert_type": "failure_rate",
  "is_enabled": true,
  "severity": "warning",
  "conditions": {"failure_rate": {"warning": 10.0, "critical": 25.0}},
  "cooldown_minutes": 60,
  "notify_teams": true,
  "notify_email": true,
  "created_at": "2026-01-09T15:00:00"
}
```

### Test 2: List Alert Rules

```bash
curl "http://localhost:8000/alerts/rules" \
  -H "Authorization: Bearer <token>"
```

### Test 3: Get Active Alerts

```bash
curl "http://localhost:8000/alerts/active?severity=critical&limit=50" \
  -H "Authorization: Bearer <token>"
```

### Test 4: Acknowledge Alert

```bash
curl -X POST "http://localhost:8000/alerts/{alert_id}/acknowledge" \
  -H "Authorization: Bearer <analyst_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "Investigating DMARC policy issue"
  }'
```

**Expected response:**

```json
{
  "id": "uuid",
  "alert_type": "failure_rate",
  "severity": "critical",
  "title": "CRITICAL: High failure rate for example.com",
  "message": "DMARC failure rate is 30.5% (threshold: 25%)",
  "status": "acknowledged",
  "acknowledged_at": "2026-01-09T15:10:00",
  "acknowledged_by": "user_uuid",
  "acknowledgement_note": "Investigating DMARC policy issue",
  ...
}
```

### Test 5: Resolve Alert

```bash
curl -X POST "http://localhost:8000/alerts/{alert_id}/resolve" \
  -H "Authorization: Bearer <analyst_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "DKIM record updated - issue resolved"
  }'
```

### Test 6: Create Suppression (Maintenance Window)

```bash
curl -X POST "http://localhost:8000/alerts/suppressions" \
  -H "Authorization: Bearer <analyst_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Weekend Maintenance",
    "description": "Suppress all alerts during weekend maintenance",
    "is_active": true,
    "alert_type": null,
    "severity": null,
    "domain": null,
    "starts_at": "2026-01-11T02:00:00Z",
    "ends_at": "2026-01-11T06:00:00Z",
    "recurrence": {
      "type": "weekly",
      "days": ["saturday", "sunday"],
      "hours": [2, 3, 4, 5]
    }
  }'
```

### Test 7: Get Alert Statistics

```bash
curl "http://localhost:8000/alerts/stats?days=30" \
  -H "Authorization: Bearer <token>"
```

**Expected response:**

```json
{
  "period_days": 30,
  "total_alerts": 45,
  "by_severity": {
    "critical": 8,
    "warning": 22,
    "info": 15
  },
  "by_type": {
    "failure_rate": 25,
    "volume_spike": 12,
    "volume_drop": 8
  },
  "by_status": {
    "created": 5,
    "acknowledged": 12,
    "resolved": 28
  },
  "by_domain": {
    "example.com": 15,
    "test.com": 12,
    "demo.com": 8
  },
  "avg_resolution_time_hours": 4.5
}
```

### Test 8: Bulk Acknowledge Alerts

```bash
curl -X POST "http://localhost:8000/alerts/bulk/acknowledge" \
  -H "Authorization: Bearer <analyst_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_ids": ["uuid1", "uuid2", "uuid3"],
    "note": "Batch acknowledgement - investigating"
  }'
```

**Expected response:**

```json
{
  "success_count": 3,
  "failed_count": 0,
  "errors": []
}
```

---

## 🔧 Configuration

### Default Alert Rules (Create via API)

**Failure Rate Warnings:**

```json
{
  "name": "DMARC Failure Rate - Warning",
  "alert_type": "failure_rate",
  "severity": "warning",
  "conditions": {"failure_rate": {"warning": 10.0}},
  "cooldown_minutes": 60,
  "notify_teams": true
}
```

**Failure Rate Critical:**

```json
{
  "name": "DMARC Failure Rate - Critical",
  "alert_type": "failure_rate",
  "severity": "critical",
  "conditions": {"failure_rate": {"critical": 25.0}},
  "cooldown_minutes": 30,
  "notify_teams": true
}
```

**Volume Spike:**

```json
{
  "name": "Email Volume Spike",
  "alert_type": "volume_spike",
  "severity": "warning",
  "conditions": {"volume_spike": {"warning": 50.0}},
  "cooldown_minutes": 120,
  "notify_teams": true
}
```

### Cooldown Periods

Default cooldowns by alert type:

| Alert Type | Default Cooldown |
|-----------|-----------------|
| failure_rate | 60 minutes |
| volume_spike | 120 minutes |
| volume_drop | 120 minutes |
| new_source | 1440 minutes (24h) |
| policy_violation | 60 minutes |
| anomaly | 180 minutes |

Override via alert rules: `cooldown_minutes` field.

---

## 🔐 Alert Lifecycle

### Status Flow

```
created → acknowledged → resolved
   ↓
suppressed (optional)
```

**created**: Alert generated by system
**acknowledged**: Someone is looking into it (analyst/admin)
**resolved**: Issue fixed (analyst/admin)
**suppressed**: Muted by suppression rule

### Who Can Do What

| Action | Admin | Analyst | Viewer |
|--------|-------|---------|--------|
| View alerts | ✅ | ✅ | ✅ |
| Acknowledge | ✅ | ✅ | ❌ |
| Resolve | ✅ | ✅ | ❌ |
| Create rules | ✅ | ❌ | ❌ |
| Create suppressions | ✅ | ✅ | ❌ |

---

## 🔔 Microsoft Teams Priority

Teams notifications are sent **FIRST** before other channels:

```python
# Notification order:
1. Microsoft Teams (if enabled)
2. Email (if enabled)
3. Slack (if enabled)
4. Generic webhook (if enabled)
```

### Teams Webhook Setup

1. In Microsoft Teams, create Incoming Webhook
2. Add to `.env`:

```bash
TEAMS_WEBHOOK_URL=https://your-org.webhook.office.com/webhookb2/...
```

3. Restart backend:

```bash
docker compose restart backend
```

---

## 📊 Alert Deduplication

### How It Works

1. **Fingerprint Generation** (SHA256):
   ```
   SHA256(alert_type + domain + threshold)
   ```

2. **Cooldown Check**:
   - Alert with same fingerprint within cooldown? → Deduplicated
   - No recent alert? → Create new alert

3. **Example**:
   - Alert 1: `failure_rate` for `example.com` at 15:00 (60min cooldown)
   - Alert 2: `failure_rate` for `example.com` at 15:30 → **Deduplicated**
   - Alert 3: `failure_rate` for `example.com` at 16:05 → **New alert**

### Benefits

- Prevents alert fatigue
- Reduces noise in Teams/email
- Tracks unique issues separately

---

## 🛠️ Alert Suppressions

### Use Cases

**1. Maintenance Windows**
```json
{
  "name": "Weekly Maintenance",
  "starts_at": "2026-01-11T02:00:00Z",
  "ends_at": "2026-01-11T06:00:00Z",
  "recurrence": {
    "type": "weekly",
    "days": ["saturday"],
    "hours": [2, 3, 4, 5]
  }
}
```

**2. Domain-Specific**
```json
{
  "name": "Suppress test.com alerts",
  "domain": "test.com",
  "alert_type": null,
  "starts_at": null,
  "ends_at": null
}
```

**3. Severity-Specific**
```json
{
  "name": "Suppress info alerts",
  "severity": "info",
  "starts_at": null,
  "ends_at": null
}
```

---

## 🐛 Troubleshooting

### Issue: Alerts not being created

**Check:**
1. Alert rules exist and are enabled: `GET /alerts/rules`
2. No active suppressions: `GET /alerts/suppressions?active_only=true`
3. Cooldown period hasn't expired yet

```bash
# Check recent alerts
curl "http://localhost:8000/alerts/history?limit=10" \
  -H "Authorization: Bearer <token>"
```

### Issue: Teams notifications not sending

**Solution:** Verify Teams webhook URL

```bash
# Test Teams webhook manually
curl -X POST "$TEAMS_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "@type": "MessageCard",
    "summary": "Test alert",
    "sections": [{
      "activityTitle": "Test Alert",
      "activitySubtitle": "If you see this, Teams is configured correctly"
    }]
  }'
```

### Issue: Too many duplicate alerts

**Solution:** Increase cooldown period

```bash
# Update alert rule cooldown
curl -X PATCH "http://localhost:8000/alerts/rules/{rule_id}" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "cooldown_minutes": 180
  }'
```

---

## ✅ Phase 3 Checklist

- [ ] Database migration 006 applied
- [ ] Backend service restarted
- [ ] Alert rules created (at least failure_rate)
- [ ] Teams webhook configured (optional)
- [ ] Test alert rule creation (Test 1)
- [ ] Test active alerts endpoint (Test 3)
- [ ] Test alert acknowledgement (Test 4)
- [ ] Test alert resolution (Test 5)
- [ ] Test alert suppressions (Test 6)
- [ ] Test alert statistics (Test 7)
- [ ] Verify Teams notifications (if configured)

---

## 📈 Next Steps

**Phase 3 is now complete!** You have a fully functional persistent alerting system with lifecycle management.

**Recommended next actions:**

1. ✅ Create default alert rules for your domains
2. ✅ Set up Microsoft Teams webhook
3. ✅ Configure maintenance window suppressions
4. ✅ Test alert workflow (create → acknowledge → resolve)
5. 🔜 **Phase 4**: ML Analytics (anomaly detection, geolocation, forecasting)

---

## 🆘 Need Help?

- **API Docs**: http://localhost:8000/docs
- **Alert Endpoints**: http://localhost:8000/docs#/Alert%20Management
- **Health Check**: `curl http://localhost:8000/health`

**Phase 3 Status**: ✅ **100% COMPLETE** (4/4 tasks)
