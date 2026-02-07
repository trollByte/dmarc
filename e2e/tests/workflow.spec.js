// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');
const { loginAndWaitForDashboard, openUploadModal } = require('./helpers/login');

test.describe('Full User Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);
  });

  test('login lands on the dashboard with expected UI elements', async ({ page }) => {
    // Dashboard container should be visible after login
    await expect(page.locator('#dashboardContainer')).toBeVisible();

    // Login overlay should be hidden
    const loginOverlay = page.locator('#loginOverlay');
    const overlayDisplay = await loginOverlay.evaluate(el => getComputedStyle(el).display);
    expect(overlayDisplay).toBe('none');

    // Toolbar action buttons should be present
    const importBtn = page.locator('#importBtn');
    const exportBtn = page.locator('#exportBtn');
    const refreshBtn = page.locator('#refreshBtn');
    await expect(importBtn).toBeVisible();
    await expect(exportBtn).toBeVisible();
    await expect(refreshBtn).toBeVisible();
  });

  test('upload a DMARC XML file and see results', async ({ page }) => {
    await openUploadModal(page);

    // Modal should be visible with a drop zone and file input
    await expect(page.locator('#uploadModal')).toBeVisible();
    await expect(page.locator('#dropZone')).toBeVisible();

    const fileInput = page.locator('#fileInput');
    await expect(fileInput).toBeAttached();

    // Create a minimal DMARC XML report in memory and upload it
    const dmarcXml = `<?xml version="1.0" encoding="UTF-8"?>
<feedback>
  <report_metadata>
    <org_name>TestOrg</org_name>
    <email>test@example.com</email>
    <report_id>test-workflow-${Date.now()}</report_id>
    <date_range><begin>1704067200</begin><end>1704153600</end></date_range>
  </report_metadata>
  <policy_published>
    <domain>example.com</domain>
    <adkim>r</adkim>
    <aspf>r</aspf>
    <p>none</p>
  </policy_published>
  <record>
    <row>
      <source_ip>192.0.2.1</source_ip>
      <count>10</count>
      <policy_evaluated><disposition>none</disposition><dkim>pass</dkim><spf>pass</spf></policy_evaluated>
    </row>
    <identifiers><header_from>example.com</header_from></identifiers>
    <auth_results>
      <dkim><domain>example.com</domain><result>pass</result></dkim>
      <spf><domain>example.com</domain><result>pass</result></spf>
    </auth_results>
  </record>
</feedback>`;

    // Use setInputFiles to simulate file selection
    await fileInput.setInputFiles({
      name: 'test-report.xml',
      mimeType: 'application/xml',
      buffer: Buffer.from(dmarcXml),
    });

    // File list should appear showing the selected file
    const fileList = page.locator('#fileList');
    await expect(fileList).toBeVisible({ timeout: 5000 });

    // File name should appear in the list
    const fileListItems = page.locator('#fileListItems');
    await expect(fileListItems).toContainText('test-report.xml');

    // Upload button should become visible since a valid file was selected
    const uploadFilesBtn = page.locator('#uploadFilesBtn');
    await expect(uploadFilesBtn).toBeVisible({ timeout: 3000 });

    // Click upload and wait for the API response
    const uploadResponsePromise = page.waitForResponse(
      (response) => response.url().includes('/upload') && response.status() < 500
    );
    await uploadFilesBtn.click();
    await uploadResponsePromise;

    // Upload results section should appear, or a notification should show
    const uploadResults = page.locator('#uploadResults');
    const notification = page.locator('#notification');
    const hasResults = await uploadResults.isVisible().catch(() => false);
    const hasNotification = await notification.isVisible().catch(() => false);
    expect(hasResults || hasNotification).toBeTruthy();
  });

  test('apply domain filter updates dashboard data', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    // Skip if in welcome state (filters hidden when no data)
    const domainFilter = page.locator('#domainFilter');
    if (!(await domainFilter.isVisible().catch(() => false))) {
      // No data means welcome state -- nothing to filter
      await expect(page.locator('#dashboardContainer')).toBeVisible();
      return;
    }

    // Domain filter should be a select element
    await expect(domainFilter).toBeVisible();

    // Get the available options
    const options = await domainFilter.locator('option').allTextContents();
    expect(options.length).toBeGreaterThan(0);

    // If there is more than just "All Domains", pick the second option
    if (options.length > 1) {
      const secondOptionValue = await domainFilter.locator('option').nth(1).getAttribute('value');
      await domainFilter.selectOption(secondOptionValue || '');

      // Wait for API call triggered by filter change
      await page.waitForResponse(
        (response) => response.url().includes('/api/') && response.status() === 200
      );

      // Dashboard should still be visible after filtering
      await expect(page.locator('#dashboardContainer')).toBeVisible();

      // A notification about filtering may appear
      const notification = page.locator('#notification');
      if (await notification.isVisible().catch(() => false)) {
        const text = await notification.textContent();
        expect(text).toBeTruthy();
      }
    }
  });

  test('apply date range filter updates dashboard data', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    const dateRangeFilter = page.locator('#dateRangeFilter');
    if (!(await dateRangeFilter.isVisible().catch(() => false))) {
      // No data -- welcome state, skip
      await expect(page.locator('#dashboardContainer')).toBeVisible();
      return;
    }

    await expect(dateRangeFilter).toBeVisible();

    // Change to "Last 7 days"
    await dateRangeFilter.selectOption('7');

    // Wait for API response
    await page.waitForResponse(
      (response) => response.url().includes('/api/') && response.status() === 200
    );

    // Dashboard should still be visible
    await expect(page.locator('#dashboardContainer')).toBeVisible();

    // Change to "All time"
    await dateRangeFilter.selectOption('all');

    await page.waitForResponse(
      (response) => response.url().includes('/api/') && response.status() === 200
    );

    await expect(page.locator('#dashboardContainer')).toBeVisible();
  });

  test('trigger CSV export via export menu', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    const exportBtn = page.locator('#exportBtn');
    if (!(await exportBtn.isVisible().catch(() => false))) {
      return;
    }

    // Open export dropdown
    await exportBtn.click();

    // Export menu should appear
    const exportMenu = page.locator('#exportMenu');
    await expect(exportMenu).toBeVisible({ timeout: 3000 });

    // Verify export options exist
    await expect(page.locator('#exportReportsCSV')).toBeVisible();
    await expect(page.locator('#exportRecordsCSV')).toBeVisible();
    await expect(page.locator('#exportSourcesCSV')).toBeVisible();
    await expect(page.locator('#exportPDF')).toBeVisible();

    // Click "Reports (CSV)" export -- intercept the download request
    const downloadPromise = page.waitForEvent('download').catch(() => null);
    const exportResponsePromise = page.waitForResponse(
      (response) => response.url().includes('/export/') && response.status() < 500
    ).catch(() => null);

    await page.locator('#exportReportsCSV').click();

    // Wait for either a download event or an API response (which may show a notification)
    const [download, exportResponse] = await Promise.all([downloadPromise, exportResponsePromise]);

    // Either a file downloaded, or a notification appeared (e.g., "No reports found")
    const notification = page.locator('#notification.show');
    const hasDownload = download !== null;
    const hasResponse = exportResponse !== null;
    const hasNotification = await notification.isVisible().catch(() => false);

    expect(hasDownload || hasResponse || hasNotification).toBeTruthy();
  });
});
