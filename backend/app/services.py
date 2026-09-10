import base64
import hashlib
import hmac
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.models import LibrarySession, LibraryVisit, StudentProfile

MANILA = ZoneInfo("Asia/Manila")


def attendance_day(now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(MANILA).date()


def daily_token(day: date) -> str:
    digest = hmac.new(
        settings.secret_key.encode(),
        f"life-college-library:{day.isoformat()}".encode(),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def utc_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=MANILA).astimezone(timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=MANILA).astimezone(timezone.utc)
    return start, end


def aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def get_or_create_daily_session(db, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    day = attendance_day(now)
    raw = daily_token(day)
    hashed = token_hash(raw)
    session = await db.scalar(
        select(LibrarySession).where(
            LibrarySession.session_date == day,
            LibrarySession.status == "open",
        )
    )
    if session:
        if session.token_hash != hashed:
            session.token_hash = hashed
            await db.commit()
            await db.refresh(session)
        return session, raw

    starts_at, expires_at = utc_bounds(day)
    session = LibrarySession(
        session_date=day,
        name="Library attendance",
        token_hash=hashed,
        starts_at=max(starts_at, now),
        expires_at=expires_at,
        status="open",
        created_by=None,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session, raw


async def scan(db, token, user):
    now = datetime.now(timezone.utc)
    session = await db.scalar(
        select(LibrarySession)
        .where(LibrarySession.token_hash == token_hash(token))
        .with_for_update()
    )
    if (
        not session
        or session.status != "open"
        or not aware_utc(session.starts_at) <= now <= aware_utc(session.expires_at)
    ):
        raise HTTPException(410, "QR code is invalid or expired")

    profile = await db.scalar(
        select(StudentProfile)
        .where(StudentProfile.user_id == user.id)
        .with_for_update()
    )
    if not profile or not profile.is_active:
        raise HTTPException(403, "Account is not registered for library attendance")

    latest = await db.scalar(
        select(LibraryVisit)
        .where(
            LibraryVisit.student_profile_id == profile.id,
            LibraryVisit.library_session_id == session.id,
        )
        .order_by(LibraryVisit.time_in.desc())
        .limit(1)
    )
    if latest and (now - aware_utc(latest.time_in)).total_seconds() < settings.duplicate_scan_seconds:
        return "duplicate", latest

    visit = LibraryVisit(
        student_profile_id=profile.id,
        library_session_id=session.id,
        time_in=now,
        status="checked_in",
        source="qr",
    )
    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    return "check_in", visit
