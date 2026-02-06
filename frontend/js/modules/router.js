/**
 * DMARC Dashboard - Hash-based Router
 * Manages page navigation, shows/hides page sections, and highlights active nav items.
 */
(function() {
    'use strict';

    const Router = {
        currentPage: null,
        pages: {},
        defaultPage: 'dashboard',
        initialized: false,

        /**
         * Register a page module with the router.
         * @param {string} name - Page identifier (matches hash and section id)
         * @param {object} module - Module with init(), load(), destroy() methods
         */
        register(name, module) {
            this.pages[name] = {
                module: module,
                initialized: false
            };
        },

        /**
         * Initialize the router. Call after login.
         */
        init() {
            if (this.initialized) return;
            this.initialized = true;

            // Listen for hash changes (back/forward navigation)
            window.addEventListener('hashchange', () => this._onHashChange());

            // Navigate to the current hash or default page
            const hash = window.location.hash.replace('#', '') || this.defaultPage;
            this.navigate(hash, true);
        },

        /**
         * Navigate to a page.
         * @param {string} pageName - The page to navigate to
         * @param {boolean} replace - If true, replace history entry instead of pushing
         */
        navigate(pageName, replace) {
            // Validate page exists as a section in the DOM
            const section = document.getElementById('page-' + pageName);
            if (!section) {
                // Fallback to default page
                pageName = this.defaultPage;
            }

            // Check admin-only pages
            const adminPages = ['users', 'audit-log', 'webhooks', 'retention'];
            if (adminPages.indexOf(pageName) !== -1) {
                const user = window.DMARC && window.DMARC.currentUser;
                if (!user || user.role !== 'admin') {
                    pageName = this.defaultPage;
                }
            }

            // Destroy current page if it has a destroy method
            if (this.currentPage && this.pages[this.currentPage]) {
                const current = this.pages[this.currentPage];
                if (current.module && typeof current.module.destroy === 'function') {
                    current.module.destroy();
                }
            }

            // Hide all page sections
            const sections = document.querySelectorAll('.page-section');
            sections.forEach(function(s) { s.hidden = true; });

            // Show the target section
            const targetSection = document.getElementById('page-' + pageName);
            if (targetSection) {
                targetSection.hidden = false;
            }

            // Update sidebar active state
            this._updateActiveNav(pageName);

            // Update hash without triggering hashchange if using replace
            if (replace) {
                history.replaceState(null, '', '#' + pageName);
            } else if (window.location.hash !== '#' + pageName) {
                history.pushState(null, '', '#' + pageName);
            }

            this.currentPage = pageName;

            // Initialize and load the page module if registered
            if (this.pages[pageName]) {
                const page = this.pages[pageName];
                if (!page.initialized && page.module && typeof page.module.init === 'function') {
                    page.module.init();
                    page.initialized = true;
                }
                if (page.module && typeof page.module.load === 'function') {
                    page.module.load();
                }
            }
        },

        /**
         * Handle hash change events (browser back/forward).
         */
        _onHashChange() {
            const hash = window.location.hash.replace('#', '') || this.defaultPage;
            if (hash !== this.currentPage) {
                this.navigate(hash, true);
            }
        },

        /**
         * Update the active state in sidebar navigation.
         * @param {string} pageName - The active page name
         */
        _updateActiveNav(pageName) {
            // Remove active class from all sidebar items
            var items = document.querySelectorAll('.sidebar-item');
            items.forEach(function(item) {
                item.classList.remove('active');
            });

            // Add active class to the matching item
            var activeItem = document.querySelector('.sidebar-item[data-page="' + pageName + '"]');
            if (activeItem) {
                activeItem.classList.add('active');
            }
        },

        /**
         * Get current page name.
         */
        getCurrentPage() {
            return this.currentPage;
        },

        /**
         * Reset router state (e.g., on logout).
         */
        reset() {
            this.currentPage = null;
            this.initialized = false;
            // Reset initialization state for all pages
            Object.keys(this.pages).forEach(function(key) {
                this.pages[key].initialized = false;
            }.bind(this));
        }
    };

    // Expose on window.DMARC namespace
    window.DMARC = window.DMARC || {};
    window.DMARC.Router = Router;
})();
