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
  const loginForm = page.locator('#loginForm, [data-testid="login-form"], form');
  await expect(loginForm).toBeVisible({ timeout: 10000 });

  // Fill in credentials (use environment variables or test defaults)
  const username = process.env.TEST_USERNAME || 'admin';
  const password = process.env.TEST_PASSWORD || 'changeme123!';

  await page.fill('#username, [name="username"], input[type="text"]', username);
  await page.fill('#password, [name="password"], input[type="password"]', password);

  // Submit login form
  await page.click('button[type="submit"], #loginBtn, [data-testid="login-button"]');

  // Wait for successful login - dashboard should be visible
  await expect(page.locator('#dashboard, [data-testid="dashboard"], .dashboard')).toBeVisible({
    timeout: 10000,
  });

  // Verify we're logged in
  await expect(page).not.toHaveURL(/login/);

  // Save authentication state
  await page.context().storageState({ path: authFile });
});
