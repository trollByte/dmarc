/**
 * DMARC Dashboard - Health Scores Page Module
 *
 * Displays domain health grades, score cards, historical trends,
 * and a sortable comparison table. Clicking a domain card navigates
 * to the Policy Advisor page filtered to that domain.
 */
(function() {
    'use strict';

    var API_BASE = '/api';

    // Grade color mapping
    var GRADE_COLORS = {
        A: '#27ae60',
        B: '#6bcb77',
        C: '#f39c12',
        D: '#e67e22',
        F: '#e74c3c'
    };

    var GRADE_BG_COLORS = {
        A: 'rgba(39, 174, 96, 0.15)',
        B: 'rgba(107, 203, 119, 0.15)',
        C: 'rgba(243, 156, 18, 0.15)',
        D: 'rgba(230, 126, 34, 0.15)',
        F: 'rgba(231, 76, 60, 0.15)'
    };

    var POLICY_LABELS = {
        none: 'None',
        quarantine: 'Quarantine',
        reject: 'Reject'
    };

    var HealthPage = {
        initialized: false,
        containerId: 'page-health',
        historicalChart: null,
        comparisonData: [],
        sortColumn: 'score',
        sortDirection: 'desc',

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
            h1.textContent = 'Health Scores';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Monitor authentication health grades across all your domains.';
            header.appendChild(desc);
            container.appendChild(header);

            // Controls row
            var controls = document.createElement('div');
            controls.className = 'health-controls';
            controls.style.cssText = 'display:flex;align-items:center;gap:12px;margin-bottom:20px;flex-wrap:wrap;';

            var daysLabel = document.createElement('label');
            daysLabel.textContent = 'Period: ';
            daysLabel.setAttribute('for', 'healthDaysSelect');
            daysLabel.style.cssText = 'color:var(--text-secondary);font-size:0.85rem;font-weight:600;';
            controls.appendChild(daysLabel);

            var daysSelect = document.createElement('select');
            daysSelect.id = 'healthDaysSelect';
            daysSelect.style.cssText = 'padding:6px 10px;border-radius:6px;border:1px solid var(--border-color);background:var(--input-bg);color:var(--text-primary);font-size:0.85rem;';
            var daysOptions = [
                { value: '7', text: 'Last 7 days' },
                { value: '30', text: 'Last 30 days' },
                { value: '90', text: 'Last 90 days' }
            ];
            daysOptions.forEach(function(opt) {
                var option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.text;
                if (opt.value === '30') option.selected = true;
                daysSelect.appendChild(option);
            });
            controls.appendChild(daysSelect);

            var refreshBtn = document.createElement('button');
            refreshBtn.className = 'btn-secondary btn-sm';
            refreshBtn.id = 'healthRefreshBtn';
            refreshBtn.textContent = 'Refresh';
            controls.appendChild(refreshBtn);

            container.appendChild(controls);

            // Summary stats row
            var summarySection = document.createElement('section');
            summarySection.className = 'stats-section';
            summarySection.setAttribute('aria-label', 'Health summary');
            var summaryGrid = document.createElement('div');
            summaryGrid.className = 'stats-grid';
            summaryGrid.id = 'healthSummaryGrid';
            summaryGrid.style.cssText = 'grid-template-columns:repeat(6,1fr);';
            summarySection.appendChild(summaryGrid);
            container.appendChild(summarySection);

            // Domain health cards grid
            var cardsHeader = document.createElement('h2');
            cardsHeader.textContent = 'Domain Health';
            cardsHeader.style.cssText = 'margin:24px 0 12px;color:var(--text-heading);font-size:1.1rem;';
            container.appendChild(cardsHeader);

            var cardsGrid = document.createElement('div');
            cardsGrid.id = 'healthCardsGrid';
            cardsGrid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-bottom:24px;';
            container.appendChild(cardsGrid);

            // Historical trend chart
            var chartSection = document.createElement('div');
            chartSection.className = 'chart-container';
            chartSection.style.marginBottom = '24px';
            var chartHeader = document.createElement('div');
            chartHeader.className = 'chart-header';
            var chartTitle = document.createElement('h2');
            chartTitle.textContent = 'Score History';
            chartHeader.appendChild(chartTitle);
            var chartHint = document.createElement('span');
            chartHint.className = 'chart-hint';
            chartHint.textContent = 'Top domains over time';
            chartHeader.appendChild(chartHint);
            chartSection.appendChild(chartHeader);
            var canvas = document.createElement('canvas');
            canvas.id = 'healthHistoricalChart';
            chartSection.appendChild(canvas);
            container.appendChild(chartSection);

            // Comparison table
            var tableSection = document.createElement('div');
            tableSection.className = 'table-section';
            var tableHeader = document.createElement('div');
            tableHeader.className = 'table-header';
            var tableTitle = document.createElement('h2');
            tableTitle.textContent = 'Domain Comparison';
            tableHeader.appendChild(tableTitle);
            tableSection.appendChild(tableHeader);

            var table = document.createElement('table');
            table.id = 'healthComparisonTable';
            table.setAttribute('aria-label', 'Domain health comparison');

            var thead = document.createElement('thead');
            var headerRow = document.createElement('tr');
            var columns = [
                { key: 'domain', label: 'Domain' },
                { key: 'grade', label: 'Grade' },
                { key: 'score', label: 'Score' },
                { key: 'pass_rate', label: 'Pass Rate' },
                { key: 'policy', label: 'Policy' },
                { key: 'trend', label: 'Trend' }
            ];
            var self = this;
            columns.forEach(function(col) {
                var th = document.createElement('th');
                th.setAttribute('scope', 'col');
                th.setAttribute('data-sort', col.key);
                th.className = 'sortable';
                th.style.cursor = 'pointer';
                th.textContent = col.label;
                th.addEventListener('click', function() {
                    self._sortTable(col.key);
                });
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);

            var tbody = document.createElement('tbody');
            tbody.id = 'healthComparisonBody';
            table.appendChild(tbody);

            tableSection.appendChild(table);
            container.appendChild(tableSection);
        },

        _bindEvents: function(container) {
            var self = this;
            var daysSelect = container.querySelector('#healthDaysSelect');
            if (daysSelect) {
                daysSelect.addEventListener('change', function() {
                    self.load();
                });
            }
            var refreshBtn = container.querySelector('#healthRefreshBtn');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', function() {
                    self.load();
                });
            }
        },

        load: function() {
            var self = this;
            var daysSelect = document.getElementById('healthDaysSelect');
            var days = daysSelect ? daysSelect.value : '30';

            // Show loading states
            this._showLoading();

            // Fetch domain health data and overall health in parallel
            Promise.all([
                fetch(API_BASE + '/advisor/domains?days=' + days).then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                }),
                fetch(API_BASE + '/advisor/health?days=' + days).then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
            ]).then(function(results) {
                var domainsResp = results[0];
                var historical = results[1];
                var domains = domainsResp && Array.isArray(domainsResp.domains) ? domainsResp.domains : (Array.isArray(domainsResp) ? domainsResp : []);
                self.comparisonData = domains;
                self._renderSummary(self.comparisonData);
                self._renderCards(self.comparisonData);
                self._renderHistoricalChart(historical);
                self._renderComparisonTable(self.comparisonData);
            }).catch(function(err) {
                console.error('Error loading health data:', err);
                var DMARC = window.DMARC;
                if (DMARC && DMARC.showNotification) {
                    DMARC.showNotification('Failed to load health scores', 'error');
                }
            });
        },

        _showLoading: function() {
            var cardsGrid = document.getElementById('healthCardsGrid');
            if (cardsGrid) cardsGrid.textContent = 'Loading...';
            var tbody = document.getElementById('healthComparisonBody');
            if (tbody) {
                tbody.textContent = '';
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.setAttribute('colspan', '6');
                td.className = 'loading';
                td.textContent = 'Loading health data...';
                tr.appendChild(td);
                tbody.appendChild(tr);
            }
        },

        _renderSummary: function(data) {
            var grid = document.getElementById('healthSummaryGrid');
            if (!grid) return;
            grid.textContent = '';

            // Count grades
            var gradeCounts = { A: 0, B: 0, C: 0, D: 0, F: 0 };
            var totalScore = 0;
            data.forEach(function(d) {
                var grade = (d.grade || 'F').toUpperCase();
                if (gradeCounts.hasOwnProperty(grade)) {
                    gradeCounts[grade]++;
                }
                totalScore += (d.overall_score || 0);
            });
            var avgScore = data.length > 0 ? Math.round(totalScore / data.length) : 0;

            // Grade summary cards
            var grades = ['A', 'B', 'C', 'D', 'F'];
            grades.forEach(function(grade) {
                var card = document.createElement('div');
                card.className = 'stat-card';
                card.style.borderLeft = '4px solid ' + GRADE_COLORS[grade];

                var header = document.createElement('div');
                header.className = 'stat-header';
                var h3 = document.createElement('h3');
                h3.textContent = 'Grade ' + grade;
                header.appendChild(h3);
                card.appendChild(header);

                var content = document.createElement('div');
                content.className = 'stat-content';
                var value = document.createElement('div');
                value.className = 'stat-value';
                value.textContent = gradeCounts[grade];
                value.style.color = GRADE_COLORS[grade];
                content.appendChild(value);
                card.appendChild(content);

                grid.appendChild(card);
            });

            // Average score card
            var avgCard = document.createElement('div');
            avgCard.className = 'stat-card';
            avgCard.style.borderLeft = '4px solid var(--accent-primary)';

            var avgHeader = document.createElement('div');
            avgHeader.className = 'stat-header';
            var avgH3 = document.createElement('h3');
            avgH3.textContent = 'Avg Score';
            avgHeader.appendChild(avgH3);
            avgCard.appendChild(avgHeader);

            var avgContent = document.createElement('div');
            avgContent.className = 'stat-content';
            var avgValue = document.createElement('div');
            avgValue.className = 'stat-value';
            avgValue.textContent = avgScore;
            avgContent.appendChild(avgValue);
            avgCard.appendChild(avgContent);

            grid.appendChild(avgCard);
        },

        _renderCards: function(data) {
            var cardsGrid = document.getElementById('healthCardsGrid');
            if (!cardsGrid) return;
            cardsGrid.textContent = '';

            if (data.length === 0) {
                var empty = document.createElement('div');
                empty.style.cssText = 'grid-column:1/-1;text-align:center;padding:40px;color:var(--text-secondary);';
                empty.textContent = 'No domain health data available. Import DMARC reports to see health scores.';
                cardsGrid.appendChild(empty);
                return;
            }

            var self = this;
            data.forEach(function(d) {
                var card = self._createDomainCard(d);
                cardsGrid.appendChild(card);
            });
        },

        _createDomainCard: function(d) {
            var grade = (d.grade || 'F').toUpperCase();
            var color = GRADE_COLORS[grade] || GRADE_COLORS.F;
            var bgColor = GRADE_BG_COLORS[grade] || GRADE_BG_COLORS.F;

            var card = document.createElement('div');
            card.className = 'stat-card';
            card.style.cssText = 'cursor:pointer;position:relative;';
            card.setAttribute('role', 'button');
            card.setAttribute('tabindex', '0');
            card.setAttribute('aria-label', 'View advisor for ' + (d.domain || 'unknown'));

            // Click navigates to advisor with domain filter
            var domain = d.domain;
            card.addEventListener('click', function() {
                window.DMARC._healthSelectedDomain = domain;
                if (window.DMARC.Router) {
                    window.DMARC.Router.navigate('advisor');
                }
            });
            card.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    card.click();
                }
            });

            // Top row: domain name + trend
            var topRow = document.createElement('div');
            topRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;';

            var domainEl = document.createElement('span');
            domainEl.style.cssText = 'font-weight:600;color:var(--text-heading);font-size:0.95rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:70%;';
            domainEl.textContent = d.domain || 'Unknown';
            domainEl.title = d.domain || '';
            topRow.appendChild(domainEl);

            var trendEl = document.createElement('span');
            trendEl.style.cssText = 'font-size:1.1rem;';
            var trend = d.trend || 'flat';
            if (trend === 'up' || trend === 'improving') {
                trendEl.textContent = '\u2191';
                trendEl.style.color = '#27ae60';
                trendEl.title = 'Improving';
            } else if (trend === 'down' || trend === 'declining') {
                trendEl.textContent = '\u2193';
                trendEl.style.color = '#e74c3c';
                trendEl.title = 'Declining';
            } else {
                trendEl.textContent = '\u2192';
                trendEl.style.color = 'var(--text-secondary)';
                trendEl.title = 'Stable';
            }
            topRow.appendChild(trendEl);
            card.appendChild(topRow);

            // Center: grade circle + score
            var center = document.createElement('div');
            center.style.cssText = 'display:flex;align-items:center;gap:16px;margin-bottom:12px;';

            var gradeCircle = document.createElement('div');
            gradeCircle.style.cssText = 'width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.5rem;font-weight:700;flex-shrink:0;background:' + bgColor + ';color:' + color + ';border:2px solid ' + color + ';';
            gradeCircle.textContent = grade;
            center.appendChild(gradeCircle);

            var scoreBlock = document.createElement('div');
            var scoreValue = document.createElement('div');
            scoreValue.style.cssText = 'font-size:1.6rem;font-weight:700;color:var(--text-heading);line-height:1.2;';
            scoreValue.textContent = (d.overall_score != null ? d.overall_score : '?');
            scoreBlock.appendChild(scoreValue);
            var scoreSuffix = document.createElement('div');
            scoreSuffix.style.cssText = 'font-size:0.75rem;color:var(--text-secondary);';
            scoreSuffix.textContent = '/ 100';
            scoreBlock.appendChild(scoreSuffix);
            center.appendChild(scoreBlock);

            card.appendChild(center);

            // Pass rate bar
            var passRate = d.pass_rate != null ? d.pass_rate : 0;
            var barOuter = document.createElement('div');
            barOuter.style.cssText = 'height:6px;border-radius:3px;background:var(--bg-tertiary);margin-bottom:8px;overflow:hidden;';
            var barInner = document.createElement('div');
            var barColor = passRate >= 90 ? '#27ae60' : passRate >= 70 ? '#f39c12' : '#e74c3c';
            barInner.style.cssText = 'height:100%;border-radius:3px;transition:width 0.4s;background:' + barColor + ';width:' + passRate + '%;';
            barOuter.appendChild(barInner);
            card.appendChild(barOuter);

            var barLabel = document.createElement('div');
            barLabel.style.cssText = 'display:flex;justify-content:space-between;font-size:0.75rem;color:var(--text-secondary);';
            var barText = document.createElement('span');
            barText.textContent = 'Pass rate';
            barLabel.appendChild(barText);
            var barPct = document.createElement('span');
            barPct.textContent = passRate.toFixed(1) + '%';
            barPct.style.fontWeight = '600';
            barLabel.appendChild(barPct);
            card.appendChild(barLabel);

            // Policy badge
            var policyRow = document.createElement('div');
            policyRow.style.cssText = 'margin-top:10px;';
            var policyBadge = document.createElement('span');
            policyBadge.className = 'badge';
            var policyText = d.policy || d.current_policy || 'none';
            policyBadge.textContent = POLICY_LABELS[policyText] || policyText;
            if (policyText === 'reject') {
                policyBadge.classList.add('badge-success');
            } else if (policyText === 'quarantine') {
                policyBadge.classList.add('badge-warning');
            } else {
                policyBadge.classList.add('badge-gray');
            }
            policyRow.appendChild(policyBadge);
            card.appendChild(policyRow);

            return card;
        },

        _renderHistoricalChart: function(historical) {
            var canvas = document.getElementById('healthHistoricalChart');
            if (!canvas) return;

            if (this.historicalChart) {
                this.historicalChart.destroy();
                this.historicalChart = null;
            }

            var dataArr = Array.isArray(historical) ? historical : [];
            if (dataArr.length === 0) return;

            // Collect unique domains and pick top 5 by latest score
            var domainLatest = {};
            dataArr.forEach(function(entry) {
                var domains = entry.domains || [];
                domains.forEach(function(dEntry) {
                    domainLatest[dEntry.domain] = dEntry.score || 0;
                });
            });

            var topDomains = Object.keys(domainLatest)
                .sort(function(a, b) { return domainLatest[b] - domainLatest[a]; })
                .slice(0, 5);

            if (topDomains.length === 0) return;

            var labels = dataArr.map(function(entry) { return entry.date; });
            var palette = ['#3498db', '#27ae60', '#f39c12', '#e74c3c', '#9b59b6'];

            var datasets = topDomains.map(function(domain, idx) {
                var scores = dataArr.map(function(entry) {
                    var found = (entry.domains || []).find(function(d) { return d.domain === domain; });
                    return found ? found.score : null;
                });
                return {
                    label: domain,
                    data: scores,
                    borderColor: palette[idx % palette.length],
                    backgroundColor: 'transparent',
                    tension: 0.4,
                    spanGaps: true,
                    pointRadius: 2
                };
            });

            var theme = document.documentElement.getAttribute('data-theme');
            var textColor = theme === 'dark' ? '#e8e8e8' : '#333333';
            var gridColor = theme === 'dark' ? '#2d4a6f' : '#e0e0e0';

            var ctx = canvas.getContext('2d');
            this.historicalChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { color: textColor }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: textColor, maxTicksLimit: 10 },
                            grid: { color: gridColor }
                        },
                        y: {
                            min: 0,
                            max: 100,
                            ticks: { color: textColor },
                            grid: { color: gridColor }
                        }
                    }
                }
            });
        },

        _renderComparisonTable: function(data) {
            var tbody = document.getElementById('healthComparisonBody');
            if (!tbody) return;
            tbody.textContent = '';

            if (data.length === 0) {
                var tr = document.createElement('tr');
                var td = document.createElement('td');
                td.setAttribute('colspan', '6');
                td.style.cssText = 'text-align:center;padding:24px;color:var(--text-secondary);';
                td.textContent = 'No domain data available.';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            // Sort
            var sorted = data.slice().sort(this._getSortFn());

            var self = this;
            sorted.forEach(function(d) {
                var tr = document.createElement('tr');
                tr.style.cursor = 'pointer';
                tr.addEventListener('click', function() {
                    window.DMARC._healthSelectedDomain = d.domain;
                    if (window.DMARC.Router) {
                        window.DMARC.Router.navigate('advisor');
                    }
                });

                // Domain
                var tdDomain = document.createElement('td');
                tdDomain.textContent = d.domain || '';
                tdDomain.style.fontWeight = '600';
                tr.appendChild(tdDomain);

                // Grade
                var tdGrade = document.createElement('td');
                var grade = (d.grade || 'F').toUpperCase();
                var gradeBadge = document.createElement('span');
                gradeBadge.className = 'badge';
                gradeBadge.textContent = grade;
                gradeBadge.style.cssText = 'background:' + (GRADE_BG_COLORS[grade] || GRADE_BG_COLORS.F) + ';color:' + (GRADE_COLORS[grade] || GRADE_COLORS.F) + ';font-weight:700;';
                tdGrade.appendChild(gradeBadge);
                tr.appendChild(tdGrade);

                // Score
                var tdScore = document.createElement('td');
                tdScore.textContent = d.overall_score != null ? d.overall_score : '-';
                tr.appendChild(tdScore);

                // Pass rate
                var tdPass = document.createElement('td');
                var pr = d.pass_rate != null ? d.pass_rate.toFixed(1) + '%' : '-';
                tdPass.textContent = pr;
                tr.appendChild(tdPass);

                // Policy
                var tdPolicy = document.createElement('td');
                var policyBadge = document.createElement('span');
                policyBadge.className = 'badge';
                var policyVal = d.policy || 'none';
                policyBadge.textContent = POLICY_LABELS[policyVal] || policyVal;
                if (policyVal === 'reject') {
                    policyBadge.classList.add('badge-success');
                } else if (policyVal === 'quarantine') {
                    policyBadge.classList.add('badge-warning');
                } else {
                    policyBadge.classList.add('badge-gray');
                }
                tdPolicy.appendChild(policyBadge);
                tr.appendChild(tdPolicy);

                // Trend
                var tdTrend = document.createElement('td');
                var trend = d.trend || 'flat';
                if (trend === 'up' || trend === 'improving') {
                    tdTrend.textContent = '\u2191 Improving';
                    tdTrend.style.color = '#27ae60';
                } else if (trend === 'down' || trend === 'declining') {
                    tdTrend.textContent = '\u2193 Declining';
                    tdTrend.style.color = '#e74c3c';
                } else {
                    tdTrend.textContent = '\u2192 Stable';
                    tdTrend.style.color = 'var(--text-secondary)';
                }
                tr.appendChild(tdTrend);

                tbody.appendChild(tr);
            });

            // Update sort indicators
            self._updateSortIndicators();
        },

        _sortTable: function(column) {
            if (this.sortColumn === column) {
                this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                this.sortColumn = column;
                this.sortDirection = column === 'domain' ? 'asc' : 'desc';
            }
            this._renderComparisonTable(this.comparisonData);
        },

        _getSortFn: function() {
            var col = this.sortColumn;
            var dir = this.sortDirection === 'asc' ? 1 : -1;
            return function(a, b) {
                var va, vb;
                if (col === 'domain') {
                    va = (a.domain || '').toLowerCase();
                    vb = (b.domain || '').toLowerCase();
                    return va < vb ? -dir : va > vb ? dir : 0;
                } else if (col === 'grade') {
                    var gradeOrder = { A: 5, B: 4, C: 3, D: 2, F: 1 };
                    va = gradeOrder[(a.grade || 'F').toUpperCase()] || 0;
                    vb = gradeOrder[(b.grade || 'F').toUpperCase()] || 0;
                } else if (col === 'score') {
                    va = a.overall_score || 0;
                    vb = b.overall_score || 0;
                } else if (col === 'pass_rate') {
                    va = a.pass_rate || 0;
                    vb = b.pass_rate || 0;
                } else if (col === 'policy') {
                    var policyOrder = { reject: 3, quarantine: 2, none: 1 };
                    va = policyOrder[a.policy] || 0;
                    vb = policyOrder[b.policy] || 0;
                } else if (col === 'trend') {
                    var trendOrder = { up: 3, improving: 3, flat: 2, stable: 2, down: 1, declining: 1 };
                    va = trendOrder[a.trend] || 2;
                    vb = trendOrder[b.trend] || 2;
                } else {
                    va = 0; vb = 0;
                }
                return (va - vb) * dir;
            };
        },

        _updateSortIndicators: function() {
            var table = document.getElementById('healthComparisonTable');
            if (!table) return;
            var ths = table.querySelectorAll('thead th[data-sort]');
            var self = this;
            ths.forEach(function(th) {
                th.setAttribute('aria-sort', 'none');
                th.style.textDecoration = '';
                if (th.getAttribute('data-sort') === self.sortColumn) {
                    th.setAttribute('aria-sort', self.sortDirection === 'asc' ? 'ascending' : 'descending');
                    th.style.textDecoration = 'underline';
                }
            });
        },

        destroy: function() {
            if (this.historicalChart) {
                this.historicalChart.destroy();
                this.historicalChart = null;
            }
        }
    };

    // Expose and register
    window.DMARC = window.DMARC || {};
    window.DMARC.HealthPage = HealthPage;
    if (window.DMARC.Router) {
        window.DMARC.Router.register('health', HealthPage);
    }
})();
