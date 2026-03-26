"""
core/supabase_client.py

Serverless-safe Supabase client.
- No module-level global singletons (avoids stale cache across warm Lambda reuse)
- Reads credentials from environment variables at call time
- Falls back to hardcoded keys so the app works even without Vercel env vars set
"""

import os
from supabase import create_client, Client

# ── Fallback credentials (used if Vercel env vars not configured) ─────────────
_FALLBACK_URL  = "https://akitkwaeotifdujkoykd.supabase.co"
_FALLBACK_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFraXRrd2Flb3RpZmR1amtveWtkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ0NDI1NjMsImV4cCI6MjA5MDAxODU2M30.TcIXK8pt01shOniRaAHKK8It1RJ3NyXSqB9RAEgBvC0"
_FALLBACK_SVC  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFraXRrd2Flb3RpZmR1amtveWtkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDQ0MjU2MywiZXhwIjoyMDkwMDE4NTYzfQ.7nrr4aDxKFR3CNwhOPEbeUY5XcEpeNguOU05Fk4-9w4"


def _get_credentials():
    """Read Supabase credentials fresh from environment (serverless-safe)."""
    url      = os.environ.get("SUPABASE_URL")      or _FALLBACK_URL
    anon_key = os.environ.get("SUPABASE_ANON_KEY")  or _FALLBACK_ANON
    svc_key  = os.environ.get("SUPABASE_SERVICE_KEY") or _FALLBACK_SVC
    return url, anon_key, svc_key


def get_supabase() -> Client:
    """Returns a Supabase anon client (respects RLS)."""
    url, anon_key, _ = _get_credentials()
    return create_client(url, anon_key)


def get_supabase_admin() -> Client:
    """Returns a Supabase service-role client (bypasses RLS). Admin use only."""
    url, _, svc_key = _get_credentials()
    return create_client(url, svc_key)


def get_supabase_with_token(token: str) -> Client:
    """Returns a Supabase client authenticated with a user JWT token."""
    url, anon_key, _ = _get_credentials()
    client = create_client(url, anon_key)
    client.postgrest.auth(token)
    return client