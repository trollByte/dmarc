/**
 * DMARC Dashboard - Forecasting Page Module
 *
 * Displays email volume forecasts with Chart.js, period comparisons,
 * and summary statistics using the forecasting API endpoints.
 */
(function() {
    'use strict';

    var API_BASE = '/api';

    /** Remove all child nodes from an element safely */
    function clearChildren(el) {
        while (el.firstChild) {
            el.removeChild(el.firstChild);
        }
    }

    /** Get theme-aware chart colors */
    function getChartColors() {
        var theme = document.documentElement.getAttribute('data-theme');
        return {
            text: theme === 'dark' ? '#e8e8e8' : '#333333',
            grid: theme === 'dark' ? '#2d4a6f' : '#e0e0e0',
            historical: '#3498db',
            forecast: '#2980b9',
            confidenceBg: 'rgba(52, 152, 219, 0.15)',
            confidenceBorder: 'rgba(52, 152, 219, 0.3)'
        };
    }

    var ForecastingPage = {
        initialized: false,
        containerId: 'page-forecasting',
        forecastChart: null,
        comparisonChart: null,
        lastForecastData: null,

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            this._buildPage(container);
            this._bindEvents(container);
        },

        load: function() {
            this._generateForecast();
            this._loadComparison();
        },

        destroy: function() {
            if (this.forecastChart) {
                this.forecastChart.destroy();
                this.forecastChart = null;
            }
            if (this.comparisonChart) {
                this.comparisonChart.destroy();
                this.comparisonChart = null;
            }
        },

        // ---- Page Structure ----

        _buildPage: function(container) {
            // Header
            var header = document.createElement('div');
            header.className = 'page-header';
            var h1 = document.createElement('h1');
            h1.textContent = 'Forecasting';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Predict future email volumes and compare historical periods.';
            header.appendChild(desc);
            container.appendChild(header);

            // Parameters panel
            var paramsPanel = document.createElement('div');
            paramsPanel.className = 'controls-bar';
            paramsPanel.id = 'forecast-params';

            // Historical days
            var histGroup = document.createElement('div');
            histGroup.className = 'filter-group';
            var histLabel = document.createElement('label');
            histLabel.textContent = 'Historical Period';
            histLabel.setAttribute('for', 'forecast-hist-days');
            histGroup.appendChild(histLabel);
            var histSelect = document.createElement('select');
            histSelect.id = 'forecast-hist-days';
            [{ v: '30', t: '30 days' }, { v: '60', t: '60 days' }, { v: '90', t: '90 days' }].forEach(function(opt) {
                var o = document.createElement('option');
                o.value = opt.v;
                o.textContent = opt.t;
                histSelect.appendChild(o);
            });
            histGroup.appendChild(histSelect);
            paramsPanel.appendChild(histGroup);

            // Forecast days
            var fcGroup = document.createElement('div');
            fcGroup.className = 'filter-group';
            var fcLabel = document.createElement('label');
            fcLabel.textContent = 'Forecast Period';
            fcLabel.setAttribute('for', 'forecast-fc-days');
            fcGroup.appendChild(fcLabel);
            var fcSelect = document.createElement('select');
            fcSelect.id = 'forecast-fc-days';
            [{ v: '7', t: '7 days' }, { v: '14', t: '14 days' }, { v: '30', t: '30 days' }].forEach(function(opt) {
                var o = document.createElement('option');
                o.value = opt.v;
                o.textContent = opt.t;
                if (opt.v === '14') o.selected = true;
                fcSelect.appendChild(o);
            });
            fcGroup.appendChild(fcSelect);
            paramsPanel.appendChild(fcGroup);

            // Generate button
            var genBtn = document.createElement('button');
            genBtn.id = 'forecast-generate-btn';
            genBtn.className = 'btn-primary btn-sm';
            genBtn.textContent = 'Generate Forecast';
            paramsPanel.appendChild(genBtn);

            // Model info display
            var modelInfo = document.createElement('div');
            modelInfo.id = 'forecast-model-info';
            modelInfo.className = 'model-info-badge';
            paramsPanel.appendChild(modelInfo);

            container.appendChild(paramsPanel);

            // Summary stats row
            var summaryRow = document.createElement('div');
            summaryRow.id = 'forecast-summary';
            summaryRow.className = 'stats-grid stats-grid-sm';
            container.appendChild(summaryRow);

            // Forecast chart
            var chartContainer = document.createElement('div');
            chartContainer.className = 'chart-container';
            var chartHeader = document.createElement('div');
            chartHeader.className = 'chart-header';
            var chartTitle = document.createElement('h2');
            chartTitle.textContent = 'Email Volume Forecast';
            chartHeader.appendChild(chartTitle);
            chartContainer.appendChild(chartHeader);
            var canvas = document.createElement('canvas');
            canvas.id = 'forecast-chart';
            chartContainer.appendChild(canvas);
            var chartLoading = document.createElement('div');
            chartLoading.id = 'forecast-chart-loading';
            chartLoading.className = 'loading';
            chartLoading.textContent = 'Generating forecast...';
            chartContainer.appendChild(chartLoading);
            container.appendChild(chartContainer);

            // Period comparison section
            var compSection = document.createElement('div');
            compSection.className = 'comparison-section';
            var compH2 = document.createElement('h2');
            compH2.textContent = 'Period Comparison';
            compSection.appendChild(compH2);

            var compCardsRow = document.createElement('div');
            compCardsRow.id = 'forecast-comparison-cards';
            compCardsRow.className = 'comparison-cards';
            compSection.appendChild(compCardsRow);

            var compChartContainer = document.createElement('div');
            compChartContainer.className = 'chart-container chart-container-sm';
            var compCanvas = document.createElement('canvas');
            compCanvas.id = 'forecast-comparison-chart';
            compChartContainer.appendChild(compCanvas);
            compSection.appendChild(compChartContainer);

            var compLoading = document.createElement('div');
            compLoading.id = 'forecast-comparison-loading';
            compLoading.className = 'loading';
            compLoading.textContent = 'Loading comparison...';
            compSection.appendChild(compLoading);

            container.appendChild(compSection);
        },

        // ---- Events ----

        _bindEvents: function(container) {
            var self = this;

            container.addEventListener('click', function(e) {
                if (e.target.closest('#forecast-generate-btn')) {
                    self._generateForecast();
                    return;
                }
            });
        },

        // ---- Forecast ----

        _generateForecast: function() {
            var self = this;
            var histSelect = document.getElementById('forecast-hist-days');
            var fcSelect = document.getElementById('forecast-fc-days');
            var days = histSelect ? parseInt(histSelect.value, 10) : 30;
            var forecastDays = fcSelect ? parseInt(fcSelect.value, 10) : 14;

            var loading = document.getElementById('forecast-chart-loading');
            var genBtn = document.getElementById('forecast-generate-btn');
            if (loading) loading.hidden = false;
            if (genBtn) {
                genBtn.disabled = true;
                genBtn.textContent = 'Generating...';
            }

            fetch(API_BASE + '/analytics/forecast/volume?history_days=' + days + '&forecast_days=' + forecastDays)
                .then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .then(function(data) {
                    if (loading) loading.hidden = true;
                    self.lastForecastData = data;
                    self._renderForecastChart(data);
                    self._renderModelInfo(data.model_info);
                    self._renderSummaryStats(data);
                })
                .catch(function(err) {
                    if (loading) {
                        loading.hidden = false;
                        loading.textContent = 'Failed to generate forecast: ' + err.message;
                    }
                })
                .finally(function() {
                    if (genBtn) {
                        genBtn.disabled = false;
                        genBtn.textContent = 'Generate Forecast';
                    }
                });
        },

        _renderForecastChart: function(data) {
            var canvas = document.getElementById('forecast-chart');
            if (!canvas) return;
            var ctx = canvas.getContext('2d');
            var colors = getChartColors();

            if (this.forecastChart) {
                this.forecastChart.destroy();
            }

            var historical = data.historical || [];
            var forecast = data.forecast || [];

            // Build combined labels
            var histLabels = historical.map(function(d) { return d.date; });
            var fcLabels = forecast.map(function(d) { return d.date; });
            var allLabels = histLabels.concat(fcLabels);

            // Historical data (solid line)
            var histValues = historical.map(function(d) { return d.value; });
            // Pad forecast region with nulls for historical line
            var histDataset = histValues.concat(forecast.map(function() { return null; }));

            // Forecast data (dashed line), pad historical region
            var fcPadding = historical.map(function() { return null; });
            // Connect: use the last historical value as first forecast point
            if (histValues.length > 0 && forecast.length > 0) {
                fcPadding[fcPadding.length - 1] = histValues[histValues.length - 1];
            }
            var fcValues = forecast.map(function(d) { return d.predicted; });
            var fcDataset = fcPadding.concat(fcValues);

            // Confidence bands
            var upperPadding = historical.map(function() { return null; });
            var lowerPadding = historical.map(function() { return null; });
            if (histValues.length > 0 && forecast.length > 0) {
                upperPadding[upperPadding.length - 1] = histValues[histValues.length - 1];
                lowerPadding[lowerPadding.length - 1] = histValues[histValues.length - 1];
            }
            var upperValues = forecast.map(function(d) { return d.upper_bound; });
            var lowerValues = forecast.map(function(d) { return d.lower_bound; });
            var upperDataset = upperPadding.concat(upperValues);
            var lowerDataset = lowerPadding.concat(lowerValues);

            this.forecastChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: allLabels,
                    datasets: [
                        {
                            label: 'Historical',
                            data: histDataset,
                            borderColor: colors.historical,
                            backgroundColor: 'rgba(52, 152, 219, 0.1)',
                            borderWidth: 2,
                            pointRadius: 1,
                            tension: 0.3,
                            fill: false,
                            spanGaps: false
                        },
                        {
                            label: 'Forecast',
                            data: fcDataset,
                            borderColor: colors.forecast,
                            borderWidth: 2,
                            borderDash: [6, 3],
                            pointRadius: 2,
                            tension: 0.3,
                            fill: false,
                            spanGaps: false
                        },
                        {
                            label: 'Upper Bound',
                            data: upperDataset,
                            borderColor: colors.confidenceBorder,
                            borderWidth: 1,
                            pointRadius: 0,
                            tension: 0.3,
                            fill: '+1',
                            backgroundColor: colors.confidenceBg,
                            spanGaps: false
                        },
                        {
                            label: 'Lower Bound',
                            data: lowerDataset,
                            borderColor: colors.confidenceBorder,
                            borderWidth: 1,
                            pointRadius: 0,
                            tension: 0.3,
                            fill: false,
                            spanGaps: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: {
                                color: colors.text,
                                filter: function(item) {
                                    // Hide upper/lower bound from legend
                                    return item.text !== 'Upper Bound' && item.text !== 'Lower Bound';
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    if (context.dataset.label === 'Upper Bound' || context.dataset.label === 'Lower Bound') {
                                        return context.dataset.label + ': ' + (context.parsed.y != null ? context.parsed.y.toLocaleString() : '-');
                                    }
                                    return context.dataset.label + ': ' + (context.parsed.y != null ? context.parsed.y.toLocaleString() : '-');
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: colors.text, maxTicksLimit: 15 },
                            grid: { color: colors.grid }
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Email Volume',
                                color: colors.text
                            },
                            ticks: {
                                callback: function(value) { return value.toLocaleString(); },
                                color: colors.text
                            },
                            grid: { color: colors.grid }
                        }
                    }
                }
            });
        },

        _renderModelInfo: function(modelInfo) {
            var el = document.getElementById('forecast-model-info');
            if (!el) return;
            clearChildren(el);

            if (!modelInfo) return;

            var typeSpan = document.createElement('span');
            typeSpan.className = 'model-info-type';
            typeSpan.textContent = 'Model: ' + (modelInfo.type || 'Linear');
            el.appendChild(typeSpan);

            if (modelInfo.r2_score != null) {
                var sep = document.createElement('span');
                sep.className = 'model-info-sep';
                sep.textContent = ' | ';
                el.appendChild(sep);

                var r2Span = document.createElement('span');
                r2Span.className = 'model-info-r2';
                r2Span.textContent = 'R\u00B2: ' + modelInfo.r2_score.toFixed(3);
                el.appendChild(r2Span);
            }
        },

        _renderSummaryStats: function(data) {
            var container = document.getElementById('forecast-summary');
            if (!container) return;
            clearChildren(container);

            var forecast = data.forecast || [];
            var historical = data.historical || [];

            // Current trend
            var trendDir = 'Stable';
            if (historical.length >= 2) {
                var recent = historical.slice(-7);
                var first = recent[0] ? recent[0].value : 0;
                var last = recent[recent.length - 1] ? recent[recent.length - 1].value : 0;
                if (last > first * 1.05) trendDir = 'Increasing';
                else if (last < first * 0.95) trendDir = 'Decreasing';
            }

            // Predicted next week volume
            var nextWeek = forecast.slice(0, 7);
            var predictedWeekly = 0;
            nextWeek.forEach(function(d) { predictedWeekly += (d.predicted || 0); });

            // Model confidence from R2
            var confidence = '-';
            if (data.model_info && data.model_info.r2_score != null) {
                var r2 = data.model_info.r2_score;
                if (r2 >= 0.8) confidence = 'High';
                else if (r2 >= 0.5) confidence = 'Medium';
                else confidence = 'Low';
            }

            var stats = [
                { label: 'Current Trend', value: trendDir, cls: trendDir === 'Increasing' ? 'stat-card-danger' : (trendDir === 'Decreasing' ? 'stat-card-success' : '') },
                { label: 'Predicted Next 7 Days', value: predictedWeekly.toLocaleString(), cls: '' },
                { label: 'Model Confidence', value: confidence, cls: confidence === 'High' ? 'stat-card-success' : (confidence === 'Low' ? 'stat-card-danger' : '') }
            ];

            stats.forEach(function(stat) {
                var card = document.createElement('div');
                card.className = 'stat-card ' + stat.cls;
                var cardHeader = document.createElement('div');
                cardHeader.className = 'stat-header';
                var cardLabel = document.createElement('h3');
                cardLabel.textContent = stat.label;
                cardHeader.appendChild(cardLabel);
                card.appendChild(cardHeader);
                var cardContent = document.createElement('div');
                cardContent.className = 'stat-content';
                var cardValue = document.createElement('div');
                cardValue.className = 'stat-value';
                cardValue.textContent = stat.value;
                cardContent.appendChild(cardValue);
                card.appendChild(cardContent);
                container.appendChild(card);
            });
        },

        // ---- Period Comparison ----

        _loadComparison: function() {
            var self = this;
            var loading = document.getElementById('forecast-comparison-loading');
            if (loading) loading.hidden = false;

            fetch(API_BASE + '/analytics/forecast/summary')
                .then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .then(function(data) {
                    if (loading) loading.hidden = true;
                    // Adapt forecast/summary response to comparison card format
                    var summary = data.summary || {};
                    var compData = {
                        period1: {
                            avg: summary.historical_avg_volume,
                            total: summary.historical_avg_volume ? summary.historical_avg_volume * 7 : null,
                            trend: 'historical'
                        },
                        period2: {
                            avg: summary.avg_predicted_volume,
                            total: summary.avg_predicted_volume ? summary.avg_predicted_volume * 7 : null,
                            trend: summary.trend || 'unknown'
                        },
                        change_pct: summary.volume_change_percent
                    };
                    self._renderComparisonCards(compData);
                    self._renderComparisonChart(compData);
                })
                .catch(function(err) {
                    if (loading) {
                        loading.hidden = false;
                        loading.textContent = 'Failed to load comparison: ' + err.message;
                    }
                });
        },

        _renderComparisonCards: function(data) {
            var container = document.getElementById('forecast-comparison-cards');
            if (!container) return;
            clearChildren(container);

            var p1 = data.period1 || {};
            var p2 = data.period2 || {};
            var changePct = data.change_pct;

            // Period 1 card
            var card1 = this._createPeriodCard('Previous Period', p1);
            container.appendChild(card1);

            // Change indicator
            var changeCard = document.createElement('div');
            changeCard.className = 'comparison-change-card';
            var changeLabel = document.createElement('div');
            changeLabel.className = 'change-label';
            changeLabel.textContent = 'Change';
            changeCard.appendChild(changeLabel);
            var changeValue = document.createElement('div');
            changeValue.className = 'change-value';
            if (changePct != null) {
                var sign = changePct >= 0 ? '+' : '';
                changeValue.textContent = sign + changePct.toFixed(1) + '%';
                if (changePct >= 0) {
                    changeValue.classList.add('change-positive');
                } else {
                    changeValue.classList.add('change-negative');
                }
            } else {
                changeValue.textContent = '-';
            }
            changeCard.appendChild(changeValue);
            var changeArrow = document.createElement('div');
            changeArrow.className = 'change-arrow';
            if (changePct != null) {
                changeArrow.textContent = changePct >= 0 ? '\u2191' : '\u2193';
                changeArrow.classList.add(changePct >= 0 ? 'change-positive' : 'change-negative');
            }
            changeCard.appendChild(changeArrow);
            container.appendChild(changeCard);

            // Period 2 card
            var card2 = this._createPeriodCard('Current Period', p2);
            container.appendChild(card2);
        },

        _createPeriodCard: function(title, period) {
            var card = document.createElement('div');
            card.className = 'comparison-period-card';

            var cardTitle = document.createElement('h4');
            cardTitle.textContent = title;
            card.appendChild(cardTitle);

            var dateRange = document.createElement('p');
            dateRange.className = 'period-dates';
            if (period.start && period.end) {
                var startDate = new Date(period.start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                var endDate = new Date(period.end).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                dateRange.textContent = startDate + ' - ' + endDate;
            }
            card.appendChild(dateRange);

            var dl = document.createElement('dl');
            dl.className = 'detail-list';

            var items = [
                ['Avg Volume', period.avg != null ? Math.round(period.avg).toLocaleString() : '-'],
                ['Total Volume', period.total != null ? period.total.toLocaleString() : '-'],
                ['Trend', period.trend || '-']
            ];
            items.forEach(function(pair) {
                var dt = document.createElement('dt');
                dt.textContent = pair[0];
                dl.appendChild(dt);
                var dd = document.createElement('dd');
                dd.textContent = pair[1];
                dl.appendChild(dd);
            });
            card.appendChild(dl);

            return card;
        },

        _renderComparisonChart: function(data) {
            var canvas = document.getElementById('forecast-comparison-chart');
            if (!canvas) return;
            var ctx = canvas.getContext('2d');
            var colors = getChartColors();

            if (this.comparisonChart) {
                this.comparisonChart.destroy();
            }

            var p1 = data.period1 || {};
            var p2 = data.period2 || {};

            this.comparisonChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['Avg Volume', 'Total Volume'],
                    datasets: [
                        {
                            label: 'Previous Period',
                            data: [p1.avg || 0, p1.total || 0],
                            backgroundColor: 'rgba(52, 152, 219, 0.6)',
                            borderColor: '#3498db',
                            borderWidth: 1
                        },
                        {
                            label: 'Current Period',
                            data: [p2.avg || 0, p2.total || 0],
                            backgroundColor: 'rgba(46, 204, 113, 0.6)',
                            borderColor: '#2ecc71',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { color: colors.text }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + context.parsed.y.toLocaleString();
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: colors.text },
                            grid: { color: colors.grid }
                        },
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) { return value.toLocaleString(); },
                                color: colors.text
                            },
                            grid: { color: colors.grid }
                        }
                    }
                }
            });
        }
    };

    // Expose and register
    window.DMARC = window.DMARC || {};
    window.DMARC.ForecastingPage = ForecastingPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('forecasting', ForecastingPage);
    }
})();
