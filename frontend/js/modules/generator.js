/**
 * DMARC Dashboard - Record Generator Page Module
 * Generate DMARC and SPF DNS TXT records with a visual form builder.
 */
(function() {
    'use strict';

    var API_BASE = '/api';

    var GeneratorPage = {
        initialized: false,
        containerId: 'page-generator',
        activeTab: 'dmarc',

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            // Page header
            var header = document.createElement('div');
            header.className = 'page-header';
            var h1 = document.createElement('h1');
            h1.textContent = 'Record Generator';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Generate DMARC and SPF DNS TXT records for your domains.';
            header.appendChild(desc);
            container.appendChild(header);

            var body = document.createElement('div');
            body.className = 'page-body';

            // Tab navigation
            var tabNav = document.createElement('div');
            tabNav.style.cssText = 'display:flex;gap:0;border-bottom:2px solid var(--border-color);margin-bottom:24px;';

            var dmarcTab = this._createTabButton('DMARC Record', 'dmarc', true);
            var spfTab = this._createTabButton('SPF Record', 'spf', false);
            tabNav.appendChild(dmarcTab);
            tabNav.appendChild(spfTab);
            body.appendChild(tabNav);

            // Tab panels
            var dmarcPanel = this._buildDmarcPanel();
            dmarcPanel.id = 'gen-panel-dmarc';
            body.appendChild(dmarcPanel);

            var spfPanel = this._buildSpfPanel();
            spfPanel.id = 'gen-panel-spf';
            spfPanel.hidden = true;
            body.appendChild(spfPanel);

            container.appendChild(body);

            // Add initial SPF mechanism row
            this._addSpfMechanism();
        },

        load: function() {
            // Refresh preview on load
            this._updateDmarcPreview();
            this._updateSpfPreview();
        },

        destroy: function() {
            // Nothing to clean up
        },

        // --- Tab Navigation ---

        _createTabButton: function(label, tabId, active) {
            var self = this;
            var btn = document.createElement('button');
            btn.className = 'gen-tab-btn' + (active ? ' gen-tab-active' : '');
            btn.textContent = label;
            btn.dataset.tab = tabId;
            btn.style.cssText = 'padding:10px 20px;border:none;background:none;font-size:0.95rem;font-weight:600;cursor:pointer;' +
                'color:' + (active ? 'var(--accent-primary)' : 'var(--text-secondary)') + ';' +
                'border-bottom:2px solid ' + (active ? 'var(--accent-primary)' : 'transparent') + ';' +
                'margin-bottom:-2px;transition:all 0.2s;';

            btn.addEventListener('click', function() {
                self._switchTab(tabId);
            });
            return btn;
        },

        _switchTab: function(tabId) {
            this.activeTab = tabId;

            // Update tab buttons
            var btns = document.querySelectorAll('.gen-tab-btn');
            btns.forEach(function(btn) {
                var isActive = btn.dataset.tab === tabId;
                btn.className = 'gen-tab-btn' + (isActive ? ' gen-tab-active' : '');
                btn.style.color = isActive ? 'var(--accent-primary)' : 'var(--text-secondary)';
                btn.style.borderBottom = '2px solid ' + (isActive ? 'var(--accent-primary)' : 'transparent');
            });

            // Show/hide panels
            var dmarcPanel = document.getElementById('gen-panel-dmarc');
            var spfPanel = document.getElementById('gen-panel-spf');
            if (dmarcPanel) dmarcPanel.hidden = (tabId !== 'dmarc');
            if (spfPanel) spfPanel.hidden = (tabId !== 'spf');
        },

        // --- DMARC Panel ---

        _buildDmarcPanel: function() {
            var self = this;
            var panel = document.createElement('div');
            panel.className = 'table-container';

            var form = document.createElement('div');
            form.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:20px;';

            // Left column
            var leftCol = document.createElement('div');
            leftCol.style.cssText = 'display:flex;flex-direction:column;gap:16px;';

            // Domain
            leftCol.appendChild(this._createField('Domain', 'gen-dmarc-domain', 'text', 'example.com'));

            // Policy
            var policyGroup = document.createElement('div');
            var policyLabel = document.createElement('label');
            policyLabel.textContent = 'Policy';
            policyLabel.style.cssText = 'display:block;font-weight:600;margin-bottom:8px;font-size:0.9rem;';
            policyGroup.appendChild(policyLabel);
            var policies = [
                { value: 'none', label: 'None', desc: 'Monitor only, no action taken' },
                { value: 'quarantine', label: 'Quarantine', desc: 'Send to spam/junk folder' },
                { value: 'reject', label: 'Reject', desc: 'Block the email entirely' }
            ];
            policies.forEach(function(p) {
                var radioWrap = self._createRadio('gen-dmarc-policy', p.value, p.label, p.desc, p.value === 'none');
                policyGroup.appendChild(radioWrap);
            });
            leftCol.appendChild(policyGroup);

            // Subdomain policy
            var subPolicyGroup = document.createElement('div');
            var subPolicyLabel = document.createElement('label');
            subPolicyLabel.textContent = 'Subdomain Policy';
            subPolicyLabel.style.cssText = 'display:block;font-weight:600;margin-bottom:8px;font-size:0.9rem;';
            subPolicyGroup.appendChild(subPolicyLabel);
            [
                { value: '', label: 'Same as parent', desc: 'Inherit parent domain policy' },
                { value: 'none', label: 'None', desc: '' },
                { value: 'quarantine', label: 'Quarantine', desc: '' },
                { value: 'reject', label: 'Reject', desc: '' }
            ].forEach(function(p) {
                subPolicyGroup.appendChild(self._createRadio('gen-dmarc-sp', p.value, p.label, p.desc, p.value === ''));
            });
            leftCol.appendChild(subPolicyGroup);

            // Percentage slider
            var pctGroup = document.createElement('div');
            var pctLabel = document.createElement('label');
            pctLabel.textContent = 'Percentage';
            pctLabel.setAttribute('for', 'gen-dmarc-pct');
            pctLabel.style.cssText = 'display:block;font-weight:600;margin-bottom:6px;font-size:0.9rem;';
            pctGroup.appendChild(pctLabel);
            var pctRow = document.createElement('div');
            pctRow.style.cssText = 'display:flex;align-items:center;gap:12px;';
            var pctSlider = document.createElement('input');
            pctSlider.type = 'range';
            pctSlider.id = 'gen-dmarc-pct';
            pctSlider.min = '0';
            pctSlider.max = '100';
            pctSlider.value = '100';
            pctSlider.style.flex = '1';
            pctSlider.addEventListener('input', function() {
                document.getElementById('gen-dmarc-pct-val').textContent = pctSlider.value + '%';
                self._updateDmarcPreview();
            });
            pctRow.appendChild(pctSlider);
            var pctVal = document.createElement('span');
            pctVal.id = 'gen-dmarc-pct-val';
            pctVal.textContent = '100%';
            pctVal.style.cssText = 'font-weight:600;min-width:40px;text-align:right;';
            pctRow.appendChild(pctVal);
            pctGroup.appendChild(pctRow);
            leftCol.appendChild(pctGroup);

            form.appendChild(leftCol);

            // Right column
            var rightCol = document.createElement('div');
            rightCol.style.cssText = 'display:flex;flex-direction:column;gap:16px;';

            // RUA emails
            rightCol.appendChild(this._createMultiEmailField('Aggregate Reports (RUA)', 'gen-dmarc-rua', 'mailto:dmarc@example.com'));

            // RUF emails
            rightCol.appendChild(this._createMultiEmailField('Forensic Reports (RUF)', 'gen-dmarc-ruf', 'mailto:forensic@example.com'));

            // Alignment options
            var alignGroup = document.createElement('div');
            var alignLabel = document.createElement('label');
            alignLabel.textContent = 'DKIM Alignment';
            alignLabel.style.cssText = 'display:block;font-weight:600;margin-bottom:8px;font-size:0.9rem;';
            alignGroup.appendChild(alignLabel);
            var alignRow = document.createElement('div');
            alignRow.style.cssText = 'display:flex;gap:16px;';
            alignRow.appendChild(this._createInlineRadio('gen-dmarc-adkim', 'r', 'Relaxed', true));
            alignRow.appendChild(this._createInlineRadio('gen-dmarc-adkim', 's', 'Strict', false));
            alignGroup.appendChild(alignRow);
            rightCol.appendChild(alignGroup);

            var spfAlignGroup = document.createElement('div');
            var spfAlignLabel = document.createElement('label');
            spfAlignLabel.textContent = 'SPF Alignment';
            spfAlignLabel.style.cssText = 'display:block;font-weight:600;margin-bottom:8px;font-size:0.9rem;';
            spfAlignGroup.appendChild(spfAlignLabel);
            var spfAlignRow = document.createElement('div');
            spfAlignRow.style.cssText = 'display:flex;gap:16px;';
            spfAlignRow.appendChild(this._createInlineRadio('gen-dmarc-aspf', 'r', 'Relaxed', true));
            spfAlignRow.appendChild(this._createInlineRadio('gen-dmarc-aspf', 's', 'Strict', false));
            spfAlignGroup.appendChild(spfAlignRow);
            rightCol.appendChild(spfAlignGroup);

            form.appendChild(rightCol);
            panel.appendChild(form);

            // Preview box
            var previewBox = this._createPreviewBox('gen-dmarc-preview', 'gen-dmarc-instructions');
            panel.appendChild(previewBox);

            // Action buttons
            var actions = document.createElement('div');
            actions.style.cssText = 'display:flex;gap:8px;margin-top:16px;';
            var genBtn = document.createElement('button');
            genBtn.className = 'btn-primary';
            genBtn.textContent = 'Generate';
            genBtn.addEventListener('click', this._onGenerateDmarc.bind(this));
            actions.appendChild(genBtn);
            var copyBtn = document.createElement('button');
            copyBtn.className = 'btn-secondary';
            copyBtn.textContent = 'Copy to Clipboard';
            copyBtn.id = 'gen-dmarc-copy';
            copyBtn.addEventListener('click', function() {
                self._copyToClipboard('gen-dmarc-preview');
            });
            actions.appendChild(copyBtn);
            panel.appendChild(actions);

            // Bind live preview on all form inputs
            panel.addEventListener('input', function() { self._updateDmarcPreview(); });
            panel.addEventListener('change', function() { self._updateDmarcPreview(); });

            return panel;
        },

        // --- SPF Panel ---

        _buildSpfPanel: function() {
            var self = this;
            var panel = document.createElement('div');
            panel.className = 'table-container';

            // Domain
            panel.appendChild(this._createField('Domain', 'gen-spf-domain', 'text', 'example.com'));

            // Mechanisms list
            var mechGroup = document.createElement('div');
            mechGroup.style.marginTop = '16px';
            var mechLabel = document.createElement('label');
            mechLabel.textContent = 'SPF Mechanisms';
            mechLabel.style.cssText = 'display:block;font-weight:600;margin-bottom:8px;font-size:0.9rem;';
            mechGroup.appendChild(mechLabel);

            var mechList = document.createElement('div');
            mechList.id = 'gen-spf-mechanisms';
            mechList.style.cssText = 'display:flex;flex-direction:column;gap:8px;';
            mechGroup.appendChild(mechList);

            var addMechBtn = document.createElement('button');
            addMechBtn.className = 'btn-secondary btn-sm';
            addMechBtn.textContent = '+ Add Mechanism';
            addMechBtn.style.marginTop = '8px';
            addMechBtn.addEventListener('click', function() { self._addSpfMechanism(); });
            mechGroup.appendChild(addMechBtn);

            // Lookup count warning
            var lookupWarn = document.createElement('div');
            lookupWarn.id = 'gen-spf-lookup-warning';
            lookupWarn.hidden = true;
            lookupWarn.style.cssText = 'margin-top:8px;padding:8px 12px;background:#fef3c7;color:#92400e;border-radius:6px;font-size:0.85rem;border:1px solid #f59e0b;';
            lookupWarn.textContent = 'Warning: SPF records with more than 10 DNS lookups may fail validation.';
            mechGroup.appendChild(lookupWarn);

            panel.appendChild(mechGroup);

            // All qualifier
            var allGroup = document.createElement('div');
            allGroup.style.marginTop = '16px';
            var allLabel = document.createElement('label');
            allLabel.textContent = 'All Qualifier (catch-all)';
            allLabel.style.cssText = 'display:block;font-weight:600;margin-bottom:8px;font-size:0.9rem;';
            allGroup.appendChild(allLabel);

            [
                { value: '~all', label: '~all (SoftFail)', desc: 'Recommended - mark as suspicious but deliver' },
                { value: '-all', label: '-all (Fail)', desc: 'Strict - reject unauthorized senders' },
                { value: '?all', label: '?all (Neutral)', desc: 'No policy statement' },
                { value: '+all', label: '+all (Pass)', desc: 'Not recommended - allows all senders' }
            ].forEach(function(q) {
                allGroup.appendChild(self._createRadio('gen-spf-all', q.value, q.label, q.desc, q.value === '~all'));
            });
            panel.appendChild(allGroup);

            // Preview box
            var previewBox = this._createPreviewBox('gen-spf-preview', 'gen-spf-instructions');
            panel.appendChild(previewBox);

            // Action buttons
            var actions = document.createElement('div');
            actions.style.cssText = 'display:flex;gap:8px;margin-top:16px;';
            var genBtn = document.createElement('button');
            genBtn.className = 'btn-primary';
            genBtn.textContent = 'Generate';
            genBtn.addEventListener('click', this._onGenerateSpf.bind(this));
            actions.appendChild(genBtn);
            var copyBtn = document.createElement('button');
            copyBtn.className = 'btn-secondary';
            copyBtn.textContent = 'Copy to Clipboard';
            copyBtn.addEventListener('click', function() {
                self._copyToClipboard('gen-spf-preview');
            });
            actions.appendChild(copyBtn);
            panel.appendChild(actions);

            // Bind live preview
            panel.addEventListener('input', function() { self._updateSpfPreview(); });
            panel.addEventListener('change', function() { self._updateSpfPreview(); });

            return panel;
        },

        // --- SPF Mechanisms ---

        _addSpfMechanism: function() {
            var self = this;
            var container = document.getElementById('gen-spf-mechanisms');
            if (!container) return;

            var row = document.createElement('div');
            row.className = 'gen-spf-mech-row';
            row.style.cssText = 'display:flex;gap:8px;align-items:center;';

            // Type dropdown
            var typeSelect = document.createElement('select');
            typeSelect.className = 'gen-spf-mech-type';
            typeSelect.style.cssText = 'padding:6px 10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);font-size:0.85rem;';
            ['include', 'ip4', 'ip6', 'a', 'mx'].forEach(function(t) {
                var opt = document.createElement('option');
                opt.value = t;
                opt.textContent = t;
                typeSelect.appendChild(opt);
            });
            row.appendChild(typeSelect);

            // Value input
            var valueInput = document.createElement('input');
            valueInput.type = 'text';
            valueInput.className = 'gen-spf-mech-value';
            valueInput.placeholder = '_spf.google.com or 192.168.1.0/24';
            valueInput.style.cssText = 'flex:1;padding:6px 10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);font-size:0.85rem;';
            row.appendChild(valueInput);

            // Remove button
            var removeBtn = document.createElement('button');
            removeBtn.className = 'btn-ghost btn-sm';
            removeBtn.textContent = 'Remove';
            removeBtn.style.color = 'var(--accent-danger)';
            removeBtn.addEventListener('click', function() {
                row.remove();
                self._updateSpfPreview();
            });
            row.appendChild(removeBtn);

            container.appendChild(row);
        },

        // --- Generate Actions ---

        _onGenerateDmarc: function() {
            var domain = this._val('gen-dmarc-domain');
            if (!domain) {
                showNotification('Please enter a domain', 'error');
                return;
            }

            var policy = this._getRadioVal('gen-dmarc-policy');
            var sp = this._getRadioVal('gen-dmarc-sp');
            var pct = parseInt(this._val('gen-dmarc-pct') || '100', 10);
            var adkim = this._getRadioVal('gen-dmarc-adkim');
            var aspf = this._getRadioVal('gen-dmarc-aspf');
            var rua = this._getMultiEmails('gen-dmarc-rua');
            var ruf = this._getMultiEmails('gen-dmarc-ruf');

            var payload = {
                domain: domain,
                policy: policy || 'none',
                percentage: pct
            };
            if (sp) payload.subdomain_policy = sp;
            if (rua.length) payload.rua = rua;
            if (ruf.length) payload.ruf = ruf;
            if (adkim) payload.adkim = adkim;
            if (aspf) payload.aspf = aspf;

            fetch(API_BASE + '/generator/dmarc-record', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, this._getHeaders()),
                body: JSON.stringify(payload)
            })
            .then(function(r) {
                if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Generation failed'); });
                return r.json();
            })
            .then(function(data) {
                var preview = document.getElementById('gen-dmarc-preview');
                if (preview) preview.textContent = data.record || '';
                var instructions = document.getElementById('gen-dmarc-instructions');
                if (instructions) {
                    instructions.textContent = 'Add this TXT record to _dmarc.' + domain;
                    instructions.hidden = false;
                }
                showNotification('DMARC record generated', 'success');
            })
            .catch(function(err) {
                showNotification(err.message, 'error');
            });
        },

        _onGenerateSpf: function() {
            var domain = this._val('gen-spf-domain');
            if (!domain) {
                showNotification('Please enter a domain', 'error');
                return;
            }

            var mechanisms = this._getSpfMechanisms();
            var allQualifier = this._getRadioVal('gen-spf-all') || '~all';

            var payload = {
                domain: domain,
                mechanisms: mechanisms,
                all_qualifier: allQualifier
            };

            fetch(API_BASE + '/generator/spf-record', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, this._getHeaders()),
                body: JSON.stringify(payload)
            })
            .then(function(r) {
                if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Generation failed'); });
                return r.json();
            })
            .then(function(data) {
                var preview = document.getElementById('gen-spf-preview');
                if (preview) preview.textContent = data.record || '';
                var instructions = document.getElementById('gen-spf-instructions');
                if (instructions) {
                    instructions.textContent = 'Add this TXT record to ' + domain;
                    instructions.hidden = false;
                }
                showNotification('SPF record generated', 'success');
            })
            .catch(function(err) {
                showNotification(err.message, 'error');
            });
        },

        // --- Live Preview ---

        _updateDmarcPreview: function() {
            var parts = ['v=DMARC1'];
            var policy = this._getRadioVal('gen-dmarc-policy');
            parts.push('p=' + (policy || 'none'));

            var sp = this._getRadioVal('gen-dmarc-sp');
            if (sp) parts.push('sp=' + sp);

            var pct = this._val('gen-dmarc-pct');
            if (pct && pct !== '100') parts.push('pct=' + pct);

            var rua = this._getMultiEmails('gen-dmarc-rua');
            if (rua.length) parts.push('rua=' + rua.join(','));

            var ruf = this._getMultiEmails('gen-dmarc-ruf');
            if (ruf.length) parts.push('ruf=' + ruf.join(','));

            var adkim = this._getRadioVal('gen-dmarc-adkim');
            if (adkim && adkim !== 'r') parts.push('adkim=' + adkim);

            var aspf = this._getRadioVal('gen-dmarc-aspf');
            if (aspf && aspf !== 'r') parts.push('aspf=' + aspf);

            var preview = document.getElementById('gen-dmarc-preview');
            if (preview) preview.textContent = parts.join('; ');

            var domain = this._val('gen-dmarc-domain');
            var instructions = document.getElementById('gen-dmarc-instructions');
            if (instructions) {
                if (domain) {
                    instructions.textContent = 'Add this TXT record to _dmarc.' + domain;
                    instructions.hidden = false;
                } else {
                    instructions.hidden = true;
                }
            }
        },

        _updateSpfPreview: function() {
            var parts = ['v=spf1'];
            var mechanisms = this._getSpfMechanisms();
            mechanisms.forEach(function(m) {
                if (m.value) {
                    parts.push(m.type + ':' + m.value);
                } else {
                    parts.push(m.type);
                }
            });

            var allQualifier = this._getRadioVal('gen-spf-all') || '~all';
            parts.push(allQualifier);

            var preview = document.getElementById('gen-spf-preview');
            if (preview) preview.textContent = parts.join(' ');

            // Lookup count warning
            var lookupTypes = ['include', 'a', 'mx'];
            var lookupCount = mechanisms.filter(function(m) { return lookupTypes.indexOf(m.type) !== -1; }).length;
            var warn = document.getElementById('gen-spf-lookup-warning');
            if (warn) warn.hidden = lookupCount <= 10;

            var domain = this._val('gen-spf-domain');
            var instructions = document.getElementById('gen-spf-instructions');
            if (instructions) {
                if (domain) {
                    instructions.textContent = 'Add this TXT record to ' + domain;
                    instructions.hidden = false;
                } else {
                    instructions.hidden = true;
                }
            }
        },

        // --- Helpers ---

        _getHeaders: function() {
            if (typeof getAuthHeaders === 'function') return getAuthHeaders();
            var DMARC = window.DMARC;
            if (DMARC && DMARC.getAuthHeaders) return DMARC.getAuthHeaders();
            return {};
        },

        _val: function(id) {
            var el = document.getElementById(id);
            return el ? el.value.trim() : '';
        },

        _getRadioVal: function(name) {
            var checked = document.querySelector('input[name="' + name + '"]:checked');
            return checked ? checked.value : '';
        },

        _getMultiEmails: function(containerId) {
            var container = document.getElementById(containerId + '-list');
            if (!container) return [];
            var emails = [];
            container.querySelectorAll('.gen-email-value').forEach(function(el) {
                var v = el.value.trim();
                if (v) emails.push(v);
            });
            return emails;
        },

        _getSpfMechanisms: function() {
            var rows = document.querySelectorAll('.gen-spf-mech-row');
            var mechanisms = [];
            rows.forEach(function(row) {
                var type = row.querySelector('.gen-spf-mech-type');
                var value = row.querySelector('.gen-spf-mech-value');
                if (type && value && value.value.trim()) {
                    mechanisms.push({ type: type.value, value: value.value.trim() });
                }
            });
            return mechanisms;
        },

        _createField: function(labelText, id, type, placeholder) {
            var group = document.createElement('div');
            var label = document.createElement('label');
            label.textContent = labelText;
            label.setAttribute('for', id);
            label.style.cssText = 'display:block;font-weight:600;margin-bottom:6px;font-size:0.9rem;';
            group.appendChild(label);
            var input = document.createElement('input');
            input.type = type || 'text';
            input.id = id;
            if (placeholder) input.placeholder = placeholder;
            input.style.cssText = 'width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);font-size:0.9rem;box-sizing:border-box;';
            group.appendChild(input);
            return group;
        },

        _createRadio: function(name, value, label, desc, checked) {
            var wrapper = document.createElement('label');
            wrapper.style.cssText = 'display:flex;align-items:flex-start;gap:8px;padding:6px 0;cursor:pointer;font-size:0.9rem;';
            var radio = document.createElement('input');
            radio.type = 'radio';
            radio.name = name;
            radio.value = value;
            if (checked) radio.checked = true;
            radio.style.marginTop = '3px';
            wrapper.appendChild(radio);
            var textWrap = document.createElement('div');
            var labelSpan = document.createElement('span');
            labelSpan.textContent = label;
            labelSpan.style.fontWeight = '500';
            textWrap.appendChild(labelSpan);
            if (desc) {
                var descSpan = document.createElement('span');
                descSpan.textContent = ' - ' + desc;
                descSpan.style.cssText = 'color:var(--text-secondary);font-size:0.85rem;';
                textWrap.appendChild(descSpan);
            }
            wrapper.appendChild(textWrap);
            return wrapper;
        },

        _createInlineRadio: function(name, value, label, checked) {
            var wrapper = document.createElement('label');
            wrapper.style.cssText = 'display:inline-flex;align-items:center;gap:6px;cursor:pointer;font-size:0.9rem;';
            var radio = document.createElement('input');
            radio.type = 'radio';
            radio.name = name;
            radio.value = value;
            if (checked) radio.checked = true;
            wrapper.appendChild(radio);
            var span = document.createElement('span');
            span.textContent = label;
            wrapper.appendChild(span);
            return wrapper;
        },

        _createMultiEmailField: function(labelText, baseId, placeholder) {
            var self = this;
            var group = document.createElement('div');
            var label = document.createElement('label');
            label.textContent = labelText;
            label.style.cssText = 'display:block;font-weight:600;margin-bottom:6px;font-size:0.9rem;';
            group.appendChild(label);

            var list = document.createElement('div');
            list.id = baseId + '-list';
            list.style.cssText = 'display:flex;flex-direction:column;gap:6px;';

            // Add initial row
            list.appendChild(this._createEmailRow(baseId, placeholder));
            group.appendChild(list);

            var addBtn = document.createElement('button');
            addBtn.className = 'btn-ghost btn-sm';
            addBtn.textContent = '+ Add another';
            addBtn.style.marginTop = '4px';
            addBtn.addEventListener('click', function() {
                list.appendChild(self._createEmailRow(baseId, placeholder));
            });
            group.appendChild(addBtn);
            return group;
        },

        _createEmailRow: function(baseId, placeholder) {
            var self = this;
            var row = document.createElement('div');
            row.style.cssText = 'display:flex;gap:6px;align-items:center;';
            var input = document.createElement('input');
            input.type = 'text';
            input.className = 'gen-email-value';
            input.placeholder = placeholder || 'mailto:user@example.com';
            input.style.cssText = 'flex:1;padding:6px 10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);font-size:0.85rem;';
            row.appendChild(input);
            var removeBtn = document.createElement('button');
            removeBtn.className = 'btn-ghost btn-sm';
            removeBtn.textContent = 'Remove';
            removeBtn.style.color = 'var(--accent-danger)';
            removeBtn.addEventListener('click', function() {
                var list = document.getElementById(baseId + '-list');
                if (list && list.children.length > 1) {
                    row.remove();
                    self._updateDmarcPreview();
                }
            });
            row.appendChild(removeBtn);
            return row;
        },

        _createPreviewBox: function(previewId, instructionsId) {
            var box = document.createElement('div');
            box.style.cssText = 'margin-top:20px;padding:16px;background:var(--bg-tertiary);border-radius:8px;border:1px solid var(--border-color);';

            var previewLabel = document.createElement('div');
            previewLabel.textContent = 'Generated Record';
            previewLabel.style.cssText = 'font-weight:600;margin-bottom:8px;font-size:0.85rem;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.05em;';
            box.appendChild(previewLabel);

            var previewCode = document.createElement('code');
            previewCode.id = previewId;
            previewCode.style.cssText = 'display:block;padding:12px;background:var(--bg-primary);border-radius:6px;font-family:monospace;font-size:0.9rem;word-break:break-all;color:var(--text-primary);border:1px solid var(--border-color);min-height:24px;';
            previewCode.textContent = previewId.indexOf('dmarc') !== -1 ? 'v=DMARC1; p=none' : 'v=spf1 ~all';
            box.appendChild(previewCode);

            var instructions = document.createElement('div');
            instructions.id = instructionsId;
            instructions.hidden = true;
            instructions.style.cssText = 'margin-top:10px;padding:8px 12px;background:rgba(77,171,247,0.1);border-radius:6px;font-size:0.85rem;color:var(--accent-primary);border:1px solid var(--accent-primary);';
            box.appendChild(instructions);

            return box;
        },

        _copyToClipboard: function(previewId) {
            var el = document.getElementById(previewId);
            if (!el) return;
            var text = el.textContent;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(function() {
                    showNotification('Copied to clipboard', 'success');
                }).catch(function() {
                    showNotification('Failed to copy', 'error');
                });
            } else {
                // Fallback for older browsers
                var ta = document.createElement('textarea');
                ta.value = text;
                ta.style.cssText = 'position:fixed;left:-9999px;';
                document.body.appendChild(ta);
                ta.select();
                try {
                    document.execCommand('copy');
                    showNotification('Copied to clipboard', 'success');
                } catch (e) {
                    showNotification('Failed to copy', 'error');
                }
                document.body.removeChild(ta);
            }
        }
    };

    // Expose module
    window.DMARC = window.DMARC || {};
    window.DMARC.GeneratorPage = GeneratorPage;

    // Register with router
    if (window.DMARC.Router) {
        window.DMARC.Router.register('generator', GeneratorPage);
    }
})();
