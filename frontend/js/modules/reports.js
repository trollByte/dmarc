/**
 * DMARC Dashboard - Reports Page Module
 * Full-featured DMARC report browser with filtering, pagination,
 * inline record expansion, bulk operations, and CSV export.
 */
(function() {
    'use strict';

    var currentPage = 1;
    var pageSize = 20;
    var totalReports = 0;
    var sortColumn = 'date_end';
    var sortDirection = 'desc';
    var expandedReportId = null;
    var recordsPage = 1;
    var recordsPageSize = 10;
    var selectedReportIds = [];
    var domainsList = [];

    // =========================================
    // Helpers (same pattern as alerts.js)
    // =========================================

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
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    function formatDateTime(dateStr) {
        if (!dateStr) return '-';
        var d = new Date(dateStr);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    }

    function getSection() {
        return document.getElementById('page-reports');
    }

    function el(tag, attrs, children) {
        var node = document.createElement(tag);
        if (attrs) {
            Object.keys(attrs).forEach(function(k) {
                if (k === 'className') node.className = attrs[k];
                else if (k === 'textContent') node.textContent = attrs[k];
                else if (k === 'hidden') node.hidden = attrs[k];
                else if (k === 'disabled') node.disabled = attrs[k];
                else if (k === 'checked') node.checked = attrs[k];
                else if (k === 'selected') node.selected = attrs[k];
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

    function clearChildren(node) {
        while (node.firstChild) node.removeChild(node.firstChild);
    }

    // =========================================
    // Badge helpers
    // =========================================

    function passRateBadge(report) {
        var total = report.total_messages || 0;
        if (total === 0) return el('span', { className: 'badge badge-gray', textContent: 'N/A' });
        // We don't have pass count directly; compute from record_count context
        // The API gives total_messages; pass rate will be computed when records are available
        // For the listing, show total messages as a number
        return el('span', { textContent: String(total) });
    }

    function policyBadge(policy) {
        if (!policy) return el('span', { className: 'badge badge-gray', textContent: '-' });
        var map = {
            none: 'badge badge-warning',
            quarantine: 'badge badge-info',
            reject: 'badge badge-success'
        };
        var cls = map[(policy || '').toLowerCase()] || 'badge badge-gray';
        return el('span', { className: cls, textContent: policy });
    }

    function resultBadge(result) {
        if (!result) return el('span', { className: 'badge badge-gray', textContent: '-' });
        var r = (result || '').toLowerCase();
        if (r === 'pass') return el('span', { className: 'badge badge-success', textContent: 'pass' });
        if (r === 'fail') return el('span', { className: 'badge badge-danger', textContent: 'fail' });
        return el('span', { className: 'badge badge-gray', textContent: result });
    }

    function dispositionBadge(disp) {
        if (!disp) return el('span', { className: 'badge badge-gray', textContent: '-' });
        var d = (disp || '').toLowerCase();
        if (d === 'none') return el('span', { className: 'badge badge-success', textContent: 'none' });
        if (d === 'quarantine') return el('span', { className: 'badge badge-warning', textContent: 'quarantine' });
        if (d === 'reject') return el('span', { className: 'badge badge-danger', textContent: 'reject' });
        return el('span', { className: 'badge badge-gray', textContent: disp });
    }

    // =========================================
    // Filter state
    // =========================================

    function getFilters() {
        var domainEl = document.getElementById('reports-filter-domain');
        var orgEl = document.getElementById('reports-filter-org');
        var daysEl = document.getElementById('reports-filter-days');
        return {
            domain: domainEl ? domainEl.value : '',
            org_name: orgEl ? orgEl.value : '',
            days: daysEl ? daysEl.value : '30'
        };
    }

    // =========================================
    // Sort helpers
    // =========================================

    function sortIcon(column) {
        if (sortColumn !== column) return el('span', { className: 'sort-icon', textContent: ' \u2195' });
        return el('span', { className: 'sort-icon', textContent: sortDirection === 'asc' ? ' \u2191' : ' \u2193' });
    }

    function makeSortableHeader(label, column) {
        var th = el('th', { className: 'sortable-header', style: { cursor: 'pointer', userSelect: 'none' } });
        th.appendChild(text(label));
        th.appendChild(sortIcon(column));
        th.addEventListener('click', function() {
            if (sortColumn === column) {
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                sortColumn = column;
                sortDirection = 'desc';
            }
            currentPage = 1;
            loadReports();
        });
        return th;
    }

    // =========================================
    // Domain list for filter dropdown
    // =========================================

    async function loadDomains() {
        try {
            var res = await fetch(apiBase() + '/domains', { headers: authHeaders() });
            if (!res.ok) return;
            var data = await res.json();
            domainsList = (data.domains || []).map(function(d) { return d.domain || d; });
            populateDomainSelect();
        } catch (e) {
            console.error('Error loading domains for reports filter:', e);
        }
    }

    function populateDomainSelect() {
        var select = document.getElementById('reports-filter-domain');
        if (!select) return;
        var currentVal = select.value;
        clearChildren(select);
        select.appendChild(el('option', { value: '', textContent: 'All Domains' }));
        domainsList.forEach(function(domain) {
            select.appendChild(el('option', { value: domain, textContent: domain }));
        });
        select.value = currentVal || '';
    }

    // =========================================
    // Load Reports
    // =========================================

    async function loadReports() {
        var tbody = document.getElementById('reports-tbody');
        if (!tbody) return;

        // Clear expanded state
        expandedReportId = null;

        // Show loading
        clearChildren(tbody);
        var colCount = isAdmin() ? 8 : 7;
        tbody.appendChild(el('tr', {}, [
            el('td', { colspan: String(colCount), className: 'loading', textContent: 'Loading reports...' })
        ]));

        var filters = getFilters();
        var params = new URLSearchParams();
        params.set('page', currentPage);
        params.set('page_size', pageSize);
        if (filters.domain) params.set('domain', filters.domain);
        if (filters.org_name) params.set('org_name', filters.org_name);
        if (filters.days) params.set('days', filters.days);

        try {
            var res = await fetch(apiBase() + '/reports?' + params.toString(), { headers: authHeaders() });
            if (!res.ok) throw new Error('Failed to load reports');
            var data = await res.json();
            var reports = data.reports || [];
            totalReports = data.total || 0;

            // Client-side sort (API may not support sort params)
            reports = sortReports(reports);

            clearChildren(tbody);

            if (reports.length === 0) {
                var emptyTd = el('td', { colspan: String(colCount) });
                emptyTd.style.textAlign = 'center';
                emptyTd.style.padding = '48px 16px';
                var emptyDiv = el('div', { className: 'empty-state' }, [
                    el('h3', { textContent: 'No reports found' }),
                    el('p', { textContent: 'Try adjusting your filters or upload new DMARC reports.' })
                ]);
                emptyTd.appendChild(emptyDiv);
                tbody.appendChild(el('tr', {}, [emptyTd]));
                updatePagination();
                updateBulkToolbar();
                return;
            }

            selectedReportIds = [];
            updateBulkToolbar();

            reports.forEach(function(report) {
                var row = buildReportRow(report);
                tbody.appendChild(row);
            });

            updatePagination();
            updateReportCount();
        } catch (e) {
            console.error('Error loading reports:', e);
            clearChildren(tbody);
            var errTd = el('td', { colspan: String(colCount), textContent: 'Failed to load reports' });
            errTd.style.textAlign = 'center';
            errTd.style.padding = '32px';
            errTd.style.color = 'var(--accent-danger)';
            tbody.appendChild(el('tr', {}, [errTd]));
        }
    }

    function sortReports(reports) {
        var col = sortColumn;
        var dir = sortDirection === 'asc' ? 1 : -1;
        return reports.slice().sort(function(a, b) {
            var va, vb;
            if (col === 'date_end' || col === 'date_begin') {
                va = new Date(a[col] || 0).getTime();
                vb = new Date(b[col] || 0).getTime();
            } else if (col === 'total_messages' || col === 'record_count') {
                va = a[col] || 0;
                vb = b[col] || 0;
            } else {
                va = (a[col] || '').toLowerCase();
                vb = (b[col] || '').toLowerCase();
            }
            if (va < vb) return -1 * dir;
            if (va > vb) return 1 * dir;
            return 0;
        });
    }

    // =========================================
    // Build Report Row
    // =========================================

    function buildReportRow(report) {
        var admin = isAdmin();
        var cells = [];

        // Checkbox (admin only)
        if (admin) {
            var cb = el('input', { type: 'checkbox', className: 'report-select-cb' });
            cb.addEventListener('change', function() {
                var id = String(report.id);
                if (cb.checked) {
                    if (selectedReportIds.indexOf(id) === -1) selectedReportIds.push(id);
                } else {
                    selectedReportIds = selectedReportIds.filter(function(x) { return x !== id; });
                }
                updateBulkToolbar();
            });
            cells.push(el('td', {}, [cb]));
        }

        // Date Range
        var dateRange = formatDate(report.date_begin) + ' - ' + formatDate(report.date_end);
        cells.push(el('td', { textContent: dateRange }));

        // Organization
        cells.push(el('td', { textContent: report.org_name || '-' }));

        // Domain
        cells.push(el('td', { textContent: report.domain || '-' }));

        // Messages
        cells.push(el('td', { textContent: String(report.total_messages || 0) }));

        // Records count as a simple metric
        cells.push(el('td', { textContent: String(report.record_count || 0) }));

        // Policy
        cells.push(el('td', {}, [policyBadge(report.p)]));

        // Actions - expand toggle
        var expandBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'View Records' });
        expandBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleRecords(report.id);
        });
        var actionsTd = el('td', { className: 'reports-actions-cell' }, [expandBtn]);

        if (admin) {
            var deleteBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Delete' });
            deleteBtn.style.color = 'var(--accent-danger)';
            deleteBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                if (confirm('Delete this report? This cannot be undone.')) {
                    deleteReport(report.id);
                }
            });
            actionsTd.appendChild(deleteBtn);
        }

        cells.push(actionsTd);

        var row = el('tr', { id: 'report-row-' + report.id }, cells);
        row.style.cursor = 'pointer';
        row.addEventListener('click', function() {
            toggleRecords(report.id);
        });

        return row;
    }

    // =========================================
    // Record Expansion
    // =========================================

    async function toggleRecords(reportId) {
        var existingDetail = document.getElementById('report-detail-' + reportId);
        if (existingDetail) {
            existingDetail.parentNode.removeChild(existingDetail);
            if (expandedReportId === reportId) {
                expandedReportId = null;
                return;
            }
        }

        // Collapse any other expanded row
        if (expandedReportId !== null && expandedReportId !== reportId) {
            var oldDetail = document.getElementById('report-detail-' + expandedReportId);
            if (oldDetail) oldDetail.parentNode.removeChild(oldDetail);
        }

        expandedReportId = reportId;
        recordsPage = 1;
        loadRecords(reportId);
    }

    async function loadRecords(reportId) {
        var reportRow = document.getElementById('report-row-' + reportId);
        if (!reportRow) return;

        // Remove existing detail row if reloading
        var oldDetail = document.getElementById('report-detail-' + reportId);
        if (oldDetail) oldDetail.parentNode.removeChild(oldDetail);

        var colCount = isAdmin() ? 8 : 7;
        var detailRow = el('tr', { id: 'report-detail-' + reportId, className: 'report-detail-row' });
        var detailTd = el('td', { colspan: String(colCount) });
        detailTd.style.padding = '0';
        detailTd.style.background = 'var(--bg-secondary, #f8fafc)';
        detailRow.appendChild(detailTd);

        // Loading state
        var loadingDiv = el('div', { style: { padding: '16px', textContent: 'Loading records...' } });
        loadingDiv.textContent = 'Loading records...';
        detailTd.appendChild(loadingDiv);

        // Insert after report row
        if (reportRow.nextSibling) {
            reportRow.parentNode.insertBefore(detailRow, reportRow.nextSibling);
        } else {
            reportRow.parentNode.appendChild(detailRow);
        }

        var params = new URLSearchParams();
        params.set('page', recordsPage);
        params.set('page_size', recordsPageSize);

        try {
            var res = await fetch(apiBase() + '/reports/' + reportId + '/records?' + params.toString(), {
                headers: authHeaders()
            });
            if (!res.ok) throw new Error('Failed to load records');
            var data = await res.json();
            var records = data.records || [];
            var totalRecords = data.total || 0;

            clearChildren(detailTd);
            detailTd.appendChild(buildRecordsTable(reportId, records, totalRecords));
        } catch (e) {
            console.error('Error loading records:', e);
            clearChildren(detailTd);
            var errDiv = el('div', { style: { padding: '16px', color: 'var(--accent-danger)' } });
            errDiv.textContent = 'Failed to load records';
            detailTd.appendChild(errDiv);
        }
    }

    function buildRecordsTable(reportId, records, totalRecords) {
        var wrapper = el('div', { style: { padding: '12px 16px 16px' } });

        var header = el('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' } });
        header.appendChild(el('h4', { textContent: 'DMARC Records (' + totalRecords + ' total)', style: { margin: '0', fontSize: '14px' } }));

        var closeBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Close' });
        closeBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            var detail = document.getElementById('report-detail-' + reportId);
            if (detail) detail.parentNode.removeChild(detail);
            expandedReportId = null;
        });
        header.appendChild(closeBtn);
        wrapper.appendChild(header);

        if (records.length === 0) {
            wrapper.appendChild(el('p', { textContent: 'No records found for this report.', style: { color: 'var(--text-secondary)', padding: '12px 0' } }));
            return wrapper;
        }

        var tableWrap = el('div', { className: 'table-container' });
        var table = el('table', {});
        table.style.fontSize = '13px';

        var thead = el('thead', {}, [
            el('tr', {}, [
                el('th', { textContent: 'Source IP' }),
                el('th', { textContent: 'Count' }),
                el('th', { textContent: 'Disposition' }),
                el('th', { textContent: 'DKIM Result' }),
                el('th', { textContent: 'SPF Result' }),
                el('th', { textContent: 'DKIM Domain' }),
                el('th', { textContent: 'SPF Domain' }),
                el('th', { textContent: 'Header From' })
            ])
        ]);
        table.appendChild(thead);

        var tbody = el('tbody', {});
        records.forEach(function(rec) {
            tbody.appendChild(el('tr', {}, [
                el('td', { textContent: rec.source_ip || '-', style: { fontFamily: 'monospace', fontSize: '12px' } }),
                el('td', { textContent: String(rec.count || 0) }),
                el('td', {}, [dispositionBadge(rec.disposition)]),
                el('td', {}, [resultBadge(rec.dkim_result || rec.dkim)]),
                el('td', {}, [resultBadge(rec.spf_result || rec.spf)]),
                el('td', { textContent: rec.dkim_domain || '-' }),
                el('td', { textContent: rec.spf_domain || '-' }),
                el('td', { textContent: rec.header_from || '-' })
            ]));
        });
        table.appendChild(tbody);
        tableWrap.appendChild(table);
        wrapper.appendChild(tableWrap);

        // Records pagination
        var totalPages = Math.ceil(totalRecords / recordsPageSize);
        if (totalPages > 1) {
            var pag = el('div', { className: 'pagination', style: { marginTop: '8px' } });

            var prevBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Prev', disabled: recordsPage <= 1 });
            prevBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                recordsPage--;
                loadRecords(reportId);
            });

            var nextBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Next', disabled: recordsPage >= totalPages });
            nextBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                recordsPage++;
                loadRecords(reportId);
            });

            pag.appendChild(prevBtn);
            pag.appendChild(el('span', { className: 'pagination-info', textContent: 'Page ' + recordsPage + ' of ' + totalPages }));
            pag.appendChild(nextBtn);
            wrapper.appendChild(pag);
        }

        return wrapper;
    }

    // =========================================
    // Pagination
    // =========================================

    function updatePagination() {
        var container = document.getElementById('reports-pagination');
        if (!container) return;
        clearChildren(container);

        var totalPages = Math.ceil(totalReports / pageSize);

        var prevBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Previous', disabled: currentPage <= 1 });
        prevBtn.addEventListener('click', function() {
            currentPage--;
            loadReports();
        });

        var nextBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Next', disabled: currentPage >= totalPages });
        nextBtn.addEventListener('click', function() {
            currentPage++;
            loadReports();
        });

        var pageInfo = el('span', { className: 'pagination-info' });
        if (totalReports > 0) {
            var start = (currentPage - 1) * pageSize + 1;
            var end = Math.min(currentPage * pageSize, totalReports);
            pageInfo.textContent = start + '-' + end + ' of ' + totalReports;
        } else {
            pageInfo.textContent = '0 reports';
        }

        var pagDiv = el('div', { className: 'pagination' }, [prevBtn, pageInfo, nextBtn]);

        // Page size selector
        var pageSizeSelect = el('select', { id: 'reports-page-size', className: 'reports-page-size-select' }, [
            el('option', { value: '10', textContent: '10 per page' }),
            el('option', { value: '20', textContent: '20 per page' }),
            el('option', { value: '50', textContent: '50 per page' })
        ]);
        pageSizeSelect.value = String(pageSize);
        pageSizeSelect.addEventListener('change', function() {
            pageSize = parseInt(pageSizeSelect.value, 10);
            currentPage = 1;
            loadReports();
        });

        var pagRow = el('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' } });
        pagRow.appendChild(pageSizeSelect);
        pagRow.appendChild(pagDiv);

        container.appendChild(pagRow);
    }

    function updateReportCount() {
        var countEl = document.getElementById('reports-total-count');
        if (countEl) countEl.textContent = totalReports + ' reports';
    }

    // =========================================
    // Bulk Selection
    // =========================================

    function updateBulkToolbar() {
        var toolbar = document.getElementById('reports-bulk-toolbar');
        if (!toolbar) return;
        if (selectedReportIds.length > 0) {
            toolbar.hidden = false;
            var count = toolbar.querySelector('.bulk-count');
            if (count) count.textContent = selectedReportIds.length + ' selected';
        } else {
            toolbar.hidden = true;
        }
    }

    async function bulkDeleteReports() {
        if (selectedReportIds.length === 0) return;
        if (!confirm('Delete ' + selectedReportIds.length + ' selected report(s)? This cannot be undone.')) return;

        var failed = 0;
        var succeeded = 0;

        for (var i = 0; i < selectedReportIds.length; i++) {
            try {
                var res = await fetch(apiBase() + '/reports/' + selectedReportIds[i], {
                    method: 'DELETE',
                    headers: authHeaders()
                });
                if (res.ok) {
                    succeeded++;
                } else {
                    failed++;
                }
            } catch (e) {
                failed++;
            }
        }

        if (succeeded > 0) {
            notify(succeeded + ' report(s) deleted', 'success');
        }
        if (failed > 0) {
            notify(failed + ' report(s) failed to delete', 'error');
        }

        selectedReportIds = [];
        loadReports();
    }

    // =========================================
    // Single Delete
    // =========================================

    async function deleteReport(id) {
        try {
            var res = await fetch(apiBase() + '/reports/' + id, {
                method: 'DELETE',
                headers: authHeaders()
            });
            if (!res.ok) throw new Error('Failed to delete report');
            notify('Report deleted', 'success');
            loadReports();
        } catch (e) {
            notify('Failed to delete report', 'error');
        }
    }

    // =========================================
    // Export CSV
    // =========================================

    function exportCSV() {
        var filters = getFilters();
        var params = new URLSearchParams();
        if (filters.days) params.set('days', filters.days);
        if (filters.domain) params.set('domain', filters.domain);

        var url = apiBase() + '/export/reports/csv?' + params.toString();
        var a = document.createElement('a');
        a.href = url;
        a.download = 'dmarc_reports_' + new Date().toISOString().split('T')[0] + '.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        notify('Downloading reports CSV...', 'info');
    }

    // =========================================
    // Render Page Structure
    // =========================================

    function renderPage() {
        var section = getSection();
        if (!section) return;
        clearChildren(section);

        var admin = isAdmin();

        // Page Header
        var headerLeft = el('div', {}, [
            el('h1', { textContent: 'DMARC Reports' }),
            el('p', { className: 'page-description', textContent: 'Browse, filter, and analyze your DMARC aggregate reports.' })
        ]);

        var headerRight = el('div', { style: { display: 'flex', gap: '8px', alignItems: 'center' } });

        var uploadBtn = el('button', { className: 'btn-secondary' }, ['Upload Report']);
        uploadBtn.addEventListener('click', function() {
            if (typeof openUploadModal === 'function') {
                openUploadModal();
            }
        });
        headerRight.appendChild(uploadBtn);

        var exportBtn = el('button', { className: 'btn-secondary' }, ['Export CSV']);
        exportBtn.addEventListener('click', exportCSV);
        headerRight.appendChild(exportBtn);

        var headerRow = el('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' } });
        headerRow.appendChild(headerLeft);
        headerRow.appendChild(headerRight);

        var pageHeader = el('div', { className: 'page-header' }, [headerRow]);

        // Filter Bar
        var filterBar = el('div', { className: 'filter-bar', style: { display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: '20px' } });

        // Domain filter
        var domainSelect = el('select', { id: 'reports-filter-domain' }, [
            el('option', { value: '', textContent: 'All Domains' })
        ]);
        var domainGroup = el('div', { className: 'filter-group' }, [
            el('label', { textContent: 'Domain', htmlFor: 'reports-filter-domain' }),
            domainSelect
        ]);
        filterBar.appendChild(domainGroup);

        // Org name filter
        var orgInput = el('input', { type: 'text', id: 'reports-filter-org', placeholder: 'Organization name' });
        orgInput.style.width = '180px';
        var orgGroup = el('div', { className: 'filter-group' }, [
            el('label', { textContent: 'Organization', htmlFor: 'reports-filter-org' }),
            orgInput
        ]);
        filterBar.appendChild(orgGroup);

        // Date range filter
        var daysSelect = el('select', { id: 'reports-filter-days' }, [
            el('option', { value: '7', textContent: 'Last 7 days' }),
            el('option', { value: '30', textContent: 'Last 30 days' }),
            el('option', { value: '90', textContent: 'Last 90 days' }),
            el('option', { value: '180', textContent: 'Last 180 days' }),
            el('option', { value: '365', textContent: 'Last year' })
        ]);
        daysSelect.value = '30';
        var daysGroup = el('div', { className: 'filter-group' }, [
            el('label', { textContent: 'Date Range', htmlFor: 'reports-filter-days' }),
            daysSelect
        ]);
        filterBar.appendChild(daysGroup);

        // Apply / Clear buttons
        var applyBtn = el('button', { className: 'btn-primary btn-sm', textContent: 'Apply' });
        applyBtn.addEventListener('click', function() {
            currentPage = 1;
            loadReports();
        });

        var clearBtn = el('button', { className: 'btn-ghost btn-sm', textContent: 'Clear' });
        clearBtn.addEventListener('click', function() {
            var ds = document.getElementById('reports-filter-domain');
            var os = document.getElementById('reports-filter-org');
            var dy = document.getElementById('reports-filter-days');
            if (ds) ds.value = '';
            if (os) os.value = '';
            if (dy) dy.value = '30';
            currentPage = 1;
            loadReports();
        });

        var btnGroup = el('div', { className: 'filter-group', style: { display: 'flex', gap: '8px', alignSelf: 'flex-end' } });
        btnGroup.appendChild(applyBtn);
        btnGroup.appendChild(clearBtn);
        filterBar.appendChild(btnGroup);

        // Report count
        var countBadge = el('span', { id: 'reports-total-count', className: 'badge badge-info', textContent: '0 reports', style: { alignSelf: 'flex-end' } });
        filterBar.appendChild(countBadge);

        // Bulk toolbar (admin only)
        var bulkToolbar = null;
        if (admin) {
            bulkToolbar = el('div', { id: 'reports-bulk-toolbar', hidden: true });
            bulkToolbar.style.cssText = 'display:flex;gap:8px;align-items:center;margin-bottom:12px;padding:8px 12px;background:var(--bg-tertiary);border-radius:8px;';
            var bulkCount = el('span', { className: 'bulk-count' });
            bulkCount.style.fontWeight = '600';
            var bulkDeleteBtn = el('button', { className: 'btn-danger btn-sm', textContent: 'Delete Selected' });
            bulkDeleteBtn.addEventListener('click', bulkDeleteReports);
            bulkToolbar.appendChild(bulkCount);
            bulkToolbar.appendChild(bulkDeleteBtn);
        }

        // Table
        var headerCells = [];
        if (admin) {
            var selectAllCb = el('input', { type: 'checkbox', id: 'reports-select-all', title: 'Select all' });
            selectAllCb.addEventListener('change', function() {
                var cbs = section.querySelectorAll('.report-select-cb');
                var check = selectAllCb.checked;
                cbs.forEach(function(cb) {
                    if (cb.checked !== check) {
                        cb.checked = check;
                        cb.dispatchEvent(new Event('change'));
                    }
                });
            });
            headerCells.push(el('th', { style: { width: '40px' } }, [selectAllCb]));
        }
        headerCells.push(makeSortableHeader('Date Range', 'date_end'));
        headerCells.push(makeSortableHeader('Organization', 'org_name'));
        headerCells.push(makeSortableHeader('Domain', 'domain'));
        headerCells.push(makeSortableHeader('Messages', 'total_messages'));
        headerCells.push(makeSortableHeader('Records', 'record_count'));
        headerCells.push(makeSortableHeader('Policy', 'p'));
        headerCells.push(el('th', { textContent: 'Actions' }));

        var tableContainer = el('div', { className: 'table-container' }, [
            el('table', {}, [
                el('thead', {}, [el('tr', {}, headerCells)]),
                el('tbody', { id: 'reports-tbody' })
            ])
        ]);

        // Pagination
        var paginationContainer = el('div', { id: 'reports-pagination', style: { marginTop: '16px' } });

        // Card wrapping the table
        var card = el('div', { className: 'card', style: { padding: '0', overflow: 'hidden' } });
        if (bulkToolbar) {
            var toolbarWrap = el('div', { style: { padding: '12px 16px 0' } });
            toolbarWrap.appendChild(bulkToolbar);
            card.appendChild(toolbarWrap);
        }
        card.appendChild(tableContainer);

        // Page body
        var pageBody = el('div', { className: 'page-body' }, [
            pageHeader,
            filterBar,
            card,
            paginationContainer
        ]);

        section.appendChild(pageBody);
    }

    // =========================================
    // Styles (injected once)
    // =========================================

    function addStyles() {
        if (document.getElementById('reports-page-styles')) return;
        var style = document.createElement('style');
        style.id = 'reports-page-styles';
        style.textContent =
            '.sortable-header:hover { background: var(--bg-tertiary, #f1f5f9); }' +
            '.sort-icon { font-size: 12px; color: var(--text-secondary); margin-left: 4px; }' +
            '.report-detail-row { cursor: default !important; }' +
            '.report-detail-row td { border-top: none !important; }' +
            '.reports-actions-cell { white-space: nowrap; }' +
            '.reports-actions-cell .btn-ghost { margin-right: 4px; }' +
            '.reports-page-size-select { padding: 4px 8px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary); font-size: 13px; }' +
            '#reports-tbody tr:not(.report-detail-row):hover { background: var(--bg-secondary, #f8fafc); }';
        document.head.appendChild(style);
    }

    // =========================================
    // Module Interface
    // =========================================

    var ReportsPage = {
        initialized: false,

        init: function() {
            if (this.initialized) return;
            this.initialized = true;
            addStyles();
            renderPage();
        },

        load: function() {
            loadDomains();
            loadReports();
        },

        destroy: function() {
            expandedReportId = null;
            selectedReportIds = [];
        }
    };

    // Expose on window.DMARC namespace and register with router
    window.DMARC = window.DMARC || {};
    window.DMARC.ReportsPage = ReportsPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('reports', ReportsPage);
    }
})();
