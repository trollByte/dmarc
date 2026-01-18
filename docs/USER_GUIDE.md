# DMARC Dashboard User Guide

Welcome to the DMARC Dashboard! This guide will help you understand and use all the features available to monitor and analyze your DMARC reports.

## Table of Contents

- [Getting Started](#getting-started)
- [Dashboard Overview](#dashboard-overview)
- [Importing Reports](#importing-reports)
- [Filtering and Analysis](#filtering-and-analysis)
- [Understanding DMARC Data](#understanding-dmarc-data)
- [Alerts and Notifications](#alerts-and-notifications)
- [Exporting Data](#exporting-data)
- [User Settings](#user-settings)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Troubleshooting](#troubleshooting)

## Getting Started

### First Login

1. Navigate to your DMARC Dashboard URL
2. Enter your username and password
3. If Two-Factor Authentication (2FA) is enabled, enter your code
4. You'll be guided through an onboarding wizard on first login

### Initial Setup

The onboarding wizard will help you:
1. Understand the dashboard layout
2. Import your first DMARC reports
3. Configure basic filters
4. Set up notifications (optional)

## Dashboard Overview

### Main Dashboard

The main dashboard displays key DMARC metrics at a glance:

| Metric | Description |
|--------|-------------|
| **Total Messages** | Total email messages analyzed |
| **Pass Rate** | Percentage of messages that passed DMARC |
| **DKIM Pass Rate** | Percentage passing DKIM authentication |
| **SPF Pass Rate** | Percentage passing SPF authentication |
| **Active Reports** | Number of reports in selected time range |

### Charts

1. **Timeline Chart** - Shows message volume over time with pass/fail breakdown
2. **Domain Distribution** - Top domains by message volume
3. **Source IP Analysis** - Top sending IP addresses
4. **Disposition Breakdown** - How messages were handled (none/quarantine/reject)

### Secondary Charts (Toggle with "More Charts" button)

- **Authentication Results** - Detailed DKIM/SPF analysis
- **Compliance Trend** - Pass rate trend over time
- **Failure Analysis** - Breakdown of failure reasons
- **Top Organizations** - Reporters sending you DMARC data

## Importing Reports

### Manual Upload

1. Click the **Import** button (or press `U`)
2. Choose upload method:
   - **File Upload**: Drag & drop or click to select files
   - **Email Ingestion**: Pull reports from your email inbox

3. Supported file formats:
   - `.xml` - Raw DMARC XML reports
   - `.xml.gz` - Gzip compressed reports
   - `.zip` - Zip archives containing XML reports

4. Click **Upload** and wait for processing

### Automatic Email Ingestion

If email ingestion is configured:
1. Reports are automatically fetched every 15 minutes
2. Click **Trigger Ingestion** to fetch immediately
3. Processed reports appear in the dashboard automatically

### Handling Duplicates

The system automatically detects duplicate reports based on content hash. Duplicates are skipped during upload.

## Filtering and Analysis

### Available Filters

| Filter | Description |
|--------|-------------|
| **Domain** | Filter by sending domain |
| **Date Range** | Preset ranges or custom dates |
| **Source IP** | Filter by sending IP address |
| **DKIM Result** | Pass, fail, or all |
| **SPF Result** | Pass, fail, or all |
| **Disposition** | None, quarantine, or reject |
| **Organization** | Filter by reporting organization |

### Using Filters

1. Select filters from the dropdown menus
2. Click **Apply Filters** or press Enter
3. Dashboard updates to show filtered data
4. Click **Reset** to clear all filters

### Saving Views

Save frequently used filter combinations:
1. Configure your filters
2. Click the **Save View** icon
3. Name your view
4. Access saved views from the Views dropdown

## Understanding DMARC Data

### Authentication Results

**DKIM (DomainKeys Identified Mail)**
- Verifies the email hasn't been altered in transit
- **Pass**: Email signature verified successfully
- **Fail**: Signature invalid or missing

**SPF (Sender Policy Framework)**
- Verifies the sending server is authorized
- **Pass**: Server is authorized to send for the domain
- **Fail**: Server is not authorized

### DMARC Policy Dispositions

| Disposition | Meaning |
|------------|---------|
| **None** | Message delivered normally (monitoring mode) |
| **Quarantine** | Message marked as spam or moved to junk |
| **Reject** | Message rejected/bounced |

### Pass Rate Interpretation

| Pass Rate | Status | Action |
|-----------|--------|--------|
| 95-100% | Excellent | Maintain current configuration |
| 85-95% | Good | Review occasional failures |
| 70-85% | Fair | Investigate failure patterns |
| Below 70% | Needs Attention | Immediate investigation required |

## Alerts and Notifications

### Alert Types

1. **Failure Rate Alerts** - Triggered when failure rate exceeds threshold
2. **Volume Alerts** - Triggered on unusual traffic patterns
3. **Authentication Alerts** - Triggered on specific auth failures
4. **DNS Change Alerts** - Triggered when DMARC/SPF/DKIM records change

### Configuring Alerts

1. Go to **Settings > Alerts**
2. Click **Create Alert Rule**
3. Configure:
   - Alert type and threshold
   - Domains to monitor
   - Notification channels
4. Save the rule

### Notification Channels

- **Email** - Receive alerts via email
- **Slack** - Post to Slack channel
- **Webhook** - Send to custom endpoint
- **In-App** - Dashboard notification center

### Viewing Notifications

1. Click the **Bell** icon in the header
2. View unread notifications
3. Click to see details
4. Mark as read or dismiss

## Exporting Data

### Export Formats

| Format | Best For |
|--------|----------|
| **CSV** | Spreadsheet analysis, data processing |
| **PDF** | Reports, presentations, compliance |
| **JSON** | API integrations, automation |

### Export Options

1. Click **Export** button
2. Select format (CSV, PDF, JSON)
3. Choose data scope:
   - Current filters
   - All data
   - Custom date range
4. Click Download

### Scheduled Reports

Set up automatic report delivery:
1. Go to **Settings > Scheduled Reports**
2. Click **Create Schedule**
3. Configure:
   - Report type and format
   - Frequency (daily, weekly, monthly)
   - Recipients
4. Save schedule

## User Settings

### Profile Settings

- Update display name
- Change email address
- Update password
- Configure 2FA

### Dashboard Preferences

- Default date range
- Default domain filter
- Chart color scheme
- Notification preferences

### Two-Factor Authentication

1. Go to **Settings > Security**
2. Click **Enable 2FA**
3. Scan QR code with authenticator app
4. Enter verification code
5. Save backup codes securely

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `?` | Show keyboard shortcuts |
| `R` | Refresh dashboard |
| `U` | Open upload dialog |
| `F` | Focus filter bar |
| `T` | Toggle theme (light/dark) |
| `C` | Toggle more charts |
| `S` | Focus search |
| `Escape` | Close modal/dropdown |
| `H` | Open help |

## Troubleshooting

### Dashboard Not Loading

1. Check your internet connection
2. Clear browser cache
3. Try a different browser
4. Contact administrator if problem persists

### Reports Not Processing

1. Verify file format is supported
2. Check file isn't corrupted
3. Look for error messages in upload results
4. Try uploading a smaller batch

### Missing Data

1. Verify date range filter
2. Check domain filter
3. Confirm reports were successfully imported
4. Try resetting all filters

### Authentication Issues

1. Verify username/password
2. Check if account is locked
3. Reset password if needed
4. Contact administrator for account issues

### Getting Help

- **In-App Help**: Click the `?` icon
- **Documentation**: Check `/docs` folder
- **Support**: Contact your administrator
- **Issues**: Report bugs on GitHub

---

## Glossary

| Term | Definition |
|------|------------|
| **DMARC** | Domain-based Message Authentication, Reporting & Conformance |
| **DKIM** | DomainKeys Identified Mail - email signature verification |
| **SPF** | Sender Policy Framework - sender authorization |
| **RUA** | Reporting URI for Aggregate reports |
| **RUF** | Reporting URI for Forensic reports |
| **Alignment** | Whether From domain matches DKIM/SPF domains |
| **Disposition** | Action taken on email (none/quarantine/reject) |
