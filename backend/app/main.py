from datetime import datetime, timezone
from urllib.parse import urlsplit

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from starlette.middleware.sessions import SessionMiddleware

from app.auth import current_librarian, current_user, issue_librarian, issue_student, verify_password
from app.config import settings
from app.database import get_db, init_database
from app.models import Librarian, LibrarySession, LibraryVisit, StudentProfile, User
from app.services import get_or_create_daily_session, scan


def frontend_origin() -> str:
    parsed = urlsplit(settings.frontend_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def safe_scan_path(value: str) -> str:
    if not value.startswith("/scan/") or value.startswith("//"):
        return "/"
    return value


def frontend_redirect(path: str, error: str | None = None) -> str:
    url = settings.frontend_url.rstrip("/") + safe_scan_path(path)
    if error:
        separator = "&" if "?" in url else "?"
        url += f"{separator}auth_error={error}"
    return url


app = FastAPI(title="Library Attendance API")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=settings.cookie_secure,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin()],
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
    await init_database()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/auth/status")
async def auth_status():
    return {
        "google_configured": bool(settings.google_client_id and settings.google_client_secret),
        "allowed_domain": settings.google_allowed_domain,
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
        profile = await db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
        if not profile:
            profile = StudentProfile(
                user_id=user.id,
                student_number=email.split("@", 1)[0].upper(),
                user_type="student",
                program=None,
                section=None,
                is_active=True,
            )
            db.add(profile)
        await db.commit()
        await db.refresh(user)
    except HTTPException as exc:
        error = "account_not_allowed" if exc.status_code == 403 else "google_auth_failed"
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
        "profile": None if not profile else {
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
    if settings.app_env != "local":
        raise HTTPException(404, "Local development sign-in is disabled")

    email = "qr-test@life.edu.ph"
    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(email=email, name="QR Test Student", role="student", is_active=True)
        db.add(user)
        await db.flush()
    profile = await db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
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
    if not librarian or not verify_password(str(body.get("password", "")), librarian.password_hash):
        raise HTTPException(401, "Invalid email or password")
    response = Response(status_code=204)
    response.set_cookie(
        "librarian_session", issue_librarian(librarian.id), httponly=True,
        secure=settings.cookie_secure, samesite=settings.cookie_samesite, max_age=28800, path="/"
    )
    return response


@app.get("/api/admin/me")
async def admin_me(librarian=Depends(current_librarian)):
    return {"id": librarian.id, "name": librarian.name, "email": librarian.email}


@app.post("/api/admin/logout")
async def admin_logout():
    response = Response(status_code=204)
    response.delete_cookie("librarian_session", path="/")
    return response


@app.get("/api/library/sessions/current")
async def current_session(db=Depends(get_db)):
    row, raw = await get_or_create_daily_session(db)
    return {
        "scan_url": f"{settings.frontend_url.rstrip('/')}/scan/{raw}",
        "session_date": row.session_date,
        "expires_at": row.expires_at,
        "status": row.status,
    }


@app.post("/api/library/sessions")
async def create_session(librarian=Depends(current_librarian), db=Depends(get_db)):
    row, raw = await get_or_create_daily_session(db)
    return {
        "scan_url": f"{settings.frontend_url.rstrip('/')}/scan/{raw}",
        "session_date": row.session_date,
        "expires_at": row.expires_at,
        "status": row.status,
    }

@app.post("/api/library/scan/{token}")
async def record(token: str, user=Depends(current_user), db=Depends(get_db)):
    action, visit = await scan(db, token, user)
    return {"action": action, "check_in_time": visit.time_in, "reference": f"LC-{visit.id:08d}"}


@app.get("/api/library/dashboard")
async def dashboard(librarian=Depends(current_librarian), db=Depends(get_db)):
    today = datetime.now(timezone.utc).date()
    rows = (
        await db.scalars(
            select(LibraryVisit)
            .join(LibrarySession)
            .where(LibrarySession.session_date == today)
            .options(selectinload(LibraryVisit.student).selectinload(StudentProfile.user))
            .order_by(LibraryVisit.time_in.desc())
        )
    ).all()
    return {
        "check_in_count": len(rows),
        "visit_count": len(rows),
        "visits": [
            {
                "id": visit.id, "name": visit.student.user.name,
                "student_number": visit.student.student_number,
                "check_in_time": visit.time_in, "status": "checked_in",
            }
            for visit in rows
        ],
    }
