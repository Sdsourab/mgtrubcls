from supabase import create_client, Client
from config import Config
import os

_supabase_client: Client = None
_supabase_admin_client: Client = None

def get_supabase() -> Client:
    """Returns the Supabase anon client (respects RLS)."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    return _supabase_client

def get_supabase_admin() -> Client:
    """Returns the Supabase service-role client (bypasses RLS). Admin use only."""
    global _supabase_admin_client
    if _supabase_admin_client is None:
        _supabase_admin_client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)
    return _supabase_admin_client

def get_supabase_with_token(token: str) -> Client:
    """Returns a Supabase client authenticated with a user JWT token."""
    client = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    client.postgrest.auth(token)
    return client
