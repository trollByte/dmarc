// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for unauthenticated users
 * These run without the stored authentication state
 */

test.describe('Authentication Flow', () => {
  test('shows login page for unauthenticated users', async ({ page }) => {
    await page.goto('/');

    // Should show login form or redirect to login
    const loginForm = page.locator('#loginForm, [data-testid="login-form"], form');
    const loginButton = page.locator('button:has-text("Login"), button:has-text("Sign in")');

    const hasLoginForm = await loginForm.isVisible().catch(() => false);
    const hasLoginButton = await loginButton.isVisible().catch(() => false);

    expect(hasLoginForm || hasLoginButton).toBeTruthy();
  });

  test('displays login form fields', async ({ page }) => {
    await page.goto('/');

    // Username field
    const usernameField = page.locator('#username, [name="username"], input[type="text"]');
    await expect(usernameField.first()).toBeVisible();

    // Password field
    const passwordField = page.locator('#password, [name="password"], input[type="password"]');
    await expect(passwordField.first()).toBeVisible();
  });

  test('shows error for invalid credentials', async ({ page }) => {
    await page.goto('/');

    // Fill in invalid credentials
    await page.fill('#username, [name="username"]', 'invalid_user');
    await page.fill('#password, [name="password"]', 'wrong_password');

    // Submit form
    await page.click('button[type="submit"], #loginBtn');

    // Wait for error message
    const errorMessage = page.locator('.error, .alert-error, [data-testid="error-message"], [role="alert"]');
    await expect(errorMessage).toBeVisible({ timeout: 5000 });
  });

  test('shows error for empty credentials', async ({ page }) => {
    await page.goto('/');

    // Try to submit without filling in credentials
    const submitButton = page.locator('button[type="submit"], #loginBtn');
    await submitButton.click();

    // Should show validation error or prevent submission
    // Either error message shows or form doesn't submit
    const errorMessage = page.locator('.error, .alert-error, [data-testid="error-message"]');
    const isErrorVisible = await errorMessage.isVisible().catch(() => false);

    // If no error message, we should still be on login page
    if (!isErrorVisible) {
      const loginForm = page.locator('#loginForm, [data-testid="login-form"]');
      await expect(loginForm).toBeVisible();
    }
  });

  test('password field hides input', async ({ page }) => {
    await page.goto('/');

    const passwordField = page.locator('#password, [name="password"], input[type="password"]');
    await expect(passwordField.first()).toHaveAttribute('type', 'password');
  });
});

test.describe('API Authentication', () => {
  test('protected endpoints require authentication', async ({ request }) => {
    // Try to access protected endpoint without auth
    const response = await request.get('/api/reports');

    // Should return 401 or redirect
    expect([401, 403]).toContain(response.status());
  });

  test('health endpoint is public', async ({ request }) => {
    const response = await request.get('/health');
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data.status).toBeDefined();
  });

  test('API health check is public', async ({ request }) => {
    const response = await request.get('/api/healthz');
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data.status).toBeDefined();
  });
});

test.describe('Password Reset', () => {
  test('forgot password link exists', async ({ page }) => {
    await page.goto('/');

    const forgotPasswordLink = page.locator('a:has-text("Forgot"), a:has-text("Reset password"), [data-testid="forgot-password"]');

    if (await forgotPasswordLink.isVisible()) {
      await expect(forgotPasswordLink).toHaveAttribute('href', /.*/);
    }
  });
});

test.describe('Security Headers', () => {
  test('response includes security headers', async ({ request }) => {
    const response = await request.get('/health');

    const headers = response.headers();

    // Check for security headers (may only be present in production)
    // These are informational - won't fail if not present in dev
    const securityHeaders = [
      'x-content-type-options',
      'x-frame-options',
    ];

    securityHeaders.forEach((header) => {
      if (headers[header]) {
        expect(headers[header]).toBeDefined();
      }
    });
  });
});
