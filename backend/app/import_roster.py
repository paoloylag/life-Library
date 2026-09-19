import argparse
import asyncio
import csv
import io
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import boto3
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import StudentProfile, User

USER_TYPES = {
    "student",
    "faculty",
    "non-teaching personnel",
    "administrator",
    "visitor",
}
FIELDS = (
    "number",
    "name",
    "email",
    "user_type",
    "program",
    "year_level",
    "section",
    "department",
    "organization",
    "is_active",
)


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0


def active_value(value: str, row_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized in ("", "true", "yes", "1", "active"):
        return True
    if normalized in ("false", "no", "0", "inactive"):
        return False
    raise ValueError(f"Row {row_number}: is_active must be true or false")


def roster_text(source: str | Path) -> str:
    location = str(source)
    if location.startswith("s3://"):
        parsed = urlsplit(location)
        if not parsed.netloc or not parsed.path.lstrip("/"):
            raise ValueError("S3 roster location must include a bucket and object key")
        try:
            body = (
                boto3.client("s3")
                .get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))["Body"]
                .read()
            )
            return body.decode("utf-8-sig")
        except Exception as exc:
            raise ValueError(f"Unable to read private S3 roster: {exc}") from exc
    return Path(source).read_text(encoding="utf-8-sig")


def read_roster(source: str | Path) -> list[dict]:
    with io.StringIO(roster_text(source), newline="") as stream:
        reader = csv.DictReader(stream)
        missing = {"number", "name", "user_type"} - set(reader.fieldnames or [])
        unknown = set(reader.fieldnames or []) - set(FIELDS)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        if unknown:
            raise ValueError(f"Unknown columns: {', '.join(sorted(unknown))}")
        rows, numbers, emails = [], set(), set()
        for row_number, raw in enumerate(reader, 2):
            row = {field: (raw.get(field) or "").strip() for field in FIELDS}
            row["email"] = row["email"].lower()
            row["user_type"] = row["user_type"].lower()
            if not row["number"] or len(row["name"]) < 2:
                raise ValueError(f"Row {row_number}: number and name are required")
            if row["user_type"] not in USER_TYPES:
                raise ValueError(f"Row {row_number}: unsupported user_type")
            if row["user_type"] != "visitor" and row["email"].count("@") != 1:
                raise ValueError(
                    f"Row {row_number}: email is required for non-visitors"
                )
            if row["email"] and (
                row["email"].count("@") != 1 or any(c.isspace() for c in row["email"])
            ):
                raise ValueError(f"Row {row_number}: invalid email")
            if row["number"].casefold() in numbers:
                raise ValueError(f"Row {row_number}: duplicate number in file")
            if row["email"] and row["email"] in emails:
                raise ValueError(f"Row {row_number}: duplicate email in file")
            numbers.add(row["number"].casefold())
            if row["email"]:
                emails.add(row["email"])
            row["is_active"] = active_value(row["is_active"], row_number)
            rows.append(row)
    if not rows:
        raise ValueError("Roster file has no data rows")
    return rows


async def import_rows(rows: list[dict], dry_run: bool = False) -> ImportResult:
    result = ImportResult()
    async with SessionLocal() as db:
        for row in rows:
            profile = await db.scalar(
                select(StudentProfile)
                .where(StudentProfile.student_number == row["number"])
                .options(selectinload(StudentProfile.user))
            )
            user_by_email = None
            if row["email"]:
                user_by_email = await db.scalar(
                    select(User)
                    .where(User.email == row["email"])
                    .options(selectinload(User.profile))
                )
            if profile and user_by_email and user_by_email.id != profile.user_id:
                raise ValueError(f"Email {row['email']} belongs to another user")
            if not profile and user_by_email and user_by_email.profile:
                raise ValueError(f"Email {row['email']} already has another profile")
            if not profile:
                user = user_by_email or User(
                    email=row["email"]
                    or f"visitor-{row['number'].lower()}@visitor.local",
                    name=row["name"],
                    role=row["user_type"],
                    is_active=row["is_active"],
                )
                if not user_by_email:
                    db.add(user)
                    await db.flush()
                profile = StudentProfile(user_id=user.id, student_number=row["number"])
                db.add(profile)
                result.created += 1
            else:
                user = profile.user
                result.updated += 1
            user.name = row["name"]
            user.is_active = row["is_active"]
            profile.is_active = row["is_active"]
            if not user.google_id:
                user.role = row["user_type"]
                profile.user_type = row["user_type"]
                if row["email"]:
                    user.email = row["email"]
            for field in (
                "program",
                "year_level",
                "section",
                "department",
                "organization",
            ):
                setattr(profile, field, row[field] or None)
            await db.flush()
        if dry_run:
            await db.rollback()
        else:
            await db.commit()
    return result


async def main():
    parser = argparse.ArgumentParser(
        description="Validate and import a library-user roster CSV"
    )
    parser.add_argument("csv_file", help="Local path or private s3://bucket/key URI")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        rows = read_roster(args.csv_file)
        result = await import_rows(rows, args.dry_run)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    action = "Validated" if args.dry_run else "Imported"
    print(
        f"{action} {len(rows)} rows: {result.created} created, {result.updated} updated."
    )


if __name__ == "__main__":
    asyncio.run(main())
