from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column

from app.auth import librarian_admin
from app.database import Base, get_db
from app.models import LibrarySettingsAudit, StudentProfile, User


class ApprovedGoogleEmail(Base):
    __tablename__ = "approved_google_emails"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    approved_by: Mapped[int] = mapped_column(ForeignKey("librarians.id"))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


async def resolve_alternate_google_user(db, info):
    email = str(info.get("email", "")).strip().lower()
    if info.get("email_verified") is not True or not info.get("sub"):
        raise HTTPException(403, "Google email is not verified")
    approval = await db.scalar(select(ApprovedGoogleEmail).where(
        ApprovedGoogleEmail.email == email, ApprovedGoogleEmail.is_active.is_(True)
    ).with_for_update())
    if not approval:
        raise HTTPException(403, "Use your Life College Google account")
    user = await db.get(User, approval.user_id)
    profile = await db.scalar(select(StudentProfile).where(StudentProfile.user_id == approval.user_id))
    if not user or not user.is_active or not profile or not profile.is_active:
        raise HTTPException(403, "Library account is inactive")
    if approval.google_id and approval.google_id != info["sub"]:
        raise HTTPException(409, "Alternate email is linked to another Google account")
    owner = await db.scalar(select(User.id).where(User.google_id == info["sub"]))
    other = await db.scalar(select(ApprovedGoogleEmail.id).where(
        ApprovedGoogleEmail.google_id == info["sub"], ApprovedGoogleEmail.id != approval.id
    ))
    if (owner is not None and owner != user.id) or other is not None:
        raise HTTPException(409, "Google identity already belongs to another account")
    approval.google_id = info["sub"]
    return user


router = APIRouter()


class AlternateEmailInput(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    is_active: bool = True


@router.get("/api/library/users/{number}/alternate-google-emails")
async def list_alternates(number: str, librarian=Depends(librarian_admin), db=Depends(get_db)):
    profile = await db.scalar(select(StudentProfile).where(StudentProfile.student_number == number))
    if not profile:
        raise HTTPException(404, "Library user not found")
    rows = (await db.scalars(select(ApprovedGoogleEmail).where(ApprovedGoogleEmail.user_id == profile.user_id))).all()
    return [{"email": row.email, "is_active": row.is_active} for row in rows]


@router.put("/api/library/users/{number}/alternate-google-email")
async def approve_alternate(number: str, body: AlternateEmailInput,
                            librarian=Depends(librarian_admin), db=Depends(get_db)):
    email = body.email.strip().lower()
    if email.count("@") != 1 or any(c.isspace() for c in email) or not all(email.split("@")):
        raise HTTPException(422, "Enter a valid email address")
    profile = await db.scalar(select(StudentProfile).where(StudentProfile.student_number == number))
    if not profile:
        raise HTTPException(404, "Library user not found")
    user = await db.get(User, profile.user_id)
    owner = await db.scalar(select(User.id).where(User.email == email))
    if owner is not None:
        raise HTTPException(409, "This email is already a primary account email")
    approval = await db.scalar(select(ApprovedGoogleEmail).where(ApprovedGoogleEmail.email == email).with_for_update())
    if approval and approval.user_id != user.id:
        raise HTTPException(409, "Alternate email is approved for another user")
    before = {"email": email, "is_active": approval.is_active if approval else False}
    if not approval:
        approval = ApprovedGoogleEmail(user_id=user.id, email=email, approved_by=librarian.id,
                                       approved_at=datetime.now(timezone.utc))
        db.add(approval)
    approval.is_active = body.is_active
    db.add(LibrarySettingsAudit(action="Alternate Google email approval updated", actor=librarian.name,
        actor_id=librarian.id, actor_email=librarian.email, changed_fields=["alternate_google_email"],
        before_values=before, after_values={"number": number, "email": email, "is_active": body.is_active},
        created_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"number": number, "email": email, "is_active": approval.is_active}
