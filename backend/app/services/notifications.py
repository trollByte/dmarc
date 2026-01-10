"""
Notification service for sending alerts

Supports multiple notification channels:
- Email (SMTP)
- Slack webhooks
- Discord webhooks
- Microsoft Teams webhooks
- Generic webhooks
"""
import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict
from datetime import datetime
from dataclasses import dataclass

from app.services.alerting import Alert
from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SMTPConfig:
    """SMTP configuration container"""
    host: str
    port: int
    user: Optional[str]
    password: Optional[str]
    from_address: str
    to_address: str
    use_tls: bool


class NotificationService:
    """Service for sending alert notifications"""

    def __init__(self):
        self.settings = get_settings()

    def _get_smtp_config(self) -> Optional[SMTPConfig]:
        """Get SMTP configuration if properly configured"""
        if not self._is_email_configured():
            return None

        return SMTPConfig(
            host=getattr(self.settings, 'smtp_host'),
            port=getattr(self.settings, 'smtp_port', 587),
            user=getattr(self.settings, 'smtp_user', None),
            password=getattr(self.settings, 'smtp_password', None),
            from_address=getattr(self.settings, 'smtp_from'),
            to_address=getattr(self.settings, 'alert_email_to'),
            use_tls=getattr(self.settings, 'smtp_use_tls', True)
        )

    def _send_email(self, subject: str, html_body: str, config: SMTPConfig) -> None:
        """Send an email using the provided configuration"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = config.from_address
        msg['To'] = config.to_address
        msg['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(config.host, config.port) as server:
            if config.use_tls:
                server.starttls()
            if config.user and config.password:
                server.login(config.user, config.password)
            server.send_message(msg)

    def send_alerts(self, alerts: List[Alert]) -> dict:
        """
        Send alerts via configured notification channels

        Args:
            alerts: List of alerts to send

        Returns:
            Dictionary with send statistics
        """
        if not alerts:
            return {'sent': 0, 'failed': 0}

        stats = {'sent': 0, 'failed': 0, 'channels': {}}

        logger.info(f"Sending {len(alerts)} alerts")

        # Send via email
        if self._is_email_configured():
            try:
                self.send_email_alerts(alerts)
                stats['sent'] += 1
                stats['channels']['email'] = 'success'
            except Exception as e:
                logger.error(f"Failed to send email alerts: {str(e)}", exc_info=True)
                stats['failed'] += 1
                stats['channels']['email'] = f'failed: {str(e)}'

        # Send via Slack
        if self._is_slack_configured():
            try:
                self.send_slack_alerts(alerts)
                stats['sent'] += 1
                stats['channels']['slack'] = 'success'
            except Exception as e:
                logger.error(f"Failed to send Slack alerts: {str(e)}", exc_info=True)
                stats['failed'] += 1
                stats['channels']['slack'] = f'failed: {str(e)}'

        # Send via Discord
        if self._is_discord_configured():
            try:
                self.send_discord_alerts(alerts)
                stats['sent'] += 1
                stats['channels']['discord'] = 'success'
            except Exception as e:
                logger.error(f"Failed to send Discord alerts: {str(e)}", exc_info=True)
                stats['failed'] += 1
                stats['channels']['discord'] = f'failed: {str(e)}'

        # Send via Teams
        if self._is_teams_configured():
            try:
                self.send_teams_alerts(alerts)
                stats['sent'] += 1
                stats['channels']['teams'] = 'success'
            except Exception as e:
                logger.error(f"Failed to send Teams alerts: {str(e)}", exc_info=True)
                stats['failed'] += 1
                stats['channels']['teams'] = f'failed: {str(e)}'

        # Send via generic webhook
        if self._is_webhook_configured():
            try:
                self.send_webhook_alerts(alerts)
                stats['sent'] += 1
                stats['channels']['webhook'] = 'success'
            except Exception as e:
                logger.error(f"Failed to send webhook alerts: {str(e)}", exc_info=True)
                stats['failed'] += 1
                stats['channels']['webhook'] = f'failed: {str(e)}'

        logger.info(f"Alert sending complete: {stats}")
        return stats

    def _is_email_configured(self) -> bool:
        """Check if email notifications are configured"""
        return bool(
            getattr(self.settings, 'smtp_host', None) and
            getattr(self.settings, 'smtp_from', None) and
            getattr(self.settings, 'alert_email_to', None)
        )

    def _is_slack_configured(self) -> bool:
        """Check if Slack webhook is configured"""
        return bool(getattr(self.settings, 'slack_webhook_url', None))

    def _is_discord_configured(self) -> bool:
        """Check if Discord webhook is configured"""
        return bool(getattr(self.settings, 'discord_webhook_url', None))

    def _is_teams_configured(self) -> bool:
        """Check if Teams webhook is configured"""
        return bool(getattr(self.settings, 'teams_webhook_url', None))

    def _is_webhook_configured(self) -> bool:
        """Check if generic webhook is configured"""
        return bool(getattr(self.settings, 'webhook_url', None))

    def send_email_alerts(self, alerts: List[Alert]):
        """Send alerts via email (SMTP)"""
        config = self._get_smtp_config()
        if not config:
            raise ValueError("SMTP not configured")

        # Group alerts by severity
        critical = [a for a in alerts if a.severity == 'critical']
        warning = [a for a in alerts if a.severity == 'warning']
        info = [a for a in alerts if a.severity == 'info']

        # Build subject
        if critical or warning:
            subject = f"DMARC Alert: {len(critical)} Critical, {len(warning)} Warning"
        else:
            subject = f"DMARC Alert: {len(info)} Informational"

        body = self._build_email_body(alerts)
        self._send_email(subject, body, config)

        logger.info(f"Sent email alert to {config.to_address}")

    def _build_email_body(self, alerts: List[Alert]) -> str:
        """Build HTML email body"""
        severity_color = {
            'critical': '#e74c3c',
            'warning': '#f39c12',
            'info': '#3498db'
        }

        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .alert { margin: 15px 0; padding: 15px; border-left: 4px solid; }
                .critical { border-color: #e74c3c; background: #fdeaea; }
                .warning { border-color: #f39c12; background: #fef5e7; }
                .info { border-color: #3498db; background: #ebf5fb; }
                .title { font-weight: bold; font-size: 16px; margin-bottom: 5px; }
                .message { margin: 5px 0; }
                .details { font-size: 12px; color: #666; margin-top: 10px; }
                .timestamp { font-size: 11px; color: #999; }
            </style>
        </head>
        <body>
            <h2>DMARC Monitoring Alerts</h2>
        """

        for alert in alerts:
            html += f"""
            <div class="alert {alert.severity}">
                <div class="title">{alert.title}</div>
                <div class="message">{alert.message}</div>
                <div class="details">
            """

            for key, value in alert.details.items():
                html += f"<div><strong>{key.replace('_', ' ').title()}:</strong> {value}</div>"

            html += f"""
                </div>
                <div class="timestamp">Detected at: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
            </div>
            """

        html += """
        </body>
        </html>
        """

        return html

    def send_slack_alerts(self, alerts: List[Alert]):
        """Send alerts to Slack via webhook"""
        webhook_url = getattr(self.settings, 'slack_webhook_url')

        # Group by severity
        critical = [a for a in alerts if a.severity == 'critical']
        warning = [a for a in alerts if a.severity == 'warning']
        info = [a for a in alerts if a.severity == 'info']

        # Build Slack message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 DMARC Alerts: {len(critical)} Critical, {len(warning)} Warning, {len(info)} Info"
                }
            }
        ]

        for alert in alerts:
            emoji = {'critical': '🔴', 'warning': '⚠️', 'info': 'ℹ️'}
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{emoji[alert.severity]} {alert.title}*\n{alert.message}"
                }
            })

            if alert.details:
                details_text = "\n".join([f"• *{k.replace('_', ' ').title()}:* {v}" for k, v in list(alert.details.items())[:5]])
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": details_text
                    }]
                })

        payload = {"blocks": blocks}

        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()

        logger.info("Sent Slack alert")

    def send_discord_alerts(self, alerts: List[Alert]):
        """Send alerts to Discord via webhook"""
        webhook_url = getattr(self.settings, 'discord_webhook_url')

        color_map = {'critical': 0xe74c3c, 'warning': 0xf39c12, 'info': 0x3498db}

        embeds = []
        for alert in alerts:
            embed = {
                "title": alert.title,
                "description": alert.message,
                "color": color_map[alert.severity],
                "timestamp": alert.timestamp.isoformat(),
                "fields": []
            }

            for key, value in list(alert.details.items())[:5]:
                embed["fields"].append({
                    "name": key.replace('_', ' ').title(),
                    "value": str(value),
                    "inline": True
                })

            embeds.append(embed)

        payload = {
            "content": f"**DMARC Monitoring Alerts** - {len(alerts)} alert(s)",
            "embeds": embeds[:10]  # Discord limit
        }

        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()

        logger.info("Sent Discord alert")

    def send_teams_alerts(self, alerts: List[Alert]):
        """Send alerts to Microsoft Teams via webhook"""
        webhook_url = getattr(self.settings, 'teams_webhook_url')

        color_map = {'critical': 'FF0000', 'warning': 'FFA500', 'info': '0078D4'}

        sections = []
        for alert in alerts:
            facts = [
                {"name": k.replace('_', ' ').title(), "value": str(v)}
                for k, v in list(alert.details.items())[:10]
            ]

            sections.append({
                "activityTitle": alert.title,
                "activitySubtitle": alert.message,
                "facts": facts,
                "markdown": True
            })

        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"DMARC Alerts: {len(alerts)}",
            "themeColor": color_map[alerts[0].severity] if alerts else '0078D4',
            "sections": sections
        }

        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()

        logger.info("Sent Teams alert")

    def send_webhook_alerts(self, alerts: List[Alert]):
        """Send alerts to generic webhook"""
        webhook_url = getattr(self.settings, 'webhook_url')

        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "alert_count": len(alerts),
            "alerts": [
                {
                    "type": alert.alert_type,
                    "severity": alert.severity,
                    "title": alert.title,
                    "message": alert.message,
                    "details": alert.details,
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert in alerts
            ]
        }

        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()

        logger.info("Sent webhook alert")

    # ==================== Single Alert Methods (Phase 3) ====================

    def send_teams_alert(
        self,
        title: str,
        message: str,
        severity: str,
        domain: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Send single alert to Microsoft Teams (PRIORITY CHANNEL).

        Args:
            title: Alert title
            message: Alert message
            severity: Severity level (critical, warning, info)
            domain: Domain (optional)
            metadata: Additional metadata (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._is_teams_configured():
            return False

        try:
            webhook_url = getattr(self.settings, 'teams_webhook_url')
            color_map = {'critical': 'FF0000', 'warning': 'FFA500', 'info': '0078D4'}

            facts = []
            if domain:
                facts.append({"name": "Domain", "value": domain})

            if metadata:
                for key, value in list(metadata.items())[:8]:
                    facts.append({
                        "name": key.replace('_', ' ').title(),
                        "value": str(value)
                    })

            payload = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "summary": title,
                "themeColor": color_map.get(severity, '0078D4'),
                "sections": [{
                    "activityTitle": f"🔔 {title}",
                    "activitySubtitle": message,
                    "facts": facts,
                    "markdown": True
                }]
            }

            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()

            logger.info(f"Sent Teams alert: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Teams alert: {e}", exc_info=True)
            return False

    def send_email_alert(
        self,
        title: str,
        message: str,
        severity: str,
        domain: Optional[str] = None
    ) -> bool:
        """
        Send single alert via email.

        Args:
            title: Alert title
            message: Alert message
            severity: Severity level
            domain: Domain (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        config = self._get_smtp_config()
        if not config:
            return False

        try:
            subject = f"DMARC Alert [{severity.upper()}]: {title}"

            severity_color = {
                'critical': '#e74c3c',
                'warning': '#f39c12',
                'info': '#3498db'
            }

            domain_html = f'<div class="domain">Domain: {domain}</div>' if domain else ''
            body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .alert {{ margin: 15px; padding: 20px; border-left: 4px solid {severity_color.get(severity, '#3498db')}; }}
                    .title {{ font-weight: bold; font-size: 18px; margin-bottom: 10px; }}
                    .message {{ margin: 10px 0; font-size: 14px; }}
                    .domain {{ color: #666; margin-top: 10px; }}
                </style>
            </head>
            <body>
                <div class="alert">
                    <div class="title">{title}</div>
                    <div class="message">{message}</div>
                    {domain_html}
                </div>
            </body>
            </html>
            """

            self._send_email(subject, body, config)
            logger.info(f"Sent email alert to {config.to_address}: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}", exc_info=True)
            return False

    def send_slack_alert(
        self,
        title: str,
        message: str,
        severity: str
    ) -> bool:
        """
        Send single alert to Slack.

        Args:
            title: Alert title
            message: Alert message
            severity: Severity level

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._is_slack_configured():
            return False

        try:
            webhook_url = getattr(self.settings, 'slack_webhook_url')
            emoji = {'critical': '🔴', 'warning': '⚠️', 'info': 'ℹ️'}

            payload = {
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{emoji.get(severity, 'ℹ️')} {title}*\n{message}"
                        }
                    }
                ]
            }

            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()

            logger.info(f"Sent Slack alert: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}", exc_info=True)
            return False
