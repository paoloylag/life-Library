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
