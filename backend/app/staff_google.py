"""Admin-controlled links; user category and Google OU never grant staff access."""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app.auth import librarian_admin, hash_password
from app.database import get_db
from app.models import Librarian, User, StudentProfile, StaffGoogleAccess, LibrarySettingsAudit

router = APIRouter(prefix="/api/admin", tags=["Staff access"])


class Grant(BaseModel):
    number: str
    role: str


@router.post("/google-access", status_code=201)
async def grant_google_access(body: Grant, admin=Depends(librarian_admin), db=Depends(get_db)):
    if body.role not in ("librarian", "librarian_associate", "auditor", "qr_display"):
        raise HTTPException(422, "Invalid staff role")
    user = await db.scalar(select(User).join(StudentProfile).where(
        StudentProfile.student_number == body.number, StudentProfile.is_active.is_(True), User.is_active.is_(True)))
    if not user or not user.email or not user.email.lower().endswith("@life.edu.ph"):
        raise HTTPException(422, "Select an active Library User with a Life College email")
    if await db.scalar(select(StaffGoogleAccess.user_id).where(StaffGoogleAccess.user_id == user.id)):
        raise HTTPException(409, "This user already has staff access. Edit their Staff Account instead.")
    row = await db.scalar(select(Librarian).where(func.lower(Librarian.email) == user.email.lower()))
    if row:
        if row.is_development or not row.is_active or row.role != body.role:
            raise HTTPException(409, "An existing staff account uses this email. Select its current role; inactive and development accounts cannot be linked.")
        if await db.get(StaffGoogleAccess, row.id):
            raise HTTPException(409, "This staff account is already linked")
    else:
        row = Librarian(name=user.name, email=user.email.lower(), role=body.role, is_active=True,
                        password_hash=hash_password(secrets.token_urlsafe(64)))
        db.add(row)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, "A staff account with this email already exists")
    db.add(StaffGoogleAccess(librarian_id=row.id, user_id=user.id))
    db.add(LibrarySettingsAudit(action="staff.google_access.granted", actor=admin.name, actor_id=admin.id,
        actor_email=admin.email, changed_fields=["staff_role", "google_user_id"], before_values={},
        after_values={"staff_id":row.id,"google_user_id":user.id,"role":row.role}, created_at=datetime.now(timezone.utc)))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Staff access already exists for this user or email")
    return {"id":row.id,"name":row.name,"email":row.email,"role":row.role}
