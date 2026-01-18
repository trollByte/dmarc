/**
 * DMARC Dashboard Load Testing Script
 *
 * This k6 script tests the performance of the DMARC Dashboard API
 * under various load conditions.
 *
 * Usage:
 *   k6 run scripts/main.js
 *   k6 run --vus 50 --duration 5m scripts/main.js
 *   k6 run scripts/main.js --env BASE_URL=https://staging.example.com
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { randomString, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

// Custom metrics
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency');
const successfulLogins = new Counter('successful_logins');
const reportsLoaded = new Counter('reports_loaded');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_URL = `${BASE_URL}/api`;

// Test configuration with stages for ramping
export const options = {
  stages: [
    { duration: '30s', target: 10 },   // Ramp up to 10 users
    { duration: '1m', target: 10 },    // Stay at 10 users
    { duration: '30s', target: 50 },   // Ramp up to 50 users
    { duration: '2m', target: 50 },    // Stay at 50 users
    { duration: '30s', target: 100 },  // Ramp up to 100 users
    { duration: '2m', target: 100 },   // Stay at 100 users
    { duration: '1m', target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],  // 95% of requests under 500ms
    http_req_failed: ['rate<0.01'],                   // Less than 1% failed requests
    errors: ['rate<0.05'],                            // Less than 5% errors
    api_latency: ['p(95)<300'],                       // 95% API calls under 300ms
  },
  noConnectionReuse: false,
  userAgent: 'k6-load-test/1.0',
};

// Test user credentials (use environment variables in production)
const TEST_USER = {
  username: __ENV.TEST_USER || 'testuser',
  password: __ENV.TEST_PASSWORD || 'testpassword123',
};

// Setup function - runs once before the test
export function setup() {
  console.log(`Starting load test against ${BASE_URL}`);

  // Verify the API is accessible
  const healthRes = http.get(`${API_URL}/healthz`);
  if (healthRes.status !== 200) {
    throw new Error(`API health check failed: ${healthRes.status}`);
  }

  return { startTime: new Date().toISOString() };
}

// Main test function - runs for each VU
export default function() {
  let authToken = null;

  // Group: Health Check
  group('Health Check', function() {
    const res = http.get(`${API_URL}/healthz`);
    const success = check(res, {
      'health check status is 200': (r) => r.status === 200,
      'health check has status field': (r) => JSON.parse(r.body).status !== undefined,
    });
    errorRate.add(!success);
    apiLatency.add(res.timings.duration);
  });

  sleep(randomIntBetween(1, 3));

  // Group: Authentication
  group('Authentication', function() {
    const loginPayload = JSON.stringify({
      username: TEST_USER.username,
      password: TEST_USER.password,
    });

    const loginRes = http.post(`${API_URL}/auth/login`, loginPayload, {
      headers: { 'Content-Type': 'application/json' },
    });

    const loginSuccess = check(loginRes, {
      'login status is 200': (r) => r.status === 200,
      'login returns token': (r) => {
        try {
          return JSON.parse(r.body).access_token !== undefined;
        } catch {
          return false;
        }
      },
    });

    if (loginSuccess && loginRes.status === 200) {
      const body = JSON.parse(loginRes.body);
      authToken = body.access_token;
      successfulLogins.add(1);
    }

    errorRate.add(!loginSuccess);
    apiLatency.add(loginRes.timings.duration);
  });

  sleep(randomIntBetween(1, 2));

  // Only continue if authenticated
  if (authToken) {
    const authHeaders = {
      'Authorization': `Bearer ${authToken}`,
      'Content-Type': 'application/json',
    };

    // Group: Dashboard Data
    group('Dashboard', function() {
      // Get summary stats
      const summaryRes = http.get(`${API_URL}/summary/dashboard`, {
        headers: authHeaders,
      });
      check(summaryRes, {
        'summary status is 200': (r) => r.status === 200,
      });
      apiLatency.add(summaryRes.timings.duration);

      // Get trend data
      const trendRes = http.get(`${API_URL}/trends/pass-rates`, {
        headers: authHeaders,
      });
      check(trendRes, {
        'trends status is 200': (r) => r.status === 200,
      });
      apiLatency.add(trendRes.timings.duration);
    });

    sleep(randomIntBetween(1, 3));

    // Group: Reports List
    group('Reports', function() {
      const reportsRes = http.get(`${API_URL}/reports?page=1&per_page=20`, {
        headers: authHeaders,
      });

      const success = check(reportsRes, {
        'reports status is 200': (r) => r.status === 200,
        'reports returns array': (r) => {
          try {
            const body = JSON.parse(r.body);
            return Array.isArray(body.reports) || Array.isArray(body);
          } catch {
            return false;
          }
        },
      });

      if (success) {
        reportsLoaded.add(1);
      }
      errorRate.add(!success);
      apiLatency.add(reportsRes.timings.duration);
    });

    sleep(randomIntBetween(1, 2));

    // Group: Notifications
    group('Notifications', function() {
      const notifRes = http.get(`${API_URL}/notifications`, {
        headers: authHeaders,
      });
      check(notifRes, {
        'notifications status is 200': (r) => r.status === 200,
      });
      apiLatency.add(notifRes.timings.duration);

      const countRes = http.get(`${API_URL}/notifications/unread-count`, {
        headers: authHeaders,
      });
      check(countRes, {
        'unread count status is 200': (r) => r.status === 200,
      });
      apiLatency.add(countRes.timings.duration);
    });

    sleep(randomIntBetween(2, 5));

    // Group: Search (heavier operation)
    group('Search', function() {
      const searchParams = new URLSearchParams({
        q: 'gmail.com',
        page: '1',
        per_page: '10',
      });

      const searchRes = http.get(`${API_URL}/search?${searchParams}`, {
        headers: authHeaders,
      });
      check(searchRes, {
        'search status is 200 or 404': (r) => r.status === 200 || r.status === 404,
      });
      apiLatency.add(searchRes.timings.duration);
    });
  }

  sleep(randomIntBetween(3, 7));
}

// Teardown function - runs once after the test
export function teardown(data) {
  console.log(`Load test completed. Started at: ${data.startTime}`);
}
