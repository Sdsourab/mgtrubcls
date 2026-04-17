"""
core/push.py
────────────
Central Web Push notification sender.

Uses pywebpush library (VAPID protocol).
VAPID keys must be set as environment variables:
  VAPID_PRIVATE_KEY  — base64url-encoded private key
  VAPID_PUBLIC_KEY   — base64url-encoded public key
  VAPID_CLAIMS_EMAIL — mailto: claim (e.g. admin@unisync.edu.bd)

Install: pip install pywebpush
"""

import os
import json
import logging
from typing import Optional

log = logging.getLogger(__name__)


# ── VAPID config from environment ─────────────────────────────

def _vapid_private_key() -> str:
    return os.environ.get('VAPID_PRIVATE_KEY', '').strip()


def _vapid_claims() -> dict:
    email = os.environ.get('VAPID_CLAIMS_EMAIL', 'mailto:admin@unisync.edu.bd').strip()
    if not email.startswith('mailto:'):
        email = 'mailto:' + email
    return {'sub': email}


def _is_configured() -> bool:
    return bool(_vapid_private_key())


# ── Send a single push notification ───────────────────────────

def send_push(subscription_json, title: str, body: str,
              url: str = '/notices/', icon: str = '/static/icons/icon-192x192.png',
              badge: str = '/static/icons/badge-72x72.png',
              tag: str = 'unisync') -> bool:
    """
    Send a Web Push notification to a single subscription.

    subscription_json: dict or JSON string from browser PushSubscription.toJSON()
    Returns True on success, False on failure.
    """
    if not _is_configured():
        log.warning('[Push] VAPID_PRIVATE_KEY not set — skipping push')
        return False

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        log.error('[Push] pywebpush not installed. Run: pip install pywebpush')
        return False

    # Normalise subscription
    if isinstance(subscription_json, str):
        try:
            sub = json.loads(subscription_json)
        except Exception:
            return False
    else:
        sub = subscription_json

    if not sub or not sub.get('endpoint'):
        return False

    payload = json.dumps({
        'title':  title,
        'body':   body,
        'icon':   icon,
        'badge':  badge,
        'url':    url,
        'tag':    tag,
    })

    try:
        webpush(
            subscription_info  = sub,
            data               = payload,
            vapid_private_key  = _vapid_private_key(),
            vapid_claims       = _vapid_claims(),
        )
        return True
    except Exception as e:
        msg = str(e)
        # 410 Gone = subscription expired — caller should delete it
        if '410' in msg or '404' in msg:
            raise _SubscriptionGone(str(sub.get('endpoint', '')))
        log.warning(f'[Push] send failed: {e}')
        return False


class _SubscriptionGone(Exception):
    """Raised when a subscription returns 410/404 (expired)."""
    pass


# ── Send to all users in a batch ──────────────────────────────

def push_to_batch(program: str, year: int, semester: int,
                  title: str, body: str, url: str = '/notices/') -> dict:
    """
    Send push notifications to all subscribed users in a batch.
    Returns {'sent': N, 'failed': N, 'removed': N}
    """
    if not _is_configured():
        return {'sent': 0, 'failed': 0, 'removed': 0, 'reason': 'VAPID not configured'}

    from core.supabase_client import get_supabase_admin
    sb = get_supabase_admin()

    sent = failed = removed = 0

    try:
        # Get all user IDs in this batch
        profiles = sb.table('profiles') \
                     .select('id') \
                     .eq('program', program) \
                     .eq('year', year) \
                     .eq('semester', semester) \
                     .execute().data or []

        if not profiles:
            return {'sent': 0, 'failed': 0, 'removed': 0}

        user_ids = [p['id'] for p in profiles]

        # Fetch their push subscriptions
        subs = sb.table('push_subscriptions') \
                 .select('id, user_id, subscription_json') \
                 .in_('user_id', user_ids) \
                 .execute().data or []

        for row in subs:
            try:
                ok = send_push(
                    subscription_json = row['subscription_json'],
                    title = title,
                    body  = body,
                    url   = url,
                )
                if ok:
                    sent += 1
                else:
                    failed += 1
            except _SubscriptionGone:
                # Subscription expired — remove from DB
                try:
                    sb.table('push_subscriptions') \
                      .delete().eq('id', row['id']).execute()
                    removed += 1
                except Exception:
                    pass
            except Exception:
                failed += 1

    except Exception as e:
        log.error(f'[Push] push_to_batch error: {e}')

    log.info(f'[Push] batch {program} Y{year}S{semester}: sent={sent} failed={failed} removed={removed}')
    return {'sent': sent, 'failed': failed, 'removed': removed}


# ── Send to a single user ─────────────────────────────────────

def push_to_user(user_id: str, title: str, body: str,
                 url: str = '/dashboard') -> bool:
    """Send push to all subscriptions of a single user."""
    if not _is_configured() or not user_id:
        return False

    from core.supabase_client import get_supabase_admin
    sb = get_supabase_admin()

    try:
        subs = sb.table('push_subscriptions') \
                 .select('id, subscription_json') \
                 .eq('user_id', user_id) \
                 .execute().data or []

        sent = False
        for row in subs:
            try:
                ok = send_push(row['subscription_json'], title, body, url)
                if ok:
                    sent = True
            except _SubscriptionGone:
                try:
                    sb.table('push_subscriptions').delete().eq('id', row['id']).execute()
                except Exception:
                    pass
        return sent
    except Exception as e:
        log.error(f'[Push] push_to_user error: {e}')
        return False