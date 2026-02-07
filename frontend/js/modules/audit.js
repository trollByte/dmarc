/**
 * DMARC Dashboard - Audit Log Module (admin only)
 *
 * Full page (#page-audit-log) with:
 *   - Summary stats cards (total events, unique users, top action, events today)
 *   - Filters: user, action type, resource type, date range
 *   - Log table with expandable details
 *   - CSV export
 *   - API usage sub-tab with Chart.js charts
 */
(function() {
    'use strict';

    var API_BASE = '/api';
    var ACTION_TYPES = ['login', 'create', 'update', 'delete', 'export'];
    var RESOURCE_TYPES = ['report', 'user', 'alert', 'view', 'scheduled_report', 'api_key'];

    var AuditPage = {
        initialized: false,
        containerId: 'page-audit-log',
        filters: {
            user_id: '',
            action: '',
            resource_type: '',
            days: 30
        },
        currentOffset: 0,
        limit: 50,
        activeTab: 'logs',
        charts: {},

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            var self = this;

            // Page header
            var header = document.createElement('div');
            header.className = 'page-header';
            var headerRow = document.createElement('div');
            headerRow.style.cssText = 'display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;';

            var headerLeft = document.createElement('div');
            var h1 = document.createElement('h1');
            h1.textContent = 'Audit Log';
            headerLeft.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Track user actions, API usage, and security events.';
            headerLeft.appendChild(desc);
            headerRow.appendChild(headerLeft);

            var exportBtn = document.createElement('button');
            exportBtn.className = 'btn-secondary';
            exportBtn.textContent = 'Export CSV';
            exportBtn.addEventListener('click', function() {
                self._exportCSV();
            });
            headerRow.appendChild(exportBtn);

            header.appendChild(headerRow);
            container.appendChild(header);

            // Tabs
            var tabBar = document.createElement('div');
            tabBar.style.cssText = 'display: flex; gap: 0; border-bottom: 2px solid var(--border-color); margin-bottom: 24px;';

            var logsTab = document.createElement('button');
            logsTab.className = 'btn-ghost';
            logsTab.id = 'auditTabLogs';
            logsTab.textContent = 'Activity Log';
            logsTab.style.cssText = 'border-bottom: 2px solid var(--accent-primary); margin-bottom: -2px; border-radius: 0; font-weight: 600;';
            logsTab.addEventListener('click', function() {
                self.activeTab = 'logs';
                self._updateTabs();
            });
            tabBar.appendChild(logsTab);

            var apiTab = document.createElement('button');
            apiTab.className = 'btn-ghost';
            apiTab.id = 'auditTabApi';
            apiTab.textContent = 'Security Events';
            apiTab.style.cssText = 'border-bottom: 2px solid transparent; margin-bottom: -2px; border-radius: 0;';
            apiTab.addEventListener('click', function() {
                self.activeTab = 'api';
                self._updateTabs();
            });
            tabBar.appendChild(apiTab);

            container.appendChild(tabBar);

            // Body
            var body = document.createElement('div');
            body.className = 'page-body';
            body.id = 'auditBody';
            container.appendChild(body);
        },

        load: function() {
            this._updateTabs();
        },

        _updateTabs: function() {
            var logsTab = document.getElementById('auditTabLogs');
            var apiTab = document.getElementById('auditTabApi');
            if (logsTab) {
                logsTab.style.borderBottomColor = this.activeTab === 'logs' ? 'var(--accent-primary)' : 'transparent';
                logsTab.style.fontWeight = this.activeTab === 'logs' ? '600' : '400';
            }
            if (apiTab) {
                apiTab.style.borderBottomColor = this.activeTab === 'api' ? 'var(--accent-primary)' : 'transparent';
                apiTab.style.fontWeight = this.activeTab === 'api' ? '600' : '400';
            }

            if (this.activeTab === 'logs') {
                this._loadLogsTab();
            } else {
                this._loadApiTab();
            }
        },

        // ---- Activity Logs Tab ----

        _loadLogsTab: function() {
            var body = document.getElementById('auditBody');
            if (!body) return;
            var self = this;

            body.textContent = '';
            var loadingDiv = document.createElement('div');
            loadingDiv.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
            loadingDiv.textContent = 'Loading audit data...';
            body.appendChild(loadingDiv);

            // Load summary and logs in parallel
            Promise.all([
                fetch(API_BASE + '/audit/stats?days=' + this.filters.days).then(function(r) { return r.ok ? r.json() : null; }),
                this._fetchLogs()
            ]).then(function(results) {
                body.textContent = '';
                self._renderSummaryCards(body, results[0]);
                self._renderFilters(body);
                self._renderLogTable(body, results[1]);
            }).catch(function() {
                body.textContent = '';
                var errDiv = document.createElement('div');
                errDiv.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
                errDiv.textContent = 'Failed to load audit data.';
                body.appendChild(errDiv);
            });
        },

        _fetchLogs: function() {
            var params = new URLSearchParams();
            if (this.filters.user_id) params.append('user_id', this.filters.user_id);
            if (this.filters.action) params.append('action', this.filters.action);
            if (this.filters.resource_type) params.append('resource_type', this.filters.resource_type);
            params.append('days', this.filters.days);
            params.append('limit', this.limit);
            params.append('offset', this.currentOffset);
            return fetch(API_BASE + '/audit/logs?' + params.toString()).then(function(r) { return r.ok ? r.json() : []; });
        },

        _renderSummaryCards: function(body, summary) {
            var statsGrid = document.createElement('div');
            statsGrid.className = 'stats-grid';
            statsGrid.style.marginBottom = '24px';

            var topAction = '-';
            if (summary && summary.by_action) {
                var maxCount = 0;
                Object.keys(summary.by_action).forEach(function(key) {
                    if (summary.by_action[key] > maxCount) {
                        maxCount = summary.by_action[key];
                        topAction = key;
                    }
                });
            }

            var cards = [
                { label: 'Total Events', value: summary ? (summary.total_events || 0).toLocaleString() : '-' },
                { label: 'Period (days)', value: summary ? (summary.period_days || 0).toLocaleString() : '-' },
                { label: 'Top Action', value: topAction },
                { label: 'Failed Logins', value: summary ? (summary.failed_logins || 0).toLocaleString() : '-' }
            ];

            var self = this;
            cards.forEach(function(card) {
                var div = document.createElement('div');
                div.className = 'stat-card';
                var headerDiv = document.createElement('div');
                headerDiv.className = 'stat-header';
                var h3 = document.createElement('h3');
                h3.textContent = card.label;
                headerDiv.appendChild(h3);
                div.appendChild(headerDiv);
                var contentDiv = document.createElement('div');
                contentDiv.className = 'stat-content';
                var valueDiv = document.createElement('div');
                valueDiv.className = 'stat-value';
                valueDiv.textContent = card.value;
                contentDiv.appendChild(valueDiv);
                div.appendChild(contentDiv);
                statsGrid.appendChild(div);
            });

            body.appendChild(statsGrid);
        },

        _renderFilters: function(body) {
            var self = this;
            var filterBar = document.createElement('div');
            filterBar.style.cssText = 'display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 20px; padding: 16px; background: var(--bg-tertiary); border-radius: 8px;';

            // Action filter
            filterBar.appendChild(this._createFilterSelect('Action', 'auditActionFilter', ACTION_TYPES, this.filters.action));

            // Resource type filter
            filterBar.appendChild(this._createFilterSelect('Resource', 'auditResourceFilter', RESOURCE_TYPES, this.filters.resource_type));

            // Days filter
            filterBar.appendChild(this._createFilterSelect('Period', 'auditDaysFilter', [
                {value: '7', label: 'Last 7 days'},
                {value: '30', label: 'Last 30 days'},
                {value: '90', label: 'Last 90 days'}
            ], String(this.filters.days)));

            // Apply
            var applyBtn = document.createElement('button');
            applyBtn.className = 'btn-primary btn-sm';
            applyBtn.textContent = 'Apply';
            applyBtn.style.marginBottom = '0';
            applyBtn.addEventListener('click', function() {
                self.filters.action = (document.getElementById('auditActionFilter') || {}).value || '';
                self.filters.resource_type = (document.getElementById('auditResourceFilter') || {}).value || '';
                self.filters.days = parseInt((document.getElementById('auditDaysFilter') || {}).value || '30', 10);
                self.currentOffset = 0;
                self._loadLogsTab();
            });
            filterBar.appendChild(applyBtn);

            body.appendChild(filterBar);
        },

        _createFilterSelect: function(label, id, options, currentValue) {
            var group = document.createElement('div');
            group.style.cssText = 'display: flex; flex-direction: column; gap: 4px;';
            var lbl = document.createElement('label');
            lbl.style.cssText = 'font-size: 0.75rem; font-weight: 500; color: var(--text-secondary);';
            lbl.textContent = label;
            group.appendChild(lbl);
            var select = document.createElement('select');
            select.id = id;
            select.style.cssText = 'padding: 6px 10px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary); font-size: 0.85rem;';
            var allOpt = document.createElement('option');
            allOpt.value = '';
            allOpt.textContent = 'All';
            select.appendChild(allOpt);
            options.forEach(function(opt) {
                var o = document.createElement('option');
                if (typeof opt === 'string') {
                    o.value = opt;
                    o.textContent = opt.charAt(0).toUpperCase() + opt.slice(1);
                } else {
                    o.value = opt.value;
                    o.textContent = opt.label;
                }
                if ((typeof opt === 'string' ? opt : opt.value) === currentValue) o.selected = true;
                select.appendChild(o);
            });
            group.appendChild(select);
            return group;
        },

        _renderLogTable: function(body, logs) {
            var self = this;
            var items = Array.isArray(logs) ? logs : [];

            if (items.length === 0) {
                var empty = document.createElement('div');
                empty.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
                empty.textContent = 'No audit log entries match your filters.';
                body.appendChild(empty);
                return;
            }

            var table = document.createElement('table');
            table.style.width = '100%';
            var thead = document.createElement('thead');
            var headerRow = document.createElement('tr');
            ['Timestamp', 'User', 'Action', 'Resource', 'Details', 'IP Address'].forEach(function(text) {
                var th = document.createElement('th');
                th.setAttribute('scope', 'col');
                th.textContent = text;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);

            var tbody = document.createElement('tbody');
            items.forEach(function(entry) {
                var tr = document.createElement('tr');

                // Timestamp
                var tdTime = document.createElement('td');
                tdTime.style.cssText = 'font-size: 0.85rem; white-space: nowrap;';
                tdTime.textContent = entry.created_at ? new Date(entry.created_at).toLocaleString() : '';
                tr.appendChild(tdTime);

                // User
                var tdUser = document.createElement('td');
                tdUser.textContent = entry.username || 'System';
                tr.appendChild(tdUser);

                // Action
                var tdAction = document.createElement('td');
                var actionBadge = document.createElement('span');
                var badgeClass = 'badge-gray';
                if (entry.action === 'create') badgeClass = 'badge-success';
                else if (entry.action === 'delete') badgeClass = 'badge-danger';
                else if (entry.action === 'update') badgeClass = 'badge-info';
                else if (entry.action === 'login') badgeClass = 'badge-primary';
                else if (entry.action === 'export') badgeClass = 'badge-warning';
                actionBadge.className = 'badge ' + badgeClass;
                actionBadge.textContent = entry.action || '';
                tdAction.appendChild(actionBadge);
                tr.appendChild(tdAction);

                // Resource
                var tdResource = document.createElement('td');
                tdResource.style.fontSize = '0.85rem';
                var resourceText = (entry.resource_type || '');
                if (entry.resource_id) resourceText += ' #' + entry.resource_id;
                tdResource.textContent = resourceText;
                tr.appendChild(tdResource);

                // Details (expandable)
                var tdDetails = document.createElement('td');
                tdDetails.style.cssText = 'max-width: 250px; font-size: 0.8rem; color: var(--text-secondary);';
                if (entry.details) {
                    var detailText = typeof entry.details === 'string' ? entry.details : JSON.stringify(entry.details);
                    if (detailText.length > 60) {
                        var shortText = document.createElement('span');
                        shortText.textContent = detailText.substring(0, 60) + '...';
                        shortText.style.cursor = 'pointer';
                        shortText.title = detailText;
                        shortText.addEventListener('click', function() {
                            if (shortText.textContent.length <= 63) {
                                shortText.textContent = detailText;
                            } else {
                                shortText.textContent = detailText.substring(0, 60) + '...';
                            }
                        });
                        tdDetails.appendChild(shortText);
                    } else {
                        tdDetails.textContent = detailText;
                    }
                } else {
                    tdDetails.textContent = '-';
                }
                tr.appendChild(tdDetails);

                // IP
                var tdIp = document.createElement('td');
                tdIp.style.cssText = 'font-size: 0.85rem; font-family: monospace;';
                tdIp.textContent = entry.ip_address || '-';
                tr.appendChild(tdIp);

                tbody.appendChild(tr);
            });

            table.appendChild(tbody);

            var tableWrapper = document.createElement('div');
            tableWrapper.className = 'table-container';
            tableWrapper.appendChild(table);
            body.appendChild(tableWrapper);

            // Pagination
            if (items.length >= this.limit || this.currentOffset > 0) {
                var pag = document.createElement('div');
                pag.style.cssText = 'display: flex; justify-content: center; gap: 8px; margin-top: 16px;';

                if (this.currentOffset > 0) {
                    var prevBtn = document.createElement('button');
                    prevBtn.className = 'btn-secondary btn-sm';
                    prevBtn.textContent = 'Previous';
                    prevBtn.addEventListener('click', function() {
                        self.currentOffset = Math.max(0, self.currentOffset - self.limit);
                        self._loadLogsTab();
                    });
                    pag.appendChild(prevBtn);
                }

                var pageInfo = document.createElement('span');
                pageInfo.style.cssText = 'display: flex; align-items: center; font-size: 0.85rem; color: var(--text-secondary);';
                pageInfo.textContent = 'Showing ' + (this.currentOffset + 1) + '-' + (this.currentOffset + items.length);
                pag.appendChild(pageInfo);

                if (items.length >= this.limit) {
                    var nextBtn = document.createElement('button');
                    nextBtn.className = 'btn-secondary btn-sm';
                    nextBtn.textContent = 'Next';
                    nextBtn.addEventListener('click', function() {
                        self.currentOffset += self.limit;
                        self._loadLogsTab();
                    });
                    pag.appendChild(nextBtn);
                }

                body.appendChild(pag);
            }
        },

        _exportCSV: function() {
            var url = API_BASE + '/audit/export/csv?days=' + this.filters.days;
            var a = document.createElement('a');
            a.href = url;
            a.download = 'audit-log.csv';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            if (typeof showNotification === 'function') {
                showNotification('Downloading audit log CSV...', 'info');
            }
        },

        // ---- Security Events Tab ----

        _loadApiTab: function() {
            var body = document.getElementById('auditBody');
            if (!body) return;
            var self = this;

            body.textContent = '';
            var loadingDiv = document.createElement('div');
            loadingDiv.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
            loadingDiv.textContent = 'Loading security events...';
            body.appendChild(loadingDiv);

            fetch(API_BASE + '/audit/security?days=' + this.filters.days)
                .then(function(r) { return r.ok ? r.json() : null; })
                .then(function(data) {
                    body.textContent = '';
                    if (!data) {
                        var errDiv = document.createElement('div');
                        errDiv.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
                        errDiv.textContent = 'Failed to load security events.';
                        body.appendChild(errDiv);
                        return;
                    }
                    var events = Array.isArray(data) ? data : [];
                    self._renderSecurityEvents(body, events);
                })
                .catch(function() {
                    body.textContent = '';
                    var errDiv = document.createElement('div');
                    errDiv.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
                    errDiv.textContent = 'Failed to load security events.';
                    body.appendChild(errDiv);
                });
        },

        _renderSecurityEvents: function(body, events) {
            // Summary stat
            var statDiv = document.createElement('div');
            statDiv.className = 'stat-card';
            statDiv.style.cssText = 'display: inline-block; margin-bottom: 24px;';
            var statHeader = document.createElement('div');
            statHeader.className = 'stat-header';
            var statH3 = document.createElement('h3');
            statH3.textContent = 'Security Events';
            statHeader.appendChild(statH3);
            statDiv.appendChild(statHeader);
            var statContent = document.createElement('div');
            statContent.className = 'stat-content';
            var statValue = document.createElement('div');
            statValue.className = 'stat-value';
            statValue.textContent = events.length.toLocaleString();
            statContent.appendChild(statValue);
            statDiv.appendChild(statContent);
            body.appendChild(statDiv);

            if (events.length === 0) {
                var empty = document.createElement('div');
                empty.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
                empty.textContent = 'No security events found in this period.';
                body.appendChild(empty);
                return;
            }

            var table = document.createElement('table');
            table.style.width = '100%';
            var thead = document.createElement('thead');
            var headerRow = document.createElement('tr');
            ['Timestamp', 'Action', 'Category', 'User', 'IP Address', 'Description'].forEach(function(text) {
                var th = document.createElement('th');
                th.setAttribute('scope', 'col');
                th.textContent = text;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);

            var tbody = document.createElement('tbody');
            events.forEach(function(entry) {
                var tr = document.createElement('tr');

                var tdTime = document.createElement('td');
                tdTime.style.cssText = 'font-size: 0.85rem; white-space: nowrap;';
                tdTime.textContent = entry.created_at ? new Date(entry.created_at).toLocaleString() : '';
                tr.appendChild(tdTime);

                var tdAction = document.createElement('td');
                var actionBadge = document.createElement('span');
                var badgeClass = 'badge-gray';
                if (entry.action && entry.action.indexOf('fail') !== -1) badgeClass = 'badge-danger';
                else if (entry.action && entry.action.indexOf('lock') !== -1) badgeClass = 'badge-warning';
                else if (entry.action && entry.action.indexOf('password') !== -1) badgeClass = 'badge-info';
                actionBadge.className = 'badge ' + badgeClass;
                actionBadge.textContent = entry.action || '';
                tdAction.appendChild(actionBadge);
                tr.appendChild(tdAction);

                var tdCategory = document.createElement('td');
                tdCategory.style.fontSize = '0.85rem';
                tdCategory.textContent = entry.category || '';
                tr.appendChild(tdCategory);

                var tdUser = document.createElement('td');
                tdUser.textContent = entry.username || 'System';
                tr.appendChild(tdUser);

                var tdIp = document.createElement('td');
                tdIp.style.cssText = 'font-size: 0.85rem; font-family: monospace;';
                tdIp.textContent = entry.ip_address || '-';
                tr.appendChild(tdIp);

                var tdDesc = document.createElement('td');
                tdDesc.style.cssText = 'max-width: 250px; font-size: 0.8rem; color: var(--text-secondary);';
                tdDesc.textContent = entry.description || '-';
                tdDesc.title = entry.description || '';
                tr.appendChild(tdDesc);

                tbody.appendChild(tr);
            });

            table.appendChild(tbody);

            var tableWrapper = document.createElement('div');
            tableWrapper.className = 'table-container';
            tableWrapper.appendChild(table);
            body.appendChild(tableWrapper);
        },

        destroy: function() {
            // Destroy charts
            var self = this;
            Object.keys(this.charts).forEach(function(key) {
                if (self.charts[key]) {
                    self.charts[key].destroy();
                    self.charts[key] = null;
                }
            });
        }
    };

    // Expose module
    window.DMARC = window.DMARC || {};
    window.DMARC.AuditPage = AuditPage;

    // Register with router
    if (window.DMARC.Router) {
        window.DMARC.Router.register('audit-log', AuditPage);
    }
})();
