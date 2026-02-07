// @ts-check
const { expect } = require('@playwright/test');

/**
 * Log in and wait for the dashboard to become visible.
 * Use this in beforeEach for tests that need an authenticated session.
 *
 * Strategy: Wait for page to fully initialize (networkidle) so the SPA
 * can read the JWT from storageState. Only fall back to manual login
 * if the dashboard doesn't appear (avoids unnecessary login attempts
 * that can trigger account lockout with parallel workers).
 */
async function loginAndWaitForDashboard(page) {
  const username = process.env.TEST_USERNAME || 'admin';
  const password = process.env.TEST_PASSWORD || 'Testpass123!';

  const dashboard = page.locator('#dashboardContainer');

  // Wait for SPA to fully initialize (reads JWT from storageState)
  await page.waitForLoadState('networkidle');

  // Check if storageState auto-logged us in
  if (await dashboard.isVisible()) {
    return;
  }

  // StorageState didn't work — try manual login
  const loginForm = page.locator('#loginForm');
  await loginForm.waitFor({ state: 'visible', timeout: 5000 });

  await page.locator('#loginUsername').fill(username);
  await page.locator('#loginPassword').fill(password);
  await page.locator('#loginSubmitBtn').click();

  try {
    await expect(dashboard).toBeVisible({ timeout: 10000 });
    return;
  } catch {
    // Login failed — reload to give storageState another chance
    await page.reload();
    await page.waitForLoadState('networkidle');

    if (await dashboard.isVisible()) {
      return;
    }

    // Final login attempt
    await loginForm.waitFor({ state: 'visible', timeout: 5000 });
    await page.locator('#loginUsername').fill(username);
    await page.locator('#loginPassword').fill(password);
    await page.locator('#loginSubmitBtn').click();
    await expect(dashboard).toBeVisible({ timeout: 10000 });
  }
}

/**
 * Open the upload modal via the import dropdown.
 * Flow: click #importBtn → dropdown opens → click #uploadBtn → modal opens
 */
async function openUploadModal(page) {
  // Click the import dropdown toggle
  await page.locator('#importBtn').click();

  // Wait for dropdown menu to appear
  await page.locator('#importMenu').waitFor({ state: 'visible', timeout: 3000 });

  // Click "Upload Files" in the dropdown
  await page.locator('#uploadBtn').click();

  // Wait for modal to appear
  await expect(page.locator('#uploadModal')).toBeVisible({ timeout: 3000 });
}

module.exports = { loginAndWaitForDashboard, openUploadModal };
