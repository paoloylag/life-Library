"""Opt-in Calendar integration with encrypted tokens and durable sync jobs."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

import httpx
from authlib.integrations.starlette_client import OAuth
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.auth import current_user, student_sessions
from app.config import settings
from app.database import SessionLocal, get_db
from app.models import BookingCalendarSync, BookingResource, FacilityBooking, GoogleCalendarConnection

router = APIRouter(prefix="/api/calendar", tags=["Google Calendar"])
SCOPE = "https://www.googleapis.com/auth/calendar.events.owned"
EVENTS = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
oauth = OAuth()
oauth.register(name="calendar", client_id=settings.google_client_id, client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile " + SCOPE})
logger = logging.getLogger(__name__)


def enabled():
    return settings.google_calendar_enabled


def cipher():
    return Fernet(settings.google_calendar_encryption_key.encode())


def configured():
    if not enabled() or not settings.google_client_id or not settings.google_client_secret:
        return False
    try:
        cipher()
        return True
    except (ValueError, TypeError):
        return False


async def calendar_user(request: Request, db=Depends(get_db)):
    user = await current_user(request, db)
    payload = student_sessions.loads(request.cookies.get("library_session", ""), max_age=43200)
    if payload.get("google_authenticated") is not True or not user.google_id:
        raise HTTPException(403, "Sign in with Google to connect your calendar")
    if not user.profile or not user.profile.is_active or user.profile.user_type == "visitor":
        raise HTTPException(403, "Calendar connections require an active school Library User")
    return user


@router.get("/status")
async def status(user=Depends(calendar_user), db=Depends(get_db)):
    if not configured():
        return {"enabled": False, "connected": False}
    connection = await db.get(GoogleCalendarConnection, user.id)
    jobs = (await db.scalars(select(BookingCalendarSync).where(BookingCalendarSync.user_id == user.id))).all()
    return {"enabled": True, "connected": connection is not None,
        "needs_reconnect": bool(connection and connection.needs_reconnect),
        "email": connection.email if connection else None,
        "pending": sum(job.state == "pending" for job in jobs),
        "failed": sum(job.state == "failed" for job in jobs)}


@router.get("/connect")
async def connect(request: Request, user=Depends(calendar_user)):
    if not configured():
        raise HTTPException(503, "Google Calendar is not configured")
    request.session["calendar_user_id"] = user.id
    return await oauth.calendar.authorize_redirect(request, settings.google_calendar_redirect_uri,
        access_type="offline", prompt="consent select_account", include_granted_scopes="true")


@router.get("/callback")
async def callback(request: Request, db=Depends(get_db)):
    result = "failed"
    expected = request.session.pop("calendar_user_id", None)
    if not configured():
        raise HTTPException(503, "Google Calendar is not configured")
    try:
        user = await calendar_user(request, db)
        if expected != user.id:
            raise ValueError("Session changed")
        token = await oauth.calendar.authorize_access_token(request)
        info = token.get("userinfo") or {}
        if not info.get("email_verified") or info.get("sub") != user.google_id:
            result = "wrong_account"
            raise ValueError("Account mismatch")
        if SCOPE not in str(token.get("scope", "")).split():
            result = "permission_required"
            raise ValueError("Calendar permission not granted")
        connection = await db.get(GoogleCalendarConnection, user.id)
        refresh = token.get("refresh_token")
        if not refresh and not connection:
            result = "reconnect"
            raise ValueError("Offline consent required")
        encrypted = cipher().encrypt(refresh.encode()).decode() if refresh else connection.refresh_token_encrypted
        if connection:
            connection.refresh_token_encrypted = encrypted
            connection.email = info["email"]
            connection.needs_reconnect = False
        else:
            db.add(GoogleCalendarConnection(user_id=user.id, email=info["email"],
                refresh_token_encrypted=encrypted, connected_at=datetime.now(timezone.utc), needs_reconnect=False))
        await db.flush()
        # Connecting also catches up the booker's current/upcoming reservations.
        for booking in (await db.scalars(select(FacilityBooking).where(FacilityBooking.ends_at > datetime.now(timezone.utc)))).all():
            if booking.owner_id == user.id or (booking.owner_id is None and booking.participants and booking.participants[0].get("user_id") == user.id):
                await queue_booking(db, booking)
        await db.commit()
        result = "connected"
    except Exception:
        await db.rollback()
        # OAuth/token exceptions may contain credentials; never log exception text.
        logger.warning("Google Calendar connection did not complete")
    return RedirectResponse(settings.frontend_url.rstrip("/") + "/book?calendar=" + result)


@router.post("/disconnect", status_code=204)
async def disconnect(user=Depends(calendar_user), db=Depends(get_db)):
    if not enabled():
        raise HTTPException(503, "Google Calendar is not enabled")
    connection = await db.scalar(select(GoogleCalendarConnection).where(GoogleCalendarConnection.user_id == user.id).with_for_update())
    if connection:
        await db.delete(connection)
    await db.commit()
    return Response(status_code=204)


@router.post("/retry", status_code=204)
async def retry(user=Depends(calendar_user), db=Depends(get_db)):
    if not configured():
        raise HTTPException(503, "Google Calendar is not configured")
    connection = await db.get(GoogleCalendarConnection, user.id)
    if not connection or connection.needs_reconnect:
        raise HTTPException(409, "Reconnect Google Calendar before retrying")
    for job in (await db.scalars(select(BookingCalendarSync).where(BookingCalendarSync.user_id == user.id, BookingCalendarSync.state == "failed").with_for_update())).all():
        job.state, job.attempts, job.last_error = "pending", 0, None
        job.next_attempt_at = datetime.now(timezone.utc)
    await db.commit()
    return Response(status_code=204)


async def queue_booking(db, booking):
    if not configured():
        return
    user_id = booking.owner_id or (booking.participants[0].get("user_id") if booking.participants else None)
    if not user_id or not await db.get(GoogleCalendarConnection, user_id):
        return
    await db.flush()
    job = await db.scalar(select(BookingCalendarSync).where(BookingCalendarSync.booking_id == booking.id).with_for_update())
    if not job:
        event_id = uuid5(NAMESPACE_URL, f"{settings.google_client_id}:{settings.frontend_url}:booking:{booking.id}:user:{user_id}").hex
        job = BookingCalendarSync(booking_id=booking.id, user_id=user_id, event_id=event_id)
        db.add(job)
    job.state, job.attempts, job.last_error = "pending", 0, None
    job.next_attempt_at = datetime.now(timezone.utc)


def event_body(booking, resource):
    start, end = booking.starts_at, booking.ends_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    description = f"Reservation #{booking.id}\nResource: {resource.name}\nManage booking: {settings.frontend_url.rstrip('/')}/book?view=history\n\nBefore using the facility, please surrender your ID to the librarian and collect your pass.\nPlease return your pass to the librarian and collect your ID after your session."
    slug = {"nap_pod":"nap-pod", "collaboration_room":"collaboration-room"}.get(resource.kind)
    if slug:
        description += f"\nGuidelines: {settings.frontend_url.rstrip('/')}/guidelines/{slug}"
    return {"summary": f"Life College Library - {resource.name} (Reservation #{booking.id})",
        "description": description, "location": "Life College Library",
        "start": {"dateTime":start.isoformat(),"timeZone":"Asia/Manila"},
        "end": {"dateTime":max(end,start+timedelta(seconds=1)).isoformat(),"timeZone":"Asia/Manila"},
        "visibility":"private", "extendedProperties":{"private":{"libraryBookingId":str(booking.id)}}}


def http_client():
    return httpx.AsyncClient(timeout=15)


async def sync_job(db, job):
    connection = await db.scalar(select(GoogleCalendarConnection).where(GoogleCalendarConnection.user_id == job.user_id).with_for_update())
    if not connection or connection.needs_reconnect:
        job.state, job.last_error = "failed", "Reconnect Google Calendar to sync this booking"
        return
    try:
        refresh = cipher().decrypt(connection.refresh_token_encrypted.encode()).decode()
        async with http_client() as client:
            response = await client.post("https://oauth2.googleapis.com/token", data={"grant_type":"refresh_token", "refresh_token":refresh,
                "client_id":settings.google_client_id,"client_secret":settings.google_client_secret})
            if response.status_code in (400,401) and response.json().get("error") == "invalid_grant":
                connection.needs_reconnect = True
                job.state, job.last_error = "failed", "Google Calendar access expired or was revoked. Reconnect your calendar."
                return
            response.raise_for_status()
            token = response.json()
            if token.get("refresh_token"):
                connection.refresh_token_encrypted = cipher().encrypt(token["refresh_token"].encode()).decode()
            headers = {"Authorization":"Bearer "+token["access_token"]}
            booking = await db.get(FacilityBooking, job.booking_id)
            cancelled = any(action.get("action") == "cancelled" for action in booking.actions)
            if cancelled:
                response = await client.delete(EVENTS+"/"+job.event_id, headers=headers, params={"sendUpdates":"none"})
                if response.status_code not in (404,410):
                    response.raise_for_status()
                job.event_url = None
            else:
                resource = await db.get(BookingResource, booking.resource_id)
                body = event_body(booking,resource)
                response = await client.patch(EVENTS+"/"+job.event_id, headers=headers, json=body, params={"sendUpdates":"none"})
                if response.status_code == 404:
                    response = await client.post(EVENTS, headers=headers, json={**body,"id":job.event_id}, params={"sendUpdates":"none"})
                    if response.status_code == 409:
                        response = await client.patch(EVENTS+"/"+job.event_id, headers=headers, json=body, params={"sendUpdates":"none"})
                response.raise_for_status()
                job.event_url = response.json().get("htmlLink")
            job.state, job.last_error = "synced", None
    except Exception:
        job.attempts += 1
        job.state = "failed" if job.attempts >= 5 else "pending"
        job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=min(3600,15*2**job.attempts))
        job.last_error = "Calendar sync failed. Your booking is saved; sync will retry." if job.state == "pending" else "Calendar sync failed after retries. Your booking is saved. Try syncing again."
        logger.warning("Calendar sync unsuccessful for booking %s",job.booking_id)


async def worker():
    while True:
        try:
            async with SessionLocal() as db:
                job = await db.scalar(select(BookingCalendarSync).where(BookingCalendarSync.state == "pending", BookingCalendarSync.next_attempt_at <= datetime.now(timezone.utc))
                    .order_by(BookingCalendarSync.next_attempt_at).with_for_update(skip_locked=True).limit(1))
                if job:
                    await sync_job(db,job)
                    await db.commit()
        except Exception:
            logger.warning("Calendar worker iteration failed")
        await asyncio.sleep(5)
