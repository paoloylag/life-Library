"""Resource reservations, using the same rules for patrons and staff."""

import asyncio
from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from app.auth import (
    current_librarian,
    current_user,
    librarian_admin,
    librarian_dashboard,
    librarian_editor,
    student_sessions,
)
from itsdangerous import BadSignature, SignatureExpired
from app.database import get_db
from app.models import BookingResource, BookingResourceType, FacilityBooking, StudentProfile, User
from uuid import uuid4
from zoneinfo import ZoneInfo
from app.library_settings import read_library_settings
from app.booking_guidelines import GUIDELINES, guideline

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])
# PostgreSQL resource row locks serialize across workers; this also covers local SQLite.
write_lock = asyncio.Lock()
CATEGORIES = {
    "student",
    "faculty",
    "non-teaching personnel",
    "administrator",
    "visitor",
}


def now():
    return datetime.now(UTC)


def aware(value):
    return (
        value.replace(tzinfo=UTC)
        if value.tzinfo is None
        else value.astimezone(UTC)
    )


MANILA = ZoneInfo("Asia/Manila")


async def booking_hours(db):
    settings = await read_library_settings(db)
    return settings.bookingOpensAt, settings.bookingClosesAt


def within_booking_hours(start, end, hours):
    local = aware(start).astimezone(MANILA)
    opening_hour, opening_minute = map(int, hours[0].split(':'))
    closing_hour, closing_minute = map(int, hours[1].split(':'))
    opening = local.replace(hour=opening_hour, minute=opening_minute, second=0, microsecond=0)
    closing = local.replace(hour=closing_hour, minute=closing_minute, second=0, microsecond=0)
    return start >= opening and end <= closing


def require_booking_hours(start, end, hours):
    if not within_booking_hours(start, end, hours):
        raise HTTPException(422, f"Bookings and extensions must fit between {hours[0]} and {hours[1]} (Manila time)")


def open_intervals(intervals, hours):
    result = []
    opening_hour, opening_minute = map(int, hours[0].split(':'))
    closing_hour, closing_minute = map(int, hours[1].split(':'))
    for interval in intervals:
        start, end = datetime.fromisoformat(interval['starts_at']), datetime.fromisoformat(interval['ends_at'])
        day = start.astimezone(MANILA).replace(hour=0, minute=0, second=0, microsecond=0)
        while day < end:
            left = max(start, day.replace(hour=opening_hour, minute=opening_minute))
            right = min(end, day.replace(hour=closing_hour, minute=closing_minute))
            if left < right:
                result.append({'starts_at': left.isoformat(), 'ends_at': right.isoformat()})
            day += timedelta(days=1)
    return result


class Participant(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    category: str
    program: str = Field(default="", max_length=120)
    year_level: str = Field(default="", max_length=50)
    department: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def validate_details(self):
        self.name = self.name.strip()
        self.program, self.year_level, self.department = (
            self.program.strip(),
            self.year_level.strip(),
            self.department.strip(),
        )
        if len(self.name.split()) < 2:
            raise ValueError("Enter the full name")
        if self.category not in CATEGORIES:
            raise ValueError("Invalid user category")
        if self.category == "student" and not (self.program and self.year_level):
            raise ValueError("Students require program and year level")
        if self.category not in {"student", "visitor"} and not self.department:
            raise ValueError("Staff require a department")
        return self


class ResourceInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    kind: str
    duration_minutes: int = Field(ge=1, le=480)
    max_minutes: int = Field(ge=1, le=480)
    capacity: int = Field(ge=1, le=100)
    is_active: bool = True

    @model_validator(mode="after")
    def policy(self):
        self.name = self.name.strip()
        if self.duration_minutes > self.max_minutes:
            raise ValueError("Duration exceeds session limit")
        if self.kind == "computer" and self.max_minutes > 120:
            raise ValueError("Computer usage cannot exceed two hours")
        if self.kind == "nap_pod" and self.duration_minutes != 45:
            raise ValueError("Nap Pod sessions last 45 minutes")
        if self.kind in {"nap_pod", "computer"} and self.capacity != 1:
            raise ValueError("Individual resources have capacity one")
        if self.kind == 'collaboration_room' and self.capacity < 3:
            raise ValueError("Collaboration Rooms must accommodate at least three users")
        return self


class BookingInput(BaseModel):
    resource_id: int
    additional_member_numbers: list[str] = Field(default_factory=list, max_length=99)
    additional_member_names: list[str] = Field(default_factory=list, max_length=99)
    guidelines_accepted: bool = False
    guidelines_version: str | None = Field(default=None, max_length=64)
    starts_at: datetime | None = None
    participants: list[Participant] = Field(default_factory=list, max_length=100)
    use_profile: bool = False
    organizer_number: str | None = Field(default=None, max_length=50)
    participant_numbers: list[str] = Field(default_factory=list, max_length=99)


class ExtensionInput(BaseModel):
    minutes: int = Field(ge=1, le=480)


async def booking_user(request, db):
    user = await current_user(request, db)
    try:
        session = student_sessions.loads(request.cookies.get("library_session", ""), max_age=43200)
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Sign in with your Life College Google account to book")
    if session.get("google_authenticated") is not True:
        raise HTTPException(403, "Google sign-in is required for resource bookings. Please sign in again.")
    profile = user.profile
    category = profile.user_type if profile else user.role
    if category not in CATEGORIES - {"visitor"} or (profile and not profile.is_active):
        raise HTTPException(403, "Resource bookings are available to active Life College students and staff only")
    return user


@router.get("/identity")
async def booking_identity(request: Request, db=Depends(get_db)):
    user = await booking_user(request, db)
    return {"id": user.id, "eligible": True}


@router.get("/guidelines")
async def booking_guidelines(request: Request, db=Depends(get_db)):
    await actor(request, db)
    return {kind: guideline(kind) for kind in GUIDELINES}


@router.get("/guidelines/{kind}")
async def public_booking_guideline(kind: str):
    document = guideline(kind)
    if document is None:
        raise HTTPException(404, "Guidelines not found")
    return document


@router.get('/members')
async def member_search(request: Request, q: str = '', organizer_number: str | None = None, db=Depends(get_db)):
    source, person = await actor(request, db)
    if len(q) > 100:
        raise HTTPException(422, 'Search text is too long')
    if source == 'manual':
        organizer = await db.scalar(select(StudentProfile).where(StudentProfile.student_number == organizer_number, StudentProfile.is_active.is_(True)))
        if not organizer:
            raise HTTPException(422, 'Select the booking organizer first')
        category, organizer_id = organizer.user_type, organizer.user_id
    else:
        category = person.profile.user_type if person.profile else person.role
        organizer_id = person.id
    query = select(StudentProfile, User).join(User, User.id == StudentProfile.user_id).where(
        StudentProfile.is_active.is_(True), User.is_active.is_(True), User.id != organizer_id,
        StudentProfile.user_type != 'visitor',
    )
    if category == 'student':
        query = query.where(StudentProfile.user_type == 'student')
    for word in q.split():
        query = query.where(func.lower(User.name).contains(word.lower(), autoescape=True) | func.lower(StudentProfile.student_number).contains(word.lower(), autoescape=True))
    rows = (await db.execute(query.order_by(User.name, User.id).limit(10))).all()
    items = [dict(number=profile.student_number,name=user.name,user_type=profile.user_type,program='',department='',year_level='',section='') for profile,user in rows]
    return {'items': items, 'total': len(items), 'page': 1, 'page_size': 10}


async def actor(request, db):
    if request.headers.get("X-Booking-Mode") == "user":
        return "user", await booking_user(request, db)
    if request.headers.get("X-Booking-Mode") == "manual":
        return "manual", await librarian_editor(await current_librarian(request, db))
    if request.headers.get("X-Booking-Mode") != "user" and request.cookies.get("librarian_session"):
        return "manual", await librarian_editor(await current_librarian(request, db))
    return "user", await booking_user(request, db)


async def rows(db, resource_id):
    return list(
        (
            await db.scalars(
                select(FacilityBooking).where(
                    FacilityBooking.resource_id == resource_id,
                    FacilityBooking.ended_at.is_(None),
                )
            )
        ).all()
    )


async def ensure_participants_available(db, participants, start, end, owner_id=None, exclude=None):
    names = {" ".join(p['name'].casefold().split()) for p in participants}
    ids = {p['user_id'] for p in participants if p.get('user_id') is not None}
    if owner_id is not None:
        ids.add(owner_id)
    # Lock identities in a consistent order across resources and group bookings.
    if ids:
        await db.execute(select(User.id).where(User.id.in_(ids)).order_by(User.id).with_for_update())
    if db.bind.dialect.name == 'postgresql':
        for name in sorted(names):
            await db.execute(select(func.pg_advisory_xact_lock(func.hashtext('library-booking:' + name))))
    query = select(FacilityBooking).where(
        FacilityBooking.ended_at.is_(None), FacilityBooking.starts_at < end,
        FacilityBooking.ends_at > start,
    )
    if exclude is not None:
        query = query.where(FacilityBooking.id != exclude)
    overlapping = (await db.scalars(query)).all()
    for booking in overlapping:
        if participant_conflict(booking, ids, names):
            raise HTTPException(409, 'A participant already has a booking during this time. End the current session or choose a different time.')


def booking_member_names(booking):
    additional = next((action.get('additional_member_names', []) for action in booking.actions if action.get('action') == 'booked'), [])
    return [p['name'] for p in booking.participants] + additional


def participant_conflict(booking, ids, names):
    return booking.owner_id in ids or any(
        p.get('user_id') in ids
        for p in booking.participants
    ) or any(" ".join(name.casefold().split()) in names for name in booking_member_names(booking))


def conflict(bookings, start, end, exclude=None):
    return any(
        b.id != exclude and aware(b.starts_at) < end and aware(b.ends_at) > start
        for b in bookings
    )


def is_cancelled(booking):
    return any(action.get("action") == "cancelled" for action in booking.actions)


async def serialize(b, resource, bookings, timestamp, db):
    hours = await booking_hours(db)
    start, end = aware(b.starts_at), aware(b.ends_at)
    active = start <= timestamp < end and b.ended_at is None
    extension = min(
        resource.duration_minutes,
        resource.max_minutes - int((end - start).total_seconds() / 60),
    )
    extension_end = end + timedelta(minutes=max(0, extension))
    reason = None
    if not active:
        reason = "Only in-progress sessions can be extended"
    elif not resource.is_active:
        reason = "This resource is inactive"
    elif extension <= 0:
        reason = "Session usage limit reached"
    elif not within_booking_hours(start, extension_end, hours):
        reason = f"The extension would go beyond booking hours ({hours[0]}-{hours[1]}, Manila time)"
    elif conflict(bookings, end, extension_end, b.id):
        reason = "Another user has reserved the next interval"
    else:
        ids = {p['user_id'] for p in b.participants if p.get('user_id') is not None}
        if b.owner_id is not None:
            ids.add(b.owner_id)
        names = {" ".join(name.casefold().split()) for name in booking_member_names(b)}
        overlapping = (await db.scalars(select(FacilityBooking).where(
            FacilityBooking.id != b.id, FacilityBooking.ended_at.is_(None),
            FacilityBooking.starts_at < extension_end, FacilityBooking.ends_at > end,
        ))).all()
        if any(participant_conflict(other, ids, names) for other in overlapping):
            reason = "A user in this session has another booking during the extension"
    can_extend = reason is None
    return {
        "id": b.id,
        "resource_id": b.resource_id,
        "resource_kind": resource.kind,
        "starts_at": start.isoformat(),
        "ends_at": end.isoformat(),
        "participants": b.participants,
        "member_names": booking_member_names(b),
        "source": b.source,
        "actions": b.actions,
        "status": "cancelled"
        if is_cancelled(b)
        else "ended"
        if b.ended_at
        else "scheduled"
        if timestamp < start
        else "active"
        if active
        else "completed",
        "can_extend": can_extend,
        "extension_unavailable_reason": reason,
        "extension_minutes": max(0, extension),
        "next_reserved": any(
            x.id != b.id
            and aware(x.starts_at) >= end
            and aware(x.starts_at) <= end + timedelta(minutes=resource.duration_minutes)
            for x in bookings
        ),
    }


@router.get("/availability")
async def availability(db=Depends(get_db)):
    hours = await booking_hours(db)
    timestamp, horizon = now(), now() + timedelta(days=1)
    resources = list(
        (
            await db.scalars(
                select(BookingResource)
                .where(BookingResource.is_active.is_(True))
                .order_by(BookingResource.id)
            )
        ).all()
    )
    result = []
    for r in resources:
        booked = sorted(
            [
                b
                for b in await rows(db, r.id)
                if aware(b.ends_at) > timestamp and aware(b.starts_at) < horizon
            ],
            key=lambda b: aware(b.starts_at),
        )
        cursor, free = timestamp, []
        for b in booked:
            if aware(b.starts_at) > cursor:
                free.append(
                    {
                        "starts_at": cursor.isoformat(),
                        "ends_at": aware(b.starts_at).isoformat(),
                    }
                )
            cursor = max(cursor, aware(b.ends_at))
        if cursor < horizon:
            free.append(
                {"starts_at": cursor.isoformat(), "ends_at": horizon.isoformat()}
            )
        result.append(
            {
                "id": r.id,
                "name": r.name,
                "kind": r.kind,
                "duration_minutes": r.duration_minutes,
                "max_minutes": r.max_minutes,
                "capacity": r.capacity,
                "available_now": within_booking_hours(timestamp, timestamp + timedelta(minutes=r.duration_minutes), hours) and not conflict(
                    booked, timestamp, timestamp + timedelta(minutes=r.duration_minutes)
                ),
                "free_intervals": open_intervals(free, hours),
            }
        )
    return {
        "server_time": timestamp.isoformat(),
        "horizon": horizon.isoformat(),
        "booking_hours": {"opens_at": hours[0], "closes_at": hours[1], "timezone": "Asia/Manila"},
        "resources": result,
    }


BUILTIN_RESOURCE_TYPES = [
    {"kind": "nap_pod", "label": "Nap Pods"},
    {"kind": "collaboration_room", "label": "Collaboration Rooms"},
    {"kind": "computer", "label": "Computers"},
]


class ResourceTypeInput(BaseModel):
    label: str = Field(min_length=2, max_length=120)


@router.get("/resource-types")
async def resource_types(request: Request, db=Depends(get_db)):
    await actor(request, db)
    custom = (await db.scalars(select(BookingResourceType).order_by(BookingResourceType.label))).all()
    return BUILTIN_RESOURCE_TYPES + [{"kind": row.kind, "label": row.label} for row in custom]


@router.post("/resource-types")
async def add_resource_type(body: ResourceTypeInput, staff=Depends(librarian_admin), db=Depends(get_db)):
    label = " ".join(body.label.split())
    if len(label) < 2:
        raise HTTPException(422, "Enter a resource type name")
    async with write_lock:
        existing = await db.scalar(select(BookingResourceType).where(func.lower(BookingResourceType.label) == label.lower()))
        if existing or label.casefold() in {item["label"].casefold() for item in BUILTIN_RESOURCE_TYPES}:
            raise HTTPException(409, "Resource type already exists")
        row = BookingResourceType(kind="custom_" + uuid4().hex[:23], label=label)
        db.add(row)
        await db.commit()
    return {"kind": row.kind, "label": row.label}


async def validate_resource_type(db, kind):
    if kind not in {item["kind"] for item in BUILTIN_RESOURCE_TYPES} and not await db.get(BookingResourceType, kind):
        raise HTTPException(422, "Select an existing resource type")


@router.post("/resources")
async def add_resource(
    body: ResourceInput, staff=Depends(librarian_admin), db=Depends(get_db)
):
    await validate_resource_type(db, body.kind)
    if await db.scalar(
        select(BookingResource).where(BookingResource.name == body.name)
    ):
        raise HTTPException(409, "Resource name already exists")
    r = BookingResource(**body.model_dump())
    db.add(r)
    await db.commit()
    return {"id": r.id}


@router.get("/resources")
async def resources(staff=Depends(librarian_dashboard), db=Depends(get_db)):
    return (
        await db.scalars(select(BookingResource).order_by(BookingResource.id))
    ).all()


@router.put("/resources/{resource_id}")
async def update_resource(
    resource_id: int,
    body: ResourceInput,
    staff=Depends(librarian_admin),
    db=Depends(get_db),
):
    await validate_resource_type(db, body.kind)
    async with write_lock:
        r = await db.scalar(
            select(BookingResource)
            .where(BookingResource.id == resource_id)
            .with_for_update()
        )
        if not r:
            raise HTTPException(404, "Resource unavailable")
        if await db.scalar(
            select(BookingResource).where(
                BookingResource.name == body.name, BookingResource.id != resource_id
            )
        ):
            raise HTTPException(409, "Resource name already exists")
        for k, v in body.model_dump().items():
            setattr(r, k, v)
        await db.commit()
    return {"id": r.id}


@router.post("")
async def create(body: BookingInput, request: Request, db=Depends(get_db)):
    source, person = await actor(request, db)
    participants = [p.model_dump() for p in body.participants]
    if body.use_profile:
        if source == "user" and (body.organizer_number or body.participant_numbers):
            raise HTTPException(422, "The organizer must be the signed-in user")
        async def snapshot(number=None):
            query = select(StudentProfile, User).join(User, User.id == StudentProfile.user_id)
            query = query.where(StudentProfile.student_number == number) if number else query.where(User.id == person.id)
            row = (await db.execute(query)).one_or_none()
            if not row or not row[0].is_active or not row[1].is_active:
                raise HTTPException(422, "Select an active library user")
            profile, user = row
            return dict(user_id=user.id, name=user.name, category=profile.user_type, program=profile.program or "",
                        year_level=profile.year_level or "", department=profile.department or "")
        if source == "manual":
            if not body.organizer_number or body.participants:
                raise HTTPException(422, "Select library users for the manual booking")
            participants = [await snapshot(number) for number in [body.organizer_number, *body.participant_numbers]]
        else:
            participants = [await snapshot(), *participants]
    if not participants:
        raise HTTPException(422, "Select a booking organizer")
    if any(p["category"] == "visitor" for p in participants):
        raise HTTPException(403, "Visitors cannot book library resources")
    async with write_lock:
        r = await db.scalar(
            select(BookingResource)
            .where(BookingResource.id == body.resource_id)
            .with_for_update()
        )
        if not r or not r.is_active:
            raise HTTPException(404, "Resource unavailable")
        document = guideline(r.kind)
        if document and (not body.guidelines_accepted or body.guidelines_version != document['version']):
            raise HTTPException(422, "Read and agree to the current booking guidelines before confirming your booking")
        additional_names = [" ".join(name.split()) for name in body.additional_member_names]
        member_numbers = body.additional_member_numbers
        if r.kind == 'collaboration_room' and (member_numbers or body.use_profile or source == 'user'):
            if len(member_numbers) < 2 or len(set(member_numbers)) != len(member_numbers):
                raise HTTPException(422, 'Select at least two distinct Library Users as additional members')
            organizer_category = (person.profile.user_type if person.profile else person.role) if source == 'user' else participants[0]['category']
            selected_members = []
            for number in member_numbers:
                row = (await db.execute(select(StudentProfile, User).join(User, User.id == StudentProfile.user_id).where(StudentProfile.student_number == number))).one_or_none()
                if not row or not row[0].is_active or not row[1].is_active or row[0].user_type == 'visitor':
                    raise HTTPException(422, 'Select active school Library Users as members')
                profile, member = row
                if organizer_category == 'student' and profile.user_type != 'student':
                    raise HTTPException(422, 'Student bookers may only select student members')
                selected_members.append(member)
            additional_names = [member.name for member in selected_members]
            if any(member.id == (person.id if source == 'user' else participants[0].get('user_id')) for member in selected_members):
                raise HTTPException(422, 'The booker is already included; select different members')
        elif member_numbers:
            raise HTTPException(422, 'Additional members are only allowed for Collaboration Rooms')
        if r.kind == 'collaboration_room' and len(participants) != 1:
            raise HTTPException(422, "Select one organizer and list the other members by full name")
        if any(len(name.split()) < 2 or len(name) > 255 for name in additional_names):
            raise HTTPException(422, "Enter each additional member's full name")
        member_names = [p['name'] for p in participants] + additional_names
        if r.kind == "collaboration_room" and len(member_names) < 3:
            raise HTTPException(422, "Collaboration Room bookings require at least three full names, including the booker")
        if r.kind != "collaboration_room" and additional_names:
            raise HTTPException(422, "Additional members are only allowed for Collaboration Rooms")
        timestamp = now()
        start = aware(body.starts_at) if body.starts_at else timestamp
        if body.starts_at and body.starts_at.tzinfo is None:
            raise HTTPException(422, "Start time must include a timezone")
        if start < timestamp:
            raise HTTPException(422, "Choose a future time or Start now")
        if start > timestamp + timedelta(days=1):
            raise HTTPException(
                422, "Reservations are available within the next 24 hours"
            )
        if len(member_names) > r.capacity:
            raise HTTPException(422, "Resource capacity exceeded")
        if len({" ".join(name.casefold().split()) for name in member_names}) != len(member_names):
            raise HTTPException(422, "List each participant only once")
        end = start + timedelta(minutes=r.duration_minutes)
        require_booking_hours(start, end, await booking_hours(db))
        await ensure_participants_available(db, [*participants, *[{'name': name} for name in additional_names]], start, end,
                                            owner_id=person.id if source == "user" else None)
        booked = await rows(db, r.id)
        if conflict(booked, start, end):
            raise HTTPException(
                409, "This time is already reserved; refresh availability"
            )
        if (
            source == "user"
            and participants[0]['name'].casefold() != person.name.strip().casefold()
        ):
            raise HTTPException(
                422, "The first participant must be the signed-in booking organizer"
            )
        b = FacilityBooking(
            resource_id=r.id,
            owner_id=person.id if source == "user" else None,
            starts_at=start,
            ends_at=end,
            participants=participants,
            source=source,
            actions=[
                {
                    "action": "booked",
                    "additional_member_names": additional_names,
                    "additional_member_numbers": member_numbers,
                    "actor": f"{source}:{person.id}",
                    "at": timestamp.isoformat(),
                }
            ],
        )
        db.add(b)
        if document:
            b.actions = [*b.actions, {
                "action": "guidelines_accepted", "actor": f"{source}:{person.id}",
                "at": timestamp.isoformat(), "version": document['version'],
                "resource_kind": r.kind, "guidelines": document,
                "accepted_by_user_id": person.id if source == 'user' else None,
                "attested_by_librarian_id": person.id if source == 'manual' else None,
                "organizer_user_id": participants[0].get('user_id'),
                "organizer_name": participants[0]['name'],
            }]
        await db.commit()
        return await serialize(b, r, booked, timestamp, db)


@router.get("")
async def list_bookings(request: Request, db=Depends(get_db)):
    if request.headers.get("X-Booking-Mode") != "user" and request.cookies.get("librarian_session"):
        await librarian_dashboard(await current_librarian(request, db))
        owner = None
    else:
        owner = (await booking_user(request, db)).id
    query = select(FacilityBooking).order_by(FacilityBooking.starts_at.desc())
    if owner is not None:
        query = query.where(FacilityBooking.owner_id == owner)
    bookings = list((await db.scalars(query)).all())
    result = []
    for b in bookings:
        r = await db.get(BookingResource, b.resource_id)
        result.append(
            {**await serialize(b, r, await rows(db, r.id), now(), db), "resource_name": r.name}
        )
    return {"items": result, "server_time": now().isoformat()}


async def change(booking_id, request, db, minutes=None, cancel=False):
    source, person = await actor(request, db)
    async with write_lock:
        b = await db.get(FacilityBooking, booking_id)
        if not b:
            raise HTTPException(404, "Booking unavailable")
        r = await db.scalar(
            select(BookingResource)
            .where(BookingResource.id == b.resource_id)
            .with_for_update()
        )
        await db.refresh(b)
        if source == "user" and b.owner_id != person.id:
            raise HTTPException(403, "You can manage only your own bookings")
        timestamp, start, end = now(), aware(b.starts_at), aware(b.ends_at)
        if cancel:
            if is_cancelled(b):
                return await serialize(b, r, await rows(db, r.id), timestamp, db)
            if b.ended_at or start <= timestamp:
                raise HTTPException(409, "Only upcoming bookings can be cancelled. Use End Session for an in-progress booking.")
            b.ended_at = timestamp
            b.actions = [*b.actions, {"action": "cancelled", "actor": f"{source}:{person.id}", "at": timestamp.isoformat()}]
            await db.commit()
            return await serialize(b, r, await rows(db, r.id), timestamp, db)
        if b.ended_at or not start <= timestamp < end:
            raise HTTPException(409, "Only active sessions can be changed")
        booked = await rows(db, r.id)
        if minutes is not None:
            new_end = end + timedelta(minutes=minutes)
            require_booking_hours(start, new_end, await booking_hours(db))
            if not r.is_active or new_end - start > timedelta(minutes=r.max_minutes):
                raise HTTPException(409, "Session usage limit reached")
            if conflict(booked, end, new_end, b.id):
                raise HTTPException(409, "Another user has reserved the next interval")
            await ensure_participants_available(db, [*b.participants, *[{'name': name} for name in booking_member_names(b)[len(b.participants):]]], end, new_end,
                                                owner_id=b.owner_id, exclude=b.id)
            b.ends_at = new_end
        else:
            b.ended_at = timestamp
            b.ends_at = timestamp
        b.actions = [
            *b.actions,
            {
                "action": "extended" if minutes else "ended_early",
                "minutes": minutes,
                "actor": f"{source}:{person.id}",
                "at": timestamp.isoformat(),
            },
        ]
        await db.commit()
        return await serialize(b, r, booked, timestamp, db)


@router.post("/{booking_id}/extend")
async def extend(
    booking_id: int, body: ExtensionInput, request: Request, db=Depends(get_db)
):
    return await change(booking_id, request, db, body.minutes)


@router.post("/{booking_id}/end")
async def end(booking_id: int, request: Request, db=Depends(get_db)):
    return await change(booking_id, request, db)


@router.post("/{booking_id}/cancel")
async def cancel_booking(booking_id: int, request: Request, db=Depends(get_db)):
    return await change(booking_id, request, db, cancel=True)


@router.get("/reports/usage")
async def usage(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    staff=Depends(librarian_dashboard),
    db=Depends(get_db),
):
    if any(v is not None and v.tzinfo is None for v in (date_from, date_to)):
        raise HTTPException(422, "Report timestamps require a timezone")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Invalid report period")
    timestamp = now()
    bookings = (
        await db.scalars(
            select(FacilityBooking).where(FacilityBooking.starts_at <= timestamp)
        )
    ).all()
    counts, totals = Counter(), Counter()
    for b in bookings:
        if is_cancelled(b):
            continue
        start = aware(b.starts_at)
        if (date_from and start < aware(date_from)) or (
            date_to and start >= aware(date_to)
        ):
            continue
        totals[b.resource_id] += 1
        for p in b.participants:
            counts[
                (
                    b.resource_id,
                    p["category"],
                    p["program"] if p["category"] == "student" else "",
                    p["year_level"] if p["category"] == "student" else "",
                    p["department"]
                    if p["category"] not in {"student", "visitor"}
                    else "",
                )
            ] += 1
    names = {r.id: r.name for r in (await db.scalars(select(BookingResource))).all()}
    return {
        "totals": [
            {
                "resource": name,
                "bookings": totals[rid],
                "participant_uses": sum(v for k, v in counts.items() if k[0] == rid),
            }
            for rid, name in names.items()
        ],
        "breakdowns": [
            {
                "resource": names[k[0]],
                "category": k[1],
                "program": k[2],
                "year_level": k[3],
                "department": k[4],
                "uses": v,
            }
            for k, v in sorted(counts.items())
        ],
    }
