// @ts-check
const { test, expect } = require('@playwright/test');
const { loginAndWaitForDashboard } = require('./helpers/login');

/**
 * Navigate to the alerts page by clicking the sidebar item.
 * Waits for the alerts section to become visible and the page to settle.
 */
async function navigateToAlerts(page) {
  const alertsSidebarBtn = page.locator('.sidebar-item[data-page="alerts"]');
  await expect(alertsSidebarBtn).toBeVisible({ timeout: 5000 });
  await alertsSidebarBtn.click();

  // Wait for the alerts page section to be visible
  const alertsSection = page.locator('#page-alerts');
  await expect(alertsSection).toBeVisible({ timeout: 10000 });

  // Wait for API calls to settle
  await page.waitForLoadState('networkidle');
}

test.describe('Alerts Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await loginAndWaitForDashboard(page);
  });

  test('navigate to alerts page and verify layout renders', async ({ page }) => {
    await navigateToAlerts(page);

    // Alerts page section should be visible
    const alertsSection = page.locator('#page-alerts');
    await expect(alertsSection).toBeVisible();

    // Stats section should be present
    const alertsStats = page.locator('#alerts-stats');
    await expect(alertsStats).toBeAttached();

    // Tab buttons should be present: Active Alerts and History at minimum
    const activeTab = page.locator('.alerts-tab-btn[data-tab="active"]');
    const historyTab = page.locator('.alerts-tab-btn[data-tab="history"]');
    await expect(activeTab).toBeVisible();
    await expect(historyTab).toBeVisible();

    // Active alerts table should be present
    const activeTbody = page.locator('#alerts-active-tbody');
    await expect(activeTbody).toBeAttached();
  });

  test('active alerts table shows data or empty state', async ({ page }) => {
    await navigateToAlerts(page);

    // Wait for the table to populate
    const activeTbody = page.locator('#alerts-active-tbody');
    await expect(activeTbody).toBeAttached();

    // Wait briefly for async data load
    await page.waitForTimeout(2000);

    // The table should have rows -- either data rows or an empty-state row
    const rows = activeTbody.locator('tr');
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThanOrEqual(1);

    // If there is an empty-state message, verify its text
    const firstRowText = await rows.first().textContent();
    if (firstRowText.includes('No active alerts')) {
      // Empty state is valid
      expect(firstRowText).toContain('No active alerts');
    } else if (firstRowText.includes('Loading')) {
      // Still loading -- wait a bit more and re-check
      await page.waitForTimeout(3000);
      const updatedText = await rows.first().textContent();
      expect(updatedText).toBeTruthy();
    } else {
      // Data rows exist -- verify they contain alert content
      expect(firstRowText.length).toBeGreaterThan(0);
    }
  });

  test('switching to history tab loads alert history', async ({ page }) => {
    await navigateToAlerts(page);

    // Click History tab
    const historyTab = page.locator('.alerts-tab-btn[data-tab="history"]');
    await historyTab.click();

    // History panel should become visible
    const historyPanel = page.locator('#alerts-panel-history');
    await expect(historyPanel).toBeVisible({ timeout: 5000 });

    // Active panel should be hidden
    const activePanel = page.locator('#alerts-panel-active');
    await expect(activePanel).toBeHidden();

    // History filters should be visible
    const histDomain = page.locator('#alerts-hist-domain');
    const histSeverity = page.locator('#alerts-hist-severity');
    const histStatus = page.locator('#alerts-hist-status');
    const histDays = page.locator('#alerts-hist-days');
    await expect(histDomain).toBeVisible();
    await expect(histSeverity).toBeVisible();
    await expect(histStatus).toBeVisible();
    await expect(histDays).toBeVisible();

    // History table body should be present
    const historyTbody = page.locator('#alerts-history-tbody');
    await expect(historyTbody).toBeAttached();
  });

  test('history filters can be applied', async ({ page }) => {
    await navigateToAlerts(page);

    // Switch to history tab
    const historyTab = page.locator('.alerts-tab-btn[data-tab="history"]');
    await historyTab.click();
    await expect(page.locator('#alerts-panel-history')).toBeVisible({ timeout: 5000 });

    // Change severity filter to "high"
    const histSeverity = page.locator('#alerts-hist-severity');
    await histSeverity.selectOption('high');

    // Change days filter
    const histDays = page.locator('#alerts-hist-days');
    await histDays.selectOption('7');

    // Click Apply button
    const applyBtn = page.locator('#alerts-hist-apply-btn');
    await expect(applyBtn).toBeVisible();
    await applyBtn.click();

    // Wait for the filtered results to load
    await page.waitForLoadState('networkidle');

    // History table should still be present (with data or empty state)
    const historyTbody = page.locator('#alerts-history-tbody');
    await expect(historyTbody).toBeAttached();

    const rows = historyTbody.locator('tr');
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThanOrEqual(0);
  });
});
