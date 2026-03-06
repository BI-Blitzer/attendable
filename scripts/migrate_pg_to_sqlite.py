"""
Export PostgreSQL data to SQLite.

Usage:
    PG_SOURCE_URL=postgresql+psycopg2://... SQLITE_TARGET=event_agent.db \
        uv run python scripts/migrate_pg_to_sqlite.py

Env vars:
    PG_SOURCE_URL   — sync SQLAlchemy URL for the source PostgreSQL DB
                      Falls back to DATABASE_URL if it starts with 'postgresql'.
    SQLITE_TARGET   — path for the output SQLite file (default: event_agent.db)
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect, text

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

pg_url = os.environ.get("PG_SOURCE_URL", "")
if not pg_url:
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("postgresql"):
        # Convert async URL to sync if needed
        pg_url = db_url.replace("+asyncpg", "").replace("+psycopg2", "")
        if "postgresql://" not in pg_url and "postgresql+" not in pg_url:
            pg_url = db_url
        # Ensure sync driver
        if "+asyncpg" in pg_url:
            pg_url = pg_url.replace("+asyncpg", "+psycopg2")
        elif "postgresql://" in pg_url and "+" not in pg_url.split("://")[0]:
            pg_url = pg_url.replace("postgresql://", "postgresql+psycopg2://")
    else:
        print("ERROR: Set PG_SOURCE_URL to a PostgreSQL connection string.", file=sys.stderr)
        sys.exit(1)

sqlite_path = os.environ.get("SQLITE_TARGET", "event_agent.db")

print(f"Source:  {pg_url[:60]}...")
print(f"Target:  {sqlite_path}")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce(value):
    """Convert PG-specific types to SQLite-compatible values."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        # Store as ISO string; SQLAlchemy DateTime will handle it
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, dict):
        return json.dumps(value)
    if hasattr(value, "value"):  # Python Enum
        return value.value
    return value


# Tables in FK-dependency order
TABLES = [
    "companies",
    "people",
    "tags",
    "events",
    "event_interests",
    "event_speakers",
    "event_organizers",
    "event_sponsors",
    "event_tags",
]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

src_engine = create_engine(pg_url, echo=False)
dst_engine = create_engine(f"sqlite:///{sqlite_path}", echo=False)

# Reflect source schema to get column names
src_insp = inspect(src_engine)

with src_engine.connect() as src_conn, dst_engine.connect() as dst_conn:
    dst_conn.execute(text("PRAGMA foreign_keys = OFF"))

    for table in TABLES:
        if table not in src_insp.get_table_names():
            print(f"  {table}: not found in source, skipping")
            continue

        columns = [col["name"] for col in src_insp.get_columns(table)]
        rows = src_conn.execute(text(f"SELECT * FROM {table}")).fetchall()

        if not rows:
            print(f"  {table}: 0 rows")
            continue

        coerced = []
        for row in rows:
            coerced.append({col: _coerce(val) for col, val in zip(columns, row)})

        # Clear destination table first (idempotent re-runs)
        dst_conn.execute(text(f"DELETE FROM {table}"))

        col_list = ", ".join(columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        dst_conn.execute(text(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"), coerced)
        dst_conn.commit()
        print(f"  {table}: {len(coerced)} rows")

    dst_conn.execute(text("PRAGMA foreign_keys = ON"))

print("Done.")
