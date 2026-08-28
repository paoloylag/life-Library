import asyncio
import getpass
from sqlalchemy import select
from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Librarian

async def main():
    email = input("Email: ").strip().lower()
    name = input("Name: ").strip()
    password = getpass.getpass("Password: ")
    if len(password) < 10: raise SystemExit("Password must be at least 10 characters.")
    async with engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        if await db.scalar(select(Librarian).where(Librarian.email == email)): raise SystemExit("Account already exists.")
        db.add(Librarian(email=email, name=name, password_hash=hash_password(password)))
        await db.commit()
    print("Librarian account created.")

if __name__ == "__main__": asyncio.run(main())
