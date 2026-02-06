/**
 * DMARC Dashboard - Page Module Template
 *
 * Copy this file and rename it for new pages.
 * Each page module follows the init/load/destroy pattern and registers
 * itself with the DMARC Router.
 *
 * Usage:
 *   1. Copy this file to frontend/js/modules/your-page.js
 *   2. Rename PageTemplate to your page name (e.g., AlertsPage)
 *   3. Update the page-id to match the HTML section id (e.g., 'alerts')
 *   4. Add a <script> tag in index.html before the router init
 *   5. Add a <section id="page-your-page" class="page-section" hidden> in index.html
 *
 * Available globals via window.DMARC:
 *   - DMARC.currentUser   - Current user object {username, role, ...}
 *   - DMARC.accessToken   - Current JWT access token
 *   - DMARC.apiFetch(url, options) - Fetch wrapper with auth headers
 *   - DMARC.showNotification(message, type) - Show toast notification
 *   - DMARC.getAuthHeaders() - Get {Authorization: 'Bearer ...'} headers
 *   - DMARC.buildQueryString(params) - Build URL query string from filters
 *   - DMARC.Router - Router instance for navigation
 */
(function() {
    'use strict';

    const PageTemplate = {
        initialized: false,
        containerId: 'page-template', // Change to match your section id

        /**
         * Initialize the page. Called once on first navigation.
         * Set up DOM elements, event listeners, and static UI.
         */
        init() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            // Build page structure using safe DOM methods
            var header = document.createElement('div');
            header.className = 'page-header';

            var h1 = document.createElement('h1');
            h1.textContent = 'Page Title';
            header.appendChild(h1);

            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Description of this page.';
            header.appendChild(desc);

            var body = document.createElement('div');
            body.className = 'page-body';

            var p = document.createElement('p');
            p.textContent = 'Page content goes here.';
            body.appendChild(p);

            container.appendChild(header);
            container.appendChild(body);

            // Bind event listeners
            // e.g., container.querySelector('.my-button').addEventListener('click', this.handleClick.bind(this));
        },

        /**
         * Load page data. Called every time the page is navigated to.
         * Fetch data from API and render.
         */
        load() {
            // Example API call:
            // var DMARC = window.DMARC;
            // fetch('/api/your-endpoint', { headers: DMARC.getAuthHeaders() })
            //     .then(r => r.json())
            //     .then(data => this.render(data))
            //     .catch(err => DMARC.showNotification('Failed to load data', 'error'));
        },

        /**
         * Render data into the page.
         * @param {object} data - API response data
         */
        render(data) {
            // Update DOM with data using safe DOM methods (textContent, createElement, etc.)
        },

        /**
         * Cleanup when navigating away. Called before another page loads.
         * Remove intervals, abort pending requests, etc.
         */
        destroy() {
            // Clean up any intervals, event listeners on window/document, etc.
        }
    };

    // Expose the module
    window.DMARC = window.DMARC || {};
    window.DMARC.PageTemplate = PageTemplate;

    // Register with router (uncomment and update page name):
    // if (window.DMARC.Router) {
    //     window.DMARC.Router.register('template', PageTemplate);
    // }
})();
