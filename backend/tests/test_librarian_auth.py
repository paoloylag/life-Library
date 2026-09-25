import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import hash_password
from app.config import settings
from app.database import Base, get_db
from app.dev_librarians import seed_dev_librarians
from app.main import app
from app.models import Librarian


@pytest.fixture
async def auth_context(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    db = factory()

    async def override_db():
        yield db

    monkeypatch.setattr(settings, "app_env", "local")
    monkeypatch.setattr(settings, "enable_dev_librarians", False)
    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, db
    app.dependency_overrides.clear()
    await db.close()
    await engine.dispose()


async def add_librarian(db, role):
    db.add(Librarian(
        name=role.title(), email=f"{role}@life.edu.ph", role=role,
        password_hash=hash_password("test-password"), is_active=True,
    ))
    await db.commit()


async def login(client, role):
    result = await client.post("/api/admin/login", json={
        "email": f"{role}@life.edu.ph", "password": "test-password",
    })
    assert result.status_code == 204


@pytest.mark.asyncio
async def test_anonymous_admin_routes_are_closed_even_in_local_mode(auth_context):
    client, _ = auth_context
    for path in (
        "/api/library/sessions/current", "/api/library/dashboard",
        "/api/library/users", "/api/library/attendance",
        "/api/library/reports", "/api/library/settings",
    ):
        assert (await client.get(path)).status_code == 401, path
    assert (await client.post("/api/library/attendance/manual", json={})).status_code == 401
    assert (await client.get("/api/admin/dev-accounts")).status_code == 404
    assert (await client.post("/api/auth/dev-login")).status_code == 404
    assert (await client.get("/api/library/settings/display")).status_code == 200


@pytest.mark.asyncio
async def test_librarian_roles_authorize_reads_and_mutations(auth_context):
    client, db = auth_context
    for role in ("librarian", "librarian_associate", "auditor"):
        await add_librarian(db, role)

    await login(client, "auditor")
    assert (await client.get("/api/library/dashboard")).status_code == 200
    assert (await client.get("/api/library/users")).status_code == 200
    assert (await client.get("/api/library/attendance")).status_code == 200
    assert (await client.get("/api/library/reports")).status_code == 200
    assert (await client.get("/api/library/sessions/current")).status_code == 403
    assert (await client.post("/api/library/attendance/manual", json={})).status_code == 403
    assert (await client.get("/api/library/settings")).status_code == 403
    await client.post("/api/admin/logout")

    await login(client, "librarian_associate")
    assert (await client.get("/api/library/sessions/current")).status_code == 200
    assert (await client.get("/api/library/settings")).status_code == 403
    await client.post("/api/admin/logout")

    await login(client, "librarian")
    assert (await client.get("/api/library/settings")).status_code == 200
    assert (await client.get("/api/admin/me")).json()["role"] == "librarian"


@pytest.mark.asyncio
async def test_local_dev_accounts_are_opt_in_and_blocked_in_production(auth_context, monkeypatch):
    client, db = auth_context
    monkeypatch.setattr(settings, "enable_dev_librarians", True)
    await seed_dev_librarians(db)
    accounts = (await client.get("/api/admin/dev-accounts")).json()["accounts"]
    assert {account["role"] for account in accounts} == {"librarian", "librarian_associate", "auditor"}
    librarian = next(account for account in accounts if account["role"] == "librarian")
    assert (await client.post("/api/admin/login", json=librarian)).status_code == 204
    assert (await client.get("/api/admin/me")).status_code == 200

    monkeypatch.setattr(settings, "app_env", "production")
    assert (await client.get("/api/admin/dev-accounts")).status_code == 404
    assert (await client.get("/api/admin/me")).status_code == 401
    assert (await client.post("/api/admin/login", json=librarian)).status_code == 401


@pytest.mark.asyncio
async def test_librarian_can_change_own_password(auth_context):
    client, db = auth_context
    await add_librarian(db, "librarian")

    assert (await client.post("/api/admin/change-password", json={
        "current_password": "test-password",
        "new_password": "replacement-password",
    })).status_code == 401

    await login(client, "librarian")
    wrong = await client.post("/api/admin/change-password", json={
        "current_password": "wrong-password",
        "new_password": "replacement-password",
    })
    assert wrong.status_code == 400
    assert wrong.json()["detail"] == "Current password is incorrect"

    same = await client.post("/api/admin/change-password", json={
        "current_password": "test-password",
        "new_password": "test-password",
    })
    assert same.status_code == 422

    changed = await client.post("/api/admin/change-password", json={
        "current_password": "test-password",
        "new_password": "replacement-password",
    })
    assert changed.status_code == 204
    assert (await client.get("/api/admin/me")).status_code == 200

    await client.post("/api/admin/logout")
    assert (await client.post("/api/admin/login", json={
        "email": "librarian@life.edu.ph", "password": "test-password",
    })).status_code == 401
    assert (await client.post("/api/admin/login", json={
        "email": "librarian@life.edu.ph", "password": "replacement-password",
    })).status_code == 204
