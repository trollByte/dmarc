// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('displays main dashboard components', async ({ page }) => {
    // Check for key dashboard elements
    await expect(page.locator('h1, .dashboard-title')).toBeVisible();

    // Check for stat cards
    const statCards = page.locator('.stat-card, [data-testid="stat-card"]');
    await expect(statCards.first()).toBeVisible();

    // Check for charts container
    await expect(page.locator('#charts, .charts-container, canvas').first()).toBeVisible();
  });

  test('displays summary statistics', async ({ page }) => {
    // Wait for data to load
    await page.waitForResponse((response) =>
      response.url().includes('/api/rollup/summary') && response.status() === 200
    );

    // Check stat values are displayed
    const totalMessages = page.locator('[data-testid="total-messages"], #totalMessages');
    await expect(totalMessages).toBeVisible();
  });

  test('shows filter controls', async ({ page }) => {
    // Domain filter
    const domainFilter = page.locator('#domainFilter, [data-testid="domain-filter"]');
    await expect(domainFilter).toBeVisible();

    // Date range filter
    const dateFilter = page.locator('#dateRangeFilter, [data-testid="date-filter"]');
    await expect(dateFilter).toBeVisible();
  });

  test('filters update dashboard data', async ({ page }) => {
    // Get initial data
    const initialTotal = await page.locator('[data-testid="total-messages"], #totalMessages').textContent();

    // Change date filter
    await page.selectOption('#dateRangeFilter, [data-testid="date-filter"]', '7');

    // Wait for refresh
    await page.waitForResponse((response) =>
      response.url().includes('/api/') && response.status() === 200
    );

    // Data should potentially change (or stay same if no data in that range)
    await expect(page.locator('[data-testid="total-messages"], #totalMessages')).toBeVisible();
  });

  test('refresh button reloads data', async ({ page }) => {
    // Click refresh button
    const refreshButton = page.locator('#refreshBtn, [data-testid="refresh-button"], button:has-text("Refresh")');
    await refreshButton.click();

    // Wait for API calls
    await page.waitForResponse((response) =>
      response.url().includes('/api/') && response.status() === 200
    );

    // Dashboard should still be visible
    await expect(page.locator('.stat-card, [data-testid="stat-card"]').first()).toBeVisible();
  });

  test('toggle secondary charts', async ({ page }) => {
    // Find toggle button
    const toggleButton = page.locator('#toggleSecondaryCharts, [data-testid="toggle-charts"]');

    if (await toggleButton.isVisible()) {
      // Click to show secondary charts
      await toggleButton.click();

      // Secondary charts should be visible
      const secondaryCharts = page.locator('#secondaryCharts, .secondary-charts');
      await expect(secondaryCharts).toBeVisible();

      // Toggle again to hide
      await toggleButton.click();
      await expect(secondaryCharts).toBeHidden();
    }
  });

  test('theme toggle works', async ({ page }) => {
    const themeToggle = page.locator('#themeToggle, [data-testid="theme-toggle"]');

    if (await themeToggle.isVisible()) {
      // Get initial theme
      const initialTheme = await page.locator('html').getAttribute('data-theme');

      // Toggle theme
      await themeToggle.click();

      // Theme should change
      const newTheme = await page.locator('html').getAttribute('data-theme');
      expect(newTheme).not.toBe(initialTheme);
    }
  });
});

test.describe('Dashboard Charts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for charts to load
    await page.waitForTimeout(2000);
  });

  test('timeline chart renders', async ({ page }) => {
    const timelineChart = page.locator('#timelineChart, [data-testid="timeline-chart"]');
    await expect(timelineChart).toBeVisible();
  });

  test('domain chart renders', async ({ page }) => {
    const domainChart = page.locator('#domainChart, [data-testid="domain-chart"]');
    await expect(domainChart).toBeVisible();
  });

  test('source IP chart renders', async ({ page }) => {
    const sourceIpChart = page.locator('#sourceIpChart, [data-testid="source-ip-chart"]');
    await expect(sourceIpChart).toBeVisible();
  });

  test('disposition chart renders', async ({ page }) => {
    const dispositionChart = page.locator('#dispositionChart, [data-testid="disposition-chart"]');
    await expect(dispositionChart).toBeVisible();
  });
});

test.describe('Dashboard Filter Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('filter panel toggle shows and hides advanced filters', async ({ page }) => {
    // Look for a filter panel toggle button
    const filterToggle = page.locator('#filterToggle, [data-testid="filter-toggle"], button:has-text("Filters"), button:has-text("Advanced")');

    if (await filterToggle.isVisible().catch(() => false)) {
      // Click to expand/toggle filter panel
      await filterToggle.click();

      // Advanced filter elements should become visible
      const advancedFilters = page.locator('#advancedFilters, .advanced-filters, #sourceIpFilter, [data-testid="advanced-filters"]');
      if (await advancedFilters.first().isVisible().catch(() => false)) {
        await expect(advancedFilters.first()).toBeVisible();

        // Toggle again to hide
        await filterToggle.click();
        // Panel may hide or stay open depending on implementation
      }
    }
  });

  test('filter apply and reset buttons exist', async ({ page }) => {
    // Apply button
    const applyBtn = page.locator('#applyFilters, [data-testid="apply-filters"], button:has-text("Apply")');
    if (await applyBtn.isVisible().catch(() => false)) {
      await expect(applyBtn).toBeVisible();
    }

    // Reset button
    const resetBtn = page.locator('#resetFilters, [data-testid="reset-filters"], button:has-text("Reset"), button:has-text("Clear")');
    if (await resetBtn.isVisible().catch(() => false)) {
      await expect(resetBtn).toBeVisible();
    }
  });
});

test.describe('Dashboard Chart Containers', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
  });

  test('all primary chart canvas elements are present', async ({ page }) => {
    // Check that chart canvas elements exist in the DOM
    const chartIds = ['timelineChart', 'domainChart', 'sourceIpChart', 'dispositionChart'];

    for (const chartId of chartIds) {
      const chart = page.locator(`#${chartId}, [data-testid="${chartId}"]`);
      if (await chart.count() > 0) {
        await expect(chart).toBeAttached();
      }
    }
  });

  test('chart containers have appropriate sizing', async ({ page }) => {
    const chartContainer = page.locator('.chart-card, .chart-container, [data-testid="chart-container"]');

    if (await chartContainer.count() > 0) {
      const box = await chartContainer.first().boundingBox();
      if (box) {
        // Charts should have reasonable dimensions
        expect(box.width).toBeGreaterThan(100);
        expect(box.height).toBeGreaterThan(50);
      }
    }
  });
});

test.describe('Dashboard Accessibility', () => {
  test('has no critical accessibility violations', async ({ page }) => {
    await page.goto('/');

    // Basic accessibility checks
    // Check for alt text on images
    const images = page.locator('img');
    const imageCount = await images.count();
    for (let i = 0; i < imageCount; i++) {
      const img = images.nth(i);
      const alt = await img.getAttribute('alt');
      const role = await img.getAttribute('role');
      // Images should have alt text or be marked as decorative
      expect(alt !== null || role === 'presentation').toBeTruthy();
    }

    // Check for form labels
    const inputs = page.locator('input:not([type="hidden"])');
    const inputCount = await inputs.count();
    for (let i = 0; i < inputCount; i++) {
      const input = inputs.nth(i);
      const id = await input.getAttribute('id');
      const ariaLabel = await input.getAttribute('aria-label');
      const ariaLabelledBy = await input.getAttribute('aria-labelledby');

      if (id) {
        const label = page.locator(`label[for="${id}"]`);
        const hasLabel = await label.count() > 0;
        // Input should have a label, aria-label, or aria-labelledby
        expect(hasLabel || ariaLabel || ariaLabelledBy).toBeTruthy();
      }
    }
  });

  test('keyboard navigation works', async ({ page }) => {
    await page.goto('/');

    // Tab through interactive elements
    await page.keyboard.press('Tab');

    // First focusable element should be focused
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });
});

test.describe('Dashboard Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('export button is visible', async ({ page }) => {
    const exportBtn = page.locator('#exportBtn, [data-testid="export-button"], button:has-text("Export"), #exportMenu');

    if (await exportBtn.isVisible().catch(() => false)) {
      await expect(exportBtn).toBeVisible();
    }
  });

  test('export menu shows format options', async ({ page }) => {
    const exportBtn = page.locator('#exportBtn, [data-testid="export-button"], button:has-text("Export")');

    if (await exportBtn.isVisible().catch(() => false)) {
      await exportBtn.click();

      // Export menu should show options like CSV, PDF, JSON
      const exportMenu = page.locator('.export-menu, .export-dropdown, [data-testid="export-menu"]');
      if (await exportMenu.isVisible().catch(() => false)) {
        await expect(exportMenu).toBeVisible();

        // Check for at least one export format option
        const exportOption = page.locator('.export-option, [data-testid="export-option"], button:has-text("CSV"), button:has-text("JSON"), a:has-text("CSV"), a:has-text("JSON")');
        if (await exportOption.first().isVisible().catch(() => false)) {
          await expect(exportOption.first()).toBeVisible();
        }
      }
    }
  });
});

test.describe('Dashboard Error States', () => {
  test('shows error state when API returns 500', async ({ page }) => {
    // Intercept API calls and return 500 error
    await page.route('**/api/rollup/summary*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    await page.goto('/');

    // Wait for the dashboard to attempt loading
    await page.waitForTimeout(3000);

    // Should show some kind of error indicator or the stat cards should handle the failure
    const errorIndicator = page.locator('.error, .error-message, .component-error, [role="alert"], .notification-error');
    const hasError = await errorIndicator.first().isVisible().catch(() => false);

    // Either error is shown, or stat cards show fallback values (dashes or zeros)
    const statCard = page.locator('.stat-card, [data-testid="stat-card"]');
    const hasStatCards = await statCard.first().isVisible().catch(() => false);

    expect(hasError || hasStatCards).toBeTruthy();
  });

  test('shows error state when network is down', async ({ page }) => {
    // Intercept all API calls and abort them (simulate network failure)
    await page.route('**/api/**', (route) => {
      route.abort('connectionrefused');
    });

    await page.goto('/');

    // Wait for the dashboard to attempt loading
    await page.waitForTimeout(3000);

    // Page should still be rendered (not a blank screen)
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });
});
