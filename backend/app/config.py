from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "sqlite+aiosqlite:///./library_attendance.db"
    database_host: str = ""
    database_port: int = 5432
    database_name: str = "library_attendance"
    database_user: str = ""
    database_password: str = ""
    secret_key: str = "development-only"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_allowed_domain: str = "life.edu.ph"
    google_calendar_enabled: bool = False
    google_calendar_redirect_uri: str = "http://127.0.0.1:8001/api/calendar/callback"
    google_calendar_encryption_key: str = ""
    booking_email_enabled: bool = False
    booking_email_test_recipient: str = ""
    booking_email_sender: str = "library@life.edu.ph"
    booking_email_configuration_set: str = "life-library-production-bookings"
    booking_email_feedback_queue: str = ""
    google_service_account_file: str = ""
    google_service_account_secret_id: str = ""
    aws_region: str = ""
    google_workspace_delegated_admin: str = ""
    google_directory_scope: str = (
        "https://www.googleapis.com/auth/admin.directory.user.readonly"
    )
    frontend_url: str = "http://localhost:5173/library"
    frontend_origins: str = ""
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "none", "strict"] = "lax"
    duplicate_scan_seconds: int = 20
    enable_dev_librarians: bool = False
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    @model_validator(mode="after")
    def assemble_database_url(self):
        if not self.database_host:
            return self
        if not self.database_user or not self.database_password:
            raise ValueError(
                "DATABASE_USER and DATABASE_PASSWORD are required when DATABASE_HOST is set"
            )
        user = quote_plus(self.database_user)
        password = quote_plus(self.database_password)
        self.database_url = (
            f"postgresql+asyncpg://{user}:{password}@{self.database_host}:"
            f"{self.database_port}/{self.database_name}"
        )
        return self

    def validate_production_auth(self) -> None:
        if self.app_env != "production":
            return
        if len(self.secret_key) < 32 or self.secret_key in (
            "development-only",
            "replace-with-a-long-random-secret",
        ):
            raise RuntimeError(
                "Production requires a unique SECRET_KEY of at least 32 characters"
            )
        if not self.cookie_secure:
            raise RuntimeError("Production requires COOKIE_SECURE=true")
        if self.booking_email_enabled:
            from urllib.parse import urlsplit

            queue = urlsplit(self.booking_email_feedback_queue)
            if (urlsplit(self.frontend_url).scheme != "https" or not self.aws_region
                    or self.booking_email_sender != "library@life.edu.ph"
                    or not self.booking_email_configuration_set
                    or queue.scheme != "https" or not (queue.hostname or "").endswith(".amazonaws.com")):
                raise RuntimeError("Booking email requires HTTPS links, the approved sender, an AWS region and an SQS feedback queue")
        if self.google_calendar_enabled:
            from cryptography.fernet import Fernet
            from urllib.parse import urlsplit

            try:
                Fernet(self.google_calendar_encryption_key.encode())
            except (ValueError, TypeError) as exc:
                raise RuntimeError("Calendar requires a valid dedicated encryption key") from exc
            frontend = urlsplit(self.frontend_url)
            callback = urlsplit(self.google_calendar_redirect_uri)
            if (not self.google_client_id or not self.google_client_secret
                    or frontend.scheme != "https" or callback.scheme != "https"
                    or callback.netloc != frontend.netloc
                    or callback.path != "/api/calendar/callback"):
                raise RuntimeError("Calendar requires OAuth credentials and a same-origin HTTPS callback")

    @property
    def allowed_frontend_origins(self) -> list[str]:
        configured = [
            origin.strip().rstrip("/")
            for origin in self.frontend_origins.split(",")
            if origin.strip()
        ]
        if configured:
            return configured

        from urllib.parse import urlsplit

        parsed = urlsplit(self.frontend_url)
        return [f"{parsed.scheme}://{parsed.netloc}"]


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
