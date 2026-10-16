"""Executed inside an ECS task by the production approval workflow."""
import asyncio
import json
import os
from datetime import datetime, timezone
from sqlalchemy import select
from app.database import SessionLocal
from app.models import User, StudentProfile, Librarian, LibrarySettingsAudit
from app.alternate_emails import ApprovedGoogleEmail


async def main():
    data = json.loads(os.environ["APPROVAL_REQUEST"])
    email = data["email"].strip().lower()
    if email.count("@") != 1 or any(c.isspace() for c in email) or not all(email.split("@")):
        raise ValueError("Invalid email")
    async with SessionLocal() as db:
        user, profile = (await db.execute(select(User, StudentProfile).join(
            StudentProfile, StudentProfile.user_id == User.id
        ).where(StudentProfile.student_number == data["number"]).with_for_update())).one()
        if " ".join(user.name.casefold().split()) != " ".join(data["expected_name"].casefold().split()):
            raise ValueError("Profile name does not match the confirmed student number")
        if not user.is_active or not profile.is_active:
            raise ValueError("Profile is inactive")
        if await db.scalar(select(User.id).where(User.email == email)) is not None:
            raise ValueError("Email is already a primary account")
        approval = await db.scalar(select(ApprovedGoogleEmail).where(ApprovedGoogleEmail.email == email).with_for_update())
        if approval and approval.user_id != user.id:
            raise ValueError("Email is approved for another profile")
        actor = await db.scalar(select(Librarian).where(Librarian.email == data["actor_email"], Librarian.is_active.is_(True)))
        before = {"email": email, "is_active": approval.is_active if approval else False}
        if not approval:
            approval = ApprovedGoogleEmail(user_id=user.id, email=email, approved_by=actor.id if actor else None, approved_at=datetime.now(timezone.utc))
            db.add(approval)
        approval.is_active = True
        db.add(LibrarySettingsAudit(action="Operator approved alternate Google email", actor=data["operator"],
            actor_id=actor.id if actor else None, actor_email=data["actor_email"],
            changed_fields=["alternate_google_email"], before_values=before,
            after_values={"number": profile.student_number, "email": email, "is_active": True},
            created_at=datetime.now(timezone.utc)))
        await db.commit()
        assert approval.user_id == user.id and approval.is_active
        print("Alternate email approval committed and verified")


asyncio.run(main())
