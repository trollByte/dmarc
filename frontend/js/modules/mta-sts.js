/**
 * DMARC Dashboard - MTA-STS Page Module
 * Monitors MTA-STS policy deployment across domains.
 */
(function() {
    'use strict';

    function clearElement(el) {
        while (el.firstChild) el.removeChild(el.firstChild);
    }

    function getAuthHeaders() {
        return window.DMARC && window.DMARC.getAuthHeaders ? window.DMARC.getAuthHeaders() :
               (window.accessToken ? { 'Authorization': 'Bearer ' + window.accessToken } :
               (typeof window.getAuthHeaders === 'function' ? window.getAuthHeaders() : {}));
    }

    function notify(msg, type) {
        if (window.DMARC && window.DMARC.showNotification) window.DMARC.showNotification(msg, type);
        else if (typeof showNotification === 'function') showNotification(msg, type);
    }

    function isAdmin() {
        var u = (window.DMARC && window.DMARC.currentUser) || window.currentUser;
        return u && u.role === 'admin';
    }

    var MtaStsPage = {
        initialized: false,
        containerId: 'page-mta-sts',
        _els: {},

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            // Page header
            var header = document.createElement('div');
            header.className = 'page-header';
            var h1 = document.createElement('h1');
            h1.textContent = 'MTA-STS Monitor';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Monitor MTA-STS policy deployment and changes across your domains.';
            header.appendChild(desc);

            var actions = document.createElement('div');
            actions.style.cssText = 'display:flex;gap:8px;margin-top:12px;';

            var addBtn = document.createElement('button');
            addBtn.className = 'btn-primary btn-sm';
            addBtn.textContent = 'Add Domain';
            addBtn.addEventListener('click', this._showAddDomain.bind(this));
            this._els.addBtn = addBtn;

            var checkAllBtn = document.createElement('button');
            checkAllBtn.className = 'btn-secondary btn-sm';
            checkAllBtn.textContent = 'Check All';
            checkAllBtn.addEventListener('click', this._checkAll.bind(this));
            this._els.checkAllBtn = checkAllBtn;

            actions.appendChild(addBtn);
            actions.appendChild(checkAllBtn);
            header.appendChild(actions);

            // Summary cards
            var summary = document.createElement('div');
            summary.className = 'stats-grid';
            summary.style.marginBottom = '20px';
            this._els.summary = summary;

            // Add domain form (hidden)
            var addForm = document.createElement('div');
            addForm.className = 'card';
            addForm.style.cssText = 'padding:16px;margin-bottom:16px;display:none;';
            var formTitle = document.createElement('h3');
            formTitle.textContent = 'Add Domain';
            formTitle.style.marginBottom = '8px';
            addForm.appendChild(formTitle);

            var formRow = document.createElement('div');
            formRow.style.cssText = 'display:flex;gap:8px;align-items:center;';
            var domainInput = document.createElement('input');
            domainInput.type = 'text';
            domainInput.placeholder = 'example.com';
            domainInput.style.cssText = 'flex:1;padding:8px;border:1px solid var(--border-color);border-radius:4px;background:var(--bg-primary);color:var(--text-primary);';
            this._els.domainInput = domainInput;

            var submitFormBtn = document.createElement('button');
            submitFormBtn.className = 'btn-primary btn-sm';
            submitFormBtn.textContent = 'Add';
            submitFormBtn.addEventListener('click', this._addDomain.bind(this));

            var cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn-ghost btn-sm';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.addEventListener('click', function() { addForm.style.display = 'none'; });

            formRow.appendChild(domainInput);
            formRow.appendChild(submitFormBtn);
            formRow.appendChild(cancelBtn);
            addForm.appendChild(formRow);
            this._els.addForm = addForm;

            // Domains table
            var tableWrap = document.createElement('div');
            tableWrap.className = 'table-container';
            var tableHeader = document.createElement('div');
            tableHeader.className = 'table-header';
            var tableTitle = document.createElement('h2');
            tableTitle.textContent = 'Monitored Domains';
            tableHeader.appendChild(tableTitle);

            var table = document.createElement('table');
            var thead = document.createElement('thead');
            var headerRow = document.createElement('tr');
            ['Domain', 'Status', 'Mode', 'Policy ID', 'Max Age', 'Last Checked', 'Actions'].forEach(function(col) {
                var th = document.createElement('th');
                th.scope = 'col';
                th.textContent = col;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);

            var tbody = document.createElement('tbody');
            this._els.tbody = tbody;
            table.appendChild(tbody);
            tableWrap.appendChild(tableHeader);
            tableWrap.appendChild(table);

            // Domain report detail panel
            var detailPanel = document.createElement('div');
            detailPanel.className = 'card';
            detailPanel.style.cssText = 'padding:16px;margin-top:16px;display:none;';
            this._els.detailPanel = detailPanel;

            // Change history
            var historyWrap = document.createElement('div');
            historyWrap.className = 'table-container';
            historyWrap.style.marginTop = '20px';
            var histHeader = document.createElement('div');
            histHeader.className = 'table-header';
            var histTitle = document.createElement('h2');
            histTitle.textContent = 'Change History';
            histHeader.appendChild(histTitle);

            var histTable = document.createElement('table');
            var histThead = document.createElement('thead');
            var histHeaderRow = document.createElement('tr');
            ['Domain', 'Change Type', 'Old Value', 'New Value', 'Detected At'].forEach(function(col) {
                var th = document.createElement('th');
                th.scope = 'col';
                th.textContent = col;
                histHeaderRow.appendChild(th);
            });
            histThead.appendChild(histHeaderRow);
            histTable.appendChild(histThead);
            var histTbody = document.createElement('tbody');
            this._els.historyTbody = histTbody;
            histTable.appendChild(histTbody);
            historyWrap.appendChild(histHeader);
            historyWrap.appendChild(histTable);

            var body = document.createElement('div');
            body.className = 'page-body';
            body.appendChild(summary);
            body.appendChild(addForm);
            body.appendChild(tableWrap);
            body.appendChild(detailPanel);
            body.appendChild(historyWrap);

            container.appendChild(header);
            container.appendChild(body);
        },

        load: function() {
            var admin = isAdmin();
            if (this._els.addBtn) this._els.addBtn.style.display = admin ? '' : 'none';
            if (this._els.checkAllBtn) this._els.checkAllBtn.style.display = admin ? '' : 'none';
            this._loadDomains();
            this._loadChanges();
        },

        destroy: function() {},

        _loadDomains: function() {
            var self = this;
            fetch('/api/mta-sts/domains?active_only=true', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(domains) {
                    self._renderDomains(Array.isArray(domains) ? domains : []);
                    return fetch('/api/mta-sts/check-all', { method: 'POST', headers: getAuthHeaders() });
                })
                .then(function(r) { return r.json(); })
                .then(function(data) { self._renderSummary(data); })
                .catch(function() { notify('Failed to load MTA-STS domains', 'error'); });
        },

        _renderSummary: function(data) {
            var el = this._els.summary;
            if (!el || !data || !data.summary) return;
            clearElement(el);

            var items = [
                { label: 'Domains Checked', value: data.domains_checked || 0, cls: '' },
                { label: 'Valid', value: data.summary.valid || 0, cls: 'stat-card-success' },
                { label: 'Invalid', value: data.summary.invalid || 0, cls: 'stat-card-danger' },
                { label: 'Missing', value: data.summary.missing || 0, cls: '' }
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

        _renderDomains: function(domains) {
            var self = this;
            var tbody = this._els.tbody;
            if (!tbody) return;
            clearElement(tbody);

            if (domains.length === 0) {
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.colSpan = 7;
                td.textContent = 'No domains monitored yet.';
                td.style.textAlign = 'center';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            domains.forEach(function(d) {
                var domain = d.domain || d;
                var tr = document.createElement('tr');

                var tdDomain = document.createElement('td');
                tdDomain.textContent = domain;
                tr.appendChild(tdDomain);

                var tdStatus = document.createElement('td');
                var badge = document.createElement('span');
                badge.className = 'badge ' + (d.status === 'valid' ? 'badge-success' : d.status === 'invalid' ? 'badge-danger' : 'badge-gray');
                badge.textContent = d.status || 'unknown';
                tdStatus.appendChild(badge);
                tr.appendChild(tdStatus);

                var tdMode = document.createElement('td');
                tdMode.textContent = (d.policy && d.policy.mode) || d.mode || '-';
                tr.appendChild(tdMode);

                var tdPid = document.createElement('td');
                tdPid.textContent = (d.record && d.record.id) || d.policy_id || '-';
                tr.appendChild(tdPid);

                var tdAge = document.createElement('td');
                var maxAge = d.policy && d.policy.max_age_days;
                tdAge.textContent = maxAge ? maxAge + ' days' : '-';
                tr.appendChild(tdAge);

                var tdChecked = document.createElement('td');
                tdChecked.textContent = d.checked_at ? new Date(d.checked_at).toLocaleString() : '-';
                tr.appendChild(tdChecked);

                var tdActions = document.createElement('td');
                var checkBtn = document.createElement('button');
                checkBtn.className = 'btn-ghost btn-sm';
                checkBtn.textContent = 'Check';
                checkBtn.addEventListener('click', function() { self._checkDomain(domain); });
                tdActions.appendChild(checkBtn);

                var viewBtn = document.createElement('button');
                viewBtn.className = 'btn-ghost btn-sm';
                viewBtn.textContent = 'Report';
                viewBtn.addEventListener('click', function() { self._viewReport(domain); });
                tdActions.appendChild(viewBtn);

                if (isAdmin()) {
                    var delBtn = document.createElement('button');
                    delBtn.className = 'btn-ghost btn-sm';
                    delBtn.style.color = 'var(--accent-danger)';
                    delBtn.textContent = 'Remove';
                    delBtn.addEventListener('click', function() { self._removeDomain(domain); });
                    tdActions.appendChild(delBtn);
                }

                tr.appendChild(tdActions);
                tbody.appendChild(tr);
            });
        },

        _checkDomain: function(domain) {
            var self = this;
            fetch('/api/mta-sts/check/' + encodeURIComponent(domain), { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function() {
                    notify('Check complete for ' + domain, 'success');
                    self._loadDomains();
                })
                .catch(function() { notify('Check failed for ' + domain, 'error'); });
        },

        _checkAll: function() {
            var self = this;
            var btn = this._els.checkAllBtn;
            if (btn) { btn.disabled = true; btn.textContent = 'Checking...'; }

            fetch('/api/mta-sts/check-all', { method: 'POST', headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    notify('Checked ' + (data.domains_checked || 0) + ' domains', 'success');
                    self._renderSummary(data);
                    self._loadDomains();
                })
                .catch(function() { notify('Check all failed', 'error'); })
                .finally(function() { if (btn) { btn.disabled = false; btn.textContent = 'Check All'; } });
        },

        _showAddDomain: function() {
            if (this._els.addForm) {
                this._els.addForm.style.display = '';
                if (this._els.domainInput) this._els.domainInput.focus();
            }
        },

        _addDomain: function() {
            var self = this;
            var input = this._els.domainInput;
            if (!input || !input.value.trim()) return;

            fetch('/api/mta-sts/domains', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, getAuthHeaders()),
                body: JSON.stringify({ domain: input.value.trim() })
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Failed to add domain');
                return r.json();
            })
            .then(function() {
                notify('Domain added', 'success');
                input.value = '';
                self._els.addForm.style.display = 'none';
                self._loadDomains();
            })
            .catch(function(err) { notify(err.message, 'error'); });
        },

        _removeDomain: function(domain) {
            if (!confirm('Remove ' + domain + ' from monitoring?')) return;
            var self = this;
            fetch('/api/mta-sts/domains/' + encodeURIComponent(domain), {
                method: 'DELETE', headers: getAuthHeaders()
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Failed');
                notify('Domain removed', 'success');
                self._loadDomains();
            })
            .catch(function() { notify('Failed to remove domain', 'error'); });
        },

        _viewReport: function(domain) {
            var self = this;
            var panel = this._els.detailPanel;
            if (!panel) return;
            panel.style.display = '';
            clearElement(panel);
            var loading = document.createElement('p');
            loading.className = 'loading';
            loading.textContent = 'Loading report...';
            panel.appendChild(loading);

            fetch('/api/mta-sts/report/' + encodeURIComponent(domain), { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) { self._renderReport(panel, data); })
                .catch(function() {
                    clearElement(panel);
                    var err = document.createElement('p');
                    err.textContent = 'Failed to load report.';
                    panel.appendChild(err);
                });
        },

        _renderReport: function(panel, data) {
            clearElement(panel);

            var titleRow = document.createElement('div');
            titleRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;';
            var title = document.createElement('h3');
            title.textContent = 'Report: ' + (data.domain || '');
            titleRow.appendChild(title);
            var closeBtn = document.createElement('button');
            closeBtn.className = 'btn-ghost btn-sm';
            closeBtn.textContent = 'Close';
            closeBtn.addEventListener('click', function() { panel.style.display = 'none'; });
            titleRow.appendChild(closeBtn);
            panel.appendChild(titleRow);

            var info = document.createElement('div');
            info.style.margin = '12px 0';
            var statusBadge = document.createElement('span');
            statusBadge.className = 'badge ' + (data.status === 'valid' ? 'badge-success' : data.status === 'invalid' ? 'badge-danger' : 'badge-gray');
            statusBadge.textContent = data.status || 'unknown';
            info.appendChild(statusBadge);
            if (data.checked_at) {
                var checked = document.createElement('span');
                checked.textContent = '  Checked: ' + new Date(data.checked_at).toLocaleString();
                checked.style.marginLeft = '12px';
                info.appendChild(checked);
            }
            panel.appendChild(info);

            if (data.record) {
                var recSec = document.createElement('div');
                recSec.style.marginBottom = '12px';
                var recTitle = document.createElement('h4');
                recTitle.textContent = 'MTA-STS Record';
                recSec.appendChild(recTitle);
                if (data.record.raw) {
                    var pre = document.createElement('pre');
                    pre.style.cssText = 'background:var(--bg-tertiary);padding:8px;border-radius:4px;overflow-x:auto;font-size:13px;';
                    pre.textContent = data.record.raw;
                    recSec.appendChild(pre);
                }
                panel.appendChild(recSec);
            }

            if (data.policy) {
                var polSec = document.createElement('div');
                polSec.style.marginBottom = '12px';
                var polTitle = document.createElement('h4');
                polTitle.textContent = 'Policy';
                polSec.appendChild(polTitle);
                var details = [
                    ['Mode', data.policy.mode],
                    ['Max Age', (data.policy.max_age_days || (data.policy.max_age_seconds ? Math.floor(data.policy.max_age_seconds / 86400) : null)) ? ((data.policy.max_age_days || Math.floor(data.policy.max_age_seconds / 86400)) + ' days') : '-'],
                    ['MX Hosts', (data.policy.mx_hosts || []).join(', ') || '-']
                ];
                details.forEach(function(pair) {
                    var row = document.createElement('div');
                    row.style.cssText = 'display:flex;gap:8px;margin:4px 0;';
                    var lbl = document.createElement('strong');
                    lbl.textContent = pair[0] + ':';
                    var val = document.createElement('span');
                    val.textContent = pair[1];
                    row.appendChild(lbl);
                    row.appendChild(val);
                    polSec.appendChild(row);
                });
                panel.appendChild(polSec);
            }

            this._renderIssueList(panel, 'Issues', data.issues, 'badge-danger');
            this._renderIssueList(panel, 'Warnings', data.warnings, 'badge-warning');
            this._renderIssueList(panel, 'Recommendations', data.recommendations, 'badge-gray');
        },

        _renderIssueList: function(parent, title, items, badgeCls) {
            if (!items || items.length === 0) return;
            var sec = document.createElement('div');
            sec.style.marginBottom = '12px';
            var h4 = document.createElement('h4');
            h4.textContent = title + ' (' + items.length + ')';
            sec.appendChild(h4);
            var ul = document.createElement('ul');
            ul.style.cssText = 'list-style:none;padding:0;margin:4px 0;';
            items.forEach(function(item) {
                var li = document.createElement('li');
                li.style.padding = '4px 0';
                var b = document.createElement('span');
                b.className = 'badge ' + badgeCls;
                b.style.cssText = 'font-size:11px;margin-right:8px;';
                b.textContent = title.charAt(0);
                li.appendChild(b);
                var txt = document.createElement('span');
                txt.textContent = typeof item === 'string' ? item : (item.message || JSON.stringify(item));
                li.appendChild(txt);
                ul.appendChild(li);
            });
            sec.appendChild(ul);
            parent.appendChild(sec);
        },

        _loadChanges: function() {
            var self = this;
            fetch('/api/mta-sts/changes?days=30&limit=50', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(changes) { self._renderChanges(Array.isArray(changes) ? changes : []); })
                .catch(function() { /* silent */ });
        },

        _renderChanges: function(changes) {
            var tbody = this._els.historyTbody;
            if (!tbody) return;
            clearElement(tbody);

            if (changes.length === 0) {
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.colSpan = 5;
                td.textContent = 'No recent changes detected.';
                td.style.textAlign = 'center';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            changes.forEach(function(c) {
                var tr = document.createElement('tr');
                [c.domain, c.change_type, c.old_value || '-', c.new_value || '-',
                 c.detected_at ? new Date(c.detected_at).toLocaleString() : '-'
                ].forEach(function(val) {
                    var td = document.createElement('td');
                    td.textContent = val;
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
        }
    };

    window.DMARC = window.DMARC || {};
    window.DMARC.MtaStsPage = MtaStsPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('mta-sts', MtaStsPage);
    }
})();
