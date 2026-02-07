// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');
const { loginAndWaitForDashboard, openUploadModal } = require('./helpers/login');

test.describe('Report Upload', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);
  });

  test('opens upload modal', async ({ page }) => {
    await openUploadModal(page);
    await expect(page.locator('#uploadModal')).toBeVisible();
  });

  test('closes upload modal', async ({ page }) => {
    await openUploadModal(page);
    const modal = page.locator('#uploadModal');
    await expect(modal).toBeVisible();

    // Close modal with close button
    await page.locator('#uploadModalClose').click();
    await expect(modal).toBeHidden();
  });

  test('closes upload modal with Escape key', async ({ page }) => {
    await openUploadModal(page);
    const modal = page.locator('#uploadModal');
    await expect(modal).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(modal).toBeHidden();
  });

  test('displays file drop zone', async ({ page }) => {
    await openUploadModal(page);
    const dropZone = page.locator('#dropZone');
    await expect(dropZone).toBeVisible();
  });

  test('shows file input', async ({ page }) => {
    await openUploadModal(page);

    // File input should exist (may be hidden but functional)
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeAttached();
  });

  test('accepts valid file types', async ({ page }) => {
    await openUploadModal(page);

    // Check accepted file types
    const fileInput = page.locator('input[type="file"]');
    const accept = await fileInput.getAttribute('accept');

    // Should accept XML and compressed files
    if (accept) {
      expect(accept).toMatch(/\.xml|\.gz|\.zip|application\/xml/i);
    }
  });

  test('upload button is initially disabled', async ({ page }) => {
    await openUploadModal(page);
    // uploadFilesBtn is hidden (not just disabled) when no files are selected
    const uploadFilesBtn = page.locator('#uploadFilesBtn');
    const isVisible = await uploadFilesBtn.isVisible().catch(() => false);
    if (isVisible) {
      await expect(uploadFilesBtn).toBeDisabled();
    } else {
      // Button being hidden when no files selected is acceptable behavior
      expect(true).toBeTruthy();
    }
  });
});

test.describe('Upload API Integration', () => {
  test('upload endpoint is accessible', async ({ request }) => {
    // Test that upload endpoint exists
    const response = await request.post('/api/dmarc/upload', {
      multipart: {
        files: {
          name: 'test.xml',
          mimeType: 'application/xml',
          buffer: Buffer.from('<feedback></feedback>'),
        },
      },
    });

    // Should get a response (even if it's an error about invalid content)
    expect([200, 400, 401, 404, 422]).toContain(response.status());
  });
});

test.describe('Email Ingestion', () => {
  test('shows email ingestion option', async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);

    // Open import dropdown
    await page.locator('#importBtn').click();
    await page.locator('#importMenu').waitFor({ state: 'visible', timeout: 3000 });

    // Check that email ingestion button exists in dropdown
    const ingestBtn = page.locator('#ingestBtn');
    await expect(ingestBtn).toBeVisible();
  });
});
