from datetime import UTC, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.google_directory import (
    delegated_jwt_claims,
    keyless_access_token,
    user_type_from_org_unit,
)
from app.models import StudentProfile, User
from app.services import attendance_day, daily_token, get_or_create_daily_session, scan


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def test_daily_token_is_stable_for_manila_day():
    before_midnight_utc = datetime(2026, 9, 9, 15, 59, tzinfo=timezone.utc)
    after_midnight_utc = datetime(2026, 9, 9, 16, 1, tzinfo=timezone.utc)

    first_day = attendance_day(before_midnight_utc)
    second_day = attendance_day(after_midnight_utc)

    assert first_day.isoformat() == "2026-09-09"
    assert second_day.isoformat() == "2026-09-10"
    assert daily_token(first_day) == daily_token(first_day)
    assert daily_token(first_day) != daily_token(second_day)


@pytest.mark.parametrize(
    ("org_unit", "expected"),
    [
        ("/Students", "student"),
        ("/Students/College/First Year", "student"),
        ("/Academics/Faculty", "faculty"),
        ("/Academics/Faculty/College", "faculty"),
        ("/Staff/Digital Transformation", "non-teaching personnel"),
        ("/Academics/Dean's Office", "non-teaching personnel"),
        ("/", "non-teaching personnel"),
    ],
)
def test_org_unit_user_type_mapping(org_unit, expected):
    assert user_type_from_org_unit(org_unit) == expected


def test_delegated_jwt_is_short_lived(monkeypatch):
    from app.google_directory import settings

    monkeypatch.setattr(
        settings,
        "google_service_account_email",
        "library@example.iam.gserviceaccount.com",
    )
    monkeypatch.setattr(settings, "google_workspace_delegated_admin", "dt@life.edu.ph")
    now = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
    claims = delegated_jwt_claims(now)

    assert claims["iss"] == "library@example.iam.gserviceaccount.com"
    assert claims["sub"] == "dt@life.edu.ph"
    assert claims["exp"] - claims["iat"] == 55 * 60


def test_keyless_token_uses_iam_signing(monkeypatch):
    from app import google_directory

    class Response:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    class Session:
        def __init__(self, credentials):
            self.credentials = credentials

        def post(self, url, json, timeout):
            assert url.endswith(
                "/librarian@example.iam.gserviceaccount.com:signJwt"
            )
            assert "payload" in json
            assert timeout == 10
            return Response({"signedJwt": "signed-jwt"})

    monkeypatch.setattr(
        google_directory.settings,
        "google_service_account_email",
        "librarian@example.iam.gserviceaccount.com",
    )
    monkeypatch.setattr(
        google_directory.google.auth,
        "default",
        lambda scopes: (object(), None),
    )
    monkeypatch.setattr(google_directory, "AuthorizedSession", Session)
    monkeypatch.setattr(
        google_directory.httpx,
        "post",
        lambda url, data, timeout: Response({"access_token": "short-lived-token"}),
    )

    assert keyless_access_token() == "short-lived-token"


@pytest.mark.asyncio
async def test_valid_scan_records_once_and_then_returns_duplicate(db):
    user = User(
        email="test@life.edu.ph",
        name="Test User",
        role="student",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    db.add(
        StudentProfile(
            user_id=user.id,
            student_number="TEST-001",
            user_type="student",
            program="Test Program",
            section="A",
            is_active=True,
        )
    )
    await db.commit()

    _, token = await get_or_create_daily_session(db)
    first_action, first_visit = await scan(db, token, user)
    second_action, second_visit = await scan(db, token, user)

    assert first_action == "check_in"
    assert second_action == "duplicate"
    assert second_visit.id == first_visit.id
