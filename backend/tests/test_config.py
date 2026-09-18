from app.config import Settings


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
