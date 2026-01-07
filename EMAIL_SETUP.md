# Email Ingestion Setup Guide

This guide explains how to configure automatic email ingestion for DMARC reports.

## Overview

The DMARC processor can automatically check an email inbox for DMARC aggregate reports and ingest them for processing. This eliminates the need for manual report uploads.

## Features

- **Automatic ingestion**: Background job checks email every 15 minutes
- **Manual trigger**: Ingest on-demand via API or dashboard button
- **Idempotent**: Duplicate reports are automatically detected and skipped
- **Multi-format support**: Handles .xml, .gz, and .zip attachments
- **Configurable search**: Custom IMAP search criteria

## Email Configuration

### 1. Environment Variables

Configure these variables in your `.env` file:

```bash
# Email (IMAP) Configuration
EMAIL_HOST=imap.gmail.com          # IMAP server hostname
EMAIL_PORT=993                      # IMAP port (usually 993 for SSL)
EMAIL_USER=your-email@example.com  # Email address
EMAIL_PASSWORD=your-app-password   # Password or app-specific password
EMAIL_FOLDER=INBOX                  # Folder to check (usually INBOX)
EMAIL_USE_SSL=true                  # Use SSL/TLS (recommended)
```

### 2. Gmail Setup

For Gmail accounts:

1. **Enable 2-Factor Authentication** (2FA) on your Google account

2. **Generate an App Password**:
   - Go to https://myaccount.google.com/security
   - Select "2-Step Verification"
   - Scroll to "App passwords"
   - Select app: "Mail"
   - Select device: "Other" (enter "DMARC Processor")
   - Copy the generated 16-character password
   - Use this password for `EMAIL_PASSWORD`

3. **Configure email forwarding** (optional):
   - Create a filter to auto-forward DMARC reports to a dedicated address
   - Keeps your main inbox clean

**Example Gmail configuration**:
```bash
EMAIL_HOST=imap.gmail.com
EMAIL_PORT=993
EMAIL_USER=dmarc-reports@yourdomain.com
EMAIL_PASSWORD=abcd efgh ijkl mnop
EMAIL_FOLDER=INBOX
EMAIL_USE_SSL=true
```

### 3. Office 365 / Outlook.com Setup

For Microsoft accounts:

**Example Outlook configuration**:
```bash
EMAIL_HOST=outlook.office365.com
EMAIL_PORT=993
EMAIL_USER=dmarc-reports@yourdomain.com
EMAIL_PASSWORD=your-password
EMAIL_FOLDER=INBOX
EMAIL_USE_SSL=true
```

### 4. Other IMAP Providers

Most email providers support IMAP. Common settings:

| Provider | IMAP Server | Port | SSL |
|----------|-------------|------|-----|
| Gmail | imap.gmail.com | 993 | Yes |
| Outlook.com | outlook.office365.com | 993 | Yes |
| Yahoo | imap.mail.yahoo.com | 993 | Yes |
| iCloud | imap.mail.me.com | 993 | Yes |
| Fastmail | imap.fastmail.com | 993 | Yes |

Consult your email provider's documentation for specific settings.

## Usage

### Automatic Ingestion

Once configured, the system automatically:

1. **Every 15 minutes**: Checks email inbox for DMARC reports
2. **Searches for**: Emails with subjects containing "Report Domain" or "DMARC"
3. **Downloads**: XML, GZ, and ZIP attachments
4. **Deduplicates**: Skips reports already in the database
5. **Processes**: Automatically parses and stores new reports

Monitor automatic ingestion in the logs:
```bash
docker logs dmarc-backend | grep -i "email ingestion"
```

### Manual Ingestion

#### Via Dashboard

1. Open the dashboard at http://localhost
2. Click the "🔄 Trigger Ingest" button
3. The system will:
   - Check email for new reports (if configured)
   - Process any pending reports
   - Update the dashboard

#### Via API

```bash
# Trigger manual email ingestion
curl -X POST http://localhost/api/ingest/trigger

# Response:
{
  "message": "Ingestion complete: 5 new reports from 50 emails (10 duplicates skipped)",
  "reports_ingested": 5,
  "emails_checked": 50
}
```

#### Via CLI

```bash
# Run the ingestion script directly
docker-compose exec backend python -m app.services.ingestion
```

### Check Configuration Status

Verify email configuration via API:

```bash
curl http://localhost/api/config/status

# Response:
{
  "email_configured": true,
  "email_host": "imap.gmail.com",
  "email_folder": "INBOX",
  "scheduler_running": true,
  "background_jobs": ["process_reports", "ingest_emails"]
}
```

## Troubleshooting

### Email Not Configured

**Symptom**: Manual trigger returns "Email not configured"

**Solution**:
1. Check environment variables are set correctly
2. Verify `.env` file is in the correct location
3. Restart the backend: `docker-compose restart backend`
4. Check configuration: `curl http://localhost/api/config/status`

### Authentication Failed

**Symptom**: Logs show "Failed to connect to email server"

**Solutions**:

1. **Gmail**: Use app-specific password, not main account password
2. **2FA Required**: Enable 2FA and generate app password
3. **Less Secure Apps**: Some providers require enabling "less secure app access"
4. **Credentials**: Double-check username and password

Test connection:
```bash
docker-compose exec backend python -c "
from app.services.email_client import IMAPClient
from app.config import get_settings

settings = get_settings()
client = IMAPClient(
    host=settings.email_host,
    port=settings.email_port,
    user=settings.email_user,
    password=settings.email_password,
    folder=settings.email_folder,
    use_ssl=settings.email_use_SSL
)

try:
    client.connect()
    print('✓ Successfully connected to email server!')
    client.disconnect()
except Exception as e:
    print(f'✗ Connection failed: {e}')
"
```

### No Reports Found

**Symptom**: Ingestion runs but finds 0 reports

**Possible causes**:

1. **No DMARC reports in inbox**: Check that reports are being received
2. **Wrong folder**: Verify `EMAIL_FOLDER` setting (try "INBOX" or "[Gmail]/All Mail")
3. **Already processed**: Reports may have been ingested previously
4. **Search criteria**: May not match your report emails

View search criteria in logs:
```bash
docker logs dmarc-backend | grep "Starting ingestion"
```

### SSL/TLS Errors

**Symptom**: SSL certificate verification failed

**Solution**:
```bash
# For development/testing only - disable SSL verification
EMAIL_USE_SSL=false
EMAIL_PORT=143  # Non-SSL port
```

**Note**: Only disable SSL in development. Always use SSL in production.

### Rate Limiting

**Symptom**: "Too many connections" or rate limit errors

**Solutions**:
1. Increase ingestion interval (edit `backend/app/services/scheduler.py`)
2. Reduce emails checked per run (`limit` parameter)
3. Use dedicated email account for DMARC reports

## Advanced Configuration

### Custom Search Criteria

Edit `backend/app/services/ingestion.py` to customize email search:

```python
# Default search
search_criteria = '(OR SUBJECT "Report Domain" SUBJECT "DMARC")'

# Only from specific sender
search_criteria = 'FROM "noreply-dmarc-support@google.com"'

# Unread emails only
search_criteria = '(UNSEEN SUBJECT "DMARC")'

# Date range
search_criteria = 'SINCE 01-Jan-2026'
```

### Adjusting Ingestion Frequency

Edit `backend/app/services/scheduler.py`:

```python
# Change from 15 to 30 minutes
self.scheduler.add_job(
    func=self._ingest_emails_job,
    trigger=IntervalTrigger(minutes=30),  # Changed
    id='ingest_emails',
    ...
)
```

### Processing Limits

Control how many emails are checked per run:

In `backend/app/services/scheduler.py`:
```python
# Check last 100 emails instead of 50
stats = service.ingest_from_inbox(limit=100)
```

## Security Best Practices

1. **Dedicated Email Account**: Use a separate account just for DMARC reports
2. **App Passwords**: Always use app-specific passwords, never main password
3. **Least Privilege**: Email account should only have read access
4. **SSL/TLS**: Always use encrypted connections (`EMAIL_USE_SSL=true`)
5. **Secrets Management**: In production, use secrets manager (AWS Secrets, Vault, etc.)
6. **Monitor Access**: Regularly review email account access logs

## Monitoring

### View Ingestion Logs

```bash
# Real-time logs
docker logs -f dmarc-backend | grep "ingestion"

# Last ingestion run
docker logs dmarc-backend | grep "Email ingestion complete" | tail -1
```

### Check Ingestion Stats

```bash
# Get statistics
curl http://localhost/api/config/status

# View ingested reports
curl http://localhost/api/reports
```

### Scheduled Job Status

```bash
# Check if ingestion job is running
docker logs dmarc-backend | grep "Email ingestion job"

# View scheduled jobs
curl http://localhost/api/config/status | python -m json.tool
```

## Email Setup Checklist

- [ ] Email account created or dedicated
- [ ] IMAP access enabled
- [ ] App password generated (if using Gmail/Outlook)
- [ ] Environment variables configured
- [ ] Backend restarted
- [ ] Configuration verified via `/api/config/status`
- [ ] Test connection successful
- [ ] Manual ingestion tested
- [ ] Automatic ingestion verified in logs

## Support

For issues:
1. Check logs: `docker logs dmarc-backend`
2. Verify configuration: `curl http://localhost/api/config/status`
3. Test email connection (see troubleshooting section)
4. Review environment variables

---

**Last Updated**: 2026-01-06
