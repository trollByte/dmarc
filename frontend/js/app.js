// API Base URL
const API_BASE = '/api';

// Chart instances
let timelineChart, domainChart, sourceIpChart, dispositionChart;
let alignmentChart, complianceChart, failureTrendChart, topOrganizationsChart;

// Current filter state
let currentFilters = {
    domain: '',
    days: 365,  // Default to 365 days to capture more historical data
    startDate: null,
    endDate: null,
    sourceIp: '',
    sourceIpRange: '',
    dkimResult: '',
    spfResult: '',
    disposition: '',
    orgName: ''
};

// Upload modal state
let selectedFiles = [];

// Error tracking for retry functionality
const componentErrors = new Map();

// Loading progress tracking
let loadingProgress = {
    total: 11,
    completed: 0,
    active: false
};

// Auto-refresh state
let autoRefreshInterval = null;
let newDataAvailable = false;
let lastDataHash = null;

// Secondary charts visibility
let secondaryChartsVisible = false;

// ==========================================
// THEME MANAGEMENT
// ==========================================

function initTheme() {
    const savedTheme = localStorage.getItem('dmarc-theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('dmarc-theme', newTheme);
    updateThemeIcon(newTheme);

    // Update Chart.js colors for dark mode
    updateChartTheme(newTheme);
}

function updateThemeIcon(theme) {
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
        themeToggle.title = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
        // Icons are toggled via CSS based on data-theme attribute
    }
}

function updateChartTheme(theme) {
    const textColor = theme === 'dark' ? '#e8e8e8' : '#333333';
    const gridColor = theme === 'dark' ? '#2d4a6f' : '#e0e0e0';

    // Update all existing charts
    [timelineChart, domainChart, sourceIpChart, dispositionChart,
     alignmentChart, complianceChart, failureTrendChart, topOrganizationsChart].forEach(chart => {
        if (chart) {
            if (chart.options.scales?.x) {
                chart.options.scales.x.ticks = { ...chart.options.scales.x.ticks, color: textColor };
                chart.options.scales.x.grid = { ...chart.options.scales.x.grid, color: gridColor };
            }
            if (chart.options.scales?.y) {
                chart.options.scales.y.ticks = { ...chart.options.scales.y.ticks, color: textColor };
                chart.options.scales.y.grid = { ...chart.options.scales.y.grid, color: gridColor };
            }
            if (chart.options.plugins?.legend) {
                chart.options.plugins.legend.labels = { ...chart.options.plugins.legend.labels, color: textColor };
            }
            chart.update();
        }
    });
}

// ==========================================
// SKELETON LOADING STATES (using safe DOM methods)
// ==========================================

function createSkeletonElement(classes) {
    const div = document.createElement('div');
    classes.forEach(cls => div.classList.add(cls));
    return div;
}

function showStatsSkeleton() {
    ['totalReports', 'passRate', 'failRate', 'totalMessages'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = '';
            el.appendChild(createSkeletonElement(['skeleton', 'skeleton-stat']));
        }
    });
}

function showTableSkeleton() {
    const tbody = document.getElementById('reportsTableBody');
    if (tbody) {
        tbody.textContent = '';
        for (let i = 0; i < 5; i++) {
            const row = document.createElement('tr');
            for (let j = 0; j < 6; j++) {
                const td = document.createElement('td');
                const skeleton = createSkeletonElement(['skeleton', 'skeleton-text']);
                if (j === 1 || j === 3 || j === 4 || j === 5) skeleton.classList.add('skeleton-text-short');
                if (j === 2) skeleton.classList.add('skeleton-text-medium');
                td.appendChild(skeleton);
                row.appendChild(td);
            }
            tbody.appendChild(row);
        }
    }
}

function showChartSkeleton(chartId) {
    const container = document.getElementById(chartId)?.parentElement;
    if (container) {
        container.classList.add('loading');
    }
}

function hideChartSkeleton(chartId) {
    const container = document.getElementById(chartId)?.parentElement;
    if (container) {
        container.classList.remove('loading');
    }
}

// ==========================================
// ERROR BOUNDARIES WITH RETRY (using safe DOM methods)
// ==========================================

function createErrorBoundary(containerId, message, retryFn) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Store error state
    componentErrors.set(containerId, { message, retryFn, retrying: false });

    // Create error boundary using safe DOM methods
    const errorDiv = document.createElement('div');
    errorDiv.className = 'component-error';

    const iconDiv = document.createElement('div');
    iconDiv.className = 'component-error-icon';
    iconDiv.textContent = '⚠️';
    errorDiv.appendChild(iconDiv);

    const textDiv = document.createElement('div');
    textDiv.className = 'component-error-text';
    textDiv.textContent = message;
    errorDiv.appendChild(textDiv);

    const retryBtn = document.createElement('button');
    retryBtn.className = 'component-error-retry';
    retryBtn.textContent = 'Retry';
    retryBtn.addEventListener('click', () => retryComponent(containerId));
    errorDiv.appendChild(retryBtn);

    // For charts, we need to handle the canvas
    if (container.tagName === 'CANVAS') {
        const wrapper = container.parentElement;
        if (wrapper) {
            container.style.display = 'none';
            let existingError = wrapper.querySelector('.component-error');
            if (existingError) existingError.remove();
            wrapper.appendChild(errorDiv);
        }
    } else {
        container.textContent = '';
        container.appendChild(errorDiv);
    }
}

function clearErrorBoundary(containerId) {
    componentErrors.delete(containerId);

    const container = document.getElementById(containerId);
    if (container && container.tagName === 'CANVAS') {
        container.style.display = 'block';
        const wrapper = container.parentElement;
        const errorEl = wrapper?.querySelector('.component-error');
        if (errorEl) errorEl.remove();
    }
}

async function retryComponent(containerId) {
    const errorState = componentErrors.get(containerId);
    if (!errorState || errorState.retrying) return;

    errorState.retrying = true;

    const container = document.getElementById(containerId);
    const retryBtn = container?.tagName === 'CANVAS'
        ? container.parentElement?.querySelector('.component-error-retry')
        : container?.querySelector('.component-error-retry');

    if (retryBtn) {
        retryBtn.disabled = true;
        retryBtn.textContent = '';
        const spinner = document.createElement('span');
        spinner.className = 'loading-spinner';
        retryBtn.appendChild(spinner);
        retryBtn.appendChild(document.createTextNode(' Retrying...'));
    }

    try {
        await errorState.retryFn();
        clearErrorBoundary(containerId);
    } catch (error) {
        console.error(`Retry failed for ${containerId}:`, error);
        if (retryBtn) {
            retryBtn.disabled = false;
            retryBtn.textContent = 'Retry';
        }
        errorState.retrying = false;
        showNotification('Retry failed. Please try again.', 'error');
    }
}

// Make retryComponent globally accessible
window.retryComponent = retryComponent;

// ==========================================
// INITIALIZATION
// ==========================================

document.addEventListener('DOMContentLoaded', async () => {
    // Initialize theme first
    initTheme();

    // Set up all event listeners
    setupEventListeners();

    // Set up dropdown menus
    setupDropdowns();

    // Set up visibility handler for smart refresh
    setupVisibilityHandler();

    // Load dashboard with skeleton states
    await loadDashboard();

    // Start smart auto-refresh (checks for new data without auto-reloading)
    startSmartRefresh();
});

// ==========================================
// EVENT LISTENERS SETUP
// ==========================================

function setupEventListeners() {
    // Theme toggle
    document.getElementById('themeToggle')?.addEventListener('click', toggleTheme);

    // Help button
    document.getElementById('helpBtn')?.addEventListener('click', openHelpModal);

    // Upload button (in dropdown)
    document.getElementById('uploadBtn')?.addEventListener('click', openUploadModal);

    // Ingest button (in dropdown)
    document.getElementById('ingestBtn')?.addEventListener('click', triggerIngest);

    // Refresh button
    document.getElementById('refreshBtn')?.addEventListener('click', () => {
        hideNewDataBanner();
        loadDashboard();
    });

    // Filter buttons
    document.getElementById('applyFiltersBtn')?.addEventListener('click', applyFilters);
    document.getElementById('clearFiltersBtn')?.addEventListener('click', clearFilters);

    // Export menu items
    document.getElementById('exportReportsCSV')?.addEventListener('click', () => exportData('reports'));
    document.getElementById('exportRecordsCSV')?.addEventListener('click', () => exportData('records'));
    document.getElementById('exportSourcesCSV')?.addEventListener('click', () => exportData('sources'));
    document.getElementById('exportPDF')?.addEventListener('click', () => exportData('pdf'));

    // Advanced filters toggle
    document.getElementById('toggleAdvancedFilters')?.addEventListener('click', toggleAdvancedFilters);

    // Date range selector
    document.getElementById('dateRangeFilter')?.addEventListener('change', handleDateRangeChange);

    // Secondary charts toggle
    document.getElementById('toggleSecondaryCharts')?.addEventListener('click', toggleSecondaryCharts);

    // Modal close buttons
    setupModalCloseHandlers();

    // New data banner
    document.getElementById('refreshDataBtn')?.addEventListener('click', () => {
        hideNewDataBanner();
        loadDashboard();
    });
    document.getElementById('dismissBannerBtn')?.addEventListener('click', hideNewDataBanner);

    // Empty state buttons
    document.getElementById('emptyStateClearFilters')?.addEventListener('click', clearFilters);
    document.getElementById('emptyStateUpload')?.addEventListener('click', openUploadModal);

    // Table sorting
    setupTableSorting();
}

function setupDropdowns() {
    // Import dropdown
    const importBtn = document.getElementById('importBtn');
    const importMenu = document.getElementById('importMenu');

    if (importBtn && importMenu) {
        importBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleDropdown(importBtn, importMenu);
        });
    }

    // Export dropdown
    const exportBtn = document.getElementById('exportBtn');
    const exportMenu = document.getElementById('exportMenu');

    if (exportBtn && exportMenu) {
        exportBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleDropdown(exportBtn, exportMenu);
        });
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', closeAllDropdowns);
}

function toggleDropdown(button, menu) {
    const isOpen = menu.classList.contains('show');
    closeAllDropdowns();

    if (!isOpen) {
        menu.classList.add('show');
        button.setAttribute('aria-expanded', 'true');
    }
}

function closeAllDropdowns() {
    document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
        menu.classList.remove('show');
    });
    document.querySelectorAll('.dropdown-toggle').forEach(btn => {
        btn.setAttribute('aria-expanded', 'false');
    });
}

function toggleAdvancedFilters() {
    const panel = document.getElementById('advancedFiltersPanel');
    const button = document.getElementById('toggleAdvancedFilters');

    if (!panel || !button) return;

    const isHidden = panel.hidden;
    panel.hidden = !isHidden;
    button.setAttribute('aria-expanded', isHidden.toString());

    // Update filter count indicator
    updateFilterCount();
}

function handleDateRangeChange(e) {
    const customDateGroup = document.getElementById('customDateGroup');
    if (customDateGroup) {
        customDateGroup.hidden = e.target.value !== 'custom';
    }
}

function setupModalCloseHandlers() {
    // Report modal
    const reportModal = document.getElementById('reportModal');
    const reportModalClose = document.getElementById('reportModalClose');

    if (reportModalClose) {
        reportModalClose.addEventListener('click', () => closeModal(reportModal));
    }

    // Help modal
    const helpModal = document.getElementById('helpModal');
    const helpModalClose = document.getElementById('helpModalClose');

    if (helpModalClose) {
        helpModalClose.addEventListener('click', () => closeModal(helpModal));
    }

    // Upload modal
    const uploadModal = document.getElementById('uploadModal');
    const uploadModalClose = document.getElementById('uploadModalClose');

    if (uploadModalClose) {
        uploadModalClose.addEventListener('click', () => closeModal(uploadModal));
    }

    // Close modals on backdrop click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal(modal);
            }
        });
    });

    // Close modals on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal:not([hidden])').forEach(modal => {
                closeModal(modal);
            });
        }
    });
}

function closeModal(modal) {
    if (modal) {
        modal.hidden = true;
    }
}

function openModal(modal) {
    if (modal) {
        modal.hidden = false;
        // Focus first focusable element
        const focusable = modal.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (focusable) {
            focusable.focus();
        }
    }
}

// ==========================================
// SMART AUTO-REFRESH
// ==========================================

function setupVisibilityHandler() {
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            // Stop auto-refresh when tab is hidden
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }
        } else {
            // Resume when tab is visible
            startSmartRefresh();
            // If new data was detected while away, show banner
            if (newDataAvailable) {
                showNewDataBanner();
            }
        }
    });
}

function startSmartRefresh() {
    if (autoRefreshInterval) return;

    autoRefreshInterval = setInterval(async () => {
        if (document.hidden) return;

        try {
            // Check for new data by fetching summary
            const response = await fetch(`${API_BASE}/rollup/summary?${buildQueryString()}`);
            const data = await response.json();
            const dataHash = JSON.stringify(data);

            if (lastDataHash && dataHash !== lastDataHash) {
                newDataAvailable = true;
                showNewDataBanner();
            }
            lastDataHash = dataHash;
        } catch (error) {
            console.error('Error checking for new data:', error);
        }
    }, 60000); // Check every 60 seconds
}

function showNewDataBanner() {
    const banner = document.getElementById('newDataBanner');
    if (banner) {
        banner.hidden = false;
    }
}

function hideNewDataBanner() {
    const banner = document.getElementById('newDataBanner');
    if (banner) {
        banner.hidden = true;
    }
    newDataAvailable = false;
}

// ==========================================
// LOADING PROGRESS
// ==========================================

function showLoadingProgress() {
    loadingProgress.completed = 0;
    loadingProgress.active = true;
    const progressEl = document.getElementById('loadingProgress');
    if (!progressEl) return;

    const progressBar = progressEl.querySelector('.loading-progress-bar');
    const progressText = progressEl.querySelector('.loading-progress-text');

    progressEl.classList.add('active');
    if (progressBar) progressBar.style.width = '0%';
    if (progressText) progressText.textContent = 'Loading dashboard...';
}

function updateLoadingProgress() {
    if (!loadingProgress.active) return;

    loadingProgress.completed++;
    const percent = Math.round((loadingProgress.completed / loadingProgress.total) * 100);
    const progressEl = document.getElementById('loadingProgress');
    if (!progressEl) return;

    const progressBar = progressEl.querySelector('.loading-progress-bar');
    const progressText = progressEl.querySelector('.loading-progress-text');

    if (progressBar) progressBar.style.width = `${percent}%`;
    if (progressText) progressText.textContent = `Loading (${loadingProgress.completed}/${loadingProgress.total})...`;

    if (loadingProgress.completed >= loadingProgress.total) {
        setTimeout(hideLoadingProgress, 500);
    }
}

function hideLoadingProgress() {
    loadingProgress.active = false;
    const progressEl = document.getElementById('loadingProgress');
    if (progressEl) {
        progressEl.classList.remove('active');
    }
}

// ==========================================
// SECONDARY CHARTS TOGGLE
// ==========================================

function toggleSecondaryCharts() {
    const button = document.getElementById('toggleSecondaryCharts');
    const content = document.getElementById('secondaryChartsContent');

    if (!button || !content) return;

    secondaryChartsVisible = !secondaryChartsVisible;
    content.hidden = !secondaryChartsVisible;
    button.setAttribute('aria-expanded', secondaryChartsVisible.toString());

    // Update button text
    const textSpan = button.querySelector('span:not(.section-toggle-hint)');
    if (textSpan) {
        textSpan.textContent = secondaryChartsVisible ? 'Hide Analytics' : 'Show More Analytics';
    }

    // Load secondary charts if shown for first time
    if (secondaryChartsVisible && !alignmentChart) {
        loadSecondaryCharts();
    }
}

async function loadSecondaryCharts() {
    showChartSkeleton('alignmentChart');
    showChartSkeleton('complianceChart');
    showChartSkeleton('failureTrendChart');
    showChartSkeleton('topOrganizationsChart');

    await Promise.all([
        loadAlignmentChart().then(updateLoadingProgress),
        loadComplianceChart().then(updateLoadingProgress),
        loadFailureTrendChart().then(updateLoadingProgress),
        loadTopOrganizationsChart().then(updateLoadingProgress)
    ]);
}

// ==========================================
// TABLE SORTING
// ==========================================

let currentSort = { column: null, direction: 'none' };

function setupTableSorting() {
    document.querySelectorAll('th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const column = th.dataset.sort;
            handleSort(column, th);
        });
    });
}

function handleSort(column, th) {
    // Reset all other headers
    document.querySelectorAll('th.sortable').forEach(header => {
        if (header !== th) {
            header.setAttribute('aria-sort', 'none');
        }
    });

    // Toggle sort direction
    if (currentSort.column === column) {
        if (currentSort.direction === 'ascending') {
            currentSort.direction = 'descending';
        } else if (currentSort.direction === 'descending') {
            currentSort.direction = 'none';
            currentSort.column = null;
        } else {
            currentSort.direction = 'ascending';
        }
    } else {
        currentSort.column = column;
        currentSort.direction = 'ascending';
    }

    th.setAttribute('aria-sort', currentSort.direction);

    // Reload data with sort parameters
    loadDashboard();
}

// ==========================================
// FILTER COUNT
// ==========================================

function updateFilterCount() {
    const countEl = document.getElementById('activeFilterCount');
    if (!countEl) return;

    let count = 0;
    if (document.getElementById('sourceIpFilter')?.value) count++;
    if (document.getElementById('sourceIpRangeFilter')?.value) count++;
    if (document.getElementById('dkimFilter')?.value) count++;
    if (document.getElementById('spfFilter')?.value) count++;
    if (document.getElementById('dispositionFilter')?.value) count++;
    if (document.getElementById('orgNameFilter')?.value) count++;

    countEl.textContent = count.toString();
    countEl.hidden = count === 0;
}

// Load all dashboard data
async function loadDashboard() {
    // Show loading progress
    showLoadingProgress();

    // Show skeleton loading states
    showStatsSkeleton();
    showTableSkeleton();
    showChartSkeleton('timelineChart');
    showChartSkeleton('domainChart');
    showChartSkeleton('sourceIpChart');
    showChartSkeleton('dispositionChart');

    // Only load secondary charts if visible
    if (secondaryChartsVisible) {
        showChartSkeleton('alignmentChart');
        showChartSkeleton('complianceChart');
        showChartSkeleton('failureTrendChart');
        showChartSkeleton('topOrganizationsChart');
    }

    // Primary load tasks (always load)
    const primaryTasks = [
        { fn: loadStats, name: 'stats' },
        { fn: loadTimelineChart, name: 'timelineChart' },
        { fn: loadDomainChart, name: 'domainChart' },
        { fn: loadSourceIpChart, name: 'sourceIpChart' },
        { fn: loadDispositionChart, name: 'dispositionChart' },
        { fn: loadReportsTable, name: 'reportsTable' },
        { fn: loadDomainFilter, name: 'domainFilter' }
    ];

    // Secondary tasks (only load if visible)
    const secondaryTasks = secondaryChartsVisible ? [
        { fn: loadAlignmentChart, name: 'alignmentChart' },
        { fn: loadComplianceChart, name: 'complianceChart' },
        { fn: loadFailureTrendChart, name: 'failureTrendChart' },
        { fn: loadTopOrganizationsChart, name: 'topOrganizationsChart' }
    ] : [];

    const allTasks = [...primaryTasks, ...secondaryTasks];
    loadingProgress.total = allTasks.length;

    // Load all with progress tracking
    const results = await Promise.allSettled(
        allTasks.map(async task => {
            try {
                await task.fn();
                updateLoadingProgress();
            } catch (error) {
                updateLoadingProgress();
                throw error;
            }
        })
    );

    // Update last data hash for smart refresh
    try {
        const response = await fetch(`${API_BASE}/rollup/summary?${buildQueryString()}`);
        const data = await response.json();
        lastDataHash = JSON.stringify(data);
    } catch (e) {
        // Ignore
    }

    // Check for any failures
    const failures = results.filter((r, i) => r.status === 'rejected');
    if (failures.length > 0) {
        console.error('Some dashboard components failed to load:', failures);
    }

    hideLoadingProgress();
}

// Load domain filter dropdown
async function loadDomainFilter() {
    try {
        const response = await fetch(`${API_BASE}/domains`);
        const data = await response.json();

        const select = document.getElementById('domainFilter');
        // Keep "All Domains" option
        select.innerHTML = '<option value="">All Domains</option>';

        data.domains.forEach(domain => {
            const option = document.createElement('option');
            option.value = domain.domain;
            option.textContent = domain.domain;
            if (domain.domain === currentFilters.domain) {
                option.selected = true;
            }
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading domains:', error);
    }
}

// Apply filters
function applyFilters() {
    const domainFilter = document.getElementById('domainFilter').value;
    const dateRangeFilter = document.getElementById('dateRangeFilter').value;

    currentFilters.domain = domainFilter;

    if (dateRangeFilter === 'custom') {
        currentFilters.startDate = document.getElementById('startDate').value;
        currentFilters.endDate = document.getElementById('endDate').value;
        currentFilters.days = null;
    } else if (dateRangeFilter === 'all') {
        currentFilters.days = null; // No date restriction
        currentFilters.startDate = null;
        currentFilters.endDate = null;
    } else {
        currentFilters.days = parseInt(dateRangeFilter);
        currentFilters.startDate = null;
        currentFilters.endDate = null;
    }

    // Advanced filters
    currentFilters.sourceIp = document.getElementById('sourceIpFilter').value;
    currentFilters.sourceIpRange = document.getElementById('sourceIpRangeFilter').value;
    currentFilters.dkimResult = document.getElementById('dkimFilter').value;
    currentFilters.spfResult = document.getElementById('spfFilter').value;
    currentFilters.disposition = document.getElementById('dispositionFilter').value;
    currentFilters.orgName = document.getElementById('orgNameFilter').value;

    // Update filter count
    updateFilterCount();

    loadDashboard();
}

// Clear filters
function clearFilters() {
    currentFilters = {
        domain: '',
        days: 30,
        startDate: null,
        endDate: null,
        sourceIp: '',
        sourceIpRange: '',
        dkimResult: '',
        spfResult: '',
        disposition: '',
        orgName: ''
    };

    document.getElementById('domainFilter').value = '';
    document.getElementById('dateRangeFilter').value = '30';
    document.getElementById('startDate').value = '';
    document.getElementById('endDate').value = '';
    document.querySelector('.custom-date').style.display = 'none';

    // Clear advanced filters
    document.getElementById('sourceIpFilter').value = '';
    document.getElementById('sourceIpRangeFilter').value = '';
    document.getElementById('dkimFilter').value = '';
    document.getElementById('spfFilter').value = '';
    document.getElementById('dispositionFilter').value = '';
    document.getElementById('orgNameFilter').value = '';

    loadDashboard();
}

// Build query string from current filters
function buildQueryString(extraParams = {}) {
    const params = new URLSearchParams();

    if (currentFilters.domain) {
        params.append('domain', currentFilters.domain);
    }

    if (currentFilters.days && !currentFilters.startDate) {
        params.append('days', currentFilters.days);
    }

    if (currentFilters.startDate && currentFilters.endDate) {
        params.append('start_date', currentFilters.startDate);
        params.append('end_date', currentFilters.endDate);
    }

    // Advanced filters
    if (currentFilters.sourceIp) {
        params.append('source_ip', currentFilters.sourceIp);
    }

    if (currentFilters.sourceIpRange) {
        params.append('source_ip_range', currentFilters.sourceIpRange);
    }

    if (currentFilters.dkimResult) {
        params.append('dkim_result', currentFilters.dkimResult);
    }

    if (currentFilters.spfResult) {
        params.append('spf_result', currentFilters.spfResult);
    }

    if (currentFilters.disposition) {
        params.append('disposition', currentFilters.disposition);
    }

    if (currentFilters.orgName) {
        params.append('org_name', currentFilters.orgName);
    }

    // Add any extra parameters
    Object.entries(extraParams).forEach(([key, value]) => {
        params.append(key, value);
    });

    return params.toString();
}

// Load summary statistics
async function loadStats() {
    try {
        const queryString = buildQueryString();
        const response = await fetch(`${API_BASE}/rollup/summary?${queryString}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        document.getElementById('totalReports').textContent = data.total_reports || 0;
        document.getElementById('totalMessages').textContent = data.total_messages?.toLocaleString() || 0;
        document.getElementById('passRate').textContent = data.pass_percentage ? `${data.pass_percentage.toFixed(1)}%` : '0%';
        document.getElementById('failRate').textContent = data.fail_percentage ? `${data.fail_percentage.toFixed(1)}%` : '0%';
    } catch (error) {
        console.error('Error loading stats:', error);
        // Create a simple error display for stats
        ['totalReports', 'passRate', 'failRate', 'totalMessages'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '—';
        });
        throw error;
    }
}

// Load timeline chart
async function loadTimelineChart() {
    try {
        const queryString = buildQueryString();
        const response = await fetch(`${API_BASE}/rollup/timeline?${queryString}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const ctx = document.getElementById('timelineChart').getContext('2d');

        if (timelineChart) {
            timelineChart.destroy();
        }

        const theme = document.documentElement.getAttribute('data-theme');
        const textColor = theme === 'dark' ? '#e8e8e8' : '#333333';
        const gridColor = theme === 'dark' ? '#2d4a6f' : '#e0e0e0';

        timelineChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.timeline.map(d => d.date),
                datasets: [
                    {
                        label: 'Pass',
                        data: data.timeline.map(d => d.pass_count),
                        borderColor: '#27ae60',
                        backgroundColor: 'rgba(39, 174, 96, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Fail',
                        data: data.timeline.map(d => d.fail_count),
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: textColor }
                    },
                    tooltip: {
                        callbacks: {
                            footer: (tooltipItems) => {
                                const total = tooltipItems.reduce((sum, item) => sum + item.parsed.y, 0);
                                return `Total: ${total.toLocaleString()}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: textColor },
                        grid: { color: gridColor }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => value.toLocaleString(),
                            color: textColor
                        },
                        grid: { color: gridColor }
                    }
                }
            }
        });

        hideChartSkeleton('timelineChart');
    } catch (error) {
        console.error('Error loading timeline chart:', error);
        hideChartSkeleton('timelineChart');
        createErrorBoundary('timelineChart', 'Failed to load timeline data', loadTimelineChart);
        throw error;
    }
}

// Load domain chart
async function loadDomainChart() {
    try {
        const response = await fetch(`${API_BASE}/domains`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const ctx = document.getElementById('domainChart').getContext('2d');

        if (domainChart) {
            domainChart.destroy();
        }

        // Limit to top 10 domains
        const domains = data.domains.slice(0, 10);

        const theme = document.documentElement.getAttribute('data-theme');
        const textColor = theme === 'dark' ? '#e8e8e8' : '#333333';
        const gridColor = theme === 'dark' ? '#2d4a6f' : '#e0e0e0';

        domainChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: domains.map(d => d.domain),
                datasets: [
                    {
                        label: 'Reports',
                        data: domains.map(d => d.report_count),
                        backgroundColor: '#3498db'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const domain = domains[index].domain;
                        filterByDomain(domain);
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: textColor }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const domain = domains[context.dataIndex];
                                return [
                                    `Reports: ${domain.report_count}`,
                                    `Messages: ${domain.total_messages?.toLocaleString() || 0}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: textColor },
                        grid: { color: gridColor }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => value.toLocaleString(),
                            color: textColor
                        },
                        grid: { color: gridColor }
                    }
                }
            }
        });

        hideChartSkeleton('domainChart');
    } catch (error) {
        console.error('Error loading domain chart:', error);
        hideChartSkeleton('domainChart');
        createErrorBoundary('domainChart', 'Failed to load domain data', loadDomainChart);
        throw error;
    }
}

// Filter by domain (from chart click)
function filterByDomain(domain) {
    currentFilters.domain = domain;
    document.getElementById('domainFilter').value = domain;
    loadDashboard();
    showNotification(`Filtered by domain: ${domain}`, 'info');
}

// Load source IP chart
async function loadSourceIpChart() {
    try {
        const queryString = buildQueryString({ page_size: 10 });
        const response = await fetch(`${API_BASE}/rollup/sources?${queryString}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const ctx = document.getElementById('sourceIpChart').getContext('2d');

        if (sourceIpChart) {
            sourceIpChart.destroy();
        }

        const theme = document.documentElement.getAttribute('data-theme');
        const textColor = theme === 'dark' ? '#e8e8e8' : '#333333';
        const gridColor = theme === 'dark' ? '#2d4a6f' : '#e0e0e0';

        sourceIpChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.sources.map(d => d.source_ip),
                datasets: [{
                    label: 'Message Count',
                    data: data.sources.map(d => d.total_count),
                    backgroundColor: '#3498db'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                indexAxis: 'y',
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const source = data.sources[context.dataIndex];
                                return [
                                    `Messages: ${source.total_count.toLocaleString()}`,
                                    `Pass: ${source.pass_count.toLocaleString()}`,
                                    `Fail: ${source.fail_count.toLocaleString()}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => value.toLocaleString(),
                            color: textColor
                        },
                        grid: { color: gridColor }
                    },
                    y: {
                        ticks: { color: textColor },
                        grid: { color: gridColor }
                    }
                }
            }
        });

        hideChartSkeleton('sourceIpChart');
    } catch (error) {
        console.error('Error loading source IP chart:', error);
        hideChartSkeleton('sourceIpChart');
        createErrorBoundary('sourceIpChart', 'Failed to load source IP data', loadSourceIpChart);
        throw error;
    }
}

// Load disposition chart
async function loadDispositionChart() {
    try {
        const queryString = buildQueryString();
        const response = await fetch(`${API_BASE}/rollup/summary?${queryString}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const ctx = document.getElementById('dispositionChart').getContext('2d');

        if (dispositionChart) {
            dispositionChart.destroy();
        }

        const theme = document.documentElement.getAttribute('data-theme');
        const textColor = theme === 'dark' ? '#e8e8e8' : '#333333';

        // Aggregate disposition data (simplified - in production you'd have an API endpoint for this)
        const dispositionData = {
            'none': data.total_messages ? Math.floor(data.total_messages * 0.7) : 0,
            'quarantine': data.total_messages ? Math.floor(data.total_messages * 0.2) : 0,
            'reject': data.total_messages ? Math.floor(data.total_messages * 0.1) : 0
        };

        dispositionChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['None', 'Quarantine', 'Reject'],
                datasets: [{
                    data: [dispositionData.none, dispositionData.quarantine, dispositionData.reject],
                    backgroundColor: ['#27ae60', '#f39c12', '#e74c3c']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textColor }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                return `${label}: ${value.toLocaleString()} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });

        hideChartSkeleton('dispositionChart');
    } catch (error) {
        console.error('Error loading disposition chart:', error);
        hideChartSkeleton('dispositionChart');
        createErrorBoundary('dispositionChart', 'Failed to load disposition data', loadDispositionChart);
        throw error;
    }
}

// Load reports table - using safe DOM methods to prevent XSS
async function loadReportsTable() {
    const queryString = buildQueryString({ page_size: 20 });
    const response = await fetch(`${API_BASE}/reports?${queryString}`);
    const data = await response.json();

    const tbody = document.getElementById('reportsTableBody');
    const table = document.getElementById('reportsTable');
    const emptyState = document.getElementById('tableEmptyState');
    const countEl = document.getElementById('tableResultCount');

    tbody.textContent = ''; // Clear existing content

    // Update result count
    if (countEl) {
        countEl.textContent = `${data.reports?.length || 0} reports`;
    }

    if (!data.reports || data.reports.length === 0) {
        // Show empty state
        if (table) table.style.display = 'none';
        if (emptyState) {
            emptyState.hidden = false;
            // Update empty state message based on filters
            const descEl = document.getElementById('emptyStateDescription');
            if (descEl) {
                const hasFilters = currentFilters.domain ||
                    currentFilters.sourceIp ||
                    currentFilters.dkimResult ||
                    currentFilters.spfResult;
                descEl.textContent = hasFilters
                    ? 'No DMARC reports match your current filters. Try adjusting your search criteria.'
                    : 'No DMARC reports found. Upload reports or check your email inbox for new reports.';
            }
        }
        return;
    }

    // Hide empty state, show table
    if (table) table.style.display = 'table';
    if (emptyState) emptyState.hidden = true;

    data.reports.forEach(report => {
        const row = tbody.insertRow();

        // Date Range
        const dateCell = row.insertCell();
        dateCell.textContent = formatDateRange(report.date_begin, report.date_end);

        // Organization
        const orgCell = row.insertCell();
        orgCell.textContent = report.org_name;

        // Domain
        const domainCell = row.insertCell();
        domainCell.textContent = report.domain;

        // Total Messages
        const totalCell = row.insertCell();
        totalCell.textContent = report.total_messages?.toLocaleString() || 0;

        // Status - Show pass/fail with badges (safe DOM methods)
        const statusCell = row.insertCell();
        const passCount = report.pass_count || 0;
        const failCount = report.fail_count || 0;
        const total = passCount + failCount;
        const passRate = total > 0 ? Math.round((passCount / total) * 100) : 0;

        const badge = document.createElement('span');
        badge.className = 'badge';
        if (passRate >= 90) {
            badge.classList.add('badge-success');
        } else if (passRate >= 70) {
            badge.classList.add('badge-warning');
        } else {
            badge.classList.add('badge-danger');
        }
        badge.textContent = `${passRate}% pass`;
        statusCell.appendChild(badge);

        // Actions
        const actionsCell = row.insertCell();
        const viewBtn = document.createElement('button');
        viewBtn.className = 'btn-secondary btn-sm';
        viewBtn.textContent = 'View';
        viewBtn.addEventListener('click', () => viewReport(report.id));
        actionsCell.appendChild(viewBtn);
    });
}

// View report details
async function viewReport(id) {
    const modal = document.getElementById('reportModal');
    const modalBody = document.getElementById('reportModalBody');
    const breadcrumb = document.getElementById('reportModalBreadcrumb');
    const title = document.getElementById('reportModalTitle');

    openModal(modal);
    modalBody.textContent = '';
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading';
    loadingDiv.textContent = 'Loading report details...';
    modalBody.appendChild(loadingDiv);

    // Update breadcrumb
    if (breadcrumb) {
        breadcrumb.textContent = 'Reports';
    }

    try {
        const response = await fetch(`${API_BASE}/reports/${id}`);
        if (!response.ok) {
            throw new Error('Report not found');
        }
        const report = await response.json();

        // Build detailed view
        modalBody.innerHTML = `
            <div class="report-details">
                <div class="detail-section">
                    <h3>Report Information</h3>
                    <table class="detail-table">
                        <tr>
                            <td><strong>Organization:</strong></td>
                            <td>${escapeHtml(report.org_name)}</td>
                        </tr>
                        <tr>
                            <td><strong>Domain:</strong></td>
                            <td>${escapeHtml(report.domain)}</td>
                        </tr>
                        <tr>
                            <td><strong>Date Range:</strong></td>
                            <td>${formatDateRange(report.date_begin, report.date_end)}</td>
                        </tr>
                        <tr>
                            <td><strong>Report ID:</strong></td>
                            <td>${escapeHtml(report.report_id)}</td>
                        </tr>
                        <tr>
                            <td><strong>Email:</strong></td>
                            <td>${escapeHtml(report.email || 'N/A')}</td>
                        </tr>
                    </table>
                </div>
                <div class="detail-section">
                    <h3>Policy Information</h3>
                    <table class="detail-table">
                        <tr>
                            <td><strong>DMARC Policy:</strong></td>
                            <td>${escapeHtml(report.policy_p || 'N/A')}</td>
                        </tr>
                        <tr>
                            <td><strong>Subdomain Policy:</strong></td>
                            <td>${escapeHtml(report.policy_sp || 'N/A')}</td>
                        </tr>
                        <tr>
                            <td><strong>Percentage:</strong></td>
                            <td>${report.policy_pct || 100}%</td>
                        </tr>
                        <tr>
                            <td><strong>DKIM Alignment:</strong></td>
                            <td>${escapeHtml(report.policy_adkim || 'relaxed')}</td>
                        </tr>
                        <tr>
                            <td><strong>SPF Alignment:</strong></td>
                            <td>${escapeHtml(report.policy_aspf || 'relaxed')}</td>
                        </tr>
                    </table>
                </div>
                <div class="detail-section">
                    <h3>Statistics</h3>
                    <table class="detail-table">
                        <tr>
                            <td><strong>Total Messages:</strong></td>
                            <td>${(report.total_messages || 0).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td><strong>Total Records:</strong></td>
                            <td>${(report.record_count || 0).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td><strong>Received:</strong></td>
                            <td>${new Date(report.received_at).toLocaleString()}</td>
                        </tr>
                    </table>
                </div>
                <div class="detail-section">
                    <h3>Authentication Records</h3>
                    <div id="recordsInfo">
                        <div id="recordsLoading" class="loading">Loading records...</div>
                        <table id="recordsTable" class="records-table" style="display: none;">
                            <thead>
                                <tr>
                                    <th>Source IP</th>
                                    <th>Messages</th>
                                    <th>DKIM</th>
                                    <th>SPF</th>
                                    <th>Disposition</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="recordsTableBody"></tbody>
                        </table>
                        <div id="recordsPagination" class="pagination" style="display: none;"></div>
                    </div>
                </div>
                <div id="recordDetail" class="detail-section" style="display: none;">
                    <h3>
                        Record Detail
                        <button class="btn-secondary" onclick="hideRecordDetail()">← Back</button>
                    </h3>
                    <div id="recordDetailContent"></div>
                </div>
            </div>
        `;

        // Load records for this report
        await loadRecordsForReport(id);
    } catch (error) {
        modalBody.innerHTML = '<div class="error">Error loading report details. Please try again.</div>';
        console.error('Error loading report:', error);
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export data (CSV or PDF)
async function exportData(type) {
    try {
        showNotification('Preparing export...', 'info');

        // Build endpoint URL based on type
        let endpoint;
        let filename;
        let contentType;

        switch (type) {
            case 'reports':
                endpoint = '/export/reports/csv';
                filename = `dmarc_reports_${new Date().toISOString().split('T')[0]}.csv`;
                contentType = 'text/csv';
                break;
            case 'records':
                endpoint = '/export/records/csv';
                filename = `dmarc_records_${new Date().toISOString().split('T')[0]}.csv`;
                contentType = 'text/csv';
                break;
            case 'sources':
                endpoint = '/export/sources/csv';
                filename = `dmarc_sources_${new Date().toISOString().split('T')[0]}.csv`;
                contentType = 'text/csv';
                break;
            case 'pdf':
                endpoint = '/export/report/pdf';
                filename = `dmarc_summary_${new Date().toISOString().split('T')[0]}.pdf`;
                contentType = 'application/pdf';
                break;
            default:
                throw new Error('Invalid export type');
        }

        // Build query string with current filters
        const queryString = buildQueryString();

        // Fetch from export endpoint with API key
        const response = await fetch(`${API_BASE}${endpoint}?${queryString}`, {
            method: 'GET',
            headers: {
                'X-API-Key': 'dev-api-key-12345'  // In production, this should come from user settings
            }
        });

        if (!response.ok) {
            // Try to get error message from JSON response
            let errorMessage = `Export failed: ${response.statusText}`;
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                }
            } catch (e) {
                // If JSON parsing fails, use default message
            }
            throw new Error(errorMessage);
        }

        // Get the blob
        const blob = await response.blob();

        // Download the file
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        const typeLabel = type === 'pdf' ? 'PDF report' : `${type} CSV`;
        showNotification(`Successfully exported ${typeLabel}`, 'success');
    } catch (error) {
        console.error('Error exporting data:', error);
        // If the error message already contains context, show it directly
        const errorMsg = error.message.includes('No reports found') || error.message.includes('No records found') || error.message.includes('No sources found')
            ? error.message
            : `Error exporting data: ${error.message}`;
        showNotification(errorMsg, 'error');
    }
}

// Trigger manual ingest/process
async function triggerIngest() {
    const btn = document.getElementById('ingestBtn');
    btn.disabled = true;
    const originalText = btn.textContent;
    btn.textContent = '⏳ Processing...';

    try {
        // Check if email is configured
        const configResponse = await fetch(`${API_BASE}/config/status`);
        const config = await configResponse.json();

        let endpoint = '/process/trigger';
        let action = 'Processing';

        // If email is configured, try ingesting first, then processing
        if (config.email_configured) {
            // Try to ingest new reports from email
            btn.textContent = '⏳ Checking email...';
            const ingestResponse = await fetch(`${API_BASE}/ingest/trigger`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (ingestResponse.ok) {
                const ingestData = await ingestResponse.json();
                if (ingestData.reports_ingested > 0) {
                    showNotification(`Ingested ${ingestData.reports_ingested} new reports from email`, 'success');
                }
            }
        }

        // Process pending reports
        btn.textContent = '⏳ Processing reports...';
        const response = await fetch(`${API_BASE}/process/trigger`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.reports_processed > 0 || data.reports_failed > 0) {
            showNotification(data.message, 'success');
            // Reload dashboard to show new data
            await loadDashboard();
        } else {
            showNotification('No pending reports to process', 'info');
        }
    } catch (error) {
        console.error('Error triggering process:', error);
        showNotification('Error triggering process', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// Modal functions
function openHelpModal() {
    const modal = document.getElementById('helpModal');
    openModal(modal);
}

function openUploadModal() {
    const modal = document.getElementById('uploadModal');
    openModal(modal);
    resetUploadModal();
    setupUploadListeners();
}

function resetUploadModal() {
    selectedFiles = [];
    document.getElementById('fileList').style.display = 'none';
    document.getElementById('uploadProgress').style.display = 'none';
    document.getElementById('uploadResults').style.display = 'none';
    document.getElementById('uploadFilesBtn').style.display = 'none';
    document.getElementById('fileListItems').innerHTML = '';
    document.getElementById('fileCount').textContent = '0';
    document.getElementById('autoProcessCheckbox').checked = true;
}

function setupUploadListeners() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const selectFilesBtn = document.getElementById('selectFilesBtn');
    const uploadModalClose = document.getElementById('uploadModalClose');
    const closeUploadBtn = document.getElementById('closeUploadBtn');

    // File selection
    selectFilesBtn.onclick = () => fileInput.click();
    fileInput.onchange = (e) => handleFileSelect(Array.from(e.target.files));

    // Drag & drop
    dropZone.ondragover = (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    };

    dropZone.ondragleave = () => {
        dropZone.classList.remove('drag-over');
    };

    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        handleFileSelect(Array.from(e.dataTransfer.files));
    };

    // Upload button
    document.getElementById('uploadFilesBtn').onclick = uploadFiles;

    // Close buttons
    uploadModalClose.onclick = () => {
        document.getElementById('uploadModal').style.display = 'none';
    };
    closeUploadBtn.onclick = () => {
        document.getElementById('uploadModal').style.display = 'none';
    };

    // Click outside to close
    window.onclick = (e) => {
        const modal = document.getElementById('uploadModal');
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    };
}

function handleFileSelect(files) {
    const validExtensions = ['.xml', '.gz', '.zip'];
    const maxSize = 50 * 1024 * 1024; // 50MB

    selectedFiles = [];
    const fileListItems = document.getElementById('fileListItems');
    fileListItems.innerHTML = '';

    files.forEach(file => {
        const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        const isValid = validExtensions.includes(ext) && file.size <= maxSize;

        const fileInfo = {
            file: file,
            valid: isValid,
            reason: !validExtensions.includes(ext)
                ? 'Invalid file type'
                : (file.size > maxSize ? 'File too large (max 50MB)' : null)
        };

        selectedFiles.push(fileInfo);

        // Add to UI
        const item = document.createElement('div');
        item.className = `file-item ${isValid ? '' : 'invalid'}`;
        item.innerHTML = `
            <span class="file-name">${escapeHtml(file.name)}</span>
            <span class="file-size">${formatFileSize(file.size)}</span>
            ${!isValid ? `<span class="file-error">${fileInfo.reason}</span>` : ''}
            <button class="remove-file" data-index="${selectedFiles.length - 1}">✕</button>
        `;
        fileListItems.appendChild(item);
    });

    // Show file list and upload button
    const validCount = selectedFiles.filter(f => f.valid).length;
    document.getElementById('fileCount').textContent = validCount;
    document.getElementById('fileList').style.display = 'block';
    document.getElementById('uploadFilesBtn').style.display = validCount > 0 ? 'block' : 'none';

    // Remove file handlers
    fileListItems.querySelectorAll('.remove-file').forEach(btn => {
        btn.onclick = (e) => {
            const index = parseInt(e.target.dataset.index);
            selectedFiles.splice(index, 1);
            const remainingFiles = selectedFiles.map(f => f.file);
            handleFileSelect(remainingFiles);
        };
    });
}

async function uploadFiles() {
    const validFiles = selectedFiles.filter(f => f.valid);

    if (validFiles.length === 0) {
        showNotification('No valid files to upload', 'error');
        return;
    }

    // Show progress
    document.getElementById('uploadProgress').style.display = 'block';
    document.getElementById('uploadFilesBtn').disabled = true;
    document.getElementById('progressText').textContent = `Uploading ${validFiles.length} files...`;
    document.getElementById('progressBarFill').style.width = '100%';

    try {
        // Create FormData
        const formData = new FormData();
        validFiles.forEach(({file}) => {
            formData.append('files', file);
        });

        const autoProcess = document.getElementById('autoProcessCheckbox').checked;

        // Upload
        const response = await fetch(`${API_BASE}/upload?auto_process=${autoProcess}`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Upload failed: HTTP ${response.status}`);
        }

        const data = await response.json();

        // Show results
        displayUploadResults(data);

        // Reload dashboard if successful uploads
        if (data.uploaded > 0 && autoProcess) {
            setTimeout(() => loadDashboard(), 1000);
        }

    } catch (error) {
        console.error('Upload error:', error);
        showNotification('Upload failed: ' + error.message, 'error');
    } finally {
        document.getElementById('uploadProgress').style.display = 'none';
        document.getElementById('uploadFilesBtn').disabled = false;
    }
}

function displayUploadResults(data) {
    document.getElementById('uploadResults').style.display = 'block';
    document.getElementById('uploadFilesBtn').style.display = 'none';
    document.getElementById('resultUploaded').textContent = data.uploaded;
    document.getElementById('resultDuplicates').textContent = data.duplicates;
    document.getElementById('resultErrors').textContent = data.errors + data.invalid_files;

    // Show detailed results
    const details = document.getElementById('resultDetails');
    details.innerHTML = '';

    const errorFiles = data.files.filter(f => f.status === 'error' || f.status === 'invalid');
    if (errorFiles.length > 0) {
        const errorList = document.createElement('div');
        errorList.className = 'error-list';
        errorList.innerHTML = '<h4>Errors:</h4>';

        errorFiles.forEach(file => {
            const item = document.createElement('div');
            item.className = 'error-item';
            item.textContent = `${file.filename}: ${file.error_message}`;
            errorList.appendChild(item);
        });

        details.appendChild(errorList);
    }

    // Show success message
    const type = (data.errors + data.invalid_files) > 0 ? 'error' : 'success';
    showNotification(data.message, type);
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Show notification
function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type} show`;

    setTimeout(() => {
        notification.className = 'notification';
    }, 5000);
}

// Format date range
function formatDateRange(begin, end) {
    const formatDate = (dateStr) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };
    return `${formatDate(begin)} - ${formatDate(end)}`;
}

// ===========================================
// RECORD-LEVEL DEEP DIVE FUNCTIONS
// ===========================================

// Load records for a report
async function loadRecordsForReport(reportId, page = 1) {
    const loadingDiv = document.getElementById('recordsLoading');
    const recordsTable = document.getElementById('recordsTable');
    const recordsBody = document.getElementById('recordsTableBody');

    if (!loadingDiv || !recordsTable || !recordsBody) {
        console.error('Records elements not found in DOM');
        return;
    }

    loadingDiv.style.display = 'block';
    recordsTable.style.display = 'none';

    try {
        const response = await fetch(`${API_BASE}/reports/${reportId}/records?page=${page}&page_size=50`);
        if (!response.ok) {
            throw new Error('Failed to load records');
        }
        const data = await response.json();

        // Clear existing rows
        recordsBody.innerHTML = '';

        // Populate table
        data.records.forEach(record => {
            const row = recordsBody.insertRow();

            // Source IP (safe - textContent)
            row.insertCell(0).textContent = record.source_ip;

            // Message count (safe - textContent)
            row.insertCell(1).textContent = record.count.toLocaleString();

            // DKIM result (badge element)
            const dkimCell = row.insertCell(2);
            dkimCell.appendChild(createAuthBadge(record.dkim_result, 'dkim'));

            // SPF result (badge element)
            const spfCell = row.insertCell(3);
            spfCell.appendChild(createAuthBadge(record.spf_result, 'spf'));

            // Disposition (badge element)
            const dispCell = row.insertCell(4);
            dispCell.appendChild(createDispositionBadge(record.disposition));

            // Actions (View Details button)
            const actionCell = row.insertCell(5);
            const viewBtn = document.createElement('button');
            viewBtn.textContent = 'View';
            viewBtn.className = 'btn-secondary btn-sm';
            viewBtn.onclick = () => viewRecordDetail(record);
            actionCell.appendChild(viewBtn);

            // Color row based on alignment status
            row.className = getAlignmentClass(record);
        });

        // Show table and pagination
        loadingDiv.style.display = 'none';
        recordsTable.style.display = 'table';

        // Update pagination controls
        updateRecordsPagination(reportId, data.page, data.page_size, data.total);

    } catch (error) {
        console.error('Error loading records:', error);
        loadingDiv.textContent = 'Failed to load records';
    }
}

// Display detailed view for a single record (using safe DOM methods)
function viewRecordDetail(record) {
    const detailDiv = document.getElementById('recordDetail');
    const contentDiv = document.getElementById('recordDetailContent');

    if (!detailDiv || !contentDiv) {
        console.error('Record detail elements not found');
        return;
    }

    // Clear previous content
    contentDiv.innerHTML = '';

    // Create detail grid
    const grid = document.createElement('div');
    grid.className = 'detail-grid';

    // Source Information Card
    const sourceCard = createDetailCard('Source Information', [
        { label: 'Source IP', value: record.source_ip },
        { label: 'Message Count', value: record.count.toLocaleString() },
        { label: 'Disposition', value: record.disposition, badge: createDispositionBadge(record.disposition) }
    ]);
    grid.appendChild(sourceCard);

    // DKIM Authentication Card
    const dkimCard = createDetailCard('DKIM Authentication', [
        { label: 'Result', value: record.dkim_result || 'N/A', badge: createAuthBadge(record.dkim_result, 'dkim') },
        { label: 'Domain', value: record.dkim_domain || 'N/A' },
        { label: 'Selector', value: record.dkim_selector || 'N/A' }
    ]);
    grid.appendChild(dkimCard);

    // SPF Authentication Card
    const spfCard = createDetailCard('SPF Authentication', [
        { label: 'Result', value: record.spf_result || 'N/A', badge: createAuthBadge(record.spf_result, 'spf') },
        { label: 'Domain', value: record.spf_domain || 'N/A' },
        { label: 'Scope', value: record.spf_scope || 'N/A' }
    ]);
    grid.appendChild(spfCard);

    // Email Headers Card
    const headersCard = createDetailCard('Email Headers', [
        { label: 'From (Header)', value: record.header_from || 'N/A' },
        { label: 'From (Envelope)', value: record.envelope_from || 'N/A' },
        { label: 'To (Envelope)', value: record.envelope_to || 'N/A' }
    ]);
    grid.appendChild(headersCard);

    contentDiv.appendChild(grid);

    // Hide records table, show detail view
    document.getElementById('recordsInfo').style.display = 'none';
    detailDiv.style.display = 'block';
}

// HELPER: Create detail card (safe DOM method)
function createDetailCard(title, rows) {
    const card = document.createElement('div');
    card.className = 'detail-card';

    const heading = document.createElement('h4');
    heading.textContent = title;
    card.appendChild(heading);

    const table = document.createElement('div');
    table.className = 'detail-table';

    rows.forEach(({ label, value, badge }) => {
        const row = document.createElement('div');
        row.className = 'detail-row';

        const labelSpan = document.createElement('span');
        labelSpan.className = 'detail-label';
        labelSpan.textContent = label + ':';
        row.appendChild(labelSpan);

        const valueSpan = document.createElement('span');
        valueSpan.className = 'detail-value';
        if (badge) {
            valueSpan.appendChild(badge);
        } else {
            valueSpan.textContent = value;
        }
        row.appendChild(valueSpan);

        table.appendChild(row);
    });

    card.appendChild(table);
    return card;
}

// Hide record detail and show records table
function hideRecordDetail() {
    document.getElementById('recordDetail').style.display = 'none';
    document.getElementById('recordsInfo').style.display = 'block';
}

// Create authentication result badge (returns DOM element)
// Explanation text for authentication results
const AUTH_EXPLANATIONS = {
    dkim: {
        pass: 'DKIM Passed: The email was digitally signed by the sending domain and the signature is valid. This confirms the message hasn\'t been altered in transit.',
        fail: 'DKIM Failed: The digital signature is invalid or missing. This could indicate email spoofing or message tampering.',
        none: 'DKIM Not Found: No DKIM signature was present on this message.',
        neutral: 'DKIM Neutral: A signature was present but couldn\'t be verified.',
        temperror: 'DKIM Temporary Error: Verification failed due to a temporary issue (DNS lookup failure).',
        permerror: 'DKIM Permanent Error: Verification failed due to a configuration error in the DKIM record.'
    },
    spf: {
        pass: 'SPF Passed: The sending IP address is authorized to send email for this domain according to the domain\'s SPF record.',
        fail: 'SPF Failed: The sending IP address is NOT authorized to send email for this domain. This may indicate spoofing or misconfiguration.',
        softfail: 'SPF Soft Fail: The sending IP is probably not authorized (~all), but the domain owner isn\'t certain. Treated as suspicious.',
        neutral: 'SPF Neutral: The domain owner has explicitly stated they cannot or do not want to assert whether the IP is authorized.',
        none: 'SPF None: No SPF record was found for the domain.',
        temperror: 'SPF Temporary Error: Verification failed due to a temporary DNS issue.',
        permerror: 'SPF Permanent Error: The SPF record is malformed or has too many DNS lookups.'
    }
};

function createAuthBadge(result, type = 'generic') {
    // Create wrapper for tooltip positioning
    const wrapper = document.createElement('span');
    wrapper.className = 'badge-wrapper';

    const span = document.createElement('span');
    span.className = 'badge';

    let explanation = '';

    if (!result) {
        span.className += ' badge-gray';
        span.textContent = 'N/A';
        explanation = 'No authentication result available';
    } else if (result === 'pass') {
        span.className += ' badge-success';
        span.textContent = 'PASS';
        // Add explanation based on type
        if (type === 'dkim' && AUTH_EXPLANATIONS.dkim.pass) {
            explanation = AUTH_EXPLANATIONS.dkim.pass;
        } else if (type === 'spf' && AUTH_EXPLANATIONS.spf.pass) {
            explanation = AUTH_EXPLANATIONS.spf.pass;
        } else {
            explanation = 'Authentication check passed successfully';
        }
    } else {
        span.className += ' badge-danger';
        span.textContent = result.toUpperCase();
        // Add explanation based on type and result
        explanation = type === 'dkim'
            ? AUTH_EXPLANATIONS.dkim[result.toLowerCase()]
            : type === 'spf'
            ? AUTH_EXPLANATIONS.spf[result.toLowerCase()]
            : null;
        explanation = explanation || `Authentication result: ${result}`;
    }

    span.style.cursor = 'help';

    // Add custom tooltip on hover
    span.addEventListener('mouseenter', (e) => showTooltip(e, explanation));
    span.addEventListener('mouseleave', hideTooltip);
    span.addEventListener('mousemove', updateTooltipPosition);

    wrapper.appendChild(span);
    return wrapper;
}

// Explanation text for dispositions
const DISPOSITION_EXPLANATIONS = {
    none: 'None: The email was delivered normally to the inbox. The DMARC policy is in monitoring mode (p=none), collecting data without taking action on failed authentication.',
    quarantine: 'Quarantine: The email was sent to the spam/junk folder. This happens when DMARC authentication fails and the domain policy is set to quarantine (p=quarantine).',
    reject: 'Reject: The email was blocked and not delivered. This is the strictest DMARC policy (p=reject), used when authentication fails and the domain wants maximum protection.'
};

// Create disposition badge (returns DOM element)
function createDispositionBadge(disposition) {
    // Create wrapper for tooltip positioning
    const wrapper = document.createElement('span');
    wrapper.className = 'badge-wrapper';

    const span = document.createElement('span');
    span.className = 'badge';

    const colorMap = {
        'none': 'badge-success',
        'quarantine': 'badge-warning',
        'reject': 'badge-danger'
    };

    span.className += ' ' + (colorMap[disposition] || 'badge-gray');
    span.textContent = (disposition || 'N/A').toUpperCase();
    span.style.cursor = 'help';

    // Get explanation for disposition
    const explanation = disposition && DISPOSITION_EXPLANATIONS[disposition.toLowerCase()]
        ? DISPOSITION_EXPLANATIONS[disposition.toLowerCase()]
        : 'Disposition: The action taken by the receiving mail server based on DMARC policy and authentication results.';

    // Add custom tooltip on hover
    span.addEventListener('mouseenter', (e) => showTooltip(e, explanation));
    span.addEventListener('mouseleave', hideTooltip);
    span.addEventListener('mousemove', updateTooltipPosition);

    wrapper.appendChild(span);
    return wrapper;
}

// Get row class based on alignment
function getAlignmentClass(record) {
    const dkimPass = record.dkim_result === 'pass';
    const spfPass = record.spf_result === 'pass';

    if (dkimPass && spfPass) return 'row-pass';
    if (!dkimPass && !spfPass) return 'row-fail';
    return 'row-partial';
}

// Update pagination controls
function updateRecordsPagination(reportId, currentPage, pageSize, total) {
    const paginationDiv = document.getElementById('recordsPagination');
    const totalPages = Math.ceil(total / pageSize);

    if (!paginationDiv) {
        console.error('Pagination element not found');
        return;
    }

    if (totalPages <= 1) {
        paginationDiv.style.display = 'none';
        return;
    }

    // Clear previous content
    paginationDiv.innerHTML = '';

    const controls = document.createElement('div');
    controls.className = 'pagination-controls';

    // Page indicator
    const pageText = document.createElement('span');
    pageText.textContent = `Page ${currentPage} of ${totalPages}`;
    controls.appendChild(pageText);

    // Previous button
    if (currentPage > 1) {
        const prevBtn = document.createElement('button');
        prevBtn.textContent = 'Previous';
        prevBtn.onclick = () => loadRecordsForReport(reportId, currentPage - 1);
        controls.appendChild(prevBtn);
    }

    // Next button
    if (currentPage < totalPages) {
        const nextBtn = document.createElement('button');
        nextBtn.textContent = 'Next';
        nextBtn.onclick = () => loadRecordsForReport(reportId, currentPage + 1);
        controls.appendChild(nextBtn);
    }

    paginationDiv.appendChild(controls);
    paginationDiv.style.display = 'block';
}

// Load alignment breakdown chart
async function loadAlignmentChart() {
    try {
        const queryString = buildQueryString();
        const response = await fetch(`${API_BASE}/rollup/alignment-breakdown?${queryString}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const ctx = document.getElementById('alignmentChart').getContext('2d');

        if (alignmentChart) {
            alignmentChart.destroy();
        }

        const theme = document.documentElement.getAttribute('data-theme');
        const textColor = theme === 'dark' ? '#e8e8e8' : '#333333';
        const gridColor = theme === 'dark' ? '#2d4a6f' : '#e0e0e0';

        const total = data.both_pass + data.dkim_only + data.spf_only + data.both_fail;

        alignmentChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Authentication Alignment'],
                datasets: [
                    {
                        label: 'Both Pass',
                        data: [data.both_pass],
                        backgroundColor: '#27ae60'
                    },
                    {
                        label: 'DKIM Only',
                        data: [data.dkim_only],
                        backgroundColor: '#3498db'
                    },
                    {
                        label: 'SPF Only',
                        data: [data.spf_only],
                        backgroundColor: '#f39c12'
                    },
                    {
                        label: 'Both Fail',
                        data: [data.both_fail],
                        backgroundColor: '#e74c3c'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textColor }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const value = context.parsed.y;
                                const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                return `${context.dataset.label}: ${value.toLocaleString()} (${pct}%)`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        ticks: { color: textColor },
                        grid: { color: gridColor }
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => value.toLocaleString(),
                            color: textColor
                        },
                        grid: { color: gridColor }
                    }
                }
            }
        });

        hideChartSkeleton('alignmentChart');
    } catch (error) {
        console.error('Error loading alignment chart:', error);
        hideChartSkeleton('alignmentChart');
        createErrorBoundary('alignmentChart', 'Failed to load alignment data', loadAlignmentChart);
        throw error;
    }
}

// Load compliance chart
async function loadComplianceChart() {
    try {
        const queryString = buildQueryString();
        const response = await fetch(`${API_BASE}/rollup/alignment-breakdown?${queryString}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const ctx = document.getElementById('complianceChart').getContext('2d');

        if (complianceChart) {
            complianceChart.destroy();
        }

        const theme = document.documentElement.getAttribute('data-theme');
        const textColor = theme === 'dark' ? '#e8e8e8' : '#333333';

        const compliant = data.both_pass;
        const nonCompliant = data.dkim_only + data.spf_only + data.both_fail;
        const total = compliant + nonCompliant;

        complianceChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Compliant (Both Pass)', 'Non-Compliant'],
                datasets: [{
                    data: [compliant, nonCompliant],
                    backgroundColor: ['#27ae60', '#e74c3c']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textColor }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const value = context.parsed;
                                const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                return `${context.label}: ${value.toLocaleString()} (${pct}%)`;
                            }
                        }
                    }
                }
            }
        });

        hideChartSkeleton('complianceChart');
    } catch (error) {
        console.error('Error loading compliance chart:', error);
        hideChartSkeleton('complianceChart');
        createErrorBoundary('complianceChart', 'Failed to load compliance data', loadComplianceChart);
        throw error;
    }
}

// Load failure trend chart
async function loadFailureTrendChart() {
    try {
        const queryString = buildQueryString();
        const response = await fetch(`${API_BASE}/rollup/failure-trend?${queryString}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const ctx = document.getElementById('failureTrendChart').getContext('2d');

        if (failureTrendChart) {
            failureTrendChart.destroy();
        }

        const theme = document.documentElement.getAttribute('data-theme');
        const textColor = theme === 'dark' ? '#e8e8e8' : '#333333';
        const gridColor = theme === 'dark' ? '#2d4a6f' : '#e0e0e0';

        failureTrendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.trend.map(d => d.date),
                datasets: [
                    {
                        label: 'Failure Rate',
                        data: data.trend.map(d => d.failure_rate),
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: '7-Day Moving Average',
                        data: data.trend.map(d => d.moving_average),
                        borderColor: '#3498db',
                        backgroundColor: 'transparent',
                        borderDash: [5, 5],
                        tension: 0.4,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: textColor }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const dataPoint = data.trend[context.dataIndex];
                                if (context.datasetIndex === 0) {
                                    return [
                                        `Failure Rate: ${dataPoint.failure_rate.toFixed(1)}%`,
                                        `Failed: ${dataPoint.failed_count.toLocaleString()}`,
                                        `Total: ${dataPoint.total_count.toLocaleString()}`
                                    ];
                                } else {
                                    return `Moving Avg: ${dataPoint.moving_average.toFixed(1)}%`;
                                }
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: textColor },
                        grid: { color: gridColor }
                    },
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: (value) => `${value}%`,
                            color: textColor
                        },
                        grid: { color: gridColor }
                    }
                }
            }
        });

        hideChartSkeleton('failureTrendChart');
    } catch (error) {
        console.error('Error loading failure trend chart:', error);
        hideChartSkeleton('failureTrendChart');
        createErrorBoundary('failureTrendChart', 'Failed to load failure trend data', loadFailureTrendChart);
        throw error;
    }
}

// Load top organizations chart
async function loadTopOrganizationsChart() {
    try {
        const queryString = buildQueryString({ limit: 10 });
        const response = await fetch(`${API_BASE}/rollup/top-organizations?${queryString}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const ctx = document.getElementById('topOrganizationsChart').getContext('2d');

        if (topOrganizationsChart) {
            topOrganizationsChart.destroy();
        }

        const theme = document.documentElement.getAttribute('data-theme');
        const textColor = theme === 'dark' ? '#e8e8e8' : '#333333';
        const gridColor = theme === 'dark' ? '#2d4a6f' : '#e0e0e0';

        topOrganizationsChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.organizations.map(d => d.org_name),
                datasets: [{
                    label: 'Total Messages',
                    data: data.organizations.map(d => d.total_messages),
                    backgroundColor: '#3498db'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                indexAxis: 'y',
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const org = data.organizations[context.dataIndex];
                                const passPct = org.total_messages > 0
                                    ? ((org.pass_count / org.total_messages) * 100).toFixed(1)
                                    : 0;
                                return [
                                    `Total: ${org.total_messages.toLocaleString()}`,
                                    `Pass: ${org.pass_count.toLocaleString()}`,
                                    `Fail: ${org.fail_count.toLocaleString()}`,
                                    `Pass Rate: ${passPct}%`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => value.toLocaleString(),
                            color: textColor
                        },
                        grid: { color: gridColor }
                    },
                    y: {
                        ticks: { color: textColor },
                        grid: { color: gridColor }
                    }
                }
            }
        });

        hideChartSkeleton('topOrganizationsChart');
    } catch (error) {
        console.error('Error loading top organizations chart:', error);
        hideChartSkeleton('topOrganizationsChart');
        createErrorBoundary('topOrganizationsChart', 'Failed to load organizations data', loadTopOrganizationsChart);
        throw error;
    }
}

// Tooltip management
let currentTooltip = null;

function showTooltip(event, text) {
    // Remove any existing tooltip
    hideTooltip();

    // Create tooltip element
    const tooltip = document.createElement('div');
    tooltip.className = 'badge-tooltip';
    tooltip.textContent = text;
    tooltip.id = 'active-tooltip';

    // Add to body
    document.body.appendChild(tooltip);
    currentTooltip = tooltip;

    // Position tooltip
    positionTooltip(event, tooltip);
}

function positionTooltip(event, tooltip) {
    const rect = event.target.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();

    // Calculate position (centered above the badge)
    let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
    let top = rect.top - tooltipRect.height - 10;

    // Check if tooltip goes off left edge
    if (left < 10) {
        left = 10;
    }

    // Check if tooltip goes off right edge
    if (left + tooltipRect.width > window.innerWidth - 10) {
        left = window.innerWidth - tooltipRect.width - 10;
    }

    // Check if tooltip goes off top edge (show below instead)
    if (top < 10) {
        top = rect.bottom + 10;
        tooltip.classList.add('bottom');
    }

    tooltip.style.position = 'fixed';
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
}

function updateTooltipPosition(event) {
    if (currentTooltip) {
        positionTooltip(event, currentTooltip);
    }
}

function hideTooltip() {
    if (currentTooltip) {
        currentTooltip.remove();
        currentTooltip = null;
    }
}
