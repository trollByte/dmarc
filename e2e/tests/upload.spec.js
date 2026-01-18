// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');

test.describe('Report Upload', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('opens upload modal', async ({ page }) => {
    // Click import/upload button
    const uploadButton = page.locator('#importBtn, [data-testid="upload-button"], button:has-text("Import")');
    await uploadButton.click();

    // Modal should be visible
    const modal = page.locator('#uploadModal, [data-testid="upload-modal"], .modal');
    await expect(modal).toBeVisible();
  });

  test('closes upload modal', async ({ page }) => {
    // Open modal
    await page.locator('#importBtn, [data-testid="upload-button"]').click();
    const modal = page.locator('#uploadModal, [data-testid="upload-modal"]');
    await expect(modal).toBeVisible();

    // Close modal with X button or close button
    const closeButton = page.locator('[data-testid="close-modal"], .modal-close, button:has-text("Cancel")');
    await closeButton.click();

    // Modal should be hidden
    await expect(modal).toBeHidden();
  });

  test('closes upload modal with Escape key', async ({ page }) => {
    // Open modal
    await page.locator('#importBtn, [data-testid="upload-button"]').click();
    const modal = page.locator('#uploadModal, [data-testid="upload-modal"]');
    await expect(modal).toBeVisible();

    // Press Escape
    await page.keyboard.press('Escape');

    // Modal should be hidden
    await expect(modal).toBeHidden();
  });

  test('displays file drop zone', async ({ page }) => {
    await page.locator('#importBtn, [data-testid="upload-button"]').click();

    // Drop zone should be visible
    const dropZone = page.locator('.drop-zone, [data-testid="drop-zone"], .file-upload-area');
    await expect(dropZone).toBeVisible();
  });

  test('shows file input', async ({ page }) => {
    await page.locator('#importBtn, [data-testid="upload-button"]').click();

    // File input should exist (may be hidden but functional)
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeAttached();
  });

  test('accepts valid file types', async ({ page }) => {
    await page.locator('#importBtn, [data-testid="upload-button"]').click();

    // Check accepted file types
    const fileInput = page.locator('input[type="file"]');
    const accept = await fileInput.getAttribute('accept');

    // Should accept XML and compressed files
    if (accept) {
      expect(accept).toMatch(/\.xml|\.gz|\.zip|application\/xml/i);
    }
  });

  test('upload button is initially disabled', async ({ page }) => {
    await page.locator('#importBtn, [data-testid="upload-button"]').click();

    // Upload/submit button should be disabled when no files selected
    const submitButton = page.locator('#uploadSubmit, [data-testid="submit-upload"], button:has-text("Upload")');
    if (await submitButton.isVisible()) {
      await expect(submitButton).toBeDisabled();
    }
  });
});

test.describe('Upload API Integration', () => {
  test('upload endpoint is accessible', async ({ request }) => {
    // Test that upload endpoint exists
    const response = await request.post('/api/upload', {
      multipart: {
        files: {
          name: 'test.xml',
          mimeType: 'application/xml',
          buffer: Buffer.from('<feedback></feedback>'),
        },
      },
    });

    // Should get a response (even if it's an error about invalid content)
    expect([200, 400, 401, 422]).toContain(response.status());
  });
});

test.describe('Email Ingestion', () => {
  test('shows email ingestion option', async ({ page }) => {
    await page.locator('#importBtn, [data-testid="upload-button"]').click();

    // Look for email ingestion tab or option
    const emailOption = page.locator('[data-testid="email-ingestion"], button:has-text("Email"), #emailIngestTab');

    if (await emailOption.isVisible()) {
      await emailOption.click();

      // Should show email ingestion UI
      const emailUI = page.locator('[data-testid="email-ingestion-form"], .email-ingestion');
      await expect(emailUI).toBeVisible();
    }
  });
});
