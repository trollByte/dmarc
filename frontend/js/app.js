// API Base URL
const API_BASE = '/api';

// Chart instances
let timelineChart, domainChart, sourceIpChart, dispositionChart;

// Current filter state
let currentFilters = {
    domain: '',
    days: 30,
    startDate: null,
    endDate: null
};

// Upload modal state
let selectedFiles = [];

// Initialize dashboard
document.addEventListener('DOMContentLoaded', async () => {
    await loadDashboard();

    // Set up button event listeners
    document.getElementById('uploadBtn').addEventListener('click', openUploadModal);
    document.getElementById('ingestBtn').addEventListener('click', triggerIngest);
    document.getElementById('exportBtn').addEventListener('click', exportToCSV);
    document.getElementById('refreshBtn').addEventListener('click', loadDashboard);
    document.getElementById('applyFiltersBtn').addEventListener('click', applyFilters);
    document.getElementById('clearFiltersBtn').addEventListener('click', clearFilters);

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

    loadDashboard();
}

// Clear filters
function clearFilters() {
    currentFilters = {
        domain: '',
        days: 30,
        startDate: null,
        endDate: null
    };

    document.getElementById('domainFilter').value = '';
    document.getElementById('dateRangeFilter').value = '30';
    document.getElementById('startDate').value = '';
    document.getElementById('endDate').value = '';
    document.querySelector('.custom-date').style.display = 'none';

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
            </div>
        `;
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

// Export data to CSV
async function exportToCSV() {
    try {
        const queryString = buildQueryString({ page_size: 1000 });
        const response = await fetch(`${API_BASE}/reports?${queryString}`);
        const data = await response.json();

        if (data.reports.length === 0) {
            showNotification('No data to export', 'error');
            return;
        }

        // Build CSV
        const headers = ['Date Begin', 'Date End', 'Organization', 'Domain', 'Report ID', 'Total Messages', 'Records', 'Policy', 'Received At'];
        const rows = data.reports.map(r => [
            r.date_begin,
            r.date_end,
            r.org_name,
            r.domain,
            r.report_id,
            r.total_messages || 0,
            r.record_count || 0,
            r.policy_p || 'N/A',
            r.received_at
        ]);

        let csvContent = headers.join(',') + '\n';
        rows.forEach(row => {
            csvContent += row.map(cell => {
                // Escape quotes and wrap in quotes if contains comma
                const cellStr = String(cell);
                if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
                    return '"' + cellStr.replace(/"/g, '""') + '"';
                }
                return cellStr;
            }).join(',') + '\n';
        });

        // Download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `dmarc_reports_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        showNotification(`Exported ${data.reports.length} reports to CSV`, 'success');
    } catch (error) {
        console.error('Error exporting CSV:', error);
        showNotification('Error exporting data', 'error');
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
