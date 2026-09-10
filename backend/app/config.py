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
    google_service_account_email: str = ""
    google_workspace_delegated_admin: str = ""
    google_directory_scope: str = "https://www.googleapis.com/auth/admin.directory.user.readonly"
    frontend_url: str = "http://localhost:5173/life-Library"
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "none", "strict"] = "lax"
    duplicate_scan_seconds: int = 20
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
