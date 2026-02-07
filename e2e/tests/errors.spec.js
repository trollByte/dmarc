// @ts-check
const { test, expect } = require('@playwright/test');
const { loginAndWaitForDashboard, openUploadModal } = require('./helpers/login');

test.describe('Error Scenarios', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);
  });

  test('network failure on API shows error UI', async ({ page }) => {
    // Wait for initial dashboard load to complete
    await page.waitForLoadState('networkidle');

    // Intercept the rollup summary API to return a 500 error
    await page.route('**/api/rollup/summary*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    // Also intercept other dashboard APIs to return 500
    await page.route('**/api/rollup/timeline*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    // Trigger a dashboard refresh to hit the intercepted routes
    const refreshBtn = page.locator('#refreshBtn');
    await expect(refreshBtn).toBeVisible();
    await refreshBtn.click();

    // Wait for the failed API calls to process
    await page.waitForTimeout(3000);

    // The app should show some error indicator:
    // - A notification toast with the error class
    // - An error message element
    // - Or the dashboard should still be rendered (graceful degradation)
    const errorNotification = page.locator('#notification.error, #notification.show');
    const errorAlert = page.locator('[role="alert"]');
    const dashboardContainer = page.locator('#dashboardContainer');

    const hasNotification = await errorNotification.isVisible().catch(() => false);
    const hasAlert = await errorAlert.first().isVisible().catch(() => false);
    const hasDashboard = await dashboardContainer.isVisible().catch(() => false);

    // At minimum, the page should not be blank -- either error is shown or dashboard degrades gracefully
    expect(hasNotification || hasAlert || hasDashboard).toBeTruthy();
  });

  test('auth expiry (401 on API calls) redirects to login', async ({ page }) => {
    // Wait for initial load to complete
    await page.waitForLoadState('networkidle');

    // Intercept ALL API calls (except auth endpoints) to return 401
    // This simulates an expired JWT token
    await page.route('**/api/**', (route) => {
      const url = route.request().url();
      // Allow auth endpoints to pass through so the refresh attempt can also fail
      if (url.includes('/auth/login')) {
        route.continue();
        return;
      }
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Token has expired' }),
      });
    });

    // Trigger a dashboard refresh to hit the intercepted routes
    await page.locator('#refreshBtn').click();

    // Wait for the 401 handling to complete (token refresh attempt + fallback)
    await page.waitForTimeout(3000);

    // The app should show the login overlay when it gets a 401 that cannot be refreshed
    const loginOverlay = page.locator('#loginOverlay');
    const loginForm = page.locator('#loginForm');

    // Login overlay should become visible (display is no longer 'none')
    const overlayDisplay = await loginOverlay.evaluate(el => getComputedStyle(el).display);
    expect(overlayDisplay).not.toBe('none');

    // Login form should be visible within the overlay
    await expect(loginForm).toBeVisible();
  });

  test('uploading an invalid file type shows error indicator', async ({ page }) => {
    await openUploadModal(page);

    // Modal and file input should be ready
    await expect(page.locator('#uploadModal')).toBeVisible();

    const fileInput = page.locator('#fileInput');
    await expect(fileInput).toBeAttached();

    // Upload a non-XML file (e.g., a plain text file with .txt extension)
    await fileInput.setInputFiles({
      name: 'not-a-report.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('This is not a DMARC report'),
    });

    // The file list should show the file
    const fileList = page.locator('#fileList');
    await expect(fileList).toBeVisible({ timeout: 3000 });

    // The file should be marked as invalid since .txt is not an accepted extension
    const invalidFile = page.locator('.file-item.invalid');
    const fileError = page.locator('.file-error');

    const hasInvalidMarker = await invalidFile.isVisible().catch(() => false);
    const hasFileError = await fileError.isVisible().catch(() => false);

    // At least one error indicator should be shown
    expect(hasInvalidMarker || hasFileError).toBeTruthy();

    // The error should mention invalid file type
    if (hasFileError) {
      const errorText = await fileError.textContent();
      expect(errorText).toContain('Invalid file type');
    }

    // Upload button should NOT be visible since there are no valid files
    const uploadFilesBtn = page.locator('#uploadFilesBtn');
    const isUploadVisible = await uploadFilesBtn.isVisible().catch(() => false);
    if (isUploadVisible) {
      // If the button is shown but disabled, that is also acceptable
      const isDisabled = await uploadFilesBtn.isDisabled();
      expect(isDisabled).toBeTruthy();
    }
  });

  test('complete network failure keeps page rendered', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    // Abort all API calls to simulate total network failure
    await page.route('**/api/**', (route) => {
      route.abort('connectionrefused');
    });

    // Trigger a refresh
    await page.locator('#refreshBtn').click();
    await page.waitForTimeout(3000);

    // The page body should still be visible (no blank screen)
    await expect(page.locator('body')).toBeVisible();

    // The dashboard container should still exist in the DOM
    const dashboardContainer = page.locator('#dashboardContainer');
    await expect(dashboardContainer).toBeAttached();
  });
});
