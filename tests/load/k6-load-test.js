/**
 * DMARC Dashboard - k6 Load Testing Script
 *
 * This script performs load testing on the DMARC Dashboard API.
 *
 * Installation:
 *   - Install k6: https://k6.io/docs/getting-started/installation/
 *
 * Usage:
 *   # Basic run
 *   k6 run k6-load-test.js
 *
 *   # With environment variables
 *   k6 run -e BASE_URL=http://localhost:8000 -e API_KEY=your-key k6-load-test.js
 *
 *   # Smoke test (quick validation)
 *   k6 run --config k6-smoke.json k6-load-test.js
 *
 *   # Load test (sustained load)
 *   k6 run --config k6-load.json k6-load-test.js
 *
 *   # Stress test (find breaking point)
 *   k6 run --config k6-stress.json k6-load-test.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || '';

// Custom metrics
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency');
const authLatency = new Trend('auth_latency');
const reportLatency = new Trend('report_latency');
const requestCount = new Counter('requests');

// Test options - default to smoke test
export const options = {
    // Smoke test configuration
    stages: [
        { duration: '1m', target: 5 },    // Ramp up to 5 users
        { duration: '2m', target: 5 },    // Stay at 5 users
        { duration: '1m', target: 0 },    // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<2000'],  // 95% of requests under 2s
        http_req_failed: ['rate<0.05'],      // Less than 5% errors
        errors: ['rate<0.05'],
    },
};

// ============================================================================
// Helper Functions
// ============================================================================

function getHeaders(includeAuth = true) {
    const headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    };

    if (includeAuth && API_KEY) {
        headers['X-API-Key'] = API_KEY;
    }

    return headers;
}

function checkResponse(response, name) {
    const success = check(response, {
        [`${name} - status is 200`]: (r) => r.status === 200,
        [`${name} - response time < 2s`]: (r) => r.timings.duration < 2000,
    });

    errorRate.add(!success);
    requestCount.add(1);

    return success;
}

// ============================================================================
// Test Scenarios
// ============================================================================

export default function () {
    // Health Check
    group('Health Checks', function () {
        const healthRes = http.get(`${BASE_URL}/health`, {
            headers: getHeaders(false),
            tags: { name: 'health' },
        });

        checkResponse(healthRes, 'Health check');
        apiLatency.add(healthRes.timings.duration);
    });

    sleep(0.5);

    // API Endpoints
    group('API Endpoints', function () {
        // Get domains
        const domainsRes = http.get(`${BASE_URL}/api/domains`, {
            headers: getHeaders(),
            tags: { name: 'domains' },
        });
        checkResponse(domainsRes, 'Get domains');
        apiLatency.add(domainsRes.timings.duration);

        sleep(0.3);

        // Get reports (paginated)
        const reportsRes = http.get(`${BASE_URL}/api/reports?limit=20&offset=0`, {
            headers: getHeaders(),
            tags: { name: 'reports' },
        });
        checkResponse(reportsRes, 'Get reports');
        reportLatency.add(reportsRes.timings.duration);

        sleep(0.3);

        // Get rollup summary
        const summaryRes = http.get(`${BASE_URL}/api/rollup/summary?days=30`, {
            headers: getHeaders(),
            tags: { name: 'summary' },
        });
        checkResponse(summaryRes, 'Get summary');
        apiLatency.add(summaryRes.timings.duration);

        sleep(0.3);

        // Get timeline data
        const timelineRes = http.get(`${BASE_URL}/api/rollup/timeline?days=30`, {
            headers: getHeaders(),
            tags: { name: 'timeline' },
        });
        checkResponse(timelineRes, 'Get timeline');
        apiLatency.add(timelineRes.timings.duration);

        sleep(0.3);

        // Get sources
        const sourcesRes = http.get(`${BASE_URL}/api/rollup/sources?limit=10`, {
            headers: getHeaders(),
            tags: { name: 'sources' },
        });
        checkResponse(sourcesRes, 'Get sources');
        apiLatency.add(sourcesRes.timings.duration);
    });

    sleep(0.5);

    // Analytics Endpoints
    group('Analytics Endpoints', function () {
        // Get geolocation map data
        const geoRes = http.get(`${BASE_URL}/analytics/geolocation/map?days=30`, {
            headers: getHeaders(),
            tags: { name: 'geolocation' },
        });
        checkResponse(geoRes, 'Get geolocation');
        apiLatency.add(geoRes.timings.duration);

        sleep(0.3);

        // Get cache stats
        const cacheRes = http.get(`${BASE_URL}/analytics/cache`, {
            headers: getHeaders(),
            tags: { name: 'cache_stats' },
        });
        checkResponse(cacheRes, 'Get cache stats');
        apiLatency.add(cacheRes.timings.duration);
    });

    sleep(0.5);

    // Alerts Endpoints
    group('Alerts Endpoints', function () {
        // Get active alerts
        const alertsRes = http.get(`${BASE_URL}/alerts/active`, {
            headers: getHeaders(),
            tags: { name: 'alerts' },
        });
        checkResponse(alertsRes, 'Get alerts');
        apiLatency.add(alertsRes.timings.duration);

        sleep(0.3);

        // Get alert stats
        const alertStatsRes = http.get(`${BASE_URL}/alerts/stats`, {
            headers: getHeaders(),
            tags: { name: 'alert_stats' },
        });
        checkResponse(alertStatsRes, 'Get alert stats');
        apiLatency.add(alertStatsRes.timings.duration);
    });

    sleep(1);
}

// ============================================================================
// Lifecycle Hooks
// ============================================================================

export function setup() {
    console.log(`Starting load test against: ${BASE_URL}`);

    // Verify connectivity
    const healthRes = http.get(`${BASE_URL}/health`);
    if (healthRes.status !== 200) {
        throw new Error(`Cannot connect to ${BASE_URL}: ${healthRes.status}`);
    }

    console.log('Connection verified, starting test...');
    return { startTime: new Date().toISOString() };
}

export function teardown(data) {
    console.log(`Test started at: ${data.startTime}`);
    console.log(`Test completed at: ${new Date().toISOString()}`);
}

// ============================================================================
// Custom Summary
// ============================================================================

export function handleSummary(data) {
    const summary = {
        timestamp: new Date().toISOString(),
        baseUrl: BASE_URL,
        metrics: {
            http_reqs: data.metrics.http_reqs?.values?.count || 0,
            http_req_duration_avg: data.metrics.http_req_duration?.values?.avg || 0,
            http_req_duration_p95: data.metrics.http_req_duration?.values?.['p(95)'] || 0,
            http_req_failed: data.metrics.http_req_failed?.values?.rate || 0,
            error_rate: data.metrics.errors?.values?.rate || 0,
        },
        thresholds: data.thresholds || {},
    };

    return {
        'stdout': textSummary(data, { indent: ' ', enableColors: true }),
        'load-test-results.json': JSON.stringify(summary, null, 2),
    };
}

function textSummary(data, options) {
    const lines = [];
    lines.push('\n========== DMARC Dashboard Load Test Results ==========\n');
    lines.push(`Timestamp: ${new Date().toISOString()}`);
    lines.push(`Target: ${BASE_URL}\n`);

    if (data.metrics.http_reqs) {
        lines.push(`Total Requests: ${data.metrics.http_reqs.values.count}`);
    }
    if (data.metrics.http_req_duration) {
        lines.push(`Avg Response Time: ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms`);
        lines.push(`P95 Response Time: ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms`);
    }
    if (data.metrics.http_req_failed) {
        lines.push(`Error Rate: ${(data.metrics.http_req_failed.values.rate * 100).toFixed(2)}%`);
    }

    lines.push('\n========================================================\n');

    return lines.join('\n');
}
