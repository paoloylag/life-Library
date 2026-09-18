from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "sqlite+aiosqlite:///./library_attendance.db"
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

    def validate_production_auth(self) -> None:
        if self.app_env != "production":
            return
        if len(self.secret_key) < 32 or self.secret_key in (
            "development-only", "replace-with-a-long-random-secret",
        ):
            raise RuntimeError("Production requires a unique SECRET_KEY of at least 32 characters")
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
