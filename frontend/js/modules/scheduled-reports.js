/**
 * DMARC Dashboard - Scheduled Reports Module
 *
 * Full management page (#page-scheduled-reports) for creating, editing,
 * running, and viewing history of scheduled report jobs.
 */
(function() {
    'use strict';

    var API_BASE = '/api';

    var REPORT_TYPES = {
        summary: 'Summary',
        detailed: 'Detailed',
        domain_health: 'Domain Health',
        alerts: 'Alerts'
    };

    var FREQUENCIES = {
        daily: 'Daily',
        weekly: 'Weekly',
        monthly: 'Monthly'
    };

    var DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

    var ScheduledReportsPage = {
        initialized: false,
        containerId: 'page-scheduled-reports',
        reports: [],
        expandedHistory: null,

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            var container = document.getElementById(this.containerId);
            if (!container) return;

            var self = this;

            // Page header
            var header = document.createElement('div');
            header.className = 'page-header';
            var headerRow = document.createElement('div');
            headerRow.style.cssText = 'display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;';

            var headerLeft = document.createElement('div');
            var h1 = document.createElement('h1');
            h1.textContent = 'Scheduled Reports';
            headerLeft.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Configure automated reports to be emailed on a schedule.';
            headerLeft.appendChild(desc);
            headerRow.appendChild(headerLeft);

            var createBtn = document.createElement('button');
            createBtn.className = 'btn-primary';
            createBtn.textContent = 'Create Report';
            createBtn.addEventListener('click', function() {
                self._showReportModal(null);
            });
            headerRow.appendChild(createBtn);

            header.appendChild(headerRow);
            container.appendChild(header);

            // Body
            var body = document.createElement('div');
            body.className = 'page-body';
            body.id = 'scheduledReportsBody';
            container.appendChild(body);
        },

        load: function() {
            this._loadReports();
        },

        _loadReports: function() {
            var body = document.getElementById('scheduledReportsBody');
            if (!body) return;
            var self = this;

            body.textContent = '';
            var loadingDiv = document.createElement('div');
            loadingDiv.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
            loadingDiv.textContent = 'Loading scheduled reports...';
            body.appendChild(loadingDiv);

            fetch(API_BASE + '/scheduled-reports')
                .then(function(r) { return r.ok ? r.json() : []; })
                .then(function(data) {
                    self.reports = Array.isArray(data) ? data : [];
                    self._renderReports(body);
                })
                .catch(function() {
                    body.textContent = '';
                    var errDiv = document.createElement('div');
                    errDiv.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
                    errDiv.textContent = 'Failed to load scheduled reports.';
                    body.appendChild(errDiv);
                });
        },

        _renderReports: function(body) {
            body.textContent = '';
            var self = this;

            if (this.reports.length === 0) {
                var empty = document.createElement('div');
                empty.style.cssText = 'text-align: center; padding: 64px; color: var(--text-muted);';
                var emptyTitle = document.createElement('h3');
                emptyTitle.style.cssText = 'margin-bottom: 8px; color: var(--text-primary);';
                emptyTitle.textContent = 'No scheduled reports';
                empty.appendChild(emptyTitle);
                var emptyDesc = document.createElement('p');
                emptyDesc.textContent = 'Create your first scheduled report to receive automated DMARC summaries.';
                empty.appendChild(emptyDesc);
                body.appendChild(empty);
                return;
            }

            var table = document.createElement('table');
            table.style.width = '100%';
            var thead = document.createElement('thead');
            var headerRow = document.createElement('tr');
            ['Name', 'Type', 'Schedule', 'Recipients', 'Status', 'Last Run', 'Next Run', 'Actions'].forEach(function(text) {
                var th = document.createElement('th');
                th.setAttribute('scope', 'col');
                th.textContent = text;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);

            var tbody = document.createElement('tbody');

            this.reports.forEach(function(report) {
                var tr = document.createElement('tr');

                // Name
                var tdName = document.createElement('td');
                tdName.style.fontWeight = '500';
                tdName.textContent = report.name;
                tr.appendChild(tdName);

                // Type
                var tdType = document.createElement('td');
                var typeBadge = document.createElement('span');
                typeBadge.className = 'badge badge-info';
                typeBadge.textContent = REPORT_TYPES[report.report_type] || report.report_type;
                tdType.appendChild(typeBadge);
                tr.appendChild(tdType);

                // Schedule
                var tdSchedule = document.createElement('td');
                tdSchedule.textContent = self._formatSchedule(report.schedule);
                tr.appendChild(tdSchedule);

                // Recipients
                var tdRecipients = document.createElement('td');
                tdRecipients.style.cssText = 'font-size: 0.8rem; max-width: 200px; overflow: hidden; text-overflow: ellipsis;';
                tdRecipients.textContent = (report.recipients || []).join(', ');
                tdRecipients.title = (report.recipients || []).join(', ');
                tr.appendChild(tdRecipients);

                // Status
                var tdStatus = document.createElement('td');
                var statusBadge = document.createElement('span');
                statusBadge.className = 'badge ' + (report.is_active ? 'badge-success' : 'badge-gray');
                statusBadge.textContent = report.is_active ? 'Active' : 'Paused';
                tdStatus.appendChild(statusBadge);
                tr.appendChild(tdStatus);

                // Last Run
                var tdLastRun = document.createElement('td');
                tdLastRun.style.fontSize = '0.85rem';
                tdLastRun.textContent = report.last_run_at ? new Date(report.last_run_at).toLocaleString() : 'Never';
                tr.appendChild(tdLastRun);

                // Next Run
                var tdNextRun = document.createElement('td');
                tdNextRun.style.fontSize = '0.85rem';
                tdNextRun.textContent = report.next_run_at ? new Date(report.next_run_at).toLocaleString() : '-';
                tr.appendChild(tdNextRun);

                // Actions
                var tdActions = document.createElement('td');
                var actionsDiv = document.createElement('div');
                actionsDiv.style.cssText = 'display: flex; gap: 4px; flex-wrap: wrap;';

                var editBtn = document.createElement('button');
                editBtn.className = 'btn-ghost btn-sm';
                editBtn.textContent = 'Edit';
                editBtn.addEventListener('click', function() {
                    self._showReportModal(report);
                });
                actionsDiv.appendChild(editBtn);

                var runBtn = document.createElement('button');
                runBtn.className = 'btn-ghost btn-sm';
                runBtn.textContent = 'Run Now';
                runBtn.addEventListener('click', function() {
                    self._runNow(report.id);
                });
                actionsDiv.appendChild(runBtn);

                var histBtn = document.createElement('button');
                histBtn.className = 'btn-ghost btn-sm';
                histBtn.textContent = 'History';
                histBtn.addEventListener('click', function() {
                    self._toggleHistory(report.id, tr);
                });
                actionsDiv.appendChild(histBtn);

                var delBtn = document.createElement('button');
                delBtn.className = 'btn-ghost btn-sm';
                delBtn.style.color = 'var(--accent-danger)';
                delBtn.textContent = 'Delete';
                delBtn.addEventListener('click', function() {
                    self._deleteReport(report.id, report.name);
                });
                actionsDiv.appendChild(delBtn);

                tdActions.appendChild(actionsDiv);
                tr.appendChild(tdActions);
                tbody.appendChild(tr);
            });

            table.appendChild(tbody);

            var tableWrapper = document.createElement('div');
            tableWrapper.className = 'table-container';
            tableWrapper.appendChild(table);
            body.appendChild(tableWrapper);
        },

        _formatSchedule: function(schedule) {
            if (!schedule) return '-';
            var freq = FREQUENCIES[schedule.frequency] || schedule.frequency;
            var parts = [freq];
            if (schedule.frequency === 'weekly' && schedule.day_of_week !== undefined) {
                parts.push('on ' + (DAYS_OF_WEEK[schedule.day_of_week] || schedule.day_of_week));
            }
            if (schedule.time) {
                parts.push('at ' + schedule.time);
            }
            return parts.join(' ');
        },

        _showReportModal: function(report) {
            var self = this;
            var isEdit = report !== null;

            var overlay = document.createElement('div');
            overlay.className = 'modal';
            overlay.setAttribute('role', 'dialog');
            overlay.setAttribute('aria-modal', 'true');
            overlay.style.display = 'flex';

            var content = document.createElement('div');
            content.className = 'modal-content';
            content.style.maxWidth = '520px';

            // Header
            var header = document.createElement('div');
            header.className = 'modal-header';
            var title = document.createElement('h2');
            title.textContent = isEdit ? 'Edit Report' : 'Create Report';
            header.appendChild(title);
            var closeBtn = document.createElement('button');
            closeBtn.className = 'modal-close';
            closeBtn.setAttribute('aria-label', 'Close');
            closeBtn.textContent = 'X';
            closeBtn.addEventListener('click', function() { document.body.removeChild(overlay); });
            header.appendChild(closeBtn);
            content.appendChild(header);

            // Body
            var body = document.createElement('div');
            body.className = 'modal-body';
            body.style.padding = '24px';

            // Name
            body.appendChild(self._createFormField('Name', function() {
                var input = document.createElement('input');
                input.type = 'text';
                input.id = 'srName';
                input.value = isEdit ? report.name : '';
                input.placeholder = 'e.g., Weekly Domain Summary';
                input.style.cssText = 'width: 100%; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary);';
                return input;
            }));

            // Report type
            body.appendChild(self._createFormField('Report Type', function() {
                var select = document.createElement('select');
                select.id = 'srType';
                select.style.cssText = 'width: 100%; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary);';
                Object.keys(REPORT_TYPES).forEach(function(key) {
                    var opt = document.createElement('option');
                    opt.value = key;
                    opt.textContent = REPORT_TYPES[key];
                    if (isEdit && report.report_type === key) opt.selected = true;
                    select.appendChild(opt);
                });
                return select;
            }));

            // Frequency
            body.appendChild(self._createFormField('Frequency', function() {
                var select = document.createElement('select');
                select.id = 'srFrequency';
                select.style.cssText = 'width: 100%; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary);';
                Object.keys(FREQUENCIES).forEach(function(key) {
                    var opt = document.createElement('option');
                    opt.value = key;
                    opt.textContent = FREQUENCIES[key];
                    if (isEdit && report.schedule && report.schedule.frequency === key) opt.selected = true;
                    select.appendChild(opt);
                });
                select.addEventListener('change', function() {
                    var dowGroup = document.getElementById('srDayOfWeekGroup');
                    if (dowGroup) dowGroup.hidden = this.value !== 'weekly';
                });
                return select;
            }));

            // Day of week (shown for weekly)
            var dowField = self._createFormField('Day of Week', function() {
                var select = document.createElement('select');
                select.id = 'srDayOfWeek';
                select.style.cssText = 'width: 100%; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary);';
                DAYS_OF_WEEK.forEach(function(day, i) {
                    var opt = document.createElement('option');
                    opt.value = String(i);
                    opt.textContent = day;
                    if (isEdit && report.schedule && report.schedule.day_of_week === i) opt.selected = true;
                    select.appendChild(opt);
                });
                return select;
            });
            dowField.id = 'srDayOfWeekGroup';
            var isWeekly = isEdit && report.schedule && report.schedule.frequency === 'weekly';
            dowField.hidden = !isWeekly;
            body.appendChild(dowField);

            // Time
            body.appendChild(self._createFormField('Time', function() {
                var input = document.createElement('input');
                input.type = 'time';
                input.id = 'srTime';
                input.value = isEdit && report.schedule ? (report.schedule.time || '08:00') : '08:00';
                input.style.cssText = 'width: 100%; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary);';
                return input;
            }));

            // Recipients
            body.appendChild(self._createFormField('Recipients (one per line)', function() {
                var textarea = document.createElement('textarea');
                textarea.id = 'srRecipients';
                textarea.rows = 3;
                textarea.placeholder = 'user@example.com';
                textarea.style.cssText = 'width: 100%; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary); resize: vertical; font-family: inherit;';
                if (isEdit && report.recipients) {
                    textarea.value = report.recipients.join('\n');
                }
                return textarea;
            }));

            // Domains
            body.appendChild(self._createFormField('Domains (comma-separated, or "all")', function() {
                var input = document.createElement('input');
                input.type = 'text';
                input.id = 'srDomains';
                input.placeholder = 'all';
                input.style.cssText = 'width: 100%; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary);';
                if (isEdit && report.domains) {
                    input.value = Array.isArray(report.domains) ? report.domains.join(', ') : 'all';
                }
                return input;
            }));

            // Active toggle
            var activeLabel = document.createElement('label');
            activeLabel.style.cssText = 'display: flex; align-items: center; gap: 8px; margin-top: 12px; font-size: 0.85rem; cursor: pointer;';
            var activeCheck = document.createElement('input');
            activeCheck.type = 'checkbox';
            activeCheck.id = 'srActive';
            activeCheck.checked = isEdit ? report.is_active : true;
            activeLabel.appendChild(activeCheck);
            activeLabel.appendChild(document.createTextNode('Active'));
            body.appendChild(activeLabel);

            content.appendChild(body);

            // Footer
            var footer = document.createElement('div');
            footer.style.cssText = 'padding: 16px 24px; display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid var(--border-color);';

            var cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn-secondary';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.addEventListener('click', function() { document.body.removeChild(overlay); });
            footer.appendChild(cancelBtn);

            var saveBtn = document.createElement('button');
            saveBtn.className = 'btn-primary';
            saveBtn.textContent = isEdit ? 'Save Changes' : 'Create Report';
            saveBtn.addEventListener('click', function() {
                self._saveReport(report, overlay);
            });
            footer.appendChild(saveBtn);
            content.appendChild(footer);

            overlay.appendChild(content);
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay) document.body.removeChild(overlay);
            });

            document.body.appendChild(overlay);
        },

        _createFormField: function(labelText, inputFn) {
            var group = document.createElement('div');
            group.style.marginBottom = '16px';
            var label = document.createElement('label');
            label.style.cssText = 'display: block; font-size: 0.85rem; font-weight: 500; color: var(--text-secondary); margin-bottom: 6px;';
            label.textContent = labelText;
            group.appendChild(label);
            group.appendChild(inputFn());
            return group;
        },

        _saveReport: function(existingReport, overlay) {
            var name = document.getElementById('srName');
            if (!name || !name.value.trim()) {
                if (name) name.style.borderColor = 'var(--accent-danger)';
                return;
            }

            var recipientsText = (document.getElementById('srRecipients') || {}).value || '';
            var recipients = recipientsText.split('\n').map(function(s) { return s.trim(); }).filter(function(s) { return s; });

            var domainsText = (document.getElementById('srDomains') || {}).value || 'all';
            var domains;
            if (domainsText.trim().toLowerCase() === 'all') {
                domains = [];
            } else {
                domains = domainsText.split(',').map(function(s) { return s.trim(); }).filter(function(s) { return s; });
            }

            var payload = {
                name: name.value.trim(),
                report_type: (document.getElementById('srType') || {}).value || 'summary',
                schedule: {
                    frequency: (document.getElementById('srFrequency') || {}).value || 'weekly',
                    day_of_week: parseInt((document.getElementById('srDayOfWeek') || {}).value || '0', 10),
                    time: (document.getElementById('srTime') || {}).value || '08:00'
                },
                recipients: recipients,
                domains: domains,
                is_active: (document.getElementById('srActive') || {}).checked !== false
            };

            var isEdit = existingReport !== null;
            var url = API_BASE + '/scheduled-reports' + (isEdit ? '/' + encodeURIComponent(existingReport.id) : '');
            var method = isEdit ? 'PUT' : 'POST';

            var self = this;
            fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(function(r) {
                if (r.ok) {
                    document.body.removeChild(overlay);
                    if (typeof showNotification === 'function') {
                        showNotification(isEdit ? 'Report updated' : 'Report created', 'success');
                    }
                    self._loadReports();
                } else {
                    if (typeof showNotification === 'function') {
                        showNotification('Failed to save report', 'error');
                    }
                }
            })
            .catch(function() {
                if (typeof showNotification === 'function') {
                    showNotification('Failed to save report', 'error');
                }
            });
        },

        _runNow: function(id) {
            var self = this;
            fetch(API_BASE + '/scheduled-reports/' + encodeURIComponent(id) + '/run', { method: 'POST' })
                .then(function(r) {
                    if (r.ok) {
                        if (typeof showNotification === 'function') {
                            showNotification('Report execution started', 'success');
                        }
                        self._loadReports();
                    } else {
                        if (typeof showNotification === 'function') {
                            showNotification('Failed to execute report', 'error');
                        }
                    }
                })
                .catch(function() {
                    if (typeof showNotification === 'function') {
                        showNotification('Failed to execute report', 'error');
                    }
                });
        },

        _deleteReport: function(id, name) {
            if (!confirm('Delete scheduled report "' + name + '"?')) return;
            var self = this;
            fetch(API_BASE + '/scheduled-reports/' + encodeURIComponent(id), { method: 'DELETE' })
                .then(function(r) {
                    if (r.ok) {
                        if (typeof showNotification === 'function') {
                            showNotification('Report deleted', 'info');
                        }
                        self._loadReports();
                    }
                })
                .catch(function() {});
        },

        _toggleHistory: function(reportId, afterRow) {
            var self = this;

            // Remove existing history row if any
            var existingRow = document.getElementById('historyRow-' + reportId);
            if (existingRow) {
                existingRow.parentNode.removeChild(existingRow);
                this.expandedHistory = null;
                return;
            }

            // Remove other expanded history
            if (this.expandedHistory) {
                var prev = document.getElementById('historyRow-' + this.expandedHistory);
                if (prev) prev.parentNode.removeChild(prev);
            }
            this.expandedHistory = reportId;

            var historyRow = document.createElement('tr');
            historyRow.id = 'historyRow-' + reportId;
            var historyCell = document.createElement('td');
            historyCell.setAttribute('colspan', '8');
            historyCell.style.cssText = 'padding: 16px 24px; background: var(--bg-tertiary);';
            historyCell.textContent = 'Loading history...';
            historyRow.appendChild(historyCell);

            afterRow.parentNode.insertBefore(historyRow, afterRow.nextSibling);

            fetch(API_BASE + '/scheduled-reports/' + encodeURIComponent(reportId) + '/logs')
                .then(function(r) { return r.ok ? r.json() : []; })
                .then(function(data) {
                    var items = Array.isArray(data) ? data : [];
                    historyCell.textContent = '';

                    if (items.length === 0) {
                        historyCell.textContent = 'No execution history.';
                        return;
                    }

                    var histTable = document.createElement('table');
                    histTable.style.cssText = 'width: 100%; font-size: 0.85rem;';
                    var hHead = document.createElement('thead');
                    var hRow = document.createElement('tr');
                    ['Status', 'Started', 'Completed', 'Error'].forEach(function(h) {
                        var th = document.createElement('th');
                        th.setAttribute('scope', 'col');
                        th.textContent = h;
                        hRow.appendChild(th);
                    });
                    hHead.appendChild(hRow);
                    histTable.appendChild(hHead);

                    var hBody = document.createElement('tbody');
                    items.forEach(function(item) {
                        var tr = document.createElement('tr');
                        var tdStatus = document.createElement('td');
                        var statusBadge = document.createElement('span');
                        var badgeClass = 'badge-gray';
                        if (item.status === 'completed') badgeClass = 'badge-success';
                        else if (item.status === 'failed') badgeClass = 'badge-danger';
                        else if (item.status === 'running') badgeClass = 'badge-info';
                        statusBadge.className = 'badge ' + badgeClass;
                        statusBadge.textContent = item.status || 'unknown';
                        tdStatus.appendChild(statusBadge);
                        tr.appendChild(tdStatus);

                        var tdStarted = document.createElement('td');
                        tdStarted.textContent = item.started_at ? new Date(item.started_at).toLocaleString() : '-';
                        tr.appendChild(tdStarted);

                        var tdCompleted = document.createElement('td');
                        tdCompleted.textContent = item.completed_at ? new Date(item.completed_at).toLocaleString() : '-';
                        tr.appendChild(tdCompleted);

                        var tdError = document.createElement('td');
                        tdError.style.cssText = 'color: var(--accent-danger); max-width: 300px; overflow: hidden; text-overflow: ellipsis;';
                        var errorText = item.error || item.error_message || '-';
                        tdError.textContent = errorText;
                        tdError.title = errorText !== '-' ? errorText : '';
                        tr.appendChild(tdError);

                        hBody.appendChild(tr);
                    });
                    histTable.appendChild(hBody);
                    historyCell.appendChild(histTable);
                })
                .catch(function() {
                    historyCell.textContent = 'Failed to load history.';
                });
        },

        destroy: function() {
            this.expandedHistory = null;
        }
    };

    // Expose module
    window.DMARC = window.DMARC || {};
    window.DMARC.ScheduledReportsPage = ScheduledReportsPage;

    // Register with router
    if (window.DMARC.Router) {
        window.DMARC.Router.register('scheduled-reports', ScheduledReportsPage);
    }
})();
