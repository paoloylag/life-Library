import pytest

from app.config import Settings


def test_production_auth_requires_strong_key_and_secure_cookie():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings(
            app_env="production", secret_key="development-only", cookie_secure=True
        ).validate_production_auth()
    with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
        Settings(
            app_env="production", secret_key="a" * 40, cookie_secure=False
        ).validate_production_auth()
    Settings(
        app_env="production", secret_key="a" * 40, cookie_secure=True
    ).validate_production_auth()


def test_database_url_can_be_assembled_from_individual_secrets():
    settings = Settings(
        _env_file=None,
        database_host="database.internal",
        database_port=5432,
        database_name="library",
        database_user="library user",
        database_password="p@ss/word",
    )

    assert settings.database_url == (
        "postgresql+asyncpg://library+user:p%40ss%2Fword@database.internal:5432/library"
    )


def test_database_secret_fields_must_be_complete():
    with pytest.raises(ValueError, match="DATABASE_USER and DATABASE_PASSWORD"):
        Settings(_env_file=None, database_host="database.internal")


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
