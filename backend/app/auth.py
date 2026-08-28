from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from app.config import settings
from app.database import get_db
from app.models import Librarian, User

student_sessions = URLSafeTimedSerializer(settings.secret_key, salt="student-auth")
librarian_sessions = URLSafeTimedSerializer(settings.secret_key, salt="librarian-auth")
passwords = PasswordHasher()

def issue_student(user_id: int) -> str: return student_sessions.dumps({"id": user_id})
def issue_librarian(librarian_id: int) -> str: return librarian_sessions.dumps({"id": librarian_id})
def hash_password(password: str) -> str: return passwords.hash(password)
def verify_password(password: str, password_hash: str) -> bool:
    try: return passwords.verify(password_hash, password)
    except VerifyMismatchError: return False

async def current_user(request: Request, db=Depends(get_db)):
    try: payload = student_sessions.loads(request.cookies.get("library_session", ""), max_age=43200)
    except BadSignature: raise HTTPException(401, "Authentication required")
    user = await db.scalar(select(User).where(User.id == payload["id"], User.is_active.is_(True)))
    if not user: raise HTTPException(401, "Account unavailable")
    return user

async def current_librarian(request: Request, db=Depends(get_db)):
    try: payload = librarian_sessions.loads(request.cookies.get("librarian_session", ""), max_age=28800)
    except BadSignature: raise HTTPException(401, "Librarian authentication required")
    librarian = await db.scalar(select(Librarian).where(Librarian.id == payload["id"], Librarian.is_active.is_(True)))
    if not librarian: raise HTTPException(401, "Librarian account unavailable")
    return librarian
