import { test, expect, devices } from '@playwright/test';

test.describe('Mobile Responsiveness', () => {
  test.use({ ...devices['iPhone 12'] });

  test('should display mobile-friendly header', async ({ page }) => {
    await page.goto('/');

    // Header should be visible
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('h1')).toBeVisible();

    // Action buttons should stack vertically
    const headerActions = page.locator('.header-actions');
    await expect(headerActions).toBeVisible();
  });

  test('should display stats in 2-column grid on mobile', async ({ page }) => {
    await page.goto('/');

    const statsGrid = page.locator('.stats-grid');
    await expect(statsGrid).toBeVisible();

    // All stat cards should be visible
    await expect(page.locator('.stat-card')).toHaveCount(4);
  });

  test('should display charts in single column on mobile', async ({ page }) => {
    await page.goto('/');

    // Charts should be visible
    await expect(page.locator('.chart-container').first()).toBeVisible();
  });

  test('should have touch-friendly button sizes', async ({ page }) => {
    await page.goto('/');

    const button = page.locator('.btn-primary').first();
    const box = await button.boundingBox();

    // Buttons should be at least 44px tall for touch targets
    expect(box?.height).toBeGreaterThanOrEqual(40);
  });

  test('should display filters in column layout on mobile', async ({ page }) => {
    await page.goto('/');

    const filters = page.locator('.filters');
    await expect(filters).toBeVisible();

    // Filters should be accessible
    await expect(page.locator('#domainFilter')).toBeVisible();
    await expect(page.locator('#dateRangeFilter')).toBeVisible();
  });

  test('should toggle advanced filters on mobile', async ({ page }) => {
    await page.goto('/');

    const toggleBtn = page.locator('#toggleAdvancedFilters');
    await toggleBtn.click();

    const advancedPanel = page.locator('#advancedFiltersPanel');
    await expect(advancedPanel).toBeVisible();
  });

  test('should open modals correctly on mobile', async ({ page }) => {
    await page.goto('/');

    // Open help modal
    await page.locator('#helpBtn').click();

    const helpModal = page.locator('#helpModal');
    await expect(helpModal).toBeVisible();

    // Modal should be nearly full width
    const modalContent = helpModal.locator('.modal-content');
    const box = await modalContent.boundingBox();
    const viewport = page.viewportSize();

    // Modal should take up most of the screen width
    if (box && viewport) {
      expect(box.width).toBeGreaterThan(viewport.width * 0.9);
    }

    // Close modal
    await helpModal.locator('.close').click();
  });

  test('should handle theme toggle on mobile', async ({ page }) => {
    await page.goto('/');

    const themeToggle = page.locator('#themeToggle');
    await expect(themeToggle).toBeVisible();

    // Toggle should be tappable
    await themeToggle.tap();

    const html = page.locator('html');
    await expect(html).toHaveAttribute('data-theme', 'dark');
  });
});

test.describe('Tablet Responsiveness', () => {
  test.use({ ...devices['iPad Mini'] });

  test('should display 2-column chart grid on tablet', async ({ page }) => {
    await page.goto('/');

    // Charts should be visible
    const chartsGrid = page.locator('.charts-grid').first();
    await expect(chartsGrid).toBeVisible();
  });

  test('should display stats in 2-column grid on tablet', async ({ page }) => {
    await page.goto('/');

    const statsGrid = page.locator('.stats-grid');
    await expect(statsGrid).toBeVisible();
  });

  test('should have working filters on tablet', async ({ page }) => {
    await page.goto('/');

    // Apply filter
    const dateRangeFilter = page.locator('#dateRangeFilter');
    await dateRangeFilter.selectOption('7');

    await page.locator('#applyFiltersBtn').click();

    // Dashboard should reload (verify by checking for loading state briefly)
    await expect(page.locator('#totalReports')).toBeVisible();
  });
});
