from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/library_attendance"
    secret_key: str = "development-only"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_allowed_domain: str = "laicollege.edu.ph"
    frontend_url: str = "http://localhost:5173"
    duplicate_scan_seconds: int = 20
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

@lru_cache
def get_settings(): return Settings()
settings = get_settings()

