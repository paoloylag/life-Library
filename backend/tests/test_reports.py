from datetime import date, datetime, timezone
from io import BytesIO

import pytest
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import LibrarySession, LibraryVisit, StudentProfile, User
from app.reports import academic_year, academic_year_start, semester
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def report_db(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()

    async def override_db():
        yield session

    monkeypatch.setattr(settings, "app_env", "local")
    app.dependency_overrides[get_db] = override_db
    yield session
    app.dependency_overrides.clear()
    await session.close()
    await engine.dispose()


@pytest.fixture
async def client(report_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


async def seed(db):
    session = LibrarySession(
        session_date=date(2026, 8, 3), name="Library", token_hash="test",
        starts_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
        expires_at=datetime(2026, 8, 4, tzinfo=timezone.utc), status="open",
    )
    db.add(session)
    await db.flush()
    for number, name, category, dates in (
        ("LC-001", "Ana Cruz", "student", [datetime(2026, 8, 3, 1, tzinfo=timezone.utc), datetime(2026, 8, 4, 1, tzinfo=timezone.utc)]),
        ("LC-002", "Ben Santos", "faculty", [datetime(2026, 8, 3, 2, tzinfo=timezone.utc)]),
    ):
        user = User(email=f"{number}@life.edu.ph", name=name, role=category)
        db.add(user)
        await db.flush()
        profile = StudentProfile(
            user_id=user.id, student_number=number, user_type=category,
            program="BS IT" if category == "student" else None,
            year_level="1st Year" if category == "student" else None,
            section="A" if category == "student" else None,
        )
        db.add(profile)
        await db.flush()
        for when in dates:
            db.add(LibraryVisit(student_profile_id=profile.id, library_session_id=session.id, time_in=when, source="manual"))
    await db.commit()


def test_academic_calendar_boundaries():
    assert academic_year_start(2026) == date(2026, 8, 3)
    assert academic_year(date(2026, 8, 2)) == "2025-2026"
    assert academic_year(date(2026, 8, 3)) == "2026-2027"
    assert semester(date(2026, 8, 2)) == "Outside Semester"
    assert semester(date(2026, 8, 3)) == "1st Semester"
    assert semester(date(2027, 1, 1)) == "2nd Semester"


@pytest.mark.asyncio
async def test_report_filters_and_exports_share_records(client, report_db):
    await seed(report_db)
    params = {"date_from": "2026-08-03", "date_to": "2026-08-04", "user_type": "student"}
    response = await client.get("/api/library/reports", params=params)
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total_visits"] == 2
    assert body["summary"]["unique_users"] == 1
    assert body["summary"]["return_visits"] == 1
    assert body["summary"]["returning_users"] == 1
    assert body["summary"]["open_days"] == 1  # Tuesday only for students
    assert body["breakdowns"]["programs"] == [{"label": "BS IT", "value": 2}]
    assert len(body["records"]) == 2

    excel = await client.get("/api/library/reports/export.xlsx", params=params)
    assert excel.status_code == 200
    book = load_workbook(BytesIO(excel.content))
    assert "Executive Summary" in book.sheetnames
    assert book["Check-ins"].max_row == 3
    assert book["Attendance Trend"].max_row == 2

    pdf = await client.get("/api/library/reports/export.pdf", params=params)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_report_rejects_invalid_filters(client):
    result = await client.get("/api/library/reports", params={"date_from": "2026-08-04", "date_to": "2026-08-03"})
    assert result.status_code == 422
