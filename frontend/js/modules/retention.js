/**
 * DMARC Dashboard - Retention Policies Page Module
 * Manages data retention policies: create, edit, execute, dry-run, view logs.
 * Admin-only page.
 */
(function() {
    'use strict';

    function clearElement(el) {
        while (el.firstChild) el.removeChild(el.firstChild);
    }

    function getAuthHeaders() {
        return window.DMARC && window.DMARC.getAuthHeaders ? window.DMARC.getAuthHeaders() :
               (typeof window.getAuthHeaders === 'function' ? window.getAuthHeaders() : {});
    }

    function notify(msg, type) {
        if (window.DMARC && window.DMARC.showNotification) window.DMARC.showNotification(msg, type);
        else if (typeof showNotification === 'function') showNotification(msg, type);
    }

    var RetentionPage = {
        initialized: false,
        containerId: 'page-retention',
        _els: {},
        _chart: null,

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            // Header
            var header = document.createElement('div');
            header.className = 'page-header';
            var h1 = document.createElement('h1');
            h1.textContent = 'Data Retention';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Manage data retention policies to control storage usage and comply with data governance requirements.';
            header.appendChild(desc);

            var actions = document.createElement('div');
            actions.style.cssText = 'display:flex;gap:8px;margin-top:12px;';
            var createBtn = document.createElement('button');
            createBtn.className = 'btn-primary btn-sm';
            createBtn.textContent = 'Create Policy';
            createBtn.addEventListener('click', this._showCreateForm.bind(this));
            actions.appendChild(createBtn);

            var execAllBtn = document.createElement('button');
            execAllBtn.className = 'btn-secondary btn-sm';
            execAllBtn.textContent = 'Execute All';
            execAllBtn.addEventListener('click', this._executeAll.bind(this));
            this._els.execAllBtn = execAllBtn;
            actions.appendChild(execAllBtn);

            header.appendChild(actions);

            // Stats summary
            var stats = document.createElement('div');
            stats.className = 'stats-grid';
            stats.style.marginBottom = '20px';
            this._els.stats = stats;

            // Create/Edit form (hidden)
            var formCard = document.createElement('div');
            formCard.className = 'card';
            formCard.style.cssText = 'padding:16px;margin-bottom:16px;display:none;';
            this._els.formCard = formCard;
            this._buildForm(formCard);

            // Policies table
            var tableWrap = document.createElement('div');
            tableWrap.className = 'table-container';
            tableWrap.style.marginBottom = '20px';
            var tableHeader = document.createElement('div');
            tableHeader.className = 'table-header';
            var tableTitle = document.createElement('h2');
            tableTitle.textContent = 'Retention Policies';
            tableHeader.appendChild(tableTitle);

            var table = document.createElement('table');
            var thead = document.createElement('thead');
            var hRow = document.createElement('tr');
            ['Name', 'Table', 'Retention Days', 'Action', 'Status', 'Last Run', 'Actions'].forEach(function(col) {
                var th = document.createElement('th');
                th.scope = 'col';
                th.textContent = col;
                hRow.appendChild(th);
            });
            thead.appendChild(hRow);
            table.appendChild(thead);
            var tbody = document.createElement('tbody');
            this._els.tbody = tbody;
            table.appendChild(tbody);
            tableWrap.appendChild(tableHeader);
            tableWrap.appendChild(table);

            // Dry-run result panel
            var dryRunPanel = document.createElement('div');
            dryRunPanel.className = 'card';
            dryRunPanel.style.cssText = 'padding:16px;margin-bottom:16px;display:none;';
            this._els.dryRunPanel = dryRunPanel;

            // Execution logs
            var logsWrap = document.createElement('div');
            logsWrap.className = 'table-container';
            logsWrap.style.marginBottom = '20px';
            var logsHeader = document.createElement('div');
            logsHeader.className = 'table-header';
            var logsTitle = document.createElement('h2');
            logsTitle.textContent = 'Execution Logs';
            logsHeader.appendChild(logsTitle);

            var logsTable = document.createElement('table');
            var logsThead = document.createElement('thead');
            var logsHRow = document.createElement('tr');
            ['Policy', 'Executed At', 'Records Affected', 'Duration', 'Status'].forEach(function(col) {
                var th = document.createElement('th');
                th.scope = 'col';
                th.textContent = col;
                logsHRow.appendChild(th);
            });
            logsThead.appendChild(logsHRow);
            logsTable.appendChild(logsThead);
            var logsTbody = document.createElement('tbody');
            this._els.logsTbody = logsTbody;
            logsTable.appendChild(logsTbody);
            logsWrap.appendChild(logsHeader);
            logsWrap.appendChild(logsTable);

            // Storage forecast chart
            var chartWrap = document.createElement('div');
            chartWrap.className = 'chart-container';
            var chartHeader = document.createElement('div');
            chartHeader.className = 'chart-header';
            var chartTitle = document.createElement('h2');
            chartTitle.textContent = 'Storage Forecast';
            chartHeader.appendChild(chartTitle);
            chartWrap.appendChild(chartHeader);
            var canvas = document.createElement('canvas');
            canvas.id = 'retentionForecastChart';
            chartWrap.appendChild(canvas);
            this._els.canvas = canvas;

            var body = document.createElement('div');
            body.className = 'page-body';
            body.appendChild(stats);
            body.appendChild(formCard);
            body.appendChild(dryRunPanel);
            body.appendChild(tableWrap);
            body.appendChild(logsWrap);
            body.appendChild(chartWrap);

            container.appendChild(header);
            container.appendChild(body);
        },

        _buildForm: function(card) {
            var self = this;

            var formTitle = document.createElement('h3');
            formTitle.style.marginBottom = '12px';
            this._els.formTitle = formTitle;
            card.appendChild(formTitle);

            var grid = document.createElement('div');
            grid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:12px;';

            // Name
            var nameGroup = this._createField('Policy Name', 'text', 'e.g., Delete old DMARC reports');
            this._els.nameInput = nameGroup.input;
            grid.appendChild(nameGroup.wrap);

            // Table
            var tableGroup = document.createElement('div');
            var tableLbl = document.createElement('label');
            tableLbl.textContent = 'Table';
            tableLbl.style.cssText = 'display:block;margin-bottom:4px;font-weight:600;font-size:13px;';
            var tableSelect = document.createElement('select');
            tableSelect.style.cssText = 'width:100%;padding:8px;border:1px solid var(--border-color);border-radius:4px;background:var(--bg-primary);color:var(--text-primary);';
            ['dmarc_reports', 'dmarc_records', 'ingested_reports', 'alert_history', 'audit_logs', 'ml_predictions', 'geolocation_cache'].forEach(function(t) {
                var opt = document.createElement('option');
                opt.value = t;
                opt.textContent = t;
                tableSelect.appendChild(opt);
            });
            this._els.tableSelect = tableSelect;
            tableGroup.appendChild(tableLbl);
            tableGroup.appendChild(tableSelect);
            grid.appendChild(tableGroup);

            // Retention days
            var daysGroup = this._createField('Retention Days', 'number', 'e.g., 90');
            daysGroup.input.min = '1';
            this._els.daysInput = daysGroup.input;
            grid.appendChild(daysGroup.wrap);

            // Action
            var actionGroup = document.createElement('div');
            var actionLbl = document.createElement('label');
            actionLbl.textContent = 'Action';
            actionLbl.style.cssText = 'display:block;margin-bottom:4px;font-weight:600;font-size:13px;';
            actionGroup.appendChild(actionLbl);

            var radioWrap = document.createElement('div');
            radioWrap.style.cssText = 'display:flex;gap:16px;align-items:center;padding:8px 0;';

            var archiveLabel = document.createElement('label');
            archiveLabel.style.cssText = 'display:flex;align-items:center;gap:4px;cursor:pointer;';
            var archiveRadio = document.createElement('input');
            archiveRadio.type = 'radio';
            archiveRadio.name = 'retentionAction';
            archiveRadio.value = 'archive';
            this._els.archiveRadio = archiveRadio;
            archiveLabel.appendChild(archiveRadio);
            archiveLabel.appendChild(document.createTextNode('Archive'));
            radioWrap.appendChild(archiveLabel);

            var deleteLabel = document.createElement('label');
            deleteLabel.style.cssText = 'display:flex;align-items:center;gap:4px;cursor:pointer;';
            var deleteRadio = document.createElement('input');
            deleteRadio.type = 'radio';
            deleteRadio.name = 'retentionAction';
            deleteRadio.value = 'delete';
            deleteRadio.checked = true;
            this._els.deleteRadio = deleteRadio;
            deleteLabel.appendChild(deleteRadio);
            deleteLabel.appendChild(document.createTextNode('Delete'));
            radioWrap.appendChild(deleteLabel);

            actionGroup.appendChild(radioWrap);
            grid.appendChild(actionGroup);

            card.appendChild(grid);

            // Active toggle
            var toggleWrap = document.createElement('div');
            toggleWrap.style.cssText = 'margin-top:12px;display:flex;align-items:center;gap:8px;';
            var activeCheck = document.createElement('input');
            activeCheck.type = 'checkbox';
            activeCheck.id = 'retentionActiveToggle';
            activeCheck.checked = true;
            this._els.activeCheck = activeCheck;
            var activeLbl = document.createElement('label');
            activeLbl.htmlFor = 'retentionActiveToggle';
            activeLbl.textContent = 'Active';
            activeLbl.style.cursor = 'pointer';
            toggleWrap.appendChild(activeCheck);
            toggleWrap.appendChild(activeLbl);
            card.appendChild(toggleWrap);

            // Buttons
            var btnRow = document.createElement('div');
            btnRow.style.cssText = 'display:flex;gap:8px;margin-top:16px;';
            var saveBtn = document.createElement('button');
            saveBtn.className = 'btn-primary btn-sm';
            saveBtn.textContent = 'Save';
            saveBtn.addEventListener('click', this._savePolicy.bind(this));
            this._els.saveBtn = saveBtn;

            var cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn-ghost btn-sm';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.addEventListener('click', function() { card.style.display = 'none'; self._editingId = null; });

            btnRow.appendChild(saveBtn);
            btnRow.appendChild(cancelBtn);
            card.appendChild(btnRow);
        },

        _createField: function(label, type, placeholder) {
            var wrap = document.createElement('div');
            var lbl = document.createElement('label');
            lbl.textContent = label;
            lbl.style.cssText = 'display:block;margin-bottom:4px;font-weight:600;font-size:13px;';
            var input = document.createElement('input');
            input.type = type;
            input.placeholder = placeholder || '';
            input.style.cssText = 'width:100%;padding:8px;border:1px solid var(--border-color);border-radius:4px;background:var(--bg-primary);color:var(--text-primary);box-sizing:border-box;';
            wrap.appendChild(lbl);
            wrap.appendChild(input);
            return { wrap: wrap, input: input };
        },

        load: function() {
            this._loadPolicies();
            this._loadStats();
            this._loadLogs();
            this._loadForecast();
        },

        destroy: function() {
            if (this._chart) { this._chart.destroy(); this._chart = null; }
        },

        _loadPolicies: function() {
            var self = this;
            fetch('/api/retention/policies', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var policies = Array.isArray(data) ? data : (data.policies || []);
                    self._renderPolicies(policies);
                })
                .catch(function() { notify('Failed to load retention policies', 'error'); });
        },

        _loadStats: function() {
            var self = this;
            fetch('/api/retention/stats', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) { self._renderStats(data); })
                .catch(function() {});
        },

        _renderStats: function(data) {
            var el = this._els.stats;
            if (!el) return;
            clearElement(el);

            var items = [
                { label: 'Total Policies', value: data.total_policies || 0, cls: '' },
                { label: 'Active Policies', value: data.active_policies || 0, cls: 'stat-card-success' },
                { label: 'Total Executions', value: data.total_executions || 0, cls: '' },
                { label: 'Records Deleted', value: (data.total_deleted || 0).toLocaleString(), cls: '' },
                { label: 'Storage Saved', value: data.storage_saved || '0 B', cls: '' }
            ];

            items.forEach(function(item) {
                var card = document.createElement('div');
                card.className = 'stat-card ' + item.cls;
                var h = document.createElement('div');
                h.className = 'stat-header';
                var h3 = document.createElement('h3');
                h3.textContent = item.label;
                h.appendChild(h3);
                var c = document.createElement('div');
                c.className = 'stat-content';
                var v = document.createElement('div');
                v.className = 'stat-value';
                v.textContent = item.value;
                c.appendChild(v);
                card.appendChild(h);
                card.appendChild(c);
                el.appendChild(card);
            });
        },

        _renderPolicies: function(policies) {
            var self = this;
            var tbody = this._els.tbody;
            if (!tbody) return;
            clearElement(tbody);

            if (policies.length === 0) {
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.colSpan = 7;
                td.textContent = 'No retention policies configured.';
                td.style.textAlign = 'center';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            policies.forEach(function(p) {
                var tr = document.createElement('tr');

                var tdName = document.createElement('td');
                tdName.textContent = p.name || '-';
                tr.appendChild(tdName);

                var tdTable = document.createElement('td');
                tdTable.textContent = p.table_name || '-';
                tr.appendChild(tdTable);

                var tdDays = document.createElement('td');
                tdDays.textContent = p.retention_days || '-';
                tr.appendChild(tdDays);

                var tdAction = document.createElement('td');
                var actionBadge = document.createElement('span');
                actionBadge.className = 'badge ' + (p.action === 'delete' ? 'badge-danger' : 'badge-warning');
                actionBadge.textContent = p.action || 'delete';
                tdAction.appendChild(actionBadge);
                tr.appendChild(tdAction);

                var tdStatus = document.createElement('td');
                var statusBadge = document.createElement('span');
                statusBadge.className = 'badge ' + (p.is_active ? 'badge-success' : 'badge-gray');
                statusBadge.textContent = p.is_active ? 'Active' : 'Inactive';
                tdStatus.appendChild(statusBadge);
                tr.appendChild(tdStatus);

                var tdLastRun = document.createElement('td');
                tdLastRun.textContent = p.last_run ? new Date(p.last_run).toLocaleString() : 'Never';
                tr.appendChild(tdLastRun);

                var tdActions = document.createElement('td');

                var editBtn = document.createElement('button');
                editBtn.className = 'btn-ghost btn-sm';
                editBtn.textContent = 'Edit';
                editBtn.addEventListener('click', function() { self._editPolicy(p); });
                tdActions.appendChild(editBtn);

                var dryRunBtn = document.createElement('button');
                dryRunBtn.className = 'btn-ghost btn-sm';
                dryRunBtn.textContent = 'Dry Run';
                dryRunBtn.addEventListener('click', function() { self._dryRun(p.id); });
                tdActions.appendChild(dryRunBtn);

                var execBtn = document.createElement('button');
                execBtn.className = 'btn-ghost btn-sm';
                execBtn.textContent = 'Execute';
                execBtn.addEventListener('click', function() { self._executePolicy(p.id, p.name); });
                tdActions.appendChild(execBtn);

                var delBtn = document.createElement('button');
                delBtn.className = 'btn-ghost btn-sm';
                delBtn.style.color = 'var(--accent-danger)';
                delBtn.textContent = 'Delete';
                delBtn.addEventListener('click', function() { self._deletePolicy(p.id, p.name); });
                tdActions.appendChild(delBtn);

                tr.appendChild(tdActions);
                tbody.appendChild(tr);
            });
        },

        _showCreateForm: function() {
            this._editingId = null;
            this._els.formTitle.textContent = 'Create Retention Policy';
            this._els.nameInput.value = '';
            this._els.tableSelect.value = 'dmarc_reports';
            this._els.daysInput.value = '';
            this._els.deleteRadio.checked = true;
            this._els.activeCheck.checked = true;
            this._els.formCard.style.display = '';
        },

        _editPolicy: function(p) {
            this._editingId = p.id;
            this._els.formTitle.textContent = 'Edit Retention Policy';
            this._els.nameInput.value = p.name || '';
            this._els.tableSelect.value = p.table_name || 'dmarc_reports';
            this._els.daysInput.value = p.retention_days || '';
            if (p.action === 'archive') {
                this._els.archiveRadio.checked = true;
            } else {
                this._els.deleteRadio.checked = true;
            }
            this._els.activeCheck.checked = p.is_active !== false;
            this._els.formCard.style.display = '';
        },

        _savePolicy: function() {
            var self = this;
            var payload = {
                name: this._els.nameInput.value.trim(),
                table_name: this._els.tableSelect.value,
                retention_days: parseInt(this._els.daysInput.value, 10),
                action: this._els.archiveRadio.checked ? 'archive' : 'delete',
                is_active: this._els.activeCheck.checked
            };

            if (!payload.name || !payload.retention_days) {
                notify('Name and retention days are required', 'error');
                return;
            }

            var url = '/api/retention/policies';
            var method = 'POST';
            if (this._editingId) {
                url = '/api/retention/policies/' + this._editingId;
                method = 'PUT';
            }

            fetch(url, {
                method: method,
                headers: Object.assign({ 'Content-Type': 'application/json' }, getAuthHeaders()),
                body: JSON.stringify(payload)
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Failed to save policy');
                return r.json();
            })
            .then(function() {
                notify('Policy saved', 'success');
                self._els.formCard.style.display = 'none';
                self._editingId = null;
                self._loadPolicies();
                self._loadStats();
            })
            .catch(function(err) { notify(err.message, 'error'); });
        },

        _deletePolicy: function(id, name) {
            if (!confirm('Delete policy "' + (name || id) + '"?')) return;
            var self = this;
            fetch('/api/retention/policies/' + id, { method: 'DELETE', headers: getAuthHeaders() })
                .then(function(r) {
                    if (!r.ok) throw new Error('Failed');
                    notify('Policy deleted', 'success');
                    self._loadPolicies();
                    self._loadStats();
                })
                .catch(function() { notify('Failed to delete policy', 'error'); });
        },

        _executePolicy: function(id, name) {
            if (!confirm('Execute retention policy "' + (name || id) + '"? This may permanently delete data.')) return;
            var self = this;
            fetch('/api/retention/execute/' + id, { method: 'POST', headers: getAuthHeaders() })
                .then(function(r) {
                    if (!r.ok) throw new Error('Failed');
                    return r.json();
                })
                .then(function(data) {
                    notify('Policy executed. ' + (data.records_deleted || data.deleted || 0) + ' records affected.', 'success');
                    self._loadPolicies();
                    self._loadLogs();
                    self._loadStats();
                })
                .catch(function() { notify('Execution failed', 'error'); });
        },

        _executeAll: function() {
            if (!confirm('Execute all active retention policies? This may permanently delete data.')) return;
            var self = this;
            var btn = this._els.execAllBtn;
            if (btn) { btn.disabled = true; btn.textContent = 'Executing...'; }

            fetch('/api/retention/execute-all', { method: 'POST', headers: getAuthHeaders() })
                .then(function(r) {
                    if (!r.ok) throw new Error('Failed');
                    return r.json();
                })
                .then(function() {
                    notify('All policies executed', 'success');
                    self._loadPolicies();
                    self._loadLogs();
                    self._loadStats();
                })
                .catch(function() { notify('Execute all failed', 'error'); })
                .finally(function() { if (btn) { btn.disabled = false; btn.textContent = 'Execute All'; } });
        },

        _dryRun: function(id) {
            var self = this;
            var panel = this._els.dryRunPanel;
            if (!panel) return;
            panel.style.display = '';
            clearElement(panel);
            var loading = document.createElement('p');
            loading.className = 'loading';
            loading.textContent = 'Running dry run...';
            panel.appendChild(loading);

            fetch('/api/retention/dry-run/' + id, { method: 'POST', headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) { self._renderDryRun(panel, data); })
                .catch(function() {
                    clearElement(panel);
                    var err = document.createElement('p');
                    err.textContent = 'Dry run failed.';
                    err.style.color = 'var(--accent-danger)';
                    panel.appendChild(err);
                });
        },

        _renderDryRun: function(panel, data) {
            clearElement(panel);

            var titleRow = document.createElement('div');
            titleRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;';
            var title = document.createElement('h3');
            title.textContent = 'Dry Run Result';
            titleRow.appendChild(title);
            var closeBtn = document.createElement('button');
            closeBtn.className = 'btn-ghost btn-sm';
            closeBtn.textContent = 'Close';
            closeBtn.addEventListener('click', function() { panel.style.display = 'none'; });
            titleRow.appendChild(closeBtn);
            panel.appendChild(titleRow);

            var fields = [
                ['Would Delete', (data.would_delete || 0).toLocaleString() + ' records'],
                ['Oldest Record', data.oldest_record ? new Date(data.oldest_record).toLocaleString() : '-'],
                ['Newest Record', data.newest_record ? new Date(data.newest_record).toLocaleString() : '-']
            ];

            fields.forEach(function(pair) {
                var row = document.createElement('div');
                row.style.cssText = 'display:flex;gap:8px;margin:6px 0;';
                var lbl = document.createElement('strong');
                lbl.textContent = pair[0] + ':';
                var val = document.createElement('span');
                val.textContent = pair[1];
                row.appendChild(lbl);
                row.appendChild(val);
                panel.appendChild(row);
            });
        },

        _loadLogs: function() {
            var self = this;
            fetch('/api/retention/logs?limit=50', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var logs = Array.isArray(data) ? data : (data.logs || []);
                    self._renderLogs(logs);
                })
                .catch(function() {});
        },

        _renderLogs: function(logs) {
            var tbody = this._els.logsTbody;
            if (!tbody) return;
            clearElement(tbody);

            if (logs.length === 0) {
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.colSpan = 5;
                td.textContent = 'No execution logs yet.';
                td.style.textAlign = 'center';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            logs.forEach(function(log) {
                var tr = document.createElement('tr');

                var tdPolicy = document.createElement('td');
                tdPolicy.textContent = log.policy_name || log.policy_id || '-';
                tr.appendChild(tdPolicy);

                var tdDate = document.createElement('td');
                tdDate.textContent = log.executed_at ? new Date(log.executed_at).toLocaleString() : '-';
                tr.appendChild(tdDate);

                var tdRecords = document.createElement('td');
                tdRecords.textContent = (log.records_affected || log.records_deleted || 0).toLocaleString();
                tr.appendChild(tdRecords);

                var tdDur = document.createElement('td');
                tdDur.textContent = log.duration ? log.duration.toFixed(2) + 's' : '-';
                tr.appendChild(tdDur);

                var tdStatus = document.createElement('td');
                var statusBadge = document.createElement('span');
                var status = log.status || 'completed';
                statusBadge.className = 'badge ' + (status === 'completed' || status === 'success' ? 'badge-success' : 'badge-danger');
                statusBadge.textContent = status;
                tdStatus.appendChild(statusBadge);
                tr.appendChild(tdStatus);

                tbody.appendChild(tr);
            });
        },

        _loadForecast: function() {
            var self = this;
            fetch('/api/retention/forecast', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) { self._renderForecast(data); })
                .catch(function() {});
        },

        _renderForecast: function(data) {
            if (!this._els.canvas || typeof Chart === 'undefined') return;
            if (this._chart) { this._chart.destroy(); this._chart = null; }

            var items = Array.isArray(data) ? data : (data.forecast || []);
            var labels = [];
            var values = [];

            items.forEach(function(item) {
                labels.push(item.date || item.month || '');
                values.push(item.storage_mb || item.estimated_size_mb || 0);
            });

            if (labels.length === 0) return;

            var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            var textColor = isDark ? '#ccc' : '#666';
            var gridColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';

            this._chart = new Chart(this._els.canvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Estimated Storage (MB)',
                        data: values,
                        backgroundColor: 'rgba(52,152,219,0.6)',
                        borderColor: '#3498db',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: { labels: { color: textColor } }
                    },
                    scales: {
                        x: { ticks: { color: textColor }, grid: { color: gridColor } },
                        y: { beginAtZero: true, ticks: { color: textColor }, grid: { color: gridColor } }
                    }
                }
            });
        }
    };

    window.DMARC = window.DMARC || {};
    window.DMARC.RetentionPage = RetentionPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('retention', RetentionPage);
    }
})();
