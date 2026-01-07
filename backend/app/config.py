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

    # Authentication
    require_api_key: bool = False  # Set to True in production
    api_keys: list[str] = []  # List of valid API keys (set via API_KEYS env var comma-separated)

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
