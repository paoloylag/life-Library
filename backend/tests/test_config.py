import pytest
from app.config import Settings


def test_production_auth_requires_strong_key_and_secure_cookie():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings(app_env="production", secret_key="development-only", cookie_secure=True).validate_production_auth()
    with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
        Settings(app_env="production", secret_key="a" * 40, cookie_secure=False).validate_production_auth()
    Settings(app_env="production", secret_key="a" * 40, cookie_secure=True).validate_production_auth()


def test_frontend_origin_is_derived_from_public_url():
    settings = Settings(
        _env_file=None,
        frontend_url="https://paoloylag.github.io/life-Library",
    )

    assert settings.allowed_frontend_origins == ["https://paoloylag.github.io"]


def test_multiple_frontend_origins_are_supported():
    settings = Settings(
        _env_file=None,
        frontend_origins="https://paoloylag.github.io, https://library.life.edu.ph/",
    )

    assert settings.allowed_frontend_origins == [
        "https://paoloylag.github.io",
        "https://library.life.edu.ph",
    ]
