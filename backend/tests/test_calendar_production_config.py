import pytest
from cryptography.fernet import Fernet

from app.config import Settings


def production_settings(**overrides):
    return Settings(_env_file=None, app_env="production", secret_key="x" * 64,
        cookie_secure=True, google_client_id="client", google_client_secret="secret",
        frontend_url="https://library.life.edu.ph", **overrides)


def test_calendar_disabled_does_not_require_key():
    production_settings(google_calendar_enabled=False).validate_production_auth()


def test_calendar_production_configuration():
    production_settings(google_calendar_enabled=True,
        google_calendar_encryption_key=Fernet.generate_key().decode(),
        google_calendar_redirect_uri="https://library.life.edu.ph/api/calendar/callback").validate_production_auth()


@pytest.mark.parametrize("callback", ["http://localhost:8001/api/calendar/callback",
    "https://other.example/api/calendar/callback", "https://library.life.edu.ph/wrong"])
def test_calendar_rejects_unsafe_callback(callback):
    with pytest.raises(RuntimeError):
        production_settings(google_calendar_enabled=True,
            google_calendar_encryption_key=Fernet.generate_key().decode(),
            google_calendar_redirect_uri=callback).validate_production_auth()


def test_calendar_rejects_missing_key():
    with pytest.raises(RuntimeError):
        production_settings(google_calendar_enabled=True,
            google_calendar_redirect_uri="https://library.life.edu.ph/api/calendar/callback").validate_production_auth()
