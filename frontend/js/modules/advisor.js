/**
 * DMARC Dashboard - Policy Advisor Page Module
 *
 * Displays actionable recommendations for improving DMARC policies,
 * a policy status comparison table, and a policy migration path
 * visualization (none -> quarantine -> reject).
 */
(function() {
    'use strict';

    var API_BASE = '/api';

    var PRIORITY_COLORS = {
        high:   { bg: '#fee2e2', fg: '#991b1b' },
        medium: { bg: '#fef3c7', fg: '#92400e' },
        low:    { bg: '#d1fae5', fg: '#065f46' }
    };

    var PRIORITY_CLASSES = {
        high: 'badge-danger',
        medium: 'badge-warning',
        low: 'badge-success'
    };

    var POLICY_LABELS = {
        none: 'None',
        quarantine: 'Quarantine',
        reject: 'Reject'
    };

    var POLICY_ORDER = { none: 0, quarantine: 1, reject: 2 };

    var AdvisorPage = {
        initialized: false,
        containerId: 'page-advisor',
        recommendations: [],
        policyStatus: [],
        selectedDomain: '',

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            this._buildPage(container);
            this._bindEvents(container);
        },

        _buildPage: function(container) {
            // Page header
            var header = document.createElement('div');
            header.className = 'page-header';
            var h1 = document.createElement('h1');
            h1.textContent = 'Policy Advisor';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Get actionable recommendations to strengthen your DMARC policies.';
            header.appendChild(desc);
            container.appendChild(header);

            // Controls row
            var controls = document.createElement('div');
            controls.style.cssText = 'display:flex;align-items:center;gap:12px;margin-bottom:20px;flex-wrap:wrap;';

            var domainLabel = document.createElement('label');
            domainLabel.textContent = 'Domain: ';
            domainLabel.setAttribute('for', 'advisorDomainFilter');
            domainLabel.style.cssText = 'color:var(--text-secondary);font-size:0.85rem;font-weight:600;';
            controls.appendChild(domainLabel);

            var domainSelect = document.createElement('select');
            domainSelect.id = 'advisorDomainFilter';
            domainSelect.style.cssText = 'padding:6px 10px;border-radius:6px;border:1px solid var(--border-color);background:var(--input-bg);color:var(--text-primary);font-size:0.85rem;min-width:180px;';
            var allOption = document.createElement('option');
            allOption.value = '';
            allOption.textContent = 'All Domains';
            domainSelect.appendChild(allOption);
            controls.appendChild(domainSelect);

            var daysLabel = document.createElement('label');
            daysLabel.textContent = 'Period: ';
            daysLabel.setAttribute('for', 'advisorDaysSelect');
            daysLabel.style.cssText = 'color:var(--text-secondary);font-size:0.85rem;font-weight:600;';
            controls.appendChild(daysLabel);

            var daysSelect = document.createElement('select');
            daysSelect.id = 'advisorDaysSelect';
            daysSelect.style.cssText = 'padding:6px 10px;border-radius:6px;border:1px solid var(--border-color);background:var(--input-bg);color:var(--text-primary);font-size:0.85rem;';
            [
                { value: '7', text: '7 days' },
                { value: '30', text: '30 days' },
                { value: '90', text: '90 days' }
            ].forEach(function(opt) {
                var option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.text;
                if (opt.value === '30') option.selected = true;
                daysSelect.appendChild(option);
            });
            controls.appendChild(daysSelect);

            var refreshBtn = document.createElement('button');
            refreshBtn.className = 'btn-secondary btn-sm';
            refreshBtn.id = 'advisorRefreshBtn';
            refreshBtn.textContent = 'Refresh';
            controls.appendChild(refreshBtn);

            container.appendChild(controls);

            // Recommendations section
            var recsHeader = document.createElement('h2');
            recsHeader.textContent = 'Recommendations';
            recsHeader.style.cssText = 'margin:0 0 12px;color:var(--text-heading);font-size:1.1rem;';
            container.appendChild(recsHeader);

            var recsList = document.createElement('div');
            recsList.id = 'advisorRecsList';
            recsList.style.cssText = 'display:flex;flex-direction:column;gap:12px;margin-bottom:28px;';
            container.appendChild(recsList);

            // Policy migration path visualization
            var migHeader = document.createElement('h2');
            migHeader.textContent = 'Policy Migration Path';
            migHeader.style.cssText = 'margin:0 0 12px;color:var(--text-heading);font-size:1.1rem;';
            container.appendChild(migHeader);

            var migViz = document.createElement('div');
            migViz.id = 'advisorMigrationViz';
            migViz.style.cssText = 'margin-bottom:28px;';
            container.appendChild(migViz);

            // Policy status table
            var tableHeader = document.createElement('h2');
            tableHeader.textContent = 'Policy Status';
            tableHeader.style.cssText = 'margin:0 0 12px;color:var(--text-heading);font-size:1.1rem;';
            container.appendChild(tableHeader);

            var tableWrap = document.createElement('div');
            tableWrap.className = 'table-section';

            var table = document.createElement('table');
            table.id = 'advisorPolicyTable';
            table.setAttribute('aria-label', 'Domain policy status');

            var thead = document.createElement('thead');
            var headerRow = document.createElement('tr');
            ['Domain', 'Current Policy', 'Recommended Policy', 'Compliance Gap'].forEach(function(label) {
                var th = document.createElement('th');
                th.setAttribute('scope', 'col');
                th.textContent = label;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);

            var tbody = document.createElement('tbody');
            tbody.id = 'advisorPolicyBody';
            table.appendChild(tbody);

            tableWrap.appendChild(table);
            container.appendChild(tableWrap);
        },

        _bindEvents: function(container) {
            var self = this;
            var domainSelect = container.querySelector('#advisorDomainFilter');
            if (domainSelect) {
                domainSelect.addEventListener('change', function() {
                    self.selectedDomain = domainSelect.value;
                    self._loadRecommendations();
                });
            }

            var daysSelect = container.querySelector('#advisorDaysSelect');
            if (daysSelect) {
                daysSelect.addEventListener('change', function() {
                    self.load();
                });
            }

            var refreshBtn = container.querySelector('#advisorRefreshBtn');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', function() {
                    self.load();
                });
            }
        },

        load: function() {
            var self = this;

            // Check if navigated from health page with a domain selected
            if (window.DMARC._healthSelectedDomain) {
                self.selectedDomain = window.DMARC._healthSelectedDomain;
                delete window.DMARC._healthSelectedDomain;
                var domainSelect = document.getElementById('advisorDomainFilter');
                if (domainSelect) {
                    // Ensure the option exists; if not, it will be added after policy-status loads
                    self._setDomainFilter(self.selectedDomain);
                }
            }

            this._showLoading();

            // Fetch policy status to populate domain filter + table, then recommendations
            Promise.all([
                fetch(API_BASE + '/advisor/policy-status').then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                }),
                this._fetchRecommendations()
            ]).then(function(results) {
                var policyData = Array.isArray(results[0]) ? results[0] : [];
                var recsData = Array.isArray(results[1]) ? results[1] : [];

                self.policyStatus = policyData;
                self.recommendations = recsData;

                self._populateDomainFilter(policyData);
                self._renderRecommendations(recsData);
                self._renderMigrationPath(policyData);
                self._renderPolicyTable(policyData);
            }).catch(function(err) {
                console.error('Error loading advisor data:', err);
                var DMARC = window.DMARC;
                if (DMARC && DMARC.showNotification) {
                    DMARC.showNotification('Failed to load advisor data', 'error');
                }
            });
        },

        _fetchRecommendations: function() {
            var daysSelect = document.getElementById('advisorDaysSelect');
            var days = daysSelect ? daysSelect.value : '30';
            var url;
            if (this.selectedDomain) {
                url = API_BASE + '/advisor/recommendations/' + encodeURIComponent(this.selectedDomain) + '?days=' + days;
            } else {
                url = API_BASE + '/advisor/recommendations?days=' + days;
            }
            return fetch(url).then(function(r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            });
        },

        _loadRecommendations: function() {
            var self = this;
            var recsList = document.getElementById('advisorRecsList');
            if (recsList) recsList.textContent = 'Loading recommendations...';

            this._fetchRecommendations().then(function(data) {
                self.recommendations = Array.isArray(data) ? data : [];
                self._renderRecommendations(self.recommendations);
            }).catch(function(err) {
                console.error('Error loading recommendations:', err);
                if (recsList) recsList.textContent = 'Failed to load recommendations.';
            });
        },

        _showLoading: function() {
            var recsList = document.getElementById('advisorRecsList');
            if (recsList) recsList.textContent = 'Loading...';
            var tbody = document.getElementById('advisorPolicyBody');
            if (tbody) {
                tbody.textContent = '';
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.setAttribute('colspan', '4');
                td.className = 'loading';
                td.textContent = 'Loading policy data...';
                tr.appendChild(td);
                tbody.appendChild(tr);
            }
            var viz = document.getElementById('advisorMigrationViz');
            if (viz) viz.textContent = 'Loading...';
        },

        _populateDomainFilter: function(policyData) {
            var select = document.getElementById('advisorDomainFilter');
            if (!select) return;

            // Preserve current selection
            var current = select.value;

            // Remove all except first option (All Domains)
            while (select.options.length > 1) {
                select.remove(1);
            }

            var domains = [];
            policyData.forEach(function(d) {
                if (d.domain && domains.indexOf(d.domain) === -1) {
                    domains.push(d.domain);
                }
            });
            domains.sort();

            domains.forEach(function(domain) {
                var opt = document.createElement('option');
                opt.value = domain;
                opt.textContent = domain;
                select.appendChild(opt);
            });

            // Restore selection
            if (this.selectedDomain) {
                this._setDomainFilter(this.selectedDomain);
            } else if (current) {
                select.value = current;
            }
        },

        _setDomainFilter: function(domain) {
            var select = document.getElementById('advisorDomainFilter');
            if (!select) return;
            // Check if option exists
            for (var i = 0; i < select.options.length; i++) {
                if (select.options[i].value === domain) {
                    select.value = domain;
                    return;
                }
            }
            // Add it
            var opt = document.createElement('option');
            opt.value = domain;
            opt.textContent = domain;
            select.appendChild(opt);
            select.value = domain;
        },

        _renderRecommendations: function(recs) {
            var container = document.getElementById('advisorRecsList');
            if (!container) return;
            container.textContent = '';

            if (recs.length === 0) {
                var empty = document.createElement('div');
                empty.style.cssText = 'text-align:center;padding:32px;color:var(--text-secondary);background:var(--card-bg);border-radius:12px;border:1px solid var(--border-color);';
                empty.textContent = this.selectedDomain
                    ? 'No recommendations for ' + this.selectedDomain + '.'
                    : 'No recommendations available. Import DMARC reports to get started.';
                container.appendChild(empty);
                return;
            }

            // Sort by priority: high first
            var priorityOrder = { high: 0, medium: 1, low: 2 };
            var sorted = recs.slice().sort(function(a, b) {
                return (priorityOrder[a.priority] || 1) - (priorityOrder[b.priority] || 1);
            });

            sorted.forEach(function(rec) {
                container.appendChild(this._createRecCard(rec));
            }.bind(this));
        },

        _createRecCard: function(rec) {
            var card = document.createElement('div');
            card.style.cssText = 'background:var(--card-bg);border:1px solid var(--border-color);border-radius:12px;padding:16px 20px;box-shadow:0 1px 3px var(--shadow-color);';

            // Top row: domain, priority, type
            var topRow = document.createElement('div');
            topRow.style.cssText = 'display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px;';

            if (rec.domain) {
                var domainEl = document.createElement('span');
                domainEl.style.cssText = 'font-weight:600;color:var(--text-heading);font-size:0.95rem;';
                domainEl.textContent = rec.domain;
                topRow.appendChild(domainEl);
            }

            var priority = (rec.priority || 'medium').toLowerCase();
            var priBadge = document.createElement('span');
            priBadge.className = 'badge ' + (PRIORITY_CLASSES[priority] || 'badge-warning');
            priBadge.textContent = priority.charAt(0).toUpperCase() + priority.slice(1);
            topRow.appendChild(priBadge);

            if (rec.type) {
                var typeBadge = document.createElement('span');
                typeBadge.className = 'badge badge-gray';
                typeBadge.textContent = rec.type.replace(/_/g, ' ');
                topRow.appendChild(typeBadge);
            }

            card.appendChild(topRow);

            // Recommended action (prominent)
            if (rec.recommended_action) {
                var action = document.createElement('div');
                action.style.cssText = 'font-size:1rem;font-weight:600;color:var(--text-primary);margin-bottom:8px;line-height:1.4;';
                action.textContent = rec.recommended_action;
                card.appendChild(action);
            }

            // Impact
            if (rec.impact) {
                var impact = document.createElement('div');
                impact.style.cssText = 'font-size:0.85rem;color:var(--text-secondary);margin-bottom:8px;';
                var impLabel = document.createElement('strong');
                impLabel.textContent = 'Impact: ';
                impact.appendChild(impLabel);
                impact.appendChild(document.createTextNode(rec.impact));
                card.appendChild(impact);
            }

            // Current state (expandable)
            if (rec.current_state) {
                card.appendChild(this._createExpandable('Current State', rec.current_state));
            }

            // Reasoning (expandable)
            if (rec.reasoning) {
                card.appendChild(this._createExpandable('Reasoning', rec.reasoning));
            }

            return card;
        },

        _createExpandable: function(title, content) {
            var details = document.createElement('details');
            details.style.cssText = 'margin-top:6px;';
            var summary = document.createElement('summary');
            summary.style.cssText = 'cursor:pointer;font-size:0.85rem;color:var(--accent-primary);font-weight:500;user-select:none;';
            summary.textContent = title;
            details.appendChild(summary);

            var body = document.createElement('div');
            body.style.cssText = 'padding:8px 0 4px 12px;font-size:0.85rem;color:var(--text-secondary);line-height:1.5;';
            body.textContent = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
            details.appendChild(body);

            return details;
        },

        _renderMigrationPath: function(policyData) {
            var container = document.getElementById('advisorMigrationViz');
            if (!container) return;
            container.textContent = '';

            var stages = ['none', 'quarantine', 'reject'];
            var stageLabels = ['None (Monitor)', 'Quarantine', 'Reject'];
            var stageColors = ['#6b7280', '#f39c12', '#27ae60'];
            var stageBgColors = ['#e5e7eb', '#fef3c7', '#d1fae5'];

            // Group domains by current policy
            var domainsByPolicy = { none: [], quarantine: [], reject: [] };
            policyData.forEach(function(d) {
                var policy = (d.current_policy || 'none').toLowerCase();
                if (!domainsByPolicy[policy]) domainsByPolicy[policy] = [];
                domainsByPolicy[policy].push(d.domain);
            });

            // Build visualization
            var vizWrap = document.createElement('div');
            vizWrap.style.cssText = 'display:flex;align-items:stretch;gap:0;background:var(--card-bg);border:1px solid var(--border-color);border-radius:12px;overflow:hidden;min-height:120px;';

            stages.forEach(function(stage, idx) {
                var stageEl = document.createElement('div');
                stageEl.style.cssText = 'flex:1;padding:16px;position:relative;border-right:' + (idx < 2 ? '2px solid var(--border-color)' : 'none') + ';';

                // Stage label
                var label = document.createElement('div');
                label.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:12px;';
                var dot = document.createElement('div');
                dot.style.cssText = 'width:12px;height:12px;border-radius:50%;flex-shrink:0;background:' + stageColors[idx] + ';';
                label.appendChild(dot);
                var labelText = document.createElement('span');
                labelText.style.cssText = 'font-weight:600;font-size:0.9rem;color:var(--text-heading);';
                labelText.textContent = stageLabels[idx];
                label.appendChild(labelText);
                stageEl.appendChild(label);

                // Domain chips
                var domains = domainsByPolicy[stage] || [];
                if (domains.length === 0) {
                    var emptyText = document.createElement('div');
                    emptyText.style.cssText = 'font-size:0.8rem;color:var(--text-muted);font-style:italic;';
                    emptyText.textContent = 'No domains';
                    stageEl.appendChild(emptyText);
                } else {
                    var chipsWrap = document.createElement('div');
                    chipsWrap.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;';
                    domains.forEach(function(domain) {
                        var chip = document.createElement('span');
                        chip.style.cssText = 'display:inline-block;padding:3px 8px;border-radius:4px;font-size:0.78rem;font-weight:500;background:' + stageBgColors[idx] + ';color:' + stageColors[idx] + ';';
                        chip.textContent = domain;
                        chipsWrap.appendChild(chip);
                    });
                    stageEl.appendChild(chipsWrap);
                }

                // Arrow between stages
                if (idx < 2) {
                    var arrow = document.createElement('div');
                    arrow.style.cssText = 'position:absolute;right:-12px;top:50%;transform:translateY(-50%);width:22px;height:22px;background:var(--card-bg);border:2px solid var(--border-color);border-radius:50%;display:flex;align-items:center;justify-content:center;z-index:1;font-size:0.75rem;color:var(--text-secondary);';
                    arrow.textContent = '\u2192';
                    stageEl.appendChild(arrow);
                }

                vizWrap.appendChild(stageEl);
            });

            container.appendChild(vizWrap);
        },

        _renderPolicyTable: function(policyData) {
            var tbody = document.getElementById('advisorPolicyBody');
            if (!tbody) return;
            tbody.textContent = '';

            if (policyData.length === 0) {
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.setAttribute('colspan', '4');
                td.style.cssText = 'text-align:center;padding:24px;color:var(--text-secondary);';
                td.textContent = 'No policy data available.';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            policyData.forEach(function(d) {
                var tr = document.createElement('tr');

                // Domain
                var tdDomain = document.createElement('td');
                tdDomain.textContent = d.domain || '';
                tdDomain.style.fontWeight = '600';
                tr.appendChild(tdDomain);

                // Current policy
                var tdCurrent = document.createElement('td');
                var currentPolicy = (d.current_policy || 'none').toLowerCase();
                var currentBadge = document.createElement('span');
                currentBadge.className = 'badge';
                currentBadge.textContent = POLICY_LABELS[currentPolicy] || currentPolicy;
                if (currentPolicy === 'reject') {
                    currentBadge.classList.add('badge-success');
                } else if (currentPolicy === 'quarantine') {
                    currentBadge.classList.add('badge-warning');
                } else {
                    currentBadge.classList.add('badge-gray');
                }
                tdCurrent.appendChild(currentBadge);
                tr.appendChild(tdCurrent);

                // Recommended policy
                var tdRec = document.createElement('td');
                var recPolicy = (d.recommended_policy || '').toLowerCase();
                if (recPolicy) {
                    var recBadge = document.createElement('span');
                    recBadge.className = 'badge';
                    recBadge.textContent = POLICY_LABELS[recPolicy] || recPolicy;
                    if (recPolicy === 'reject') {
                        recBadge.classList.add('badge-success');
                    } else if (recPolicy === 'quarantine') {
                        recBadge.classList.add('badge-warning');
                    } else {
                        recBadge.classList.add('badge-gray');
                    }
                    tdRec.appendChild(recBadge);
                } else {
                    tdRec.textContent = '-';
                    tdRec.style.color = 'var(--text-muted)';
                }
                tr.appendChild(tdRec);

                // Compliance gap indicator
                var tdGap = document.createElement('td');
                var gapValue = d.compliance_gap;
                if (gapValue != null && gapValue !== undefined) {
                    var gapText;
                    var gapColor;
                    if (typeof gapValue === 'number') {
                        if (gapValue <= 0) {
                            gapText = 'Compliant';
                            gapColor = '#27ae60';
                        } else if (gapValue === 1) {
                            gapText = '1 step to go';
                            gapColor = '#f39c12';
                        } else {
                            gapText = gapValue + ' steps to go';
                            gapColor = '#e74c3c';
                        }
                    } else {
                        gapText = String(gapValue);
                        gapColor = 'var(--text-secondary)';
                    }
                    var gapEl = document.createElement('span');
                    gapEl.style.cssText = 'font-weight:600;font-size:0.85rem;color:' + gapColor + ';';
                    gapEl.textContent = gapText;
                    tdGap.appendChild(gapEl);
                } else {
                    // Compute from policies
                    var currentOrder = POLICY_ORDER[currentPolicy] || 0;
                    var recOrder = POLICY_ORDER[recPolicy] || currentOrder;
                    var gap = recOrder - currentOrder;
                    var gapSpan = document.createElement('span');
                    if (gap <= 0) {
                        gapSpan.textContent = 'Compliant';
                        gapSpan.style.color = '#27ae60';
                    } else if (gap === 1) {
                        gapSpan.textContent = '1 step to go';
                        gapSpan.style.color = '#f39c12';
                    } else {
                        gapSpan.textContent = gap + ' steps to go';
                        gapSpan.style.color = '#e74c3c';
                    }
                    gapSpan.style.fontWeight = '600';
                    gapSpan.style.fontSize = '0.85rem';
                    tdGap.appendChild(gapSpan);
                }
                tr.appendChild(tdGap);

                tbody.appendChild(tr);
            });
        },

        destroy: function() {
            // Nothing to clean up
        }
    };

    // Expose and register
    window.DMARC = window.DMARC || {};
    window.DMARC.AdvisorPage = AdvisorPage;
    if (window.DMARC.Router) {
        window.DMARC.Router.register('advisor', AdvisorPage);
    }
})();
