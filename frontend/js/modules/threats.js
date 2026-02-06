/**
 * DMARC Dashboard - Threat Intelligence Page Module
 * IP threat lookup, high-threat IP table, enriched anomalies, cache management.
 *
 * Security: All dynamic content is sanitized via _esc() which uses
 * textContent-to-innerHTML conversion to prevent XSS.
 */
(function() {
    'use strict';

    var API_BASE = '/api';

    /**
     * Escape HTML to prevent XSS - creates a text node and extracts safe HTML.
     * @param {string} text - Raw text to escape
     * @returns {string} HTML-safe string
     */
    function esc(text) {
        var div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    /**
     * Create a DOM element from a tag name with optional properties.
     * @param {string} tag
     * @param {object} props - attributes and textContent
     * @param {Array} children - child elements
     * @returns {HTMLElement}
     */
    function el(tag, props, children) {
        var elem = document.createElement(tag);
        if (props) {
            Object.keys(props).forEach(function(key) {
                if (key === 'textContent') {
                    elem.textContent = props[key];
                } else if (key === 'className') {
                    elem.className = props[key];
                } else if (key === 'hidden') {
                    elem.hidden = props[key];
                } else if (key === 'style') {
                    elem.setAttribute('style', props[key]);
                } else {
                    elem.setAttribute(key, props[key]);
                }
            });
        }
        if (children) {
            children.forEach(function(child) {
                if (typeof child === 'string') {
                    elem.appendChild(document.createTextNode(child));
                } else if (child) {
                    elem.appendChild(child);
                }
            });
        }
        return elem;
    }

    function levelClass(level) {
        var l = (level || '').toLowerCase();
        if (l === 'critical') return 'critical';
        if (l === 'high') return 'high';
        if (l === 'medium') return 'medium';
        if (l === 'low') return 'low';
        return 'none';
    }

    function scoreColor(score) {
        if (score >= 80) return '#e74c3c';
        if (score >= 60) return '#e67e22';
        if (score >= 40) return '#f39c12';
        if (score >= 20) return '#27ae60';
        return '#95a5a6';
    }

    function countryFlag(code) {
        if (!code || code.length !== 2) return '';
        var c = code.toUpperCase();
        return String.fromCodePoint(0x1F1E6 + c.charCodeAt(0) - 65) +
               String.fromCodePoint(0x1F1E6 + c.charCodeAt(1) - 65);
    }

    /**
     * Build a stat field row using safe DOM methods.
     * @returns {HTMLElement}
     */
    function buildField(label, value) {
        var wrapper = el('div', { className: 'threat-field' });
        wrapper.appendChild(el('span', { className: 'threat-label', textContent: label }));
        wrapper.appendChild(el('span', { className: 'threat-value', textContent: String(value) }));
        return wrapper;
    }

    var ThreatIntelPage = {
        initialized: false,
        highThreatData: [],
        sortField: 'abuse_score',
        sortDir: 'desc',
        minScore: 50,

        init: function() {
            if (this.initialized) return;
            this.initialized = true;
            this._buildPage();
            this._bindEvents();
        },

        load: function() {
            this._loadCacheStats();
            this._loadHighThreatIPs();
            this._loadEnrichedAnomalies();
        },

        destroy: function() {
            // Nothing to clean up
        },

        _buildPage: function() {
            var section = document.getElementById('page-threats');
            if (!section) return;

            // Clear existing content
            section.textContent = '';

            var page = el('div', { className: 'threat-intel-page' });

            // Page title
            page.appendChild(el('h2', { className: 'page-title', textContent: 'Threat Intelligence' }));

            // Stats cards
            var statsGrid = el('div', { className: 'threat-stats-grid' });

            var cards = [
                { id: 'threatCachedIPs', title: 'Cached IPs', cls: '' },
                { id: 'threatHighCount', title: 'High-Threat IPs', cls: ' stat-card-danger' },
                { id: 'threatAPIStatus', title: 'API Status', cls: '' },
                { id: 'threatCacheBreakdown', title: 'Cache Breakdown', cls: '' }
            ];

            cards.forEach(function(card) {
                var sc = el('div', { className: 'stat-card' + card.cls });
                var hdr = el('div', { className: 'stat-header' });
                hdr.appendChild(el('h3', { textContent: card.title }));
                sc.appendChild(hdr);
                var content = el('div', { className: 'stat-content' });
                var valCls = card.id === 'threatCacheBreakdown' ? 'stat-value-sm' : 'stat-value';
                content.appendChild(el('div', { id: card.id, className: valCls, textContent: '-' }));
                sc.appendChild(content);
                statsGrid.appendChild(sc);
            });
            page.appendChild(statsGrid);

            // IP Lookup section
            var lookupSection = el('div', { className: 'threat-section' });
            lookupSection.appendChild(el('h3', { textContent: 'IP Lookup' }));
            var lookupBar = el('div', { className: 'threat-lookup-bar' });
            lookupBar.appendChild(el('input', {
                type: 'text', id: 'threatIPInput', className: 'threat-ip-input',
                placeholder: 'Enter IP address (e.g. 192.168.1.1)', autocomplete: 'off'
            }));
            lookupBar.appendChild(el('button', { id: 'threatLookupBtn', className: 'btn-primary', textContent: 'Check IP' }));
            lookupSection.appendChild(lookupBar);
            lookupSection.appendChild(el('div', { id: 'threatLookupResult', className: 'threat-lookup-result', hidden: true }));
            page.appendChild(lookupSection);

            // High-Threat IPs Table
            var tableSection = el('div', { className: 'threat-section' });
            var tableSectionHeader = el('div', { className: 'threat-section-header' });
            tableSectionHeader.appendChild(el('h3', { textContent: 'High-Threat IPs' }));
            var filterBar = el('div', { className: 'threat-filter-bar' });
            filterBar.appendChild(el('label', { 'for': 'threatMinScore', textContent: 'Min Score: ' }));
            filterBar.appendChild(el('input', {
                type: 'range', id: 'threatMinScore', min: '0', max: '100', value: '50',
                className: 'threat-score-slider'
            }));
            filterBar.appendChild(el('span', { id: 'threatMinScoreLabel', textContent: '50' }));
            tableSectionHeader.appendChild(filterBar);
            tableSection.appendChild(tableSectionHeader);

            var tableContainer = el('div', { className: 'table-container' });
            var table = el('table', { id: 'threatTable', className: 'threat-table' });
            var thead = el('thead');
            var headerRow = el('tr');
            var columns = [
                { sort: 'ip_address', label: 'IP Address' },
                { sort: 'threat_level', label: 'Threat Level' },
                { sort: 'abuse_score', label: 'Abuse Score' },
                { sort: 'total_reports', label: 'Reports' },
                { sort: null, label: 'ISP' },
                { sort: 'country_code', label: 'Country' },
                { sort: null, label: 'Categories' }
            ];
            columns.forEach(function(col) {
                var attrs = { textContent: col.label };
                if (col.sort) {
                    attrs.className = 'sortable';
                    attrs['data-sort'] = col.sort;
                }
                headerRow.appendChild(el('th', attrs));
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);
            var tbody = el('tbody', { id: 'threatTableBody' });
            var loadingRow = el('tr');
            loadingRow.appendChild(el('td', { className: 'loading', textContent: 'Loading...', colspan: '7' }));
            tbody.appendChild(loadingRow);
            table.appendChild(tbody);
            tableContainer.appendChild(table);
            tableSection.appendChild(tableContainer);
            page.appendChild(tableSection);

            // Enriched Anomalies
            var anomalySection = el('div', { className: 'threat-section' });
            anomalySection.appendChild(el('h3', { textContent: 'Enriched Anomalies' }));
            anomalySection.appendChild(el('p', { className: 'threat-section-desc', textContent: 'Combined ML anomaly detection + threat intelligence data' }));
            var anomalyGrid = el('div', { id: 'threatAnomalies', className: 'threat-anomalies-grid' });
            anomalyGrid.appendChild(el('div', { className: 'loading', textContent: 'Loading anomalies...' }));
            anomalySection.appendChild(anomalyGrid);
            page.appendChild(anomalySection);

            // Admin Section
            var adminSection = el('div', { id: 'threatAdminSection', className: 'threat-section threat-admin', hidden: true });
            adminSection.appendChild(el('h3', { textContent: 'Cache Management' }));
            adminSection.appendChild(el('button', { id: 'threatPurgeBtn', className: 'btn-danger', textContent: 'Purge Expired Cache' }));
            page.appendChild(adminSection);

            section.appendChild(page);

            // Show admin section for admins
            var user = window.DMARC && window.DMARC.currentUser;
            if (user && user.role === 'admin') {
                adminSection.hidden = false;
            }
        },

        _bindEvents: function() {
            var self = this;

            // IP lookup
            var lookupBtn = document.getElementById('threatLookupBtn');
            var ipInput = document.getElementById('threatIPInput');
            if (lookupBtn) {
                lookupBtn.addEventListener('click', function() { self._lookupIP(); });
            }
            if (ipInput) {
                ipInput.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') self._lookupIP();
                });
            }

            // Min score slider
            var slider = document.getElementById('threatMinScore');
            var sliderLabel = document.getElementById('threatMinScoreLabel');
            if (slider) {
                slider.addEventListener('input', function() {
                    if (sliderLabel) sliderLabel.textContent = slider.value;
                    self.minScore = parseInt(slider.value, 10);
                    self._loadHighThreatIPs();
                });
            }

            // Table sorting
            var table = document.getElementById('threatTable');
            if (table) {
                table.addEventListener('click', function(e) {
                    var th = e.target.closest('th[data-sort]');
                    if (!th) return;
                    var field = th.dataset.sort;
                    if (self.sortField === field) {
                        self.sortDir = self.sortDir === 'asc' ? 'desc' : 'asc';
                    } else {
                        self.sortField = field;
                        self.sortDir = 'desc';
                    }
                    self._renderHighThreatTable();
                });
            }

            // Purge cache
            var purgeBtn = document.getElementById('threatPurgeBtn');
            if (purgeBtn) {
                purgeBtn.addEventListener('click', function() {
                    if (confirm('Are you sure you want to purge expired cache entries?')) {
                        self._purgeCache();
                    }
                });
            }
        },

        _lookupIP: async function() {
            var input = document.getElementById('threatIPInput');
            var resultDiv = document.getElementById('threatLookupResult');
            if (!input || !resultDiv) return;

            var ip = input.value.trim();
            if (!ip) return;

            // Basic IP validation
            if (!/^[\d.:a-fA-F]+$/.test(ip)) {
                resultDiv.textContent = '';
                resultDiv.appendChild(el('div', { className: 'threat-error', textContent: 'Invalid IP address format' }));
                resultDiv.hidden = false;
                return;
            }

            resultDiv.textContent = '';
            resultDiv.appendChild(el('div', { className: 'loading', textContent: 'Checking...' }));
            resultDiv.hidden = false;

            try {
                var response = await fetch(API_BASE + '/threat-intel/check/' + encodeURIComponent(ip) + '?use_cache=true');
                if (!response.ok) throw new Error('HTTP ' + response.status);
                var data = await response.json();
                resultDiv.textContent = '';
                resultDiv.appendChild(this._buildLookupResult(data));
            } catch (err) {
                resultDiv.textContent = '';
                resultDiv.appendChild(el('div', { className: 'threat-error', textContent: 'Failed to look up IP: ' + err.message }));
            }
        },

        /**
         * Build lookup result card using safe DOM construction.
         * @param {object} data - API response
         * @returns {HTMLElement}
         */
        _buildLookupResult: function(data) {
            var card = el('div', { className: 'threat-result-card' });

            // Header: IP + badge
            var header = el('div', { className: 'threat-result-header' });
            header.appendChild(el('span', { className: 'threat-ip-label', textContent: data.ip_address || '' }));
            header.appendChild(el('span', {
                className: 'badge threat-badge-' + levelClass(data.threat_level),
                textContent: data.threat_level || 'unknown'
            }));
            card.appendChild(header);

            var body = el('div', { className: 'threat-result-body' });

            // Abuse score bar
            var scoreRow = el('div', { className: 'threat-result-row' });
            scoreRow.appendChild(el('span', { className: 'threat-label', textContent: 'Abuse Score' }));
            var barWrap = el('div', { className: 'threat-score-bar-wrap' });
            barWrap.appendChild(el('div', {
                className: 'threat-score-bar',
                style: 'width:' + (data.abuse_score || 0) + '%;background:' + scoreColor(data.abuse_score || 0)
            }));
            scoreRow.appendChild(barWrap);
            scoreRow.appendChild(el('span', { className: 'threat-score-val', textContent: (data.abuse_score || 0) + '/100' }));
            body.appendChild(scoreRow);

            // Detail fields grid
            var grid = el('div', { className: 'threat-result-grid' });
            grid.appendChild(buildField('Total Reports', data.total_reports || 0));
            grid.appendChild(buildField('Last Reported', data.last_reported ? new Date(data.last_reported).toLocaleDateString() : 'N/A'));
            grid.appendChild(buildField('ISP', data.isp || 'N/A'));
            grid.appendChild(buildField('Domain', data.domain || 'N/A'));
            grid.appendChild(buildField('Country', countryFlag(data.country_code) + ' ' + (data.country_code || 'N/A')));
            grid.appendChild(buildField('Usage Type', data.usage_type || 'N/A'));
            grid.appendChild(buildField('Whitelisted', data.is_whitelisted ? 'Yes' : 'No'));
            grid.appendChild(buildField('Tor Exit', data.is_tor ? 'Yes' : 'No'));
            grid.appendChild(buildField('Public', data.is_public ? 'Yes' : 'No'));
            grid.appendChild(buildField('Source', data.source || 'N/A'));
            body.appendChild(grid);

            // Categories
            if (data.categories && data.categories.length > 0) {
                var catDiv = el('div', { className: 'threat-categories' });
                catDiv.appendChild(el('span', { className: 'threat-label', textContent: 'Categories' }));
                data.categories.forEach(function(c) {
                    catDiv.appendChild(el('span', { className: 'threat-tag', textContent: c }));
                });
                body.appendChild(catDiv);
            }

            // Cached at
            if (data.cached_at) {
                body.appendChild(el('div', { className: 'threat-cached-at', textContent: 'Cached: ' + new Date(data.cached_at).toLocaleString() }));
            }

            card.appendChild(body);
            return card;
        },

        _loadCacheStats: async function() {
            try {
                var response = await fetch(API_BASE + '/threat-intel/cache/stats');
                if (!response.ok) throw new Error('HTTP ' + response.status);
                var data = await response.json();

                var cachedEl = document.getElementById('threatCachedIPs');
                var apiEl = document.getElementById('threatAPIStatus');
                var breakdownEl = document.getElementById('threatCacheBreakdown');

                if (cachedEl) cachedEl.textContent = (data.active_entries || 0).toLocaleString();
                if (apiEl) {
                    apiEl.textContent = data.api_configured ? 'Configured' : 'Not Configured';
                    apiEl.style.color = data.api_configured ? 'var(--accent-success)' : 'var(--accent-warning)';
                }
                if (breakdownEl && data.breakdown_by_level) {
                    breakdownEl.textContent = '';
                    var levels = ['critical', 'high', 'medium', 'low', 'none'];
                    var hasSome = false;
                    levels.forEach(function(level) {
                        if (data.breakdown_by_level[level]) {
                            breakdownEl.appendChild(el('span', {
                                className: 'threat-badge-' + levelClass(level) + ' badge-sm',
                                textContent: level + ': ' + data.breakdown_by_level[level]
                            }));
                            breakdownEl.appendChild(document.createTextNode(' '));
                            hasSome = true;
                        }
                    });
                    if (!hasSome) breakdownEl.textContent = 'No data';
                }
            } catch (err) {
                console.error('Failed to load cache stats:', err);
            }
        },

        _loadHighThreatIPs: async function() {
            try {
                var response = await fetch(API_BASE + '/threat-intel/high-threat?min_score=' + this.minScore + '&limit=50');
                if (!response.ok) throw new Error('HTTP ' + response.status);
                var data = await response.json();
                this.highThreatData = Array.isArray(data) ? data : [];

                var countEl = document.getElementById('threatHighCount');
                if (countEl) countEl.textContent = this.highThreatData.length;

                this._renderHighThreatTable();
            } catch (err) {
                console.error('Failed to load high-threat IPs:', err);
                var tbody = document.getElementById('threatTableBody');
                if (tbody) {
                    tbody.textContent = '';
                    var row = el('tr');
                    row.appendChild(el('td', { colspan: '7', className: 'threat-error', textContent: 'Failed to load data' }));
                    tbody.appendChild(row);
                }
            }
        },

        _renderHighThreatTable: function() {
            var tbody = document.getElementById('threatTableBody');
            if (!tbody) return;

            var data = this.highThreatData.slice();
            var field = this.sortField;
            var dir = this.sortDir;

            data.sort(function(a, b) {
                var va = a[field];
                var vb = b[field];
                if (va == null) va = '';
                if (vb == null) vb = '';
                if (typeof va === 'number' && typeof vb === 'number') {
                    return dir === 'asc' ? va - vb : vb - va;
                }
                va = String(va).toLowerCase();
                vb = String(vb).toLowerCase();
                if (va < vb) return dir === 'asc' ? -1 : 1;
                if (va > vb) return dir === 'asc' ? 1 : -1;
                return 0;
            });

            // Update sort indicators
            var headers = document.querySelectorAll('#threatTable th[data-sort]');
            for (var h = 0; h < headers.length; h++) {
                headers[h].classList.remove('sort-asc', 'sort-desc');
                if (headers[h].dataset.sort === field) {
                    headers[h].classList.add(dir === 'asc' ? 'sort-asc' : 'sort-desc');
                }
            }

            tbody.textContent = '';

            if (data.length === 0) {
                var emptyRow = el('tr');
                emptyRow.appendChild(el('td', { colspan: '7', className: 'threat-empty', textContent: 'No high-threat IPs found above score ' + this.minScore }));
                tbody.appendChild(emptyRow);
                return;
            }

            var self = this;
            data.forEach(function(item) {
                var row = el('tr');

                // IP link
                var ipCell = el('td');
                var ipBtn = el('button', { className: 'btn-link threat-ip-link', textContent: item.ip_address || '' });
                ipBtn.addEventListener('click', function() {
                    var ipInput = document.getElementById('threatIPInput');
                    if (ipInput) ipInput.value = item.ip_address;
                    self._lookupIP();
                    var inputEl = document.getElementById('threatIPInput');
                    if (inputEl) inputEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                });
                ipCell.appendChild(ipBtn);
                row.appendChild(ipCell);

                // Threat level badge
                var levelCell = el('td');
                levelCell.appendChild(el('span', {
                    className: 'badge threat-badge-' + levelClass(item.threat_level),
                    textContent: item.threat_level || ''
                }));
                row.appendChild(levelCell);

                // Abuse score bar
                var scoreCell = el('td');
                var miniWrap = el('div', { className: 'threat-score-bar-mini-wrap' });
                miniWrap.appendChild(el('div', {
                    className: 'threat-score-bar-mini',
                    style: 'width:' + (item.abuse_score || 0) + '%;background:' + scoreColor(item.abuse_score || 0)
                }));
                scoreCell.appendChild(miniWrap);
                scoreCell.appendChild(document.createTextNode(' ' + (item.abuse_score || 0)));
                row.appendChild(scoreCell);

                // Reports
                row.appendChild(el('td', { textContent: String(item.total_reports || 0) }));

                // ISP
                row.appendChild(el('td', { textContent: item.isp || '-' }));

                // Country
                row.appendChild(el('td', { textContent: countryFlag(item.country_code) + ' ' + (item.country_code || '-') }));

                // Categories
                var catCell = el('td');
                if (item.categories && item.categories.length > 0) {
                    item.categories.forEach(function(c) {
                        catCell.appendChild(el('span', { className: 'threat-tag-sm', textContent: c }));
                        catCell.appendChild(document.createTextNode(' '));
                    });
                } else {
                    catCell.textContent = '-';
                }
                row.appendChild(catCell);

                tbody.appendChild(row);
            });
        },

        _loadEnrichedAnomalies: async function() {
            var container = document.getElementById('threatAnomalies');
            if (!container) return;

            try {
                var response = await fetch(API_BASE + '/threat-intel/enrich-anomalies?days=7&limit=20');
                if (!response.ok) throw new Error('HTTP ' + response.status);
                var data = await response.json();
                var items = Array.isArray(data) ? data : [];

                container.textContent = '';

                if (items.length === 0) {
                    container.appendChild(el('div', { className: 'threat-empty', textContent: 'No enriched anomalies found' }));
                    return;
                }

                var self = this;
                items.forEach(function(item) {
                    var riskScore = item.combined_risk_score || 0;
                    var riskColor = scoreColor(riskScore);
                    var threatInfo = item.threat_info || {};

                    var card = el('div', { className: 'threat-anomaly-card' });

                    // Header
                    var header = el('div', { className: 'threat-anomaly-header' });
                    var ipBtn = el('button', { className: 'btn-link threat-ip-link', textContent: item.ip_address || '' });
                    ipBtn.addEventListener('click', function() {
                        var ipInput = document.getElementById('threatIPInput');
                        if (ipInput) ipInput.value = item.ip_address;
                        self._lookupIP();
                        var inputEl = document.getElementById('threatIPInput');
                        if (inputEl) inputEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    });
                    header.appendChild(ipBtn);
                    header.appendChild(el('span', {
                        className: 'badge threat-badge-' + levelClass(threatInfo.threat_level),
                        textContent: threatInfo.threat_level || 'unknown'
                    }));
                    card.appendChild(header);

                    // Scores
                    var scores = el('div', { className: 'threat-anomaly-scores' });

                    var riskItem = el('div', { className: 'threat-score-item' });
                    riskItem.appendChild(el('span', { className: 'threat-label', textContent: 'Combined Risk' }));
                    var riskBarWrap = el('div', { className: 'threat-score-bar-wrap' });
                    riskBarWrap.appendChild(el('div', {
                        className: 'threat-score-bar',
                        style: 'width:' + riskScore + '%;background:' + riskColor
                    }));
                    riskItem.appendChild(riskBarWrap);
                    riskItem.appendChild(el('span', { className: 'threat-score-val', textContent: riskScore.toFixed(0) }));
                    scores.appendChild(riskItem);

                    var anomalyItem = el('div', { className: 'threat-score-item' });
                    anomalyItem.appendChild(el('span', { className: 'threat-label', textContent: 'Anomaly Score' }));
                    anomalyItem.appendChild(el('span', { className: 'threat-score-val', textContent: (item.anomaly_score || 0).toFixed(2) }));
                    scores.appendChild(anomalyItem);

                    card.appendChild(scores);

                    // Risk factors
                    if (item.risk_factors && item.risk_factors.length > 0) {
                        var rfDiv = el('div', { className: 'threat-risk-factors' });
                        rfDiv.appendChild(el('span', { className: 'threat-label', textContent: 'Risk Factors' }));
                        var ul = el('ul');
                        item.risk_factors.forEach(function(f) {
                            ul.appendChild(el('li', { textContent: f }));
                        });
                        rfDiv.appendChild(ul);
                        card.appendChild(rfDiv);
                    }

                    // Expand button and detail
                    var detailDiv = el('div', { className: 'threat-anomaly-detail', hidden: true });
                    var detailGrid = el('div', { className: 'threat-result-grid' });
                    detailGrid.appendChild(buildField('Abuse Score', threatInfo.abuse_score || 'N/A'));
                    detailGrid.appendChild(buildField('Total Reports', threatInfo.total_reports || 'N/A'));
                    detailGrid.appendChild(buildField('ISP', threatInfo.isp || 'N/A'));
                    detailGrid.appendChild(buildField('Country', countryFlag(threatInfo.country_code) + ' ' + (threatInfo.country_code || 'N/A')));
                    detailDiv.appendChild(detailGrid);

                    var expandBtn = el('button', { className: 'btn-ghost btn-sm threat-expand-btn', textContent: 'Show details' });
                    expandBtn.addEventListener('click', function() {
                        var isHidden = detailDiv.hidden;
                        detailDiv.hidden = !isHidden;
                        expandBtn.textContent = isHidden ? 'Hide details' : 'Show details';
                    });
                    card.appendChild(expandBtn);
                    card.appendChild(detailDiv);

                    container.appendChild(card);
                });
            } catch (err) {
                console.error('Failed to load enriched anomalies:', err);
                container.textContent = '';
                container.appendChild(el('div', { className: 'threat-error', textContent: 'Failed to load anomaly data' }));
            }
        },

        _purgeCache: async function() {
            try {
                var response = await fetch(API_BASE + '/threat-intel/cache/purge', { method: 'POST' });
                if (!response.ok) throw new Error('HTTP ' + response.status);
                if (typeof showNotification === 'function') {
                    showNotification('Cache purged successfully', 'success');
                }
                this._loadCacheStats();
            } catch (err) {
                if (typeof showNotification === 'function') {
                    showNotification('Failed to purge cache: ' + err.message, 'error');
                }
            }
        }
    };

    // Register with router
    window.DMARC = window.DMARC || {};
    window.DMARC.ThreatIntelPage = ThreatIntelPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('threats', ThreatIntelPage);
    }
})();
