"""Supabase client for the agent.

The agent uses the SERVICE ROLE key, which skips Row Level Security, so every
query in the agent must filter by the logged-in teacher's user_id itself.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


class SupabaseNotConfigured(RuntimeError):
    pass


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise SupabaseNotConfigured("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in agent/.env")
    return create_client(s.supabase_url, s.supabase_service_role_key)


def ping_database() -> tuple[bool, str]:
    """Run a tiny query to prove the credentials and schema work."""
    try:
        get_supabase().table("textbooks").select("id").limit(1).execute()
        return True, "connected"
    except SupabaseNotConfigured as e:
        return False, str(e)
    except Exception as e:  # network error, wrong key, schema not run yet...
        return False, f"{type(e).__name__}: {e}"
