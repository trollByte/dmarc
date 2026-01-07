from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://dmarc:dmarc@db:5432/dmarc"

    # Email (IMAP)
    email_host: str = ""
    email_port: int = 993
    email_user: str = ""
    email_password: str = ""
    email_folder: str = "INBOX"
    email_use_ssl: bool = True

    # Storage
    raw_reports_path: str = "/app/storage/raw_reports"

    # Application
    app_name: str = "DMARC Report Processor"
    debug: bool = False
    log_level: str = "INFO"

    # Logging
    log_dir: str = "/app/logs"
    log_json: bool = False  # Enable JSON logging for production
    enable_request_logging: bool = True

    # Redis Cache
    redis_url: str = "redis://redis:6379/0"
    cache_enabled: bool = True
    cache_default_ttl: int = 300  # 5 minutes

    # Authentication
    require_api_key: bool = False  # Set to True in production
    api_keys: list[str] = []  # List of valid API keys (set via API_KEYS env var comma-separated)

    # Alerting - Thresholds
    alert_failure_warning: float = 10.0  # Warning if failure rate > 10%
    alert_failure_critical: float = 25.0  # Critical if failure rate > 25%
    alert_volume_spike: float = 50.0  # Alert if volume increases > 50%
    alert_volume_drop: float = -30.0  # Alert if volume decreases > 30%
    enable_alerts: bool = False  # Enable/disable alerting system

    # Alerting - Email (SMTP)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    alert_email_to: str = ""  # Email address to send alerts to

    # Alerting - Webhooks
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""
    teams_webhook_url: str = ""
    webhook_url: str = ""  # Generic webhook URL

    @field_validator('api_keys', mode='before')
    @classmethod
    def parse_api_keys(cls, v):
        """Parse comma-separated API keys from environment variable"""
        if isinstance(v, str):
            return [key.strip() for key in v.split(',') if key.strip()]
        return v or []

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
