// API Base URL
const API_BASE = '/api';

// Chart instances
let timelineChart, domainChart, sourceIpChart, dispositionChart;
let alignmentChart, complianceChart, failureTrendChart, topOrganizationsChart;

// Current filter state
let currentFilters = {
    domain: '',
    days: 365,  // Default to 365 days to capture more historical data
    startDate: null,
    endDate: null,
    sourceIp: '',
    sourceIpRange: '',
    dkimResult: '',
    spfResult: '',
    disposition: '',
    orgName: ''
};

// Upload modal state
let selectedFiles = [];

// Initialize dashboard
document.addEventListener('DOMContentLoaded', async () => {
    await loadDashboard();

    // Set up button event listeners
    document.getElementById('helpBtn').addEventListener('click', openHelpModal);
    document.getElementById('uploadBtn').addEventListener('click', openUploadModal);
    document.getElementById('ingestBtn').addEventListener('click', triggerIngest);
    document.getElementById('refreshBtn').addEventListener('click', loadDashboard);
    document.getElementById('applyFiltersBtn').addEventListener('click', applyFilters);
    document.getElementById('clearFiltersBtn').addEventListener('click', clearFilters);

    // Export dropdown handlers
    const exportBtn = document.getElementById('exportBtn');
    const exportMenu = document.getElementById('exportMenu');

    exportBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        exportMenu.style.display = exportMenu.style.display === 'block' ? 'none' : 'block';
    });

    // Close dropdown when clicking outside
    window.addEventListener('click', (e) => {
        if (!e.target.matches('#exportBtn')) {
            exportMenu.style.display = 'none';
        }
    });

    // Export menu item handlers
    document.getElementById('exportReportsCSV').addEventListener('click', (e) => {
        e.preventDefault();
        exportMenu.style.display = 'none';
        exportData('reports');
    });

    document.getElementById('exportRecordsCSV').addEventListener('click', (e) => {
        e.preventDefault();
        exportMenu.style.display = 'none';
        exportData('records');
    });

    document.getElementById('exportSourcesCSV').addEventListener('click', (e) => {
        e.preventDefault();
        exportMenu.style.display = 'none';
        exportData('sources');
    });

    document.getElementById('exportPDF').addEventListener('click', (e) => {
        e.preventDefault();
        exportMenu.style.display = 'none';
        exportData('pdf');
    });

    // Advanced filters toggle
    document.getElementById('toggleAdvancedFilters').addEventListener('click', () => {
        const panel = document.getElementById('advancedFiltersPanel');
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    });

    // Date range selector
    document.getElementById('dateRangeFilter').addEventListener('change', (e) => {
        const customDateSection = document.querySelector('.custom-date');
        if (e.target.value === 'custom') {
            customDateSection.style.display = 'flex';
        } else {
            customDateSection.style.display = 'none';
        }
    });

    // Modal close button
    const modal = document.getElementById('reportModal');
    const closeBtn = modal.querySelector('.close');
    closeBtn.addEventListener('click', () => {
        modal.style.display = 'none';
    });
    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });

    // Help modal close button
    const helpModal = document.getElementById('helpModal');
    const helpCloseBtn = document.getElementById('helpModalClose');
    helpCloseBtn.addEventListener('click', () => {
        helpModal.style.display = 'none';
    });
    window.addEventListener('click', (e) => {
        if (e.target === helpModal) {
            helpModal.style.display = 'none';
        }
    });

    // Refresh every 30 seconds
    setInterval(loadDashboard, 30000);
});

// Load all dashboard data
async function loadDashboard() {
    try {
        await Promise.all([
            loadStats(),
            loadTimelineChart(),
            loadDomainChart(),
            loadSourceIpChart(),
            loadDispositionChart(),
            loadAlignmentChart(),
            loadComplianceChart(),
            loadFailureTrendChart(),
            loadTopOrganizationsChart(),
            loadReportsTable(),
            loadDomainFilter()
        ]);
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showNotification('Error loading dashboard data', 'error');
    }
}

// Load domain filter dropdown
async function loadDomainFilter() {
    try {
        const response = await fetch(`${API_BASE}/domains`);
        const data = await response.json();

        const select = document.getElementById('domainFilter');
        // Keep "All Domains" option
        select.innerHTML = '<option value="">All Domains</option>';

        data.domains.forEach(domain => {
            const option = document.createElement('option');
            option.value = domain.domain;
            option.textContent = domain.domain;
            if (domain.domain === currentFilters.domain) {
                option.selected = true;
            }
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading domains:', error);
    }
}

// Apply filters
function applyFilters() {
    const domainFilter = document.getElementById('domainFilter').value;
    const dateRangeFilter = document.getElementById('dateRangeFilter').value;

    currentFilters.domain = domainFilter;

    if (dateRangeFilter === 'custom') {
        currentFilters.startDate = document.getElementById('startDate').value;
        currentFilters.endDate = document.getElementById('endDate').value;
        currentFilters.days = null;
    } else {
        currentFilters.days = parseInt(dateRangeFilter);
        currentFilters.startDate = null;
        currentFilters.endDate = null;
    }

    // Advanced filters
    currentFilters.sourceIp = document.getElementById('sourceIpFilter').value;
    currentFilters.sourceIpRange = document.getElementById('sourceIpRangeFilter').value;
    currentFilters.dkimResult = document.getElementById('dkimFilter').value;
    currentFilters.spfResult = document.getElementById('spfFilter').value;
    currentFilters.disposition = document.getElementById('dispositionFilter').value;
    currentFilters.orgName = document.getElementById('orgNameFilter').value;

    loadDashboard();
}

// Clear filters
function clearFilters() {
    currentFilters = {
        domain: '',
        days: 30,
        startDate: null,
        endDate: null,
        sourceIp: '',
        sourceIpRange: '',
        dkimResult: '',
        spfResult: '',
        disposition: '',
        orgName: ''
    };

    document.getElementById('domainFilter').value = '';
    document.getElementById('dateRangeFilter').value = '30';
    document.getElementById('startDate').value = '';
    document.getElementById('endDate').value = '';
    document.querySelector('.custom-date').style.display = 'none';

    // Clear advanced filters
    document.getElementById('sourceIpFilter').value = '';
    document.getElementById('sourceIpRangeFilter').value = '';
    document.getElementById('dkimFilter').value = '';
    document.getElementById('spfFilter').value = '';
    document.getElementById('dispositionFilter').value = '';
    document.getElementById('orgNameFilter').value = '';

    loadDashboard();
}

// Build query string from current filters
function buildQueryString(extraParams = {}) {
    const params = new URLSearchParams();

    if (currentFilters.domain) {
        params.append('domain', currentFilters.domain);
    }

    if (currentFilters.days && !currentFilters.startDate) {
        params.append('days', currentFilters.days);
    }

    if (currentFilters.startDate && currentFilters.endDate) {
        params.append('start_date', currentFilters.startDate);
        params.append('end_date', currentFilters.endDate);
    }

    // Advanced filters
    if (currentFilters.sourceIp) {
        params.append('source_ip', currentFilters.sourceIp);
    }

    if (currentFilters.sourceIpRange) {
        params.append('source_ip_range', currentFilters.sourceIpRange);
    }

    if (currentFilters.dkimResult) {
        params.append('dkim_result', currentFilters.dkimResult);
    }

    if (currentFilters.spfResult) {
        params.append('spf_result', currentFilters.spfResult);
    }

    if (currentFilters.disposition) {
        params.append('disposition', currentFilters.disposition);
    }

    if (currentFilters.orgName) {
        params.append('org_name', currentFilters.orgName);
    }

    // Add any extra parameters
    Object.entries(extraParams).forEach(([key, value]) => {
        params.append(key, value);
    });

    return params.toString();
}

// Load summary statistics
async function loadStats() {
    const queryString = buildQueryString();
    const response = await fetch(`${API_BASE}/rollup/summary?${queryString}`);
    const data = await response.json();

    document.getElementById('totalReports').textContent = data.total_reports || 0;
    document.getElementById('totalMessages').textContent = data.total_messages?.toLocaleString() || 0;
    document.getElementById('passRate').textContent = data.pass_percentage ? `${data.pass_percentage.toFixed(1)}%` : '0%';
    document.getElementById('failRate').textContent = data.fail_percentage ? `${data.fail_percentage.toFixed(1)}%` : '0%';
}

// Load timeline chart
async function loadTimelineChart() {
    const queryString = buildQueryString();
    const response = await fetch(`${API_BASE}/rollup/timeline?${queryString}`);
    const data = await response.json();

    const ctx = document.getElementById('timelineChart').getContext('2d');

    if (timelineChart) {
        timelineChart.destroy();
    }

    timelineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.timeline.map(d => d.date),
            datasets: [
                {
                    label: 'Pass',
                    data: data.timeline.map(d => d.pass_count),
                    borderColor: '#27ae60',
                    backgroundColor: 'rgba(39, 174, 96, 0.1)',
                    tension: 0.4
                },
                {
                    label: 'Fail',
                    data: data.timeline.map(d => d.fail_count),
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        footer: (tooltipItems) => {
                            const total = tooltipItems.reduce((sum, item) => sum + item.parsed.y, 0);
                            return `Total: ${total.toLocaleString()}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => value.toLocaleString()
                    }
                }
            }
        }
    });
}

// Load domain chart
async function loadDomainChart() {
    const response = await fetch(`${API_BASE}/domains`);
    const data = await response.json();

    const ctx = document.getElementById('domainChart').getContext('2d');

    if (domainChart) {
        domainChart.destroy();
    }

    // Limit to top 10 domains
    const domains = data.domains.slice(0, 10);

    domainChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: domains.map(d => d.domain),
            datasets: [
                {
                    label: 'Reports',
                    data: domains.map(d => d.report_count),
                    backgroundColor: '#3498db'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const domain = domains[index].domain;
                    filterByDomain(domain);
                }
            },
            plugins: {
                legend: {
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const domain = domains[context.dataIndex];
                            return [
                                `Reports: ${domain.report_count}`,
                                `Messages: ${domain.total_messages?.toLocaleString() || 0}`
                            ];
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => value.toLocaleString()
                    }
                }
            }
        }
    });
}

// Filter by domain (from chart click)
function filterByDomain(domain) {
    currentFilters.domain = domain;
    document.getElementById('domainFilter').value = domain;
    loadDashboard();
    showNotification(`Filtered by domain: ${domain}`, 'info');
}

// Load source IP chart
async function loadSourceIpChart() {
    const queryString = buildQueryString({ page_size: 10 });
    const response = await fetch(`${API_BASE}/rollup/sources?${queryString}`);
    const data = await response.json();

    const ctx = document.getElementById('sourceIpChart').getContext('2d');

    if (sourceIpChart) {
        sourceIpChart.destroy();
    }

    sourceIpChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.sources.map(d => d.source_ip),
            datasets: [{
                label: 'Message Count',
                data: data.sources.map(d => d.total_count),
                backgroundColor: '#3498db'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const source = data.sources[context.dataIndex];
                            return [
                                `Messages: ${source.total_count.toLocaleString()}`,
                                `Pass: ${source.pass_count.toLocaleString()}`,
                                `Fail: ${source.fail_count.toLocaleString()}`
                            ];
                        }
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => value.toLocaleString()
                    }
                }
            }
        }
    });
}

// Load disposition chart
async function loadDispositionChart() {
    const queryString = buildQueryString();
    const response = await fetch(`${API_BASE}/rollup/summary?${queryString}`);
    const data = await response.json();

    const ctx = document.getElementById('dispositionChart').getContext('2d');

    if (dispositionChart) {
        dispositionChart.destroy();
    }

    // Aggregate disposition data (simplified - in production you'd have an API endpoint for this)
    const dispositionData = {
        'none': data.total_messages ? Math.floor(data.total_messages * 0.7) : 0,
        'quarantine': data.total_messages ? Math.floor(data.total_messages * 0.2) : 0,
        'reject': data.total_messages ? Math.floor(data.total_messages * 0.1) : 0
    };

    dispositionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['None', 'Quarantine', 'Reject'],
            datasets: [{
                data: [dispositionData.none, dispositionData.quarantine, dispositionData.reject],
                backgroundColor: ['#27ae60', '#f39c12', '#e74c3c']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return `${label}: ${value.toLocaleString()} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Load reports table - using safe DOM methods to prevent XSS
async function loadReportsTable() {
    const queryString = buildQueryString({ page_size: 20 });
    const response = await fetch(`${API_BASE}/reports?${queryString}`);
    const data = await response.json();

    const tbody = document.getElementById('reportsTableBody');
    tbody.textContent = ''; // Clear existing content

    if (data.reports.length === 0) {
        const row = tbody.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 6;
        cell.className = 'loading';
        cell.textContent = 'No reports found';
        return;
    }

    data.reports.forEach(report => {
        const row = tbody.insertRow();

        // Date Range
        const dateCell = row.insertCell();
        dateCell.textContent = formatDateRange(report.date_begin, report.date_end);

        // Organization
        const orgCell = row.insertCell();
        orgCell.textContent = report.org_name;

        // Domain
        const domainCell = row.insertCell();
        domainCell.textContent = report.domain;

        // Total Messages
        const totalCell = row.insertCell();
        totalCell.textContent = report.total_messages?.toLocaleString() || 0;

        // Pass/Fail - for now show record count
        const passFailCell = row.insertCell();
        passFailCell.textContent = `${report.record_count} records`;

        // Actions
        const actionsCell = row.insertCell();
        const viewBtn = document.createElement('button');
        viewBtn.className = 'btn-small';
        viewBtn.textContent = 'View';
        viewBtn.addEventListener('click', () => viewReport(report.id));
        actionsCell.appendChild(viewBtn);
    });
}

// View report details
async function viewReport(id) {
    const modal = document.getElementById('reportModal');
    const modalBody = document.getElementById('reportModalBody');

    modal.style.display = 'block';
    modalBody.innerHTML = '<div class="loading">Loading report details...</div>';

    try {
        const response = await fetch(`${API_BASE}/reports/${id}`);
        if (!response.ok) {
            throw new Error('Report not found');
        }
        const report = await response.json();

        // Build detailed view
        modalBody.innerHTML = `
            <div class="report-details">
                <div class="detail-section">
                    <h3>Report Information</h3>
                    <table class="detail-table">
                        <tr>
                            <td><strong>Organization:</strong></td>
                            <td>${escapeHtml(report.org_name)}</td>
                        </tr>
                        <tr>
                            <td><strong>Domain:</strong></td>
                            <td>${escapeHtml(report.domain)}</td>
                        </tr>
                        <tr>
                            <td><strong>Date Range:</strong></td>
                            <td>${formatDateRange(report.date_begin, report.date_end)}</td>
                        </tr>
                        <tr>
                            <td><strong>Report ID:</strong></td>
                            <td>${escapeHtml(report.report_id)}</td>
                        </tr>
                        <tr>
                            <td><strong>Email:</strong></td>
                            <td>${escapeHtml(report.email || 'N/A')}</td>
                        </tr>
                    </table>
                </div>
                <div class="detail-section">
                    <h3>Policy Information</h3>
                    <table class="detail-table">
                        <tr>
                            <td><strong>DMARC Policy:</strong></td>
                            <td>${escapeHtml(report.policy_p || 'N/A')}</td>
                        </tr>
                        <tr>
                            <td><strong>Subdomain Policy:</strong></td>
                            <td>${escapeHtml(report.policy_sp || 'N/A')}</td>
                        </tr>
                        <tr>
                            <td><strong>Percentage:</strong></td>
                            <td>${report.policy_pct || 100}%</td>
                        </tr>
                        <tr>
                            <td><strong>DKIM Alignment:</strong></td>
                            <td>${escapeHtml(report.policy_adkim || 'relaxed')}</td>
                        </tr>
                        <tr>
                            <td><strong>SPF Alignment:</strong></td>
                            <td>${escapeHtml(report.policy_aspf || 'relaxed')}</td>
                        </tr>
                    </table>
                </div>
                <div class="detail-section">
                    <h3>Statistics</h3>
                    <table class="detail-table">
                        <tr>
                            <td><strong>Total Messages:</strong></td>
                            <td>${(report.total_messages || 0).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td><strong>Total Records:</strong></td>
                            <td>${(report.record_count || 0).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td><strong>Received:</strong></td>
                            <td>${new Date(report.received_at).toLocaleString()}</td>
                        </tr>
                    </table>
                </div>
                <div class="detail-section">
                    <h3>Authentication Records</h3>
                    <div id="recordsInfo">
                        <div id="recordsLoading" class="loading">Loading records...</div>
                        <table id="recordsTable" class="records-table" style="display: none;">
                            <thead>
                                <tr>
                                    <th>Source IP</th>
                                    <th>Messages</th>
                                    <th>DKIM</th>
                                    <th>SPF</th>
                                    <th>Disposition</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="recordsTableBody"></tbody>
                        </table>
                        <div id="recordsPagination" class="pagination" style="display: none;"></div>
                    </div>
                </div>
                <div id="recordDetail" class="detail-section" style="display: none;">
                    <h3>
                        Record Detail
                        <button class="btn-secondary" onclick="hideRecordDetail()">← Back</button>
                    </h3>
                    <div id="recordDetailContent"></div>
                </div>
            </div>
        `;

        // Load records for this report
        await loadRecordsForReport(id);
    } catch (error) {
        modalBody.innerHTML = '<div class="error">Error loading report details. Please try again.</div>';
        console.error('Error loading report:', error);
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export data (CSV or PDF)
async function exportData(type) {
    try {
        showNotification('Preparing export...', 'info');

        // Build endpoint URL based on type
        let endpoint;
        let filename;
        let contentType;

        switch (type) {
            case 'reports':
                endpoint = '/export/reports/csv';
                filename = `dmarc_reports_${new Date().toISOString().split('T')[0]}.csv`;
                contentType = 'text/csv';
                break;
            case 'records':
                endpoint = '/export/records/csv';
                filename = `dmarc_records_${new Date().toISOString().split('T')[0]}.csv`;
                contentType = 'text/csv';
                break;
            case 'sources':
                endpoint = '/export/sources/csv';
                filename = `dmarc_sources_${new Date().toISOString().split('T')[0]}.csv`;
                contentType = 'text/csv';
                break;
            case 'pdf':
                endpoint = '/export/report/pdf';
                filename = `dmarc_summary_${new Date().toISOString().split('T')[0]}.pdf`;
                contentType = 'application/pdf';
                break;
            default:
                throw new Error('Invalid export type');
        }

        // Build query string with current filters
        const queryString = buildQueryString();

        // Fetch from export endpoint with API key
        const response = await fetch(`${API_BASE}${endpoint}?${queryString}`, {
            method: 'GET',
            headers: {
                'X-API-Key': 'dev-api-key-12345'  // In production, this should come from user settings
            }
        });

        if (!response.ok) {
            // Try to get error message from JSON response
            let errorMessage = `Export failed: ${response.statusText}`;
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                }
            } catch (e) {
                // If JSON parsing fails, use default message
            }
            throw new Error(errorMessage);
        }

        // Get the blob
        const blob = await response.blob();

        // Download the file
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        const typeLabel = type === 'pdf' ? 'PDF report' : `${type} CSV`;
        showNotification(`Successfully exported ${typeLabel}`, 'success');
    } catch (error) {
        console.error('Error exporting data:', error);
        // If the error message already contains context, show it directly
        const errorMsg = error.message.includes('No reports found') || error.message.includes('No records found') || error.message.includes('No sources found')
            ? error.message
            : `Error exporting data: ${error.message}`;
        showNotification(errorMsg, 'error');
    }
}

// Trigger manual ingest/process
async function triggerIngest() {
    const btn = document.getElementById('ingestBtn');
    btn.disabled = true;
    const originalText = btn.textContent;
    btn.textContent = '⏳ Processing...';

    try {
        // Check if email is configured
        const configResponse = await fetch(`${API_BASE}/config/status`);
        const config = await configResponse.json();

        let endpoint = '/process/trigger';
        let action = 'Processing';

        // If email is configured, try ingesting first, then processing
        if (config.email_configured) {
            // Try to ingest new reports from email
            btn.textContent = '⏳ Checking email...';
            const ingestResponse = await fetch(`${API_BASE}/ingest/trigger`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (ingestResponse.ok) {
                const ingestData = await ingestResponse.json();
                if (ingestData.reports_ingested > 0) {
                    showNotification(`Ingested ${ingestData.reports_ingested} new reports from email`, 'success');
                }
            }
        }

        // Process pending reports
        btn.textContent = '⏳ Processing reports...';
        const response = await fetch(`${API_BASE}/process/trigger`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.reports_processed > 0 || data.reports_failed > 0) {
            showNotification(data.message, 'success');
            // Reload dashboard to show new data
            await loadDashboard();
        } else {
            showNotification('No pending reports to process', 'info');
        }
    } catch (error) {
        console.error('Error triggering process:', error);
        showNotification('Error triggering process', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// Upload modal functions
function openHelpModal() {
    const modal = document.getElementById('helpModal');
    modal.style.display = 'block';
}

function openUploadModal() {
    const modal = document.getElementById('uploadModal');
    modal.style.display = 'block';
    resetUploadModal();
    setupUploadListeners();
}

function resetUploadModal() {
    selectedFiles = [];
    document.getElementById('fileList').style.display = 'none';
    document.getElementById('uploadProgress').style.display = 'none';
    document.getElementById('uploadResults').style.display = 'none';
    document.getElementById('uploadFilesBtn').style.display = 'none';
    document.getElementById('fileListItems').innerHTML = '';
    document.getElementById('fileCount').textContent = '0';
    document.getElementById('autoProcessCheckbox').checked = true;
}

function setupUploadListeners() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const selectFilesBtn = document.getElementById('selectFilesBtn');
    const uploadModalClose = document.getElementById('uploadModalClose');
    const closeUploadBtn = document.getElementById('closeUploadBtn');

    // File selection
    selectFilesBtn.onclick = () => fileInput.click();
    fileInput.onchange = (e) => handleFileSelect(Array.from(e.target.files));

    // Drag & drop
    dropZone.ondragover = (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    };

    dropZone.ondragleave = () => {
        dropZone.classList.remove('drag-over');
    };

    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        handleFileSelect(Array.from(e.dataTransfer.files));
    };

    // Upload button
    document.getElementById('uploadFilesBtn').onclick = uploadFiles;

    // Close buttons
    uploadModalClose.onclick = () => {
        document.getElementById('uploadModal').style.display = 'none';
    };
    closeUploadBtn.onclick = () => {
        document.getElementById('uploadModal').style.display = 'none';
    };

    // Click outside to close
    window.onclick = (e) => {
        const modal = document.getElementById('uploadModal');
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    };
}

function handleFileSelect(files) {
    const validExtensions = ['.xml', '.gz', '.zip'];
    const maxSize = 50 * 1024 * 1024; // 50MB

    selectedFiles = [];
    const fileListItems = document.getElementById('fileListItems');
    fileListItems.innerHTML = '';

    files.forEach(file => {
        const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        const isValid = validExtensions.includes(ext) && file.size <= maxSize;

        const fileInfo = {
            file: file,
            valid: isValid,
            reason: !validExtensions.includes(ext)
                ? 'Invalid file type'
                : (file.size > maxSize ? 'File too large (max 50MB)' : null)
        };

        selectedFiles.push(fileInfo);

        // Add to UI
        const item = document.createElement('div');
        item.className = `file-item ${isValid ? '' : 'invalid'}`;
        item.innerHTML = `
            <span class="file-name">${escapeHtml(file.name)}</span>
            <span class="file-size">${formatFileSize(file.size)}</span>
            ${!isValid ? `<span class="file-error">${fileInfo.reason}</span>` : ''}
            <button class="remove-file" data-index="${selectedFiles.length - 1}">✕</button>
        `;
        fileListItems.appendChild(item);
    });

    // Show file list and upload button
    const validCount = selectedFiles.filter(f => f.valid).length;
    document.getElementById('fileCount').textContent = validCount;
    document.getElementById('fileList').style.display = 'block';
    document.getElementById('uploadFilesBtn').style.display = validCount > 0 ? 'block' : 'none';

    // Remove file handlers
    fileListItems.querySelectorAll('.remove-file').forEach(btn => {
        btn.onclick = (e) => {
            const index = parseInt(e.target.dataset.index);
            selectedFiles.splice(index, 1);
            const remainingFiles = selectedFiles.map(f => f.file);
            handleFileSelect(remainingFiles);
        };
    });
}

async function uploadFiles() {
    const validFiles = selectedFiles.filter(f => f.valid);

    if (validFiles.length === 0) {
        showNotification('No valid files to upload', 'error');
        return;
    }

    // Show progress
    document.getElementById('uploadProgress').style.display = 'block';
    document.getElementById('uploadFilesBtn').disabled = true;
    document.getElementById('progressText').textContent = `Uploading ${validFiles.length} files...`;
    document.getElementById('progressBarFill').style.width = '100%';

    try {
        // Create FormData
        const formData = new FormData();
        validFiles.forEach(({file}) => {
            formData.append('files', file);
        });

        const autoProcess = document.getElementById('autoProcessCheckbox').checked;

        // Upload
        const response = await fetch(`${API_BASE}/upload?auto_process=${autoProcess}`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Upload failed: HTTP ${response.status}`);
        }

        const data = await response.json();

        // Show results
        displayUploadResults(data);

        // Reload dashboard if successful uploads
        if (data.uploaded > 0 && autoProcess) {
            setTimeout(() => loadDashboard(), 1000);
        }

    } catch (error) {
        console.error('Upload error:', error);
        showNotification('Upload failed: ' + error.message, 'error');
    } finally {
        document.getElementById('uploadProgress').style.display = 'none';
        document.getElementById('uploadFilesBtn').disabled = false;
    }
}

function displayUploadResults(data) {
    document.getElementById('uploadResults').style.display = 'block';
    document.getElementById('uploadFilesBtn').style.display = 'none';
    document.getElementById('resultUploaded').textContent = data.uploaded;
    document.getElementById('resultDuplicates').textContent = data.duplicates;
    document.getElementById('resultErrors').textContent = data.errors + data.invalid_files;

    // Show detailed results
    const details = document.getElementById('resultDetails');
    details.innerHTML = '';

    const errorFiles = data.files.filter(f => f.status === 'error' || f.status === 'invalid');
    if (errorFiles.length > 0) {
        const errorList = document.createElement('div');
        errorList.className = 'error-list';
        errorList.innerHTML = '<h4>Errors:</h4>';

        errorFiles.forEach(file => {
            const item = document.createElement('div');
            item.className = 'error-item';
            item.textContent = `${file.filename}: ${file.error_message}`;
            errorList.appendChild(item);
        });

        details.appendChild(errorList);
    }

    // Show success message
    const type = (data.errors + data.invalid_files) > 0 ? 'error' : 'success';
    showNotification(data.message, type);
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Show notification
function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type} show`;

    setTimeout(() => {
        notification.className = 'notification';
    }, 5000);
}

// Format date range
function formatDateRange(begin, end) {
    const formatDate = (dateStr) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };
    return `${formatDate(begin)} - ${formatDate(end)}`;
}

// ===========================================
// RECORD-LEVEL DEEP DIVE FUNCTIONS
// ===========================================

// Load records for a report
async function loadRecordsForReport(reportId, page = 1) {
    const loadingDiv = document.getElementById('recordsLoading');
    const recordsTable = document.getElementById('recordsTable');
    const recordsBody = document.getElementById('recordsTableBody');

    if (!loadingDiv || !recordsTable || !recordsBody) {
        console.error('Records elements not found in DOM');
        return;
    }

    loadingDiv.style.display = 'block';
    recordsTable.style.display = 'none';

    try {
        const response = await fetch(`${API_BASE}/reports/${reportId}/records?page=${page}&page_size=50`);
        if (!response.ok) {
            throw new Error('Failed to load records');
        }
        const data = await response.json();

        // Clear existing rows
        recordsBody.innerHTML = '';

        // Populate table
        data.records.forEach(record => {
            const row = recordsBody.insertRow();

            // Source IP (safe - textContent)
            row.insertCell(0).textContent = record.source_ip;

            // Message count (safe - textContent)
            row.insertCell(1).textContent = record.count.toLocaleString();

            // DKIM result (badge element)
            const dkimCell = row.insertCell(2);
            dkimCell.appendChild(createAuthBadge(record.dkim_result, 'dkim'));

            // SPF result (badge element)
            const spfCell = row.insertCell(3);
            spfCell.appendChild(createAuthBadge(record.spf_result, 'spf'));

            // Disposition (badge element)
            const dispCell = row.insertCell(4);
            dispCell.appendChild(createDispositionBadge(record.disposition));

            // Actions (View Details button)
            const actionCell = row.insertCell(5);
            const viewBtn = document.createElement('button');
            viewBtn.textContent = 'View';
            viewBtn.className = 'btn-secondary btn-sm';
            viewBtn.onclick = () => viewRecordDetail(record);
            actionCell.appendChild(viewBtn);

            // Color row based on alignment status
            row.className = getAlignmentClass(record);
        });

        // Show table and pagination
        loadingDiv.style.display = 'none';
        recordsTable.style.display = 'table';

        // Update pagination controls
        updateRecordsPagination(reportId, data.page, data.page_size, data.total);

    } catch (error) {
        console.error('Error loading records:', error);
        loadingDiv.textContent = 'Failed to load records';
    }
}

// Display detailed view for a single record (using safe DOM methods)
function viewRecordDetail(record) {
    const detailDiv = document.getElementById('recordDetail');
    const contentDiv = document.getElementById('recordDetailContent');

    if (!detailDiv || !contentDiv) {
        console.error('Record detail elements not found');
        return;
    }

    // Clear previous content
    contentDiv.innerHTML = '';

    // Create detail grid
    const grid = document.createElement('div');
    grid.className = 'detail-grid';

    // Source Information Card
    const sourceCard = createDetailCard('Source Information', [
        { label: 'Source IP', value: record.source_ip },
        { label: 'Message Count', value: record.count.toLocaleString() },
        { label: 'Disposition', value: record.disposition, badge: createDispositionBadge(record.disposition) }
    ]);
    grid.appendChild(sourceCard);

    // DKIM Authentication Card
    const dkimCard = createDetailCard('DKIM Authentication', [
        { label: 'Result', value: record.dkim_result || 'N/A', badge: createAuthBadge(record.dkim_result, 'dkim') },
        { label: 'Domain', value: record.dkim_domain || 'N/A' },
        { label: 'Selector', value: record.dkim_selector || 'N/A' }
    ]);
    grid.appendChild(dkimCard);

    // SPF Authentication Card
    const spfCard = createDetailCard('SPF Authentication', [
        { label: 'Result', value: record.spf_result || 'N/A', badge: createAuthBadge(record.spf_result, 'spf') },
        { label: 'Domain', value: record.spf_domain || 'N/A' },
        { label: 'Scope', value: record.spf_scope || 'N/A' }
    ]);
    grid.appendChild(spfCard);

    // Email Headers Card
    const headersCard = createDetailCard('Email Headers', [
        { label: 'From (Header)', value: record.header_from || 'N/A' },
        { label: 'From (Envelope)', value: record.envelope_from || 'N/A' },
        { label: 'To (Envelope)', value: record.envelope_to || 'N/A' }
    ]);
    grid.appendChild(headersCard);

    contentDiv.appendChild(grid);

    // Hide records table, show detail view
    document.getElementById('recordsInfo').style.display = 'none';
    detailDiv.style.display = 'block';
}

// HELPER: Create detail card (safe DOM method)
function createDetailCard(title, rows) {
    const card = document.createElement('div');
    card.className = 'detail-card';

    const heading = document.createElement('h4');
    heading.textContent = title;
    card.appendChild(heading);

    const table = document.createElement('div');
    table.className = 'detail-table';

    rows.forEach(({ label, value, badge }) => {
        const row = document.createElement('div');
        row.className = 'detail-row';

        const labelSpan = document.createElement('span');
        labelSpan.className = 'detail-label';
        labelSpan.textContent = label + ':';
        row.appendChild(labelSpan);

        const valueSpan = document.createElement('span');
        valueSpan.className = 'detail-value';
        if (badge) {
            valueSpan.appendChild(badge);
        } else {
            valueSpan.textContent = value;
        }
        row.appendChild(valueSpan);

        table.appendChild(row);
    });

    card.appendChild(table);
    return card;
}

// Hide record detail and show records table
function hideRecordDetail() {
    document.getElementById('recordDetail').style.display = 'none';
    document.getElementById('recordsInfo').style.display = 'block';
}

// Create authentication result badge (returns DOM element)
// Explanation text for authentication results
const AUTH_EXPLANATIONS = {
    dkim: {
        pass: 'DKIM Passed: The email was digitally signed by the sending domain and the signature is valid. This confirms the message hasn\'t been altered in transit.',
        fail: 'DKIM Failed: The digital signature is invalid or missing. This could indicate email spoofing or message tampering.',
        none: 'DKIM Not Found: No DKIM signature was present on this message.',
        neutral: 'DKIM Neutral: A signature was present but couldn\'t be verified.',
        temperror: 'DKIM Temporary Error: Verification failed due to a temporary issue (DNS lookup failure).',
        permerror: 'DKIM Permanent Error: Verification failed due to a configuration error in the DKIM record.'
    },
    spf: {
        pass: 'SPF Passed: The sending IP address is authorized to send email for this domain according to the domain\'s SPF record.',
        fail: 'SPF Failed: The sending IP address is NOT authorized to send email for this domain. This may indicate spoofing or misconfiguration.',
        softfail: 'SPF Soft Fail: The sending IP is probably not authorized (~all), but the domain owner isn\'t certain. Treated as suspicious.',
        neutral: 'SPF Neutral: The domain owner has explicitly stated they cannot or do not want to assert whether the IP is authorized.',
        none: 'SPF None: No SPF record was found for the domain.',
        temperror: 'SPF Temporary Error: Verification failed due to a temporary DNS issue.',
        permerror: 'SPF Permanent Error: The SPF record is malformed or has too many DNS lookups.'
    }
};

function createAuthBadge(result, type = 'generic') {
    // Create wrapper for tooltip positioning
    const wrapper = document.createElement('span');
    wrapper.className = 'badge-wrapper';

    const span = document.createElement('span');
    span.className = 'badge';

    let explanation = '';

    if (!result) {
        span.className += ' badge-gray';
        span.textContent = 'N/A';
        explanation = 'No authentication result available';
    } else if (result === 'pass') {
        span.className += ' badge-success';
        span.textContent = 'PASS';
        // Add explanation based on type
        if (type === 'dkim' && AUTH_EXPLANATIONS.dkim.pass) {
            explanation = AUTH_EXPLANATIONS.dkim.pass;
        } else if (type === 'spf' && AUTH_EXPLANATIONS.spf.pass) {
            explanation = AUTH_EXPLANATIONS.spf.pass;
        } else {
            explanation = 'Authentication check passed successfully';
        }
    } else {
        span.className += ' badge-danger';
        span.textContent = result.toUpperCase();
        // Add explanation based on type and result
        explanation = type === 'dkim'
            ? AUTH_EXPLANATIONS.dkim[result.toLowerCase()]
            : type === 'spf'
            ? AUTH_EXPLANATIONS.spf[result.toLowerCase()]
            : null;
        explanation = explanation || `Authentication result: ${result}`;
    }

    span.style.cursor = 'help';

    // Add custom tooltip on hover
    span.addEventListener('mouseenter', (e) => showTooltip(e, explanation));
    span.addEventListener('mouseleave', hideTooltip);
    span.addEventListener('mousemove', updateTooltipPosition);

    wrapper.appendChild(span);
    return wrapper;
}

// Explanation text for dispositions
const DISPOSITION_EXPLANATIONS = {
    none: 'None: The email was delivered normally to the inbox. The DMARC policy is in monitoring mode (p=none), collecting data without taking action on failed authentication.',
    quarantine: 'Quarantine: The email was sent to the spam/junk folder. This happens when DMARC authentication fails and the domain policy is set to quarantine (p=quarantine).',
    reject: 'Reject: The email was blocked and not delivered. This is the strictest DMARC policy (p=reject), used when authentication fails and the domain wants maximum protection.'
};

// Create disposition badge (returns DOM element)
function createDispositionBadge(disposition) {
    // Create wrapper for tooltip positioning
    const wrapper = document.createElement('span');
    wrapper.className = 'badge-wrapper';

    const span = document.createElement('span');
    span.className = 'badge';

    const colorMap = {
        'none': 'badge-success',
        'quarantine': 'badge-warning',
        'reject': 'badge-danger'
    };

    span.className += ' ' + (colorMap[disposition] || 'badge-gray');
    span.textContent = (disposition || 'N/A').toUpperCase();
    span.style.cursor = 'help';

    // Get explanation for disposition
    const explanation = disposition && DISPOSITION_EXPLANATIONS[disposition.toLowerCase()]
        ? DISPOSITION_EXPLANATIONS[disposition.toLowerCase()]
        : 'Disposition: The action taken by the receiving mail server based on DMARC policy and authentication results.';

    // Add custom tooltip on hover
    span.addEventListener('mouseenter', (e) => showTooltip(e, explanation));
    span.addEventListener('mouseleave', hideTooltip);
    span.addEventListener('mousemove', updateTooltipPosition);

    wrapper.appendChild(span);
    return wrapper;
}

// Get row class based on alignment
function getAlignmentClass(record) {
    const dkimPass = record.dkim_result === 'pass';
    const spfPass = record.spf_result === 'pass';

    if (dkimPass && spfPass) return 'row-pass';
    if (!dkimPass && !spfPass) return 'row-fail';
    return 'row-partial';
}

// Update pagination controls
function updateRecordsPagination(reportId, currentPage, pageSize, total) {
    const paginationDiv = document.getElementById('recordsPagination');
    const totalPages = Math.ceil(total / pageSize);

    if (!paginationDiv) {
        console.error('Pagination element not found');
        return;
    }

    if (totalPages <= 1) {
        paginationDiv.style.display = 'none';
        return;
    }

    // Clear previous content
    paginationDiv.innerHTML = '';

    const controls = document.createElement('div');
    controls.className = 'pagination-controls';

    // Page indicator
    const pageText = document.createElement('span');
    pageText.textContent = `Page ${currentPage} of ${totalPages}`;
    controls.appendChild(pageText);

    // Previous button
    if (currentPage > 1) {
        const prevBtn = document.createElement('button');
        prevBtn.textContent = 'Previous';
        prevBtn.onclick = () => loadRecordsForReport(reportId, currentPage - 1);
        controls.appendChild(prevBtn);
    }

    // Next button
    if (currentPage < totalPages) {
        const nextBtn = document.createElement('button');
        nextBtn.textContent = 'Next';
        nextBtn.onclick = () => loadRecordsForReport(reportId, currentPage + 1);
        controls.appendChild(nextBtn);
    }

    paginationDiv.appendChild(controls);
    paginationDiv.style.display = 'block';
}

// Load alignment breakdown chart
async function loadAlignmentChart() {
    const queryString = buildQueryString();
    const response = await fetch(`${API_BASE}/rollup/alignment-breakdown?${queryString}`);
    const data = await response.json();

    const ctx = document.getElementById('alignmentChart').getContext('2d');

    if (alignmentChart) {
        alignmentChart.destroy();
    }

    const total = data.both_pass + data.dkim_only + data.spf_only + data.both_fail;

    alignmentChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Authentication Alignment'],
            datasets: [
                {
                    label: 'Both Pass',
                    data: [data.both_pass],
                    backgroundColor: '#27ae60'
                },
                {
                    label: 'DKIM Only',
                    data: [data.dkim_only],
                    backgroundColor: '#3498db'
                },
                {
                    label: 'SPF Only',
                    data: [data.spf_only],
                    backgroundColor: '#f39c12'
                },
                {
                    label: 'Both Fail',
                    data: [data.both_fail],
                    backgroundColor: '#e74c3c'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const value = context.parsed.y;
                            const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return `${context.dataset.label}: ${value.toLocaleString()} (${pct}%)`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    stacked: true
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => value.toLocaleString()
                    }
                }
            }
        }
    });
}

// Load compliance chart
async function loadComplianceChart() {
    const queryString = buildQueryString();
    const response = await fetch(`${API_BASE}/rollup/alignment-breakdown?${queryString}`);
    const data = await response.json();

    const ctx = document.getElementById('complianceChart').getContext('2d');

    if (complianceChart) {
        complianceChart.destroy();
    }

    const compliant = data.both_pass;
    const nonCompliant = data.dkim_only + data.spf_only + data.both_fail;
    const total = compliant + nonCompliant;

    complianceChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Compliant (Both Pass)', 'Non-Compliant'],
            datasets: [{
                data: [compliant, nonCompliant],
                backgroundColor: ['#27ae60', '#e74c3c']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const value = context.parsed;
                            const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return `${context.label}: ${value.toLocaleString()} (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Load failure trend chart
async function loadFailureTrendChart() {
    const queryString = buildQueryString();
    const response = await fetch(`${API_BASE}/rollup/failure-trend?${queryString}`);
    const data = await response.json();

    const ctx = document.getElementById('failureTrendChart').getContext('2d');

    if (failureTrendChart) {
        failureTrendChart.destroy();
    }

    failureTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.trend.map(d => d.date),
            datasets: [
                {
                    label: 'Failure Rate',
                    data: data.trend.map(d => d.failure_rate),
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    tension: 0.4,
                    fill: true
                },
                {
                    label: '7-Day Moving Average',
                    data: data.trend.map(d => d.moving_average),
                    borderColor: '#3498db',
                    backgroundColor: 'transparent',
                    borderDash: [5, 5],
                    tension: 0.4,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const dataPoint = data.trend[context.dataIndex];
                            if (context.datasetIndex === 0) {
                                return [
                                    `Failure Rate: ${dataPoint.failure_rate.toFixed(1)}%`,
                                    `Failed: ${dataPoint.failed_count.toLocaleString()}`,
                                    `Total: ${dataPoint.total_count.toLocaleString()}`
                                ];
                            } else {
                                return `Moving Avg: ${dataPoint.moving_average.toFixed(1)}%`;
                            }
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: (value) => `${value}%`
                    }
                }
            }
        }
    });
}

// Load top organizations chart
async function loadTopOrganizationsChart() {
    const queryString = buildQueryString({ limit: 10 });
    const response = await fetch(`${API_BASE}/rollup/top-organizations?${queryString}`);
    const data = await response.json();

    const ctx = document.getElementById('topOrganizationsChart').getContext('2d');

    if (topOrganizationsChart) {
        topOrganizationsChart.destroy();
    }

    topOrganizationsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.organizations.map(d => d.org_name),
            datasets: [{
                label: 'Total Messages',
                data: data.organizations.map(d => d.total_messages),
                backgroundColor: '#3498db'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const org = data.organizations[context.dataIndex];
                            const passPct = org.total_messages > 0
                                ? ((org.pass_count / org.total_messages) * 100).toFixed(1)
                                : 0;
                            return [
                                `Total: ${org.total_messages.toLocaleString()}`,
                                `Pass: ${org.pass_count.toLocaleString()}`,
                                `Fail: ${org.fail_count.toLocaleString()}`,
                                `Pass Rate: ${passPct}%`
                            ];
                        }
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => value.toLocaleString()
                    }
                }
            }
        }
    });
}

// Tooltip management
let currentTooltip = null;

function showTooltip(event, text) {
    // Remove any existing tooltip
    hideTooltip();

    // Create tooltip element
    const tooltip = document.createElement('div');
    tooltip.className = 'badge-tooltip';
    tooltip.textContent = text;
    tooltip.id = 'active-tooltip';

    // Add to body
    document.body.appendChild(tooltip);
    currentTooltip = tooltip;

    // Position tooltip
    positionTooltip(event, tooltip);
}

function positionTooltip(event, tooltip) {
    const rect = event.target.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();

    // Calculate position (centered above the badge)
    let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
    let top = rect.top - tooltipRect.height - 10;

    // Check if tooltip goes off left edge
    if (left < 10) {
        left = 10;
    }

    // Check if tooltip goes off right edge
    if (left + tooltipRect.width > window.innerWidth - 10) {
        left = window.innerWidth - tooltipRect.width - 10;
    }

    // Check if tooltip goes off top edge (show below instead)
    if (top < 10) {
        top = rect.bottom + 10;
        tooltip.classList.add('bottom');
    }

    tooltip.style.position = 'fixed';
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
}

function updateTooltipPosition(event) {
    if (currentTooltip) {
        positionTooltip(event, currentTooltip);
    }
}

function hideTooltip() {
    if (currentTooltip) {
        currentTooltip.remove();
        currentTooltip = null;
    }
}
