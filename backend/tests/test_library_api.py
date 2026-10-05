import csv
import io

import pytest
from app.config import settings
from app.auth import hash_password, issue_student
from app.database import Base, get_db
from app.main import LibraryUserInput, app, clean_user_input
from app.models import Librarian, StudentProfile, User
from app.services import get_or_create_daily_session
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def test_manual_student_defaults_to_bs_entrep():
    values = clean_user_input(
        LibraryUserInput(
            number="ST-1", name="Student One", email="one@life.edu.ph", user_type="student"
        )
    )
    assert values["program"] == "BS-ENTREP"


@pytest.mark.asyncio
async def test_search_nonadjacent_name_words(client, api_db):
    for index, name in enumerate(["Paolo Miguel Ylag", "Paolo Santos", "Helen Ylag"]):
        user = User(email=f"search{index}@life.edu.ph", name=name, role="student", is_active=True)
        api_db.add(user)
        await api_db.flush()
        api_db.add(StudentProfile(user_id=user.id, student_number=f"SEARCH-{index}", user_type="student", is_active=True))
    await api_db.commit()
    for query in ["paolo ylag", "YLAG PAOLO", "  paolo   ylag  "]:
        response = await client.get("/api/library/users", params={"q": query})
        assert response.status_code == 200
        assert [item["name"] for item in response.json()["items"]] == ["Paolo Miguel Ylag"]
    exported = await client.get("/api/library/users/export.csv", params={"q": "paolo ylag"})
    assert [row["name"] for row in csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff")))] == ["Paolo Miguel Ylag"]


@pytest.mark.asyncio
async def test_users_paginate_after_surname_sort_and_export_all(client, api_db):
    for index, name in enumerate(["Amy Zebra", "Zoe Alpha", "Ben Middle"]):
        user = User(email=f"page{index}@life.edu.ph", name=name, role="student", is_active=True)
        api_db.add(user)
        await api_db.flush()
        api_db.add(StudentProfile(user_id=user.id, student_number=f"PAGE-{index}", user_type="student", is_active=True))
    await api_db.commit()
    first = (await client.get("/api/library/users?page=1&page_size=2")).json()
    second = (await client.get("/api/library/users?page=2&page_size=2")).json()
    assert first["total"] == second["total"] == 3
    assert [item["name"] for item in first["items"]] == ["Zoe Alpha", "Ben Middle"]
    assert [item["name"] for item in second["items"]] == ["Amy Zebra"]
    filtered = (await client.get("/api/library/users?q=Zebra&page_size=10")).json()
    assert filtered["total"] == 1
    exported = await client.get("/api/library/users/export.csv")
    assert len(list(csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff"))))) == 3


@pytest.mark.asyncio
async def test_staff_csv_preview_and_import(client, api_db, monkeypatch):
    monkeypatch.setattr(
        "app.import_roster.SessionLocal",
        async_sessionmaker(api_db.bind, expire_on_commit=False),
    )
    csv_data = (
        "Employee ID,Lsst Name,First Name,Middle Name,Preferred Name,Employment Status,Department,Position,Immediate Supervisor,Date Hired,Regularization Date,Contact No.,User Type\n"
        "NA,Cruz,Jamie,Lee,Jay,Part-time,Academics,Adjunct Faculty,Dean,July 1 2026,na,09123456789,faculty\n"
    )
    headers = {"Content-Type": "text/csv"}
    preview = await client.post(
        "/api/library/users/import-staff.csv?dry_run=true",
        content=csv_data,
        headers=headers,
    )
    assert preview.status_code == 200
    assert preview.json()["created"] == 1
    assert preview.json()["generated_ids"] == 1
    assert preview.json()["missing_emails"] == 1
    assert await api_db.scalar(select(func.count(StudentProfile.id))) == 0

    applied = await client.post(
        "/api/library/users/import-staff.csv?dry_run=false",
        content=csv_data,
        headers=headers,
    )
    assert applied.status_code == 200
    profiles = (await api_db.scalars(select(StudentProfile))).all()
    assert len(profiles) == 1
    assert profiles[0].user_type == "faculty"
    assert profiles[0].middle_name == "Lee"
    assert applied.json()["ignored_columns"] == [
        "Employment Status",
        "Position",
        "Immediate Supervisor",
        "Date Hired",
        "Regularization Date",
    ]
    users = await client.get("/api/library/users")
    assert users.json()["items"][0]["display_number"] == ""
    exported = await client.get("/api/library/users/export.csv")
    assert list(csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff"))))[0]["number"] == ""


@pytest.fixture
async def api_db(monkeypatch):
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
async def client(api_db):
    api_db.add(Librarian(email="admin@life.edu.ph", name="Test Librarian", password_hash=hash_password("test-password"), role="librarian", is_active=True))
    await api_db.commit()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as value:
        assert (await value.post("/api/admin/login", json={"email": "admin@life.edu.ph", "password": "test-password"})).status_code == 204
        yield value


async def add_user(db):
    user = User(email="angela@life.edu.ph", name="Angela Reyes", role="student")
    db.add(user)
    await db.flush()
    profile = StudentProfile(
        user_id=user.id,
        student_number="LC-001",
        user_type="student",
        program="BS-ENTREP",
        year_level="1st Year",
        section="1A",
        is_active=True,
    )
    db.add(profile)
    await db.commit()
    return profile


@pytest.mark.asyncio
async def test_authenticated_profile_returns_saved_staff_department(client, api_db):
    user = User(
        email="staff@life.edu.ph",
        name="Library Staff",
        google_id="google-staff-1",
        role="non-teaching personnel",
        is_active=True,
    )
    api_db.add(user)
    await api_db.flush()
    api_db.add(
        StudentProfile(
            user_id=user.id,
            student_number="STAFF-001",
            user_type="non-teaching personnel",
            department="Library Services",
            is_active=True,
        )
    )
    await api_db.commit()
    client.cookies.set("library_session", issue_student(user.id))

    response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["profile"]["department"] == "Library Services"


@pytest.mark.asyncio
async def test_user_search_manual_check_in_and_history(client, api_db):
    await add_user(api_db)
    users = await client.get("/api/library/users", params={"q": "Angela"})
    assert users.status_code == 200
    assert users.json()["items"][0]["number"] == "LC-001"

    recorded = await client.post(
        "/api/library/attendance/manual",
        json={"user_number": "LC-001", "note": "Scanner unavailable"},
    )
    assert recorded.status_code == 200

    history = await client.get("/api/library/users/LC-001/visits")
    assert history.status_code == 200
    assert history.json()["items"][0]["source"] == "manual"
    assert history.json()["items"][0]["note"] == "Scanner unavailable"
    assert history.json()["items"][0]["recorded_by"] == "Test Librarian"


@pytest.mark.asyncio
async def test_archive_hides_user_preserves_visits_and_can_restore(client, api_db):
    await add_user(api_db)
    recorded = await client.post(
        "/api/library/attendance/manual",
        json={"user_number": "LC-001", "note": "Before archive"},
    )
    assert recorded.status_code == 200

    archived = await client.patch(
        "/api/library/users/LC-001/archive", json={"archived": True}
    )
    assert archived.status_code == 200
    assert archived.json()["is_active"] is False
    assert (await client.get("/api/library/users")).json()["total"] == 0
    archived_list = await client.get(
        "/api/library/users", params={"status": "archived"}
    )
    assert archived_list.json()["total"] == 1
    assert archived_list.json()["items"][0]["number"] == "LC-001"
    history = await client.get("/api/library/users/LC-001/visits")
    assert history.json()["total"] == 1

    unavailable = await client.post(
        "/api/library/attendance/manual", json={"user_number": "LC-001"}
    )
    assert unavailable.status_code == 404
    restored = await client.patch(
        "/api/library/users/LC-001/archive", json={"archived": False}
    )
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True
    assert (await client.get("/api/library/users")).json()["total"] == 1


@pytest.mark.asyncio
async def test_guest_qr_check_in_is_persisted(client, api_db):
    _, token = await get_or_create_daily_session(api_db)
    response = await client.post(
        f"/api/library/scan/{token}/guest",
        json={"name": "Guest User", "organization": "Community", "purpose": "Research"},
    )
    assert response.status_code == 200
    number = response.json()["user_number"]

    history = await client.get(f"/api/library/users/{number}/visits")
    assert history.status_code == 200
    assert history.json()["items"][0]["source"] == "guest"
    assert history.json()["items"][0]["purpose"] == "Research"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["Paolo Miguel Ylag", "Helen Alod"])
async def test_guest_check_in_rejects_existing_internal_user(client, api_db, name):
    user = User(
        email=name.lower().replace(" ", ".") + "@life.edu.ph",
        name=name,
        role="non-teaching personnel",
        is_active=True,
    )
    api_db.add(user)
    await api_db.flush()
    api_db.add(
        StudentProfile(
            user_id=user.id,
            student_number=name.upper().replace(" ", "-"),
            user_type="non-teaching personnel",
            department="Administration",
            is_active=True,
        )
    )
    await api_db.commit()
    _, token = await get_or_create_daily_session(api_db)

    response = await client.post(
        f"/api/library/scan/{token}/guest",
        json={"name": name.lower(), "organization": "Life College", "purpose": "Work"},
    )

    assert response.status_code == 409
    assert "Continue with Google" in response.json()["detail"]
    profiles = (
        await api_db.scalars(
            select(StudentProfile)
            .join(User)
            .where(func.lower(User.name) == name.lower())
        )
    ).all()
    assert len(profiles) == 1
