import pytest
from app.config import settings
from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Librarian, StudentProfile, User
from app.services import get_or_create_daily_session
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


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
