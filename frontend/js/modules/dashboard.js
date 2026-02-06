/**
 * DMARC Dashboard - Dashboard Page Module
 * Contains init/load for the main dashboard view (stats, charts, reports table).
 * The actual rendering logic remains in app.js; this module orchestrates it.
 */
(function() {
    'use strict';

    const DashboardPage = {
        initialized: false,

        /**
         * Initialize the dashboard page.
         * Binds filter bar events and sets up dashboard-specific UI.
         */
        init() {
            if (this.initialized) return;
            this.initialized = true;
            // Dashboard event listeners are already set up in app.js setupEventListeners()
            // Start smart refresh on first dashboard init
            if (typeof startSmartRefresh === 'function') {
                startSmartRefresh();
            }
        },

        /**
         * Load/reload dashboard data.
         * Called on navigation to dashboard and on refresh.
         */
        load() {
            // Use the existing loadDashboard function from app.js
            if (typeof loadDashboard === 'function') {
                loadDashboard();
                // Also load comparison data and sparklines
                if (typeof loadComparisonData === 'function') {
                    loadComparisonData().then(function() {
                        if (typeof renderStatCardSparklines === 'function') {
                            renderStatCardSparklines();
                        }
                        if (typeof renderPeriodComparisons === 'function') {
                            renderPeriodComparisons();
                        }
                    });
                }
            }
        },

        /**
         * Cleanup when navigating away from dashboard.
         */
        destroy() {
            // Nothing to clean up - charts persist in DOM
        }
    };

    // Register with router
    window.DMARC = window.DMARC || {};
    window.DMARC.DashboardPage = DashboardPage;
})();
