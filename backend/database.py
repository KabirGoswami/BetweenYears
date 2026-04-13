"""
Supabase client factory — two clients:
  • anon_client  : used for user-scoped operations (RLS enforced via user JWT)
  • admin_client : uses service role key, bypasses RLS — use carefully
"""
from functools import lru_cache
from supabase import create_client, Client
from config import get_settings

settings = get_settings()


@lru_cache
def get_anon_client() -> Client:
    """Returns the anon-key Supabase client (RLS enforced)."""
    return create_client(settings.supabase_url, settings.supabase_anon_key)


@lru_cache
def get_admin_client() -> Client:
    """Returns the service-role Supabase client (bypasses RLS).
    Only use server-side for admin operations like batch jobs and GDPR exports.
    """
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_authed_client(access_token: str) -> Client:
    """Returns an anon client with the user's JWT injected — RLS enforced per user."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client
