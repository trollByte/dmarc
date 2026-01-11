# DMARC Dashboard - Load Testing

This directory contains k6 load testing scripts for the DMARC Dashboard.

## Prerequisites

Install k6: https://k6.io/docs/getting-started/installation/

```bash
# macOS
brew install k6

# Windows (Chocolatey)
choco install k6

# Docker
docker pull grafana/k6
```

## Test Types

### Smoke Test
Quick validation that the system works under minimal load.
- Duration: 1 minute
- Users: 1
- Purpose: Verify basic functionality

```bash
k6 run --config k6-smoke.json k6-load-test.js
```

### Load Test
Sustained load to verify system handles expected traffic.
- Duration: ~16 minutes
- Users: Ramps from 0 → 20 → 50 → 0
- Purpose: Performance baseline

```bash
k6 run --config k6-load.json k6-load-test.js
```

### Stress Test
Find the breaking point of the system.
- Duration: ~27 minutes
- Users: Ramps from 0 → 200
- Purpose: Identify limits

```bash
k6 run --config k6-stress.json k6-load-test.js
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:8000` | Target URL |
| `API_KEY` | (empty) | API key for authentication |

### Running with Environment Variables

```bash
# Local development
k6 run -e BASE_URL=http://localhost:8000 k6-load-test.js

# Staging environment
k6 run -e BASE_URL=https://staging.dmarc.example.com -e API_KEY=your-key k6-load-test.js
```

### Running with Docker

```bash
docker run -i grafana/k6 run - < k6-load-test.js

# With environment variables
docker run -i -e BASE_URL=http://host.docker.internal:8000 grafana/k6 run - < k6-load-test.js
```

## Endpoints Tested

| Group | Endpoint | Purpose |
|-------|----------|---------|
| Health | `/health` | System health check |
| API | `/api/domains` | List domains |
| API | `/api/reports` | Get reports (paginated) |
| API | `/api/rollup/summary` | Aggregate statistics |
| API | `/api/rollup/timeline` | Time series data |
| API | `/api/rollup/sources` | Top source IPs |
| Analytics | `/analytics/geolocation/map` | Geo distribution |
| Analytics | `/analytics/cache` | Cache statistics |
| Alerts | `/alerts/active` | Active alerts |
| Alerts | `/alerts/stats` | Alert statistics |

## Performance Targets

| Metric | Target | Description |
|--------|--------|-------------|
| P95 Latency | < 2000ms | 95th percentile response time |
| P99 Latency | < 3000ms | 99th percentile response time |
| Error Rate | < 5% | Percentage of failed requests |
| Throughput | > 50 req/s | Minimum sustainable throughput |

## Interpreting Results

### Key Metrics

- **http_req_duration**: Response time distribution
- **http_req_failed**: Percentage of failed requests
- **http_reqs**: Total number of requests
- **vus**: Number of virtual users
- **iterations**: Completed test iterations

### Example Output

```
     ✓ Health check - status is 200
     ✓ Health check - response time < 2s
     ✓ Get domains - status is 200
     ...

     checks.........................: 100.00% ✓ 1000  ✗ 0
     data_received..................: 2.5 MB  156 kB/s
     data_sent......................: 150 kB  9.4 kB/s
     http_req_duration..............: avg=45ms  min=10ms  max=500ms  p(95)=120ms
     http_req_failed................: 0.00%   ✓ 0     ✗ 1000
     http_reqs......................: 1000    62.5/s
```

## Results Storage

Results are automatically saved to:
- `load-test-results.json` - Machine-readable results

## Troubleshooting

### High Error Rate

1. Check application logs: `docker-compose logs backend`
2. Verify database connectivity
3. Check for rate limiting

### High Latency

1. Check database query performance
2. Review cache hit rates
3. Check for resource constraints

### Connection Refused

1. Verify service is running
2. Check firewall rules
3. Verify BASE_URL is correct

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run Load Tests
  run: |
    docker run -i -e BASE_URL=${{ secrets.STAGING_URL }} \
      grafana/k6 run --config k6-smoke.json - < tests/load/k6-load-test.js
```

### Threshold Failures

Tests will fail (exit code 99) if thresholds are not met, making them suitable for CI/CD gates.
