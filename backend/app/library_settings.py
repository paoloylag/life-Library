import re
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select

from app.models import Librarian, LibraryConfiguration, LibrarySettingsAudit


class LibrarySettings(BaseModel):
    libraryName: str = Field(default="Life College Library", min_length=1, max_length=120)
    timezone: Literal["Asia/Manila", "UTC"] = "Asia/Manila"
    opensAt: str = "07:00"
    closesAt: str = "18:00"
    qrExpiryMinutes: int = Field(default=1440, ge=1, le=1440)
    duplicateWindowMinutes: int = Field(default=5, ge=1, le=60)
    academicYear: str = Field(default="2026-2027", max_length=9)
    semester: Literal["1st Semester", "2nd Semester", "Summer"] = "1st Semester"
    programs: list[str] = Field(
        default_factory=lambda: [
            "BS-ENTREP",
            "BS-ENTREP-FE",
            "BS-ENTREP-TE",
            "BS-ENTREP-SE",
            "BS-ENTREP-AE",
            "BS-ENTREP-CE",
        ]
    )
    sections: list[str] = Field(default_factory=lambda: ["1A", "1B", "2A", "2B"])
    yearLevels: list[str] = Field(default_factory=lambda: ["1st Year", "2nd Year", "3rd Year", "4th Year"])
    departments: list[str] = Field(
        default_factory=lambda: ["Academic Affairs", "Administration", "Student Services", "Library Services", "Finance"]
    )
    librarians: list[str] = Field(default_factory=lambda: ["Library Registrar"])
    visitorFields: list[str] = Field(default_factory=lambda: ["Full name", "Organization", "Purpose of visit", "Contact number"])
    defaultReportPeriod: Literal["Daily", "Weekly", "Monthly", "Annual"] = "Monthly"
    defaultReportUserType: Literal["All", "student", "faculty", "non-teaching personnel", "administrator", "visitor"] = "All"
    retentionYears: int = Field(default=5, ge=1, le=10)
    qrHeading: str = Field(default="Scan to record your visit", min_length=1, max_length=70)
    qrInstructions: str = Field(default="Use your school Google account to verify your identity and record your library check-in.", max_length=220)
    roomBookingUrl: str = Field(default="", max_length=2048)

    @field_validator("roomBookingUrl")
    @classmethod
    def valid_room_booking_url(cls, value: str) -> str:
        value = value.strip()
        if value and (urlsplit(value).scheme != "https" or not urlsplit(value).hostname):
            raise ValueError("Room booking link must be an HTTPS URL")
        return value

    @field_validator("opensAt", "closesAt")
    @classmethod
    def valid_time(cls, value: str) -> str:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("Time must use HH:MM")
        return value

    @field_validator("academicYear")
    @classmethod
    def valid_year(cls, value: str) -> str:
        try:
            start, end = map(int, value.split("-"))
            if end != start + 1 or not 1900 <= start <= 2200:
                raise ValueError
        except ValueError as exc:
            raise ValueError("Academic year must use YYYY-YYYY") from exc
        return value

    @field_validator("programs", "sections", "yearLevels", "departments", "librarians", "visitorFields")
    @classmethod
    def valid_list(cls, values: list[str]) -> list[str]:
        if len(values) > 100 or any(not value.strip() or len(value) > 120 for value in values):
            raise ValueError("Lists allow up to 100 nonempty entries of 120 characters each")
        return [value.strip() for value in values]

    @model_validator(mode="after")
    def valid_hours(self):
        if self.opensAt >= self.closesAt:
            raise ValueError("Opening time must be before closing time")
        return self


async def read_library_settings(db) -> LibrarySettings:
    row = await db.get(LibraryConfiguration, 1)
    return LibrarySettings.model_validate(row.values) if row else LibrarySettings()


_SENSITIVE_SETTING_PARTS = ("secret", "password", "token", "credential", "private_key")


def _audit_snapshot(values: dict) -> dict:
    return {
        key: "[REDACTED]" if any(part in key.lower() for part in _SENSITIVE_SETTING_PARTS) else value
        for key, value in values.items()
    }


async def save_library_settings(db, payload: LibrarySettings, actor: Librarian) -> dict:
    row = await db.get(LibraryConfiguration, 1)
    now = datetime.now(timezone.utc)
    before = dict(row.values) if row else {}
    after = payload.model_dump()
    changed_fields = sorted(
        key for key in before.keys() | after.keys() if before.get(key) != after.get(key)
    )
    if row and not changed_fields:
        return after
    if row:
        row.values = after
        row.updated_at = now
    else:
        db.add(LibraryConfiguration(id=1, values=after, updated_at=now))
    db.add(LibrarySettingsAudit(
        action="Settings updated" if before else "Settings created",
        actor=actor.name,
        actor_id=actor.id,
        actor_email=actor.email,
        changed_fields=changed_fields,
        before_values=_audit_snapshot(before),
        after_values=_audit_snapshot(after),
        created_at=now,
    ))
    await db.commit()
    return after


async def settings_audit(db) -> list[dict]:
    rows = (await db.scalars(
        select(LibrarySettingsAudit).order_by(LibrarySettingsAudit.created_at.desc(), LibrarySettingsAudit.id.desc()).limit(20)
    )).all()
    return [{
        "id": str(row.id),
        "action": row.action,
        "user": row.actor,
        "actorId": row.actor_id,
        "actorEmail": row.actor_email,
        "changedFields": row.changed_fields or [],
        "beforeValues": row.before_values,
        "afterValues": row.after_values,
        "at": row.created_at.isoformat(),
    } for row in rows]
