import asyncio
from datetime import timedelta, timezone

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import LibrarySession, LibraryVisit, StudentProfile, User
from app.services import attendance_day, daily_token, token_hash, utc_bounds

USERS = [
    (
        "LC-2026-00124",
        "Angela Reyes",
        "student",
        "BS-ENTREP",
        "1st Year",
        "1A",
        "",
    ),
    (
        "LC-2025-00817",
        "Marcus Lim",
        "student",
        "BS-ENTREP-FE",
        "2nd Year",
        "1B",
        "",
    ),
    (
        "LC-2024-00309",
        "Sofia Navarro",
        "student",
        "BS-ENTREP-TE",
        "3rd Year",
        "2A",
        "",
    ),
    (
        "LC-2023-00542",
        "Daniel Cruz",
        "student",
        "BS-ENTREP",
        "4th Year",
        "2B",
        "",
    ),
    (
        "LC-2025-00288",
        "Mika Santos",
        "student",
        "BS-ENTREP-SE",
        "2nd Year",
        "1B",
        "",
    ),
    (
        "LC-2024-00911",
        "Paolo Garcia",
        "student",
        "BS-ENTREP-FE",
        "3rd Year",
        "2A",
        "",
    ),
    (
        "LC-2026-00417",
        "Nina Flores",
        "student",
        "BS-ENTREP-TE",
        "1st Year",
        "1A",
        "",
    ),
    (
        "LC-2023-00726",
        "Ethan Ramos",
        "student",
        "BS-ENTREP",
        "4th Year",
        "2B",
        "",
    ),
    ("FAC-0018", "Dr. Carla Mendoza", "faculty", "", "", "", "Academic Affairs"),
    ("FAC-0031", "Prof. Luis Bautista", "faculty", "", "", "", "Academic Affairs"),
    ("FAC-0044", "Prof. Aira Villanueva", "faculty", "", "", "", "Student Services"),
    (
        "NTP-0012",
        "Grace Dela Rosa",
        "non-teaching personnel",
        "",
        "",
        "",
        "Library Services",
    ),
    (
        "NTP-0025",
        "Noel Castillo",
        "non-teaching personnel",
        "",
        "",
        "",
        "Administration",
    ),
    ("NTP-0038", "Rina Torres", "non-teaching personnel", "", "", "", "Finance"),
    ("VIS-2026-0184", "Juan Dela Cruz", "visitor", "", "", "", "External Visitor"),
    ("VIS-2026-0217", "Maria Salazar", "visitor", "", "", "", "External Visitor"),
]


async def seed() -> None:
    async with SessionLocal() as db:
        profiles = []
        for number, name, user_type, program, year_level, section, department in USERS:
            profile = await db.scalar(
                select(StudentProfile).where(StudentProfile.student_number == number)
            )
            if not profile:
                user = User(
                    email=f"{number.lower()}@seed.life.edu.ph",
                    name=name,
                    role=user_type,
                    is_active=True,
                )
                db.add(user)
                await db.flush()
                profile = StudentProfile(
                    user_id=user.id,
                    student_number=number,
                    user_type=user_type,
                    program=program or None,
                    year_level=year_level or None,
                    section=section or None,
                    department=department or None,
                    is_active=True,
                )
                db.add(profile)
                await db.flush()
            profiles.append(profile)
        await db.commit()

        seeded_visits = await db.scalar(
            select(func.count(LibraryVisit.id)).where(LibraryVisit.source == "seed")
        )
        if seeded_visits:
            return

        today = attendance_day()
        sessions = {}
        for offset in range(30):
            day = today - timedelta(days=offset)
            starts_at, expires_at = utc_bounds(day)
            session = await db.scalar(
                select(LibrarySession).where(LibrarySession.session_date == day)
            )
            if not session:
                session = LibrarySession(
                    session_date=day,
                    name="Development seed",
                    token_hash=token_hash(daily_token(day)),
                    starts_at=starts_at,
                    expires_at=expires_at,
                    status="open" if offset == 0 else "expired",
                )
                db.add(session)
                await db.flush()
            sessions[day] = session

        for index in range(84):
            profile = profiles[index % len(profiles)]
            day = today - timedelta(days=index % 30)
            starts_at, _ = utc_bounds(day)
            checked_in_at = starts_at + timedelta(
                hours=8 + index % 9, minutes=(index * 7) % 60
            )
            db.add(
                LibraryVisit(
                    student_profile_id=profile.id,
                    library_session_id=sessions[day].id,
                    time_in=checked_in_at.astimezone(timezone.utc),
                    status="checked_in",
                    source="seed",
                )
            )
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
