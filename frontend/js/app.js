// API Base URL
const API_BASE = '/api';

// Chart instances
let timelineChart, domainChart, sourceIpChart;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', async () => {
    await loadDashboard();

    // Set up ingest button
    document.getElementById('ingestBtn').addEventListener('click', triggerIngest);

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
            loadReportsTable()
        ]);
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showNotification('Error loading dashboard data', 'error');
    }
}

// Load summary statistics
async function loadStats() {
    const response = await fetch(`${API_BASE}/stats/summary`);
    const data = await response.json();

    document.getElementById('totalReports').textContent = data.total_reports || 0;
    document.getElementById('totalMessages').textContent = data.total_messages?.toLocaleString() || 0;
    document.getElementById('passRate').textContent = data.pass_rate ? `${data.pass_rate.toFixed(1)}%` : '0%';
    document.getElementById('failRate').textContent = data.fail_rate ? `${data.fail_rate.toFixed(1)}%` : '0%';
}

// Load timeline chart
async function loadTimelineChart() {
    const response = await fetch(`${API_BASE}/stats/by-date`);
    const data = await response.json();

    const ctx = document.getElementById('timelineChart').getContext('2d');

    if (timelineChart) {
        timelineChart.destroy();
    }

    timelineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: [
                {
                    label: 'Pass',
                    data: data.map(d => d.pass_count),
                    borderColor: '#27ae60',
                    backgroundColor: 'rgba(39, 174, 96, 0.1)',
                    tension: 0.4
                },
                {
                    label: 'Fail',
                    data: data.map(d => d.fail_count),
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
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Load domain chart
async function loadDomainChart() {
    const response = await fetch(`${API_BASE}/stats/by-domain?limit=10`);
    const data = await response.json();

    const ctx = document.getElementById('domainChart').getContext('2d');

    if (domainChart) {
        domainChart.destroy();
    }

    domainChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.domain),
            datasets: [
                {
                    label: 'Pass',
                    data: data.map(d => d.pass_count),
                    backgroundColor: '#27ae60'
                },
                {
                    label: 'Fail',
                    data: data.map(d => d.fail_count),
                    backgroundColor: '#e74c3c'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                x: {
                    stacked: true
                },
                y: {
                    stacked: true,
                    beginAtZero: true
                }
            }
        }
    });
}

// Load source IP chart
async function loadSourceIpChart() {
    const response = await fetch(`${API_BASE}/stats/by-source-ip?limit=10`);
    const data = await response.json();

    const ctx = document.getElementById('sourceIpChart').getContext('2d');

    if (sourceIpChart) {
        sourceIpChart.destroy();
    }

    sourceIpChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.source_ip),
            datasets: [{
                label: 'Message Count',
                data: data.map(d => d.count),
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
                }
            },
            scales: {
                x: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Load reports table - using safe DOM methods to prevent XSS
async function loadReportsTable() {
    const response = await fetch(`${API_BASE}/reports?limit=20`);
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
        totalCell.textContent = report.total_records?.toLocaleString() || 0;

        // Pass/Fail
        const passFailCell = row.insertCell();
        const passSpan = document.createElement('span');
        passSpan.className = 'pass';
        passSpan.textContent = report.pass_count || 0;
        const failSpan = document.createElement('span');
        failSpan.className = 'fail';
        failSpan.textContent = report.fail_count || 0;
        passFailCell.appendChild(passSpan);
        passFailCell.appendChild(document.createTextNode(' / '));
        passFailCell.appendChild(failSpan);

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
    try {
        const response = await fetch(`${API_BASE}/reports/${id}`);
        const data = await response.json();
        alert(`Report Details:\n\nOrganization: ${data.org_name}\nDomain: ${data.domain}\nDate Range: ${formatDateRange(data.date_begin, data.date_end)}\nTotal Records: ${data.records?.length || 0}`);
    } catch (error) {
        showNotification('Error loading report details', 'error');
    }
}

// Trigger manual ingest
async function triggerIngest() {
    const btn = document.getElementById('ingestBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Processing...';

    try {
        const response = await fetch(`${API_BASE}/ingest/trigger`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            showNotification(data.message || 'Ingest completed successfully', 'success');
            setTimeout(loadDashboard, 2000);
        } else {
            showNotification(data.detail || 'Ingest failed', 'error');
        }
    } catch (error) {
        showNotification('Error triggering ingest', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🔄 Trigger Ingest';
    }
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
