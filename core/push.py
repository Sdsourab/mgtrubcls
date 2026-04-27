"""
core/push.py
────────────
Central Web Push notification sender (VAPID / pywebpush).

Environment variables required:
  VAPID_PRIVATE_KEY   — base64url-encoded EC private key
  VAPID_PUBLIC_KEY    — base64url-encoded EC public key (used by push-client.js)
  VAPID_CLAIMS_EMAIL  — e.g.  admin@rub.ac.bd

Install: pip install pywebpush

Three public helpers:
  push_to_batch(program, year, semester, title, body, ...)
      → sends to all subscribed users in that batch only

  push_to_all(title, body, ...)
      → sends to every subscribed user (admin / teacher central notice)

  push_to_user(user_id, title, body, ...)
      → sends to one specific user
"""

import os
import json
import logging

log = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────

def _private_key() -> str:
    return os.environ.get('VAPID_PRIVATE_KEY', '').strip()


def _claims() -> dict:
    email = os.environ.get('VAPID_CLAIMS_EMAIL', 'admin@rub.ac.bd').strip()
    return {'sub': 'mailto:' + email.removeprefix('mailto:')}


def _configured() -> bool:
    return bool(_private_key())


# ── Internal exception ────────────────────────────────────────

class _Gone(Exception):
    """410 / 404 → subscription is invalid; should be deleted."""
    pass


# ── Low-level single-subscription send ───────────────────────

def _send_one(sub_json, title: str, body: str,
               url: str, icon: str, badge: str,
               tag: str, notice_id: str) -> bool:
    """
    Send one Web Push notification.
    Raises _Gone if subscription is expired (410/404).
    Returns True on success, False on other failures.
    """
    try:
        from pywebpush import webpush
    except ImportError:
        log.error('[Push] pywebpush not installed — pip install pywebpush')
        return False

    if isinstance(sub_json, str):
        try:
            sub = json.loads(sub_json)
        except Exception:
            return False
    else:
        sub = sub_json

    if not sub or not sub.get('endpoint'):
        return False

    payload = json.dumps({
        'title':     title,
        'body':      body,
        'icon':      icon,
        'badge':     badge,
        'url':       url,
        'tag':       tag,
        'notice_id': notice_id,
    })

    try:
        webpush(
            subscription_info = sub,
            data              = payload,
            vapid_private_key = _private_key(),
            vapid_claims      = _claims(),
        )
        return True
    except Exception as e:
        msg = str(e)
        if '410' in msg or '404' in msg:
            raise _Gone(sub.get('endpoint', ''))
        log.warning(f'[Push] send failed: {e}')
        return False


# ── Batch-send helper ─────────────────────────────────────────

def _dispatch(subs: list, title: str, body: str, url: str,
              notice_id: str,
              icon  : str = '/static/icons/icon-192x192.png',
              badge : str = '/static/icons/badge-72x72.png',
              tag   : str = 'unisync') -> dict:
    """
    Send to a list of subscription rows from DB.
    Automatically deletes expired subscriptions (410/404).
    Returns {'sent': N, 'failed': N, 'removed': N}
    """
    from core.supabase_client import get_supabase_admin
    sb = get_supabase_admin()

    sent = failed = removed = 0

    for row in subs:
        try:
            ok = _send_one(
                sub_json  = row['subscription_json'],
                title     = title, body = body,
                url       = url,  icon = icon, badge = badge,
                tag       = tag,  notice_id = notice_id,
            )
            if ok:
                sent += 1
            else:
                failed += 1
        except _Gone:
            # Subscription expired — clean up DB
            try:
                sb.table('push_subscriptions').delete().eq('id', row['id']).execute()
                removed += 1
            except Exception:
                pass
        except Exception as e:
            log.debug(f'[Push] row error: {e}')
            failed += 1

    return {'sent': sent, 'failed': failed, 'removed': removed}


# ── Public API ────────────────────────────────────────────────

def push_to_batch(program: str, year: int, semester: int,
                  title: str, body: str,
                  url: str = '/notices/',
                  notice_id: str = '') -> dict:
    """
    Send push to all subscribed users in a specific batch.
    Used for batch-specific notices (e.g. BBA 2Y Sem 1).
    """
    if not _configured():
        log.debug('[Push] VAPID not configured — skipping push_to_batch')
        return {'sent': 0, 'failed': 0, 'removed': 0}

    from core.supabase_client import get_supabase_admin
    sb = get_supabase_admin()

    try:
        # Fetch user IDs in this batch
        profiles = sb.table('profiles') \
                     .select('id') \
                     .eq('program', program) \
                     .eq('course_year', year) \
                     .eq('course_semester', semester) \
                     .execute().data or []

        if not profiles:
            return {'sent': 0, 'failed': 0, 'removed': 0}

        user_ids = [p['id'] for p in profiles]

        # Fetch their subscriptions
        subs = sb.table('push_subscriptions') \
                 .select('id, subscription_json') \
                 .in_('user_id', user_ids) \
                 .execute().data or []

        result = _dispatch(subs, title, body, url, notice_id)
        log.info(f'[Push] batch {program} Y{year}S{semester}: {result}')
        return result

    except Exception as e:
        log.error(f'[Push] push_to_batch error: {e}')
        return {'sent': 0, 'failed': 0, 'removed': 0}


def push_to_all(title: str, body: str,
                url: str = '/notices/',
                notice_id: str = '') -> dict:
    """
    Send push to every subscribed user.
    Used when admin/teacher sends a central notice with no batch target.
    """
    if not _configured():
        log.debug('[Push] VAPID not configured — skipping push_to_all')
        return {'sent': 0, 'failed': 0, 'removed': 0}

    from core.supabase_client import get_supabase_admin
    sb = get_supabase_admin()

    try:
        subs = sb.table('push_subscriptions') \
                 .select('id, subscription_json') \
                 .execute().data or []

        result = _dispatch(subs, title, body, url, notice_id)
        log.info(f'[Push] broadcast to {len(subs)} subs: {result}')
        return result

    except Exception as e:
        log.error(f'[Push] push_to_all error: {e}')
        return {'sent': 0, 'failed': 0, 'removed': 0}


def push_to_user(user_id: str, title: str, body: str,
                 url: str = '/dashboard',
                 notice_id: str = '') -> bool:
    """Send push to all subscriptions of one specific user."""
    if not _configured() or not user_id:
        return False

    from core.supabase_client import get_supabase_admin
    sb = get_supabase_admin()

    try:
        subs = sb.table('push_subscriptions') \
                 .select('id, subscription_json') \
                 .eq('user_id', user_id) \
                 .execute().data or []

        result = _dispatch(subs, title, body, url, notice_id)
        return result['sent'] > 0

    except Exception as e:
        log.error(f'[Push] push_to_user error: {e}')
        return False