// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Authentication UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('login page renders with form fields', async ({ page }) => {
    // Login form should be present
    const loginForm = page.locator('#loginForm, [data-testid="login-form"], form');
    await expect(loginForm.first()).toBeVisible({ timeout: 10000 });

    // Username field should be present
    const usernameField = page.locator('#loginUsername, #username, [name="username"], input[type="text"]');
    await expect(usernameField.first()).toBeVisible();

    // Password field should be present
    const passwordField = page.locator('#loginPassword, #password, [name="password"], input[type="password"]');
    await expect(passwordField.first()).toBeVisible();

    // Submit button should be present
    const submitBtn = page.locator('#loginSubmitBtn, button[type="submit"], #loginBtn');
    await expect(submitBtn.first()).toBeVisible();
  });

  test('login with invalid credentials shows error message', async ({ page }) => {
    // Fill in invalid credentials
    const usernameField = page.locator('#loginUsername, #username, [name="username"]');
    const passwordField = page.locator('#loginPassword, #password, [name="password"]');

    await usernameField.first().fill('invalid_user');
    await passwordField.first().fill('wrong_password');

    // Submit form
    const submitBtn = page.locator('#loginSubmitBtn, button[type="submit"], #loginBtn');
    await submitBtn.first().click();

    // Wait for error message
    const errorMessage = page.locator('#loginError, .error, .alert-error, [data-testid="error-message"], [role="alert"]');
    await expect(errorMessage.first()).toBeVisible({ timeout: 5000 });
  });

  test('page loads with login overlay visible', async ({ page }) => {
    // Login overlay or login form should be visible on load
    const loginOverlay = page.locator('#loginOverlay, #loginForm, [data-testid="login-form"]');
    await expect(loginOverlay.first()).toBeVisible({ timeout: 10000 });
  });

  test('dashboard is hidden when not authenticated', async ({ page }) => {
    // Dashboard container should be hidden or not visible
    const dashboard = page.locator('#dashboardContainer, [data-testid="dashboard"]');

    if (await dashboard.count() > 0) {
      // Dashboard element exists but should be hidden
      const isVisible = await dashboard.first().isVisible().catch(() => false);
      expect(isVisible).toBe(false);
    }

    // Login overlay should be showing instead
    const loginOverlay = page.locator('#loginOverlay, #loginForm, [data-testid="login-form"]');
    await expect(loginOverlay.first()).toBeVisible({ timeout: 10000 });
  });

  test('password field masks input', async ({ page }) => {
    const passwordField = page.locator('#loginPassword, #password, [name="password"], input[type="password"]');
    await expect(passwordField.first()).toHaveAttribute('type', 'password');
  });

  test('login button has correct text', async ({ page }) => {
    const submitBtn = page.locator('#loginSubmitBtn, button[type="submit"], #loginBtn');
    const btnText = await submitBtn.first().textContent();
    expect(btnText.trim().toLowerCase()).toMatch(/sign in|login|log in/);
  });
});
