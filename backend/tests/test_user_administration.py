import pytest
from app.models import StudentProfile, User
from sqlalchemy import select

from test_librarian_auth import add_librarian, auth_context, login


@pytest.mark.asyncio
async def test_admin_can_create_and_update_all_user_categories(auth_context):
    client, db = auth_context
    for role in ("librarian", "auditor"):
        await add_librarian(db, role)
    payload = {
        "number": "LC-100", "name": "Alex Rivera", "email": "alex@life.edu.ph",
        "user_type": "student", "program": "BSIT", "year_level": "1", "section": "A",
    }
    await login(client, "auditor")
    assert (await client.post("/api/library/users", json=payload)).status_code == 403
    await client.post("/api/admin/logout")
    await login(client, "librarian")
    created = await client.post("/api/library/users", json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["program"] == "BSIT"
    assert (await client.post("/api/library/users", json=payload)).status_code == 409
    for category in ("faculty", "non-teaching personnel", "administrator", "visitor"):
        updated = await client.put("/api/library/users/LC-100", json={
            **payload, "user_type": category,
        })
        assert updated.status_code == 200, updated.text
        assert updated.json()["user_type"] == category
    visitor = await client.post("/api/library/users", json={
        "number": "VIS-100", "name": "Guest Rivera", "user_type": "visitor",
    })
    assert visitor.status_code == 201, visitor.text
    assert visitor.json()["email"] == ""
    assert (await client.get("/api/library/users/VIS-100")).status_code == 200


@pytest.mark.asyncio
async def test_google_linked_category_cannot_be_overridden(auth_context):
    client, db = auth_context
    await add_librarian(db, "librarian")
    user = User(email="staff@life.edu.ph", name="Staff", google_id="google-1", role="non-teaching personnel")
    db.add(user)
    await db.flush()
    db.add(StudentProfile(user_id=user.id, student_number="STAFF-1", user_type="non-teaching personnel"))
    await db.commit()
    await login(client, "librarian")
    response = await client.put("/api/library/users/STAFF-1", json={
        "number": "STAFF-1", "name": "Staff", "email": "staff@life.edu.ph",
        "user_type": "student",
    })
    assert response.status_code == 409
    response = await client.put("/api/library/users/STAFF-1", json={
        "number": "STAFF-2", "name": "Staff", "email": "staff@life.edu.ph",
        "user_type": "non-teaching personnel",
    })
    assert response.status_code == 409
    assert (await db.scalar(select(StudentProfile).where(StudentProfile.student_number == "STAFF-1"))).user_type == "non-teaching personnel"
