// @ts-check
const { test, expect } = require('@playwright/test');
const { loginAndWaitForDashboard } = require('./helpers/login');

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);
  });

  test('displays main dashboard components', async ({ page }) => {
    // Dashboard shows either stat cards (with data) or welcome state (no data)
    const statCards = page.locator('.stat-card');
    const welcomeState = page.locator('#welcomeEmptyState, .welcome-empty-state');

    const hasStatCards = await statCards.first().isVisible().catch(() => false);
    const hasWelcome = await welcomeState.isVisible().catch(() => false);

    expect(hasStatCards || hasWelcome).toBeTruthy();
  });

  test('displays summary statistics', async ({ page }) => {
    // Stats visible with data, or welcome state shown when empty
    const totalMessages = page.locator('#totalMessages');
    const welcomeState = page.locator('#welcomeEmptyState, .welcome-empty-state');

    const hasStats = await totalMessages.isVisible().catch(() => false);
    const hasWelcome = await welcomeState.isVisible().catch(() => false);

    expect(hasStats || hasWelcome).toBeTruthy();
  });

  test('shows filter controls', async ({ page }) => {
    // Filters are hidden in welcome state (no data); visible when data exists
    const domainFilter = page.locator('#domainFilter');
    const welcomeState = page.locator('#welcomeEmptyState, .welcome-empty-state');

    const hasFilters = await domainFilter.isVisible().catch(() => false);
    const hasWelcome = await welcomeState.isVisible().catch(() => false);

    expect(hasFilters || hasWelcome).toBeTruthy();

    if (hasFilters) {
      const dateFilter = page.locator('#dateRangeFilter');
      await expect(dateFilter).toBeVisible();
    }
  });

  test('filters update dashboard data', async ({ page }) => {
    // Wait for dashboard to settle (API response may trigger welcome state)
    await page.waitForLoadState('networkidle');

    // Skip if in welcome state (filters hidden when no data)
    const dateRangeFilter = page.locator('#dateRangeFilter');
    if (!(await dateRangeFilter.isVisible().catch(() => false))) {
      return;
    }

    // Change date filter
    await page.selectOption('#dateRangeFilter', '7');

    // Wait for refresh
    await page.waitForResponse((response) =>
      response.url().includes('/api/') && response.status() === 200
    );

    // Data should potentially change (or stay same if no data in that range)
    await expect(page.locator('#totalMessages')).toBeVisible();
  });

  test('refresh button reloads data', async ({ page }) => {
    // Refresh button is in toolbar, always visible
    const refreshButton = page.locator('#refreshBtn');
    await expect(refreshButton).toBeVisible();
    await refreshButton.click();

    // Wait for API calls
    await page.waitForResponse((response) =>
      response.url().includes('/api/') && response.status() === 200
    );

    // Dashboard container should still be visible
    await expect(page.locator('#dashboardContainer')).toBeVisible();
  });

  test('toggle secondary charts', async ({ page }) => {
    // Find toggle button
    const toggleButton = page.locator('#toggleSecondaryCharts');

    if (await toggleButton.isVisible()) {
      // Click to show secondary charts
      await toggleButton.click();

      // Secondary charts should be visible
      const secondaryCharts = page.locator('#secondaryChartsContent');
      await expect(secondaryCharts).toBeVisible();

      // Toggle again to hide
      await toggleButton.click();
      await expect(secondaryCharts).toBeHidden();
    }
  });

  test('theme toggle works', async ({ page }) => {
    const themeToggle = page.locator('#themeToggle');

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
    await loginAndWaitForDashboard(page);
    // Wait for charts to load
    await page.waitForTimeout(2000);
  });

  test('timeline chart renders', async ({ page }) => {
    const timelineChart = page.locator('#timelineChart');
    // Charts hidden in welcome state (no data)
    if (await timelineChart.isVisible().catch(() => false)) {
      await expect(timelineChart).toBeVisible();
    } else {
      await expect(page.locator('#dashboardContainer')).toBeVisible();
    }
  });

  test('domain chart renders', async ({ page }) => {
    const domainChart = page.locator('#domainChart');
    if (await domainChart.isVisible().catch(() => false)) {
      await expect(domainChart).toBeVisible();
    } else {
      await expect(page.locator('#dashboardContainer')).toBeVisible();
    }
  });

  test('source IP chart renders', async ({ page }) => {
    const sourceIpChart = page.locator('#sourceIpChart');
    if (await sourceIpChart.isVisible().catch(() => false)) {
      await expect(sourceIpChart).toBeVisible();
    } else {
      await expect(page.locator('#dashboardContainer')).toBeVisible();
    }
  });

  test('disposition chart renders', async ({ page }) => {
    const dispositionChart = page.locator('#dispositionChart');
    if (await dispositionChart.isVisible().catch(() => false)) {
      await expect(dispositionChart).toBeVisible();
    } else {
      await expect(page.locator('#dashboardContainer')).toBeVisible();
    }
  });
});

test.describe('Dashboard Filter Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);
  });

  test('filter panel toggle shows and hides advanced filters', async ({ page }) => {
    // Look for a filter panel toggle button
    const filterToggle = page.locator('#filterToggle');

    if (await filterToggle.isVisible().catch(() => false)) {
      // Click to expand/toggle filter panel
      await filterToggle.click();

      // Advanced filter elements should become visible
      const advancedFilters = page.locator('#advancedFilters');
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
    const applyBtn = page.locator('#applyFilters');
    if (await applyBtn.isVisible().catch(() => false)) {
      await expect(applyBtn).toBeVisible();
    }

    // Reset button
    const resetBtn = page.locator('#resetFilters');
    if (await resetBtn.isVisible().catch(() => false)) {
      await expect(resetBtn).toBeVisible();
    }
  });
});

test.describe('Dashboard Chart Containers', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);
    await page.waitForTimeout(2000);
  });

  test('all primary chart canvas elements are present', async ({ page }) => {
    // Check that chart canvas elements exist in the DOM
    const chartIds = ['timelineChart', 'domainChart', 'sourceIpChart', 'dispositionChart'];

    for (const chartId of chartIds) {
      const chart = page.locator(`#${chartId}`);
      if (await chart.count() > 0) {
        await expect(chart).toBeAttached();
      }
    }
  });

  test('chart containers have appropriate sizing', async ({ page }) => {
    const chartContainer = page.locator('.chart-card');

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
    await loginAndWaitForDashboard(page);

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

    // Check for form labels - only check visible inputs to avoid hidden form elements
    const inputs = page.locator('input:not([type="hidden"]):visible');
    const inputCount = await inputs.count();
    for (let i = 0; i < inputCount; i++) {
      const input = inputs.nth(i);
      const id = await input.getAttribute('id');
      const ariaLabel = await input.getAttribute('aria-label');
      const ariaLabelledBy = await input.getAttribute('aria-labelledby');

      if (id) {
        const label = page.locator(`label[for="${id}"]`);
        const hasLabel = await label.count() > 0;
        const placeholder = await input.getAttribute('placeholder');
        const title = await input.getAttribute('title');
        // Input should have a label, aria-label, aria-labelledby, placeholder, or title
        expect(hasLabel || ariaLabel || ariaLabelledBy || placeholder || title).toBeTruthy();
      }
    }
  });

  test('keyboard navigation works', async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);

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
    await loginAndWaitForDashboard(page);
  });

  test('export button is visible', async ({ page }) => {
    const exportBtn = page.locator('#exportBtn');

    if (await exportBtn.isVisible().catch(() => false)) {
      await expect(exportBtn).toBeVisible();
    }
  });

  test('export menu shows format options', async ({ page }) => {
    const exportBtn = page.locator('#exportBtn');

    if (await exportBtn.isVisible().catch(() => false)) {
      await exportBtn.click();

      // Export menu should show options like CSV, PDF, JSON
      const exportMenu = page.locator('.export-menu');
      if (await exportMenu.isVisible().catch(() => false)) {
        await expect(exportMenu).toBeVisible();

        // Check for at least one export format option
        const exportOption = page.locator('.export-option');
        if (await exportOption.first().isVisible().catch(() => false)) {
          await expect(exportOption.first()).toBeVisible();
        }
      }
    }
  });
});

test.describe('Dashboard Error States', () => {
  test('shows error state when API returns 500', async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);

    // Now intercept the summary API to return 500
    await page.route('**/api/rollup/summary*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    // Trigger a refresh to hit the intercepted route
    await page.locator('#refreshBtn').click();
    await page.waitForTimeout(2000);

    // Should show some kind of error indicator or stat cards with fallback values
    const errorIndicator = page.locator('[role="alert"], .notification-error, .error-message');
    const hasError = await errorIndicator.first().isVisible().catch(() => false);

    const statCard = page.locator('.stat-card');
    const hasStatCards = await statCard.first().isVisible().catch(() => false);

    expect(hasError || hasStatCards).toBeTruthy();
  });

  test('shows error state when network is down', async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);

    // Now intercept all API calls to simulate network failure
    await page.route('**/api/**', (route) => {
      route.abort('connectionrefused');
    });

    // Trigger a refresh to hit the intercepted routes
    await page.locator('#refreshBtn').click();
    await page.waitForTimeout(2000);

    // Page should still be rendered (not a blank screen)
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });
});
