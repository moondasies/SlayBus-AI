"""Prepare a plain local Postgres (with pgvector) to behave like Supabase.

Usage:  python scripts/setup_local_db.py postgresql://user@localhost:5432/slaybus [--reset]

--reset drops all SLAYBUS tables first (DESTROYS DATA in that database).
Do NOT point this at your real Supabase project; there, run supabase/schema.sql
in the SQL editor instead.
"""

import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
STUBS = Path(__file__).with_name("supabase_stubs.sql")
SCHEMA = ROOT / "supabase" / "schema.sql"
RESET = """
drop table if exists public.questions, public.papers, public.chunks, public.chapters, public.textbooks,
  public.profiles cascade;
truncate auth.users cascade;
"""


def setup(url: str, reset: bool = False) -> None:
    if "supabase.co" in url or "supabase.com" in url:
        raise SystemExit("Refusing to run on a Supabase database. Use the SQL editor with supabase/schema.sql.")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("create extension if not exists vector")
        conn.execute(STUBS.read_text())
        if reset:
            conn.execute(RESET)
        conn.execute(SCHEMA.read_text())
        conn.execute("grant all on all tables in schema public to authenticated")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    setup(sys.argv[1], reset="--reset" in sys.argv)
    print("Local database ready.")
