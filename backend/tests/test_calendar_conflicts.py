from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import func, select

from app import calendar_sync as cal
from app.config import settings
from app.models import FacilityBooking
from test_calendar_sync import calendar_config, setup_user, setup_booking
from test_librarian_auth import auth_context


@pytest.mark.asyncio
@pytest.mark.parametrize("events,expected", [
    ([], "clear"),
    ([{"status":"confirmed","summary":"Never expose this private title"}], "conflict"),
    ([{"status":"confirmed","transparency":"transparent"}], "clear"),
    ([{"status":"cancelled"}], "clear"),
    ([{"attendees":[{"self":True,"responseStatus":"declined"}]}], "clear"),
    ([{"attendees":[{"self":False,"responseStatus":"declined"}]}], "conflict"),
])
async def test_busy_event_filtering_and_privacy(auth_context, calendar_config, monkeypatch, events, expected):
    client, db = auth_context
    user = await setup_user(db, client)
    booking = await setup_booking(db, user)
    calls = []
    def handle(request):
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(200,json={"access_token":"private-access"})
        assert request.url.params["singleEvents"] == "true"
        assert request.url.params["showDeleted"] == "false"
        assert "summary" not in request.url.params["fields"]
        start=datetime.fromisoformat(request.url.params["timeMin"])
        end=datetime.fromisoformat(request.url.params["timeMax"])
        assert end-start == timedelta(minutes=45)
        return httpx.Response(200,json={"items":events})
    monkeypatch.setattr(cal,"http_client",lambda:httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    result=await client.post("/api/calendar/conflicts",json={"resource_id":booking.resource_id})
    assert result.status_code == 200 and result.json() == {"state":expected}
    assert "private" not in result.text and "Never expose" not in result.text
    assert len(calls)==2 and calls[-1].method=="GET"
    assert await db.scalar(select(func.count()).select_from(FacilityBooking)) == 1


@pytest.mark.asyncio
async def test_conflict_pagination_and_error_are_advisory(auth_context, calendar_config, monkeypatch):
    client, db = auth_context
    user=await setup_user(db,client)
    booking=await setup_booking(db,user)
    def handle(request):
        if request.method=="POST":return httpx.Response(200,json={"access_token":"private-access"})
        if request.url.params.get("pageToken")=="next":return httpx.Response(200,json={"items":[{}]})
        return httpx.Response(200,json={"items":[{"transparency":"transparent"}],"nextPageToken":"next"})
    monkeypatch.setattr(cal,"http_client",lambda:httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    payload={"resource_id":booking.resource_id,"starts_at":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
    assert (await client.post("/api/calendar/conflicts",json=payload)).json()=={"state":"conflict"}
    monkeypatch.setattr(cal,"http_client",lambda:httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(503,json={"private":"provider detail"}))))
    result=await client.post("/api/calendar/conflicts",json=payload)
    assert result.json()=={"state":"unavailable"}
    assert await db.scalar(select(func.count()).select_from(FacilityBooking))==1


@pytest.mark.asyncio
async def test_conflict_authorization_and_input_validation(auth_context, calendar_config, monkeypatch):
    client, db=auth_context
    assert (await client.post("/api/calendar/conflicts",json={"resource_id":1})).status_code==401
    user=await setup_user(db,client)
    assert (await client.post("/api/calendar/conflicts",json={"resource_id":1})).json()=={"state":"not_connected"}
    booking=await setup_booking(db,user)
    for start in ["2026-01-01T09:00:00",(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()]:
        assert (await client.post("/api/calendar/conflicts",json={"resource_id":booking.resource_id,"starts_at":start})).status_code==422
    assert (await client.post("/api/calendar/conflicts",json={"resource_id":99999})).status_code==404
    monkeypatch.setattr(settings,"google_calendar_enabled",False)
    assert (await client.post("/api/calendar/conflicts",json={"resource_id":booking.resource_id})).json()=={"state":"disabled"}


@pytest.mark.asyncio
async def test_non_google_user_cannot_read_calendar(auth_context, calendar_config):
    from app.auth import issue_student
    client, db=auth_context
    user=await setup_user(db,client)
    client.cookies.set("library_session",issue_student(user.id))
    assert (await client.post("/api/calendar/conflicts",json={"resource_id":1})).status_code==403
