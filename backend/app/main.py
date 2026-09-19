import asyncio
from uuid import uuid4
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from starlette.middleware.sessions import SessionMiddleware

from app.auth import (
    current_librarian,
    current_user,
    issue_librarian,
    issue_student,
    hash_password,
    librarian_admin,
    librarian_editor,
    verify_password,
)
from app.config import settings
from app.database import SessionLocal, get_db, init_database
from app.dev_librarians import DEV_ACCOUNTS, dev_accounts_enabled, seed_dev_librarians
from app.google_directory import lookup_directory_identity
from app.library_settings import LibrarySettings, read_library_settings, save_library_settings, settings_audit
from app.models import Librarian, LibraryConfiguration, LibrarySession, LibraryVisit, StudentProfile, User
from app.report_exports import export_excel, export_pdf
from app.reports import ReportFilters, build_report
from app.services import (
    MANILA,
    attendance_day,
    create_visitor_profile,
    get_or_create_daily_session,
    scan,
    utc_bounds,
    valid_session_for_token,
)


class ManualCheckIn(BaseModel):
    user_number: str | None = None
    visitor_name: str | None = None
    organization: str | None = None
    purpose: str | None = None
    checked_in_at: datetime | None = None
    note: str | None = Field(default=None, max_length=1000)


class GuestCheckIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    organization: str | None = Field(default=None, max_length=180)
    purpose: str = Field(min_length=2, max_length=180)


class StaffAccountCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=10, max_length=128)
    role: str


class StaffAccountUpdate(BaseModel):
    role: str
    is_active: bool


def staff_json(row: Librarian):
    return {"id": row.id, "name": row.name, "email": row.email,
            "role": row.role, "is_active": row.is_active,
            "is_development": row.is_development}


class LibraryUserInput(BaseModel):
    number: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=255)
    email: str = Field(default="", max_length=255)
    user_type: str
    program: str = Field(default="", max_length=120)
    year_level: str = Field(default="", max_length=50)
    section: str = Field(default="", max_length=120)
    department: str = Field(default="", max_length=120)
    organization: str = Field(default="", max_length=180)
    is_active: bool = True


USER_CATEGORIES = {"student", "faculty", "non-teaching personnel", "administrator", "visitor"}


def clean_user_input(body: LibraryUserInput):
    values = {key: value.strip() if isinstance(value, str) else value for key, value in body.model_dump().items()}
    values["email"] = values["email"].lower()
    if not values["number"] or len(values["name"]) < 2 or values["user_type"] not in USER_CATEGORIES:
        raise HTTPException(422, "Enter a valid number, name, and user category")
    if values["user_type"] != "visitor" and ("@" not in values["email"] or values["email"].endswith("@visitor.local")):
        raise HTTPException(422, "An email address is required for a non-visitor account")
    if values["email"] and ("@" not in values["email"] or values["email"].startswith("@")):
        raise HTTPException(422, "Enter a valid email address")
    return values


def safe_scan_path(value: str) -> str:
    if not value.startswith("/scan/") or value.startswith("//"):
        return "/"
    return value


def scan_url(request: Request, token: str) -> str:
    if settings.app_env != "production":
        origin = request.headers.get("origin", "").rstrip("/")
        if origin:
            base_path = urlsplit(settings.frontend_url).path.rstrip("/")
            return f"{origin}{base_path}/scan/{token}"
    return f"{settings.frontend_url.rstrip('/')}/scan/{token}"


def frontend_redirect(path: str, error: str | None = None) -> str:
    url = settings.frontend_url.rstrip("/") + safe_scan_path(path)
    if error:
        separator = "&" if "?" in url else "?"
        url += f"{separator}auth_error={error}"
    return url


def profile_json(profile: StudentProfile, visit_count: int = 0, last_visit=None):
    return {
        "number": profile.student_number,
        "name": profile.user.name,
        "email": profile.user.email
        if not profile.user.email.endswith("@visitor.local")
        else "",
        "user_type": profile.user_type,
        "program": profile.program or "",
        "year_level": profile.year_level or "",
        "section": profile.section or "",
        "department": profile.department or "",
        "organization": profile.organization or "",
        "is_active": profile.is_active and profile.user.is_active,
        "managed_by_google": bool(profile.user.google_id),
        "visit_count": visit_count,
        "last_visit": last_visit,
    }


def visit_json(visit: LibraryVisit):
    profile = visit.student
    return {
        "id": visit.id,
        "user_number": profile.student_number,
        "name": profile.user.name,
        "user_type": profile.user_type,
        "program": profile.program or "",
        "year_level": profile.year_level or "",
        "section": profile.section or "",
        "department": profile.department or "",
        "organization": profile.organization or "",
        "check_in_time": visit.time_in,
        "source": visit.source,
        "recorded_by": visit.adjuster.name if visit.adjuster else None,
        "note": visit.adjustment_note or "",
        "purpose": visit.purpose or "",
        "reference": f"LC-{visit.id:08d}",
    }


app = FastAPI(title="Library Attendance API")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site=settings.cookie_samesite,
    https_only=settings.cookie_secure,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@app.on_event("startup")
async def startup() -> None:
    settings.validate_production_auth()
    await init_database()
    if dev_accounts_enabled():
        async with SessionLocal() as db:
            await seed_dev_librarians(db)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/auth/status")
async def auth_status():
    return {
        "google_configured": bool(
            settings.google_client_id and settings.google_client_secret
        ),
        "allowed_domain": settings.google_allowed_domain,
    }


@app.get("/api/library/settings")
async def get_library_settings(
    librarian=Depends(librarian_admin), db=Depends(get_db),
):
    row = await db.get(LibraryConfiguration, 1)
    return {
        "settings": (await read_library_settings(db)).model_dump(),
        "audit": await settings_audit(db),
        "configured": row is not None,
    }


@app.put("/api/library/settings")
async def put_library_settings(
    payload: LibrarySettings,
    librarian=Depends(librarian_admin),
    db=Depends(get_db),
):
    await save_library_settings(db, payload, librarian.name)
    return {"settings": payload.model_dump(), "audit": await settings_audit(db), "configured": True}


@app.get("/api/library/settings/display")
async def get_library_display_settings(db=Depends(get_db)):
    values = await read_library_settings(db)
    return {
        "libraryName": values.libraryName,
        "qrHeading": values.qrHeading,
        "qrInstructions": values.qrInstructions,
        "roomBookingUrl": values.roomBookingUrl,
    }


@app.get("/api/auth/google")
async def login(request: Request, next: str = "/"):
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503, "Google authentication is not configured")
    next_path = safe_scan_path(next)
    request.session["next"] = next_path
    return await oauth.google.authorize_redirect(
        request,
        settings.google_redirect_uri,
        hd=settings.google_allowed_domain,
        prompt="select_account",
    )


@app.get("/api/auth/google/callback")
async def callback(request: Request, db=Depends(get_db)):
    next_path = safe_scan_path(request.session.pop("next", "/"))
    try:
        token = await oauth.google.authorize_access_token(request)
        info = token.get("userinfo") or {}
        email = str(info.get("email", "")).strip().lower()
        if not info.get("email_verified"):
            raise HTTPException(403, "Google email is not verified")
        if str(info.get("hd", "")).lower() != settings.google_allowed_domain.lower():
            raise HTTPException(403, "Use your Life College Google account")

        user = await db.scalar(
            select(User).where(or_(User.google_id == info["sub"], User.email == email))
        )
        if user and user.google_id and user.google_id != info["sub"]:
            raise HTTPException(409, "This email is linked to another Google account")
        if not user:
            user = User(
                email=email,
                name=info.get("name") or email,
                google_id=info["sub"],
                avatar_url=info.get("picture"),
            )
            db.add(user)
        else:
            user.google_id = info["sub"]
            user.name = info.get("name") or user.name
            user.avatar_url = info.get("picture") or user.avatar_url

        await db.flush()
        directory_identity = await asyncio.to_thread(lookup_directory_identity, email)
        profile = await db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == user.id)
        )
        if not profile:
            resolved_user_type = (
                directory_identity.user_type if directory_identity else "student"
            )
            profile = StudentProfile(
                user_id=user.id,
                student_number=email.split("@", 1)[0].upper(),
                user_type=resolved_user_type,
                program=None,
                section=None,
                is_active=True,
            )
            db.add(profile)
            user.role = resolved_user_type
        elif directory_identity:
            profile.user_type = directory_identity.user_type
            user.role = directory_identity.user_type
        await db.commit()
        await db.refresh(user)
    except HTTPException as exc:
        error = (
            "account_not_allowed" if exc.status_code == 403 else "google_auth_failed"
        )
        return RedirectResponse(frontend_redirect(next_path, error))
    except Exception:
        return RedirectResponse(frontend_redirect(next_path, "google_auth_failed"))

    response = RedirectResponse(frontend_redirect(next_path))
    response.set_cookie(
        "library_session",
        issue_student(user.id),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=43200,
        path="/",
    )
    return response


@app.get("/api/auth/me")
async def me(user=Depends(current_user)):
    profile = user.profile
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "profile": None
        if not profile
        else {
            "number": profile.student_number,
            "user_type": profile.user_type,
            "program": profile.program or "",
            "year_level": "",
            "section": profile.section or "",
            "department": "",
        },
    }


@app.post("/api/auth/dev-login")
async def dev_login(db=Depends(get_db)):
    if not dev_accounts_enabled():
        raise HTTPException(404, "Local development sign-in is disabled")

    email = "qr-test@life.edu.ph"
    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(email=email, name="QR Test Student", role="student", is_active=True)
        db.add(user)
        await db.flush()
    profile = await db.scalar(
        select(StudentProfile).where(StudentProfile.user_id == user.id)
    )
    if not profile:
        db.add(
            StudentProfile(
                user_id=user.id,
                student_number="QR-TEST-001",
                user_type="student",
                program="Local Development",
                section="Test Section",
                is_active=True,
            )
        )
    await db.commit()

    response = Response(status_code=204)
    response.set_cookie(
        "library_session",
        issue_student(user.id),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=43200,
        path="/",
    )
    return response


@app.post("/api/auth/logout")
async def user_logout():
    response = Response(status_code=204)
    response.delete_cookie("library_session", path="/")
    return response


@app.post("/api/admin/login")
async def admin_login(request: Request, db=Depends(get_db)):
    body = await request.json()
    librarian = await db.scalar(
        select(Librarian).where(
            Librarian.email == str(body.get("email", "")).strip().lower(),
            Librarian.is_active.is_(True),
        )
    )
    if (
        not librarian
        or (librarian.is_development and not dev_accounts_enabled())
        or not verify_password(str(body.get("password", "")), librarian.password_hash)
    ):
        raise HTTPException(401, "Invalid email or password")
    response = Response(status_code=204)
    response.set_cookie(
        "librarian_session",
        issue_librarian(librarian.id),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=28800,
        path="/",
    )
    return response


@app.get("/api/admin/me")
async def admin_me(librarian=Depends(current_librarian)):
    return {"id": librarian.id, "name": librarian.name, "email": librarian.email, "role": librarian.role}


@app.get("/api/admin/accounts")
async def list_staff_accounts(librarian=Depends(librarian_editor), db=Depends(get_db)):
    rows = (await db.scalars(select(Librarian).order_by(Librarian.name))).all()
    return {"items": [staff_json(row) for row in rows]}


@app.post("/api/admin/accounts", status_code=201)
async def create_staff_account(
    body: StaffAccountCreate, librarian=Depends(librarian_editor), db=Depends(get_db)
):
    name, email = body.name.strip(), body.email.strip().lower()
    if (len(name) < 2 or email.count("@") != 1 or
            any(char.isspace() for char in email) or
            not all(email.split("@"))):
        raise HTTPException(422, "Enter a valid name and email address")
    if body.role not in ("librarian", "librarian_associate", "auditor"):
        raise HTTPException(422, "Invalid staff role")
    if body.role == "librarian" and librarian.role != "librarian":
        raise HTTPException(403, "Only a librarian may assign the librarian role")
    if await db.scalar(select(Librarian.id).where(Librarian.email == email)):
        raise HTTPException(409, "A staff account with this email already exists")
    row = Librarian(name=name, email=email, role=body.role,
                    password_hash=hash_password(body.password), is_active=True)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "A staff account with this email already exists")
    return staff_json(row)


@app.patch("/api/admin/accounts/{account_id}")
async def update_staff_account(
    account_id: int, body: StaffAccountUpdate,
    librarian=Depends(librarian_editor), db=Depends(get_db)
):
    row = await db.get(Librarian, account_id)
    if not row:
        raise HTTPException(404, "Staff account not found")
    if row.is_development:
        raise HTTPException(409, "Development test accounts cannot be edited")
    if body.role not in ("librarian", "librarian_associate", "auditor"):
        raise HTTPException(422, "Invalid staff role")
    if librarian.role != "librarian" and (row.role == "librarian" or body.role == "librarian"):
        raise HTTPException(403, "Only a librarian may manage librarian accounts")
    if row.id == librarian.id and (not body.is_active or body.role != row.role):
        raise HTTPException(409, "You cannot remove your own access")
    if row.role == "librarian" and (body.role != "librarian" or not body.is_active) and row.is_active:
        count = await db.scalar(select(func.count(Librarian.id)).where(
            Librarian.role == "librarian", Librarian.is_active.is_(True),
            Librarian.is_development.is_(False)))
        if count <= 1:
            raise HTTPException(409, "At least one active librarian is required")
    row.role, row.is_active = body.role, body.is_active
    await db.commit()
    return staff_json(row)


@app.get("/api/admin/dev-accounts")
async def admin_dev_accounts():
    if not dev_accounts_enabled():
        raise HTTPException(404, "Development accounts unavailable")
    return {"accounts": DEV_ACCOUNTS}


@app.post("/api/admin/logout")
async def admin_logout():
    response = Response(status_code=204)
    response.delete_cookie("librarian_session", path="/")
    return response


@app.get("/api/library/sessions/current")
async def current_session(
    request: Request, librarian=Depends(librarian_editor), db=Depends(get_db),
):
    row, raw = await get_or_create_daily_session(db)
    return {
        "scan_url": scan_url(request, raw),
        "session_date": row.session_date,
        "expires_at": row.expires_at,
        "status": row.status,
    }


@app.post("/api/library/sessions")
async def create_session(
    request: Request, librarian=Depends(librarian_editor), db=Depends(get_db)
):
    row, raw = await get_or_create_daily_session(db)
    return {
        "scan_url": scan_url(request, raw),
        "session_date": row.session_date,
        "expires_at": row.expires_at,
        "status": row.status,
    }


@app.post("/api/library/scan/{token}")
async def record(token: str, user=Depends(current_user), db=Depends(get_db)):
    action, visit = await scan(db, token, user)
    return {
        "action": action,
        "check_in_time": visit.time_in,
        "reference": f"LC-{visit.id:08d}",
    }


@app.post("/api/library/scan/{token}/guest")
async def record_guest(token: str, body: GuestCheckIn, db=Depends(get_db)):
    session = await valid_session_for_token(db, token)
    profile = await create_visitor_profile(db, body.name, body.organization)
    visit = LibraryVisit(
        student_profile_id=profile.id,
        library_session_id=session.id,
        time_in=datetime.now(timezone.utc),
        status="checked_in",
        source="guest",
        purpose=body.purpose.strip(),
    )
    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    return {
        "action": "check_in",
        "check_in_time": visit.time_in,
        "reference": f"LC-{visit.id:08d}",
        "user_number": profile.student_number,
    }


@app.get("/api/library/users")
async def library_users(
    q: str = "",
    user_type: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    librarian=Depends(current_librarian),
    db=Depends(get_db),
):
    filters = []
    if q.strip():
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                User.name.ilike(term),
                User.email.ilike(term),
                StudentProfile.student_number.ilike(term),
                StudentProfile.program.ilike(term),
                StudentProfile.section.ilike(term),
                StudentProfile.department.ilike(term),
            )
        )
    if user_type.strip():
        filters.append(StudentProfile.user_type == user_type.strip().lower())

    total = await db.scalar(
        select(func.count(StudentProfile.id)).join(User).where(*filters)
    )
    profiles = (
        await db.scalars(
            select(StudentProfile)
            .join(User)
            .where(*filters)
            .options(selectinload(StudentProfile.user))
            .order_by(User.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    summaries = {}
    if profiles:
        rows = (
            await db.execute(
                select(
                    LibraryVisit.student_profile_id,
                    func.count(LibraryVisit.id),
                    func.max(LibraryVisit.time_in),
                )
                .where(
                    LibraryVisit.student_profile_id.in_(
                        [profile.id for profile in profiles]
                    )
                )
                .group_by(LibraryVisit.student_profile_id)
            )
        ).all()
        summaries = {row[0]: (row[1], row[2]) for row in rows}
    items = [
        profile_json(profile, *summaries.get(profile.id, (0, None)))
        for profile in profiles
    ]
    items.sort(
        key=lambda item: (item["name"].split()[-1].casefold(), item["name"].casefold())
    )
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


@app.post("/api/library/users", status_code=201)
async def create_library_user(
    body: LibraryUserInput, librarian=Depends(librarian_admin), db=Depends(get_db)
):
    values = clean_user_input(body)
    email = values["email"] or f"visitor-{uuid4().hex}@visitor.local"
    if await db.scalar(select(User.id).where(User.email == email)) or await db.scalar(
        select(StudentProfile.id).where(StudentProfile.student_number == values["number"])
    ):
        raise HTTPException(409, "Email address or user number already exists")
    user = User(email=email, name=values["name"], role=values["user_type"], is_active=values["is_active"])
    db.add(user)
    await db.flush()
    profile = StudentProfile(
        user_id=user.id, student_number=values["number"], user_type=values["user_type"],
        is_active=values["is_active"], **{key: values[key] or None for key in
        ("program", "year_level", "section", "department", "organization")}
    )
    db.add(profile)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Email address or user number already exists")
    await db.refresh(profile)
    return profile_json(profile)


@app.put("/api/library/users/{number}")
async def update_library_user(
    number: str, body: LibraryUserInput, librarian=Depends(librarian_admin), db=Depends(get_db)
):
    values = clean_user_input(body)
    profile = await db.scalar(
        select(StudentProfile).where(StudentProfile.student_number == number)
        .options(selectinload(StudentProfile.user))
    )
    if not profile:
        raise HTTPException(404, "Library user not found")
    if profile.user.google_id and values["user_type"] != profile.user_type:
        raise HTTPException(409, "Google-linked user categories are managed by Workspace")
    if profile.user.google_id and (values["email"] != profile.user.email or values["number"] != number):
        raise HTTPException(409, "Google-linked email and user number cannot be changed here")
    if not values["email"] and values["user_type"] == "visitor":
        values["email"] = profile.user.email
    if values["email"] != profile.user.email and await db.scalar(
        select(User.id).where(User.email == values["email"])
    ):
        raise HTTPException(409, "Email address already exists")
    if values["number"] != number and await db.scalar(
        select(StudentProfile.id).where(StudentProfile.student_number == values["number"])
    ):
        raise HTTPException(409, "User number already exists")
    profile.user.name = values["name"]
    profile.user.email = values["email"]
    profile.user.role = values["user_type"]
    profile.user.is_active = values["is_active"]
    profile.student_number = values["number"]
    profile.user_type = values["user_type"]
    profile.is_active = values["is_active"]
    for key in ("program", "year_level", "section", "department", "organization"):
        setattr(profile, key, values[key] or None)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Email address or user number already exists")
    return profile_json(profile)


@app.get("/api/library/users/{number}")
async def library_user(
    number: str, librarian=Depends(current_librarian), db=Depends(get_db)
):
    profile = await db.scalar(
        select(StudentProfile)
        .where(StudentProfile.student_number == number)
        .options(selectinload(StudentProfile.user))
    )
    if not profile:
        raise HTTPException(404, "Library user not found")
    summary = (
        await db.execute(
            select(func.count(LibraryVisit.id), func.max(LibraryVisit.time_in)).where(
                LibraryVisit.student_profile_id == profile.id
            )
        )
    ).one()
    return profile_json(profile, summary[0], summary[1])


@app.get("/api/library/users/{number}/visits")
async def library_user_visits(
    number: str, librarian=Depends(current_librarian), db=Depends(get_db)
):
    profile = await db.scalar(
        select(StudentProfile).where(StudentProfile.student_number == number)
    )
    if not profile:
        raise HTTPException(404, "Library user not found")
    rows = (
        await db.scalars(
            select(LibraryVisit)
            .where(LibraryVisit.student_profile_id == profile.id)
            .options(
                selectinload(LibraryVisit.student).selectinload(StudentProfile.user),
                selectinload(LibraryVisit.adjuster),
            )
            .order_by(LibraryVisit.time_in.desc())
        )
    ).all()
    return {"items": [visit_json(row) for row in rows], "total": len(rows)}


@app.get("/api/library/attendance")
async def attendance(
    q: str = "",
    user_type: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    librarian=Depends(current_librarian),
    db=Depends(get_db),
):
    filters = []
    if q.strip():
        term = f"%{q.strip()}%"
        filters.append(
            or_(User.name.ilike(term), StudentProfile.student_number.ilike(term))
        )
    if user_type.strip():
        filters.append(StudentProfile.user_type == user_type.strip().lower())
    base = select(LibraryVisit).join(StudentProfile).join(User).where(*filters)
    total = await db.scalar(
        select(func.count(LibraryVisit.id))
        .join(StudentProfile)
        .join(User)
        .where(*filters)
    )
    rows = (
        await db.scalars(
            base.options(
                selectinload(LibraryVisit.student).selectinload(StudentProfile.user),
                selectinload(LibraryVisit.adjuster),
            )
            .order_by(LibraryVisit.time_in.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return {
        "items": [visit_json(row) for row in rows],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


@app.post("/api/library/attendance/manual")
async def manual_check_in(
    body: ManualCheckIn,
    librarian=Depends(librarian_editor),
    db=Depends(get_db),
):
    checked_in_at = body.checked_in_at or datetime.now(timezone.utc)
    if checked_in_at.tzinfo is None:
        checked_in_at = checked_in_at.replace(tzinfo=timezone.utc)
    checked_in_at = checked_in_at.astimezone(timezone.utc)
    if checked_in_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(422, "Check-in time cannot be in the future")

    if body.user_number:
        profile = await db.scalar(
            select(StudentProfile).where(
                StudentProfile.student_number == body.user_number
            )
        )
        if not profile or not profile.is_active:
            raise HTTPException(404, "Active library user not found")
    elif body.visitor_name and body.visitor_name.strip():
        profile = await create_visitor_profile(db, body.visitor_name, body.organization)
    else:
        raise HTTPException(422, "Select a library user or enter a visitor name")

    manual_day = attendance_day(checked_in_at)
    session = await db.scalar(
        select(LibrarySession)
        .where(LibrarySession.session_date == manual_day)
        .order_by(LibrarySession.id.desc())
    )
    if not session:
        session, _ = await get_or_create_daily_session(db, checked_in_at)
    visit = LibraryVisit(
        student_profile_id=profile.id,
        library_session_id=session.id,
        time_in=checked_in_at,
        status="checked_in",
        source="manual",
        adjusted_by=librarian.id,
        adjustment_note=(body.note or "").strip() or None,
        purpose=(body.purpose or "").strip() or None,
    )
    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    return {
        "action": "check_in",
        "check_in_time": visit.time_in,
        "reference": f"LC-{visit.id:08d}",
        "recorded_by": librarian.name,
    }


@app.get("/api/library/dashboard")
async def dashboard(librarian=Depends(current_librarian), db=Depends(get_db)):
    starts_at, expires_at = utc_bounds(attendance_day())
    rows = (
        await db.scalars(
            select(LibraryVisit)
            .where(LibraryVisit.time_in.between(starts_at, expires_at))
            .options(
                selectinload(LibraryVisit.student).selectinload(StudentProfile.user),
                selectinload(LibraryVisit.adjuster),
            )
            .order_by(LibraryVisit.time_in.desc())
        )
    ).all()
    unique_users = len({visit.student_profile_id for visit in rows})
    hours: dict[int, int] = {}
    for visit in rows:
        local_hour = visit.time_in.astimezone(MANILA).hour
        hours[local_hour] = hours.get(local_hour, 0) + 1
    peak_hour = max(hours, key=hours.get) if hours else None
    return {
        "check_in_count": len(rows),
        "unique_visitors": unique_users,
        "peak_hour": peak_hour,
        "visits": [visit_json(visit) for visit in rows[:20]],
    }


def report_filters(
    date_from: date | None = None,
    date_to: date | None = None,
    academic_year: str = "All",
    semester: str = "All",
    grouping: str = "Monthly",
    user_type: str = "All",
    year_level: str = "All",
    section: str = "All",
    program: str = "All",
    department: str = "All",
) -> ReportFilters:
    return ReportFilters(
        date_from=date_from, date_to=date_to, academic_year=academic_year,
        semester=semester, grouping=grouping, user_type=user_type,
        year_level=year_level, section=section, program=program,
        department=department,
    )


@app.get("/api/library/reports")
async def library_report(
    filters: ReportFilters = Depends(report_filters),
    librarian=Depends(current_librarian),
    db=Depends(get_db),
):
    return await build_report(db, filters)


@app.get("/api/library/reports/export.xlsx")
async def library_report_excel(
    filters: ReportFilters = Depends(report_filters),
    librarian=Depends(current_librarian),
    db=Depends(get_db),
):
    report = await build_report(db, filters)
    return Response(
        content=export_excel(report),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="life-college-library-report.xlsx"'},
    )


@app.get("/api/library/reports/export.pdf")
async def library_report_pdf(
    filters: ReportFilters = Depends(report_filters),
    librarian=Depends(current_librarian),
    db=Depends(get_db),
):
    report = await build_report(db, filters)
    return Response(
        content=export_pdf(report),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="life-college-library-report.pdf"'},
    )
