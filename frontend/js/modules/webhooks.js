/**
 * DMARC Dashboard - Webhooks Page Module
 * Manages webhook endpoints: create, edit, test, view delivery logs.
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

    function generateSecret(len) {
        var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        var result = '';
        var arr = new Uint8Array(len || 32);
        if (window.crypto && window.crypto.getRandomValues) {
            window.crypto.getRandomValues(arr);
            for (var i = 0; i < arr.length; i++) {
                result += chars.charAt(arr[i] % chars.length);
            }
        } else {
            for (var j = 0; j < (len || 32); j++) {
                result += chars.charAt(Math.floor(Math.random() * chars.length));
            }
        }
        return result;
    }

    var WebhooksPage = {
        initialized: false,
        containerId: 'page-webhooks',
        _els: {},
        _availableEvents: [],
        _editingId: null,

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            // Header
            var header = document.createElement('div');
            header.className = 'page-header';
            var h1 = document.createElement('h1');
            h1.textContent = 'Webhooks';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Configure webhook endpoints to receive real-time notifications for DMARC events.';
            header.appendChild(desc);

            var actions = document.createElement('div');
            actions.style.cssText = 'display:flex;gap:8px;margin-top:12px;';
            var addBtn = document.createElement('button');
            addBtn.className = 'btn-primary btn-sm';
            addBtn.textContent = 'Add Webhook';
            addBtn.addEventListener('click', this._showCreateForm.bind(this));
            actions.appendChild(addBtn);
            header.appendChild(actions);

            // Create/Edit form (hidden)
            var formCard = document.createElement('div');
            formCard.className = 'card';
            formCard.style.cssText = 'padding:16px;margin-bottom:16px;display:none;';
            this._els.formCard = formCard;
            this._buildForm(formCard);

            // Test result panel (hidden)
            var testPanel = document.createElement('div');
            testPanel.className = 'card';
            testPanel.style.cssText = 'padding:16px;margin-bottom:16px;display:none;';
            this._els.testPanel = testPanel;

            // Webhooks table
            var tableWrap = document.createElement('div');
            tableWrap.className = 'table-container';
            tableWrap.style.marginBottom = '20px';
            var tableHeader = document.createElement('div');
            tableHeader.className = 'table-header';
            var tableTitle = document.createElement('h2');
            tableTitle.textContent = 'Configured Webhooks';
            tableHeader.appendChild(tableTitle);

            var table = document.createElement('table');
            var thead = document.createElement('thead');
            var hRow = document.createElement('tr');
            ['URL', 'Events', 'Status', 'Last Delivery', 'Success Rate', 'Actions'].forEach(function(col) {
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

            // Delivery logs section
            var logsWrap = document.createElement('div');
            logsWrap.className = 'table-container';
            logsWrap.style.display = 'none';
            this._els.logsWrap = logsWrap;

            var logsHeader = document.createElement('div');
            logsHeader.className = 'table-header';
            var logsTitleRow = document.createElement('div');
            logsTitleRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;width:100%;';
            var logsTitle = document.createElement('h2');
            logsTitle.textContent = 'Delivery Logs';
            this._els.logsTitle = logsTitle;
            logsTitleRow.appendChild(logsTitle);
            var closeLogsBtn = document.createElement('button');
            closeLogsBtn.className = 'btn-ghost btn-sm';
            closeLogsBtn.textContent = 'Close';
            closeLogsBtn.addEventListener('click', function() { logsWrap.style.display = 'none'; });
            logsTitleRow.appendChild(closeLogsBtn);
            logsHeader.appendChild(logsTitleRow);

            var logsTable = document.createElement('table');
            var logsThead = document.createElement('thead');
            var logsHRow = document.createElement('tr');
            ['Timestamp', 'Event', 'Status Code', 'Response Time', 'Retry Count'].forEach(function(col) {
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

            var body = document.createElement('div');
            body.className = 'page-body';
            body.appendChild(formCard);
            body.appendChild(testPanel);
            body.appendChild(tableWrap);
            body.appendChild(logsWrap);

            container.appendChild(header);
            container.appendChild(body);
        },

        _buildForm: function(card) {
            var self = this;

            var formTitle = document.createElement('h3');
            formTitle.style.marginBottom = '12px';
            this._els.formTitle = formTitle;
            card.appendChild(formTitle);

            // URL
            var urlGroup = document.createElement('div');
            urlGroup.style.marginBottom = '12px';
            var urlLbl = document.createElement('label');
            urlLbl.textContent = 'Webhook URL';
            urlLbl.style.cssText = 'display:block;margin-bottom:4px;font-weight:600;font-size:13px;';
            var urlInput = document.createElement('input');
            urlInput.type = 'url';
            urlInput.placeholder = 'https://example.com/webhook';
            urlInput.style.cssText = 'width:100%;padding:8px;border:1px solid var(--border-color);border-radius:4px;background:var(--bg-primary);color:var(--text-primary);box-sizing:border-box;';
            this._els.urlInput = urlInput;
            urlGroup.appendChild(urlLbl);
            urlGroup.appendChild(urlInput);
            card.appendChild(urlGroup);

            // Events multi-select
            var eventsGroup = document.createElement('div');
            eventsGroup.style.marginBottom = '12px';
            var eventsLbl = document.createElement('label');
            eventsLbl.textContent = 'Events';
            eventsLbl.style.cssText = 'display:block;margin-bottom:4px;font-weight:600;font-size:13px;';
            eventsGroup.appendChild(eventsLbl);
            var eventsContainer = document.createElement('div');
            eventsContainer.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;padding:8px;border:1px solid var(--border-color);border-radius:4px;max-height:160px;overflow-y:auto;';
            this._els.eventsContainer = eventsContainer;
            eventsGroup.appendChild(eventsContainer);
            card.appendChild(eventsGroup);

            // Secret
            var secretGroup = document.createElement('div');
            secretGroup.style.marginBottom = '12px';
            var secretLbl = document.createElement('label');
            secretLbl.textContent = 'Secret';
            secretLbl.style.cssText = 'display:block;margin-bottom:4px;font-weight:600;font-size:13px;';
            secretGroup.appendChild(secretLbl);

            var secretRow = document.createElement('div');
            secretRow.style.cssText = 'display:flex;gap:8px;';
            var secretInput = document.createElement('input');
            secretInput.type = 'text';
            secretInput.placeholder = 'Webhook signing secret';
            secretInput.style.cssText = 'flex:1;padding:8px;border:1px solid var(--border-color);border-radius:4px;background:var(--bg-primary);color:var(--text-primary);font-family:monospace;';
            this._els.secretInput = secretInput;
            secretRow.appendChild(secretInput);

            var genBtn = document.createElement('button');
            genBtn.className = 'btn-secondary btn-sm';
            genBtn.textContent = 'Generate';
            genBtn.addEventListener('click', function() {
                secretInput.value = generateSecret(32);
            });
            secretRow.appendChild(genBtn);
            secretGroup.appendChild(secretRow);
            card.appendChild(secretGroup);

            // Active toggle
            var toggleWrap = document.createElement('div');
            toggleWrap.style.cssText = 'margin-bottom:16px;display:flex;align-items:center;gap:8px;';
            var activeCheck = document.createElement('input');
            activeCheck.type = 'checkbox';
            activeCheck.id = 'webhookActiveToggle';
            activeCheck.checked = true;
            this._els.activeCheck = activeCheck;
            var activeLbl = document.createElement('label');
            activeLbl.htmlFor = 'webhookActiveToggle';
            activeLbl.textContent = 'Active';
            activeLbl.style.cursor = 'pointer';
            toggleWrap.appendChild(activeCheck);
            toggleWrap.appendChild(activeLbl);
            card.appendChild(toggleWrap);

            // Buttons
            var btnRow = document.createElement('div');
            btnRow.style.cssText = 'display:flex;gap:8px;';
            var saveBtn = document.createElement('button');
            saveBtn.className = 'btn-primary btn-sm';
            saveBtn.textContent = 'Save';
            saveBtn.addEventListener('click', this._saveWebhook.bind(this));

            var cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn-ghost btn-sm';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.addEventListener('click', function() { card.style.display = 'none'; self._editingId = null; });

            btnRow.appendChild(saveBtn);
            btnRow.appendChild(cancelBtn);
            card.appendChild(btnRow);
        },

        load: function() {
            this._loadEvents();
            this._loadWebhooks();
        },

        destroy: function() {},

        _loadEvents: function() {
            var self = this;
            fetch('/api/webhooks/events', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    self._availableEvents = Array.isArray(data) ? data : (data.events || []);
                    self._renderEventCheckboxes();
                })
                .catch(function() {
                    self._availableEvents = [
                        'report.received', 'report.processed', 'alert.triggered',
                        'threat.detected', 'policy.changed', 'ingestion.completed'
                    ];
                    self._renderEventCheckboxes();
                });
        },

        _renderEventCheckboxes: function(selected) {
            var container = this._els.eventsContainer;
            if (!container) return;
            clearElement(container);

            var selectedSet = {};
            if (selected) {
                selected.forEach(function(e) { selectedSet[e] = true; });
            }

            this._availableEvents.forEach(function(evt) {
                var evtName = typeof evt === 'string' ? evt : (evt.name || evt.event || '');
                if (!evtName) return;

                var label = document.createElement('label');
                label.style.cssText = 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:13px;min-width:180px;';
                var cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.value = evtName;
                cb.dataset.eventCheckbox = 'true';
                if (selectedSet[evtName]) cb.checked = true;
                label.appendChild(cb);
                label.appendChild(document.createTextNode(evtName));
                container.appendChild(label);
            });
        },

        _getSelectedEvents: function() {
            var container = this._els.eventsContainer;
            if (!container) return [];
            var checked = [];
            var cbs = container.querySelectorAll('input[data-event-checkbox]');
            for (var i = 0; i < cbs.length; i++) {
                if (cbs[i].checked) checked.push(cbs[i].value);
            }
            return checked;
        },

        _loadWebhooks: function() {
            var self = this;
            fetch('/api/webhooks/', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var hooks = Array.isArray(data) ? data : (data.webhooks || []);
                    self._renderWebhooks(hooks);
                })
                .catch(function() { notify('Failed to load webhooks', 'error'); });
        },

        _renderWebhooks: function(hooks) {
            var self = this;
            var tbody = this._els.tbody;
            if (!tbody) return;
            clearElement(tbody);

            if (hooks.length === 0) {
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.colSpan = 6;
                td.textContent = 'No webhooks configured.';
                td.style.textAlign = 'center';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            hooks.forEach(function(hook) {
                var tr = document.createElement('tr');

                // URL (truncated)
                var tdUrl = document.createElement('td');
                var url = hook.url || '-';
                tdUrl.textContent = url.length > 50 ? url.substring(0, 50) + '...' : url;
                tdUrl.title = url;
                tdUrl.style.maxWidth = '250px';
                tr.appendChild(tdUrl);

                // Events (tag badges)
                var tdEvents = document.createElement('td');
                var events = hook.events || [];
                events.forEach(function(evt) {
                    var tag = document.createElement('span');
                    tag.className = 'badge';
                    tag.style.cssText = 'margin:2px;font-size:11px;';
                    tag.textContent = evt;
                    tdEvents.appendChild(tag);
                });
                if (events.length === 0) {
                    tdEvents.textContent = '-';
                }
                tr.appendChild(tdEvents);

                // Status
                var tdStatus = document.createElement('td');
                var statusBadge = document.createElement('span');
                statusBadge.className = 'badge ' + (hook.is_active ? 'badge-success' : 'badge-gray');
                statusBadge.textContent = hook.is_active ? 'Active' : 'Inactive';
                tdStatus.appendChild(statusBadge);
                tr.appendChild(tdStatus);

                // Last Delivery
                var tdLastDel = document.createElement('td');
                tdLastDel.textContent = hook.last_delivery ? new Date(hook.last_delivery).toLocaleString() : 'Never';
                tr.appendChild(tdLastDel);

                // Success Rate
                var tdRate = document.createElement('td');
                var rate = hook.success_rate;
                if (rate != null) {
                    var rateBadge = document.createElement('span');
                    var rateNum = typeof rate === 'number' ? rate : parseFloat(rate);
                    rateBadge.className = 'badge ' + (rateNum >= 90 ? 'badge-success' : rateNum >= 50 ? 'badge-warning' : 'badge-danger');
                    rateBadge.textContent = rateNum.toFixed(1) + '%';
                    tdRate.appendChild(rateBadge);
                } else {
                    tdRate.textContent = '-';
                }
                tr.appendChild(tdRate);

                // Actions
                var tdActions = document.createElement('td');

                var editBtn = document.createElement('button');
                editBtn.className = 'btn-ghost btn-sm';
                editBtn.textContent = 'Edit';
                editBtn.addEventListener('click', function() { self._editWebhook(hook); });
                tdActions.appendChild(editBtn);

                var testBtn = document.createElement('button');
                testBtn.className = 'btn-ghost btn-sm';
                testBtn.textContent = 'Test';
                testBtn.addEventListener('click', function() { self._testWebhook(hook.id); });
                tdActions.appendChild(testBtn);

                var logsBtn = document.createElement('button');
                logsBtn.className = 'btn-ghost btn-sm';
                logsBtn.textContent = 'Logs';
                logsBtn.addEventListener('click', function() { self._viewLogs(hook.id, hook.url); });
                tdActions.appendChild(logsBtn);

                var delBtn = document.createElement('button');
                delBtn.className = 'btn-ghost btn-sm';
                delBtn.style.color = 'var(--accent-danger)';
                delBtn.textContent = 'Delete';
                delBtn.addEventListener('click', function() { self._deleteWebhook(hook.id, hook.url); });
                tdActions.appendChild(delBtn);

                tr.appendChild(tdActions);
                tbody.appendChild(tr);
            });
        },

        _showCreateForm: function() {
            this._editingId = null;
            this._els.formTitle.textContent = 'Add Webhook';
            this._els.urlInput.value = '';
            this._els.secretInput.value = '';
            this._els.activeCheck.checked = true;
            this._renderEventCheckboxes([]);
            this._els.formCard.style.display = '';
            this._els.urlInput.focus();
        },

        _editWebhook: function(hook) {
            this._editingId = hook.id;
            this._els.formTitle.textContent = 'Edit Webhook';
            this._els.urlInput.value = hook.url || '';
            this._els.secretInput.value = hook.secret || '';
            this._els.activeCheck.checked = hook.is_active !== false;
            this._renderEventCheckboxes(hook.events || []);
            this._els.formCard.style.display = '';
        },

        _saveWebhook: function() {
            var self = this;
            var url = this._els.urlInput.value.trim();
            var events = this._getSelectedEvents();
            var secret = this._els.secretInput.value.trim();
            var isActive = this._els.activeCheck.checked;

            if (!url) {
                notify('URL is required', 'error');
                return;
            }

            var payload = {
                url: url,
                events: events,
                secret: secret || undefined,
                is_active: isActive
            };

            var apiUrl = '/api/webhooks/';
            var method = 'POST';
            if (this._editingId) {
                apiUrl = '/api/webhooks/' + this._editingId;
                method = 'PUT';
            }

            fetch(apiUrl, {
                method: method,
                headers: Object.assign({ 'Content-Type': 'application/json' }, getAuthHeaders()),
                body: JSON.stringify(payload)
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Failed to save webhook');
                return r.json();
            })
            .then(function() {
                notify('Webhook saved', 'success');
                self._els.formCard.style.display = 'none';
                self._editingId = null;
                self._loadWebhooks();
            })
            .catch(function(err) { notify(err.message, 'error'); });
        },

        _deleteWebhook: function(id, url) {
            if (!confirm('Delete webhook for ' + (url || id) + '?')) return;
            var self = this;
            fetch('/api/webhooks/' + id, { method: 'DELETE', headers: getAuthHeaders() })
                .then(function(r) {
                    if (!r.ok) throw new Error('Failed');
                    notify('Webhook deleted', 'success');
                    self._loadWebhooks();
                })
                .catch(function() { notify('Failed to delete webhook', 'error'); });
        },

        _testWebhook: function(id) {
            var self = this;
            var panel = this._els.testPanel;
            if (!panel) return;
            panel.style.display = '';
            clearElement(panel);
            var loading = document.createElement('p');
            loading.className = 'loading';
            loading.textContent = 'Sending test delivery...';
            panel.appendChild(loading);

            fetch('/api/webhooks/' + id + '/test', { method: 'POST', headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) { self._renderTestResult(panel, data); })
                .catch(function() {
                    clearElement(panel);
                    var err = document.createElement('p');
                    err.textContent = 'Test delivery failed.';
                    err.style.color = 'var(--accent-danger)';
                    panel.appendChild(err);
                });
        },

        _renderTestResult: function(panel, data) {
            clearElement(panel);

            var titleRow = document.createElement('div');
            titleRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;';
            var title = document.createElement('h3');
            title.textContent = 'Test Delivery Result';
            titleRow.appendChild(title);
            var closeBtn = document.createElement('button');
            closeBtn.className = 'btn-ghost btn-sm';
            closeBtn.textContent = 'Close';
            closeBtn.addEventListener('click', function() { panel.style.display = 'none'; });
            titleRow.appendChild(closeBtn);
            panel.appendChild(titleRow);

            var success = data.success || data.status_code === 200 || (data.status_code >= 200 && data.status_code < 300);
            var statusBadge = document.createElement('span');
            statusBadge.className = 'badge ' + (success ? 'badge-success' : 'badge-danger');
            statusBadge.textContent = success ? 'Success' : 'Failed';
            panel.appendChild(statusBadge);

            var fields = [
                ['Status Code', data.status_code || '-'],
                ['Response Time', data.response_time ? data.response_time + 'ms' : '-'],
                ['Response Body', data.response_body || data.message || '-']
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

        _viewLogs: function(id, url) {
            var self = this;
            var wrap = this._els.logsWrap;
            if (!wrap) return;
            wrap.style.display = '';

            if (this._els.logsTitle) {
                this._els.logsTitle.textContent = 'Delivery Logs' + (url ? ' - ' + (url.length > 40 ? url.substring(0, 40) + '...' : url) : '');
            }

            clearElement(this._els.logsTbody);
            var loadingTr = document.createElement('tr');
            var loadingTd = document.createElement('td');
            loadingTd.colSpan = 5;
            loadingTd.className = 'loading';
            loadingTd.textContent = 'Loading logs...';
            loadingTr.appendChild(loadingTd);
            this._els.logsTbody.appendChild(loadingTr);

            fetch('/api/webhooks/' + id + '/logs?limit=50', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var logs = Array.isArray(data) ? data : (data.logs || []);
                    self._renderLogs(logs);
                })
                .catch(function() {
                    clearElement(self._els.logsTbody);
                    var tr = document.createElement('tr');
                    var td = document.createElement('td');
                    td.colSpan = 5;
                    td.textContent = 'Failed to load logs.';
                    td.style.color = 'var(--accent-danger)';
                    tr.appendChild(td);
                    self._els.logsTbody.appendChild(tr);
                });
        },

        _renderLogs: function(logs) {
            var tbody = this._els.logsTbody;
            if (!tbody) return;
            clearElement(tbody);

            if (logs.length === 0) {
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.colSpan = 5;
                td.textContent = 'No delivery logs found.';
                td.style.textAlign = 'center';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            logs.forEach(function(log) {
                var tr = document.createElement('tr');

                var tdTime = document.createElement('td');
                tdTime.textContent = log.timestamp ? new Date(log.timestamp).toLocaleString() : (log.created_at ? new Date(log.created_at).toLocaleString() : '-');
                tr.appendChild(tdTime);

                var tdEvent = document.createElement('td');
                tdEvent.textContent = log.event || log.event_type || '-';
                tr.appendChild(tdEvent);

                var tdCode = document.createElement('td');
                var code = log.status_code || log.response_code;
                if (code) {
                    var codeBadge = document.createElement('span');
                    var codeNum = parseInt(code, 10);
                    codeBadge.className = 'badge ' + (codeNum >= 200 && codeNum < 300 ? 'badge-success' : codeNum >= 400 ? 'badge-danger' : 'badge-warning');
                    codeBadge.textContent = code;
                    tdCode.appendChild(codeBadge);
                } else {
                    tdCode.textContent = '-';
                }
                tr.appendChild(tdCode);

                var tdRespTime = document.createElement('td');
                tdRespTime.textContent = log.response_time ? log.response_time + 'ms' : '-';
                tr.appendChild(tdRespTime);

                var tdRetry = document.createElement('td');
                tdRetry.textContent = log.retry_count != null ? log.retry_count : (log.retries != null ? log.retries : '-');
                tr.appendChild(tdRetry);

                tbody.appendChild(tr);
            });
        }
    };

    window.DMARC = window.DMARC || {};
    window.DMARC.WebhooksPage = WebhooksPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('webhooks', WebhooksPage);
    }
})();
