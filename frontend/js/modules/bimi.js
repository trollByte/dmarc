/**
 * DMARC Dashboard - BIMI Page Module
 * Manages BIMI records and logo validation for domains.
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

    function isAdmin() {
        var u = (window.DMARC && window.DMARC.currentUser) || window.currentUser;
        return u && u.role === 'admin';
    }

    var BimiPage = {
        initialized: false,
        containerId: 'page-bimi',
        _els: {},

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            // Header
            var header = document.createElement('div');
            header.className = 'page-header';
            var h1 = document.createElement('h1');
            h1.textContent = 'BIMI Records';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Brand Indicators for Message Identification - manage and validate BIMI records for your domains.';
            header.appendChild(desc);

            // Actions row
            var actions = document.createElement('div');
            actions.style.cssText = 'display:flex;gap:8px;margin-top:12px;';

            var addBtn = document.createElement('button');
            addBtn.className = 'btn-primary btn-sm';
            addBtn.textContent = 'Add Record';
            addBtn.addEventListener('click', this._showAddForm.bind(this));
            this._els.addBtn = addBtn;

            var validateBtn = document.createElement('button');
            validateBtn.className = 'btn-secondary btn-sm';
            validateBtn.textContent = 'Validate Domain';
            validateBtn.addEventListener('click', this._showValidateForm.bind(this));

            actions.appendChild(addBtn);
            actions.appendChild(validateBtn);
            header.appendChild(actions);

            // Status summary
            var statusBar = document.createElement('div');
            statusBar.className = 'stats-grid';
            statusBar.style.marginBottom = '20px';
            this._els.statusBar = statusBar;

            // Add record form (hidden)
            var addForm = document.createElement('div');
            addForm.className = 'card';
            addForm.style.cssText = 'padding:16px;margin-bottom:16px;display:none;';
            this._els.addForm = addForm;

            var formTitle = document.createElement('h3');
            formTitle.textContent = 'Add BIMI Record';
            formTitle.style.marginBottom = '12px';
            addForm.appendChild(formTitle);

            var domainRow = document.createElement('div');
            domainRow.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap;';

            var domainInput = document.createElement('input');
            domainInput.type = 'text';
            domainInput.placeholder = 'example.com';
            domainInput.style.cssText = 'flex:1;min-width:200px;padding:8px;border:1px solid var(--border-color);border-radius:4px;background:var(--bg-primary);color:var(--text-primary);';
            this._els.addDomainInput = domainInput;
            domainRow.appendChild(domainInput);

            var submitBtn = document.createElement('button');
            submitBtn.className = 'btn-primary btn-sm';
            submitBtn.textContent = 'Add';
            submitBtn.addEventListener('click', this._addRecord.bind(this));
            domainRow.appendChild(submitBtn);

            var cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn-ghost btn-sm';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.addEventListener('click', function() { addForm.style.display = 'none'; });
            domainRow.appendChild(cancelBtn);

            addForm.appendChild(domainRow);

            // Validate form (hidden)
            var validateForm = document.createElement('div');
            validateForm.className = 'card';
            validateForm.style.cssText = 'padding:16px;margin-bottom:16px;display:none;';
            this._els.validateForm = validateForm;

            var valTitle = document.createElement('h3');
            valTitle.textContent = 'Validate BIMI for Domain';
            valTitle.style.marginBottom = '12px';
            validateForm.appendChild(valTitle);

            var valRow = document.createElement('div');
            valRow.style.cssText = 'display:flex;gap:8px;align-items:center;';

            var valInput = document.createElement('input');
            valInput.type = 'text';
            valInput.placeholder = 'example.com';
            valInput.style.cssText = 'flex:1;padding:8px;border:1px solid var(--border-color);border-radius:4px;background:var(--bg-primary);color:var(--text-primary);';
            this._els.valDomainInput = valInput;
            valRow.appendChild(valInput);

            var valSubmit = document.createElement('button');
            valSubmit.className = 'btn-primary btn-sm';
            valSubmit.textContent = 'Validate';
            valSubmit.addEventListener('click', this._validateDomain.bind(this));
            valRow.appendChild(valSubmit);

            var valCancel = document.createElement('button');
            valCancel.className = 'btn-ghost btn-sm';
            valCancel.textContent = 'Cancel';
            valCancel.addEventListener('click', function() { validateForm.style.display = 'none'; });
            valRow.appendChild(valCancel);

            validateForm.appendChild(valRow);

            var valResult = document.createElement('div');
            valResult.style.cssText = 'margin-top:12px;display:none;';
            this._els.valResult = valResult;
            validateForm.appendChild(valResult);

            // Records table
            var tableWrap = document.createElement('div');
            tableWrap.className = 'table-container';
            var tableHeader = document.createElement('div');
            tableHeader.className = 'table-header';
            var tableTitle = document.createElement('h2');
            tableTitle.textContent = 'BIMI Records';
            tableHeader.appendChild(tableTitle);

            var table = document.createElement('table');
            var thead = document.createElement('thead');
            var hRow = document.createElement('tr');
            ['Domain', 'Has BIMI', 'Logo URL', 'VMC Status', 'Actions'].forEach(function(col) {
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

            // Detail panel
            var detailPanel = document.createElement('div');
            detailPanel.className = 'card';
            detailPanel.style.cssText = 'padding:16px;margin-top:16px;display:none;';
            this._els.detailPanel = detailPanel;

            var body = document.createElement('div');
            body.className = 'page-body';
            body.appendChild(statusBar);
            body.appendChild(addForm);
            body.appendChild(validateForm);
            body.appendChild(tableWrap);
            body.appendChild(detailPanel);

            container.appendChild(header);
            container.appendChild(body);
        },

        load: function() {
            if (this._els.addBtn) this._els.addBtn.style.display = isAdmin() ? '' : 'none';
            this._loadRecords();
            this._loadStatus();
        },

        destroy: function() {},

        _loadRecords: function() {
            var self = this;
            fetch('/api/bimi/records', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var records = Array.isArray(data) ? data : (data.records || []);
                    self._renderRecords(records);
                })
                .catch(function() { notify('Failed to load BIMI records', 'error'); });
        },

        _loadStatus: function() {
            var self = this;
            fetch('/api/bimi/status', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) { self._renderStatus(data); })
                .catch(function() {});
        },

        _renderStatus: function(data) {
            var el = this._els.statusBar;
            if (!el) return;
            clearElement(el);

            var domains = Array.isArray(data) ? data : (data.domains || []);
            var total = domains.length;
            var withBimi = 0;
            var withVmc = 0;
            domains.forEach(function(d) {
                if (d.has_bimi) withBimi++;
                if (d.vmc_valid || d.vmc_status === 'valid') withVmc++;
            });

            var items = [
                { label: 'Total Domains', value: total, cls: '' },
                { label: 'With BIMI', value: withBimi, cls: 'stat-card-success' },
                { label: 'Without BIMI', value: total - withBimi, cls: total - withBimi > 0 ? 'stat-card-danger' : '' },
                { label: 'VMC Verified', value: withVmc, cls: '' }
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

        _renderRecords: function(records) {
            var self = this;
            var tbody = this._els.tbody;
            if (!tbody) return;
            clearElement(tbody);

            if (records.length === 0) {
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.colSpan = 5;
                td.textContent = 'No BIMI records found.';
                td.style.textAlign = 'center';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            records.forEach(function(rec) {
                var tr = document.createElement('tr');

                var tdDomain = document.createElement('td');
                tdDomain.textContent = rec.domain || '-';
                tr.appendChild(tdDomain);

                var tdHas = document.createElement('td');
                var hasBadge = document.createElement('span');
                if (rec.has_bimi || rec.bimi_found) {
                    hasBadge.className = 'badge badge-success';
                    hasBadge.textContent = 'Yes';
                } else {
                    hasBadge.className = 'badge badge-gray';
                    hasBadge.textContent = 'No';
                }
                tdHas.appendChild(hasBadge);
                tr.appendChild(tdHas);

                var tdLogo = document.createElement('td');
                var logoUrl = rec.logo_url || rec.logo || '-';
                if (logoUrl !== '-' && logoUrl.length > 40) {
                    tdLogo.textContent = logoUrl.substring(0, 40) + '...';
                    tdLogo.title = logoUrl;
                } else {
                    tdLogo.textContent = logoUrl;
                }
                tr.appendChild(tdLogo);

                var tdVmc = document.createElement('td');
                var vmcBadge = document.createElement('span');
                var vmcStatus = rec.vmc_status || (rec.vmc_valid ? 'valid' : 'none');
                vmcBadge.className = 'badge ' + (vmcStatus === 'valid' ? 'badge-success' : vmcStatus === 'invalid' ? 'badge-danger' : 'badge-gray');
                vmcBadge.textContent = vmcStatus;
                tdVmc.appendChild(vmcBadge);
                tr.appendChild(tdVmc);

                var tdActions = document.createElement('td');
                var viewBtn = document.createElement('button');
                viewBtn.className = 'btn-ghost btn-sm';
                viewBtn.textContent = 'Details';
                viewBtn.addEventListener('click', function() { self._showDetail(rec); });
                tdActions.appendChild(viewBtn);

                if (isAdmin() && rec.id) {
                    var delBtn = document.createElement('button');
                    delBtn.className = 'btn-ghost btn-sm';
                    delBtn.style.color = 'var(--accent-danger)';
                    delBtn.textContent = 'Delete';
                    delBtn.addEventListener('click', function() { self._deleteRecord(rec.id); });
                    tdActions.appendChild(delBtn);
                }

                tr.appendChild(tdActions);
                tbody.appendChild(tr);
            });
        },

        _showDetail: function(rec) {
            var panel = this._els.detailPanel;
            if (!panel) return;
            panel.style.display = '';
            clearElement(panel);

            var titleRow = document.createElement('div');
            titleRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;';
            var title = document.createElement('h3');
            title.textContent = 'BIMI Details: ' + (rec.domain || '');
            titleRow.appendChild(title);
            var closeBtn = document.createElement('button');
            closeBtn.className = 'btn-ghost btn-sm';
            closeBtn.textContent = 'Close';
            closeBtn.addEventListener('click', function() { panel.style.display = 'none'; });
            titleRow.appendChild(closeBtn);
            panel.appendChild(titleRow);

            var fields = [
                ['Domain', rec.domain],
                ['Has BIMI', rec.has_bimi || rec.bimi_found ? 'Yes' : 'No'],
                ['Logo URL', rec.logo_url || rec.logo || '-'],
                ['VMC Status', rec.vmc_status || '-'],
                ['VMC URL', rec.vmc_url || '-'],
                ['Selector', rec.selector || 'default'],
                ['Record', rec.record || rec.raw || '-']
            ];

            fields.forEach(function(pair) {
                var row = document.createElement('div');
                row.style.cssText = 'display:flex;gap:8px;margin:6px 0;';
                var lbl = document.createElement('strong');
                lbl.textContent = pair[0] + ':';
                lbl.style.minWidth = '100px';
                var val = document.createElement('span');
                val.textContent = pair[1] || '-';
                val.style.wordBreak = 'break-all';
                row.appendChild(lbl);
                row.appendChild(val);
                panel.appendChild(row);
            });

            // Logo preview if URL available
            var logoUrl = rec.logo_url || rec.logo;
            if (logoUrl && logoUrl !== '-') {
                var previewSec = document.createElement('div');
                previewSec.style.cssText = 'margin-top:12px;padding:12px;background:var(--bg-tertiary);border-radius:4px;';
                var previewTitle = document.createElement('h4');
                previewTitle.textContent = 'Logo Preview';
                previewSec.appendChild(previewTitle);
                var img = document.createElement('img');
                img.src = logoUrl;
                img.alt = 'BIMI logo for ' + (rec.domain || 'domain');
                img.style.cssText = 'max-width:120px;max-height:120px;margin-top:8px;border:1px solid var(--border-color);border-radius:4px;';
                img.onerror = function() {
                    var errMsg = document.createElement('p');
                    errMsg.textContent = 'Could not load logo image.';
                    errMsg.style.color = 'var(--accent-danger)';
                    previewSec.replaceChild(errMsg, img);
                };
                previewSec.appendChild(img);
                panel.appendChild(previewSec);
            }
        },

        _showAddForm: function() {
            if (this._els.addForm) {
                this._els.addForm.style.display = '';
                if (this._els.addDomainInput) this._els.addDomainInput.focus();
            }
        },

        _addRecord: function() {
            var self = this;
            var input = this._els.addDomainInput;
            if (!input || !input.value.trim()) return;

            fetch('/api/bimi/records', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, getAuthHeaders()),
                body: JSON.stringify({ domain: input.value.trim() })
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Failed to add BIMI record');
                return r.json();
            })
            .then(function() {
                notify('BIMI record added', 'success');
                input.value = '';
                self._els.addForm.style.display = 'none';
                self._loadRecords();
            })
            .catch(function(err) { notify(err.message, 'error'); });
        },

        _deleteRecord: function(id) {
            if (!confirm('Delete this BIMI record?')) return;
            var self = this;
            fetch('/api/bimi/records/' + encodeURIComponent(id), {
                method: 'DELETE', headers: getAuthHeaders()
            })
            .then(function(r) {
                if (!r.ok) throw new Error('Failed');
                notify('BIMI record deleted', 'success');
                self._loadRecords();
            })
            .catch(function() { notify('Failed to delete record', 'error'); });
        },

        _showValidateForm: function() {
            if (this._els.validateForm) {
                this._els.validateForm.style.display = '';
                this._els.valResult.style.display = 'none';
                if (this._els.valDomainInput) this._els.valDomainInput.focus();
            }
        },

        _validateDomain: function() {
            var self = this;
            var input = this._els.valDomainInput;
            if (!input || !input.value.trim()) return;
            var resultEl = this._els.valResult;
            if (!resultEl) return;

            resultEl.style.display = '';
            clearElement(resultEl);
            var loading = document.createElement('p');
            loading.className = 'loading';
            loading.textContent = 'Validating...';
            resultEl.appendChild(loading);

            fetch('/api/bimi/validation/' + encodeURIComponent(input.value.trim()), { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) { self._renderValidation(resultEl, data); })
                .catch(function() {
                    clearElement(resultEl);
                    var err = document.createElement('p');
                    err.textContent = 'Validation failed.';
                    err.style.color = 'var(--accent-danger)';
                    resultEl.appendChild(err);
                });
        },

        _renderValidation: function(el, data) {
            clearElement(el);

            var statusBadge = document.createElement('span');
            var valid = data.valid || data.is_valid;
            statusBadge.className = 'badge ' + (valid ? 'badge-success' : 'badge-danger');
            statusBadge.textContent = valid ? 'Valid' : 'Invalid';
            el.appendChild(statusBadge);

            var fields = [
                ['Domain', data.domain],
                ['Has BIMI Record', data.has_bimi_record ? 'Yes' : 'No'],
                ['Logo URL', data.logo_url || '-'],
                ['VMC', data.vmc_status || (data.has_vmc ? 'Found' : 'Not found')]
            ];

            fields.forEach(function(pair) {
                var row = document.createElement('div');
                row.style.cssText = 'display:flex;gap:8px;margin:4px 0;';
                var lbl = document.createElement('strong');
                lbl.textContent = pair[0] + ':';
                var val = document.createElement('span');
                val.textContent = pair[1] || '-';
                row.appendChild(lbl);
                row.appendChild(val);
                el.appendChild(row);
            });

            if (data.issues && data.issues.length > 0) {
                var issueTitle = document.createElement('h4');
                issueTitle.textContent = 'Issues';
                issueTitle.style.marginTop = '8px';
                el.appendChild(issueTitle);
                data.issues.forEach(function(issue) {
                    var p = document.createElement('p');
                    p.style.cssText = 'color:var(--accent-danger);margin:2px 0;';
                    p.textContent = typeof issue === 'string' ? issue : (issue.message || JSON.stringify(issue));
                    el.appendChild(p);
                });
            }
        }
    };

    window.DMARC = window.DMARC || {};
    window.DMARC.BimiPage = BimiPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('bimi', BimiPage);
    }
})();
