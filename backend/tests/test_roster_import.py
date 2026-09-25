import pytest
from app.database import Base
from app.import_roster import (
    import_rows,
    read_roster,
    read_roster_text,
    read_staff_text,
    roster_text,
)
from app.models import StudentProfile, User
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


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


def test_roster_text_parsing():
    rows = read_roster_text(
        "number,name,email,user_type,program,section\n"
        "LC-2,Student Two,two@life.edu.ph,student,BSIT,B\n"
    )
    assert rows[0]["program"] == "BSIT"
    assert rows[0]["section"] == "B"


def test_staff_masterlist_aliases_and_category():
    rows, ignored = read_staff_text(
        "Employee ID,Lsst Name,First Name,Preferred Name,Employment Status,"
        "Office,User Type,Status,Position,Extra\n"
        "EMP-01,Reyes,Alex,Lex,Regular,Library,Faculty,Active,Librarian,test\n",
    )
    assert rows[0]["number"] == "EMP-01"
    assert rows[0]["name"] == "Alex Reyes"
    assert rows[0]["email"] == "staff-emp-01@staff.local"
    assert rows[0]["department"] == "Library"
    assert rows[0]["user_type"] == "faculty"
    assert rows[0]["preferred_name"] == "Lex"
    assert rows[0]["employment_status"] == "Regular"
    assert rows[0]["position"] == "Librarian"
    assert ignored == ["Extra"]


def test_staff_masterlist_rejects_bad_rows():
    with pytest.raises(ValueError, match="duplicate number"):
        read_staff_text(
            "Employee ID,Full Name,Email,User Type\n"
            "EMP-01,Alex Reyes,alex@life.edu.ph,faculty\n"
            "EMP-01,Jamie Cruz,jamie@life.edu.ph,faculty\n",
        )
    with pytest.raises(ValueError, match="full name or first and last name"):
        read_staff_text("Employee ID,First Name,User Type\nEMP-01,Alex,faculty\n")
    with pytest.raises(ValueError, match="Missing required User Type column"):
        read_staff_text("Employee ID,Full Name\nEMP-01,Alex Reyes\n")
    with pytest.raises(ValueError, match="Row 2: User Type must be"):
        read_staff_text("Employee ID,Full Name,User Type\nEMP-01,Alex Reyes,\n")


def test_staff_masterlist_generates_missing_id_and_uses_explicit_type():
    rows, ignored = read_staff_text(
        "Employee ID,Lsst Name,First Name,Position,User Type\n"
        "NA,Cruz,Jamie,Adjunct Faculty,faculty\n",
    )
    assert rows[0]["number"].startswith("STAFF-")
    assert rows[0]["user_type"] == "faculty"
    assert ignored == []


def test_staff_masterlist_accepts_non_teaching_label():
    rows, _ = read_staff_text(
        "Employee ID,Last Name,First Name,User Type\n"
        "EMP-02,Cruz,Jamie,Non-Teaching\n",
    )
    assert rows[0]["user_type"] == "non-teaching personnel"


def test_exported_staff_with_blank_id_can_be_reimported():
    rows = read_roster_text(
        "number,name,email,user_type,department\n"
        ",Jamie Cruz,,faculty,Academics\n"
    )
    assert rows[0]["number"].startswith("STAFF-")


@pytest.mark.asyncio
async def test_staff_reimport_without_email_preserves_known_email(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.import_roster.SessionLocal", factory)
    header = "Employee ID,Full Name,Email,Department,User Type\n"
    first, _ = read_staff_text(
        header + "EMP-1,Alex Reyes,alex@life.edu.ph,Library,non-teaching personnel\n",
    )
    later, _ = read_staff_text(
        header + "EMP-1,Alex Reyes,,Library,non-teaching personnel\n",
    )
    await import_rows(first)
    await import_rows(later)
    async with factory() as db:
        user = await db.scalar(select(User).where(User.name == "Alex Reyes"))
        assert user.email == "alex@life.edu.ph"
    await engine.dispose()


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


@pytest.mark.asyncio
async def test_roster_reconciles_sso_profile_by_email(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.import_roster.SessionLocal", factory)
    async with factory() as db:
        user = User(
            email="student@life.edu.ph",
            name="SSO Student",
            google_id="google-student",
            role="student",
            is_active=True,
        )
        db.add(user)
        await db.flush()
        db.add(
            StudentProfile(
                user_id=user.id,
                student_number="STUDENT",
                user_type="student",
                is_active=True,
            )
        )
        await db.commit()

    rows = [
        {
            "number": "LC-2026-01234",
            "name": "Student Official Name",
            "email": "student@life.edu.ph",
            "user_type": "student",
            "program": "BSIT",
            "year_level": "1st Year",
            "section": "A",
            "department": "",
            "organization": "",
            "is_active": True,
        }
    ]
    result = await import_rows(rows)
    assert result.created == 0
    assert result.updated == 1
    async with factory() as db:
        profiles = (await db.scalars(select(StudentProfile))).all()
        assert len(profiles) == 1
        assert profiles[0].student_number == "LC-2026-01234"
        assert profiles[0].program == "BSIT"
        assert profiles[0].section == "A"
        user = await db.get(User, profiles[0].user_id)
        assert user.google_id == "google-student"
    await engine.dispose()
