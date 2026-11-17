"""Postgres access (Supabase's database) through a small connection pool.

The agent connects as the database owner, which skips Row Level Security.
So EVERY query in the agent filters by the logged-in teacher's user_id itself.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator, Sequence

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from app.config import get_settings


class DatabaseNotConfigured(RuntimeError):
    pass


@lru_cache
def get_pool() -> ConnectionPool:
    s = get_settings()
    if not s.database_url:
        raise DatabaseNotConfigured("Set DATABASE_URL in agent/.env")
    return ConnectionPool(
        s.database_url,
        min_size=1,
        max_size=10,
        open=True,
        configure=_configure,
        kwargs={
            "row_factory": dict_row,
            "autocommit": True,
            # Supabase poolers don't like server-side prepared statements.
            "prepare_threshold": None,
        },
    )


def _configure(conn: Connection) -> None:
    # pgvector may live in the "extensions" schema on Supabase. Set this per
    # connection (poolers can drop startup "options").
    conn.execute("set search_path = public, extensions")


@contextmanager
def connection() -> Iterator[Connection]:
    with get_pool().connection() as conn:
        yield conn


@contextmanager
def transaction() -> Iterator[Connection]:
    with get_pool().connection() as conn:
        with conn.transaction():
            yield conn


def fetch_all(sql: str, params: Sequence[Any] | dict | None = None, conn: Connection | None = None) -> list[dict]:
    if conn is not None:
        return conn.execute(sql, params).fetchall()
    with connection() as c:
        return c.execute(sql, params).fetchall()


def fetch_one(sql: str, params: Sequence[Any] | dict | None = None, conn: Connection | None = None) -> dict | None:
    if conn is not None:
        return conn.execute(sql, params).fetchone()
    with connection() as c:
        return c.execute(sql, params).fetchone()


def execute(sql: str, params: Sequence[Any] | dict | None = None, conn: Connection | None = None) -> int:
    if conn is not None:
        return conn.execute(sql, params).rowcount
    with connection() as c:
        return c.execute(sql, params).rowcount


def to_vector(values: Sequence[float]) -> str:
    """pgvector text format: '[0.1,0.2,...]' (cast with ::vector in SQL)."""
    return "[" + ",".join(f"{v:.7f}" for v in values) + "]"


def jsonb(value: Any) -> Jsonb | None:
    return None if value is None else Jsonb(value)


def ping_database() -> tuple[bool, str]:
    """Run a tiny query to prove the credentials and schema work."""
    try:
        fetch_one("select count(*) as n from public.textbooks")
        return True, "connected"
    except DatabaseNotConfigured as e:
        return False, str(e)
    except Exception as e:  # network error, wrong password, schema not run yet...
        return False, f"{type(e).__name__}: {e}"


def dumps(value: Any) -> str:
    return json.dumps(value, default=str)
