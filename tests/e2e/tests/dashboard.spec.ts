import { test, expect } from '@playwright/test';

test.describe('DMARC Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should load the dashboard page', async ({ page }) => {
    await expect(page).toHaveTitle(/DMARC Report Dashboard/);
    await expect(page.locator('h1')).toContainText('DMARC Report Dashboard');
  });

  test('should display stats cards', async ({ page }) => {
    // Wait for stats to load (skeleton to disappear)
    await expect(page.locator('#totalReports')).not.toContainText('skeleton');
    await expect(page.locator('#passRate')).toBeVisible();
    await expect(page.locator('#failRate')).toBeVisible();
    await expect(page.locator('#totalMessages')).toBeVisible();
  });

  test('should display all charts', async ({ page }) => {
    const charts = [
      'timelineChart',
      'domainChart',
      'sourceIpChart',
      'dispositionChart',
      'alignmentChart',
      'complianceChart',
      'failureTrendChart',
      'topOrganizationsChart'
    ];

    for (const chartId of charts) {
      await expect(page.locator(`#${chartId}`)).toBeVisible();
    }
  });

  test('should display reports table', async ({ page }) => {
    await expect(page.locator('#reportsTable')).toBeVisible();
    await expect(page.locator('#reportsTableBody')).toBeVisible();
  });

  test('should have working filter controls', async ({ page }) => {
    // Domain filter
    await expect(page.locator('#domainFilter')).toBeVisible();

    // Date range filter
    await expect(page.locator('#dateRangeFilter')).toBeVisible();

    // Apply and Clear buttons
    await expect(page.locator('#applyFiltersBtn')).toBeVisible();
    await expect(page.locator('#clearFiltersBtn')).toBeVisible();
  });

  test('should show custom date fields when custom range selected', async ({ page }) => {
    const dateRangeFilter = page.locator('#dateRangeFilter');
    await dateRangeFilter.selectOption('custom');

    await expect(page.locator('.custom-date')).toBeVisible();
    await expect(page.locator('#startDate')).toBeVisible();
    await expect(page.locator('#endDate')).toBeVisible();
  });

  test('should toggle advanced filters panel', async ({ page }) => {
    const toggleBtn = page.locator('#toggleAdvancedFilters');
    const advancedPanel = page.locator('#advancedFiltersPanel');

    // Initially hidden
    await expect(advancedPanel).toBeHidden();

    // Click to show
    await toggleBtn.click();
    await expect(advancedPanel).toBeVisible();

    // Click to hide
    await toggleBtn.click();
    await expect(advancedPanel).toBeHidden();
  });

  test('should have working header action buttons', async ({ page }) => {
    await expect(page.locator('#helpBtn')).toBeVisible();
    await expect(page.locator('#uploadBtn')).toBeVisible();
    await expect(page.locator('#ingestBtn')).toBeVisible();
    await expect(page.locator('#exportBtn')).toBeVisible();
    await expect(page.locator('#refreshBtn')).toBeVisible();
  });
});

test.describe('Dark Mode', () => {
  test('should toggle dark mode', async ({ page }) => {
    await page.goto('/');

    const themeToggle = page.locator('#themeToggle');
    await expect(themeToggle).toBeVisible();

    // Initially light mode
    const html = page.locator('html');
    const initialTheme = await html.getAttribute('data-theme');

    // Toggle theme
    await themeToggle.click();

    // Theme should change
    const newTheme = await html.getAttribute('data-theme');
    expect(newTheme).not.toBe(initialTheme);

    // Toggle back
    await themeToggle.click();
    const finalTheme = await html.getAttribute('data-theme');
    expect(finalTheme).toBe(initialTheme);
  });

  test('should persist theme preference', async ({ page, context }) => {
    await page.goto('/');

    // Set to dark mode
    await page.locator('#themeToggle').click();

    // Check localStorage
    const theme = await page.evaluate(() => localStorage.getItem('dmarc-theme'));
    expect(theme).toBe('dark');

    // Reload page
    await page.reload();

    // Theme should still be dark
    const html = page.locator('html');
    await expect(html).toHaveAttribute('data-theme', 'dark');
  });
});

test.describe('Help Modal', () => {
  test('should open and close help modal', async ({ page }) => {
    await page.goto('/');

    const helpBtn = page.locator('#helpBtn');
    const helpModal = page.locator('#helpModal');

    // Open modal
    await helpBtn.click();
    await expect(helpModal).toBeVisible();

    // Check content
    await expect(helpModal.locator('h2')).toContainText('Understanding DMARC');

    // Close modal
    await helpModal.locator('#helpModalClose').click();
    await expect(helpModal).toBeHidden();
  });

  test('should close help modal on outside click', async ({ page }) => {
    await page.goto('/');

    await page.locator('#helpBtn').click();
    const helpModal = page.locator('#helpModal');
    await expect(helpModal).toBeVisible();

    // Click outside (on the modal backdrop)
    await helpModal.click({ position: { x: 10, y: 10 } });
    await expect(helpModal).toBeHidden();
  });
});

test.describe('Upload Modal', () => {
  test('should open and close upload modal', async ({ page }) => {
    await page.goto('/');

    const uploadBtn = page.locator('#uploadBtn');
    const uploadModal = page.locator('#uploadModal');

    // Open modal
    await uploadBtn.click();
    await expect(uploadModal).toBeVisible();

    // Check content
    await expect(uploadModal.locator('h2')).toContainText('Upload DMARC Reports');
    await expect(uploadModal.locator('#dropZone')).toBeVisible();

    // Close modal
    await uploadModal.locator('#uploadModalClose').click();
    await expect(uploadModal).toBeHidden();
  });

  test('should show file selection options', async ({ page }) => {
    await page.goto('/');

    await page.locator('#uploadBtn').click();

    const uploadModal = page.locator('#uploadModal');
    await expect(uploadModal.locator('#selectFilesBtn')).toBeVisible();
    await expect(uploadModal.locator('#autoProcessCheckbox')).toBeVisible();
    await expect(uploadModal.locator('#closeUploadBtn')).toBeVisible();
  });
});

test.describe('Export Dropdown', () => {
  test('should toggle export menu', async ({ page }) => {
    await page.goto('/');

    const exportBtn = page.locator('#exportBtn');
    const exportMenu = page.locator('#exportMenu');

    // Initially hidden
    await expect(exportMenu).toBeHidden();

    // Click to show
    await exportBtn.click();
    await expect(exportMenu).toBeVisible();

    // Click to hide
    await exportBtn.click();
    await expect(exportMenu).toBeHidden();
  });

  test('should have all export options', async ({ page }) => {
    await page.goto('/');

    await page.locator('#exportBtn').click();

    const exportMenu = page.locator('#exportMenu');
    await expect(exportMenu.locator('#exportReportsCSV')).toBeVisible();
    await expect(exportMenu.locator('#exportRecordsCSV')).toBeVisible();
    await expect(exportMenu.locator('#exportSourcesCSV')).toBeVisible();
    await expect(exportMenu.locator('#exportPDF')).toBeVisible();
  });
});
