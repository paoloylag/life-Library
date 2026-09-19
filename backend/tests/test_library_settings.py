import pytest
from app.auth import hash_password
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Librarian
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def client(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()

    async def override_db():
        yield session

    monkeypatch.setattr(settings, "app_env", "local")
    app.dependency_overrides[get_db] = override_db
    session.add(Librarian(email="admin@life.edu.ph", name="Test Librarian", password_hash=hash_password("test-password"), role="librarian", is_active=True))
    await session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        assert (await value.post("/api/admin/login", json={"email": "admin@life.edu.ph", "password": "test-password"})).status_code == 204
        yield value
    app.dependency_overrides.clear()
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_settings_persist_and_public_display_is_limited(client):
    initial = await client.get("/api/library/settings")
    assert initial.status_code == 200
    assert initial.json()["configured"] is False
    payload = initial.json()["settings"]
    payload["libraryName"] = "Life College Main Library"
    payload["qrHeading"] = "Welcome to the Library"
    payload["duplicateWindowMinutes"] = 12
    payload["defaultReportUserType"] = "faculty"
    payload["programs"] = ["Arts, Design", "BS IT"]
    payload["roomBookingUrl"] = "https://booking.example.edu/rooms"

    saved = await client.put("/api/library/settings", json=payload)
    assert saved.status_code == 200
    assert saved.json()["audit"][0]["action"] == "Settings updated"
    again = await client.get("/api/library/settings")
    assert again.json()["configured"] is True
    assert again.json()["settings"]["programs"] == ["Arts, Design", "BS IT"]
    assert again.json()["settings"]["duplicateWindowMinutes"] == 12
    assert len(again.json()["audit"]) == 1

    display = await client.get("/api/library/settings/display")
    assert display.json()["qrHeading"] == "Welcome to the Library"
    assert display.json()["roomBookingUrl"] == "https://booking.example.edu/rooms"
    assert "librarians" not in display.json()


@pytest.mark.asyncio
async def test_settings_validate_and_require_librarian_in_production(client, monkeypatch):
    payload = (await client.get("/api/library/settings")).json()["settings"]
    payload["opensAt"] = "19:00"
    payload["closesAt"] = "18:00"
    assert (await client.put("/api/library/settings", json=payload)).status_code == 422
    payload["opensAt"] = "07:00"
    payload["roomBookingUrl"] = "javascript:alert(1)"
    assert (await client.put("/api/library/settings", json=payload)).status_code == 422

    monkeypatch.setattr(settings, "app_env", "production")
    await client.post("/api/admin/logout")
    assert (await client.get("/api/library/settings")).status_code == 401
    assert (await client.put("/api/library/settings", json=payload)).status_code == 401
    assert (await client.get("/api/library/settings/display")).status_code == 200
