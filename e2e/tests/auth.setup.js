// @ts-check
const { test: setup, expect } = require('@playwright/test');

const authFile = 'playwright/.auth/user.json';

/**
 * Authentication setup - runs before all authenticated tests
 * Logs in and saves the authentication state
 */
setup('authenticate', async ({ page }) => {
  // Navigate to login page
  await page.goto('/');

  // Check if already logged in
  const logoutButton = page.locator('[data-testid="logout-button"], #logoutBtn');
  if (await logoutButton.isVisible({ timeout: 2000 }).catch(() => false)) {
    // Already logged in, save state and return
    await page.context().storageState({ path: authFile });
    return;
  }

  // Wait for login form
  const loginForm = page.locator('#loginForm');
  await expect(loginForm).toBeVisible({ timeout: 10000 });

  // Fill in credentials (use environment variables or test defaults)
  const username = process.env.TEST_USERNAME || 'admin';
  const password = process.env.TEST_PASSWORD || 'Testpass123!';

  await page.fill('#loginUsername', username);
  await page.fill('#loginPassword', password);

  // Submit login form
  await page.click('#loginSubmitBtn, button[type="submit"]');

  // Wait for successful login - dashboard container should become visible
  await expect(page.locator('#dashboardContainer')).toBeVisible({
    timeout: 10000,
  });

  // Save authentication state
  await page.context().storageState({ path: authFile });
});
