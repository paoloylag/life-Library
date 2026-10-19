from datetime import UTC, datetime, timedelta

import pytest

from app.auth import issue_student
from app.booking_guidelines import GUIDELINES_VERSION
from app.models import User, StudentProfile

pytest_plugins = ["test_library_api"]


@pytest.fixture(autouse=True)
def booking_test_clock(monkeypatch):
    monkeypatch.setattr('app.bookings.now', lambda: datetime(2026, 10, 18, 5, 0, tzinfo=UTC))

PERSON = {
    "name": "Sample Student",
    "category": "student",
    "program": "BS-ENTREP",
    "year_level": "1",
}


@pytest.mark.asyncio
async def test_booking_hours_and_closing_boundary(client, api_db, monkeypatch):
    from app.models import LibraryConfiguration
    api_db.add(LibraryConfiguration(id=1, values={"bookingOpensAt":"09:00","bookingClosesAt":"19:00"}, updated_at=datetime.now(UTC)))
    await api_db.commit()
    import app.bookings as module
    timestamp = datetime(2026, 10, 18, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(module, 'now', lambda: timestamp)
    rid = await resource(client)
    availability = (await client.get('/api/bookings/availability')).json()['resources'][0]
    assert availability['available_now'] is False
    for interval in availability['free_intervals']:
        assert datetime.fromisoformat(interval['starts_at']).astimezone(module.MANILA).hour >= 9
        assert datetime.fromisoformat(interval['ends_at']).astimezone(module.MANILA).hour <= 19
    body = {'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':rid, 'participants':[PERSON]}
    assert (await client.post('/api/bookings', json=body)).status_code == 422
    for hour, minute in [(0,59),(10,16),(11,0)]:
        result = await client.post('/api/bookings', json={**body,'starts_at':timestamp.replace(hour=hour,minute=minute).isoformat()})
        assert result.status_code == 422, result.text
    valid = await client.post('/api/bookings', json={**body,'starts_at':timestamp.replace(hour=10,minute=15).isoformat()})
    assert valid.status_code == 200, valid.text
    timestamp = timestamp.replace(hour=10,minute=16)
    listed = (await client.get('/api/bookings')).json()['items'][0]
    assert listed['can_extend'] is False
    assert '19:00' in listed['extension_unavailable_reason']
    assert (await client.post(f"/api/bookings/{valid.json()['id']}/extend",json={'minutes':45})).status_code == 422


@pytest.mark.asyncio
async def test_custom_resource_types(client):
    headers = {"X-Booking-Mode": "manual"}
    result = await client.post('/api/bookings/resource-types', headers=headers, json={"label": "  Study   Desks  "})
    assert result.status_code == 200, result.text
    kind = result.json()['kind']
    assert result.json()['label'] == 'Study Desks'
    duplicate = await client.post('/api/bookings/resource-types', headers=headers, json={"label": "study desks"})
    assert duplicate.status_code == 409
    listed = await client.get('/api/bookings/resource-types', headers=headers)
    assert any(item['kind'] == kind for item in listed.json())
    added = await client.post('/api/bookings/resources', json={"name": "Study Desk 1", "kind": kind, "duration_minutes": 60, "max_minutes": 120, "capacity": 1})
    assert added.status_code == 200, added.text
    invalid = await client.post('/api/bookings/resources', json={"name": "Unknown Desk", "kind": "unknown", "duration_minutes": 60, "max_minutes": 120, "capacity": 1})
    assert invalid.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['nap_pod', 'collaboration_room'])
@pytest.mark.parametrize('mode', ['manual', 'user'])
async def test_guideline_agreement_required_and_audited(client, api_db, kind, mode):
    from app.booking_guidelines import guideline
    rid = await resource(client, kind, capacity=3 if kind=='collaboration_room' else 1, duration_minutes=45 if kind=='nap_pod' else 60, max_minutes=90 if kind=='nap_pod' else 120)
    user = User(name=PERSON['name'],email='guideline-user@life.edu.ph',role='student',is_active=True)
    api_db.add(user)
    await api_db.commit()
    client.cookies.set('library_session', issue_student(user.id,google_authenticated=True))
    headers={'X-Booking-Mode':mode}
    documents=await client.get('/api/bookings/guidelines',headers=headers)
    assert documents.status_code==200
    assert len(documents.json()[kind]['sections'][0]['items'])==8
    body={'resource_id':rid,'participants':[PERSON],'additional_member_names':['Other Student','Another Student'] if kind=='collaboration_room' else []}
    if kind=='collaboration_room' and mode=='user':
        for index,name in enumerate(['Other Student','Another Student']):
            member=User(name=name,email=f'guideline-member-{index}@life.edu.ph',role='student',is_active=True)
            api_db.add(member)
            await api_db.flush()
            api_db.add(StudentProfile(user_id=member.id,student_number=f'GM-{index}',user_type='student',is_active=True))
        await api_db.commit()
        body['additional_member_numbers']=['GM-0','GM-1']
    for consent in [{},{'guidelines_accepted':False,'guidelines_version':GUIDELINES_VERSION},{'guidelines_accepted':True,'guidelines_version':'outdated'}]:
        result=await client.post('/api/bookings',headers=headers,json={**body,**consent})
        assert result.status_code==422,result.text
    result=await client.post('/api/bookings',headers=headers,json={**body,'guidelines_accepted':True,'guidelines_version':GUIDELINES_VERSION})
    assert result.status_code==200,result.text
    audit=next(action for action in result.json()['actions'] if action['action']=='guidelines_accepted')
    assert audit['version']==GUIDELINES_VERSION
    assert audit['guidelines']==guideline(kind)
    assert audit['organizer_name']==PERSON['name']
    assert audit['at']
    if mode=='user':
        assert audit['accepted_by_user_id']==user.id
        assert audit['attested_by_librarian_id'] is None
    else:
        assert audit['accepted_by_user_id'] is None
        assert audit['attested_by_librarian_id'] is not None


@pytest.mark.asyncio
async def test_computer_does_not_require_unrelated_guidelines(client):
    rid=await resource(client,'computer',duration_minutes=120,max_minutes=120)
    result=await client.post('/api/bookings',json={'resource_id':rid,'participants':[PERSON]})
    assert result.status_code==200,result.text
    assert not any(action['action']=='guidelines_accepted' for action in result.json()['actions'])


@pytest.mark.asyncio
async def test_student_member_search_and_selection_are_restricted(client, api_db):
    rid=await resource(client,'collaboration_room',duration_minutes=60,max_minutes=120,capacity=6)
    for number,name,category in [('BOOKER','Student Booker','student'),('S1','First Student','student'),('S2','Second Student','student'),('F1','Staff Faculty','faculty')]:
        user=User(name=name,email=number.lower()+'@life.edu.ph',role=category,is_active=True)
        api_db.add(user)
        await api_db.flush()
        api_db.add(StudentProfile(user_id=user.id,student_number=number,user_type=category,is_active=True))
        if number=='BOOKER':
            owner_id=user.id
    await api_db.commit()
    client.cookies.set('library_session',issue_student(owner_id,google_authenticated=True))
    headers={'X-Booking-Mode':'user'}
    result=await client.get('/api/bookings/members',headers=headers)
    assert {item['number'] for item in result.json()['items']}=={'S1','S2'}
    assert (await client.get('/api/bookings/members?q=Faculty',headers=headers)).json()['items']==[]
    manual=await client.get('/api/bookings/members?organizer_number=BOOKER',headers={'X-Booking-Mode':'manual'})
    assert {item['number'] for item in manual.json()['items']}=={'S1','S2'}
    body={'resource_id':rid,'use_profile':True,'guidelines_accepted':True,'guidelines_version':GUIDELINES_VERSION}
    for numbers in [[],['S1','F1'],['S1','BOOKER'],['S1','S1']]:
        rejected=await client.post('/api/bookings',headers=headers,json={**body,'additional_member_numbers':numbers})
        assert rejected.status_code==422,rejected.text
    manual_reject=await client.post('/api/bookings',headers={'X-Booking-Mode':'manual'},json={**body,'organizer_number':'BOOKER','additional_member_numbers':['S1','F1']})
    assert manual_reject.status_code==422
    accepted=await client.post('/api/bookings',headers=headers,json={**body,'additional_member_numbers':['S1','S2'],'additional_member_names':['Wrong Name','Spoofed Name']})
    assert accepted.status_code==200,accepted.text
    assert accepted.json()['member_names']==['Student Booker','First Student','Second Student']


@pytest.mark.asyncio
async def test_collab_requires_three_distinct_full_names(client):
    rid=await resource(client,'collaboration_room',duration_minutes=60,max_minutes=120,capacity=3)
    body={'resource_id':rid,'participants':[PERSON],'guidelines_accepted':True,'guidelines_version':GUIDELINES_VERSION}
    for names in [[],['Second Person'],['Second Person','second person'],[PERSON['name'],'Third Person'],['   ','Third Person'],['Single','Third Person'],['Second Person','Third Person','Fourth Person']]:
        response=await client.post('/api/bookings',json={**body,'additional_member_names':names})
        assert response.status_code==422,response.text
    booked=await client.post('/api/bookings',json={**body,'additional_member_names':['  Second   Person  ','Third Person']})
    assert booked.status_code==200,booked.text
    assert booked.json()['member_names']==[PERSON['name'],'Second Person','Third Person']
    assert booked.json()['actions'][0]['additional_member_names']==['Second Person','Third Person']
    computer=await resource(client,'computer',name='Separate Computer',duration_minutes=60,max_minutes=120)
    conflict=await client.post('/api/bookings',json={'resource_id':computer,'participants':[{**PERSON,'name':'Second Person'}]})
    assert conflict.status_code==409,conflict.text


@pytest.mark.asyncio
async def test_configurable_booking_hours_default_and_save(client, monkeypatch):
    from app.library_settings import LibrarySettings
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        LibrarySettings(bookingOpensAt='18:00', bookingClosesAt='06:00')
    with pytest.raises(ValidationError):
        LibrarySettings(bookingOpensAt='25:00')
    monkeypatch.setattr('app.bookings.now', lambda: datetime(2026, 10, 18, 0, 0, tzinfo=UTC))
    rid = await resource(client)
    data = (await client.get('/api/bookings/availability')).json()
    assert data['booking_hours']['opens_at'] == '06:00'
    assert data['booking_hours']['closes_at'] == '18:00'
    assert data['resources'][0]['available_now']
    settings = (await client.get('/api/library/settings')).json()['settings']
    settings.update(bookingOpensAt='08:30', bookingClosesAt='17:15')
    saved = await client.put('/api/library/settings', json=settings)
    assert saved.status_code == 200, saved.text
    data = (await client.get('/api/bookings/availability')).json()
    assert data['booking_hours']['opens_at'] == '08:30'
    assert not data['resources'][0]['available_now']
    assert (await client.post('/api/bookings', json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':rid,'participants':[PERSON]})).status_code == 422


@pytest.mark.asyncio
async def test_cancel_future_booking_releases_slot_and_preserves_history(client, api_db, monkeypatch):
    import app.bookings as module
    timestamp = datetime(2026, 10, 18, 5, 0, tzinfo=UTC)
    monkeypatch.setattr(module, 'now', lambda: timestamp)
    rid = await resource(client)
    owner = User(name=PERSON['name'], email='cancel-owner@life.edu.ph', role='student', is_active=True)
    other = User(name='Another Student', email='cancel-other@life.edu.ph', role='student', is_active=True)
    api_db.add_all([owner, other])
    await api_db.commit()
    headers = {'X-Booking-Mode': 'user'}
    client.cookies.set('library_session', issue_student(owner.id, google_authenticated=True))
    start = timestamp + timedelta(minutes=20)
    result = await client.post('/api/bookings', headers=headers, json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, 'starts_at': start.isoformat(), 'participants': [PERSON]})
    assert result.status_code == 200, result.text
    bid = result.json()['id']
    client.cookies.set('library_session', issue_student(other.id, google_authenticated=True))
    assert (await client.post(f'/api/bookings/{bid}/cancel', headers=headers)).status_code == 403
    client.cookies.set('library_session', issue_student(owner.id, google_authenticated=True))
    cancelled = await client.post(f'/api/bookings/{bid}/cancel', headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()['status'] == 'cancelled'
    assert cancelled.json()['starts_at'] == result.json()['starts_at']
    assert cancelled.json()['ends_at'] == result.json()['ends_at']
    assert cancelled.json()['actions'][-1]['action'] == 'cancelled'
    assert (await client.post(f'/api/bookings/{bid}/cancel', headers=headers)).status_code == 200
    assert len((await client.get('/api/bookings', headers=headers)).json()['items']) == 1
    available = (await client.get('/api/bookings/availability')).json()['resources'][0]
    assert available['available_now'] is True
    replacement = await client.post('/api/bookings', headers={'X-Booking-Mode': 'manual'}, json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, 'starts_at': start.isoformat(), 'participants': [PERSON]})
    assert replacement.status_code == 200, replacement.text
    replacement_id = replacement.json()['id']
    assert (await client.post(f'/api/bookings/{replacement_id}/cancel', headers={'X-Booking-Mode':'manual'})).status_code == 200
    timestamp = start + timedelta(minutes=1)
    report = (await client.get('/api/bookings/reports/usage')).json()
    assert report['totals'][0]['bookings'] == 0
    active = await client.post('/api/bookings', json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':rid, 'participants':[PERSON]})
    assert active.status_code == 200
    assert (await client.post(f"/api/bookings/{active.json()['id']}/cancel")).status_code == 409


@pytest.mark.asyncio
async def test_booking_requires_google_and_excludes_visitors(client, api_db):
    rid = await resource(client)
    user = User(name='School Student', email='school@life.edu.ph', role='student', is_active=True)
    api_db.add(user)
    await api_db.commit()
    headers = {'X-Booking-Mode': 'user'}
    client.cookies.set('library_session', issue_student(user.id))
    assert (await client.get('/api/bookings/identity', headers=headers)).status_code == 403
    assert (await client.get('/api/bookings', headers=headers)).status_code == 403
    assert (await client.post('/api/bookings', headers=headers, json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, 'participants': [PERSON]})).status_code == 403
    client.cookies.set('library_session', issue_student(user.id, google_authenticated=True))
    assert (await client.get('/api/bookings/identity', headers=headers)).status_code == 200
    user.role = 'visitor'
    await api_db.commit()
    assert (await client.get('/api/bookings/identity', headers=headers)).status_code == 403
    assert (await client.post('/api/bookings', headers=headers, json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, 'participants': [PERSON]})).status_code == 403
    visitor = {**PERSON, 'category': 'visitor'}
    assert (await client.post('/api/bookings', headers={'X-Booking-Mode': 'manual'}, json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, 'participants': [visitor]})).status_code == 403


@pytest.mark.asyncio
async def test_profile_based_bookings_use_saved_identity(client, api_db):
    rid = await resource(client)
    user = User(name='Profile Student',email='profile-booking@life.edu.ph',role='student',is_active=True)
    api_db.add(user)
    await api_db.flush()
    profile = StudentProfile(user_id=user.id,student_number='PROFILE-BOOK',user_type='student',program='BS-ENTREP-FE',year_level=None,is_active=True)
    api_db.add(profile)
    await api_db.commit()
    manual = await client.post('/api/bookings',headers={'X-Booking-Mode':'manual'},json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':rid,'use_profile':True,'organizer_number':profile.student_number})
    assert manual.status_code == 200, manual.text
    assert manual.json()['participants'][0]['name'] == user.name
    assert manual.json()['participants'][0]['program'] == 'BS-ENTREP-FE'
    client.cookies.set('library_session',issue_student(user.id, google_authenticated=True))
    personal = await client.post('/api/bookings',headers={'X-Booking-Mode':'user'},json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':rid,'use_profile':True,'starts_at':manual.json()['ends_at']})
    assert personal.status_code == 200, personal.text
    assert personal.json()['participants'][0]['name'] == user.name
    assert personal.json()['participants'][0]['year_level'] == ''
    spoof = await client.post('/api/bookings',headers={'X-Booking-Mode':'user'},json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':rid,'use_profile':True,'organizer_number':'ANOTHER-USER'})
    assert spoof.status_code == 422
    profile.is_active = False
    await api_db.commit()
    rejected = await client.post('/api/bookings',headers={'X-Booking-Mode':'manual'},json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':rid,'use_profile':True,'organizer_number':profile.student_number})
    assert rejected.status_code == 422


@pytest.mark.asyncio
async def test_one_nap_pod_per_person_across_manual_and_user_bookings(client, api_db, monkeypatch):
    first_id = await resource(client)
    second_id = await resource(client, name='Second Nap Pod')
    user = User(name='Nap Pod Student',email='nap-limit@life.edu.ph',role='student',is_active=True)
    api_db.add(user)
    await api_db.flush()
    api_db.add(StudentProfile(user_id=user.id,student_number='NAP-USER',user_type='student',is_active=True))
    await api_db.commit()
    client.cookies.set('library_session',issue_student(user.id, google_authenticated=True))
    headers = {'X-Booking-Mode':'user'}
    first = await client.post('/api/bookings',headers=headers,json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':first_id,'use_profile':True})
    assert first.status_code == 200, first.text
    duplicate = await client.post('/api/bookings',headers=headers,json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':second_id,'use_profile':True})
    assert duplicate.status_code == 409
    manual = await client.post('/api/bookings',headers={'X-Booking-Mode':'manual'},json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':second_id,'use_profile':True,'organizer_number':'NAP-USER'})
    assert manual.status_code == 409
    later = await client.post('/api/bookings',headers=headers,json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':second_id,'use_profile':True,'starts_at':first.json()['ends_at']})
    assert later.status_code == 200, later.text
    extension = await client.post(f"/api/bookings/{first.json()['id']}/extend",headers=headers,json={'minutes':45})
    assert extension.status_code == 409
    assert (await client.post(f"/api/bookings/{first.json()['id']}/end",headers=headers)).status_code == 200
    monkeypatch.setattr('app.bookings.now', lambda: datetime(2026, 10, 18, 5, 0, 1, tzinfo=UTC))
    replacement = await client.post('/api/bookings',headers=headers,json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':first_id,'use_profile':True})
    # Its full session would overlap the already scheduled reservation.
    assert replacement.status_code == 409


async def resource(client, kind="nap_pod", **changes):
    body = {
        "name": "Test Resource",
        "kind": kind,
        "duration_minutes": 45,
        "max_minutes": 90,
        "capacity": 1,
        **changes,
    }
    response = await client.post("/api/bookings/resources", json=body)
    assert response.status_code == 200, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_actual_time_overlap_extension_release_and_report(client, monkeypatch):
    import app.bookings as module

    timestamp = datetime(2026, 10, 14, 5, 17, tzinfo=UTC)
    monkeypatch.setattr(module, "now", lambda: timestamp)
    rid = await resource(client)
    body = {'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, "participants": [PERSON]}
    first = await client.post("/api/bookings", json=body)
    assert first.status_code == 200, first.text
    b = first.json()
    assert datetime.fromisoformat(b["starts_at"]) == timestamp
    assert datetime.fromisoformat(b["ends_at"]) == timestamp + timedelta(minutes=45)
    assert (await client.post("/api/bookings", json=body)).status_code == 409
    second = await client.post(
        "/api/bookings", json={**body, "starts_at": b["ends_at"]}
    )
    assert second.status_code == 200
    listed = (await client.get("/api/bookings")).json()["items"]
    assert not next(x for x in listed if x["id"] == b["id"])["can_extend"]
    assert (
        await client.post(f"/api/bookings/{b['id']}/extend", json={"minutes": 45})
    ).status_code == 409
    timestamp += timedelta(minutes=10)
    assert (await client.post(f"/api/bookings/{b['id']}/end")).status_code == 200
    a = (await client.get("/api/bookings/availability")).json()["resources"][0]
    assert a["free_intervals"][0]["starts_at"] == timestamp.isoformat()
    # A full session still cannot fit before the reservation, despite early release.
    assert not a["available_now"]
    report = (await client.get("/api/bookings/reports/usage")).json()
    assert report["totals"][0]["bookings"] == 1
    assert report["breakdowns"][0]["uses"] == 1


@pytest.mark.asyncio
async def test_computer_limit_and_nap_extension(client):
    rid = await resource(client, "computer", duration_minutes=120, max_minutes=120)
    b = (
        await client.post(
            "/api/bookings", json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, "participants": [PERSON]}
        )
    ).json()
    assert not b["can_extend"]
    assert (
        await client.post(f"/api/bookings/{b['id']}/extend", json={"minutes": 1})
    ).status_code == 409
    assert (
        await client.post(
            "/api/bookings/resources",
            json={
                "name": "Invalid PC",
                "kind": "computer",
                "duration_minutes": 120,
                "max_minutes": 121,
                "capacity": 1,
            },
        )
    ).status_code == 422
    rid = await resource(client, name="Nap Two")
    b = (
        await client.post(
            "/api/bookings", json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, "participants": [{**PERSON, "name": "Another Student"}]}
        )
    ).json()
    assert b["can_extend"]
    assert (
        await client.post(f"/api/bookings/{b['id']}/extend", json={"minutes": 45})
    ).status_code == 200
    assert (
        await client.post(f"/api/bookings/{b['id']}/extend", json={"minutes": 1})
    ).status_code == 409


@pytest.mark.asyncio
async def test_cross_resource_participants_cannot_overlap(client):
    nap = await resource(client)
    room = await resource(client,'collaboration_room',name='Collaboration',duration_minutes=60,max_minutes=120,capacity=4)
    computer = await resource(client,'computer',name='Computer',duration_minutes=60,max_minutes=120)
    first = await client.post('/api/bookings',json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':nap,'participants':[PERSON]})
    assert first.status_code == 200
    member = {**PERSON,'name':'Other Organizer'}
    group = await client.post('/api/bookings',json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':room,'additional_member_names':['Additional One','Additional Two'],'participants':[PERSON]})
    assert group.status_code == 409
    pc = await client.post('/api/bookings',json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':computer,'participants':[PERSON]})
    assert pc.status_code == 409
    later = await client.post('/api/bookings',json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':computer,'starts_at':first.json()['ends_at'],'participants':[PERSON]})
    assert later.status_code == 200
    listed = (await client.get('/api/bookings')).json()['items']
    blocked = next(item for item in listed if item['id'] == first.json()['id'])
    assert blocked['can_extend'] is False
    assert blocked['extension_unavailable_reason'] == 'A user in this session has another booking during the extension'
    assert (await client.post(f"/api/bookings/{first.json()['id']}/extend",json={'minutes':45})).status_code == 409
    assert (await client.post(f"/api/bookings/{first.json()['id']}/end")).status_code == 200
    # A different person can still use a free resource concurrently.
    assert (await client.post('/api/bookings',json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':room,'additional_member_names':['Additional One','Additional Two'],'participants':[member]})).status_code == 200


@pytest.mark.asyncio
async def test_collaboration_room_records_organizer_and_member_names(client):
    rid = await resource(
        client, "collaboration_room", duration_minutes=60, max_minutes=120, capacity=3
    )
    staff = {"name": "Sample Faculty", "category": "faculty", "department": "Academics"}
    b = await client.post(
        "/api/bookings", json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, "participants": [PERSON, staff]}
    )
    assert b.status_code == 422
    b = await client.post(
        "/api/bookings", json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, "participants": [staff], "additional_member_names": ["Second Person", "Third Person"]}
    )
    assert b.status_code == 200
    assert len(b.json()['participants']) == 1
    report = (await client.get("/api/bookings/reports/usage")).json()
    assert report["totals"][0]["bookings"] == 1
    assert report["totals"][0]["participant_uses"] == 1
    assert any(x["department"] == "Academics" for x in report["breakdowns"])
    assert (
        await client.post(
            "/api/bookings",
            json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, "participants": [{**PERSON, "year_level": ""}]},
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_owner_controls_and_private_lists(client, api_db):
    rid = await resource(client)
    admin_booking = (
        await client.post(
            "/api/bookings", json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, "participants": [PERSON]}
        )
    ).json()
    user = User(
        name="Sample Student",
        email="booking@life.edu.ph",
        role="student",
        is_active=True,
    )
    api_db.add(user)
    await api_db.commit()
    client.cookies.clear()
    assert (await client.get("/api/bookings")).status_code == 401
    client.cookies.set("library_session", issue_student(user.id, google_authenticated=True))
    assert (await client.get("/api/bookings")).json()["items"] == []
    assert (
        await client.post(f"/api/bookings/{admin_booking['id']}/end")
    ).status_code == 403
    assert (await client.get("/api/bookings/reports/usage")).status_code == 401


@pytest.mark.asyncio
async def test_user_view_does_not_inherit_librarian_session(client, api_db):
    rid = await resource(client)
    manual = await client.post('/api/bookings', headers={'X-Booking-Mode':'manual'}, json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':rid,'participants':[PERSON]})
    assert manual.status_code == 200
    user = User(name='Sample Student',email='mixed-session@life.edu.ph',role='student',is_active=True)
    api_db.add(user)
    await api_db.commit()
    client.cookies.set('library_session',issue_student(user.id, google_authenticated=True))
    headers = {'X-Booking-Mode':'user'}
    assert (await client.get('/api/bookings',headers=headers)).json()['items'] == []
    assert (await client.post(f"/api/bookings/{manual.json()['id']}/end",headers=headers)).status_code == 403
    starts = manual.json()['ends_at']
    personal = await client.post('/api/bookings',headers=headers,json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id':rid,'starts_at':starts,'participants':[PERSON]})
    assert personal.status_code == 200
    assert personal.json()['source'] == 'user'
    assert len((await client.get('/api/bookings',headers=headers)).json()['items']) == 1
    assert len((await client.get('/api/bookings')).json()['items']) == 2


@pytest.mark.asyncio
async def test_invalid_start_times(client):
    rid = await resource(client)
    for start in [
        "2026-01-01T00:00:00",
        "2020-01-01T00:00:00Z",
        "2099-01-01T00:00:00Z",
    ]:
        assert (
            await client.post(
                "/api/bookings",
                json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, "starts_at": start, "participants": [PERSON]},
            )
        ).status_code == 422


@pytest.mark.asyncio
async def test_patron_booking_and_completed_prompt_state(client, api_db, monkeypatch):
    import app.bookings as module

    timestamp = datetime(2026, 10, 14, 5, 17, tzinfo=UTC)
    monkeypatch.setattr(module, "now", lambda: timestamp)
    rid = await resource(client)
    user = User(
        name="Sample Student",
        email="patron@life.edu.ph",
        role="student",
        is_active=True,
    )
    api_db.add(user)
    await api_db.commit()
    client.cookies.clear()
    client.cookies.set("library_session", issue_student(user.id, google_authenticated=True))
    first = await client.post(
        "/api/bookings", json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, "participants": [PERSON]}
    )
    assert first.status_code == 200
    b = first.json()
    future = await client.post(
        "/api/bookings",
        json={'guidelines_accepted': True, 'guidelines_version': GUIDELINES_VERSION, 'resource_id': rid, "starts_at": b["ends_at"], "participants": [PERSON]},
    )
    assert future.status_code == 200
    timestamp += timedelta(minutes=45)
    items = (await client.get("/api/bookings")).json()["items"]
    completed = next(item for item in items if item["id"] == b["id"])
    assert completed["status"] == "completed"
    assert completed["next_reserved"] is True
    assert not completed["can_extend"]
    assert (await client.post(f"/api/bookings/{b['id']}/end")).status_code == 409
