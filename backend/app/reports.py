from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import LibraryVisit, StudentProfile
from app.services import aware_utc, utc_bounds

MANILA = ZoneInfo("Asia/Manila")
CATEGORIES = (
    "Student", "Faculty / Teaching Personnel", "Non-Teaching Personnel",
    "Administrator", "Visitor",
)
USER_TYPES = {
    "student": CATEGORIES[0], "faculty": CATEGORIES[1],
    "non-teaching personnel": CATEGORIES[2], "administrator": CATEGORIES[3],
    "visitor": CATEGORIES[4],
}
GROUPINGS = ("Daily", "Weekly", "Monthly", "Annual")
SEMESTERS = ("1st Semester", "2nd Semester", "Outside Semester")


@dataclass(frozen=True)
class ReportFilters:
    date_from: date | None = None
    date_to: date | None = None
    academic_year: str = "All"
    semester: str = "All"
    grouping: str = "Monthly"
    user_type: str = "All"
    year_level: str = "All"
    section: str = "All"
    program: str = "All"
    department: str = "All"

    def validate(self) -> None:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise HTTPException(422, "Date from must not be after date to")
        if self.grouping not in GROUPINGS:
            raise HTTPException(422, "Invalid trend grouping")
        if self.semester != "All" and self.semester not in SEMESTERS:
            raise HTTPException(422, "Invalid semester")
        if self.user_type != "All" and self.user_type not in USER_TYPES:
            raise HTTPException(422, "Invalid user type")
        if self.academic_year != "All":
            try:
                start, end = map(int, self.academic_year.split("-"))
                if end != start + 1 or not 1900 <= start <= 2200:
                    raise ValueError
            except ValueError as exc:
                raise HTTPException(422, "Invalid academic year") from exc


def academic_year_start(year: int) -> date:
    first = date(year, 8, 1)
    return first + timedelta(days=max(0, 7 - first.weekday()) if first.weekday() > 4 else 0)


def academic_year(day: date) -> str:
    start = day.year if day >= academic_year_start(day.year) else day.year - 1
    return f"{start}-{start + 1}"


def semester(day: date) -> str:
    if day.month >= 8 and day >= academic_year_start(day.year):
        return SEMESTERS[0]
    if day.month <= 5:
        return SEMESTERS[1]
    return SEMESTERS[2]


def series(counts: Counter) -> list[dict]:
    return [{"label": str(key), "value": count} for key, count in sorted(counts.items())]


def top(items: list[dict], limit: int = 8) -> list[dict]:
    return sorted(items, key=lambda item: (-item["value"], item["label"]))[:limit]


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def report_open_day(day: date, user_type: str) -> bool:
    return day.weekday() in ((1, 2, 3, 4) if user_type == "student" else (0, 1, 2, 3, 4))


async def build_report(db, filters: ReportFilters) -> dict:
    filters.validate()
    query = select(LibraryVisit).options(
        selectinload(LibraryVisit.student).selectinload(StudentProfile.user)
    ).order_by(LibraryVisit.time_in, LibraryVisit.id)
    if filters.date_from:
        query = query.where(LibraryVisit.time_in >= utc_bounds(filters.date_from)[0])
    if filters.date_to:
        query = query.where(LibraryVisit.time_in <= utc_bounds(filters.date_to)[1])
    visits = (await db.scalars(query)).all()
    all_times = (await db.scalars(select(LibraryVisit.time_in))).all()
    profiles = (await db.scalars(select(StudentProfile))).all()
    options = {
        "academic_years": sorted({academic_year(aware_utc(v).astimezone(MANILA).date()) for v in all_times}, reverse=True),
        "semesters": list(SEMESTERS), "user_types": list(USER_TYPES),
        "year_levels": sorted({p.year_level for p in profiles if p.year_level}),
        "sections": sorted({p.section for p in profiles if p.section}),
        "programs": sorted({p.program for p in profiles if p.program}),
        "departments": sorted({p.department for p in profiles if p.department}),
    }
    rows = []
    for visit in visits:
        profile = visit.student
        local_time = aware_utc(visit.time_in).astimezone(MANILA)
        day = local_time.date()
        if filters.academic_year != "All" and academic_year(day) != filters.academic_year:
            continue
        if filters.semester != "All" and semester(day) != filters.semester:
            continue
        if filters.user_type != "All" and profile.user_type != filters.user_type:
            continue
        if filters.year_level != "All" and profile.year_level != filters.year_level:
            continue
        if filters.section != "All" and profile.section != filters.section:
            continue
        if filters.program != "All" and profile.program != filters.program:
            continue
        if filters.department != "All" and profile.department != filters.department:
            continue
        rows.append({
            "id": visit.id, "date": day.isoformat(),
            "academic_year": academic_year(day), "semester": semester(day),
            "check_in_time": local_time.isoformat(), "name": profile.user.name,
            "user_number": profile.student_number, "user_type": profile.user_type,
            "category": USER_TYPES.get(profile.user_type, CATEGORIES[2]),
            "program": profile.program or "", "year_level": profile.year_level or "",
            "section": profile.section or "", "department": profile.department or "",
            "organization": profile.organization or "", "source": visit.source,
            "note": visit.adjustment_note or "", "purpose": visit.purpose or "",
            "profile_id": profile.id,
        })
    daily = Counter(row["date"] for row in rows)
    weekly = Counter(week_start(date.fromisoformat(row["date"])).isoformat() for row in rows)
    monthly = Counter(row["date"][:7] for row in rows)
    annual = Counter(row["date"][:4] for row in rows)
    semesters = Counter(f'{row["academic_year"]} / {row["semester"]}' for row in rows)
    hours = Counter(datetime.fromisoformat(row["check_in_time"]).strftime("%H:00") for row in rows)
    weekdays = Counter(date.fromisoformat(row["date"]).strftime("%A") for row in rows)
    categories = Counter(row["category"] for row in rows)
    students = [row for row in rows if row["user_type"] == "student"]
    programs = Counter(row["program"] or "Not specified" for row in students)
    years = Counter(row["year_level"] or "Not specified" for row in students)
    sections = Counter(row["section"] or "Not specified" for row in students)
    year_sections = Counter(" / ".join(filter(None, (row["year_level"], row["section"]))) or "Not specified" for row in students)
    per_user = Counter(row["profile_id"] for row in rows)
    first = filters.date_from or (date.fromisoformat(rows[0]["date"]) if rows else None)
    last = filters.date_to or (date.fromisoformat(rows[-1]["date"]) if rows else None)
    days = [first + timedelta(days=offset) for offset in range((last - first).days + 1)] if first and last and first <= last else []
    open_days = sum(
        report_open_day(day, filters.user_type)
        and (filters.academic_year == "All" or academic_year(day) == filters.academic_year)
        and (filters.semester == "All" or semester(day) == filters.semester)
        for day in days
    )
    week_periods = {week_start(day) for day in days}
    month_periods = {(day.year, day.month) for day in days}
    total, unique = len(rows), len(per_user)
    summary = {
        "total_visits": total, "unique_users": unique,
        "return_visits": total - unique,
        "returning_users": sum(count > 1 for count in per_user.values()),
        "open_days": open_days,
        "average_per_open_day": round(total / open_days, 2) if open_days else 0,
        "average_per_week": round(total / len(week_periods), 2) if week_periods else 0,
        "average_per_month": round(total / len(month_periods), 2) if month_periods else 0,
        "average_per_user": round(total / unique, 2) if unique else 0,
        "peak_day": top(series(daily), 1)[0] if daily else None,
        "peak_hour": top(series(hours), 1)[0] if hours else None,
    }
    trend = {"Daily": daily, "Weekly": weekly, "Monthly": monthly, "Annual": annual}
    breakdowns = {
        "trend": series(trend[filters.grouping]), "daily": series(daily),
        "weekly": series(weekly), "monthly": series(monthly),
        "hours": series(hours), "weekdays": series(weekdays),
        "semesters": series(semesters),
        "categories": [{"label": category, "value": categories[category]} for category in CATEGORIES],
        "programs": top(series(programs), 100), "year_levels": top(series(years), 100),
        "sections": top(series(sections), 100), "year_sections": top(series(year_sections), 100),
    }
    return {
        "generated_at": datetime.now(timezone.utc).astimezone(MANILA).isoformat(),
        "filters": {key: value.isoformat() if isinstance(value, date) else value for key, value in vars(filters).items()},
        "period_start": first.isoformat() if first else None,
        "period_end": last.isoformat() if last else None,
        "academic_years": sorted({row["academic_year"] for row in rows}),
        "semesters": sorted({row["semester"] for row in rows}),
        "calendar_note": "Students: Tuesday-Friday, 9:00-18:00. Staff: Monday-Friday, 7:00-17:00. Holiday closures are not yet excluded.",
        "profile_note": "Historical breakdowns use each user's current profile.",
        "summary": summary, "breakdowns": breakdowns, "options": options,
        "records": [{key: value for key, value in row.items() if key != "profile_id"} for row in rows],
    }
