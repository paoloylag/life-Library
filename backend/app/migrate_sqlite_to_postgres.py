import argparse
import asyncio
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import JSON, Boolean, Date, DateTime, delete, func, select, text

from app import models  # noqa: F401
from app.config import settings
from app.database import Base, engine

TABLE_ORDER = [
    "librarians",
    "users",
    "student_profiles",
    "library_sessions",
    "library_visits",
    "library_configuration",
    "library_settings_audit",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy the local SQLite dataset into a migrated PostgreSQL database."
    )
    parser.add_argument("source", type=Path, help="Path to the source SQLite database")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing target rows before importing the SQLite dataset",
    )
    return parser.parse_args()


def convert_value(column, value):
    if value is None:
        return None
    if isinstance(column.type, Boolean):
        return bool(value)
    if isinstance(column.type, DateTime) and isinstance(value, str):
        return datetime.fromisoformat(value)
    if isinstance(column.type, Date) and isinstance(value, str):
        return date.fromisoformat(value)
    if isinstance(column.type, JSON) and isinstance(value, str):
        return json.loads(value)
    return value


def read_source(source: Path) -> dict[str, list[dict]]:
    if not source.is_file():
        raise FileNotFoundError(f"SQLite source does not exist: {source}")

    result: dict[str, list[dict]] = {}
    with sqlite3.connect(source) as connection:
        connection.row_factory = sqlite3.Row
        available = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        for table_name in TABLE_ORDER:
            if table_name not in available:
                result[table_name] = []
                continue
            table = Base.metadata.tables[table_name]
            rows = connection.execute(f'SELECT * FROM "{table_name}"').fetchall()
            result[table_name] = []
            for row in rows:
                source_columns = set(row.keys())
                result[table_name].append(
                    {
                        column.name: convert_value(column, row[column.name])
                        for column in table.columns
                        if column.name in source_columns
                    }
                )
    return result


async def import_data(source: Path, replace: bool) -> dict[str, int]:
    if not settings.database_url.startswith(("postgresql+asyncpg://", "postgresql://")):
        raise RuntimeError("DATABASE_URL must point to PostgreSQL")

    source_rows = read_source(source)
    async with engine.begin() as connection:
        existing = 0
        for table_name in TABLE_ORDER:
            result = await connection.execute(
                select(func.count()).select_from(Base.metadata.tables[table_name])
            )
            existing += result.scalar_one()
        if existing and not replace:
            raise RuntimeError(
                f"Target contains {existing} rows; rerun with --replace to overwrite it"
            )

        if replace:
            for table_name in reversed(TABLE_ORDER):
                await connection.execute(delete(Base.metadata.tables[table_name]))

        for table_name in TABLE_ORDER:
            rows = source_rows[table_name]
            if rows:
                await connection.execute(
                    Base.metadata.tables[table_name].insert(), rows
                )

        for table_name in TABLE_ORDER:
            table = Base.metadata.tables[table_name]
            if "id" not in table.columns:
                continue
            await connection.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence(:table_name, 'id'), "
                    'COALESCE((SELECT MAX(id) FROM "' + table_name + '"), 1), '
                    'EXISTS (SELECT 1 FROM "' + table_name + '"))'
                ),
                {"table_name": table_name},
            )

    await engine.dispose()
    return {name: len(rows) for name, rows in source_rows.items()}


async def main() -> None:
    args = parse_args()
    counts = await import_data(args.source.resolve(), args.replace)
    for table_name, count in counts.items():
        print(f"{table_name}: {count}")
    print("SQLite data imported into PostgreSQL.")


if __name__ == "__main__":
    asyncio.run(main())
