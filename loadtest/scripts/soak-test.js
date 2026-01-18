/**
 * DMARC Dashboard Soak Test
 *
 * This test runs for an extended period to identify memory leaks,
 * resource exhaustion, and degradation over time.
 *
 * Usage:
 *   k6 run scripts/soak-test.js
 *   k6 run --duration 4h scripts/soak-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency');
const totalRequests = new Counter('total_requests');

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_URL = `${BASE_URL}/api`;

export const options = {
  stages: [
    { duration: '5m', target: 30 },     // Ramp up
    { duration: '1h', target: 30 },     // Stay at normal load
    { duration: '5m', target: 0 },      // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],
    errors: ['rate<0.05'],
    // Check for degradation over time
    'api_latency{group:::Health Check}': ['p(95)<100'],
    'api_latency{group:::Dashboard}': ['p(95)<300'],
  },
};

// Simulate realistic user behavior
const scenarios = [
  { weight: 30, name: 'dashboard_viewer' },
  { weight: 40, name: 'report_browser' },
  { weight: 20, name: 'active_user' },
  { weight: 10, name: 'heavy_user' },
];

function selectScenario() {
  const rand = Math.random() * 100;
  let cumulative = 0;
  for (const scenario of scenarios) {
    cumulative += scenario.weight;
    if (rand < cumulative) {
      return scenario.name;
    }
  }
  return 'dashboard_viewer';
}

function dashboardViewer() {
  // Just checks dashboard
  const res = http.get(`${API_URL}/summary/dashboard`);
  check(res, { 'dashboard ok': (r) => r.status === 200 || r.status === 401 });
  apiLatency.add(res.timings.duration);
  totalRequests.add(1);
  sleep(5);
}

function reportBrowser() {
  // Browses through reports
  for (let page = 1; page <= 3; page++) {
    const res = http.get(`${API_URL}/reports?page=${page}&per_page=20`);
    check(res, { 'reports ok': (r) => r.status === 200 || r.status === 401 });
    apiLatency.add(res.timings.duration);
    totalRequests.add(1);
    sleep(2);
  }
}

function activeUser() {
  // Uses multiple features
  const endpoints = [
    '/summary/dashboard',
    '/reports?page=1&per_page=10',
    '/notifications',
    '/trends/pass-rates',
  ];

  for (const endpoint of endpoints) {
    const res = http.get(`${API_URL}${endpoint}`);
    check(res, { 'endpoint ok': (r) => r.status === 200 || r.status === 401 });
    apiLatency.add(res.timings.duration);
    totalRequests.add(1);
    sleep(1);
  }
}

function heavyUser() {
  // Performs resource-intensive operations
  // Search
  const searchRes = http.get(`${API_URL}/search?q=test&per_page=50`);
  check(searchRes, { 'search ok': (r) => r.status === 200 || r.status === 404 || r.status === 401 });
  totalRequests.add(1);
  sleep(1);

  // Export (if endpoint exists)
  const exportRes = http.get(`${API_URL}/export/summary`);
  check(exportRes, { 'export ok': (r) => r.status === 200 || r.status === 404 || r.status === 401 });
  totalRequests.add(1);
  sleep(2);

  // Large report list
  const reportsRes = http.get(`${API_URL}/reports?page=1&per_page=100`);
  check(reportsRes, { 'large reports ok': (r) => r.status === 200 || r.status === 401 });
  totalRequests.add(1);
  sleep(3);
}

export default function() {
  // Health check first
  const healthRes = http.get(`${API_URL}/healthz`);
  const success = check(healthRes, {
    'health check ok': (r) => r.status === 200,
  });
  errorRate.add(!success);
  totalRequests.add(1);

  // Run scenario based on selection
  const scenario = selectScenario();
  switch (scenario) {
    case 'dashboard_viewer':
      dashboardViewer();
      break;
    case 'report_browser':
      reportBrowser();
      break;
    case 'active_user':
      activeUser();
      break;
    case 'heavy_user':
      heavyUser();
      break;
  }

  // Random think time
  sleep(Math.random() * 5 + 2);
}

export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'soak-test-summary.json': JSON.stringify(data, null, 2),
  };
}

// Helper for text summary
function textSummary(data, options) {
  const summary = [];
  summary.push('=== Soak Test Summary ===');
  summary.push(`Total Requests: ${data.metrics.total_requests?.values?.count || 'N/A'}`);
  summary.push(`Error Rate: ${(data.metrics.errors?.values?.rate * 100)?.toFixed(2) || 0}%`);
  summary.push(`P95 Latency: ${data.metrics.api_latency?.values?.['p(95)']?.toFixed(2) || 'N/A'}ms`);
  summary.push(`P99 Latency: ${data.metrics.api_latency?.values?.['p(99)']?.toFixed(2) || 'N/A'}ms`);
  return summary.join('\n');
}
