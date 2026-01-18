/**
 * DMARC Dashboard Stress Test
 *
 * This test pushes the system beyond normal load to find its breaking point.
 * It gradually increases load until the system starts failing.
 *
 * Usage:
 *   k6 run scripts/stress-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency');

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_URL = `${BASE_URL}/api`;

export const options = {
  stages: [
    { duration: '2m', target: 50 },    // Warm up
    { duration: '5m', target: 50 },    // Stay at 50
    { duration: '2m', target: 100 },   // Scale to 100
    { duration: '5m', target: 100 },   // Stay at 100
    { duration: '2m', target: 200 },   // Scale to 200
    { duration: '5m', target: 200 },   // Stay at 200
    { duration: '2m', target: 300 },   // Scale to 300
    { duration: '5m', target: 300 },   // Stay at 300
    { duration: '2m', target: 400 },   // Scale to 400
    { duration: '5m', target: 400 },   // Stay at 400 (breaking point test)
    { duration: '5m', target: 0 },     // Scale down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'],  // More lenient for stress test
    http_req_failed: ['rate<0.10'],      // Allow 10% failure rate
    errors: ['rate<0.20'],               // Allow 20% errors at peak
  },
};

export default function() {
  // Focus on the most resource-intensive endpoints

  // Health check (light)
  const healthRes = http.get(`${API_URL}/healthz`);
  check(healthRes, {
    'health is 200': (r) => r.status === 200,
  });
  apiLatency.add(healthRes.timings.duration);

  sleep(0.5);

  // Dashboard summary (medium)
  const summaryRes = http.get(`${API_URL}/summary/dashboard`);
  const summarySuccess = check(summaryRes, {
    'summary is 200 or 401': (r) => r.status === 200 || r.status === 401,
  });
  errorRate.add(!summarySuccess);
  apiLatency.add(summaryRes.timings.duration);

  sleep(0.5);

  // Reports list with pagination (heavy)
  const reportsRes = http.get(`${API_URL}/reports?page=1&per_page=50`);
  const reportsSuccess = check(reportsRes, {
    'reports is 200 or 401': (r) => r.status === 200 || r.status === 401,
  });
  errorRate.add(!reportsSuccess);
  apiLatency.add(reportsRes.timings.duration);

  sleep(1);
}
