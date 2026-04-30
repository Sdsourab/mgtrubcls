"""
core/push.py
────────────
Web Push sender using pywebpush + VAPID.

env vars needed:
  VAPID_PRIVATE_KEY   — base64url EC private key
  VAPID_CLAIMS_EMAIL  — e.g. admin@rub.ac.bd

pip install pywebpush
"""
import os, json, logging
log = logging.getLogger(__name__)

class _Gone(Exception): pass

def _key():   return os.environ.get('VAPID_PRIVATE_KEY', '').strip()
def _ok():    return bool(_key())
def _claims():
    e = os.environ.get('VAPID_CLAIMS_EMAIL', 'admin@rub.ac.bd').strip()
    return {'sub': 'mailto:' + e.removeprefix('mailto:')}

def _one(sub_json, title, body,
         url   = '/notices/',
         icon  = '/static/icons/icon-192x192.png',
         badge = '/static/icons/badge-72x72.png',
         tag   = 'unisync',
         nid   = '') -> bool:
    try: from pywebpush import webpush
    except ImportError:
        log.error('[Push] pywebpush not installed'); return False

    sub = json.loads(sub_json) if isinstance(sub_json, str) else sub_json
    if not sub or not sub.get('endpoint'): return False

    try:
        webpush(
            subscription_info = sub,
            data = json.dumps({'title':title,'body':body,'icon':icon,
                               'badge':badge,'url':url,'tag':tag,'notice_id':nid}),
            vapid_private_key = _key(),
            vapid_claims      = _claims(),
        )
        return True
    except Exception as e:
        if '410' in str(e) or '404' in str(e): raise _Gone()
        log.debug(f'[Push] {e}'); return False

def _dispatch(subs, title, body, url, nid):
    from core.supabase_client import get_supabase_admin
    sb = get_supabase_admin()
    sent = failed = removed = 0
    for row in subs:
        try:
            if _one(row['subscription_json'], title, body, url=url, nid=nid):
                sent += 1
            else:
                failed += 1
        except _Gone:
            try: sb.table('push_subscriptions').delete().eq('id', row['id']).execute()
            except: pass
            removed += 1
        except Exception as e:
            log.debug(f'[Push] row err: {e}'); failed += 1
    return {'sent': sent, 'failed': failed, 'removed': removed}

# ── Public helpers ─────────────────────────────────────────────

def push_to_batch(program, year, semester, title, body,
                  url='/notices/', notice_id=''):
    """Push to all users in one batch (program + year + semester)."""
    if not _ok(): return {'sent':0,'failed':0,'removed':0}
    from core.supabase_client import get_supabase_admin
    sb = get_supabase_admin()
    try:
        pids = [p['id'] for p in
                sb.table('profiles').select('id')
                  .eq('program', program).eq('year', year).eq('semester', semester)
                  .execute().data or []]
        if not pids: return {'sent':0,'failed':0,'removed':0}
        subs = sb.table('push_subscriptions').select('id,subscription_json') \
                 .in_('user_id', pids).execute().data or []
        r = _dispatch(subs, title, body, url, notice_id)
        log.info(f'[Push] batch {program}Y{year}S{semester}: {r}'); return r
    except Exception as e:
        log.error(f'[Push] push_to_batch: {e}')
        return {'sent':0,'failed':0,'removed':0}

def push_to_all(title, body, url='/notices/', notice_id=''):
    """Push to every subscribed user (central/admin notices)."""
    if not _ok(): return {'sent':0,'failed':0,'removed':0}
    from core.supabase_client import get_supabase_admin
    sb = get_supabase_admin()
    try:
        subs = sb.table('push_subscriptions').select('id,subscription_json').execute().data or []
        r = _dispatch(subs, title, body, url, notice_id)
        log.info(f'[Push] broadcast {len(subs)} subs: {r}'); return r
    except Exception as e:
        log.error(f'[Push] push_to_all: {e}')
        return {'sent':0,'failed':0,'removed':0}

def push_to_user(user_id, title, body, url='/dashboard', notice_id=''):
    """Push to one specific user."""
    if not _ok() or not user_id: return False
    from core.supabase_client import get_supabase_admin
    sb = get_supabase_admin()
    try:
        subs = sb.table('push_subscriptions').select('id,subscription_json') \
                 .eq('user_id', user_id).execute().data or []
        return _dispatch(subs, title, body, url, notice_id)['sent'] > 0
    except Exception as e:
        log.error(f'[Push] push_to_user: {e}'); return False