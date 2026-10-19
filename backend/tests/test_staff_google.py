import pytest
from sqlalchemy import select
from app.auth import issue_student
from app.models import User, StudentProfile, Librarian, StaffGoogleAccess
from test_librarian_auth import auth_context, add_librarian, login


@pytest.mark.asyncio
async def test_google_staff_access_requires_explicit_grant_and_verified_session(auth_context):
    client, db = auth_context
    await add_librarian(db, 'librarian')
    user = User(name='Staff Google User', email='google.staff@life.edu.ph', role='faculty', is_active=True)
    db.add(user)
    await db.flush()
    profile = StudentProfile(user_id=user.id, student_number='STAFF-001', user_type='faculty', is_active=True)
    db.add(profile)
    await db.commit()
    client.cookies.set('library_session', issue_student(user.id, google_authenticated=True))
    assert (await client.get('/api/admin/me')).status_code == 401
    assert (await client.post('/api/admin/google-access', json={'number':'STAFF-001','role':'librarian'})).status_code == 401
    client.cookies.clear()
    await login(client, 'librarian')
    result = await client.post('/api/admin/google-access', json={'number':'STAFF-001','role':'auditor'})
    assert result.status_code == 201, result.text
    staff_id = result.json()['id']
    assert (await client.post('/api/admin/google-access', json={'number':'STAFF-001','role':'librarian'})).status_code == 409
    client.cookies.clear()
    client.cookies.set('library_session', issue_student(user.id))
    assert (await client.get('/api/admin/me')).status_code == 401
    client.cookies.clear()
    client.cookies.set('library_session', issue_student(user.id, google_authenticated=True))
    assert (await client.get('/api/admin/me')).json()['role'] == 'auditor'
    assert (await client.post('/api/admin/google-access', json={'number':'STAFF-001','role':'librarian'})).status_code == 403
    assert (await client.get('/api/library/settings')).status_code == 403
    staff = await db.get(Librarian, staff_id)
    staff.role = 'librarian_associate'
    await db.commit()
    assert (await client.get('/api/admin/me')).json()['role'] == 'librarian_associate'
    staff.is_active = False
    await db.commit()
    assert (await client.get('/api/admin/me')).status_code == 401
    staff.is_active = True
    profile.is_active = False
    await db.commit()
    assert (await client.get('/api/admin/me')).status_code == 401
    profile.is_active = True
    await db.commit()
    assert (await client.post('/api/admin/logout')).status_code == 204
    client.cookies.clear()
    assert (await client.get('/api/admin/me')).status_code == 401
