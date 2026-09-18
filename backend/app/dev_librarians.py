import secrets

from sqlalchemy import select

from app.auth import hash_password
from app.config import settings
from app.models import Librarian

DEV_ACCOUNTS = [
    {"role": role, "name": name, "email": f"{role}@dev.library.local", "password": secrets.token_urlsafe(15)}
    for role, name in (
        ("admin", "Development Administrator"),
        ("librarian", "Development Librarian"),
        ("auditor", "Development Auditor"),
    )
]


def dev_accounts_enabled() -> bool:
    return settings.app_env == "local" and settings.enable_dev_librarians


async def seed_dev_librarians(db) -> None:
    if not dev_accounts_enabled():
        return
    for account in DEV_ACCOUNTS:
        row = await db.scalar(select(Librarian).where(Librarian.email == account["email"]))
        if row and not row.is_development:
            continue
        if not row:
            row = Librarian(email=account["email"], name=account["name"])
            db.add(row)
        row.name = account["name"]
        row.role = account["role"]
        row.password_hash = hash_password(account["password"])
        row.is_development = True
        row.is_active = True
    await db.commit()
