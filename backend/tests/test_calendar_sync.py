from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app import calendar_sync as cal
from app.auth import issue_student
from app.config import settings
from app.models import User, StudentProfile, BookingResource, FacilityBooking, GoogleCalendarConnection, BookingCalendarSync
from test_librarian_auth import auth_context


@pytest.fixture
def calendar_config(monkeypatch):
    monkeypatch.setattr(settings, "google_calendar_enabled", True)
    monkeypatch.setattr(settings, "google_calendar_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "google_client_id", "calendar-test-client")
    monkeypatch.setattr(settings, "google_client_secret", "calendar-test-secret")


async def setup_user(db, client):
    user=User(name="Calendar User",email="calendar@life.edu.ph",google_id="google-sub-1",role="student",is_active=True)
    db.add(user)
    await db.flush()
    db.add(StudentProfile(user_id=user.id,student_number="CAL-1",user_type="student",is_active=True))
    await db.commit()
    client.cookies.set("library_session",issue_student(user.id,google_authenticated=True))
    return user


async def setup_booking(db,user):
    resource=BookingResource(name="Nap Pod 1",kind="nap_pod",duration_minutes=45,max_minutes=90,capacity=1,is_active=True)
    db.add(resource)
    await db.flush()
    now=datetime.now(timezone.utc)
    booking=FacilityBooking(resource_id=resource.id,owner_id=user.id,starts_at=now,ends_at=now+timedelta(minutes=45),
        participants=[{"user_id":user.id,"name":user.name}],source="user",actions=[])
    db.add(booking)
    db.add(GoogleCalendarConnection(user_id=user.id,email=user.email,refresh_token_encrypted=cal.cipher().encrypt(b"private-refresh").decode(),connected_at=now,needs_reconnect=False))
    await db.commit()
    return booking


@pytest.mark.asyncio
async def test_calendar_authorization_and_token_privacy(auth_context,calendar_config,monkeypatch):
    client,db=auth_context
    assert (await client.get('/api/calendar/status')).status_code==401
    user=await setup_user(db,client)
    assert (await client.get('/api/calendar/status')).json()['connected'] is False
    client.cookies.clear()
    client.cookies.set('library_session',issue_student(user.id))
    assert (await client.get('/api/calendar/connect')).status_code==403
    client.cookies.clear()
    client.cookies.set('library_session',issue_student(user.id,google_authenticated=True))
    await setup_booking(db,user)
    response=await client.get('/api/calendar/status')
    assert response.json()['connected'] is True
    assert 'private-refresh' not in response.text and 'refresh_token' not in response.text
    monkeypatch.setattr(settings,'app_env','production')
    monkeypatch.setattr(settings,'google_calendar_enabled',False)
    assert (await client.get('/api/calendar/status')).json()['enabled'] is False
    assert (await client.get('/api/calendar/connect')).status_code==503
    monkeypatch.setattr(settings,'google_calendar_enabled',True)
    assert (await client.get('/api/calendar/status')).json()['enabled'] is True


@pytest.mark.asyncio
@pytest.mark.parametrize('sub,scope,expected',[('other-account',cal.SCOPE,'wrong_account'),('google-sub-1','openid email profile','permission_required'),('google-sub-1',cal.SCOPE,'connected')])
async def test_calendar_callback_identity_and_consent(auth_context,calendar_config,monkeypatch,sub,scope,expected):
    client,db=auth_context
    user=await setup_user(db,client)
    async def redirect(request,*args,**kwargs):
        assert kwargs['access_type']=='offline'
        assert 'consent' in kwargs['prompt']
        return RedirectResponse('https://accounts.google.com/')
    async def token(request):
        return {'userinfo':{'sub':sub,'email':user.email,'email_verified':True},'scope':scope,'refresh_token':'never-plaintext'}
    monkeypatch.setattr(cal.oauth.calendar,'authorize_redirect',redirect)
    monkeypatch.setattr(cal.oauth.calendar,'authorize_access_token',token)
    assert (await client.get('/api/calendar/connect')).status_code==307
    user_id=user.id
    result=await client.get('/api/calendar/callback')
    assert result.headers['location'].endswith('calendar='+expected)
    connection=await db.get(GoogleCalendarConnection,user_id)
    if expected=='connected':
        assert connection.refresh_token_encrypted!='never-plaintext'
        assert cal.cipher().decrypt(connection.refresh_token_encrypted.encode())==b'never-plaintext'
    else:
        assert connection is None


@pytest.mark.asyncio
async def test_calendar_create_update_cancel_and_idempotency(auth_context,calendar_config,monkeypatch):
    client,db=auth_context
    user=await setup_user(db,client)
    booking=await setup_booking(db,user)
    await cal.queue_booking(db,booking)
    await db.commit()
    job=await db.get(BookingCalendarSync,booking.id)
    event_id=job.event_id
    calls=[]
    exists=False
    def handle(request):
        nonlocal exists
        calls.append((request.method,str(request.url),request.content))
        if 'oauth2.googleapis.com' in str(request.url):
            return httpx.Response(200,json={'access_token':'access-private'})
        if request.method=='PATCH':
            return httpx.Response(200 if exists else 404,json={'htmlLink':'https://calendar.google.com/event'})
        if request.method=='POST':
            exists=True
            return httpx.Response(200,json={'htmlLink':'https://calendar.google.com/event'})
        return httpx.Response(204)
    monkeypatch.setattr(cal,'http_client',lambda:httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    await cal.sync_job(db,job)
    assert job.state=='synced'
    inserts=[call for call in calls if call[0]=='POST' and '/calendar/v3/' in call[1]]
    assert len(inserts)==1 and event_id.encode() in inserts[0][2]
    assert b'Reservation #'+str(booking.id).encode() in inserts[0][2]
    assert b'Asia/Manila' in inserts[0][2] and b'attendees' not in inserts[0][2]
    assert b'guidelines/nap-pod' in inserts[0][2]
    booking.ends_at+=timedelta(minutes=45)
    await cal.queue_booking(db,booking)
    await cal.sync_job(db,job)
    assert job.event_id==event_id and job.state=='synced'
    assert len([call for call in calls if call[0]=='POST' and '/calendar/v3/' in call[1]])==1
    booking.actions=[{'action':'cancelled'}]
    await cal.queue_booking(db,booking)
    await cal.sync_job(db,job)
    assert job.state=='synced' and job.event_url is None
    assert calls[-1][0]=='DELETE'


@pytest.mark.asyncio
async def test_calendar_failure_does_not_erase_booking_and_retry_disconnect(auth_context,calendar_config,monkeypatch):
    client,db=auth_context
    user=await setup_user(db,client)
    booking=await setup_booking(db,user)
    await cal.queue_booking(db,booking)
    await db.commit()
    job=await db.get(BookingCalendarSync,booking.id)
    monkeypatch.setattr(cal,'http_client',lambda:httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(503,json={'error':'private-refresh'}))))
    for _ in range(5):
        await cal.sync_job(db,job)
    assert job.state=='failed' and 'private-refresh' not in job.last_error
    assert await db.get(FacilityBooking,booking.id) is not None
    await db.commit()
    assert (await client.post('/api/calendar/retry')).status_code==204
    assert job.state=='pending' and job.attempts==0
    assert (await client.post('/api/calendar/disconnect')).status_code==204
    assert await db.get(GoogleCalendarConnection,user.id) is None
    await cal.sync_job(db,job)
    assert job.state=='failed'


@pytest.mark.asyncio
async def test_revoked_access_requires_reconnect(auth_context,calendar_config,monkeypatch):
    client,db=auth_context
    user=await setup_user(db,client)
    booking=await setup_booking(db,user)
    await cal.queue_booking(db,booking)
    job=await db.scalar(select(BookingCalendarSync))
    monkeypatch.setattr(cal,'http_client',lambda:httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(400,json={'error':'invalid_grant'}))))
    await cal.sync_job(db,job)
    assert (await db.get(GoogleCalendarConnection,user.id)).needs_reconnect is True
    assert job.state=='failed'


@pytest.mark.asyncio
async def test_booking_routes_queue_calendar_changes(auth_context,calendar_config,monkeypatch):
    from app import bookings
    from app.models import BookingEmail
    from app.booking_guidelines import GUIDELINES_VERSION
    client,db=auth_context
    user=await setup_user(db,client)
    old=await setup_booking(db,user)
    timestamp=datetime(2026,10,19,6,0,tzinfo=timezone.utc)
    monkeypatch.setattr(bookings,'now',lambda:timestamp)
    monkeypatch.setattr(settings,'booking_email_enabled',True)
    old.starts_at=timestamp-timedelta(hours=2)
    old.ends_at=timestamp-timedelta(hours=1)
    old.ended_at=old.ends_at
    await db.commit()
    body={'resource_id':old.resource_id,'use_profile':True,'guidelines_accepted':True,'guidelines_version':GUIDELINES_VERSION}
    headers={'X-Booking-Mode':'user'}
    response=await client.post('/api/bookings',json=body,headers=headers)
    assert response.status_code==200,response.text
    booking_id=response.json()['id']
    job=await db.get(BookingCalendarSync,booking_id)
    assert job.user_id==user.id and job.state=='pending'
    assert await db.scalar(select(BookingEmail.id).where(BookingEmail.booking_id==booking_id,BookingEmail.kind=='confirmed'))
    for action,payload in [('extend',{'minutes':45}),('end',None)]:
        job.state='synced'
        await db.commit()
        response=await client.post(f'/api/bookings/{booking_id}/{action}',json=payload,headers=headers)
        assert response.status_code==200,response.text
        assert job.state=='pending'
        kind='extended' if action=='extend' else 'ended'
        assert await db.scalar(select(BookingEmail.id).where(BookingEmail.booking_id==booking_id,BookingEmail.kind==kind))
    future=await client.post('/api/bookings',headers=headers,json={**body,'starts_at':(timestamp+timedelta(hours=2)).isoformat()})
    assert future.status_code==200,future.text
    future_id=future.json()['id']
    future_job=await db.get(BookingCalendarSync,future_id)
    future_job.state='synced'
    await db.commit()
    result=await client.post(f'/api/bookings/{future_id}/cancel',headers=headers)
    assert result.status_code==200,result.text
    assert future_job.state=='pending'
    assert await db.scalar(select(BookingEmail.id).where(BookingEmail.booking_id==future_id,BookingEmail.kind=='cancelled'))
