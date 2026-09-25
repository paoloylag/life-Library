import pytest

from test_librarian_auth import add_librarian, auth_context, login


@pytest.mark.asyncio
async def test_staff_account_creation_and_role_boundaries(auth_context):
    client, db = auth_context
    for role in ("librarian", "librarian_associate", "auditor"):
        await add_librarian(db, role)
    body = {"name": "New Librarian", "email": "new@life.edu.ph",
            "password": "a-strong-test-password", "role": "librarian_associate"}
    assert (await client.post("/api/admin/accounts", json=body)).status_code == 401
    await login(client, "auditor")
    assert (await client.get("/api/admin/accounts")).status_code == 403
    assert (await client.post("/api/admin/accounts", json=body)).status_code == 403
    await client.post("/api/admin/logout")

    await login(client, "librarian_associate")
    short = await client.post("/api/admin/accounts", json={**body, "email": "short@life.edu.ph", "password": "123456789"})
    assert short.status_code == 422
    boundary = await client.post("/api/admin/accounts", json={**body, "email": "ten@life.edu.ph", "password": "1234567890"})
    assert boundary.status_code == 201, boundary.text
    created = await client.post("/api/admin/accounts", json=body)
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "librarian_associate"
    assert "password" not in created.json() and "password_hash" not in created.json()
    assert (await client.post("/api/admin/accounts", json=body)).status_code == 409
    assert (await client.post("/api/admin/accounts", json={**body, "role": "librarian", "email": "other@life.edu.ph"})).status_code == 403
    account_id = created.json()["id"]
    changed = await client.patch(f"/api/admin/accounts/{account_id}", json={"role": "auditor", "is_active": True})
    assert changed.status_code == 200, changed.text
    assert (await client.patch(f"/api/admin/accounts/{account_id}", json={"role": "librarian", "is_active": True})).status_code == 403
    await client.post("/api/admin/logout")

    await login(client, "librarian")
    head = await client.post("/api/admin/accounts", json={**body, "email": "second-librarian@life.edu.ph", "role": "librarian"})
    assert head.status_code == 201, head.text
    assert (await client.get("/api/admin/accounts")).json()["items"]
    assert (await client.patch(f"/api/admin/accounts/{head.json()['id']}", json={"role": "auditor", "is_active": True})).status_code == 200
    assert (await client.post("/api/admin/login", json={"email": "new@life.edu.ph", "password": body["password"]})).status_code == 204


@pytest.mark.asyncio
async def test_librarian_cannot_remove_own_access(auth_context):
    client, db = auth_context
    await add_librarian(db, "librarian")
    await login(client, "librarian")
    me = (await client.get("/api/admin/me")).json()
    for role, active in (("auditor", True), ("librarian", False)):
        response = await client.patch(f"/api/admin/accounts/{me['id']}", json={"role": role, "is_active": active})
        assert response.status_code == 409
