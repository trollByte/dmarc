# Service Level Objectives (SLOs) and Indicators (SLIs)

## Overview

This document defines the Service Level Indicators (SLIs) and Service Level Objectives (SLOs) for the DMARC Dashboard. These metrics ensure the service meets reliability, performance, and availability targets.

## Definitions

- **SLI (Service Level Indicator)**: A quantifiable measure of service behavior
- **SLO (Service Level Objective)**: Target value or range for an SLI
- **SLA (Service Level Agreement)**: A contractual obligation based on SLOs (not covered here)
- **Error Budget**: The allowed amount of unreliability (100% - SLO%)

## Service Level Objectives

### 1. Availability SLO

**Target: 99.5% uptime (monthly)**

#### SLI Definition

```
availability = (successful_requests / total_requests) * 100
```

Where:
- `successful_requests`: HTTP responses with status codes 200-299, 400-499 (excluding 429)
- `total_requests`: All HTTP requests to the API

#### Measurement

```promql
# Availability over 30 days
(
  sum(rate(http_requests_total{job="dmarc-backend",status!~"5..",status!="429"}[30d]))
  /
  sum(rate(http_requests_total{job="dmarc-backend"}[30d]))
) * 100
```

#### Target Breakdown

| Period | Target Uptime | Allowed Downtime |
|--------|---------------|------------------|
| Monthly | 99.5% | 3.6 hours |
| Weekly | 99.5% | 50.4 minutes |
| Daily | 99.5% | 7.2 minutes |

#### Error Budget

- **Monthly error budget**: 0.5% (3.6 hours)
- When error budget is exhausted: Halt all non-critical feature deployments
- Error budget resets: Monthly (1st of each month)

---

### 2. Latency SLO

**Target: 95% of requests complete in < 500ms**

#### SLI Definition

```
latency_p95 = 95th percentile of request duration
```

#### Measurement

```promql
# P95 latency over 5 minutes
histogram_quantile(0.95,
  rate(http_request_duration_seconds_bucket{job="dmarc-backend"}[5m])
) * 1000
```

#### Target Breakdown

| Percentile | Target | Description |
|------------|--------|-------------|
| P50 | < 200ms | Median response time |
| P95 | < 500ms | 95th percentile (SLO target) |
| P99 | < 1000ms | 99th percentile |
| P99.9 | < 2000ms | Tail latency |

#### Per-Endpoint Targets

| Endpoint Type | P95 Target | P99 Target |
|---------------|------------|------------|
| Health checks | < 50ms | < 100ms |
| Read operations (GET) | < 300ms | < 800ms |
| Write operations (POST/PUT) | < 500ms | < 1000ms |
| Complex queries | < 1000ms | < 2000ms |
| Report processing | < 5000ms | < 10000ms |

---

### 3. Error Rate SLO

**Target: < 1% error rate (5xx responses)**

#### SLI Definition

```
error_rate = (5xx_responses / total_requests) * 100
```

#### Measurement

```promql
# Error rate over 5 minutes
(
  sum(rate(http_requests_total{job="dmarc-backend",status=~"5.."}[5m]))
  /
  sum(rate(http_requests_total{job="dmarc-backend"}[5m]))
) * 100
```

#### Target Breakdown

| Error Type | Target | Alert Threshold |
|------------|--------|-----------------|
| 5xx errors | < 1% | > 0.5% |
| 4xx errors | < 10% | > 15% |
| Database errors | < 0.1% | > 0.05% |
| Cache errors | < 0.5% | > 0.25% |

---

### 4. Data Freshness SLO

**Target: 95% of DMARC reports processed within 1 hour**

#### SLI Definition

```
data_freshness = time_from_ingestion_to_processed
```

#### Measurement

```promql
# Average processing time
avg(
  time() - ingested_reports_ingestion_timestamp{status="processed"}
)
```

#### Target Breakdown

| Percentile | Target | Description |
|------------|--------|-------------|
| P50 | < 15 minutes | Median processing time |
| P95 | < 1 hour | 95th percentile (SLO target) |
| P99 | < 2 hours | 99th percentile |

---

### 5. Database Performance SLO

**Target: 95% of queries complete in < 100ms**

#### SLI Definition

```
db_query_latency_p95 = 95th percentile of database query duration
```

#### Measurement

```promql
# Database query P95 latency
histogram_quantile(0.95,
  rate(pg_stat_statements_mean_exec_time_bucket[5m])
) * 1000
```

#### Target Breakdown

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Connection pool utilization | < 70% | > 80% |
| Active connections | < 50 | > 70 |
| Query P95 latency | < 100ms | > 150ms |
| Long-running queries | < 5 | > 10 |

---

### 6. Celery Task Success Rate SLO

**Target: 99% of background tasks complete successfully**

#### SLI Definition

```
task_success_rate = (successful_tasks / total_tasks) * 100
```

#### Measurement

```promql
# Task success rate over 1 hour
(
  sum(rate(celery_task_succeeded_total[1h]))
  /
  sum(rate(celery_task_total[1h]))
) * 100
```

#### Target Breakdown

| Task Type | Success Rate Target | Max Retry |
|-----------|---------------------|-----------|
| Email ingestion | 99% | 3 |
| Report parsing | 99.5% | 2 |
| Alert generation | 99.9% | 1 |
| ML training | 95% | 1 |

---

## Monitoring and Alerting

### Critical Alerts (Page immediately)

1. **Availability < 99%** (over 5 minutes)
   ```promql
   (sum(rate(http_requests_total{status!~"5.."}[5m])) / sum(rate(http_requests_total[5m]))) < 0.99
   ```

2. **P95 Latency > 1000ms** (over 5 minutes)
   ```promql
   histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1.0
   ```

3. **Error Rate > 5%** (over 5 minutes)
   ```promql
   (sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))) > 0.05
   ```

### Warning Alerts (Notify during business hours)

1. **Availability < 99.5%** (over 15 minutes)
2. **P95 Latency > 500ms** (over 15 minutes)
3. **Error Rate > 1%** (over 15 minutes)
4. **Error budget burn rate > 10x** (fast burn)

### Informational Alerts

1. **P99 Latency > 2000ms**
2. **Database connections > 70%**
3. **Cache hit rate < 80%**
4. **Disk usage > 80%**

---

## Error Budget Policy

### Error Budget Calculation

```
error_budget_remaining = (1 - (actual_uptime / target_uptime)) * 100
```

### Burn Rate Thresholds

| Burn Rate | Window | Action |
|-----------|--------|--------|
| > 14.4x | 1 hour | Page on-call immediately |
| > 6x | 6 hours | Create incident, notify team |
| > 3x | 24 hours | Review in next planning meeting |
| > 1x | 72 hours | Monitor closely |

### Policy Actions

| Error Budget Remaining | Action |
|------------------------|--------|
| > 50% | Normal operations, deploy as planned |
| 25-50% | Increase caution, prioritize reliability |
| 10-25% | Freeze non-critical deployments, focus on stability |
| < 10% | Full deployment freeze, emergency reliability work only |

---

## Dashboard Links

- **SLO Dashboard**: http://grafana:3000/d/dmarc-slos
- **Availability**: http://grafana:3000/d/dmarc-availability
- **Latency**: http://grafana:3000/d/dmarc-latency
- **Error Budget**: http://grafana:3000/d/dmarc-error-budget

---

## Review Schedule

- **Weekly**: Review SLI metrics and trends
- **Monthly**: Assess SLO compliance and error budget
- **Quarterly**: Review and update SLO targets
- **Annually**: Comprehensive SLO framework review

---

## Incident Response

### SLO Breach Response

1. **Detect**: Alert fires when SLO threshold is breached
2. **Triage**: Determine severity and impact
3. **Mitigate**: Take immediate action to restore service
4. **Investigate**: Root cause analysis
5. **Document**: Post-incident review and action items
6. **Improve**: Update systems to prevent recurrence

### Post-Incident Actions

- Document incident in runbook
- Update error budget tracking
- Create action items for reliability improvements
- Conduct blameless post-mortem within 48 hours

---

## References

- [Google SRE Book - SLIs, SLOs, and SLAs](https://sre.google/sre-book/service-level-objectives/)
- [Implementing SLOs](https://sre.google/workbook/implementing-slos/)
- [Error Budget Policy](https://sre.google/workbook/error-budget-policy/)

---

## Appendix: Example Prometheus Queries

### Availability (30-day)

```promql
avg_over_time(
  (
    sum(rate(http_requests_total{status!~"5.."}[5m]))
    /
    sum(rate(http_requests_total[5m]))
  )[30d:5m]
) * 100
```

### Error Budget Remaining

```promql
(1 - (
  (
    sum(rate(http_requests_total{status!~"5.."}[30d]))
    /
    sum(rate(http_requests_total[30d]))
  )
  / 0.995
)) * 100
```

### Fast Burn Alert (1 hour window, 14.4x burn rate)

```promql
(
  1 - (
    sum(rate(http_requests_total{status!~"5.."}[1h]))
    /
    sum(rate(http_requests_total[1h]))
  )
) > (14.4 * 0.005)  # 14.4x the allowed error rate
```

### Slow Burn Alert (24 hour window, 3x burn rate)

```promql
(
  1 - (
    sum(rate(http_requests_total{status!~"5.."}[24h]))
    /
    sum(rate(http_requests_total[24h]))
  )
) > (3 * 0.005)  # 3x the allowed error rate
```

---

**Document Owner**: Operations Team
**Last Updated**: 2026-02-06
**Next Review**: 2026-05-06
