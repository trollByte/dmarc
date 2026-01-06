from pydantic_settings import BaseSettings
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

    # Application
    app_name: str = "DMARC Report Processor"
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
