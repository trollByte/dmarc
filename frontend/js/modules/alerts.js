/**
 * DMARC Dashboard - Alert Management Page Module
 * Manages active alerts, history, alert rules, and suppressions.
 */
(function() {
    'use strict';

    var refreshTimer = null;
    var currentTab = 'active';
    var historyOffset = 0;
    var historyLimit = 20;
    var selectedAlertIds = [];

    function isAdmin() {
        var user = window.DMARC && window.DMARC.currentUser;
        if (!user) user = (typeof currentUser !== 'undefined') ? currentUser : null;
        return user && user.role === 'admin';
    }

    function authHeaders() {
        if (typeof getAuthHeaders === 'function') return getAuthHeaders();
        return {};
    }

    function apiBase() {
        return (typeof API_BASE !== 'undefined') ? API_BASE : '/api';
    }

    function notify(msg, type) {
        if (typeof showNotification === 'function') showNotification(msg, type || 'success');
    }

    function formatDate(dateStr) {
        if (!dateStr) return '-';
        var d = new Date(dateStr);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    }

    function getSection() {
        return document.getElementById('page-alerts');
    }

    // Safe DOM element creation helpers
    function el(tag, attrs, children) {
        var node = document.createElement(tag);
        if (attrs) {
            Object.keys(attrs).forEach(function(k) {
                if (k === 'className') node.className = attrs[k];
                else if (k === 'textContent') node.textContent = attrs[k];
                else if (k === 'hidden') node.hidden = attrs[k];
                else if (k === 'disabled') node.disabled = attrs[k];
                else if (k === 'checked') node.checked = attrs[k];
                else if (k === 'htmlFor') node.htmlFor = attrs[k];
                else if (k.indexOf('on') === 0) node.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
                else if (k === 'style' && typeof attrs[k] === 'object') {
                    Object.keys(attrs[k]).forEach(function(sk) { node.style[sk] = attrs[k][sk]; });
                } else node.setAttribute(k, attrs[k]);
            });
        }
        if (children) {
            (Array.isArray(children) ? children : [children]).forEach(function(c) {
                if (c == null) return;
                if (typeof c === 'string') node.appendChild(document.createTextNode(c));
                else node.appendChild(c);
            });
        }
        return node;
    }

    function text(s) { return document.createTextNode(String(s || '')); }

    function severityBadge(severity) {
        var map = { critical: 'badge badge-danger', high: 'badge badge-warning', medium: 'badge badge-info', low: 'badge badge-gray' };
        var cls = map[(severity || '').toLowerCase()] || 'badge badge-gray';
        return el('span', { className: cls, textContent: severity || '' });
    }

    function statusBadge(status) {
        var map = { created: 'badge badge-danger', acknowledged: 'badge badge-warning', resolved: 'badge badge-success', suppressed: 'badge badge-gray' };
        var cls = map[(status || '').toLowerCase()] || 'badge badge-gray';
        return el('span', { className: cls, textContent: status || '' });
    }

    function closeIcon() {
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('class', 'icon');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', 'currentColor');
        svg.setAttribute('stroke-width', '2');
        var l1 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        l1.setAttribute('x1', '18'); l1.setAttribute('y1', '6'); l1.setAttribute('x2', '6'); l1.setAttribute('y2', '18');
        var l2 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        l2.setAttribute('x1', '6'); l2.setAttribute('y1', '6'); l2.setAttribute('x2', '18'); l2.setAttribute('y2', '18');
        svg.appendChild(l1);
        svg.appendChild(l2);
        return svg;
    }

    function clearChildren(node) {
        while (node.firstChild) node.removeChild(node.firstChild);
    }

    // =========================================
    // Stats
    // =========================================
    async function loadStats() {
        try {
            var res = await fetch(apiBase() + '/alerts/stats', { headers: authHeaders() });
            if (!res.ok) throw new Error('Failed to load stats');
            var data = await res.json();
            var container = document.getElementById('alerts-stats');
            if (!container) return;

            var total = data.total || 0;
            var bySeverity = data.by_severity || {};
            var critical = bySeverity.critical || 0;
            var high = bySeverity.high || 0;
            var medium = (bySeverity.medium || 0) + (bySeverity.low || 0);

            function statCard(label, value, extraClass, borderColor) {
                var card = el('div', { className: 'stat-card' + (extraClass ? ' ' + extraClass : '') });
                if (borderColor) card.style.borderLeft = '4px solid ' + borderColor;
                card.appendChild(el('div', { className: 'stat-header' }, [el('h3', {}, [label])]));
                card.appendChild(el('div', { className: 'stat-content' }, [el('div', { className: 'stat-value', textContent: String(value) })]));
                return card;
            }

            clearChildren(container);
            container.appendChild(statCard('Active Alerts', total, 'stat-card-danger', null));
            container.appendChild(statCard('Critical', critical, null, '#dc2626'));
            container.appendChild(statCard('High', high, null, '#f59e0b'));
            container.appendChild(statCard('Medium / Low', medium, null, '#6b7280'));
        } catch (e) {
            console.error('Error loading alert stats:', e);
        }
    }

    // =========================================
    // Active Alerts Tab
    // =========================================
    async function loadActiveAlerts() {
        var tbody = document.getElementById('alerts-active-tbody');
        if (!tbody) return;
        clearChildren(tbody);
        tbody.appendChild(el('tr', {}, [el('td', { colspan: '7', className: 'loading', textContent: 'Loading alerts...' })]));

        try {
            var res = await fetch(apiBase() + '/alerts/active', { headers: authHeaders() });
            if (!res.ok) throw new Error('Failed to load alerts');
            var data = await res.json();
            var alerts = Array.isArray(data) ? data : (data.alerts || []);

            clearChildren(tbody);

            if (alerts.length === 0) {
                var emptyTd = el('td', { colspan: '7', textContent: 'No active alerts' });
                emptyTd.style.textAlign = 'center';
                emptyTd.style.padding = '32px';
                emptyTd.style.color = 'var(--text-secondary)';
                tbody.appendChild(el('tr', {}, [emptyTd]));
                return;
            }

            selectedAlertIds = [];
            updateBulkToolbar();

            alerts.forEach(function(a) {
                var cb = el('input', { type: 'checkbox', className: 'alert-select-cb' });
                cb.addEventListener('change', function() {
                    var id = String(a.id);
                    if (cb.checked) {
                        if (selectedAlertIds.indexOf(id) === -1) selectedAlertIds.push(id);
                    } else {
                        selectedAlertIds = selectedAlertIds.filter(function(x) { return x !== id; });
                    }
                    updateBulkToolbar();
                });

                var actionsTd = el('td', { className: 'alert-actions-cell' });
                if (a.status !== 'acknowledged') {
                    var ackBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Acknowledge' });
                    ackBtn.addEventListener('click', function() { acknowledgeAlert(a.id); });
                    actionsTd.appendChild(ackBtn);
                }
                var resolveBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Resolve' });
                resolveBtn.addEventListener('click', function() { resolveAlert(a.id); });
                actionsTd.appendChild(resolveBtn);

                var row = el('tr', {}, [
                    el('td', {}, [cb]),
                    el('td', {}, [severityBadge(a.severity)]),
                    el('td', { textContent: a.alert_type || a.type || '' }),
                    el('td', { textContent: a.title || a.message || '-' }),
                    el('td', { textContent: a.domain || '-' }),
                    el('td', { textContent: formatDate(a.created_at) }),
                    actionsTd
                ]);
                tbody.appendChild(row);
            });
        } catch (e) {
            console.error('Error loading active alerts:', e);
            clearChildren(tbody);
            var errTd = el('td', { colspan: '7', textContent: 'Failed to load alerts' });
            errTd.style.textAlign = 'center';
            errTd.style.padding = '32px';
            errTd.style.color = 'var(--accent-danger)';
            tbody.appendChild(el('tr', {}, [errTd]));
        }
    }

    function updateBulkToolbar() {
        var toolbar = document.getElementById('alerts-bulk-toolbar');
        if (!toolbar) return;
        if (selectedAlertIds.length > 0) {
            toolbar.hidden = false;
            var count = toolbar.querySelector('.bulk-count');
            if (count) count.textContent = selectedAlertIds.length + ' selected';
        } else {
            toolbar.hidden = true;
        }
    }

    function toggleSelectAll() {
        var section = getSection();
        if (!section) return;
        var cbs = section.querySelectorAll('.alert-select-cb');
        var allChecked = selectedAlertIds.length > 0 && selectedAlertIds.length === cbs.length;

        selectedAlertIds = [];
        cbs.forEach(function(cb) {
            cb.checked = !allChecked;
            if (!allChecked) {
                // Derive id from the row position; re-read from loaded data
                var row = cb.closest('tr');
                if (row) {
                    var idText = row.querySelectorAll('td')[2]; // type column not useful, use a different approach
                }
            }
        });
        // Simpler: re-trigger change events
        cbs.forEach(function(cb) {
            cb.dispatchEvent(new Event('change'));
        });
    }

    async function acknowledgeAlert(id) {
        try {
            var res = await fetch(apiBase() + '/alerts/' + id + '/acknowledge', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
                body: JSON.stringify({ notes: '' })
            });
            if (!res.ok) throw new Error('Failed to acknowledge');
            notify('Alert acknowledged', 'success');
            loadActiveAlerts();
            loadStats();
        } catch (e) {
            notify('Failed to acknowledge alert', 'error');
        }
    }

    async function resolveAlert(id) {
        try {
            var res = await fetch(apiBase() + '/alerts/' + id + '/resolve', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
                body: JSON.stringify({ notes: '' })
            });
            if (!res.ok) throw new Error('Failed to resolve');
            notify('Alert resolved', 'success');
            loadActiveAlerts();
            loadStats();
        } catch (e) {
            notify('Failed to resolve alert', 'error');
        }
    }

    async function bulkAcknowledge() {
        if (selectedAlertIds.length === 0) return;
        try {
            var res = await fetch(apiBase() + '/alerts/acknowledge/bulk', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
                body: JSON.stringify({ alert_ids: selectedAlertIds })
            });
            if (!res.ok) throw new Error('Failed');
            notify(selectedAlertIds.length + ' alerts acknowledged', 'success');
            selectedAlertIds = [];
            loadActiveAlerts();
            loadStats();
        } catch (e) {
            notify('Bulk acknowledge failed', 'error');
        }
    }

    async function bulkResolve() {
        if (selectedAlertIds.length === 0) return;
        try {
            var res = await fetch(apiBase() + '/alerts/resolve/bulk', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
                body: JSON.stringify({ alert_ids: selectedAlertIds })
            });
            if (!res.ok) throw new Error('Failed');
            notify(selectedAlertIds.length + ' alerts resolved', 'success');
            selectedAlertIds = [];
            loadActiveAlerts();
            loadStats();
        } catch (e) {
            notify('Bulk resolve failed', 'error');
        }
    }

    // =========================================
    // History Tab
    // =========================================
    async function loadHistory() {
        var tbody = document.getElementById('alerts-history-tbody');
        if (!tbody) return;
        clearChildren(tbody);
        tbody.appendChild(el('tr', {}, [el('td', { colspan: '8', className: 'loading', textContent: 'Loading history...' })]));

        var params = new URLSearchParams();
        var domainEl = document.getElementById('alerts-hist-domain');
        var severityEl = document.getElementById('alerts-hist-severity');
        var statusEl = document.getElementById('alerts-hist-status');
        var daysEl = document.getElementById('alerts-hist-days');

        if (domainEl && domainEl.value) params.set('domain', domainEl.value);
        if (severityEl && severityEl.value) params.set('severity', severityEl.value);
        if (statusEl && statusEl.value) params.set('status', statusEl.value);
        if (daysEl && daysEl.value) params.set('days', daysEl.value);
        params.set('limit', historyLimit);
        params.set('offset', historyOffset);

        try {
            var res = await fetch(apiBase() + '/alerts/history?' + params.toString(), { headers: authHeaders() });
            if (!res.ok) throw new Error('Failed to load history');
            var data = await res.json();
            var alerts = Array.isArray(data) ? data : (data.alerts || data.items || []);
            var total = data.total || alerts.length;

            clearChildren(tbody);

            if (alerts.length === 0) {
                var emptyTd = el('td', { colspan: '8', textContent: 'No alert history found' });
                emptyTd.style.textAlign = 'center';
                emptyTd.style.padding = '32px';
                emptyTd.style.color = 'var(--text-secondary)';
                tbody.appendChild(el('tr', {}, [emptyTd]));
                updateHistoryPagination(0);
                return;
            }

            alerts.forEach(function(a) {
                tbody.appendChild(el('tr', {}, [
                    el('td', {}, [severityBadge(a.severity)]),
                    el('td', { textContent: a.alert_type || a.type || '' }),
                    el('td', { textContent: a.title || a.message || '-' }),
                    el('td', { textContent: a.domain || '-' }),
                    el('td', {}, [statusBadge(a.status)]),
                    el('td', { textContent: formatDate(a.created_at) }),
                    el('td', { textContent: formatDate(a.acknowledged_at) }),
                    el('td', { textContent: formatDate(a.resolved_at) })
                ]));
            });

            updateHistoryPagination(total);
        } catch (e) {
            console.error('Error loading alert history:', e);
            clearChildren(tbody);
            var errTd = el('td', { colspan: '8', textContent: 'Failed to load history' });
            errTd.style.textAlign = 'center';
            errTd.style.padding = '32px';
            errTd.style.color = 'var(--accent-danger)';
            tbody.appendChild(el('tr', {}, [errTd]));
        }
    }

    function updateHistoryPagination(total) {
        var container = document.getElementById('alerts-history-pagination');
        if (!container) return;
        clearChildren(container);

        var totalPages = Math.ceil(total / historyLimit);
        var currentPage = Math.floor(historyOffset / historyLimit) + 1;

        if (totalPages <= 1) return;

        var prevBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Previous', disabled: currentPage <= 1 });
        prevBtn.addEventListener('click', function() {
            historyOffset = (currentPage - 2) * historyLimit;
            loadHistory();
        });

        var nextBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Next', disabled: currentPage >= totalPages });
        nextBtn.addEventListener('click', function() {
            historyOffset = currentPage * historyLimit;
            loadHistory();
        });

        var pagDiv = el('div', { className: 'pagination' }, [
            prevBtn,
            el('span', { className: 'pagination-info', textContent: 'Page ' + currentPage + ' of ' + totalPages }),
            nextBtn
        ]);
        container.appendChild(pagDiv);
    }

    // =========================================
    // Rules Tab (Admin)
    // =========================================
    async function loadRules() {
        var tbody = document.getElementById('alerts-rules-tbody');
        if (!tbody) return;
        clearChildren(tbody);
        tbody.appendChild(el('tr', {}, [el('td', { colspan: '5', className: 'loading', textContent: 'Loading rules...' })]));

        try {
            var res = await fetch(apiBase() + '/alerts/rules', { headers: authHeaders() });
            if (!res.ok) throw new Error('Failed');
            var data = await res.json();
            var rules = Array.isArray(data) ? data : (data.rules || []);

            clearChildren(tbody);

            if (rules.length === 0) {
                var emptyTd = el('td', { colspan: '5', textContent: 'No alert rules configured' });
                emptyTd.style.textAlign = 'center';
                emptyTd.style.padding = '32px';
                emptyTd.style.color = 'var(--text-secondary)';
                tbody.appendChild(el('tr', {}, [emptyTd]));
                return;
            }

            rules.forEach(function(r) {
                var toggle = el('input', { type: 'checkbox', checked: !!r.is_active });
                toggle.addEventListener('change', function() {
                    toggleRule(r.id, toggle.checked);
                });
                var toggleLabel = el('label', { className: 'toggle-switch' }, [toggle, el('span', { className: 'toggle-slider' })]);

                var editBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Edit' });
                editBtn.addEventListener('click', function() { openRuleModal(r); });

                var deleteBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Delete' });
                deleteBtn.style.color = 'var(--accent-danger)';
                deleteBtn.addEventListener('click', function() {
                    if (confirm('Delete this alert rule?')) deleteRule(r.id);
                });

                tbody.appendChild(el('tr', {}, [
                    el('td', { textContent: r.name || '' }),
                    el('td', { textContent: r.alert_type || '' }),
                    el('td', {}, [severityBadge(r.severity)]),
                    el('td', {}, [toggleLabel]),
                    el('td', {}, [editBtn, deleteBtn])
                ]));
            });
        } catch (e) {
            console.error('Error loading rules:', e);
            clearChildren(tbody);
            var errTd = el('td', { colspan: '5', textContent: 'Failed to load rules' });
            errTd.style.textAlign = 'center';
            errTd.style.padding = '32px';
            errTd.style.color = 'var(--accent-danger)';
            tbody.appendChild(el('tr', {}, [errTd]));
        }
    }

    async function toggleRule(id, isActive) {
        try {
            var res = await fetch(apiBase() + '/alerts/rules/' + id, {
                method: 'PATCH',
                headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
                body: JSON.stringify({ is_active: isActive })
            });
            if (!res.ok) throw new Error('Failed');
            notify('Rule ' + (isActive ? 'enabled' : 'disabled'), 'success');
        } catch (e) {
            notify('Failed to update rule', 'error');
            loadRules();
        }
    }

    async function deleteRule(id) {
        try {
            var res = await fetch(apiBase() + '/alerts/rules/' + id, {
                method: 'DELETE',
                headers: authHeaders()
            });
            if (!res.ok) throw new Error('Failed');
            notify('Rule deleted', 'success');
            loadRules();
        } catch (e) {
            notify('Failed to delete rule', 'error');
        }
    }

    function openRuleModal(rule) {
        var modal = document.getElementById('alertRuleModal');
        if (!modal) return;
        var title = document.getElementById('alertRuleModalTitle');
        var form = document.getElementById('alertRuleForm');

        if (title) title.textContent = rule ? 'Edit Alert Rule' : 'Create Alert Rule';
        if (form) {
            form.setAttribute('data-rule-id', rule ? rule.id : '');
            form.elements['ruleName'].value = rule ? rule.name : '';
            form.elements['ruleType'].value = rule ? rule.alert_type : '';
            form.elements['ruleSeverity'].value = rule ? rule.severity : 'medium';
            form.elements['ruleActive'].checked = rule ? rule.is_active : true;
            form.elements['ruleChannels'].value = rule && rule.channels ? rule.channels.join(', ') : '';
            form.elements['ruleConditions'].value = rule && rule.conditions ? JSON.stringify(rule.conditions, null, 2) : '{}';
        }
        modal.hidden = false;
    }

    function closeRuleModal() {
        var modal = document.getElementById('alertRuleModal');
        if (modal) modal.hidden = true;
    }

    async function saveRule(e) {
        e.preventDefault();
        var form = document.getElementById('alertRuleForm');
        if (!form) return;

        var id = form.getAttribute('data-rule-id');
        var channels = form.elements['ruleChannels'].value.split(',').map(function(c) { return c.trim(); }).filter(Boolean);
        var conditions;
        try {
            conditions = JSON.parse(form.elements['ruleConditions'].value || '{}');
        } catch (err) {
            notify('Invalid JSON in conditions', 'error');
            return;
        }

        var body = {
            name: form.elements['ruleName'].value,
            alert_type: form.elements['ruleType'].value,
            severity: form.elements['ruleSeverity'].value,
            is_active: form.elements['ruleActive'].checked,
            channels: channels,
            conditions: conditions
        };

        try {
            var url = apiBase() + '/alerts/rules' + (id ? '/' + id : '');
            var method = id ? 'PATCH' : 'POST';
            var res = await fetch(url, {
                method: method,
                headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
                body: JSON.stringify(body)
            });
            if (!res.ok) throw new Error('Failed to save');
            notify('Rule ' + (id ? 'updated' : 'created'), 'success');
            closeRuleModal();
            loadRules();
        } catch (e) {
            notify('Failed to save rule', 'error');
        }
    }

    // =========================================
    // Suppressions Tab (Admin)
    // =========================================
    async function loadSuppressions() {
        var tbody = document.getElementById('alerts-suppressions-tbody');
        if (!tbody) return;
        clearChildren(tbody);
        tbody.appendChild(el('tr', {}, [el('td', { colspan: '6', className: 'loading', textContent: 'Loading suppressions...' })]));

        try {
            var res = await fetch(apiBase() + '/alerts/suppressions', { headers: authHeaders() });
            if (!res.ok) throw new Error('Failed');
            var data = await res.json();
            var items = Array.isArray(data) ? data : (data.suppressions || []);

            clearChildren(tbody);

            if (items.length === 0) {
                var emptyTd = el('td', { colspan: '6', textContent: 'No active suppressions' });
                emptyTd.style.textAlign = 'center';
                emptyTd.style.padding = '32px';
                emptyTd.style.color = 'var(--text-secondary)';
                tbody.appendChild(el('tr', {}, [emptyTd]));
                return;
            }

            items.forEach(function(s) {
                var deleteBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Delete' });
                deleteBtn.style.color = 'var(--accent-danger)';
                deleteBtn.addEventListener('click', function() {
                    if (confirm('Delete this suppression?')) deleteSuppression(s.id);
                });

                tbody.appendChild(el('tr', {}, [
                    el('td', { textContent: s.domain || '*' }),
                    el('td', { textContent: s.alert_type || '*' }),
                    el('td', { textContent: s.reason || '-' }),
                    el('td', { textContent: formatDate(s.starts_at) }),
                    el('td', { textContent: formatDate(s.ends_at) }),
                    el('td', {}, [deleteBtn])
                ]));
            });
        } catch (e) {
            console.error('Error loading suppressions:', e);
            clearChildren(tbody);
            var errTd = el('td', { colspan: '6', textContent: 'Failed to load suppressions' });
            errTd.style.textAlign = 'center';
            errTd.style.padding = '32px';
            errTd.style.color = 'var(--accent-danger)';
            tbody.appendChild(el('tr', {}, [errTd]));
        }
    }

    async function deleteSuppression(id) {
        try {
            var res = await fetch(apiBase() + '/alerts/suppressions/' + id, {
                method: 'DELETE',
                headers: authHeaders()
            });
            if (!res.ok) throw new Error('Failed');
            notify('Suppression deleted', 'success');
            loadSuppressions();
        } catch (e) {
            notify('Failed to delete suppression', 'error');
        }
    }

    function openSuppressionModal() {
        var modal = document.getElementById('alertSuppressionModal');
        if (!modal) return;
        var form = document.getElementById('alertSuppressionForm');
        if (form) form.reset();
        modal.hidden = false;
    }

    function closeSuppressionModal() {
        var modal = document.getElementById('alertSuppressionModal');
        if (modal) modal.hidden = true;
    }

    async function saveSuppression(e) {
        e.preventDefault();
        var form = document.getElementById('alertSuppressionForm');
        if (!form) return;

        var body = {
            domain: form.elements['suppDomain'].value,
            alert_type: form.elements['suppType'].value,
            reason: form.elements['suppReason'].value,
            starts_at: form.elements['suppStart'].value ? new Date(form.elements['suppStart'].value).toISOString() : null,
            ends_at: form.elements['suppEnd'].value ? new Date(form.elements['suppEnd'].value).toISOString() : null
        };

        try {
            var res = await fetch(apiBase() + '/alerts/suppressions', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
                body: JSON.stringify(body)
            });
            if (!res.ok) throw new Error('Failed');
            notify('Suppression created', 'success');
            closeSuppressionModal();
            loadSuppressions();
        } catch (e) {
            notify('Failed to create suppression', 'error');
        }
    }

    // =========================================
    // Tab Navigation
    // =========================================
    function switchTab(tabName) {
        currentTab = tabName;
        var section = getSection();
        if (!section) return;

        section.querySelectorAll('.alerts-tab-btn').forEach(function(btn) {
            btn.classList.toggle('active', btn.getAttribute('data-tab') === tabName);
        });

        section.querySelectorAll('.alerts-tab-panel').forEach(function(panel) {
            panel.hidden = panel.id !== 'alerts-panel-' + tabName;
        });

        if (tabName === 'active') loadActiveAlerts();
        else if (tabName === 'history') { historyOffset = 0; loadHistory(); }
        else if (tabName === 'rules') loadRules();
        else if (tabName === 'suppressions') loadSuppressions();
    }

    // =========================================
    // Render page structure (safe DOM construction)
    // =========================================
    function renderPage() {
        var section = getSection();
        if (!section) return;
        clearChildren(section);

        var admin = isAdmin();

        // Stats bar
        var statsSection = el('section', { className: 'stats-section', 'aria-label': 'Alert statistics' }, [
            el('div', { className: 'stats-grid', id: 'alerts-stats' })
        ]);

        // Tabs
        var tabsDiv = el('div', { className: 'alerts-tabs' });
        tabsDiv.style.display = 'flex';
        tabsDiv.style.gap = '8px';
        tabsDiv.style.marginBottom = '20px';
        tabsDiv.style.borderBottom = '2px solid var(--border-color)';
        tabsDiv.style.paddingBottom = '0';

        var tabActive = el('button', { className: 'alerts-tab-btn btn-ghost active', 'data-tab': 'active', textContent: 'Active Alerts' });
        var tabHistory = el('button', { className: 'alerts-tab-btn btn-ghost', 'data-tab': 'history', textContent: 'History' });
        tabsDiv.appendChild(tabActive);
        tabsDiv.appendChild(tabHistory);

        if (admin) {
            tabsDiv.appendChild(el('button', { className: 'alerts-tab-btn btn-ghost', 'data-tab': 'rules', textContent: 'Rules' }));
            tabsDiv.appendChild(el('button', { className: 'alerts-tab-btn btn-ghost', 'data-tab': 'suppressions', textContent: 'Suppressions' }));
        }

        // Active Alerts Panel
        var bulkToolbar = el('div', { id: 'alerts-bulk-toolbar', hidden: true });
        bulkToolbar.style.cssText = 'display:flex;gap:8px;align-items:center;margin-bottom:12px;padding:8px 12px;background:var(--bg-tertiary);border-radius:8px;';
        var bulkCount = el('span', { className: 'bulk-count' });
        bulkCount.style.fontWeight = '600';
        var bulkAckBtn = el('button', { className: 'btn-secondary btn-sm', id: 'alerts-bulk-ack-btn', textContent: 'Acknowledge Selected' });
        var bulkResolveBtn = el('button', { className: 'btn-secondary btn-sm', id: 'alerts-bulk-resolve-btn', textContent: 'Resolve Selected' });
        bulkToolbar.appendChild(bulkCount);
        bulkToolbar.appendChild(bulkAckBtn);
        bulkToolbar.appendChild(bulkResolveBtn);

        var selectAllCb = el('input', { type: 'checkbox', id: 'alerts-select-all', title: 'Select all' });

        var activeTable = el('div', { className: 'table-container' }, [
            el('table', {}, [
                el('thead', {}, [el('tr', {}, [
                    el('th', { style: { width: '40px' } }, [selectAllCb]),
                    el('th', { textContent: 'Severity' }),
                    el('th', { textContent: 'Type' }),
                    el('th', { textContent: 'Title' }),
                    el('th', { textContent: 'Domain' }),
                    el('th', { textContent: 'Created' }),
                    el('th', { textContent: 'Actions' })
                ])]),
                el('tbody', { id: 'alerts-active-tbody' })
            ])
        ]);

        var activePanel = el('div', { id: 'alerts-panel-active', className: 'alerts-tab-panel' }, [bulkToolbar, activeTable]);

        // History Panel
        var histFilters = el('div', { className: 'alerts-history-filters' });
        histFilters.style.cssText = 'display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;';

        function filterGroup(label, input) {
            var fg = el('div', { className: 'filter-group' });
            fg.appendChild(el('label', { textContent: label, htmlFor: input.id || '' }));
            fg.appendChild(input);
            return fg;
        }

        var histDomain = el('input', { type: 'text', id: 'alerts-hist-domain', placeholder: 'Filter by domain', className: 'global-search-input' });
        histDomain.style.width = '160px';
        var histSeverity = el('select', { id: 'alerts-hist-severity' }, [
            el('option', { value: '', textContent: 'All' }),
            el('option', { value: 'critical', textContent: 'Critical' }),
            el('option', { value: 'high', textContent: 'High' }),
            el('option', { value: 'medium', textContent: 'Medium' }),
            el('option', { value: 'low', textContent: 'Low' })
        ]);
        var histStatus = el('select', { id: 'alerts-hist-status' }, [
            el('option', { value: '', textContent: 'All' }),
            el('option', { value: 'created', textContent: 'Created' }),
            el('option', { value: 'acknowledged', textContent: 'Acknowledged' }),
            el('option', { value: 'resolved', textContent: 'Resolved' })
        ]);
        var histDays = el('select', { id: 'alerts-hist-days' }, [
            el('option', { value: '7', textContent: '7 days' }),
            el('option', { value: '30', textContent: '30 days', selected: 'selected' }),
            el('option', { value: '90', textContent: '90 days' }),
            el('option', { value: '365', textContent: '1 year' })
        ]);
        var histApplyBtn = el('button', { className: 'btn-primary btn-sm', id: 'alerts-hist-apply-btn', textContent: 'Apply' });
        var histApplyGroup = el('div', { className: 'filter-group' });
        histApplyGroup.style.alignSelf = 'flex-end';
        histApplyGroup.appendChild(histApplyBtn);

        histFilters.appendChild(filterGroup('Domain', histDomain));
        histFilters.appendChild(filterGroup('Severity', histSeverity));
        histFilters.appendChild(filterGroup('Status', histStatus));
        histFilters.appendChild(filterGroup('Period', histDays));
        histFilters.appendChild(histApplyGroup);

        var historyTable = el('div', { className: 'table-container' }, [
            el('table', {}, [
                el('thead', {}, [el('tr', {}, [
                    el('th', { textContent: 'Severity' }),
                    el('th', { textContent: 'Type' }),
                    el('th', { textContent: 'Title' }),
                    el('th', { textContent: 'Domain' }),
                    el('th', { textContent: 'Status' }),
                    el('th', { textContent: 'Created' }),
                    el('th', { textContent: 'Acknowledged' }),
                    el('th', { textContent: 'Resolved' })
                ])]),
                el('tbody', { id: 'alerts-history-tbody' })
            ])
        ]);

        var historyPanel = el('div', { id: 'alerts-panel-history', className: 'alerts-tab-panel', hidden: true }, [
            histFilters, historyTable, el('div', { id: 'alerts-history-pagination' })
        ]);
        historyPanel.querySelector('#alerts-history-pagination').style.marginTop = '16px';

        // Page wrapper
        var pageDiv = el('div', { className: 'alerts-page' }, [statsSection, tabsDiv, activePanel, historyPanel]);

        // Admin panels
        if (admin) {
            // Rules Panel
            var rulesHeader = el('div', { className: 'table-header' });
            rulesHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;';
            rulesHeader.appendChild(el('h3', { textContent: 'Alert Rules' }));
            var createRuleBtn = el('button', { className: 'btn-primary btn-sm', id: 'alerts-create-rule-btn', textContent: 'Create Rule' });
            rulesHeader.appendChild(createRuleBtn);

            var rulesTable = el('div', { className: 'table-container' }, [
                el('table', {}, [
                    el('thead', {}, [el('tr', {}, [
                        el('th', { textContent: 'Name' }),
                        el('th', { textContent: 'Type' }),
                        el('th', { textContent: 'Severity' }),
                        el('th', { textContent: 'Active' }),
                        el('th', { textContent: 'Actions' })
                    ])]),
                    el('tbody', { id: 'alerts-rules-tbody' })
                ])
            ]);

            pageDiv.appendChild(el('div', { id: 'alerts-panel-rules', className: 'alerts-tab-panel', hidden: true }, [rulesHeader, rulesTable]));

            // Suppressions Panel
            var suppHeader = el('div', { className: 'table-header' });
            suppHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;';
            suppHeader.appendChild(el('h3', { textContent: 'Alert Suppressions' }));
            var createSuppBtn = el('button', { className: 'btn-primary btn-sm', id: 'alerts-create-suppression-btn', textContent: 'Create Suppression' });
            suppHeader.appendChild(createSuppBtn);

            var suppTable = el('div', { className: 'table-container' }, [
                el('table', {}, [
                    el('thead', {}, [el('tr', {}, [
                        el('th', { textContent: 'Domain' }),
                        el('th', { textContent: 'Alert Type' }),
                        el('th', { textContent: 'Reason' }),
                        el('th', { textContent: 'Starts' }),
                        el('th', { textContent: 'Ends' }),
                        el('th', { textContent: 'Actions' })
                    ])]),
                    el('tbody', { id: 'alerts-suppressions-tbody' })
                ])
            ]);

            pageDiv.appendChild(el('div', { id: 'alerts-panel-suppressions', className: 'alerts-tab-panel', hidden: true }, [suppHeader, suppTable]));
        }

        section.appendChild(pageDiv);

        // Build Rule Modal
        section.appendChild(buildRuleModal());

        // Build Suppression Modal
        section.appendChild(buildSuppressionModal());

        // Bind static events
        bindStaticEvents();
    }

    function buildRuleModal() {
        var form = el('form', { id: 'alertRuleForm', 'data-rule-id': '' });

        function formGroup(label, input) {
            var g = el('div', { className: 'filter-group' });
            g.style.marginBottom = '12px';
            g.appendChild(el('label', { textContent: label, htmlFor: input.id || '' }));
            g.appendChild(input);
            return g;
        }

        form.appendChild(formGroup('Name', el('input', { type: 'text', name: 'ruleName', id: 'ruleName', required: 'required', placeholder: 'Rule name' })));
        form.appendChild(formGroup('Alert Type', el('input', { type: 'text', name: 'ruleType', id: 'ruleType', required: 'required', placeholder: 'e.g., spf_failure, dkim_failure' })));
        form.appendChild(formGroup('Severity', el('select', { name: 'ruleSeverity', id: 'ruleSeverity' }, [
            el('option', { value: 'critical', textContent: 'Critical' }),
            el('option', { value: 'high', textContent: 'High' }),
            el('option', { value: 'medium', textContent: 'Medium', selected: 'selected' }),
            el('option', { value: 'low', textContent: 'Low' })
        ])));

        var activeGroup = el('div', { className: 'filter-group' });
        activeGroup.style.marginBottom = '12px';
        var activeLabel = el('label', {}, [el('input', { type: 'checkbox', name: 'ruleActive', id: 'ruleActive', checked: true }), text(' Active')]);
        activeGroup.appendChild(activeLabel);
        form.appendChild(activeGroup);

        form.appendChild(formGroup('Channels (comma separated)', el('input', { type: 'text', name: 'ruleChannels', id: 'ruleChannels', placeholder: 'email, webhook' })));

        var conditionsTextarea = el('textarea', { name: 'ruleConditions', id: 'ruleConditions', rows: '4' });
        conditionsTextarea.style.cssText = 'width:100%;font-family:monospace;resize:vertical;';
        conditionsTextarea.textContent = '{}';
        form.appendChild(formGroup('Conditions (JSON)', conditionsTextarea));

        var actions = el('div', { className: 'modal-actions' }, [
            el('button', { type: 'submit', className: 'btn-primary', textContent: 'Save Rule' }),
            el('button', { type: 'button', className: 'btn-secondary alert-rule-modal-close', textContent: 'Cancel' })
        ]);
        form.appendChild(actions);

        var closeBtn = el('button', { className: 'modal-close alert-rule-modal-close', 'aria-label': 'Close' }, [closeIcon()]);

        var modal = el('div', { id: 'alertRuleModal', className: 'modal', role: 'dialog', 'aria-modal': 'true', hidden: true }, [
            el('div', { className: 'modal-content' }, [
                el('div', { className: 'modal-header' }, [
                    el('h2', { id: 'alertRuleModalTitle', textContent: 'Create Alert Rule' }),
                    closeBtn
                ]),
                el('div', { className: 'modal-body' }, [form])
            ])
        ]);
        return modal;
    }

    function buildSuppressionModal() {
        var form = el('form', { id: 'alertSuppressionForm' });

        function formGroup(label, input) {
            var g = el('div', { className: 'filter-group' });
            g.style.marginBottom = '12px';
            g.appendChild(el('label', { textContent: label, htmlFor: input.id || '' }));
            g.appendChild(input);
            return g;
        }

        form.appendChild(formGroup('Domain', el('input', { type: 'text', name: 'suppDomain', id: 'suppDomain', required: 'required', placeholder: 'example.com' })));
        form.appendChild(formGroup('Alert Type', el('input', { type: 'text', name: 'suppType', id: 'suppType', placeholder: 'e.g., spf_failure (leave blank for all)' })));
        form.appendChild(formGroup('Reason', el('input', { type: 'text', name: 'suppReason', id: 'suppReason', required: 'required', placeholder: 'Reason for suppression' })));
        form.appendChild(formGroup('Start Date', el('input', { type: 'datetime-local', name: 'suppStart', id: 'suppStart' })));
        form.appendChild(formGroup('End Date', el('input', { type: 'datetime-local', name: 'suppEnd', id: 'suppEnd' })));

        var actions = el('div', { className: 'modal-actions' }, [
            el('button', { type: 'submit', className: 'btn-primary', textContent: 'Create Suppression' }),
            el('button', { type: 'button', className: 'btn-secondary alert-supp-modal-close', textContent: 'Cancel' })
        ]);
        form.appendChild(actions);

        var closeBtn = el('button', { className: 'modal-close alert-supp-modal-close', 'aria-label': 'Close' }, [closeIcon()]);

        var modal = el('div', { id: 'alertSuppressionModal', className: 'modal', role: 'dialog', 'aria-modal': 'true', hidden: true }, [
            el('div', { className: 'modal-content' }, [
                el('div', { className: 'modal-header' }, [
                    el('h2', { textContent: 'Create Suppression' }),
                    closeBtn
                ]),
                el('div', { className: 'modal-body' }, [form])
            ])
        ]);
        return modal;
    }

    function bindStaticEvents() {
        var section = getSection();
        if (!section) return;

        // Tab buttons
        section.querySelectorAll('.alerts-tab-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                switchTab(this.getAttribute('data-tab'));
            });
        });

        // Select all checkbox
        var selectAll = document.getElementById('alerts-select-all');
        if (selectAll) {
            selectAll.addEventListener('change', function() {
                var section = getSection();
                if (!section) return;
                var cbs = section.querySelectorAll('.alert-select-cb');
                var check = selectAll.checked;
                cbs.forEach(function(cb) {
                    if (cb.checked !== check) {
                        cb.checked = check;
                        cb.dispatchEvent(new Event('change'));
                    }
                });
            });
        }

        // Bulk actions
        var bulkAckBtn = document.getElementById('alerts-bulk-ack-btn');
        if (bulkAckBtn) bulkAckBtn.addEventListener('click', bulkAcknowledge);

        var bulkResolveBtn = document.getElementById('alerts-bulk-resolve-btn');
        if (bulkResolveBtn) bulkResolveBtn.addEventListener('click', bulkResolve);

        // History filter apply
        var histApply = document.getElementById('alerts-hist-apply-btn');
        if (histApply) {
            histApply.addEventListener('click', function() {
                historyOffset = 0;
                loadHistory();
            });
        }

        // Create rule button
        var createRuleBtn = document.getElementById('alerts-create-rule-btn');
        if (createRuleBtn) {
            createRuleBtn.addEventListener('click', function() { openRuleModal(null); });
        }

        // Rule modal close buttons
        section.querySelectorAll('.alert-rule-modal-close').forEach(function(btn) {
            btn.addEventListener('click', closeRuleModal);
        });

        // Rule form submit
        var ruleForm = document.getElementById('alertRuleForm');
        if (ruleForm) {
            ruleForm.addEventListener('submit', saveRule);
        }

        // Create suppression button
        var createSuppBtn = document.getElementById('alerts-create-suppression-btn');
        if (createSuppBtn) {
            createSuppBtn.addEventListener('click', openSuppressionModal);
        }

        // Suppression modal close buttons
        section.querySelectorAll('.alert-supp-modal-close').forEach(function(btn) {
            btn.addEventListener('click', closeSuppressionModal);
        });

        // Suppression form submit
        var suppForm = document.getElementById('alertSuppressionForm');
        if (suppForm) {
            suppForm.addEventListener('submit', saveSuppression);
        }

        // Close modals on backdrop click
        [document.getElementById('alertRuleModal'), document.getElementById('alertSuppressionModal')].forEach(function(modal) {
            if (modal) {
                modal.addEventListener('click', function(e) {
                    if (e.target === modal) {
                        modal.hidden = true;
                    }
                });
            }
        });
    }

    // =========================================
    // Tab styling (injected once)
    // =========================================
    function addTabStyles() {
        if (document.getElementById('alerts-tab-styles')) return;
        var style = document.createElement('style');
        style.id = 'alerts-tab-styles';
        style.textContent =
            '.alerts-tab-btn { padding: 8px 16px; border: none; border-bottom: 2px solid transparent; margin-bottom: -2px; cursor: pointer; font-weight: 500; transition: border-color 0.2s, color 0.2s; }' +
            '.alerts-tab-btn.active { border-bottom-color: var(--accent-primary); color: var(--accent-primary); }' +
            '.alerts-tab-btn:hover:not(.active) { border-bottom-color: var(--border-color); }' +
            '.badge-info { background-color: #dbeafe; color: #1e40af; }' +
            '.toggle-switch { position: relative; display: inline-block; width: 36px; height: 20px; }' +
            '.toggle-switch input { opacity: 0; width: 0; height: 0; }' +
            '.toggle-slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: 0.3s; border-radius: 20px; }' +
            '.toggle-slider:before { position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px; background-color: white; transition: 0.3s; border-radius: 50%; }' +
            '.toggle-switch input:checked + .toggle-slider { background-color: var(--accent-primary); }' +
            '.toggle-switch input:checked + .toggle-slider:before { transform: translateX(16px); }' +
            '.pagination { display: flex; align-items: center; justify-content: center; gap: 12px; }' +
            '.pagination-info { font-size: 14px; color: var(--text-secondary); }' +
            '.alert-actions-cell { white-space: nowrap; }' +
            '.alert-actions-cell .btn-ghost { margin-right: 4px; }';
        document.head.appendChild(style);
    }

    // =========================================
    // Module Interface
    // =========================================
    var AlertsPage = {
        initialized: false,

        init: function() {
            if (this.initialized) return;
            this.initialized = true;
            addTabStyles();
            renderPage();
        },

        load: function() {
            loadStats();
            switchTab(currentTab);
            this._startAutoRefresh();
        },

        destroy: function() {
            this._stopAutoRefresh();
        },

        _startAutoRefresh: function() {
            this._stopAutoRefresh();
            refreshTimer = setInterval(function() {
                if (currentTab === 'active') {
                    loadStats();
                    loadActiveAlerts();
                }
            }, 60000);
        },

        _stopAutoRefresh: function() {
            if (refreshTimer) {
                clearInterval(refreshTimer);
                refreshTimer = null;
            }
        }
    };

    // Expose on window.DMARC namespace and register with router
    window.DMARC = window.DMARC || {};
    window.DMARC.AlertsPage = AlertsPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('alerts', AlertsPage);
    }
})();
