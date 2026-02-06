/**
 * DMARC Dashboard - TLS-RPT Page Module
 * Displays TLS reporting data: summaries, failures, timelines.
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

    var TlsRptPage = {
        initialized: false,
        containerId: 'page-tls-rpt',
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
            h1.textContent = 'TLS-RPT Reports';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'TLS reporting data showing SMTP TLS failures and compliance across your domains.';
            header.appendChild(desc);

            // Summary cards
            var summary = document.createElement('div');
            summary.className = 'stats-grid';
            summary.style.marginBottom = '20px';
            this._els.summary = summary;

            // Timeline chart
            var chartWrap = document.createElement('div');
            chartWrap.className = 'chart-container';
            chartWrap.style.marginBottom = '20px';
            var chartHeader = document.createElement('div');
            chartHeader.className = 'chart-header';
            var chartTitle = document.createElement('h2');
            chartTitle.textContent = 'TLS Failures Over Time';
            chartHeader.appendChild(chartTitle);
            chartWrap.appendChild(chartHeader);
            var canvas = document.createElement('canvas');
            canvas.id = 'tlsRptTimelineChart';
            chartWrap.appendChild(canvas);
            this._els.canvas = canvas;

            // Failures table
            var failWrap = document.createElement('div');
            failWrap.className = 'table-container';
            failWrap.style.marginBottom = '20px';
            var failHeader = document.createElement('div');
            failHeader.className = 'table-header';
            var failTitle = document.createElement('h2');
            failTitle.textContent = 'Recent Failures';
            failHeader.appendChild(failTitle);

            var failTable = document.createElement('table');
            var failThead = document.createElement('thead');
            var failHRow = document.createElement('tr');
            ['Domain', 'Failure Type', 'Count', 'Last Seen', 'Details'].forEach(function(col) {
                var th = document.createElement('th');
                th.scope = 'col';
                th.textContent = col;
                failHRow.appendChild(th);
            });
            failThead.appendChild(failHRow);
            failTable.appendChild(failThead);
            var failTbody = document.createElement('tbody');
            this._els.failTbody = failTbody;
            failTable.appendChild(failTbody);
            failWrap.appendChild(failHeader);
            failWrap.appendChild(failTable);

            // Reports table
            var reportsWrap = document.createElement('div');
            reportsWrap.className = 'table-container';
            reportsWrap.style.marginBottom = '20px';
            var repHeader = document.createElement('div');
            repHeader.className = 'table-header';
            var repTitle = document.createElement('h2');
            repTitle.textContent = 'TLS Reports';
            repHeader.appendChild(repTitle);
            var repCount = document.createElement('span');
            repCount.className = 'table-count';
            this._els.repCount = repCount;
            repHeader.appendChild(repCount);

            var repTable = document.createElement('table');
            var repThead = document.createElement('thead');
            var repHRow = document.createElement('tr');
            ['ID', 'Domain', 'Organization', 'Date', 'Total', 'Failures'].forEach(function(col) {
                var th = document.createElement('th');
                th.scope = 'col';
                th.textContent = col;
                repHRow.appendChild(th);
            });
            repThead.appendChild(repHRow);
            repTable.appendChild(repThead);
            var repTbody = document.createElement('tbody');
            this._els.repTbody = repTbody;
            repTable.appendChild(repTbody);
            reportsWrap.appendChild(repHeader);
            reportsWrap.appendChild(repTable);

            // Pagination
            var pagination = document.createElement('div');
            pagination.style.cssText = 'display:flex;justify-content:center;gap:8px;margin-top:12px;';
            this._els.pagination = pagination;
            reportsWrap.appendChild(pagination);

            // Domains list
            var domainsWrap = document.createElement('div');
            domainsWrap.className = 'table-container';
            var domHeader = document.createElement('div');
            domHeader.className = 'table-header';
            var domTitle = document.createElement('h2');
            domTitle.textContent = 'Domains with TLS Reports';
            domHeader.appendChild(domTitle);
            var domList = document.createElement('div');
            domList.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;padding:12px;';
            this._els.domainsList = domList;
            domainsWrap.appendChild(domHeader);
            domainsWrap.appendChild(domList);

            var body = document.createElement('div');
            body.className = 'page-body';
            body.appendChild(summary);
            body.appendChild(chartWrap);
            body.appendChild(failWrap);
            body.appendChild(reportsWrap);
            body.appendChild(domainsWrap);

            container.appendChild(header);
            container.appendChild(body);

            this._currentPage = 1;
        },

        load: function() {
            this._loadSummary();
            this._loadFailures();
            this._loadTimeline();
            this._loadReports(1);
            this._loadDomains();
        },

        destroy: function() {
            if (this._chart) {
                this._chart.destroy();
                this._chart = null;
            }
        },

        _loadSummary: function() {
            var self = this;
            fetch('/api/tls-rpt/summary?days=30', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) { self._renderSummary(data); })
                .catch(function() {});
        },

        _renderSummary: function(data) {
            var el = this._els.summary;
            if (!el) return;
            clearElement(el);

            var items = [
                { label: 'Total Reports', value: data.total_reports || 0, cls: '' },
                { label: 'Total Failures', value: data.total_failures || 0, cls: 'stat-card-danger' },
                { label: 'Domains Reporting', value: data.domains_reporting || data.domains || 0, cls: '' },
                { label: 'Failure Rate', value: (data.failure_rate != null ? data.failure_rate.toFixed(1) + '%' : '0%'), cls: data.failure_rate > 5 ? 'stat-card-danger' : '' }
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

        _loadFailures: function() {
            var self = this;
            fetch('/api/tls-rpt/failures?days=30&limit=50', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) { self._renderFailures(Array.isArray(data) ? data : []); })
                .catch(function() {});
        },

        _renderFailures: function(failures) {
            var tbody = this._els.failTbody;
            if (!tbody) return;
            clearElement(tbody);

            if (failures.length === 0) {
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.colSpan = 5;
                td.textContent = 'No TLS failures found.';
                td.style.textAlign = 'center';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            failures.forEach(function(f) {
                var tr = document.createElement('tr');

                var tdDomain = document.createElement('td');
                tdDomain.textContent = f.domain || '-';
                tr.appendChild(tdDomain);

                var tdType = document.createElement('td');
                var typeBadge = document.createElement('span');
                typeBadge.className = 'badge badge-danger';
                typeBadge.textContent = f.failure_type || f.result_type || '-';
                tdType.appendChild(typeBadge);
                tr.appendChild(tdType);

                var tdCount = document.createElement('td');
                tdCount.textContent = f.count || f.failed_session_count || 0;
                tr.appendChild(tdCount);

                var tdSeen = document.createElement('td');
                tdSeen.textContent = f.last_seen ? new Date(f.last_seen).toLocaleString() : '-';
                tr.appendChild(tdSeen);

                var tdDetails = document.createElement('td');
                var detailBtn = document.createElement('button');
                detailBtn.className = 'btn-ghost btn-sm';
                detailBtn.textContent = 'Details';
                detailBtn.addEventListener('click', function() {
                    self._toggleFailureDetail(tr, f);
                });
                tdDetails.appendChild(detailBtn);
                tr.appendChild(tdDetails);

                tbody.appendChild(tr);
            });

            var self = this;
        },

        _toggleFailureDetail: function(row, failure) {
            var next = row.nextElementSibling;
            if (next && next.dataset.detailRow) {
                next.parentNode.removeChild(next);
                return;
            }
            var detailRow = document.createElement('tr');
            detailRow.dataset.detailRow = 'true';
            var td = document.createElement('td');
            td.colSpan = 5;
            td.style.cssText = 'background:var(--bg-tertiary);padding:12px;';

            var details = [
                ['Sending MTA', failure.sending_mta_domain || failure.sending_mta || '-'],
                ['Receiving MTA', failure.receiving_mta || '-'],
                ['Failure Reason', failure.failure_reason || failure.failure_reason_code || '-'],
                ['Additional Info', failure.additional_information || '-']
            ];
            details.forEach(function(pair) {
                var div = document.createElement('div');
                div.style.margin = '4px 0';
                var lbl = document.createElement('strong');
                lbl.textContent = pair[0] + ': ';
                var val = document.createElement('span');
                val.textContent = pair[1];
                div.appendChild(lbl);
                div.appendChild(val);
                td.appendChild(div);
            });

            detailRow.appendChild(td);
            row.parentNode.insertBefore(detailRow, row.nextSibling);
        },

        _loadTimeline: function() {
            var self = this;
            fetch('/api/tls-rpt/timeline?days=30', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) { self._renderTimeline(data); })
                .catch(function() {});
        },

        _renderTimeline: function(data) {
            if (!this._els.canvas || typeof Chart === 'undefined') return;
            if (this._chart) { this._chart.destroy(); this._chart = null; }

            var labels = [];
            var failures = [];
            var items = Array.isArray(data) ? data : (data.timeline || []);

            items.forEach(function(item) {
                labels.push(item.date || item.day || '');
                failures.push(item.failures || item.failure_count || 0);
            });

            var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            var textColor = isDark ? '#ccc' : '#666';
            var gridColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';

            this._chart = new Chart(this._els.canvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'TLS Failures',
                        data: failures,
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231,76,60,0.1)',
                        fill: true,
                        tension: 0.3
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
        },

        _loadReports: function(page) {
            var self = this;
            this._currentPage = page;
            fetch('/api/tls-rpt/reports?page=' + page + '&per_page=20', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var reports = Array.isArray(data) ? data : (data.reports || data.items || []);
                    var total = data.total || reports.length;
                    self._renderReports(reports, total, page);
                })
                .catch(function() { notify('Failed to load TLS reports', 'error'); });
        },

        _renderReports: function(reports, total, page) {
            var self = this;
            var tbody = this._els.repTbody;
            if (!tbody) return;
            clearElement(tbody);

            if (this._els.repCount) {
                this._els.repCount.textContent = total + ' reports';
            }

            if (reports.length === 0) {
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.colSpan = 6;
                td.textContent = 'No TLS-RPT reports found.';
                td.style.textAlign = 'center';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            reports.forEach(function(r) {
                var tr = document.createElement('tr');
                [r.id || '-', r.domain || '-', r.organization || r.org_name || '-',
                 r.date ? new Date(r.date).toLocaleDateString() : '-',
                 r.total_count || r.total || 0,
                 r.failure_count || r.failures || 0
                ].forEach(function(val) {
                    var td = document.createElement('td');
                    td.textContent = val;
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });

            // Pagination
            var pag = this._els.pagination;
            if (pag) {
                clearElement(pag);
                var totalPages = Math.ceil(total / 20) || 1;
                if (totalPages > 1) {
                    for (var i = 1; i <= Math.min(totalPages, 10); i++) {
                        var btn = document.createElement('button');
                        btn.className = i === page ? 'btn-primary btn-sm' : 'btn-ghost btn-sm';
                        btn.textContent = i;
                        btn.addEventListener('click', (function(p) { return function() { self._loadReports(p); }; })(i));
                        pag.appendChild(btn);
                    }
                }
            }
        },

        _loadDomains: function() {
            var self = this;
            fetch('/api/tls-rpt/domains', { headers: getAuthHeaders() })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var domains = Array.isArray(data) ? data : (data.domains || []);
                    self._renderDomainsList(domains);
                })
                .catch(function() {});
        },

        _renderDomainsList: function(domains) {
            var el = this._els.domainsList;
            if (!el) return;
            clearElement(el);

            if (domains.length === 0) {
                var p = document.createElement('p');
                p.textContent = 'No domains with TLS reports.';
                p.style.color = 'var(--text-secondary)';
                el.appendChild(p);
                return;
            }

            domains.forEach(function(d) {
                var tag = document.createElement('span');
                tag.className = 'badge';
                tag.style.cssText = 'font-size:13px;padding:6px 12px;';
                var domain = d.domain || d;
                var count = d.report_count || d.count || '';
                tag.textContent = domain + (count ? ' (' + count + ')' : '');
                el.appendChild(tag);
            });
        }
    };

    window.DMARC = window.DMARC || {};
    window.DMARC.TlsRptPage = TlsRptPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('tls-rpt', TlsRptPage);
    }
})();
