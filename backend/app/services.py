import hashlib,secrets
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.config import settings
from app.models import LibrarySession,LibraryVisit,StudentProfile
async def scan(db,token,user):
    now=datetime.now(timezone.utc); session=await db.scalar(select(LibrarySession).where(LibrarySession.token_hash==hashlib.sha256(token.encode()).hexdigest()).with_for_update())
    if not session or session.status!="open" or not session.starts_at<=now<=session.expires_at: raise HTTPException(410,"QR code is invalid or expired")
    profile=await db.scalar(select(StudentProfile).where(StudentProfile.user_id==user.id).with_for_update())
    if not profile or not profile.is_active: raise HTTPException(403,"Account is not registered for library attendance")
    latest=await db.scalar(select(LibraryVisit).where(LibraryVisit.student_profile_id==profile.id,LibraryVisit.library_session_id==session.id).order_by(LibraryVisit.time_in.desc()).limit(1))
    if latest and (now-latest.time_in).total_seconds()<settings.duplicate_scan_seconds:return "duplicate",latest
    visit=LibraryVisit(student_profile_id=profile.id,library_session_id=session.id,time_in=now,status="checked_in",source="qr");db.add(visit)
    await db.commit();await db.refresh(visit);return "check_in",visit
def token_pair():
    raw=secrets.token_urlsafe(32);return raw,hashlib.sha256(raw.encode()).hexdigest()
