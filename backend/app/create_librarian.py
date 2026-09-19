import argparse
import asyncio
import getpass
import os

from sqlalchemy import select

from app.auth import hash_password
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Librarian


def arguments():
    parser = argparse.ArgumentParser(description="Create a library staff account")
    parser.add_argument("--email")
    parser.add_argument("--name")
    parser.add_argument(
        "--role", choices=("librarian", "librarian_associate", "auditor")
    )
    parser.add_argument(
        "--password-env",
        default="LIBRARIAN_INITIAL_PASSWORD",
        help="Environment variable containing the initial password",
    )
    return parser.parse_args()


async def create_account(email: str, name: str, role: str, password: str):
    email, name, role = email.strip().lower(), name.strip(), role.strip().lower()
    if role not in ("librarian", "librarian_associate", "auditor"):
        raise SystemExit("Invalid role.")
    if len(name) < 2 or email.count("@") != 1 or any(char.isspace() for char in email):
        raise SystemExit("Enter a valid name and email address.")
    if len(password) < 10:
        raise SystemExit("Password must be at least 10 characters.")
    if settings.app_env != "production":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        if await db.scalar(select(Librarian).where(Librarian.email == email)):
            raise SystemExit("Account already exists.")
        db.add(
            Librarian(
                email=email, name=name, role=role, password_hash=hash_password(password)
            )
        )
        await db.commit()
    print("Librarian account created.")


async def main():
    args = arguments()
    email = args.email or input("Email: ")
    name = args.name or input("Name: ")
    role = (
        args.role
        or input("Role [librarian/librarian_associate/auditor] (librarian_associate): ")
        .strip()
        .lower()
        or "librarian_associate"
    )
    password = os.environ.get(args.password_env) or getpass.getpass("Password: ")
    await create_account(email, name, role, password)


if __name__ == "__main__":
    asyncio.run(main())
