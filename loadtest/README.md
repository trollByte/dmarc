# DMARC Dashboard Load Testing

This directory contains k6 load testing scripts for the DMARC Dashboard application.

## Prerequisites

Install k6:

```bash
# macOS
brew install k6

# Windows (Chocolatey)
choco install k6

# Linux (Debian/Ubuntu)
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6

# Docker
docker pull grafana/k6
```

## Test Scripts

| Script | Description | Duration |
|--------|-------------|----------|
| `main.js` | Standard load test with ramping | ~8 minutes |
| `stress-test.js` | Finds system breaking points | ~35 minutes |
| `soak-test.js` | Extended test for memory leaks | ~1+ hour |

## Running Tests

### Basic Load Test

```bash
# Run with default settings
k6 run scripts/main.js

# Run against staging environment
k6 run scripts/main.js --env BASE_URL=https://staging.example.com

# Run with specific user credentials
k6 run scripts/main.js --env TEST_USER=admin --env TEST_PASSWORD=secret
```

### Stress Test

```bash
# Run stress test
k6 run scripts/stress-test.js

# Output results to file
k6 run scripts/stress-test.js --out json=stress-results.json
```

### Soak Test

```bash
# Run soak test (1 hour default)
k6 run scripts/soak-test.js

# Run extended soak test (4 hours)
k6 run scripts/soak-test.js --duration 4h
```

### Docker

```bash
docker run --rm -i grafana/k6 run - <scripts/main.js

# With environment variables
docker run --rm -i -e BASE_URL=http://host.docker.internal:8000 grafana/k6 run - <scripts/main.js
```

## Thresholds

The tests include the following performance thresholds:

| Metric | Threshold | Description |
|--------|-----------|-------------|
| `http_req_duration (p95)` | < 500ms | 95th percentile response time |
| `http_req_duration (p99)` | < 1000ms | 99th percentile response time |
| `http_req_failed` | < 1% | Failed request rate |
| `errors` | < 5% | Custom error rate |
| `api_latency (p95)` | < 300ms | API-specific latency |

## Output and Reporting

### Console Output

By default, k6 outputs a summary to the console showing:
- Request statistics
- Response time percentiles
- Error rates
- Custom metrics

### JSON Output

```bash
k6 run scripts/main.js --out json=results.json
```

### InfluxDB + Grafana

```bash
k6 run scripts/main.js --out influxdb=http://localhost:8086/k6
```

### Cloud (k6 Cloud)

```bash
k6 cloud scripts/main.js
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run Load Tests
  uses: grafana/k6-action@v0.3.0
  with:
    filename: loadtest/scripts/main.js
  env:
    BASE_URL: ${{ secrets.STAGING_URL }}
```

## Interpreting Results

### Good Results

- P95 latency under 500ms
- Error rate under 1%
- Consistent response times throughout the test

### Warning Signs

- Increasing latency over time (memory leak)
- Error rate increasing with load
- Timeouts during stress test

### Breaking Point Indicators

- Response times exceed 5 seconds
- Error rate exceeds 10%
- System becomes unresponsive

## Troubleshooting

### Connection Refused

Ensure the application is running and accessible:

```bash
curl http://localhost:8000/api/healthz
```

### Authentication Errors

Check test credentials:

```bash
k6 run scripts/main.js --env TEST_USER=correct_user --env TEST_PASSWORD=correct_pass
```

### Memory Issues

For large tests, increase k6 memory:

```bash
K6_BROWSER_POOL_SIZE=4 k6 run scripts/main.js
```
