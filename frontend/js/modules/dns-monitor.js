/**
 * DMARC Dashboard - DNS Monitor Page Module
 * Monitors DNS record changes (DMARC, SPF, DKIM, MX) for tracked domains.
 */
(function() {
    'use strict';

    var API_BASE = '/api';

    function clearChildren(el) {
        while (el.firstChild) el.removeChild(el.firstChild);
    }

    var DnsMonitorPage = {
        initialized: false,
        containerId: 'page-dns-monitor',
        domains: [],
        changes: [],

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            // Page header
            var header = document.createElement('div');
            header.className = 'page-header';
            var h1 = document.createElement('h1');
            h1.textContent = 'DNS Monitor';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Track DNS record changes for your domains. Monitor DMARC, SPF, DKIM, and MX records.';
            header.appendChild(desc);
            container.appendChild(header);

            var body = document.createElement('div');
            body.className = 'page-body';
            body.id = 'dns-monitor-body';

            // --- Monitored Domains Section ---
            var domainsSection = document.createElement('div');
            domainsSection.className = 'table-container';

            var domainsHeader = document.createElement('div');
            domainsHeader.className = 'table-header';
            var domainsTitle = document.createElement('h2');
            domainsTitle.textContent = 'Monitored Domains';
            domainsHeader.appendChild(domainsTitle);

            var headerActions = document.createElement('div');
            headerActions.style.cssText = 'display:flex;gap:8px;align-items:center;';

            var checkAllBtn = document.createElement('button');
            checkAllBtn.className = 'btn-secondary btn-sm';
            checkAllBtn.textContent = 'Check All';
            checkAllBtn.id = 'dns-check-all-btn';
            checkAllBtn.addEventListener('click', this._onCheckAll.bind(this));
            headerActions.appendChild(checkAllBtn);

            var addBtn = document.createElement('button');
            addBtn.className = 'btn-primary btn-sm';
            addBtn.textContent = 'Add Domain';
            addBtn.id = 'dns-add-domain-btn';
            addBtn.addEventListener('click', this._showAddModal.bind(this));
            headerActions.appendChild(addBtn);

            domainsHeader.appendChild(headerActions);
            domainsSection.appendChild(domainsHeader);

            var domainsTable = document.createElement('table');
            domainsTable.id = 'dns-domains-table';
            var thead = document.createElement('thead');
            var headRow = document.createElement('tr');
            ['Domain', 'Status', 'Monitors', 'Last Checked', 'Actions'].forEach(function(text) {
                var th = document.createElement('th');
                th.setAttribute('scope', 'col');
                th.textContent = text;
                headRow.appendChild(th);
            });
            thead.appendChild(headRow);
            domainsTable.appendChild(thead);

            var domainsBody = document.createElement('tbody');
            domainsBody.id = 'dns-domains-tbody';
            var loadingRow = document.createElement('tr');
            var loadingCell = document.createElement('td');
            loadingCell.colSpan = 5;
            loadingCell.className = 'loading';
            loadingCell.textContent = 'Loading domains...';
            loadingRow.appendChild(loadingCell);
            domainsBody.appendChild(loadingRow);
            domainsTable.appendChild(domainsBody);
            domainsSection.appendChild(domainsTable);
            body.appendChild(domainsSection);

            // --- Change History Section ---
            var changesSection = document.createElement('div');
            changesSection.className = 'table-container';

            var changesHeader = document.createElement('div');
            changesHeader.className = 'table-header';
            var changesTitle = document.createElement('h2');
            changesTitle.textContent = 'Change History';
            changesHeader.appendChild(changesTitle);
            changesSection.appendChild(changesHeader);

            // Filters row
            var filtersRow = document.createElement('div');
            filtersRow.style.cssText = 'display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;align-items:flex-end;';

            // Domain filter
            var domainGroup = this._createFilterGroup('Domain', 'dns-change-domain-filter', 'select');
            filtersRow.appendChild(domainGroup);

            // Record type filter
            var typeGroup = this._createFilterGroup('Record Type', 'dns-change-type-filter', 'select');
            var typeSelect = typeGroup.querySelector('select');
            [['', 'All Types'], ['DMARC', 'DMARC'], ['SPF', 'SPF'], ['DKIM', 'DKIM'], ['MX', 'MX']].forEach(function(opt) {
                var option = document.createElement('option');
                option.value = opt[0];
                option.textContent = opt[1];
                typeSelect.appendChild(option);
            });
            filtersRow.appendChild(typeGroup);

            // Days filter
            var daysGroup = this._createFilterGroup('Time Range', 'dns-change-days-filter', 'select');
            var daysSelect = daysGroup.querySelector('select');
            [['7', 'Last 7 days'], ['30', 'Last 30 days'], ['90', 'Last 90 days']].forEach(function(opt) {
                var option = document.createElement('option');
                option.value = opt[0];
                option.textContent = opt[1];
                if (opt[0] === '30') option.selected = true;
                daysSelect.appendChild(option);
            });
            filtersRow.appendChild(daysGroup);

            var applyBtn = document.createElement('button');
            applyBtn.className = 'btn-primary btn-sm';
            applyBtn.textContent = 'Apply';
            applyBtn.style.marginBottom = '2px';
            applyBtn.addEventListener('click', this._loadChanges.bind(this));
            filtersRow.appendChild(applyBtn);

            changesSection.appendChild(filtersRow);

            // Changes table
            var changesTable = document.createElement('table');
            changesTable.id = 'dns-changes-table';
            var cthead = document.createElement('thead');
            var cheadRow = document.createElement('tr');
            ['Domain', 'Record Type', 'Change', 'Old Value', 'New Value', 'Detected', 'Actions'].forEach(function(text) {
                var th = document.createElement('th');
                th.setAttribute('scope', 'col');
                th.textContent = text;
                cheadRow.appendChild(th);
            });
            cthead.appendChild(cheadRow);
            changesTable.appendChild(cthead);

            var changesBody = document.createElement('tbody');
            changesBody.id = 'dns-changes-tbody';
            var cLoadingRow = document.createElement('tr');
            var cLoadingCell = document.createElement('td');
            cLoadingCell.colSpan = 7;
            cLoadingCell.className = 'loading';
            cLoadingCell.textContent = 'Loading changes...';
            cLoadingRow.appendChild(cLoadingCell);
            changesBody.appendChild(cLoadingRow);
            changesTable.appendChild(changesBody);
            changesSection.appendChild(changesTable);
            body.appendChild(changesSection);

            container.appendChild(body);

            // --- Add Domain Modal ---
            this._createAddModal();

            // Hide admin buttons for non-admins
            this._updateAdminVisibility();
        },

        load: function() {
            this._loadDomains();
            this._loadChanges();
        },

        destroy: function() {
            // Nothing to clean up
        },

        // --- Data Loading ---

        _loadDomains: function() {
            var self = this;
            var tbody = document.getElementById('dns-domains-tbody');
            if (!tbody) return;

            clearChildren(tbody);
            var loadingRow = document.createElement('tr');
            var loadingCell = document.createElement('td');
            loadingCell.colSpan = 5;
            loadingCell.className = 'loading';
            loadingCell.textContent = 'Loading domains...';
            loadingRow.appendChild(loadingCell);
            tbody.appendChild(loadingRow);

            fetch(API_BASE + '/dns-monitor/domains?active_only=false', {
                headers: this._getHeaders()
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Failed to load domains');
                return r.json();
            })
            .then(function(data) {
                self.domains = Array.isArray(data) ? data : (data.domains || []);
                self._renderDomains();
                self._updateDomainFilter();
            })
            .catch(function(err) {
                clearChildren(tbody);
                var row = document.createElement('tr');
                var cell = document.createElement('td');
                cell.colSpan = 5;
                cell.textContent = 'Failed to load domains: ' + err.message;
                cell.style.color = 'var(--accent-danger)';
                row.appendChild(cell);
                tbody.appendChild(row);
            });
        },

        _loadChanges: function() {
            var self = this;
            var tbody = document.getElementById('dns-changes-tbody');
            if (!tbody) return;

            clearChildren(tbody);
            var loadingRow = document.createElement('tr');
            var loadingCell = document.createElement('td');
            loadingCell.colSpan = 7;
            loadingCell.className = 'loading';
            loadingCell.textContent = 'Loading changes...';
            loadingRow.appendChild(loadingCell);
            tbody.appendChild(loadingRow);

            var domainFilter = document.getElementById('dns-change-domain-filter');
            var typeFilter = document.getElementById('dns-change-type-filter');
            var daysFilter = document.getElementById('dns-change-days-filter');

            var params = [];
            if (domainFilter && domainFilter.value) params.push('domain=' + encodeURIComponent(domainFilter.value));
            if (typeFilter && typeFilter.value) params.push('record_type=' + encodeURIComponent(typeFilter.value));
            if (daysFilter && daysFilter.value) params.push('days=' + encodeURIComponent(daysFilter.value));
            params.push('limit=100');

            fetch(API_BASE + '/dns-monitor/changes?' + params.join('&'), {
                headers: this._getHeaders()
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Failed to load changes');
                return r.json();
            })
            .then(function(data) {
                self.changes = Array.isArray(data) ? data : (data.changes || []);
                self._renderChanges();
            })
            .catch(function(err) {
                clearChildren(tbody);
                var row = document.createElement('tr');
                var cell = document.createElement('td');
                cell.colSpan = 7;
                cell.textContent = 'Failed to load changes: ' + err.message;
                cell.style.color = 'var(--accent-danger)';
                row.appendChild(cell);
                tbody.appendChild(row);
            });
        },

        // --- Rendering ---

        _renderDomains: function() {
            var self = this;
            var tbody = document.getElementById('dns-domains-tbody');
            if (!tbody) return;
            clearChildren(tbody);

            if (!this.domains.length) {
                var row = document.createElement('tr');
                var cell = document.createElement('td');
                cell.colSpan = 5;
                cell.textContent = 'No monitored domains. Add a domain to get started.';
                cell.style.textAlign = 'center';
                cell.style.color = 'var(--text-secondary)';
                cell.style.padding = '24px';
                row.appendChild(cell);
                tbody.appendChild(row);
                return;
            }

            this.domains.forEach(function(domain) {
                var row = document.createElement('tr');

                // Domain
                var domainCell = document.createElement('td');
                domainCell.textContent = domain.domain;
                domainCell.style.fontWeight = '600';
                row.appendChild(domainCell);

                // Status badge
                var statusCell = document.createElement('td');
                var badge = document.createElement('span');
                badge.className = 'badge ' + (domain.is_active ? 'badge-success' : 'badge-gray');
                badge.textContent = domain.is_active ? 'Active' : 'Inactive';
                statusCell.appendChild(badge);
                row.appendChild(statusCell);

                // Monitors
                var monitorsCell = document.createElement('td');
                var monitors = [];
                if (domain.monitor_dmarc) monitors.push('DMARC');
                if (domain.monitor_spf) monitors.push('SPF');
                if (domain.monitor_dkim) monitors.push('DKIM');
                if (domain.monitor_mx) monitors.push('MX');
                monitors.forEach(function(m) {
                    var monitorBadge = document.createElement('span');
                    monitorBadge.className = 'badge badge-gray';
                    monitorBadge.textContent = m;
                    monitorBadge.style.cssText = 'margin-right:4px;font-size:11px;padding:2px 6px;';
                    monitorsCell.appendChild(monitorBadge);
                });
                if (!monitors.length) {
                    monitorsCell.textContent = 'None';
                    monitorsCell.style.color = 'var(--text-secondary)';
                }
                row.appendChild(monitorsCell);

                // Last checked
                var checkedCell = document.createElement('td');
                checkedCell.textContent = domain.last_checked_at ? self._formatDate(domain.last_checked_at) : 'Never';
                checkedCell.style.color = domain.last_checked_at ? '' : 'var(--text-secondary)';
                row.appendChild(checkedCell);

                // Actions
                var actionsCell = document.createElement('td');
                actionsCell.style.cssText = 'display:flex;gap:6px;';

                var checkBtn = document.createElement('button');
                checkBtn.className = 'btn-secondary btn-sm';
                checkBtn.textContent = 'Check Now';
                checkBtn.addEventListener('click', function() { self._onCheckDomain(domain.domain); });
                actionsCell.appendChild(checkBtn);

                var removeBtn = document.createElement('button');
                removeBtn.className = 'btn-ghost btn-sm dns-admin-action';
                removeBtn.textContent = 'Remove';
                removeBtn.style.color = 'var(--accent-danger)';
                removeBtn.addEventListener('click', function() { self._onRemoveDomain(domain.domain); });
                actionsCell.appendChild(removeBtn);

                row.appendChild(actionsCell);
                tbody.appendChild(row);
            });

            this._updateAdminVisibility();
        },

        _renderChanges: function() {
            var self = this;
            var tbody = document.getElementById('dns-changes-tbody');
            if (!tbody) return;
            clearChildren(tbody);

            if (!this.changes.length) {
                var row = document.createElement('tr');
                var cell = document.createElement('td');
                cell.colSpan = 7;
                cell.textContent = 'No changes detected in the selected time range.';
                cell.style.textAlign = 'center';
                cell.style.color = 'var(--text-secondary)';
                cell.style.padding = '24px';
                row.appendChild(cell);
                tbody.appendChild(row);
                return;
            }

            this.changes.forEach(function(change) {
                var row = document.createElement('tr');

                // Highlight unacknowledged changes
                if (!change.acknowledged) {
                    row.style.borderLeft = '3px solid var(--accent-warning)';
                }

                // Domain
                var domainCell = document.createElement('td');
                domainCell.textContent = change.domain;
                row.appendChild(domainCell);

                // Record type
                var typeCell = document.createElement('td');
                var typeBadge = document.createElement('span');
                typeBadge.className = 'badge badge-gray';
                typeBadge.textContent = change.record_type;
                typeCell.appendChild(typeBadge);
                row.appendChild(typeCell);

                // Change type badge
                var changeCell = document.createElement('td');
                var changeBadge = document.createElement('span');
                var changeClass = 'badge-gray';
                if (change.change_type === 'added') changeClass = 'badge-success';
                else if (change.change_type === 'modified') changeClass = 'badge-warning';
                else if (change.change_type === 'removed') changeClass = 'badge-danger';
                changeBadge.className = 'badge ' + changeClass;
                changeBadge.textContent = change.change_type;
                changeCell.appendChild(changeBadge);
                row.appendChild(changeCell);

                // Old value
                var oldCell = document.createElement('td');
                var oldCode = document.createElement('code');
                oldCode.textContent = change.old_value || '-';
                oldCode.style.cssText = 'font-size:0.8rem;word-break:break-all;max-width:200px;display:inline-block;';
                oldCell.appendChild(oldCode);
                row.appendChild(oldCell);

                // New value
                var newCell = document.createElement('td');
                var newCode = document.createElement('code');
                newCode.textContent = change.new_value || '-';
                newCode.style.cssText = 'font-size:0.8rem;word-break:break-all;max-width:200px;display:inline-block;';
                newCell.appendChild(newCode);
                row.appendChild(newCell);

                // Detected at
                var dateCell = document.createElement('td');
                dateCell.textContent = change.detected_at ? self._formatDate(change.detected_at) : '-';
                dateCell.style.whiteSpace = 'nowrap';
                row.appendChild(dateCell);

                // Actions
                var actionsCell = document.createElement('td');
                if (!change.acknowledged) {
                    var ackBtn = document.createElement('button');
                    ackBtn.className = 'btn-secondary btn-sm';
                    ackBtn.textContent = 'Acknowledge';
                    ackBtn.addEventListener('click', function() { self._onAcknowledge(change.id); });
                    actionsCell.appendChild(ackBtn);
                } else {
                    var ackSpan = document.createElement('span');
                    ackSpan.textContent = 'Acknowledged';
                    ackSpan.style.cssText = 'color:var(--text-secondary);font-size:0.85rem;';
                    actionsCell.appendChild(ackSpan);
                }
                row.appendChild(actionsCell);

                tbody.appendChild(row);
            });
        },

        // --- Actions ---

        _onCheckAll: function() {
            var self = this;
            var btn = document.getElementById('dns-check-all-btn');
            if (btn) { btn.disabled = true; btn.textContent = 'Checking...'; }

            fetch(API_BASE + '/dns-monitor/check', {
                method: 'POST',
                headers: this._getHeaders()
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Check failed');
                return r.json();
            })
            .then(function(data) {
                var msg = 'Checked ' + (data.domains_checked || 0) + ' domains. ' +
                    (data.total_changes || 0) + ' changes detected.';
                showNotification(msg, data.total_changes > 0 ? 'info' : 'success');
                self._loadDomains();
                self._loadChanges();
            })
            .catch(function(err) {
                showNotification('Failed to check domains: ' + err.message, 'error');
            })
            .finally(function() {
                if (btn) { btn.disabled = false; btn.textContent = 'Check All'; }
            });
        },

        _onCheckDomain: function(domain) {
            var self = this;
            fetch(API_BASE + '/dns-monitor/check/' + encodeURIComponent(domain), {
                method: 'POST',
                headers: this._getHeaders()
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Check failed');
                return r.json();
            })
            .then(function(data) {
                var changes = data.changes ? data.changes.length : 0;
                showNotification(domain + ': ' + changes + ' change(s) detected.', changes > 0 ? 'info' : 'success');
                self._loadDomains();
                self._loadChanges();
            })
            .catch(function(err) {
                showNotification('Failed to check ' + domain + ': ' + err.message, 'error');
            });
        },

        _onRemoveDomain: function(domain) {
            if (!confirm('Remove "' + domain + '" from monitoring? This cannot be undone.')) return;
            var self = this;

            fetch(API_BASE + '/dns-monitor/domains/' + encodeURIComponent(domain), {
                method: 'DELETE',
                headers: this._getHeaders()
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Delete failed');
                showNotification('Removed ' + domain + ' from monitoring', 'success');
                self._loadDomains();
            })
            .catch(function(err) {
                showNotification('Failed to remove domain: ' + err.message, 'error');
            });
        },

        _onAcknowledge: function(changeId) {
            var self = this;
            fetch(API_BASE + '/dns-monitor/changes/' + encodeURIComponent(changeId) + '/acknowledge', {
                method: 'POST',
                headers: this._getHeaders()
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Acknowledge failed');
                self._loadChanges();
            })
            .catch(function(err) {
                showNotification('Failed to acknowledge change: ' + err.message, 'error');
            });
        },

        // --- Add Domain Modal ---

        _createAddModal: function() {
            var modal = document.createElement('div');
            modal.id = 'dns-add-domain-modal';
            modal.className = 'modal';
            modal.setAttribute('role', 'dialog');
            modal.setAttribute('aria-modal', 'true');
            modal.setAttribute('aria-labelledby', 'dns-add-modal-title');
            modal.hidden = true;

            var content = document.createElement('div');
            content.className = 'modal-content';

            // Header
            var header = document.createElement('div');
            header.className = 'modal-header';
            var title = document.createElement('h2');
            title.id = 'dns-add-modal-title';
            title.textContent = 'Add Domain to Monitor';
            header.appendChild(title);
            var closeBtn = document.createElement('button');
            closeBtn.className = 'modal-close';
            closeBtn.setAttribute('aria-label', 'Close modal');
            closeBtn.textContent = '\u00D7';
            closeBtn.addEventListener('click', this._hideAddModal.bind(this));
            header.appendChild(closeBtn);
            content.appendChild(header);

            // Body
            var body = document.createElement('div');
            body.className = 'modal-body';

            // Domain input
            var domainGroup = document.createElement('div');
            domainGroup.style.marginBottom = '16px';
            var domainLabel = document.createElement('label');
            domainLabel.textContent = 'Domain';
            domainLabel.setAttribute('for', 'dns-add-domain-input');
            domainLabel.style.cssText = 'display:block;font-weight:600;margin-bottom:6px;font-size:0.9rem;';
            domainGroup.appendChild(domainLabel);
            var domainInput = document.createElement('input');
            domainInput.type = 'text';
            domainInput.id = 'dns-add-domain-input';
            domainInput.placeholder = 'example.com';
            domainInput.style.cssText = 'width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);font-size:0.9rem;box-sizing:border-box;';
            domainGroup.appendChild(domainInput);
            body.appendChild(domainGroup);

            // Monitor checkboxes
            var monitorsGroup = document.createElement('div');
            monitorsGroup.style.marginBottom = '16px';
            var monitorsLabel = document.createElement('label');
            monitorsLabel.textContent = 'Records to Monitor';
            monitorsLabel.style.cssText = 'display:block;font-weight:600;margin-bottom:8px;font-size:0.9rem;';
            monitorsGroup.appendChild(monitorsLabel);

            var checkboxes = [
                { id: 'dns-add-dmarc', label: 'DMARC', checked: true },
                { id: 'dns-add-spf', label: 'SPF', checked: true },
                { id: 'dns-add-dkim', label: 'DKIM', checked: false },
                { id: 'dns-add-mx', label: 'MX', checked: false }
            ];
            checkboxes.forEach(function(cb) {
                var wrapper = document.createElement('label');
                wrapper.style.cssText = 'display:inline-flex;align-items:center;gap:6px;margin-right:16px;font-size:0.9rem;cursor:pointer;';
                var input = document.createElement('input');
                input.type = 'checkbox';
                input.id = cb.id;
                input.checked = cb.checked;
                wrapper.appendChild(input);
                var span = document.createElement('span');
                span.textContent = cb.label;
                wrapper.appendChild(span);
                monitorsGroup.appendChild(wrapper);
            });
            body.appendChild(monitorsGroup);

            // DKIM selectors
            var dkimGroup = document.createElement('div');
            dkimGroup.style.marginBottom = '16px';
            var dkimLabel = document.createElement('label');
            dkimLabel.textContent = 'DKIM Selectors (comma-separated)';
            dkimLabel.setAttribute('for', 'dns-add-dkim-selectors');
            dkimLabel.style.cssText = 'display:block;font-weight:600;margin-bottom:6px;font-size:0.9rem;';
            dkimGroup.appendChild(dkimLabel);
            var dkimInput = document.createElement('input');
            dkimInput.type = 'text';
            dkimInput.id = 'dns-add-dkim-selectors';
            dkimInput.placeholder = 'selector1, selector2';
            dkimInput.style.cssText = 'width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);font-size:0.9rem;box-sizing:border-box;';
            dkimGroup.appendChild(dkimInput);
            body.appendChild(dkimGroup);

            // Actions
            var actions = document.createElement('div');
            actions.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;margin-top:20px;';
            var cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn-secondary';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.addEventListener('click', this._hideAddModal.bind(this));
            actions.appendChild(cancelBtn);
            var saveBtn = document.createElement('button');
            saveBtn.className = 'btn-primary';
            saveBtn.textContent = 'Add Domain';
            saveBtn.id = 'dns-add-domain-save';
            saveBtn.addEventListener('click', this._onAddDomain.bind(this));
            actions.appendChild(saveBtn);
            body.appendChild(actions);

            content.appendChild(body);
            modal.appendChild(content);

            // Close on backdrop click
            modal.addEventListener('click', function(e) {
                if (e.target === modal) this._hideAddModal();
            }.bind(this));

            document.body.appendChild(modal);
        },

        _showAddModal: function() {
            var modal = document.getElementById('dns-add-domain-modal');
            if (modal) {
                // Reset form
                var domainInput = document.getElementById('dns-add-domain-input');
                if (domainInput) domainInput.value = '';
                document.getElementById('dns-add-dmarc').checked = true;
                document.getElementById('dns-add-spf').checked = true;
                document.getElementById('dns-add-dkim').checked = false;
                document.getElementById('dns-add-mx').checked = false;
                var selInput = document.getElementById('dns-add-dkim-selectors');
                if (selInput) selInput.value = '';
                modal.hidden = false;
            }
        },

        _hideAddModal: function() {
            var modal = document.getElementById('dns-add-domain-modal');
            if (modal) modal.hidden = true;
        },

        _onAddDomain: function() {
            var self = this;
            var domainInput = document.getElementById('dns-add-domain-input');
            var domain = domainInput ? domainInput.value.trim() : '';
            if (!domain) {
                showNotification('Please enter a domain name', 'error');
                return;
            }

            var selectorsInput = document.getElementById('dns-add-dkim-selectors');
            var selectors = [];
            if (selectorsInput && selectorsInput.value.trim()) {
                selectors = selectorsInput.value.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
            }

            var payload = {
                domain: domain,
                monitor_dmarc: document.getElementById('dns-add-dmarc').checked,
                monitor_spf: document.getElementById('dns-add-spf').checked,
                monitor_dkim: document.getElementById('dns-add-dkim').checked,
                monitor_mx: document.getElementById('dns-add-mx').checked,
                dkim_selectors: selectors
            };

            var saveBtn = document.getElementById('dns-add-domain-save');
            if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Adding...'; }

            fetch(API_BASE + '/dns-monitor/domains', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, this._getHeaders()),
                body: JSON.stringify(payload)
            })
            .then(function(r) {
                if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Failed to add domain'); });
                return r.json();
            })
            .then(function() {
                showNotification('Added ' + domain + ' to monitoring', 'success');
                self._hideAddModal();
                self._loadDomains();
            })
            .catch(function(err) {
                showNotification(err.message, 'error');
            })
            .finally(function() {
                if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Add Domain'; }
            });
        },

        // --- Helpers ---

        _getHeaders: function() {
            if (typeof getAuthHeaders === 'function') return getAuthHeaders();
            var DMARC = window.DMARC;
            if (DMARC && DMARC.getAuthHeaders) return DMARC.getAuthHeaders();
            return {};
        },

        _formatDate: function(dateStr) {
            var d = new Date(dateStr);
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
        },

        _createFilterGroup: function(labelText, id, type) {
            var group = document.createElement('div');
            group.style.cssText = 'display:flex;flex-direction:column;gap:4px;';
            var label = document.createElement('label');
            label.textContent = labelText;
            label.setAttribute('for', id);
            label.style.cssText = 'font-size:0.8rem;font-weight:600;color:var(--text-secondary);';
            group.appendChild(label);

            var input;
            if (type === 'select') {
                input = document.createElement('select');
                var defaultOpt = document.createElement('option');
                defaultOpt.value = '';
                defaultOpt.textContent = 'All';
                input.appendChild(defaultOpt);
            } else {
                input = document.createElement('input');
                input.type = type || 'text';
            }
            input.id = id;
            input.style.cssText = 'padding:6px 10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);font-size:0.85rem;';
            group.appendChild(input);
            return group;
        },

        _updateDomainFilter: function() {
            var select = document.getElementById('dns-change-domain-filter');
            if (!select) return;
            // Keep first "All" option, remove the rest
            while (select.options.length > 1) select.remove(1);
            this.domains.forEach(function(d) {
                var opt = document.createElement('option');
                opt.value = d.domain;
                opt.textContent = d.domain;
                select.appendChild(opt);
            });
        },

        _updateAdminVisibility: function() {
            var user = (window.DMARC && window.DMARC.currentUser) || (typeof currentUser !== 'undefined' ? currentUser : null);
            var isAdmin = user && user.role === 'admin';
            var adminBtns = document.querySelectorAll('#' + this.containerId + ' .dns-admin-action, #dns-add-domain-btn, #dns-check-all-btn');
            adminBtns.forEach(function(btn) {
                btn.style.display = isAdmin ? '' : 'none';
            });
        }
    };

    // Expose module
    window.DMARC = window.DMARC || {};
    window.DMARC.DnsMonitorPage = DnsMonitorPage;

    // Register with router
    if (window.DMARC.Router) {
        window.DMARC.Router.register('dns-monitor', DnsMonitorPage);
    }
})();
