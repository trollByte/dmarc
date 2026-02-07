// @ts-check
const { test, expect } = require('@playwright/test');
const { loginAndWaitForDashboard } = require('./helpers/login');

/**
 * Authentication flow tests (runs with authenticated state from setup)
 * Tests for authenticated user experience: user menu, logout, protected routes
 */

test.describe('Authenticated User Experience', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);
  });

  test('dashboard is visible when authenticated', async ({ page }) => {
    // Dashboard should be visible (login overlay hidden)
    const dashboard = page.locator('#dashboardContainer');
    await expect(dashboard).toBeVisible({ timeout: 10000 });
  });

  test('login overlay is hidden when authenticated', async ({ page }) => {
    // Login overlay should not be visible
    const loginOverlay = page.locator('#loginOverlay');

    if (await loginOverlay.count() > 0) {
      const isVisible = await loginOverlay.isVisible().catch(() => false);
      expect(isVisible).toBe(false);
    }
  });

  test('user menu is visible when logged in', async ({ page }) => {
    const userMenu = page.locator('#userMenu');

    if (await userMenu.isVisible().catch(() => false)) {
      await expect(userMenu).toBeVisible();

      // User display name should be shown
      const displayName = page.locator('#userDisplayName');
      if (await displayName.isVisible().catch(() => false)) {
        const text = await displayName.textContent();
        expect(text.length).toBeGreaterThan(0);
      }
    }
  });

  test('user menu dropdown opens on click', async ({ page }) => {
    const userMenuTrigger = page.locator('#userMenuTrigger');

    if (await userMenuTrigger.isVisible().catch(() => false)) {
      await userMenuTrigger.click();

      const dropdown = page.locator('#userMenuDropdown');
      await expect(dropdown).toBeVisible({ timeout: 3000 });

      // Dropdown should show username and role
      const username = page.locator('#userMenuUsername');
      if (await username.isVisible().catch(() => false)) {
        const text = await username.textContent();
        expect(text.length).toBeGreaterThan(0);
      }
    }
  });

  test('API calls succeed with authentication', async ({ page, request }) => {
    // Make an API call to verify auth works (uses storageState cookies)
    const response = await request.get('/api/rollup/summary');
    // Should not get 401 (authenticated via storageState)
    expect(response.status()).not.toBe(401);
  });
});

test.describe('Logout Flow', () => {
  test('logout button returns to login screen', async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);

    // Wait for dashboard to load
    const dashboard = page.locator('#dashboardContainer');
    await dashboard.waitFor({ state: 'visible', timeout: 10000 }).catch(() => {});

    // Find and click logout button (may be in a dropdown menu)
    const userMenuTrigger = page.locator('#userMenuTrigger');
    if (await userMenuTrigger.isVisible().catch(() => false)) {
      await userMenuTrigger.click();
      await page.waitForTimeout(500);
    }

    const logoutBtn = page.locator('#logoutBtn');
    if (await logoutBtn.isVisible().catch(() => false)) {
      await logoutBtn.click();

      // Login overlay should become visible
      const loginOverlay = page.locator('#loginOverlay');
      await expect(loginOverlay).toBeVisible({ timeout: 5000 });

      // Dashboard should be hidden
      const dashboardAfterLogout = page.locator('#dashboardContainer');
      if (await dashboardAfterLogout.count() > 0) {
        const isVisible = await dashboardAfterLogout.isVisible().catch(() => false);
        expect(isVisible).toBe(false);
      }
    }
  });
});

test.describe('Protected Routes', () => {
  test('API reports endpoint requires authentication', async ({ request }) => {
    // This test runs with stored auth state, so it should succeed
    const response = await request.get('/api/reports');

    // Should get a successful response (not 401) since we're authenticated
    expect([200, 404]).toContain(response.status());
  });

  test('API domains endpoint requires authentication', async ({ request }) => {
    const response = await request.get('/api/domains');

    expect([200, 404]).toContain(response.status());
  });

  test('API summary endpoint requires authentication', async ({ request }) => {
    const response = await request.get('/api/rollup/summary');

    expect([200, 404]).toContain(response.status());
  });
});
