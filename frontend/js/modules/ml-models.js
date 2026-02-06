/**
 * DMARC Dashboard - ML Models & Anomaly Detection Page Module
 *
 * Tabbed layout: Models | Anomalies
 * Models tab: list, train, deploy, detail panel
 * Anomalies tab: run detection, recent anomalies, feedback
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

    var MLModelsPage = {
        initialized: false,
        containerId: 'page-ml-models',
        activeTab: 'models',
        selectedModelId: null,
        selectedAnomalyIdx: null,
        anomalyResults: [],
        refreshInterval: null,

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            this._buildPage(container);
            this._bindEvents(container);
        },

        load: function() {
            if (this.activeTab === 'models') {
                this._loadModels();
            } else {
                this._loadRecentAnomalies();
            }
        },

        destroy: function() {
            if (this.refreshInterval) {
                clearInterval(this.refreshInterval);
                this.refreshInterval = null;
            }
        },

        // ---- Page Structure ----

        _buildPage: function(container) {
            // Header
            var header = document.createElement('div');
            header.className = 'page-header';
            var h1 = document.createElement('h1');
            h1.textContent = 'ML Models & Anomaly Detection';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Manage machine learning models and detect anomalous email sending patterns.';
            header.appendChild(desc);
            container.appendChild(header);

            // Tabs
            var tabBar = document.createElement('div');
            tabBar.className = 'tab-bar';
            tabBar.setAttribute('role', 'tablist');

            var modelsTab = document.createElement('button');
            modelsTab.className = 'tab-btn active';
            modelsTab.setAttribute('role', 'tab');
            modelsTab.setAttribute('aria-selected', 'true');
            modelsTab.setAttribute('data-tab', 'models');
            modelsTab.textContent = 'Models';

            var anomaliesTab = document.createElement('button');
            anomaliesTab.className = 'tab-btn';
            anomaliesTab.setAttribute('role', 'tab');
            anomaliesTab.setAttribute('aria-selected', 'false');
            anomaliesTab.setAttribute('data-tab', 'anomalies');
            anomaliesTab.textContent = 'Anomalies';

            tabBar.appendChild(modelsTab);
            tabBar.appendChild(anomaliesTab);
            container.appendChild(tabBar);

            // Tab panels
            var modelsPanel = document.createElement('div');
            modelsPanel.id = 'ml-tab-models';
            modelsPanel.className = 'tab-panel-content';
            modelsPanel.setAttribute('role', 'tabpanel');
            this._buildModelsPanel(modelsPanel);
            container.appendChild(modelsPanel);

            var anomaliesPanel = document.createElement('div');
            anomaliesPanel.id = 'ml-tab-anomalies';
            anomaliesPanel.className = 'tab-panel-content';
            anomaliesPanel.setAttribute('role', 'tabpanel');
            anomaliesPanel.hidden = true;
            this._buildAnomaliesPanel(anomaliesPanel);
            container.appendChild(anomaliesPanel);

            // Model detail side panel
            var detailPanel = document.createElement('div');
            detailPanel.id = 'ml-model-detail';
            detailPanel.className = 'detail-panel';
            detailPanel.hidden = true;
            container.appendChild(detailPanel);

            // Anomaly detail side panel
            var anomalyDetail = document.createElement('div');
            anomalyDetail.id = 'ml-anomaly-detail';
            anomalyDetail.className = 'detail-panel';
            anomalyDetail.hidden = true;
            container.appendChild(anomalyDetail);
        },

        _buildModelsPanel: function(panel) {
            // Actions bar
            var actionsBar = document.createElement('div');
            actionsBar.className = 'section-actions';

            var trainBtn = document.createElement('button');
            trainBtn.id = 'ml-train-btn';
            trainBtn.className = 'btn-primary btn-sm';
            trainBtn.textContent = 'Train New Model';
            actionsBar.appendChild(trainBtn);

            panel.appendChild(actionsBar);

            // Models table
            var tableWrap = document.createElement('div');
            tableWrap.className = 'table-container';
            var table = document.createElement('table');
            table.id = 'ml-models-table';
            table.className = 'data-table';
            var thead = document.createElement('thead');
            var headerRow = document.createElement('tr');
            ['', 'Version', 'Type', 'Accuracy', 'Samples', 'Features', 'Status', 'Created', 'Actions'].forEach(function(text) {
                var th = document.createElement('th');
                th.setAttribute('scope', 'col');
                th.textContent = text;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);
            var tbody = document.createElement('tbody');
            tbody.id = 'ml-models-tbody';
            table.appendChild(tbody);
            tableWrap.appendChild(table);
            panel.appendChild(tableWrap);

            // Loading state
            var loading = document.createElement('div');
            loading.id = 'ml-models-loading';
            loading.className = 'loading';
            loading.textContent = 'Loading models...';
            panel.appendChild(loading);
        },

        _buildAnomaliesPanel: function(panel) {
            // Detection controls
            var controls = document.createElement('div');
            controls.className = 'controls-bar';

            // Days selector
            var daysGroup = document.createElement('div');
            daysGroup.className = 'filter-group';
            var daysLabel = document.createElement('label');
            daysLabel.textContent = 'Analysis Period';
            daysLabel.setAttribute('for', 'anomaly-days');
            daysGroup.appendChild(daysLabel);
            var daysSelect = document.createElement('select');
            daysSelect.id = 'anomaly-days';
            [{ v: '7', t: '7 days' }, { v: '14', t: '14 days' }, { v: '30', t: '30 days' }].forEach(function(opt) {
                var o = document.createElement('option');
                o.value = opt.v;
                o.textContent = opt.t;
                daysSelect.appendChild(o);
            });
            daysGroup.appendChild(daysSelect);
            controls.appendChild(daysGroup);

            // Threshold slider
            var threshGroup = document.createElement('div');
            threshGroup.className = 'filter-group';
            var threshLabel = document.createElement('label');
            threshLabel.textContent = 'Threshold';
            threshLabel.setAttribute('for', 'anomaly-threshold');
            threshGroup.appendChild(threshLabel);
            var threshWrap = document.createElement('div');
            threshWrap.className = 'slider-wrap';
            var threshInput = document.createElement('input');
            threshInput.type = 'range';
            threshInput.id = 'anomaly-threshold';
            threshInput.min = '-0.9';
            threshInput.max = '-0.3';
            threshInput.step = '0.1';
            threshInput.value = '-0.5';
            var threshValue = document.createElement('span');
            threshValue.id = 'anomaly-threshold-value';
            threshValue.className = 'slider-value';
            threshValue.textContent = '-0.5';
            threshWrap.appendChild(threshInput);
            threshWrap.appendChild(threshValue);
            threshGroup.appendChild(threshWrap);
            controls.appendChild(threshGroup);

            var detectBtn = document.createElement('button');
            detectBtn.id = 'anomaly-detect-btn';
            detectBtn.className = 'btn-primary btn-sm';
            detectBtn.textContent = 'Run Detection';
            controls.appendChild(detectBtn);

            panel.appendChild(controls);

            // Recent anomalies heading
            var recentHeading = document.createElement('h3');
            recentHeading.className = 'section-subtitle';
            recentHeading.textContent = 'Recent Anomalies';
            panel.appendChild(recentHeading);

            // Anomalies table
            var tableWrap = document.createElement('div');
            tableWrap.className = 'table-container';
            var table = document.createElement('table');
            table.id = 'ml-anomalies-table';
            table.className = 'data-table';
            var thead = document.createElement('thead');
            var headerRow = document.createElement('tr');
            ['IP Address', 'Anomaly Score', 'Volume', 'Failure Rate', 'Unique Domains', 'Prediction', 'Actions'].forEach(function(text) {
                var th = document.createElement('th');
                th.setAttribute('scope', 'col');
                th.textContent = text;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);
            var tbody = document.createElement('tbody');
            tbody.id = 'ml-anomalies-tbody';
            table.appendChild(tbody);
            tableWrap.appendChild(table);
            panel.appendChild(tableWrap);

            var loading = document.createElement('div');
            loading.id = 'ml-anomalies-loading';
            loading.className = 'loading';
            loading.textContent = 'Loading anomalies...';
            panel.appendChild(loading);
        },

        // ---- Events ----

        _bindEvents: function(container) {
            var self = this;

            container.addEventListener('click', function(e) {
                var tabBtn = e.target.closest('.tab-btn');
                if (tabBtn) {
                    var tab = tabBtn.getAttribute('data-tab');
                    self._switchTab(tab);
                    return;
                }

                if (e.target.closest('#ml-train-btn')) {
                    self._showTrainDialog();
                    return;
                }

                if (e.target.closest('#anomaly-detect-btn')) {
                    self._runDetection();
                    return;
                }

                var modelRow = e.target.closest('#ml-models-tbody tr');
                if (modelRow && !e.target.closest('button')) {
                    var modelId = modelRow.getAttribute('data-model-id');
                    if (modelId) self._showModelDetail(modelId);
                    return;
                }

                var deployBtn = e.target.closest('.ml-deploy-btn');
                if (deployBtn) {
                    var id = deployBtn.getAttribute('data-model-id');
                    self._deployModel(id);
                    return;
                }

                var anomalyRow = e.target.closest('#ml-anomalies-tbody tr');
                if (anomalyRow && !e.target.closest('button')) {
                    var idx = parseInt(anomalyRow.getAttribute('data-idx'), 10);
                    self._showAnomalyDetail(idx);
                    return;
                }

                var feedbackBtn = e.target.closest('.anomaly-feedback-btn');
                if (feedbackBtn) {
                    var predId = feedbackBtn.getAttribute('data-prediction-id');
                    var isTP = feedbackBtn.getAttribute('data-feedback') === 'true';
                    self._submitFeedback(predId, isTP);
                    return;
                }

                if (e.target.closest('.detail-panel-close')) {
                    self._closeDetailPanels();
                    return;
                }
            });

            var threshInput = container.querySelector('#anomaly-threshold');
            if (threshInput) {
                threshInput.addEventListener('input', function() {
                    var val = container.querySelector('#anomaly-threshold-value');
                    if (val) val.textContent = threshInput.value;
                });
            }
        },

        _switchTab: function(tab) {
            this.activeTab = tab;
            var container = document.getElementById(this.containerId);
            if (!container) return;

            container.querySelectorAll('.tab-btn').forEach(function(btn) {
                var isActive = btn.getAttribute('data-tab') === tab;
                btn.classList.toggle('active', isActive);
                btn.setAttribute('aria-selected', String(isActive));
            });

            var modelsPanel = document.getElementById('ml-tab-models');
            var anomaliesPanel = document.getElementById('ml-tab-anomalies');
            if (modelsPanel) modelsPanel.hidden = (tab !== 'models');
            if (anomaliesPanel) anomaliesPanel.hidden = (tab !== 'anomalies');

            this._closeDetailPanels();

            if (tab === 'models') {
                this._loadModels();
            } else {
                this._loadRecentAnomalies();
            }
        },

        _closeDetailPanels: function() {
            var modelDetail = document.getElementById('ml-model-detail');
            var anomalyDetail = document.getElementById('ml-anomaly-detail');
            if (modelDetail) modelDetail.hidden = true;
            if (anomalyDetail) anomalyDetail.hidden = true;
            this.selectedModelId = null;
            this.selectedAnomalyIdx = null;
        },

        // ---- Models Tab ----

        _loadModels: function() {
            var self = this;
            var loading = document.getElementById('ml-models-loading');
            var tbody = document.getElementById('ml-models-tbody');
            var trainBtn = document.getElementById('ml-train-btn');
            if (loading) loading.hidden = false;

            var user = window.DMARC && window.DMARC.currentUser;
            if (!user) user = window.currentUser;
            var isAdmin = user && user.role === 'admin';
            if (trainBtn) trainBtn.hidden = !isAdmin;

            fetch(API_BASE + '/analytics/ml/models')
                .then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .then(function(data) {
                    if (loading) loading.hidden = true;
                    var models = Array.isArray(data) ? data : (data.models || []);
                    self._renderModelsTable(models, isAdmin);
                })
                .catch(function(err) {
                    if (loading) loading.hidden = true;
                    if (tbody) {
                        clearChildren(tbody);
                        var row = document.createElement('tr');
                        var cell = document.createElement('td');
                        cell.setAttribute('colspan', '9');
                        cell.className = 'empty-message';
                        cell.textContent = 'Failed to load models. ' + err.message;
                        row.appendChild(cell);
                        tbody.appendChild(row);
                    }
                });
        },

        _renderModelsTable: function(models, isAdmin) {
            var tbody = document.getElementById('ml-models-tbody');
            if (!tbody) return;
            clearChildren(tbody);

            if (models.length === 0) {
                var row = document.createElement('tr');
                var cell = document.createElement('td');
                cell.setAttribute('colspan', '9');
                cell.className = 'empty-message';
                cell.textContent = 'No models found. Train a model to get started.';
                row.appendChild(cell);
                tbody.appendChild(row);
                return;
            }

            models.forEach(function(model) {
                var row = document.createElement('tr');
                row.setAttribute('data-model-id', model.id);
                row.className = 'clickable-row';

                // Star icon for deployed
                var starCell = document.createElement('td');
                if (model.is_deployed) {
                    starCell.textContent = '\u2605';
                    starCell.className = 'deployed-star';
                    starCell.title = 'Currently deployed';
                }
                row.appendChild(starCell);

                // Version
                var versionCell = document.createElement('td');
                versionCell.textContent = model.version || 'v' + model.id;
                row.appendChild(versionCell);

                // Type
                var typeCell = document.createElement('td');
                typeCell.textContent = model.model_type || 'isolation_forest';
                row.appendChild(typeCell);

                // Accuracy (progress bar)
                var accCell = document.createElement('td');
                var accuracy = model.accuracy_score != null ? model.accuracy_score : 0;
                var accWrap = document.createElement('div');
                accWrap.className = 'progress-bar-wrap';
                var accBar = document.createElement('div');
                accBar.className = 'progress-bar-fill';
                var pct = Math.round(accuracy * 100);
                accBar.style.width = pct + '%';
                if (pct >= 80) accBar.classList.add('progress-success');
                else if (pct >= 60) accBar.classList.add('progress-warning');
                else accBar.classList.add('progress-danger');
                accWrap.appendChild(accBar);
                var accText = document.createElement('span');
                accText.className = 'progress-text';
                accText.textContent = pct + '%';
                accCell.appendChild(accWrap);
                accCell.appendChild(accText);
                row.appendChild(accCell);

                // Samples
                var samplesCell = document.createElement('td');
                samplesCell.textContent = (model.training_samples || 0).toLocaleString();
                row.appendChild(samplesCell);

                // Features
                var featCell = document.createElement('td');
                featCell.textContent = model.feature_count || '-';
                row.appendChild(featCell);

                // Status badge
                var statusCell = document.createElement('td');
                var badge = document.createElement('span');
                badge.className = 'badge';
                if (model.is_deployed) {
                    badge.classList.add('badge-success');
                    badge.textContent = 'Deployed';
                } else if (model.status === 'archived') {
                    badge.classList.add('badge-gray');
                    badge.textContent = 'Archived';
                } else {
                    badge.classList.add('badge-info');
                    badge.textContent = 'Trained';
                }
                statusCell.appendChild(badge);
                row.appendChild(statusCell);

                // Created
                var createdCell = document.createElement('td');
                if (model.created_at) {
                    var d = new Date(model.created_at);
                    createdCell.textContent = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                } else {
                    createdCell.textContent = '-';
                }
                row.appendChild(createdCell);

                // Actions
                var actionsCell = document.createElement('td');
                if (isAdmin && !model.is_deployed && model.status !== 'archived') {
                    var deployBtn = document.createElement('button');
                    deployBtn.className = 'btn-secondary btn-xs ml-deploy-btn';
                    deployBtn.setAttribute('data-model-id', model.id);
                    deployBtn.textContent = 'Deploy';
                    actionsCell.appendChild(deployBtn);
                }
                row.appendChild(actionsCell);

                tbody.appendChild(row);
            });
        },

        _showTrainDialog: function() {
            var self = this;
            var days = prompt('Training data period (days):', '90');
            if (!days) return;
            days = parseInt(days, 10);
            if (isNaN(days) || days < 1) {
                if (typeof showNotification === 'function') showNotification('Invalid days value', 'error');
                return;
            }

            if (!confirm('Start training a new model using the last ' + days + ' days of data?')) return;

            fetch(API_BASE + '/analytics/ml/train', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ days: days })
            })
                .then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .then(function(data) {
                    if (typeof showNotification === 'function') {
                        showNotification('Training started. Model ID: ' + (data.model_id || 'pending'), 'success');
                    }
                    self._startTrainingPoll();
                })
                .catch(function(err) {
                    if (typeof showNotification === 'function') showNotification('Failed to start training: ' + err.message, 'error');
                });
        },

        _startTrainingPoll: function() {
            var self = this;
            if (self.refreshInterval) clearInterval(self.refreshInterval);
            self.refreshInterval = setInterval(function() {
                self._loadModels();
            }, 5000);
            setTimeout(function() {
                if (self.refreshInterval) {
                    clearInterval(self.refreshInterval);
                    self.refreshInterval = null;
                }
            }, 120000);
        },

        _deployModel: function(modelId) {
            var self = this;
            if (!confirm('Deploy this model? It will replace the currently deployed model.')) return;

            fetch(API_BASE + '/analytics/ml/deploy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: parseInt(modelId, 10) })
            })
                .then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .then(function() {
                    if (typeof showNotification === 'function') showNotification('Model deployed successfully', 'success');
                    self._loadModels();
                })
                .catch(function(err) {
                    if (typeof showNotification === 'function') showNotification('Failed to deploy model: ' + err.message, 'error');
                });
        },

        _showModelDetail: function(modelId) {
            var self = this;
            var panel = document.getElementById('ml-model-detail');
            if (!panel) return;

            panel.hidden = false;
            clearChildren(panel);

            var closeBtn = document.createElement('button');
            closeBtn.className = 'btn-ghost btn-sm detail-panel-close';
            closeBtn.textContent = 'Close';
            panel.appendChild(closeBtn);

            var loadingEl = document.createElement('div');
            loadingEl.className = 'loading';
            loadingEl.textContent = 'Loading model details...';
            panel.appendChild(loadingEl);

            Promise.all([
                fetch(API_BASE + '/analytics/ml/models/' + modelId).then(function(r) { return r.ok ? r.json() : null; }),
                fetch(API_BASE + '/analytics/ml/models/' + modelId + '/stats').then(function(r) { return r.ok ? r.json() : null; })
            ])
                .then(function(results) {
                    var model = results[0];
                    var stats = results[1];
                    loadingEl.hidden = true;
                    self._renderModelDetail(panel, model, stats);
                })
                .catch(function() {
                    loadingEl.textContent = 'Failed to load model details.';
                });
        },

        _renderModelDetail: function(panel, model, stats) {
            if (!model) return;

            var h3 = document.createElement('h3');
            h3.textContent = 'Model: ' + (model.version || 'v' + model.id);
            panel.appendChild(h3);

            var details = [
                ['Type', model.model_type || 'isolation_forest'],
                ['Status', model.is_deployed ? 'Deployed' : (model.status || 'Trained')],
                ['Accuracy', model.accuracy_score != null ? (Math.round(model.accuracy_score * 100) + '%') : '-'],
                ['Training Samples', (model.training_samples || 0).toLocaleString()],
                ['Feature Count', model.feature_count || '-'],
                ['Created', model.created_at ? new Date(model.created_at).toLocaleString() : '-']
            ];

            var dl = document.createElement('dl');
            dl.className = 'detail-list';
            details.forEach(function(pair) {
                var dt = document.createElement('dt');
                dt.textContent = pair[0];
                dl.appendChild(dt);
                var dd = document.createElement('dd');
                dd.textContent = pair[1];
                dl.appendChild(dd);
            });
            panel.appendChild(dl);

            if (stats) {
                var statsH = document.createElement('h4');
                statsH.textContent = 'Performance Stats';
                panel.appendChild(statsH);

                var statsDl = document.createElement('dl');
                statsDl.className = 'detail-list';
                Object.entries(stats).forEach(function(pair) {
                    var dt = document.createElement('dt');
                    dt.textContent = pair[0].replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
                    statsDl.appendChild(dt);
                    var dd = document.createElement('dd');
                    var v = pair[1];
                    dd.textContent = typeof v === 'number' ? (v % 1 === 0 ? v.toLocaleString() : v.toFixed(4)) : String(v);
                    statsDl.appendChild(dd);
                });
                panel.appendChild(statsDl);
            }

            if (model.feature_importance && typeof model.feature_importance === 'object') {
                var fiH = document.createElement('h4');
                fiH.textContent = 'Feature Importance';
                panel.appendChild(fiH);

                var entries = Object.entries(model.feature_importance).sort(function(a, b) { return b[1] - a[1]; });
                var fiList = document.createElement('div');
                fiList.className = 'feature-importance-list';
                entries.forEach(function(pair) {
                    var row = document.createElement('div');
                    row.className = 'feature-importance-row';
                    var label = document.createElement('span');
                    label.className = 'fi-label';
                    label.textContent = pair[0];
                    var barWrap = document.createElement('div');
                    barWrap.className = 'progress-bar-wrap';
                    var bar = document.createElement('div');
                    bar.className = 'progress-bar-fill progress-info';
                    bar.style.width = Math.round(pair[1] * 100) + '%';
                    barWrap.appendChild(bar);
                    var val = document.createElement('span');
                    val.className = 'fi-value';
                    val.textContent = (pair[1] * 100).toFixed(1) + '%';
                    row.appendChild(label);
                    row.appendChild(barWrap);
                    row.appendChild(val);
                    fiList.appendChild(row);
                });
                panel.appendChild(fiList);
            }
        },

        // ---- Anomalies Tab ----

        _loadRecentAnomalies: function() {
            var self = this;
            var loading = document.getElementById('ml-anomalies-loading');
            var tbody = document.getElementById('ml-anomalies-tbody');
            if (loading) loading.hidden = false;

            var daysSelect = document.getElementById('anomaly-days');
            var days = daysSelect ? daysSelect.value : '7';

            fetch(API_BASE + '/analytics/anomalies/recent?days=' + days + '&limit=50')
                .then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .then(function(data) {
                    if (loading) loading.hidden = true;
                    var anomalies = Array.isArray(data) ? data : (data.predictions || data.anomalies || []);
                    self.anomalyResults = anomalies;
                    self._renderAnomaliesTable(anomalies);
                })
                .catch(function(err) {
                    if (loading) loading.hidden = true;
                    if (tbody) {
                        clearChildren(tbody);
                        var row = document.createElement('tr');
                        var cell = document.createElement('td');
                        cell.setAttribute('colspan', '7');
                        cell.className = 'empty-message';
                        cell.textContent = 'Failed to load anomalies. ' + err.message;
                        row.appendChild(cell);
                        tbody.appendChild(row);
                    }
                });
        },

        _runDetection: function() {
            var self = this;
            var daysSelect = document.getElementById('anomaly-days');
            var threshInput = document.getElementById('anomaly-threshold');
            var days = daysSelect ? parseInt(daysSelect.value, 10) : 7;
            var threshold = threshInput ? parseFloat(threshInput.value) : -0.5;

            var detectBtn = document.getElementById('anomaly-detect-btn');
            if (detectBtn) {
                detectBtn.disabled = true;
                detectBtn.textContent = 'Detecting...';
            }

            fetch(API_BASE + '/analytics/anomalies/detect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ days: days, threshold: threshold })
            })
                .then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .then(function(data) {
                    var anomalies = Array.isArray(data) ? data : (data.anomalies || data.predictions || []);
                    self.anomalyResults = anomalies;
                    self._renderAnomaliesTable(anomalies);
                    if (typeof showNotification === 'function') {
                        showNotification('Detection complete. Found ' + anomalies.length + ' anomalies.', 'success');
                    }
                })
                .catch(function(err) {
                    if (typeof showNotification === 'function') showNotification('Detection failed: ' + err.message, 'error');
                })
                .finally(function() {
                    if (detectBtn) {
                        detectBtn.disabled = false;
                        detectBtn.textContent = 'Run Detection';
                    }
                });
        },

        _renderAnomaliesTable: function(anomalies) {
            var tbody = document.getElementById('ml-anomalies-tbody');
            if (!tbody) return;
            clearChildren(tbody);

            if (anomalies.length === 0) {
                var row = document.createElement('tr');
                var cell = document.createElement('td');
                cell.setAttribute('colspan', '7');
                cell.className = 'empty-message';
                cell.textContent = 'No anomalies detected.';
                row.appendChild(cell);
                tbody.appendChild(row);
                return;
            }

            // Sort by anomaly score (most anomalous first)
            anomalies.sort(function(a, b) { return (a.anomaly_score || 0) - (b.anomaly_score || 0); });

            var self = this;
            anomalies.forEach(function(anomaly, idx) {
                var row = document.createElement('tr');
                row.className = 'clickable-row';
                row.setAttribute('data-idx', idx);

                // IP Address
                var ipCell = document.createElement('td');
                ipCell.textContent = anomaly.ip_address || anomaly.source_ip || '-';
                row.appendChild(ipCell);

                // Anomaly Score (colored bar)
                var scoreCell = document.createElement('td');
                var score = anomaly.anomaly_score != null ? anomaly.anomaly_score : 0;
                var scoreWrap = document.createElement('div');
                scoreWrap.className = 'anomaly-score-bar';
                var scoreBar = document.createElement('div');
                scoreBar.className = 'anomaly-score-fill';
                var scorePct = Math.min(Math.abs(score) * 100, 100);
                scoreBar.style.width = scorePct + '%';
                if (score < -0.7) scoreBar.classList.add('score-high');
                else if (score < -0.5) scoreBar.classList.add('score-medium');
                else scoreBar.classList.add('score-low');
                scoreWrap.appendChild(scoreBar);
                var scoreText = document.createElement('span');
                scoreText.className = 'score-text';
                scoreText.textContent = score.toFixed(3);
                scoreCell.appendChild(scoreWrap);
                scoreCell.appendChild(scoreText);
                row.appendChild(scoreCell);

                // Features summary
                var features = anomaly.features || {};

                var volCell = document.createElement('td');
                volCell.textContent = (features.total_count || 0).toLocaleString();
                row.appendChild(volCell);

                var frCell = document.createElement('td');
                var failRate = features.failure_rate != null ? features.failure_rate : 0;
                frCell.textContent = (failRate * 100).toFixed(1) + '%';
                row.appendChild(frCell);

                var udCell = document.createElement('td');
                udCell.textContent = features.unique_domains || '-';
                row.appendChild(udCell);

                // Prediction
                var predCell = document.createElement('td');
                var predBadge = document.createElement('span');
                predBadge.className = 'badge';
                var prediction = anomaly.prediction || (score < -0.5 ? 'anomalous' : 'normal');
                if (prediction === 'anomalous' || prediction === -1 || prediction === 'anomaly') {
                    predBadge.classList.add('badge-danger');
                    predBadge.textContent = 'Anomalous';
                } else {
                    predBadge.classList.add('badge-success');
                    predBadge.textContent = 'Normal';
                }
                predCell.appendChild(predBadge);
                row.appendChild(predCell);

                // Actions
                var actionsCell = document.createElement('td');
                var viewBtn = document.createElement('button');
                viewBtn.className = 'btn-ghost btn-xs';
                viewBtn.textContent = 'Details';
                viewBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    self._showAnomalyDetail(idx);
                });
                actionsCell.appendChild(viewBtn);
                row.appendChild(actionsCell);

                tbody.appendChild(row);
            });
        },

        _showAnomalyDetail: function(idx) {
            var anomaly = this.anomalyResults[idx];
            if (!anomaly) return;

            var panel = document.getElementById('ml-anomaly-detail');
            if (!panel) return;

            panel.hidden = false;
            clearChildren(panel);
            this.selectedAnomalyIdx = idx;

            // Close button
            var closeBtn = document.createElement('button');
            closeBtn.className = 'btn-ghost btn-sm detail-panel-close';
            closeBtn.textContent = 'Close';
            panel.appendChild(closeBtn);

            var h3 = document.createElement('h3');
            h3.textContent = 'Anomaly Details';
            panel.appendChild(h3);

            // IP
            var ipP = document.createElement('p');
            ipP.className = 'detail-ip';
            var ipStrong = document.createElement('strong');
            ipStrong.textContent = anomaly.ip_address || anomaly.source_ip || '-';
            ipP.appendChild(ipStrong);
            panel.appendChild(ipP);

            // Score visualization
            var score = anomaly.anomaly_score != null ? anomaly.anomaly_score : 0;
            var scoreSection = document.createElement('div');
            scoreSection.className = 'anomaly-score-gauge';
            var scoreLabel = document.createElement('div');
            scoreLabel.className = 'gauge-label';
            scoreLabel.textContent = 'Anomaly Score: ' + score.toFixed(4);
            scoreSection.appendChild(scoreLabel);
            var gaugeWrap = document.createElement('div');
            gaugeWrap.className = 'anomaly-score-bar large';
            var gaugeBar = document.createElement('div');
            gaugeBar.className = 'anomaly-score-fill';
            var gaugePct = Math.min(Math.abs(score) * 100, 100);
            gaugeBar.style.width = gaugePct + '%';
            if (score < -0.7) gaugeBar.classList.add('score-high');
            else if (score < -0.5) gaugeBar.classList.add('score-medium');
            else gaugeBar.classList.add('score-low');
            gaugeWrap.appendChild(gaugeBar);
            scoreSection.appendChild(gaugeWrap);
            panel.appendChild(scoreSection);

            // All features
            var features = anomaly.features || {};
            if (Object.keys(features).length > 0) {
                var featH = document.createElement('h4');
                featH.textContent = 'Features';
                panel.appendChild(featH);

                var dl = document.createElement('dl');
                dl.className = 'detail-list';
                Object.entries(features).forEach(function(pair) {
                    var dt = document.createElement('dt');
                    dt.textContent = pair[0].replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
                    dl.appendChild(dt);
                    var dd = document.createElement('dd');
                    var v = pair[1];
                    if (typeof v === 'number') {
                        dd.textContent = v % 1 === 0 ? v.toLocaleString() : v.toFixed(4);
                    } else {
                        dd.textContent = String(v);
                    }
                    dl.appendChild(dd);
                });
                panel.appendChild(dl);
            }

            // Feedback buttons
            var predId = anomaly.id || anomaly.prediction_id;
            if (predId) {
                var feedbackH = document.createElement('h4');
                feedbackH.textContent = 'Feedback';
                panel.appendChild(feedbackH);

                var feedbackWrap = document.createElement('div');
                feedbackWrap.className = 'feedback-buttons';

                var tpBtn = document.createElement('button');
                tpBtn.className = 'btn-danger btn-sm anomaly-feedback-btn';
                tpBtn.setAttribute('data-prediction-id', predId);
                tpBtn.setAttribute('data-feedback', 'true');
                tpBtn.textContent = 'True Positive';

                var fpBtn = document.createElement('button');
                fpBtn.className = 'btn-secondary btn-sm anomaly-feedback-btn';
                fpBtn.setAttribute('data-prediction-id', predId);
                fpBtn.setAttribute('data-feedback', 'false');
                fpBtn.textContent = 'False Positive';

                feedbackWrap.appendChild(tpBtn);
                feedbackWrap.appendChild(fpBtn);
                panel.appendChild(feedbackWrap);

                var notesLabel = document.createElement('label');
                notesLabel.textContent = 'Notes (optional)';
                notesLabel.setAttribute('for', 'anomaly-feedback-notes');
                panel.appendChild(notesLabel);
                var notesInput = document.createElement('textarea');
                notesInput.id = 'anomaly-feedback-notes';
                notesInput.className = 'feedback-notes';
                notesInput.rows = 3;
                notesInput.placeholder = 'Add notes about this anomaly...';
                panel.appendChild(notesInput);
            }
        },

        _submitFeedback: function(predictionId, isTruePositive) {
            var notesEl = document.getElementById('anomaly-feedback-notes');
            var notes = notesEl ? notesEl.value.trim() : '';

            fetch(API_BASE + '/analytics/anomalies/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prediction_id: parseInt(predictionId, 10),
                    is_true_positive: isTruePositive,
                    notes: notes || undefined
                })
            })
                .then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .then(function() {
                    if (typeof showNotification === 'function') {
                        showNotification('Feedback submitted. ' + (isTruePositive ? 'Marked as true positive.' : 'Marked as false positive.'), 'success');
                    }
                })
                .catch(function(err) {
                    if (typeof showNotification === 'function') showNotification('Failed to submit feedback: ' + err.message, 'error');
                });
        }
    };

    // Expose and register
    window.DMARC = window.DMARC || {};
    window.DMARC.MLModelsPage = MLModelsPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('ml-models', MLModelsPage);
    }
})();
