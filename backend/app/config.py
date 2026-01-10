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

    # Celery (distributed task queue)
    celery_broker_url: str = "redis://redis:6379/1"  # Use DB 1 for broker
    celery_result_backend: str = ""  # Will be set to database_url + sqlalchemy prefix
    celery_task_track_started: bool = True
    celery_task_time_limit: int = 1800  # 30 minutes hard limit
    celery_worker_prefetch_multiplier: int = 4
    use_celery: bool = False  # Set to True to use Celery instead of APScheduler

    # Authentication (Legacy API Keys)
    require_api_key: bool = False  # Set to True in production
    api_keys: list[str] = []  # List of valid API keys (set via API_KEYS env var comma-separated)

    # JWT Authentication
    jwt_secret_key: str = ""  # REQUIRED: Generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15  # Access token expires in 15 minutes
    jwt_refresh_token_expire_days: int = 7  # Refresh token expires in 7 days

    # Password Policy
    password_min_length: int = 12
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_digit: bool = True
    password_require_special: bool = True

    # Account Security
    max_failed_login_attempts: int = 5
    account_lockout_duration_minutes: int = 30

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

    # Threat Intelligence
    abuseipdb_api_key: str = ""  # Get free key at https://www.abuseipdb.com/api

    # OAuth / SSO
    oauth_enabled: bool = False
    oauth_base_url: str = ""  # e.g., https://your-domain.com (for redirect URIs)

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # Microsoft OAuth (Azure AD)
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = "common"  # Use "common" for multi-tenant, or specific tenant ID

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
