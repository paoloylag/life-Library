from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Librarian(Base):
    __tablename__ = "librarians"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String(30), default="librarian_associate")
    is_development: Mapped[bool] = mapped_column(Boolean, default=False)


class StaffGoogleAccess(Base):
    __tablename__ = "staff_google_access"
    librarian_id: Mapped[int] = mapped_column(ForeignKey("librarians.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    google_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(30), default="student")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    profile: Mapped["StudentProfile|None"] = relationship(
        back_populates="user", uselist=False
    )


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    student_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_type: Mapped[str] = mapped_column(String(50), default="student")
    program: Mapped[str | None] = mapped_column(String(120))
    year_level: Mapped[str | None] = mapped_column(String(50))
    section: Mapped[str | None] = mapped_column(String(120))
    department: Mapped[str | None] = mapped_column(String(120))
    preferred_name: Mapped[str | None] = mapped_column(String(120))
    middle_name: Mapped[str | None] = mapped_column(String(120))
    contact_number: Mapped[str | None] = mapped_column(String(80))
    organization: Mapped[str | None] = mapped_column(String(180))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    user: Mapped[User] = relationship(back_populates="profile")


class LibrarySession(Base):
    __tablename__ = "library_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_date: Mapped[date] = mapped_column(Date, index=True)
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("librarians.id"), nullable=True
    )


class LibraryVisit(Base):
    __tablename__ = "library_visits"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id"), index=True
    )
    library_session_id: Mapped[int] = mapped_column(
        ForeignKey("library_sessions.id"), index=True
    )
    time_in: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="checked_in", index=True)
    source: Mapped[str] = mapped_column(String(20), default="qr")
    adjusted_by: Mapped[int | None] = mapped_column(ForeignKey("librarians.id"))
    adjustment_note: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(String(180))
    student: Mapped[StudentProfile] = relationship()
    session: Mapped[LibrarySession] = relationship()
    adjuster: Mapped[Librarian | None] = relationship()


class LibraryConfiguration(Base):
    __tablename__ = "library_configuration"
    id: Mapped[int] = mapped_column(primary_key=True)
    values: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LibrarySettingsAudit(Base):
    __tablename__ = "library_settings_audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(120))
    actor: Mapped[str] = mapped_column(String(255))
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("librarians.id", ondelete="SET NULL"), nullable=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changed_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)
    before_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BookingResourceType(Base):
    __tablename__ = "booking_resource_types"
    kind: Mapped[str] = mapped_column(String(30), primary_key=True)
    label: Mapped[str] = mapped_column(String(120), unique=True)


class BookingResource(Base):
    __tablename__ = "booking_resources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    kind: Mapped[str] = mapped_column(String(30))
    duration_minutes: Mapped[int] = mapped_column()
    max_minutes: Mapped[int] = mapped_column()
    capacity: Mapped[int] = mapped_column(default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FacilityBooking(Base):
    __tablename__ = "facility_bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("booking_resources.id"), index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    participants: Mapped[list] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(20))
    actions: Mapped[list] = mapped_column(JSON)


class GoogleCalendarConnection(Base):
    __tablename__ = "google_calendar_connections"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    refresh_token_encrypted: Mapped[str] = mapped_column(Text)
    needs_reconnect: Mapped[bool] = mapped_column(Boolean, default=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BookingCalendarSync(Base):
    __tablename__ = "booking_calendar_sync"
    booking_id: Mapped[int] = mapped_column(ForeignKey("facility_bookings.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_id: Mapped[str] = mapped_column(String(64))
    event_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)


class BookingEmail(Base):
    __tablename__ = "booking_emails"
    id: Mapped[int] = mapped_column(primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("facility_bookings.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    recipient: Mapped[str] = mapped_column(String(255), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(30), index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
