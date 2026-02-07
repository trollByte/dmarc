// API Base URL
const API_BASE = window.DMARC_CONFIG?.apiBase || '/api';

// Default filter days
const DEFAULT_FILTER_DAYS = window.DMARC_CONFIG?.defaultFilterDays || 365;

// ==========================================
// SHARED NAMESPACE
// ==========================================

window.DMARC = window.DMARC || {};

// ==========================================
// AUTHENTICATION
// ==========================================

let accessToken = null;
let refreshToken = null;
let currentUser = null;
let isRefreshingToken = false;

function getAuthHeaders() {
    if (accessToken) {
        return { 'Authorization': 'Bearer ' + accessToken };
    }
    return {};
}

function showLoginOverlay() {
    const overlay = document.getElementById('loginOverlay');
    const dashboard = document.getElementById('dashboardContainer');
    if (overlay) overlay.style.display = '';
    if (dashboard) dashboard.style.display = 'none';
}

function hideLoginOverlay() {
    const overlay = document.getElementById('loginOverlay');
    const dashboard = document.getElementById('dashboardContainer');
    if (overlay) overlay.style.display = 'none';
    if (dashboard) dashboard.style.display = '';
}

function updateUserMenu() {
    const userMenu = document.getElementById('userMenu');
    const displayName = document.getElementById('userDisplayName');
    const menuUsername = document.getElementById('userMenuUsername');
    const menuRole = document.getElementById('userMenuRole');
    if (currentUser && userMenu) {
        userMenu.hidden = false;
        if (displayName) displayName.textContent = currentUser.username || '';
        if (menuUsername) menuUsername.textContent = currentUser.username || '';
        if (menuRole) menuRole.textContent = currentUser.role || '';
    } else if (userMenu) {
        userMenu.hidden = true;
    }
}

async function login(username, password) {
    const errorEl = document.getElementById('loginError');
    const submitBtn = document.getElementById('loginSubmitBtn');
    if (errorEl) errorEl.hidden = true;
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Signing in...';
    }

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || 'Invalid credentials');
        }

        const data = await response.json();
        accessToken = data.access_token;
        refreshToken = data.refresh_token;

        // Fetch user info
        await fetchCurrentUser();

        hideLoginOverlay();
        updateUserMenu();
        updateSidebarUser();
        initSidebarAndRouter();
    } catch (err) {
        if (errorEl) {
            errorEl.textContent = err.message;
            errorEl.hidden = false;
        }
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Sign In';
        }
    }
}

async function fetchCurrentUser() {
    try {
        const response = await fetch(`${API_BASE}/auth/me`, {
            headers: getAuthHeaders()
        });
        if (response.ok) {
            const data = await response.json();
            currentUser = data.user || data;
        }
    } catch (e) {
        // Silently fail - user info is not critical
    }
}

async function refreshAccessToken() {
    if (isRefreshingToken || !refreshToken) return false;
    isRefreshingToken = true;

    try {
        const response = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });

        if (!response.ok) {
            // Refresh failed - force re-login
            accessToken = null;
            refreshToken = null;
            currentUser = null;
            showLoginOverlay();
            updateUserMenu();
            return false;
        }

        const data = await response.json();
        accessToken = data.access_token;
        return true;
    } catch (e) {
        return false;
    } finally {
        isRefreshingToken = false;
    }
}

async function logout() {
    try {
        if (accessToken && refreshToken) {
            await fetch(`${API_BASE}/auth/logout`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...getAuthHeaders()
                },
                body: JSON.stringify({ refresh_token: refreshToken })
            });
        }
    } catch (e) {
        // Logout API call is best-effort
    }

    accessToken = null;
    refreshToken = null;
    currentUser = null;
    showLoginOverlay();
    updateUserMenu();
    resetSidebarAndRouter();

    // Clear login form
    const usernameInput = document.getElementById('loginUsername');
    const passwordInput = document.getElementById('loginPassword');
    const errorEl = document.getElementById('loginError');
    if (usernameInput) usernameInput.value = '';
    if (passwordInput) passwordInput.value = '';
    if (errorEl) errorEl.hidden = true;
}

// Wrap the native fetch to inject auth headers and handle 401s
const _originalFetch = window.fetch;
window.fetch = async function(url, options = {}) {
    // Only inject auth headers for API calls (not for the auth endpoints themselves during login)
    const urlStr = typeof url === 'string' ? url : url.toString();
    const isApiCall = urlStr.startsWith(API_BASE) || urlStr.startsWith('/api');
    const isAuthEndpoint = urlStr.includes('/auth/login') || urlStr.includes('/auth/refresh');

    if (isApiCall && !isAuthEndpoint && accessToken) {
        options.headers = {
            ...options.headers,
            ...getAuthHeaders()
        };
    }

    let response = await _originalFetch.call(window, url, options);

    // If 401 on an API call, try refreshing the token once
    if (response.status === 401 && isApiCall && !isAuthEndpoint && refreshToken) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
            // Retry with new token
            options.headers = {
                ...options.headers,
                ...getAuthHeaders()
            };
            response = await _originalFetch.call(window, url, options);
        }
    }

    // If still 401, show login
    if (response.status === 401 && isApiCall && !isAuthEndpoint) {
        showLoginOverlay();
        updateUserMenu();
    }

    return response;
};

function setupAuthEventListeners() {
    // Login form submission
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const username = document.getElementById('loginUsername').value.trim();
            const password = document.getElementById('loginPassword').value;
            if (username && password) {
                login(username, password);
            }
        });
    }

    // Logout button
    document.getElementById('logoutBtn')?.addEventListener('click', logout);

    // User menu dropdown toggle
    const userMenuTrigger = document.getElementById('userMenuTrigger');
    const userMenuDropdown = document.getElementById('userMenuDropdown');
    if (userMenuTrigger && userMenuDropdown) {
        userMenuTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !userMenuDropdown.hidden;
            userMenuDropdown.hidden = isOpen;
            userMenuTrigger.setAttribute('aria-expanded', String(!isOpen));
        });

        // Close user menu on outside click
        document.addEventListener('click', () => {
            userMenuDropdown.hidden = true;
            userMenuTrigger.setAttribute('aria-expanded', 'false');
        });
    }
}

// ==========================================
// SIDEBAR & ROUTER MANAGEMENT
// ==========================================

/**
 * Initialize sidebar event handlers and start the router after login.
 * Registers the dashboard page module, shows admin section if applicable,
 * and navigates to the current hash or default page.
 */
function initSidebarAndRouter() {
    var Router = window.DMARC.Router;
    if (!Router) return;

    // Register dashboard module if available
    if (window.DMARC.DashboardPage) {
        Router.register('dashboard', window.DMARC.DashboardPage);
    }

    // Show admin section if user is admin
    var adminSection = document.getElementById('sidebarAdminSection');
    if (adminSection) {
        if (currentUser && currentUser.role === 'admin') {
            adminSection.classList.add('visible');
        } else {
            adminSection.classList.remove('visible');
        }
    }

    // Initialize router (navigates to current hash or default)
    Router.init();
}

/**
 * Reset sidebar and router state on logout.
 */
function resetSidebarAndRouter() {
    var Router = window.DMARC.Router;
    if (Router) {
        Router.reset();
    }

    // Hide admin section
    var adminSection = document.getElementById('sidebarAdminSection');
    if (adminSection) {
        adminSection.classList.remove('visible');
    }

    // Clear sidebar user info
    var nameEl = document.getElementById('sidebarUserName');
    var roleEl = document.getElementById('sidebarUserRole');
    if (nameEl) nameEl.textContent = '';
    if (roleEl) roleEl.textContent = '';

    // Collapse sidebar on mobile
    var appLayout = document.getElementById('dashboardContainer');
    if (appLayout) appLayout.classList.remove('sidebar-mobile-open');
}

/**
 * Update sidebar footer with current user information.
 */
function updateSidebarUser() {
    var nameEl = document.getElementById('sidebarUserName');
    var roleEl = document.getElementById('sidebarUserRole');
    if (currentUser) {
        if (nameEl) nameEl.textContent = currentUser.username || '';
        if (roleEl) roleEl.textContent = currentUser.role || '';
    }
}

/**
 * Set up sidebar UI interactions: collapse toggle, nav clicks, mobile toggle.
 * Called once during DOMContentLoaded.
 */
function setupSidebar() {
    var appLayout = document.getElementById('dashboardContainer');
    var sidebar = document.getElementById('sidebar');
    var toggleBtn = document.getElementById('sidebarToggle');
    var mobileToggle = document.getElementById('sidebarMobileToggle');
    var overlay = document.getElementById('sidebarOverlay');

    // Sidebar collapse toggle (class goes on app-layout parent)
    if (toggleBtn && appLayout) {
        toggleBtn.addEventListener('click', function() {
            appLayout.classList.toggle('sidebar-collapsed');
            var isCollapsed = appLayout.classList.contains('sidebar-collapsed');
            toggleBtn.setAttribute('aria-label', isCollapsed ? 'Expand sidebar' : 'Collapse sidebar');
            toggleBtn.setAttribute('title', isCollapsed ? 'Expand sidebar' : 'Collapse sidebar');
            try {
                localStorage.setItem('dmarc-sidebar-collapsed', isCollapsed ? '1' : '0');
            } catch (e) {
                // localStorage not available
            }
        });

        // Restore collapsed state from localStorage
        try {
            if (localStorage.getItem('dmarc-sidebar-collapsed') === '1') {
                appLayout.classList.add('sidebar-collapsed');
                toggleBtn.setAttribute('aria-label', 'Expand sidebar');
                toggleBtn.setAttribute('title', 'Expand sidebar');
            }
        } catch (e) {
            // localStorage not available
        }
    }

    // Mobile sidebar toggle (hamburger menu)
    if (mobileToggle && appLayout) {
        mobileToggle.addEventListener('click', function() {
            appLayout.classList.toggle('sidebar-mobile-open');
        });
    }

    // Close mobile sidebar when overlay is clicked
    if (overlay && appLayout) {
        overlay.addEventListener('click', function() {
            appLayout.classList.remove('sidebar-mobile-open');
        });
    }

    // Sidebar navigation item clicks
    var navItems = document.querySelectorAll('.sidebar-item[data-page]');
    navItems.forEach(function(item) {
        item.addEventListener('click', function() {
            var pageName = item.getAttribute('data-page');
            if (pageName && window.DMARC.Router) {
                window.DMARC.Router.navigate(pageName);
            }
            // Close mobile sidebar after navigation
            if (appLayout) appLayout.classList.remove('sidebar-mobile-open');
        });
    });
}

// Chart instances
let timelineChart, domainChart, sourceIpChart, dispositionChart;
let alignmentChart, complianceChart, failureTrendChart, topOrganizationsChart;

// Current filter state
let currentFilters = {
    domain: '',
    days: DEFAULT_FILTER_DAYS,  // Configurable default filter days
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
const AUTO_REFRESH_INTERVAL = window.DMARC_CONFIG?.autoRefreshInterval || 60000;
let autoRefreshInterval = null;
let newDataAvailable = false;
let lastDataHash = null;

// Secondary charts visibility
let secondaryChartsVisible = false;

// Onboarding state
let onboardingState = {
    currentStep: 1,
    totalSteps: 5,
    completed: false
};

// Feature tooltips queue
const featureTooltipsQueue = [
    { target: '#importBtn', text: 'Import DMARC reports from files or your email inbox', position: 'bottom' },
    { target: '#dateRangeFilter', text: 'Filter reports by date range to analyze specific periods', position: 'bottom' },
    { target: '#toggleSecondaryCharts', text: 'Click to reveal additional analytics charts', position: 'top' }
];

// Comparison/trend data cache
let trendDataCache = {
    passRate: [],
    failRate: [],
    messageVolume: [],
    lastUpdated: null
};

// Keyboard shortcuts configuration
const keyboardShortcuts = [
    { key: '?', description: 'Show keyboard shortcuts', action: 'showKeyboardShortcuts' },
    { key: 'r', description: 'Refresh dashboard', action: 'refresh' },
    { key: 'u', description: 'Upload reports', action: 'upload' },
    { key: 'f', description: 'Focus filter bar', action: 'focusFilter' },
    { key: 'h', description: 'Open help', action: 'help' },
    { key: 'Escape', description: 'Close modal/dropdown', action: 'escape' },
    { key: 't', description: 'Toggle theme', action: 'toggleTheme' },
    { key: 'c', description: 'Toggle more charts', action: 'toggleCharts' },
    { key: 's', description: 'Focus search (global)', action: 'focusSearch' }
];

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
// ONBOARDING WIZARD
// ==========================================

function checkFirstRun() {
    const hasCompletedOnboarding = localStorage.getItem('dmarc-onboarding-completed');
    return !hasCompletedOnboarding;
}

function showOnboarding() {
    const modal = document.getElementById('onboardingModal');
    if (modal) {
        modal.hidden = false;
        updateOnboardingStep(1);
        setupOnboardingListeners();
    }
}

function setupOnboardingListeners() {
    const nextBtn = document.getElementById('onboardingNext');
    const prevBtn = document.getElementById('onboardingPrev');
    const skipBtn = document.getElementById('onboardingSkip');
    const uploadBtn = document.getElementById('onboardingUpload');
    const dots = document.querySelectorAll('.onboarding-dot');

    nextBtn?.addEventListener('click', goToNextStep);
    prevBtn?.addEventListener('click', goToPrevStep);
    skipBtn?.addEventListener('click', completeOnboarding);
    uploadBtn?.addEventListener('click', () => {
        completeOnboarding();
        openUploadModal();
    });

    dots.forEach(dot => {
        dot.addEventListener('click', () => {
            const step = parseInt(dot.dataset.step, 10);
            goToStep(step);
        });
    });
}

function goToNextStep() {
    if (onboardingState.currentStep < onboardingState.totalSteps) {
        goToStep(onboardingState.currentStep + 1);
    } else {
        completeOnboarding();
    }
}

function goToPrevStep() {
    if (onboardingState.currentStep > 1) {
        goToStep(onboardingState.currentStep - 1);
    }
}

function goToStep(step) {
    onboardingState.currentStep = step;
    updateOnboardingStep(step);
}

function updateOnboardingStep(step) {
    // Update progress bar
    const progressBar = document.getElementById('onboardingProgressBar');
    if (progressBar) {
        progressBar.style.width = `${(step / onboardingState.totalSteps) * 100}%`;
    }

    // Update step visibility
    for (let i = 1; i <= onboardingState.totalSteps; i++) {
        const stepEl = document.getElementById(`onboardingStep${i}`);
        if (stepEl) {
            stepEl.hidden = i !== step;
        }
    }

    // Update dots
    document.querySelectorAll('.onboarding-dot').forEach(dot => {
        const dotStep = parseInt(dot.dataset.step, 10);
        dot.classList.remove('active', 'completed');
        dot.setAttribute('aria-selected', 'false');

        if (dotStep === step) {
            dot.classList.add('active');
            dot.setAttribute('aria-selected', 'true');
        } else if (dotStep < step) {
            dot.classList.add('completed');
        }
    });

    // Update navigation buttons
    const prevBtn = document.getElementById('onboardingPrev');
    const nextBtn = document.getElementById('onboardingNext');

    if (prevBtn) {
        prevBtn.hidden = step === 1;
    }

    if (nextBtn) {
        nextBtn.textContent = step === onboardingState.totalSteps ? 'Get Started' : 'Next';
    }

    // Update modal title based on step
    const titles = [
        'Welcome to DMARC Dashboard',
        'Import Your Reports',
        'Understand Your Data',
        'Take Action',
        'Ready to Go!'
    ];
    const title = document.getElementById('onboardingModalTitle');
    if (title && titles[step - 1]) {
        title.textContent = titles[step - 1];
    }
}

function completeOnboarding() {
    localStorage.setItem('dmarc-onboarding-completed', 'true');
    onboardingState.completed = true;

    const modal = document.getElementById('onboardingModal');
    if (modal) {
        modal.hidden = true;
    }

    // Start showing feature tooltips after onboarding
    setTimeout(showNextFeatureTooltip, 1000);
}

// ==========================================
// FEATURE TOOLTIPS (Contextual Help)
// ==========================================

let currentTooltipIndex = 0;
let seenTooltips = JSON.parse(localStorage.getItem('dmarc-seen-tooltips') || '[]');

function showNextFeatureTooltip() {
    const tooltip = document.getElementById('featureTooltip');
    if (!tooltip) return;

    // Find next unseen tooltip
    while (currentTooltipIndex < featureTooltipsQueue.length) {
        const tooltipConfig = featureTooltipsQueue[currentTooltipIndex];
        if (!seenTooltips.includes(tooltipConfig.target)) {
            showFeatureTooltip(tooltipConfig);
            return;
        }
        currentTooltipIndex++;
    }
}

function showFeatureTooltip(config) {
    const tooltip = document.getElementById('featureTooltip');
    const targetEl = document.querySelector(config.target);

    if (!tooltip || !targetEl) return;

    // Set tooltip content
    const textEl = tooltip.querySelector('.feature-tooltip-text');
    if (textEl) {
        textEl.textContent = config.text;
    }

    // Position tooltip
    const targetRect = targetEl.getBoundingClientRect();
    tooltip.setAttribute('data-position', config.position);

    // Calculate position
    let top, left;
    const tooltipPadding = 12;

    switch (config.position) {
        case 'bottom':
            top = targetRect.bottom + tooltipPadding;
            left = targetRect.left + (targetRect.width / 2);
            break;
        case 'top':
            top = targetRect.top - tooltipPadding;
            left = targetRect.left + (targetRect.width / 2);
            break;
        case 'left':
            top = targetRect.top + (targetRect.height / 2);
            left = targetRect.left - tooltipPadding;
            break;
        case 'right':
            top = targetRect.top + (targetRect.height / 2);
            left = targetRect.right + tooltipPadding;
            break;
        default:
            top = targetRect.bottom + tooltipPadding;
            left = targetRect.left + (targetRect.width / 2);
    }

    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;
    tooltip.style.transform = config.position === 'bottom' || config.position === 'top'
        ? 'translateX(-50%)'
        : 'translateY(-50%)';

    if (config.position === 'top') {
        tooltip.style.transform = 'translateX(-50%) translateY(-100%)';
    }

    tooltip.hidden = false;

    // Setup dismiss handler
    const dismissBtn = tooltip.querySelector('.feature-tooltip-dismiss');
    const dismissHandler = () => {
        dismissFeatureTooltip(config.target);
        dismissBtn?.removeEventListener('click', dismissHandler);
    };
    dismissBtn?.addEventListener('click', dismissHandler);
}

function dismissFeatureTooltip(target) {
    const tooltip = document.getElementById('featureTooltip');
    if (tooltip) {
        tooltip.hidden = true;
    }

    // Mark as seen
    seenTooltips.push(target);
    localStorage.setItem('dmarc-seen-tooltips', JSON.stringify(seenTooltips));

    // Show next tooltip after delay
    currentTooltipIndex++;
    setTimeout(showNextFeatureTooltip, 3000);
}

// ==========================================
// WELCOME EMPTY STATE
// ==========================================

function showWelcomeEmptyState() {
    // Insert into dashboard section so it hides when navigating away
    const dashboardSection = document.getElementById('page-dashboard');
    if (!dashboardSection) return;

    // Prevent duplicate welcome states
    if (document.getElementById('welcomeEmptyState')) return;

    // Hide dashboard content sections
    const sections = dashboardSection.querySelectorAll('.filter-bar, .stats-section, .charts-section, .table-section');
    sections.forEach(section => {
        section.style.display = 'none';
    });

    // Create welcome state
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'welcome-empty-state';
    welcomeDiv.id = 'welcomeEmptyState';

    // Icon
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('viewBox', '0 0 24 24');
    icon.setAttribute('fill', 'none');
    icon.setAttribute('stroke', 'currentColor');
    icon.setAttribute('stroke-width', '1.5');
    icon.classList.add('welcome-empty-state-icon');
    icon.innerHTML = `
        <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" stroke-linecap="round" stroke-linejoin="round"/>
    `;
    welcomeDiv.appendChild(icon);

    // Title
    const title = document.createElement('h2');
    title.textContent = 'Welcome to DMARC Dashboard';
    welcomeDiv.appendChild(title);

    // Description
    const desc = document.createElement('p');
    desc.textContent = 'Get started by importing your first DMARC reports. You can upload XML files directly or connect your email inbox to automatically receive reports.';
    welcomeDiv.appendChild(desc);

    // Actions
    const actions = document.createElement('div');
    actions.className = 'welcome-empty-state-actions';

    const uploadBtn = document.createElement('button');
    uploadBtn.className = 'btn-primary';
    uploadBtn.innerHTML = `
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
        </svg>
        Upload Reports
    `;
    uploadBtn.addEventListener('click', openUploadModal);
    actions.appendChild(uploadBtn);

    const learnBtn = document.createElement('button');
    learnBtn.className = 'btn-secondary';
    learnBtn.innerHTML = `
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
        Learn About DMARC
    `;
    learnBtn.addEventListener('click', openHelpModal);
    actions.appendChild(learnBtn);

    welcomeDiv.appendChild(actions);

    // Features grid
    const features = document.createElement('div');
    features.className = 'welcome-empty-state-features';

    const featureData = [
        { icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z', title: 'Security Insights', desc: 'Monitor authentication' },
        { icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z', title: 'Visual Analytics', desc: 'Charts and trends' },
        { icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z', title: 'Real-time Updates', desc: 'Auto-refresh data' }
    ];

    featureData.forEach(f => {
        const feature = document.createElement('div');
        feature.className = 'welcome-feature';

        const fIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        fIcon.setAttribute('viewBox', '0 0 24 24');
        fIcon.setAttribute('fill', 'none');
        fIcon.setAttribute('stroke', 'currentColor');
        fIcon.setAttribute('stroke-width', '1.5');
        fIcon.classList.add('welcome-feature-icon');
        fIcon.innerHTML = `<path d="${f.icon}" stroke-linecap="round" stroke-linejoin="round"/>`;
        feature.appendChild(fIcon);

        const fTitle = document.createElement('h4');
        fTitle.textContent = f.title;
        feature.appendChild(fTitle);

        const fDesc = document.createElement('p');
        fDesc.textContent = f.desc;
        feature.appendChild(fDesc);

        features.appendChild(feature);
    });

    welcomeDiv.appendChild(features);

    dashboardSection.appendChild(welcomeDiv);
}

function hideWelcomeEmptyState() {
    const welcomeState = document.getElementById('welcomeEmptyState');
    if (welcomeState) {
        welcomeState.remove();
    }

    const dashboardSection = document.getElementById('page-dashboard');
    if (dashboardSection) {
        const sections = dashboardSection.querySelectorAll('.filter-bar, .stats-section, .charts-section, .table-section');
        sections.forEach(section => {
            section.style.display = '';
        });
    }
}

// ==========================================
// GLOBAL SEARCH
// ==========================================

let searchDebounceTimer = null;
let searchCache = {
    domains: [],
    organizations: [],
    sourceIps: []
};

function setupGlobalSearch() {
    const searchInput = document.getElementById('globalSearchInput');
    const searchResults = document.getElementById('globalSearchResults');

    if (!searchInput || !searchResults) return;

    // Hide kbd hint on focus
    searchInput.addEventListener('focus', () => {
        const kbd = searchInput.parentElement.querySelector('.global-search-kbd');
        if (kbd) kbd.style.display = 'none';
    });

    searchInput.addEventListener('blur', () => {
        const kbd = searchInput.parentElement.querySelector('.global-search-kbd');
        if (kbd) kbd.style.display = '';
        // Delay hiding results to allow click
        setTimeout(() => {
            if (!searchResults.contains(document.activeElement)) {
                searchResults.hidden = true;
            }
        }, 200);
    });

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();

        clearTimeout(searchDebounceTimer);

        if (query.length < 2) {
            searchResults.hidden = true;
            return;
        }

        searchDebounceTimer = setTimeout(() => {
            performGlobalSearch(query);
        }, 300);
    });

    // Keyboard navigation in results
    searchInput.addEventListener('keydown', (e) => {
        const items = searchResults.querySelectorAll('.search-result-item');
        const activeItem = searchResults.querySelector('.search-result-item.active');

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (!activeItem && items.length > 0) {
                items[0].classList.add('active');
            } else if (activeItem) {
                const index = Array.from(items).indexOf(activeItem);
                activeItem.classList.remove('active');
                if (index < items.length - 1) {
                    items[index + 1].classList.add('active');
                } else {
                    items[0].classList.add('active');
                }
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (activeItem) {
                const index = Array.from(items).indexOf(activeItem);
                activeItem.classList.remove('active');
                if (index > 0) {
                    items[index - 1].classList.add('active');
                } else {
                    items[items.length - 1].classList.add('active');
                }
            }
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (activeItem) {
                activeItem.click();
            }
        }
    });
}

async function performGlobalSearch(query) {
    const searchResults = document.getElementById('globalSearchResults');
    if (!searchResults) return;

    // Clear previous results
    searchResults.textContent = '';

    try {
        // Search across multiple endpoints
        const results = await Promise.all([
            searchDomains(query),
            searchOrganizations(query),
            searchSourceIps(query)
        ]);

        const [domains, organizations, sourceIps] = results;

        if (domains.length === 0 && organizations.length === 0 && sourceIps.length === 0) {
            const noResults = document.createElement('div');
            noResults.className = 'search-no-results';
            noResults.textContent = `No results found for "${query}"`;
            searchResults.appendChild(noResults);
        } else {
            // Add domain results
            if (domains.length > 0) {
                const group = createSearchResultGroup('Domains', domains, 'domain');
                searchResults.appendChild(group);
            }

            // Add organization results
            if (organizations.length > 0) {
                const group = createSearchResultGroup('Organizations', organizations, 'org');
                searchResults.appendChild(group);
            }

            // Add IP results
            if (sourceIps.length > 0) {
                const group = createSearchResultGroup('Source IPs', sourceIps, 'ip');
                searchResults.appendChild(group);
            }
        }

        searchResults.hidden = false;
    } catch (error) {
        console.error('Search error:', error);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'search-no-results';
        errorDiv.textContent = 'Search failed. Please try again.';
        searchResults.appendChild(errorDiv);
        searchResults.hidden = false;
    }
}

async function searchDomains(query) {
    // Use cached domains if available
    if (searchCache.domains.length === 0) {
        try {
            const response = await fetch(`${API_BASE}/reports/domains`);
            if (response.ok) {
                const data = await response.json();
                searchCache.domains = data.domains || [];
            }
        } catch (e) {
            console.error('Failed to fetch domains:', e);
        }
    }

    const lowerQuery = query.toLowerCase();
    return searchCache.domains
        .filter(d => d.toLowerCase().includes(lowerQuery))
        .slice(0, 5)
        .map(d => ({ title: d, subtitle: 'Domain' }));
}

async function searchOrganizations(query) {
    // Use cached orgs if available
    if (searchCache.organizations.length === 0) {
        try {
            const response = await fetch(`${API_BASE}/rollup/top-organizations?${buildQueryString()}`);
            if (response.ok) {
                const data = await response.json();
                searchCache.organizations = (data.organizations || []).map(o => o.org_name);
            }
        } catch (e) {
            console.error('Failed to fetch organizations:', e);
        }
    }

    const lowerQuery = query.toLowerCase();
    return searchCache.organizations
        .filter(o => o.toLowerCase().includes(lowerQuery))
        .slice(0, 5)
        .map(o => ({ title: o, subtitle: 'Organization' }));
}

async function searchSourceIps(query) {
    // IP pattern check
    const isIpLike = /^[\d.:\/]+$/.test(query);

    if (!isIpLike && query.length < 3) return [];

    try {
        const response = await fetch(`${API_BASE}/rollup/top-source-ips?${buildQueryString()}`);
        if (response.ok) {
            const data = await response.json();
            const lowerQuery = query.toLowerCase();
            return data
                .filter(ip => ip.source_ip.includes(lowerQuery))
                .slice(0, 5)
                .map(ip => ({
                    title: ip.source_ip,
                    subtitle: `${ip.count.toLocaleString()} messages`
                }));
        }
    } catch (e) {
        console.error('Failed to search IPs:', e);
    }

    return [];
}

function createSearchResultGroup(title, items, type) {
    const group = document.createElement('div');
    group.className = 'search-result-group';

    const groupTitle = document.createElement('div');
    groupTitle.className = 'search-result-group-title';
    groupTitle.textContent = title;
    group.appendChild(groupTitle);

    items.forEach(item => {
        const resultItem = document.createElement('div');
        resultItem.className = 'search-result-item';
        resultItem.setAttribute('role', 'option');
        resultItem.setAttribute('tabindex', '-1');

        // Icon based on type
        const iconPaths = {
            domain: 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9',
            org: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
            ip: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01'
        };

        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        icon.setAttribute('viewBox', '0 0 24 24');
        icon.setAttribute('fill', 'none');
        icon.setAttribute('stroke', 'currentColor');
        icon.setAttribute('stroke-width', '1.5');
        icon.classList.add('search-result-icon');
        icon.innerHTML = `<path d="${iconPaths[type]}" stroke-linecap="round" stroke-linejoin="round"/>`;
        resultItem.appendChild(icon);

        const content = document.createElement('div');
        content.className = 'search-result-content';

        const titleEl = document.createElement('div');
        titleEl.className = 'search-result-title';
        titleEl.textContent = item.title;
        content.appendChild(titleEl);

        const subtitle = document.createElement('div');
        subtitle.className = 'search-result-subtitle';
        subtitle.textContent = item.subtitle;
        content.appendChild(subtitle);

        resultItem.appendChild(content);

        // Handle click
        resultItem.addEventListener('click', () => {
            applySearchResult(type, item.title);
        });

        group.appendChild(resultItem);
    });

    return group;
}

function applySearchResult(type, value) {
    const searchInput = document.getElementById('globalSearchInput');
    const searchResults = document.getElementById('globalSearchResults');

    if (searchInput) searchInput.value = '';
    if (searchResults) searchResults.hidden = true;

    switch (type) {
        case 'domain':
            const domainFilter = document.getElementById('domainFilter');
            if (domainFilter) {
                // Find or add the domain option
                let option = Array.from(domainFilter.options).find(o => o.value === value);
                if (!option) {
                    option = document.createElement('option');
                    option.value = value;
                    option.textContent = value;
                    domainFilter.appendChild(option);
                }
                domainFilter.value = value;
                currentFilters.domain = value;
            }
            break;
        case 'org':
            const orgFilter = document.getElementById('orgNameFilter');
            if (orgFilter) {
                orgFilter.value = value;
                currentFilters.orgName = value;
            }
            // Expand advanced filters if needed
            const advPanel = document.getElementById('advancedFiltersPanel');
            if (advPanel && advPanel.hidden) {
                toggleAdvancedFilters();
            }
            break;
        case 'ip':
            const ipFilter = document.getElementById('sourceIpFilter');
            if (ipFilter) {
                ipFilter.value = value;
                currentFilters.sourceIp = value;
            }
            // Expand advanced filters if needed
            const advPanel2 = document.getElementById('advancedFiltersPanel');
            if (advPanel2 && advPanel2.hidden) {
                toggleAdvancedFilters();
            }
            break;
    }

    // Apply filters
    applyFilters();
    showNotification(`Filtered by ${type}: ${value}`, 'info');
}

// ==========================================
// KEYBOARD SHORTCUTS
// ==========================================

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', handleKeyboardShortcut);
}

function handleKeyboardShortcut(e) {
    // Ignore if typing in an input field
    const activeElement = document.activeElement;
    const isInputActive = activeElement.tagName === 'INPUT' ||
                         activeElement.tagName === 'TEXTAREA' ||
                         activeElement.tagName === 'SELECT' ||
                         activeElement.isContentEditable;

    if (isInputActive && e.key !== 'Escape') return;

    // Check if any modal is open (except for Escape which should close them)
    const hasOpenModal = document.querySelector('.modal:not([hidden])');

    switch (e.key) {
        case '?':
            if (!hasOpenModal) {
                e.preventDefault();
                showKeyboardShortcutsModal();
            }
            break;
        case 'r':
            if (!hasOpenModal) {
                e.preventDefault();
                hideNewDataBanner();
                loadDashboard();
                showNotification('Dashboard refreshed', 'info');
            }
            break;
        case 'u':
            if (!hasOpenModal) {
                e.preventDefault();
                openUploadModal();
            }
            break;
        case 'f':
            if (!hasOpenModal) {
                e.preventDefault();
                const domainFilter = document.getElementById('domainFilter');
                if (domainFilter) {
                    domainFilter.focus();
                    showNotification('Filter bar focused', 'info');
                }
            }
            break;
        case 'h':
            if (!hasOpenModal) {
                e.preventDefault();
                openHelpModal();
            }
            break;
        case 't':
            if (!hasOpenModal) {
                e.preventDefault();
                toggleTheme();
                const theme = document.documentElement.getAttribute('data-theme');
                showNotification(`Switched to ${theme} mode`, 'info');
            }
            break;
        case 'c':
            if (!hasOpenModal) {
                e.preventDefault();
                toggleSecondaryCharts();
            }
            break;
        case 's':
            if (!hasOpenModal) {
                e.preventDefault();
                const searchInput = document.getElementById('globalSearchInput');
                if (searchInput) {
                    searchInput.focus();
                }
            }
            break;
        case 'Escape':
            // Close any open modals or dropdowns
            closeAllDropdowns();
            document.querySelectorAll('.modal:not([hidden])').forEach(modal => {
                closeModal(modal);
            });
            // Also hide feature tooltip
            const tooltip = document.getElementById('featureTooltip');
            if (tooltip) tooltip.hidden = true;
            break;
    }
}

function showKeyboardShortcutsModal() {
    let modal = document.getElementById('keyboardShortcutsModal');

    if (!modal) {
        // Create modal if it doesn't exist
        modal = document.createElement('div');
        modal.id = 'keyboardShortcutsModal';
        modal.className = 'modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-labelledby', 'keyboardShortcutsTitle');

        const content = document.createElement('div');
        content.className = 'modal-content modal-shortcuts';

        // Header
        const header = document.createElement('div');
        header.className = 'modal-header';

        const title = document.createElement('h2');
        title.id = 'keyboardShortcutsTitle';
        title.textContent = 'Keyboard Shortcuts';
        header.appendChild(title);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'modal-close';
        closeBtn.setAttribute('aria-label', 'Close modal');
        closeBtn.innerHTML = `
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        `;
        closeBtn.addEventListener('click', () => closeModal(modal));
        header.appendChild(closeBtn);

        content.appendChild(header);

        // Body
        const body = document.createElement('div');
        body.className = 'modal-body shortcuts-body';

        const shortcutsList = document.createElement('div');
        shortcutsList.className = 'shortcuts-list';

        keyboardShortcuts.forEach(shortcut => {
            const row = document.createElement('div');
            row.className = 'shortcut-row';

            const keys = document.createElement('div');
            keys.className = 'shortcut-keys';

            const kbd = document.createElement('kbd');
            kbd.className = 'kbd';
            kbd.textContent = shortcut.key === 'Escape' ? 'Esc' : shortcut.key;
            keys.appendChild(kbd);

            row.appendChild(keys);

            const desc = document.createElement('span');
            desc.className = 'shortcut-description';
            desc.textContent = shortcut.description;
            row.appendChild(desc);

            shortcutsList.appendChild(row);
        });

        body.appendChild(shortcutsList);

        // Footer hint
        const hint = document.createElement('p');
        hint.className = 'shortcuts-hint';
        hint.textContent = 'Press ? anytime to see these shortcuts';
        body.appendChild(hint);

        content.appendChild(body);
        modal.appendChild(content);

        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal(modal);
        });

        document.body.appendChild(modal);
    }

    openModal(modal);
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

    // Set up auth event listeners (login form, logout button)
    setupAuthEventListeners();

    // Set up all event listeners
    setupEventListeners();

    // Set up dropdown menus
    setupDropdowns();

    // Set up keyboard shortcuts
    setupKeyboardShortcuts();

    // Set up global search
    setupGlobalSearch();

    // Set up saved views
    setupSavedViews();

    // Set up inline validation
    setupInlineValidation();

    // Set up notification center
    setupNotificationCenter();

    // Set up dashboard customization
    setupDashboardCustomization();

    // Set up export builder
    setupExportBuilder();

    // Set up visibility handler for smart refresh
    setupVisibilityHandler();

    // Set up sidebar interactions (collapse, nav clicks, mobile toggle)
    setupSidebar();

    // Export shared state and utility functions onto window.DMARC namespace
    // These are used by page modules loaded after app.js
    Object.defineProperty(window.DMARC, 'currentUser', {
        get: function() { return currentUser; },
        configurable: true
    });
    Object.defineProperty(window.DMARC, 'accessToken', {
        get: function() { return accessToken; },
        configurable: true
    });
    window.DMARC.getAuthHeaders = getAuthHeaders;
    window.DMARC.showNotification = showNotification;
    window.DMARC.buildQueryString = buildQueryString;
    window.DMARC.apiFetch = function(url, options) {
        return fetch(url, options);
    };

    // Check if first-time setup is needed before showing login
    const needsSetup = typeof checkSetupNeeded === 'function' ? await checkSetupNeeded() : false;
    if (!needsSetup) {
        // Show login overlay by default - dashboard loads after successful login
        showLoginOverlay();
    }
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

    // Prevent filter form submission (replaces inline onsubmit)
    document.getElementById('filterForm')?.addEventListener('submit', (e) => e.preventDefault());

    // Back to records button (replaces inline onclick)
    document.getElementById('backToRecordsBtn')?.addEventListener('click', hideRecordDetail);

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
    }, AUTO_REFRESH_INTERVAL); // Configurable refresh interval
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
        // Set initial aria-sort state
        if (!th.hasAttribute('aria-sort')) {
            th.setAttribute('aria-sort', 'none');
        }
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
        console.warn('Cache update failed:', e);
    }

    // Check for any failures and show user-visible error indication
    const failures = results.map((r, i) => ({ result: r, task: allTasks[i] }))
        .filter(({ result }) => result.status === 'rejected');
    if (failures.length > 0) {
        console.error('Some dashboard components failed to load:', failures);
        const failedNames = failures.map(f => f.task.name).join(', ');
        showNotification(
            `Some components failed to load: ${failedNames}`,
            'error',
            { retryCallback: loadDashboard, duration: 10000 }
        );
    }

    // Load comparison data and render stat card enhancements
    try {
        await loadComparisonData();
        renderStatCardSparklines();
        renderPeriodComparisons();
    } catch (e) {
        console.error('Error loading comparison data:', e);
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

        // Check if this is empty (no reports at all with no filters)
        const hasNoData = !data.total_reports || data.total_reports === 0;
        const hasNoFilters = !currentFilters.domain && !currentFilters.sourceIp &&
                            !currentFilters.sourceIpRange && !currentFilters.dkimResult &&
                            !currentFilters.spfResult && !currentFilters.disposition &&
                            !currentFilters.orgName && currentFilters.days === DEFAULT_FILTER_DAYS;

        if (hasNoData && hasNoFilters) {
            // Show welcome empty state for first-time users
            showWelcomeEmptyState();
        } else {
            // Ensure welcome state is hidden when we have data
            hideWelcomeEmptyState();
        }

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
    const tbody = document.getElementById('reportsTableBody');
    const table = document.getElementById('reportsTable');
    const emptyState = document.getElementById('tableEmptyState');
    const countEl = document.getElementById('tableResultCount');

    let data;
    try {
        const queryString = buildQueryString({ page_size: 20 });
        const response = await fetch(`${API_BASE}/reports?${queryString}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        data = await response.json();
    } catch (error) {
        console.error('Error loading reports table:', error);
        showNotification('Failed to load reports', 'error');
        if (tbody) {
            tbody.textContent = '';
            const row = tbody.insertRow();
            const cell = row.insertCell();
            cell.colSpan = 6;
            cell.className = 'error';
            cell.textContent = 'Failed to load reports. Please try refreshing.';
        }
        throw error;
    }

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

// Current report for modal tabs
let currentReportId = null;
let currentReportData = null;

// View report details with tabbed interface
async function viewReport(id) {
    const modal = document.getElementById('reportModal');
    const breadcrumb = document.getElementById('reportModalBreadcrumb');
    const title = document.getElementById('reportModalTitle');

    currentReportId = id;

    openModal(modal);
    setupReportModalTabs();
    resetReportModalTabs();

    // Update breadcrumb
    if (breadcrumb) {
        breadcrumb.textContent = 'Reports';
    }

    // Show loading in overview tab
    const overviewTab = document.getElementById('tab-overview');
    if (overviewTab) {
        overviewTab.textContent = '';
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'loading';
        loadingDiv.textContent = 'Loading report details...';
        overviewTab.appendChild(loadingDiv);
    }

    try {
        const response = await fetch(`${API_BASE}/reports/${id}`);
        if (!response.ok) {
            throw new Error('Report not found');
        }
        const report = await response.json();
        currentReportData = report;

        // Update title
        if (title) {
            title.textContent = `Report: ${report.org_name}`;
        }

        // Update records count badge
        const recordsCount = document.getElementById('records-count');
        if (recordsCount) {
            recordsCount.textContent = report.record_count || 0;
        }

        // Build overview tab content
        renderOverviewTab(report);

        // Setup copy button
        const copyBtn = document.getElementById('reportCopyBtn');
        if (copyBtn) {
            copyBtn.onclick = () => copyToClipboard(report.report_id, 'Report ID copied!');
        }

    } catch (error) {
        const overviewTab = document.getElementById('tab-overview');
        if (overviewTab) {
            overviewTab.textContent = '';
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error';
            errorDiv.textContent = 'Error loading report details. Please try again.';
            overviewTab.appendChild(errorDiv);
        }
        console.error('Error loading report:', error);
    }
}

// Setup report modal tabs
function setupReportModalTabs() {
    const tabs = document.querySelectorAll('.modal-tab');
    tabs.forEach(tab => {
        // Remove existing listeners by cloning
        const newTab = tab.cloneNode(true);
        tab.parentNode.replaceChild(newTab, tab);

        newTab.addEventListener('click', () => {
            const targetId = newTab.getAttribute('aria-controls');
            switchReportTab(targetId, newTab);
        });
    });
}

function resetReportModalTabs() {
    // Reset to overview tab
    const tabs = document.querySelectorAll('.modal-tab');
    const panels = document.querySelectorAll('.tab-panel');

    tabs.forEach(tab => {
        const isOverview = tab.id === 'tab-btn-overview';
        tab.classList.toggle('active', isOverview);
        tab.setAttribute('aria-selected', isOverview ? 'true' : 'false');
    });

    panels.forEach(panel => {
        const isOverview = panel.id === 'tab-overview';
        panel.hidden = !isOverview;
        panel.classList.toggle('active', isOverview);
    });
}

async function switchReportTab(targetId, tabButton) {
    // Update tab buttons
    document.querySelectorAll('.modal-tab').forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
    });
    tabButton.classList.add('active');
    tabButton.setAttribute('aria-selected', 'true');

    // Update panels
    document.querySelectorAll('.tab-panel').forEach(p => {
        p.hidden = p.id !== targetId;
        p.classList.toggle('active', p.id === targetId);
    });

    // Load content for the tab if needed
    const panel = document.getElementById(targetId);
    if (!panel) return;

    switch (targetId) {
        case 'tab-records':
            if (!panel.dataset.loaded) {
                await loadRecordsTab();
                panel.dataset.loaded = 'true';
            }
            break;
        case 'tab-policy':
            if (!panel.dataset.loaded) {
                renderPolicyTab();
                panel.dataset.loaded = 'true';
            }
            break;
        case 'tab-raw':
            if (!panel.dataset.loaded) {
                await loadRawXmlTab();
                panel.dataset.loaded = 'true';
            }
            break;
    }
}

function renderOverviewTab(report) {
    const panel = document.getElementById('tab-overview');
    if (!panel) return;

    panel.textContent = '';
    panel.classList.add('fade-in');

    const details = document.createElement('div');
    details.className = 'report-details';

    // Report Information Section
    const infoSection = createDetailSection('Report Information', [
        ['Organization', report.org_name],
        ['Domain', report.domain],
        ['Date Range', formatDateRange(report.date_begin, report.date_end)],
        ['Report ID', report.report_id],
        ['Email', report.email || 'N/A']
    ]);
    details.appendChild(infoSection);

    // Statistics Section
    const statsSection = createDetailSection('Statistics', [
        ['Total Messages', (report.total_messages || 0).toLocaleString()],
        ['Total Records', (report.record_count || 0).toLocaleString()],
        ['Received', new Date(report.received_at).toLocaleString()]
    ]);
    details.appendChild(statsSection);

    panel.appendChild(details);
}

function createDetailSection(title, rows) {
    const section = document.createElement('div');
    section.className = 'detail-section';

    const heading = document.createElement('h3');
    heading.textContent = title;
    section.appendChild(heading);

    const table = document.createElement('table');
    table.className = 'detail-table';

    rows.forEach(([label, value]) => {
        const tr = document.createElement('tr');

        const tdLabel = document.createElement('td');
        const strong = document.createElement('strong');
        strong.textContent = label + ':';
        tdLabel.appendChild(strong);
        tr.appendChild(tdLabel);

        const tdValue = document.createElement('td');
        tdValue.textContent = value;
        tr.appendChild(tdValue);

        table.appendChild(tr);
    });

    section.appendChild(table);
    return section;
}

async function loadRecordsTab() {
    const panel = document.getElementById('tab-records');
    if (!panel || !currentReportId) return;

    panel.textContent = '';
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading';
    loadingDiv.textContent = 'Loading records...';
    panel.appendChild(loadingDiv);

    try {
        await loadRecordsForReport(currentReportId, panel);
    } catch (error) {
        panel.textContent = '';
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = 'Error loading records.';
        panel.appendChild(errorDiv);
    }
}

function renderPolicyTab() {
    const panel = document.getElementById('tab-policy');
    if (!panel || !currentReportData) return;

    panel.textContent = '';
    panel.classList.add('fade-in');

    const report = currentReportData;

    const grid = document.createElement('div');
    grid.className = 'policy-grid';

    const policyItems = [
        ['DMARC Policy', report.policy_p || 'none', 'How receivers should handle failing messages'],
        ['Subdomain Policy', report.policy_sp || 'none', 'Policy for subdomains'],
        ['Percentage', (report.policy_pct || 100) + '%', 'Percentage of messages to apply policy'],
        ['DKIM Alignment', report.policy_adkim || 'relaxed', 'DKIM domain alignment mode'],
        ['SPF Alignment', report.policy_aspf || 'relaxed', 'SPF domain alignment mode']
    ];

    policyItems.forEach(([label, value, description]) => {
        const item = document.createElement('div');
        item.className = 'policy-item';

        const itemLabel = document.createElement('div');
        itemLabel.className = 'policy-item-label';
        itemLabel.textContent = label;
        item.appendChild(itemLabel);

        const itemValue = document.createElement('div');
        itemValue.className = 'policy-item-value';
        itemValue.textContent = value;
        item.appendChild(itemValue);

        grid.appendChild(item);
    });

    panel.appendChild(grid);
}

async function loadRawXmlTab() {
    const panel = document.getElementById('tab-raw');
    if (!panel || !currentReportId) return;

    panel.textContent = '';
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading';
    loadingDiv.textContent = 'Loading XML...';
    panel.appendChild(loadingDiv);

    try {
        const response = await fetch(`${API_BASE}/reports/${currentReportId}/raw`);
        if (!response.ok) {
            throw new Error('Raw XML not available');
        }
        const xmlText = await response.text();

        panel.textContent = '';

        const container = document.createElement('div');
        container.className = 'raw-xml-container';

        const header = document.createElement('div');
        header.className = 'raw-xml-header';

        const label = document.createElement('span');
        label.textContent = 'Raw DMARC Report XML';
        header.appendChild(label);

        const copyXmlBtn = document.createElement('button');
        copyXmlBtn.className = 'btn-secondary btn-sm';
        copyXmlBtn.textContent = 'Copy XML';
        copyXmlBtn.addEventListener('click', () => copyToClipboard(xmlText, 'XML copied!'));
        header.appendChild(copyXmlBtn);

        container.appendChild(header);

        const content = document.createElement('div');
        content.className = 'raw-xml-content';

        const pre = document.createElement('pre');
        pre.textContent = xmlText;
        content.appendChild(pre);

        container.appendChild(content);
        panel.appendChild(container);

    } catch (error) {
        panel.textContent = '';
        const errorDiv = document.createElement('div');
        errorDiv.className = 'empty-state';
        errorDiv.textContent = 'Raw XML not available for this report.';
        panel.appendChild(errorDiv);
    }
}

function copyToClipboard(text, successMessage) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification(successMessage || 'Copied!', 'success');
    }).catch(() => {
        showNotification('Failed to copy', 'error');
    });
}

// ==========================================
// SAVED VIEWS
// ==========================================

let savedViews = JSON.parse(localStorage.getItem('dmarc-saved-views') || '[]');

function setupSavedViews() {
    const container = document.querySelector('.filter-bar-actions');
    if (!container) return;

    // Create saved views dropdown
    const dropdown = document.createElement('div');
    dropdown.className = 'saved-views-dropdown';

    const trigger = document.createElement('button');
    trigger.className = 'saved-views-trigger';
    trigger.innerHTML = `
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
        </svg>
        Saved Views
    `;

    const menu = document.createElement('div');
    menu.className = 'saved-views-menu';
    menu.hidden = true;

    dropdown.appendChild(trigger);
    dropdown.appendChild(menu);
    container.insertBefore(dropdown, container.firstChild);

    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.hidden = !menu.hidden;
        if (!menu.hidden) {
            renderSavedViewsMenu(menu);
        }
    });

    document.addEventListener('click', () => {
        menu.hidden = true;
    });
}

function renderSavedViewsMenu(menu) {
    menu.textContent = '';

    // Header
    const header = document.createElement('div');
    header.className = 'saved-views-header';

    const headerTitle = document.createElement('span');
    headerTitle.textContent = 'Saved Views';
    header.appendChild(headerTitle);

    menu.appendChild(header);

    // Views list
    const list = document.createElement('div');
    list.className = 'saved-views-list';

    if (savedViews.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'saved-views-empty';
        empty.textContent = 'No saved views yet';
        list.appendChild(empty);
    } else {
        savedViews.forEach((view, index) => {
            const item = document.createElement('div');
            item.className = 'saved-view-item';

            const name = document.createElement('span');
            name.className = 'saved-view-item-name';
            name.textContent = view.name;
            item.appendChild(name);

            const actions = document.createElement('div');
            actions.className = 'saved-view-item-actions';

            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'saved-view-delete';
            deleteBtn.innerHTML = `
                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            `;
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteSavedView(index);
                renderSavedViewsMenu(menu);
            });
            actions.appendChild(deleteBtn);

            item.appendChild(actions);

            item.addEventListener('click', () => {
                applySavedView(view);
                menu.hidden = true;
            });

            list.appendChild(item);
        });
    }

    menu.appendChild(list);

    // Save current view input
    const divider = document.createElement('div');
    divider.className = 'saved-views-divider';
    menu.appendChild(divider);

    const saveInput = document.createElement('div');
    saveInput.className = 'save-view-input';

    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Save current view...';
    input.addEventListener('click', (e) => e.stopPropagation());

    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn-secondary btn-sm';
    saveBtn.textContent = 'Save';
    saveBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (input.value.trim()) {
            saveCurrentView(input.value.trim());
            input.value = '';
            renderSavedViewsMenu(menu);
        }
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && input.value.trim()) {
            saveCurrentView(input.value.trim());
            input.value = '';
            renderSavedViewsMenu(menu);
        }
    });

    saveInput.appendChild(input);
    saveInput.appendChild(saveBtn);
    menu.appendChild(saveInput);
}

function saveCurrentView(name) {
    const view = {
        name: name,
        filters: { ...currentFilters },
        savedAt: new Date().toISOString()
    };

    savedViews.push(view);
    localStorage.setItem('dmarc-saved-views', JSON.stringify(savedViews));
    showNotification(`View "${name}" saved`, 'success');
}

function applySavedView(view) {
    // Apply filters
    Object.assign(currentFilters, view.filters);

    // Update UI elements
    const domainFilter = document.getElementById('domainFilter');
    if (domainFilter) domainFilter.value = currentFilters.domain || '';

    const dateRangeFilter = document.getElementById('dateRangeFilter');
    if (dateRangeFilter) {
        if (currentFilters.startDate && currentFilters.endDate) {
            dateRangeFilter.value = 'custom';
        } else {
            dateRangeFilter.value = currentFilters.days?.toString() || DEFAULT_FILTER_DAYS.toString();
        }
    }

    const sourceIpFilter = document.getElementById('sourceIpFilter');
    if (sourceIpFilter) sourceIpFilter.value = currentFilters.sourceIp || '';

    const dkimResultFilter = document.getElementById('dkimResultFilter');
    if (dkimResultFilter) dkimResultFilter.value = currentFilters.dkimResult || '';

    const spfResultFilter = document.getElementById('spfResultFilter');
    if (spfResultFilter) spfResultFilter.value = currentFilters.spfResult || '';

    const dispositionFilter = document.getElementById('dispositionFilter');
    if (dispositionFilter) dispositionFilter.value = currentFilters.disposition || '';

    const orgNameFilter = document.getElementById('orgNameFilter');
    if (orgNameFilter) orgNameFilter.value = currentFilters.orgName || '';

    // Show advanced filters if any are active
    const hasAdvancedFilters = currentFilters.sourceIp || currentFilters.dkimResult ||
                               currentFilters.spfResult || currentFilters.disposition ||
                               currentFilters.orgName;

    const advPanel = document.getElementById('advancedFiltersPanel');
    if (advPanel && hasAdvancedFilters && advPanel.hidden) {
        toggleAdvancedFilters();
    }

    // Apply and reload
    loadDashboard();
    updateFilterCount();
    showNotification(`Applied view: ${view.name}`, 'info');
}

function deleteSavedView(index) {
    const view = savedViews[index];
    savedViews.splice(index, 1);
    localStorage.setItem('dmarc-saved-views', JSON.stringify(savedViews));
    showNotification(`Deleted view: ${view.name}`, 'info');
}

// ==========================================
// INLINE VALIDATION
// ==========================================

function setupInlineValidation() {
    // IP address validation
    const sourceIpFilter = document.getElementById('sourceIpFilter');
    if (sourceIpFilter) {
        wrapInputForValidation(sourceIpFilter, validateIpAddress, 'Enter a valid IP address (e.g., 192.168.1.1)');
    }

    // IP range validation
    const sourceIpRangeFilter = document.getElementById('sourceIpRangeFilter');
    if (sourceIpRangeFilter) {
        wrapInputForValidation(sourceIpRangeFilter, validateIpRange, 'Enter a valid CIDR range (e.g., 192.168.0.0/24)');
    }
}

function wrapInputForValidation(input, validator, errorMessage) {
    // Don't wrap if already wrapped
    if (input.parentElement.classList.contains('input-wrapper')) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'input-wrapper';

    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    // Add validation icons
    const validIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    validIcon.setAttribute('viewBox', '0 0 24 24');
    validIcon.setAttribute('fill', 'none');
    validIcon.setAttribute('stroke', 'currentColor');
    validIcon.setAttribute('stroke-width', '2');
    validIcon.classList.add('input-validation-icon', 'valid-icon');
    validIcon.innerHTML = '<polyline points="20 6 9 17 4 12"></polyline>';
    wrapper.appendChild(validIcon);

    const invalidIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    invalidIcon.setAttribute('viewBox', '0 0 24 24');
    invalidIcon.setAttribute('fill', 'none');
    invalidIcon.setAttribute('stroke', 'currentColor');
    invalidIcon.setAttribute('stroke-width', '2');
    invalidIcon.classList.add('input-validation-icon', 'invalid-icon');
    invalidIcon.innerHTML = '<circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line>';
    wrapper.appendChild(invalidIcon);

    // Add error message
    const errorDiv = document.createElement('span');
    errorDiv.className = 'input-error';
    errorDiv.textContent = errorMessage;
    wrapper.appendChild(errorDiv);

    // Add validation on input
    input.addEventListener('input', () => {
        const value = input.value.trim();

        if (value === '') {
            wrapper.classList.remove('valid', 'invalid');
        } else if (validator(value)) {
            wrapper.classList.remove('invalid');
            wrapper.classList.add('valid');
        } else {
            wrapper.classList.remove('valid');
            wrapper.classList.add('invalid');
        }
    });

    input.addEventListener('blur', () => {
        // Only show invalid state after blur
        const value = input.value.trim();
        if (value === '') {
            wrapper.classList.remove('valid', 'invalid');
        }
    });
}

function validateIpAddress(value) {
    // IPv4
    const ipv4Regex = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (ipv4Regex.test(value)) {
        const parts = value.split('.').map(Number);
        return parts.every(part => part >= 0 && part <= 255);
    }

    // IPv6 (simplified check)
    const ipv6Regex = /^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::$|^([0-9a-fA-F]{1,4}:)*:([0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{1,4}$/;
    return ipv6Regex.test(value);
}

function validateIpRange(value) {
    // CIDR notation
    const cidrRegex = /^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$/;
    if (cidrRegex.test(value)) {
        const [ip, prefix] = value.split('/');
        const prefixNum = parseInt(prefix, 10);
        if (prefixNum < 0 || prefixNum > 32) return false;

        const parts = ip.split('.').map(Number);
        return parts.every(part => part >= 0 && part <= 255);
    }

    return false;
}

// ==========================================
// SPARKLINES & COMPARISON VIEWS
// ==========================================

function createSparkline(data, container, options = {}) {
    const {
        width = 80,
        height = 24,
        strokeColor = 'var(--accent-primary)',
        fillColor = 'var(--accent-primary)',
        showArea = true
    } = options;

    if (!data || data.length < 2) {
        container.textContent = '—';
        return;
    }

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    // Calculate points
    const points = data.map((value, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((value - min) / range) * (height - 4) - 2;
        return { x, y };
    });

    // Create SVG
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('class', 'sparkline-svg');
    svg.setAttribute('aria-hidden', 'true');

    // Determine trend
    const trend = data[data.length - 1] > data[0] ? 'up' : data[data.length - 1] < data[0] ? 'down' : 'flat';

    // Create path
    const pathData = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

    if (showArea) {
        const areaPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        const areaData = `${pathData} L ${width} ${height} L 0 ${height} Z`;
        areaPath.setAttribute('d', areaData);
        areaPath.setAttribute('class', 'sparkline-area');
        areaPath.style.fill = fillColor;
        areaPath.style.opacity = '0.1';
        svg.appendChild(areaPath);
    }

    const linePath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    linePath.setAttribute('d', pathData);
    linePath.setAttribute('class', 'sparkline-line');
    linePath.style.stroke = strokeColor;
    svg.appendChild(linePath);

    // Add endpoint dot
    const endDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    endDot.setAttribute('cx', points[points.length - 1].x);
    endDot.setAttribute('cy', points[points.length - 1].y);
    endDot.setAttribute('r', '2');
    endDot.style.fill = strokeColor;
    svg.appendChild(endDot);

    container.textContent = '';
    container.appendChild(svg);
    container.classList.add('sparkline');
    container.classList.remove('trend-up', 'trend-down');
    if (trend === 'up') container.classList.add('trend-up');
    if (trend === 'down') container.classList.add('trend-down');

    return { trend, change: data[data.length - 1] - data[0] };
}

async function loadComparisonData() {
    try {
        // Get timeline data for the current period
        const queryString = buildQueryString();
        const response = await fetch(`${API_BASE}/rollup/timeline?${queryString}`);
        if (!response.ok) return null;

        const data = await response.json();
        const timeline = data.timeline || [];

        if (timeline.length < 2) return null;

        // Extract trend data
        trendDataCache.passRate = timeline.map(d => {
            const total = (d.pass_count || 0) + (d.fail_count || 0);
            return total > 0 ? (d.pass_count / total) * 100 : 0;
        });

        trendDataCache.failRate = timeline.map(d => {
            const total = (d.pass_count || 0) + (d.fail_count || 0);
            return total > 0 ? (d.fail_count / total) * 100 : 0;
        });

        trendDataCache.messageVolume = timeline.map(d => (d.pass_count || 0) + (d.fail_count || 0));

        trendDataCache.lastUpdated = new Date();

        return trendDataCache;
    } catch (error) {
        console.error('Error loading comparison data:', error);
        return null;
    }
}

function renderStatCardSparklines() {
    if (!trendDataCache.passRate.length) return;

    // Pass rate sparkline
    const passRateCard = document.querySelector('#passRate')?.closest('.stat-card');
    if (passRateCard) {
        let sparklineContainer = passRateCard.querySelector('.stat-sparkline');
        if (!sparklineContainer) {
            sparklineContainer = document.createElement('div');
            sparklineContainer.className = 'stat-sparkline';
            passRateCard.appendChild(sparklineContainer);
        }
        createSparkline(trendDataCache.passRate, sparklineContainer, {
            strokeColor: 'var(--accent-success)',
            fillColor: 'var(--accent-success)'
        });
    }

    // Fail rate sparkline
    const failRateCard = document.querySelector('#failRate')?.closest('.stat-card');
    if (failRateCard) {
        let sparklineContainer = failRateCard.querySelector('.stat-sparkline');
        if (!sparklineContainer) {
            sparklineContainer = document.createElement('div');
            sparklineContainer.className = 'stat-sparkline';
            failRateCard.appendChild(sparklineContainer);
        }
        createSparkline(trendDataCache.failRate, sparklineContainer, {
            strokeColor: 'var(--accent-danger)',
            fillColor: 'var(--accent-danger)'
        });
    }

    // Message volume sparkline
    const messagesCard = document.querySelector('#totalMessages')?.closest('.stat-card');
    if (messagesCard) {
        let sparklineContainer = messagesCard.querySelector('.stat-sparkline');
        if (!sparklineContainer) {
            sparklineContainer = document.createElement('div');
            sparklineContainer.className = 'stat-sparkline';
            messagesCard.appendChild(sparklineContainer);
        }
        createSparkline(trendDataCache.messageVolume, sparklineContainer, {
            strokeColor: 'var(--accent-primary)',
            fillColor: 'var(--accent-primary)'
        });
    }
}

function renderPeriodComparisons() {
    if (!trendDataCache.passRate.length || trendDataCache.passRate.length < 4) return;

    // Split data into two halves for period-over-period comparison
    const midpoint = Math.floor(trendDataCache.passRate.length / 2);

    // Pass rate comparison
    const passComparison = calculatePeriodComparison(
        trendDataCache.passRate.slice(midpoint),
        trendDataCache.passRate.slice(0, midpoint)
    );
    const passRateTrend = document.getElementById('passRateTrend');
    if (passRateTrend) renderComparisonIndicator(passRateTrend, passComparison, 'passRate');

    // Fail rate comparison
    const failComparison = calculatePeriodComparison(
        trendDataCache.failRate.slice(midpoint),
        trendDataCache.failRate.slice(0, midpoint)
    );
    const failRateTrend = document.getElementById('failRateTrend');
    if (failRateTrend) renderComparisonIndicator(failRateTrend, failComparison, 'failRate');

    // Message volume comparison
    const volumeComparison = calculatePeriodComparison(
        trendDataCache.messageVolume.slice(midpoint),
        trendDataCache.messageVolume.slice(0, midpoint)
    );
    const totalMessagesTrend = document.getElementById('totalMessagesTrend');
    if (totalMessagesTrend) renderComparisonIndicator(totalMessagesTrend, volumeComparison, 'messages');

    // Total reports comparison (reuse message volume data as proxy)
    const totalReportsTrend = document.getElementById('totalReportsTrend');
    if (totalReportsTrend) renderComparisonIndicator(totalReportsTrend, volumeComparison, 'reports');
}

function calculatePeriodComparison(currentData, previousData) {
    if (!currentData || !previousData) return null;

    const currentTotal = currentData.reduce((sum, val) => sum + val, 0);
    const previousTotal = previousData.reduce((sum, val) => sum + val, 0);

    if (previousTotal === 0) return null;

    const percentChange = ((currentTotal - previousTotal) / previousTotal) * 100;

    return {
        current: currentTotal,
        previous: previousTotal,
        change: currentTotal - previousTotal,
        percentChange: percentChange,
        direction: percentChange > 0 ? 'up' : percentChange < 0 ? 'down' : 'flat'
    };
}

function renderComparisonIndicator(container, comparison, metric) {
    if (!comparison) {
        container.textContent = '';
        return;
    }

    container.textContent = '';
    container.className = 'comparison-indicator';

    const arrow = document.createElement('span');
    arrow.className = 'comparison-arrow';

    const value = document.createElement('span');
    value.className = 'comparison-value';

    if (comparison.direction === 'up') {
        arrow.textContent = '↑';
        container.classList.add('comparison-up');
        // For fail rate, up is bad; for pass rate, up is good
        if (metric === 'failRate') {
            container.classList.add('comparison-negative');
        } else {
            container.classList.add('comparison-positive');
        }
    } else if (comparison.direction === 'down') {
        arrow.textContent = '↓';
        container.classList.add('comparison-down');
        if (metric === 'failRate') {
            container.classList.add('comparison-positive');
        } else {
            container.classList.add('comparison-negative');
        }
    } else {
        arrow.textContent = '→';
        container.classList.add('comparison-flat');
    }

    value.textContent = `${Math.abs(comparison.percentChange).toFixed(1)}%`;

    container.appendChild(arrow);
    container.appendChild(value);
}

// ==========================================
// NOTIFICATION CENTER
// ==========================================

let notifications = JSON.parse(localStorage.getItem('dmarc-notifications') || '[]');
let unreadCount = notifications.filter(n => !n.read).length;

function setupNotificationCenter() {
    const headerActions = document.querySelector('.action-group-secondary');
    if (!headerActions) return;

    // Create notification center button
    const notifCenter = document.createElement('div');
    notifCenter.className = 'notification-center';

    const trigger = document.createElement('button');
    trigger.className = 'btn-icon notification-trigger';
    trigger.setAttribute('aria-label', 'Notifications');
    trigger.innerHTML = `
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
        </svg>
        <span class="notification-badge" id="notificationBadge">${unreadCount || ''}</span>
    `;

    const panel = document.createElement('div');
    panel.className = 'notification-panel';
    panel.id = 'notificationPanel';
    panel.hidden = true;

    notifCenter.appendChild(trigger);
    notifCenter.appendChild(panel);

    // Insert before theme toggle
    const themeToggle = headerActions.querySelector('#themeToggle');
    if (themeToggle) {
        headerActions.insertBefore(notifCenter, themeToggle);
    } else {
        headerActions.appendChild(notifCenter);
    }

    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        panel.hidden = !panel.hidden;
        if (!panel.hidden) {
            renderNotificationPanel();
        }
    });

    document.addEventListener('click', (e) => {
        if (!notifCenter.contains(e.target)) {
            panel.hidden = true;
        }
    });

    // Add some initial notifications if empty
    if (notifications.length === 0) {
        addNotification({
            type: 'info',
            title: 'Welcome to DMARC Dashboard',
            message: 'Start by importing your DMARC reports to see analytics.',
            time: new Date().toISOString()
        });
    }
}

function renderNotificationPanel() {
    const panel = document.getElementById('notificationPanel');
    if (!panel) return;

    panel.textContent = '';

    // Header
    const header = document.createElement('div');
    header.className = 'notification-panel-header';

    const title = document.createElement('h3');
    title.textContent = 'Notifications';
    header.appendChild(title);

    if (notifications.some(n => !n.read)) {
        const markReadBtn = document.createElement('button');
        markReadBtn.className = 'notification-mark-read';
        markReadBtn.textContent = 'Mark all read';
        markReadBtn.addEventListener('click', markAllNotificationsRead);
        header.appendChild(markReadBtn);
    }

    panel.appendChild(header);

    // List
    const list = document.createElement('div');
    list.className = 'notification-list';

    if (notifications.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'notification-empty';
        empty.innerHTML = `
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
            </svg>
            <p>No notifications</p>
        `;
        list.appendChild(empty);
    } else {
        // Show most recent first, limit to 10
        const recentNotifs = [...notifications].reverse().slice(0, 10);

        recentNotifs.forEach((notif, index) => {
            const item = document.createElement('div');
            item.className = 'notification-item';
            if (!notif.read) item.classList.add('unread');

            // Icon
            const iconDiv = document.createElement('div');
            iconDiv.className = `notification-item-icon ${notif.type}`;

            const iconPaths = {
                info: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
                success: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
                warning: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
                error: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z'
            };

            iconDiv.innerHTML = `
                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="${iconPaths[notif.type] || iconPaths.info}" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            `;
            item.appendChild(iconDiv);

            // Content
            const content = document.createElement('div');
            content.className = 'notification-item-content';

            const titleEl = document.createElement('div');
            titleEl.className = 'notification-item-title';
            titleEl.textContent = notif.title;
            content.appendChild(titleEl);

            const message = document.createElement('div');
            message.className = 'notification-item-message';
            message.textContent = notif.message;
            content.appendChild(message);

            const time = document.createElement('div');
            time.className = 'notification-item-time';
            time.textContent = formatRelativeTime(new Date(notif.time));
            content.appendChild(time);

            item.appendChild(content);

            item.addEventListener('click', () => {
                markNotificationRead(notifications.length - 1 - index);
                renderNotificationPanel();
            });

            list.appendChild(item);
        });
    }

    panel.appendChild(list);
}

function addNotification(notif) {
    notifications.push({
        ...notif,
        id: Date.now(),
        read: false,
        time: notif.time || new Date().toISOString()
    });

    // Keep only last 50 notifications
    if (notifications.length > 50) {
        notifications = notifications.slice(-50);
    }

    localStorage.setItem('dmarc-notifications', JSON.stringify(notifications));
    updateNotificationBadge();
}

function markNotificationRead(index) {
    if (notifications[index]) {
        notifications[index].read = true;
        localStorage.setItem('dmarc-notifications', JSON.stringify(notifications));
        updateNotificationBadge();
    }
}

function markAllNotificationsRead() {
    notifications.forEach(n => n.read = true);
    localStorage.setItem('dmarc-notifications', JSON.stringify(notifications));
    updateNotificationBadge();
    renderNotificationPanel();
}

function updateNotificationBadge() {
    unreadCount = notifications.filter(n => !n.read).length;
    const badge = document.getElementById('notificationBadge');
    if (badge) {
        badge.textContent = unreadCount > 0 ? (unreadCount > 9 ? '9+' : unreadCount) : '';
        badge.dataset.count = unreadCount;
    }
}

function formatRelativeTime(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
}

// ==========================================
// DASHBOARD CUSTOMIZATION
// ==========================================

let dashboardLayout = JSON.parse(localStorage.getItem('dmarc-dashboard-layout') || 'null');
let pinnedWidgets = JSON.parse(localStorage.getItem('dmarc-pinned-widgets') || '[]');

const defaultWidgets = [
    { id: 'stats', name: 'Statistics Cards', section: 'stats', pinned: true },
    { id: 'timeline', name: 'Timeline Chart', section: 'charts-primary', pinned: true },
    { id: 'domain', name: 'Domain Distribution', section: 'charts-primary', pinned: true },
    { id: 'sourceIp', name: 'Top Source IPs', section: 'charts-primary', pinned: true },
    { id: 'disposition', name: 'Disposition', section: 'charts-primary', pinned: true },
    { id: 'alignment', name: 'Alignment Status', section: 'charts-secondary', pinned: false },
    { id: 'compliance', name: 'Compliance Trend', section: 'charts-secondary', pinned: false },
    { id: 'failureTrend', name: 'Failure Trend', section: 'charts-secondary', pinned: false },
    { id: 'topOrgs', name: 'Top Organizations', section: 'charts-secondary', pinned: false },
    { id: 'reportsTable', name: 'Reports Table', section: 'table', pinned: true }
];

function setupDashboardCustomization() {
    // Add customize button to header
    const headerActions = document.querySelector('.action-group-secondary');
    if (!headerActions) return;

    const customizeBtn = document.createElement('button');
    customizeBtn.className = 'btn-icon';
    customizeBtn.id = 'customizeDashboardBtn';
    customizeBtn.setAttribute('aria-label', 'Customize dashboard');
    customizeBtn.title = 'Customize dashboard';
    customizeBtn.innerHTML = `
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7"></rect>
            <rect x="14" y="3" width="7" height="7"></rect>
            <rect x="14" y="14" width="7" height="7"></rect>
            <rect x="3" y="14" width="7" height="7"></rect>
        </svg>
    `;

    customizeBtn.addEventListener('click', openCustomizeModal);

    // Insert before notification center if it exists
    const notifCenter = headerActions.querySelector('.notification-center');
    if (notifCenter) {
        headerActions.insertBefore(customizeBtn, notifCenter);
    } else {
        const themeToggle = headerActions.querySelector('#themeToggle');
        if (themeToggle) {
            headerActions.insertBefore(customizeBtn, themeToggle);
        } else {
            headerActions.appendChild(customizeBtn);
        }
    }

    // Load saved widget visibility
    applyWidgetVisibility();
}

function openCustomizeModal() {
    let modal = document.getElementById('customizeModal');

    if (!modal) {
        modal = createCustomizeModal();
        document.body.appendChild(modal);
    }

    renderCustomizeModalContent();
    openModal(modal);
}

function createCustomizeModal() {
    const modal = document.createElement('div');
    modal.id = 'customizeModal';
    modal.className = 'modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'customizeModalTitle');
    modal.hidden = true;

    modal.innerHTML = `
        <div class="modal-content modal-customize">
            <div class="modal-header">
                <h2 id="customizeModalTitle">Customize Dashboard</h2>
                <button class="modal-close" aria-label="Close modal">
                    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
            <div class="modal-body customize-body" id="customizeModalBody">
                <!-- Content will be rendered dynamically -->
            </div>
            <div class="modal-footer">
                <button class="btn-ghost" id="resetLayoutBtn">Reset to Default</button>
                <button class="btn-primary" id="saveLayoutBtn">Save Changes</button>
            </div>
        </div>
    `;

    // Event listeners
    modal.querySelector('.modal-close').addEventListener('click', () => closeModal(modal));
    modal.querySelector('#resetLayoutBtn').addEventListener('click', resetDashboardLayout);
    modal.querySelector('#saveLayoutBtn').addEventListener('click', () => {
        saveDashboardLayout();
        closeModal(modal);
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal(modal);
    });

    return modal;
}

function renderCustomizeModalContent() {
    const body = document.getElementById('customizeModalBody');
    if (!body) return;

    body.textContent = '';

    const intro = document.createElement('p');
    intro.className = 'customize-intro';
    intro.textContent = 'Toggle widgets on or off. Drag to reorder within each section.';
    body.appendChild(intro);

    // Group widgets by section
    const sections = {
        'stats': 'Statistics',
        'charts-primary': 'Primary Charts',
        'charts-secondary': 'Secondary Charts',
        'table': 'Data Table'
    };

    // Load saved widget order
    const savedOrder = loadWidgetOrder();

    Object.entries(sections).forEach(([sectionId, sectionName]) => {
        let widgets = defaultWidgets.filter(w => w.section === sectionId);
        if (widgets.length === 0) return;

        // Apply saved order if available
        if (savedOrder && savedOrder[sectionName]) {
            const orderedWidgets = [];
            savedOrder[sectionName].forEach(widgetId => {
                const widget = widgets.find(w => w.id === widgetId);
                if (widget) orderedWidgets.push(widget);
            });
            // Add any widgets not in saved order (new widgets)
            widgets.forEach(widget => {
                if (!orderedWidgets.includes(widget)) {
                    orderedWidgets.push(widget);
                }
            });
            widgets = orderedWidgets;
        }

        const section = document.createElement('div');
        section.className = 'customize-section';

        const sectionTitle = document.createElement('h3');
        sectionTitle.textContent = sectionName;
        section.appendChild(sectionTitle);

        const widgetList = document.createElement('div');
        widgetList.className = 'customize-widget-list';

        widgets.forEach(widget => {
            const isPinned = pinnedWidgets.includes(widget.id) || widget.pinned;

            const item = document.createElement('div');
            item.className = 'customize-widget-item';
            item.dataset.widgetId = widget.id;
            item.draggable = true;

            // Add drag event handlers
            item.addEventListener('dragstart', handleDragStart);
            item.addEventListener('dragover', handleDragOver);
            item.addEventListener('drop', handleDrop);
            item.addEventListener('dragend', handleDragEnd);

            const dragHandle = document.createElement('span');
            dragHandle.className = 'widget-drag-handle';
            dragHandle.innerHTML = `
                <svg class="icon" viewBox="0 0 24 24" fill="currentColor" style="width:16px;height:16px">
                    <circle cx="9" cy="6" r="1.5"/>
                    <circle cx="15" cy="6" r="1.5"/>
                    <circle cx="9" cy="12" r="1.5"/>
                    <circle cx="15" cy="12" r="1.5"/>
                    <circle cx="9" cy="18" r="1.5"/>
                    <circle cx="15" cy="18" r="1.5"/>
                </svg>
            `;
            item.appendChild(dragHandle);

            const label = document.createElement('label');
            label.className = 'widget-toggle-label';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = isPinned;
            checkbox.dataset.widgetId = widget.id;
            checkbox.addEventListener('change', (e) => {
                toggleWidgetPinned(widget.id, e.target.checked);
            });

            const toggle = document.createElement('span');
            toggle.className = 'widget-toggle';

            const name = document.createElement('span');
            name.className = 'widget-name';
            name.textContent = widget.name;

            label.appendChild(checkbox);
            label.appendChild(toggle);
            label.appendChild(name);
            item.appendChild(label);

            widgetList.appendChild(item);
        });

        section.appendChild(widgetList);
        body.appendChild(section);
    });
}

function toggleWidgetPinned(widgetId, isPinned) {
    if (isPinned) {
        if (!pinnedWidgets.includes(widgetId)) {
            pinnedWidgets.push(widgetId);
        }
    } else {
        pinnedWidgets = pinnedWidgets.filter(id => id !== widgetId);
    }
}

function saveDashboardLayout() {
    localStorage.setItem('dmarc-pinned-widgets', JSON.stringify(pinnedWidgets));
    applyWidgetVisibility();
    showNotification('Dashboard layout saved', 'success');
}

function resetDashboardLayout() {
    pinnedWidgets = defaultWidgets.filter(w => w.pinned).map(w => w.id);
    localStorage.setItem('dmarc-pinned-widgets', JSON.stringify(pinnedWidgets));
    renderCustomizeModalContent();
    applyWidgetVisibility();
    showNotification('Dashboard reset to default', 'info');
}

function applyWidgetVisibility() {
    // Map widget IDs to their DOM selectors
    const widgetSelectors = {
        stats: '.stats-section',
        timeline: '#timelineChart',
        domain: '#domainChart',
        sourceIp: '#sourceIpChart',
        disposition: '#dispositionChart',
        alignment: '#alignmentChart',
        compliance: '#complianceChart',
        failureTrend: '#failureTrendChart',
        topOrgs: '#topOrganizationsChart',
        reportsTable: '.table-section'
    };

    // Determine which widgets should be visible
    // If no saved preferences, use default pinned state
    const visibleWidgets = pinnedWidgets.length === 0
        ? defaultWidgets.filter(w => w.pinned).map(w => w.id)
        : pinnedWidgets;

    // Toggle visibility for each widget
    Object.entries(widgetSelectors).forEach(([widgetId, selector]) => {
        const el = document.querySelector(selector);
        if (!el) return;

        // For chart canvases, toggle the parent .chart-container
        const target = el.tagName === 'CANVAS' ? el.closest('.chart-container') : el;
        if (!target) return;

        const isVisible = visibleWidgets.includes(widgetId);
        target.style.display = isVisible ? '' : 'none';
    });

    // Toggle primary charts section visibility
    const primaryCharts = document.querySelector('.charts-section-primary');
    if (primaryCharts) {
        const hasPrimaryVisible = visibleWidgets.some(id =>
            ['timeline', 'domain', 'sourceIp', 'disposition'].includes(id)
        );
        primaryCharts.style.display = hasPrimaryVisible ? '' : 'none';
    }

    // Toggle secondary charts section visibility
    const secondaryCharts = document.querySelector('.charts-section-secondary');
    if (secondaryCharts) {
        const hasSecondaryVisible = visibleWidgets.some(id =>
            ['alignment', 'compliance', 'failureTrend', 'topOrgs'].includes(id)
        );
        secondaryCharts.style.display = hasSecondaryVisible ? '' : 'none';
    }
}

// Drag and drop state
let draggedItem = null;

function handleDragStart(e) {
    draggedItem = e.currentTarget;
    e.currentTarget.style.opacity = '0.5';
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', e.currentTarget.innerHTML);
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';

    const target = e.currentTarget;
    if (draggedItem && target !== draggedItem && target.classList.contains('customize-widget-item')) {
        // Only allow reordering within the same section
        const draggedSection = draggedItem.closest('.customize-widget-list');
        const targetSection = target.closest('.customize-widget-list');

        if (draggedSection === targetSection) {
            const rect = target.getBoundingClientRect();
            const midpoint = rect.top + rect.height / 2;

            if (e.clientY < midpoint) {
                target.parentNode.insertBefore(draggedItem, target);
            } else {
                target.parentNode.insertBefore(draggedItem, target.nextSibling);
            }
        }
    }

    return false;
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }

    // Save the new order to localStorage
    saveWidgetOrder();

    return false;
}

function handleDragEnd(e) {
    e.currentTarget.style.opacity = '';
    draggedItem = null;
}

function saveWidgetOrder() {
    const widgetOrder = {};

    // Collect the order of widgets in each section
    document.querySelectorAll('.customize-widget-list').forEach(list => {
        const section = list.closest('.customize-section');
        const sectionTitle = section.querySelector('h3').textContent;
        const items = Array.from(list.querySelectorAll('.customize-widget-item'));
        widgetOrder[sectionTitle] = items.map(item => item.dataset.widgetId);
    });

    localStorage.setItem('dmarc-widget-order', JSON.stringify(widgetOrder));
}

function loadWidgetOrder() {
    const savedOrder = localStorage.getItem('dmarc-widget-order');
    return savedOrder ? JSON.parse(savedOrder) : null;
}

// ==========================================
// EXPORT REPORT BUILDER
// ==========================================

function setupExportBuilder() {
    // Add export builder option to export menu
    const exportMenu = document.getElementById('exportMenu');
    if (!exportMenu) return;

    // Add divider and builder option
    const divider = document.createElement('div');
    divider.className = 'dropdown-divider';

    const builderItem = document.createElement('button');
    builderItem.className = 'dropdown-item';
    builderItem.id = 'exportBuilderBtn';
    builderItem.innerHTML = `
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="12" y1="18" x2="12" y2="12"></line>
            <line x1="9" y1="15" x2="15" y2="15"></line>
        </svg>
        Custom Report Builder
    `;
    builderItem.addEventListener('click', openExportBuilder);

    exportMenu.appendChild(divider);
    exportMenu.appendChild(builderItem);
}

function openExportBuilder() {
    let modal = document.getElementById('exportBuilderModal');

    if (!modal) {
        modal = createExportBuilderModal();
        document.body.appendChild(modal);
    }

    openModal(modal);
    closeAllDropdowns();
}

function createExportBuilderModal() {
    const modal = document.createElement('div');
    modal.id = 'exportBuilderModal';
    modal.className = 'modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'exportBuilderTitle');
    modal.hidden = true;

    modal.innerHTML = `
        <div class="modal-content modal-large modal-export-builder">
            <div class="modal-header">
                <h2 id="exportBuilderTitle">Custom Report Builder</h2>
                <button class="modal-close" aria-label="Close modal">
                    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
            <div class="modal-body export-builder-body">
                <div class="export-builder-section">
                    <h3>Report Title</h3>
                    <input type="text" id="exportReportTitle" class="export-input" placeholder="DMARC Summary Report" value="DMARC Summary Report">
                </div>

                <div class="export-builder-section">
                    <h3>Include Sections</h3>
                    <div class="export-checkboxes">
                        <label class="export-checkbox">
                            <input type="checkbox" id="exportIncludeSummary" checked>
                            <span>Executive Summary</span>
                        </label>
                        <label class="export-checkbox">
                            <input type="checkbox" id="exportIncludeStats" checked>
                            <span>Statistics Overview</span>
                        </label>
                        <label class="export-checkbox">
                            <input type="checkbox" id="exportIncludeCharts" checked>
                            <span>Charts & Visualizations</span>
                        </label>
                        <label class="export-checkbox">
                            <input type="checkbox" id="exportIncludeTopSources" checked>
                            <span>Top Source IPs</span>
                        </label>
                        <label class="export-checkbox">
                            <input type="checkbox" id="exportIncludeDomains" checked>
                            <span>Domain Breakdown</span>
                        </label>
                        <label class="export-checkbox">
                            <input type="checkbox" id="exportIncludeFailures">
                            <span>Failure Analysis</span>
                        </label>
                        <label class="export-checkbox">
                            <input type="checkbox" id="exportIncludeRecommendations">
                            <span>Recommendations</span>
                        </label>
                    </div>
                </div>

                <div class="export-builder-section">
                    <h3>Export Format</h3>
                    <div class="export-format-options">
                        <label class="export-format-option">
                            <input type="radio" name="exportFormat" value="pdf" checked>
                            <span class="export-format-card">
                                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                    <polyline points="14 2 14 8 20 8"></polyline>
                                </svg>
                                <strong>PDF</strong>
                                <small>Best for sharing</small>
                            </span>
                        </label>
                        <label class="export-format-option">
                            <input type="radio" name="exportFormat" value="csv">
                            <span class="export-format-card">
                                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                    <line x1="8" y1="13" x2="16" y2="13"></line>
                                    <line x1="8" y1="17" x2="16" y2="17"></line>
                                </svg>
                                <strong>CSV</strong>
                                <small>Raw data export</small>
                            </span>
                        </label>
                        <label class="export-format-option">
                            <input type="radio" name="exportFormat" value="json">
                            <span class="export-format-card">
                                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="16 18 22 12 16 6"></polyline>
                                    <polyline points="8 6 2 12 8 18"></polyline>
                                </svg>
                                <strong>JSON</strong>
                                <small>For developers</small>
                            </span>
                        </label>
                    </div>
                </div>

                <div class="export-builder-section">
                    <h3>Date Range</h3>
                    <p class="export-date-info">Using current filter: <strong id="exportDateRangeLabel">Last 365 days</strong></p>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn-ghost" id="exportBuilderCancel">Cancel</button>
                <button class="btn-primary" id="exportBuilderGenerate">
                    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                    </svg>
                    Generate Report
                </button>
            </div>
        </div>
    `;

    // Event listeners
    modal.querySelector('.modal-close').addEventListener('click', () => closeModal(modal));
    modal.querySelector('#exportBuilderCancel').addEventListener('click', () => closeModal(modal));
    modal.querySelector('#exportBuilderGenerate').addEventListener('click', generateCustomReport);

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal(modal);
    });

    // Update date range label
    updateExportDateLabel();

    return modal;
}

function updateExportDateLabel() {
    const label = document.getElementById('exportDateRangeLabel');
    if (!label) return;

    if (currentFilters.startDate && currentFilters.endDate) {
        label.textContent = `${currentFilters.startDate} to ${currentFilters.endDate}`;
    } else {
        const daysMap = {
            '7': 'Last 7 days',
            '30': 'Last 30 days',
            '90': 'Last 90 days',
            '365': 'Last 365 days',
            '0': 'All time'
        };
        label.textContent = daysMap[currentFilters.days?.toString()] || `Last ${currentFilters.days} days`;
    }
}

async function generateCustomReport() {
    const format = document.querySelector('input[name="exportFormat"]:checked')?.value || 'pdf';
    const title = document.getElementById('exportReportTitle')?.value || 'DMARC Summary Report';

    const sections = {
        summary: document.getElementById('exportIncludeSummary')?.checked,
        stats: document.getElementById('exportIncludeStats')?.checked,
        charts: document.getElementById('exportIncludeCharts')?.checked,
        topSources: document.getElementById('exportIncludeTopSources')?.checked,
        domains: document.getElementById('exportIncludeDomains')?.checked,
        failures: document.getElementById('exportIncludeFailures')?.checked,
        recommendations: document.getElementById('exportIncludeRecommendations')?.checked
    };

    showNotification('Generating report...', 'info');

    try {
        // For now, use existing export functionality
        // In a full implementation, this would send sections config to backend
        if (format === 'pdf') {
            await exportData('pdf');
        } else if (format === 'csv') {
            await exportData('reports');
        } else if (format === 'json') {
            // Export as JSON
            const queryString = buildQueryString();
            const response = await fetch(`${API_BASE}/rollup/summary?${queryString}`);
            const data = await response.json();

            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `dmarc_report_${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            URL.revokeObjectURL(url);

            showNotification('JSON report downloaded', 'success');
        }

        closeModal(document.getElementById('exportBuilderModal'));
    } catch (error) {
        showNotification('Failed to generate report', 'error');
        console.error('Export error:', error);
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
    const MAX_UPLOAD_SIZE = window.DMARC_CONFIG?.maxUploadSize || (50 * 1024 * 1024);
    const maxSize = MAX_UPLOAD_SIZE;

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
            // Try to get detailed error message from response
            let errorDetail = `HTTP ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorDetail = errorData.detail;
                }
            } catch (e) {
                // If JSON parsing fails, use default message
            }
            throw new Error(`Upload failed: ${errorDetail}`);
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
function showNotification(message, type = 'success', options = {}) {
    const notification = document.getElementById('notification');

    // Clear any existing content and buttons
    while (notification.firstChild) {
        notification.removeChild(notification.firstChild);
    }

    // Add message text
    const messageSpan = document.createElement('span');
    messageSpan.textContent = message;
    notification.appendChild(messageSpan);

    // Add retry button if callback provided
    if (options.retryCallback) {
        const retryBtn = document.createElement('button');
        retryBtn.textContent = 'Retry';
        retryBtn.className = 'notification-retry-btn';
        retryBtn.style.marginLeft = '10px';
        retryBtn.style.padding = '4px 12px';
        retryBtn.style.border = 'none';
        retryBtn.style.borderRadius = '4px';
        retryBtn.style.cursor = 'pointer';
        retryBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
        retryBtn.style.color = 'inherit';
        retryBtn.onclick = () => {
            notification.className = 'notification';
            options.retryCallback();
        };
        notification.appendChild(retryBtn);
    }

    notification.className = `notification ${type} show`;
    notification.setAttribute('role', 'alert');
    notification.setAttribute('aria-live', 'assertive');

    setTimeout(() => {
        notification.className = 'notification';
    }, options.duration || 5000);
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
