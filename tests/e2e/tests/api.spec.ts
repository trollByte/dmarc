import { test, expect } from '@playwright/test';

test.describe('API Health Check', () => {
  test('should return healthy status', async ({ request }) => {
    const response = await request.get('/health');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('status');
  });
});

test.describe('Dashboard API Endpoints', () => {
  test('should return domains list', async ({ request }) => {
    const response = await request.get('/api/domains');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('domains');
    expect(Array.isArray(data.domains)).toBeTruthy();
  });

  test('should return rollup summary', async ({ request }) => {
    const response = await request.get('/api/rollup/summary');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('total_reports');
    expect(data).toHaveProperty('total_messages');
  });

  test('should return rollup timeline', async ({ request }) => {
    const response = await request.get('/api/rollup/timeline?days=30');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('timeline');
    expect(Array.isArray(data.timeline)).toBeTruthy();
  });

  test('should return rollup sources', async ({ request }) => {
    const response = await request.get('/api/rollup/sources?page_size=10');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('sources');
    expect(Array.isArray(data.sources)).toBeTruthy();
  });

  test('should return alignment breakdown', async ({ request }) => {
    const response = await request.get('/api/rollup/alignment-breakdown');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('both_pass');
    expect(data).toHaveProperty('both_fail');
  });

  test('should return failure trend', async ({ request }) => {
    const response = await request.get('/api/rollup/failure-trend');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('trend');
    expect(Array.isArray(data.trend)).toBeTruthy();
  });

  test('should return top organizations', async ({ request }) => {
    const response = await request.get('/api/rollup/top-organizations?limit=10');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('organizations');
    expect(Array.isArray(data.organizations)).toBeTruthy();
  });

  test('should return reports list', async ({ request }) => {
    const response = await request.get('/api/reports?page_size=10');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('reports');
    expect(Array.isArray(data.reports)).toBeTruthy();
  });
});

test.describe('API Filtering', () => {
  test('should filter by date range', async ({ request }) => {
    const response = await request.get('/api/rollup/summary?days=7');
    expect(response.ok()).toBeTruthy();
  });

  test('should filter by domain', async ({ request }) => {
    // First get a domain
    const domainsResponse = await request.get('/api/domains');
    const domainsData = await domainsResponse.json();

    if (domainsData.domains.length > 0) {
      const domain = domainsData.domains[0].domain;
      const response = await request.get(`/api/rollup/summary?domain=${domain}`);
      expect(response.ok()).toBeTruthy();
    }
  });

  test('should handle invalid parameters gracefully', async ({ request }) => {
    const response = await request.get('/api/rollup/summary?days=invalid');
    // Should return 422 or handle gracefully
    expect([200, 422].includes(response.status())).toBeTruthy();
  });
});

test.describe('API Error Handling', () => {
  test('should return 404 for non-existent report', async ({ request }) => {
    const response = await request.get('/api/reports/00000000-0000-0000-0000-000000000000');
    expect(response.status()).toBe(404);
  });

  test('should return 405 for wrong method on trigger endpoints', async ({ request }) => {
    const response = await request.get('/api/process/trigger');
    expect(response.status()).toBe(405);
  });
});
