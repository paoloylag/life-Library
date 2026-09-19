import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.import_roster import import_rows, read_roster, roster_text
from app.models import StudentProfile, User


def test_roster_validation(tmp_path):
    source = tmp_path / "roster.csv"
    source.write_text(
        "number,name,email,user_type,is_active\n"
        "LC-1,Student One,one@life.edu.ph,student,true\n",
        encoding="utf-8",
    )
    rows = read_roster(source)
    assert rows[0]["is_active"] is True
    source.write_text(
        "number,name,email,user_type\n"
        "LC-1,Student One,one@life.edu.ph,student\n"
        "LC-1,Student Two,two@life.edu.ph,student\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate number"):
        read_roster(source)


def test_private_s3_roster_input(monkeypatch):
    class Body:
        def read(self):
            return (
                b"number,name,email,user_type\nLC-1,Student,one@life.edu.ph,student\n"
            )

    class S3:
        def get_object(self, **kwargs):
            assert kwargs == {"Bucket": "private-bucket", "Key": "rosters/users.csv"}
            return {"Body": Body()}

    monkeypatch.setattr("app.import_roster.boto3.client", lambda service: S3())
    assert "LC-1" in roster_text("s3://private-bucket/rosters/users.csv")


@pytest.mark.asyncio
async def test_roster_dry_run_upsert_and_google_identity(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.import_roster.SessionLocal", factory)
    rows = [
        {
            "number": "LC-1",
            "name": "Student One",
            "email": "one@life.edu.ph",
            "user_type": "student",
            "program": "BSIT",
            "year_level": "1st Year",
            "section": "A",
            "department": "",
            "organization": "",
            "is_active": True,
        }
    ]
    result = await import_rows(rows, dry_run=True)
    assert result.created == 1
    async with factory() as db:
        assert await db.scalar(select(func.count(User.id))) == 0
    await import_rows(rows)
    rows[0].update(name="Student Updated", program="BSCS")
    result = await import_rows(rows)
    assert result.updated == 1
    async with factory() as db:
        user = await db.scalar(select(User).where(User.email == "one@life.edu.ph"))
        profile = await db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == user.id)
        )
        assert user.name == "Student Updated" and profile.program == "BSCS"
        user.google_id = "google-1"
        profile.user_type = "faculty"
        await db.commit()
    rows[0]["user_type"] = "student"
    await import_rows(rows)
    async with factory() as db:
        profile = await db.scalar(
            select(StudentProfile).where(StudentProfile.student_number == "LC-1")
        )
        assert profile.user_type == "faculty"
    await engine.dispose()
