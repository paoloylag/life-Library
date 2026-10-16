import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.database import Base
from app.models import User, StudentProfile, Librarian
from app.alternate_emails import ApprovedGoogleEmail, resolve_alternate_google_user
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_approved_personal_identity_preserves_school_profile():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        admin = Librarian(name='Admin', email='admin@life.edu.ph', password_hash='test', role='librarian')
        user = User(name='Justin Willis Cu Garcia', email='justin.garcia@life.edu.ph', google_id='school-sub', role='student')
        db.add_all([admin,user])
        await db.flush()
        profile = StudentProfile(user_id=user.id, student_number='250101000011', user_type='student', program='BS-ENTREP', section='2A')
        approval = ApprovedGoogleEmail(user_id=user.id,email='justinjustin31@gmail.com',approved_by=admin.id,approved_at=datetime.now(timezone.utc))
        db.add_all([profile,approval])
        await db.commit()
        info = {'email':'justinjustin31@gmail.com','sub':'personal-sub','email_verified':True}
        resolved = await resolve_alternate_google_user(db,info)
        assert resolved.id == user.id
        assert user.email == 'justin.garcia@life.edu.ph'
        assert user.google_id == 'school-sub'
        assert profile.student_number == '250101000011'
        assert approval.google_id == 'personal-sub'
        for bad in [dict(info,email='unknown@gmail.com'),dict(info,email_verified=False),dict(info,sub='different-sub')]:
            with pytest.raises(HTTPException):
                await resolve_alternate_google_user(db,bad)
        approval.is_active = False
        await db.flush()
        with pytest.raises(HTTPException):
            await resolve_alternate_google_user(db,info)
    await engine.dispose()
