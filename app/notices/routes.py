"""
app/notices/routes.py
─────────────────────
Notice system with instant Web Push on creation.

PUSH LOGIC:
  • Notice created with target_year + target_sem + program
      → push_to_batch(program, year, sem)   — only that batch
  • Notice created with NO batch target (admin/teacher central)
      → push_to_all()                       — every subscribed user
  • Push failures NEVER prevent notice from being saved.
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import datetime, timezone
import logging
import re

log = logging.getLogger(__name__)
notices_bp = Blueprint('notices', __name__)

# ── Helpers ───────────────────────────────────────────────────

def _get_profile(user_id: str) -> dict:
    if not user_id:
        return {}
    try:
        return get_supabase_admin() \
               .table('profiles').select('*') \
               .eq('id', user_id).single().execute().data or {}
    except Exception:
        return {}


def _strip_html(html: str) -> str:
    return re.sub(r'<[^>]+>', ' ', html or '').strip()


def _fire_push(notice: dict) -> None:
    """
    Send Web Push immediately after notice is saved.
    Batch-aware: matches target_year / target_sem / program.
    Central notice (no target) → all users.
    Silent on any error.
    """
    try:
        from core.push import push_to_batch, push_to_all

        EMOJI = {
            'general':  '📢',
            'exam':     '📝',
            'class':    '📅',
            'resource': '📁',
            'urgent':   '🚨',
            'result':   '🏆',
        }

        notice_id   = str(notice.get('id', ''))
        ntype       = notice.get('type', 'general')
        emoji       = EMOJI.get(ntype, '📢')
        push_title  = f"{emoji} {notice.get('title', 'New Notice')}"
        push_body   = (notice.get('content_text') or 'Tap to view')[:120]
        push_url    = f"/notices/?highlight={notice_id}"
        program     = notice.get('program', '')
        target_year = notice.get('target_year')
        target_sem  = notice.get('target_sem')

        # Batch-specific notice
        if target_year and target_sem and program:
            push_to_batch(
                program   = program,
                year      = int(target_year),
                semester  = int(target_sem),
                title     = push_title,
                body      = push_body,
                url       = push_url,
                notice_id = notice_id,
            )
        else:
            # Central — send to all
            push_to_all(
                title     = push_title,
                body      = push_body,
                url       = push_url,
                notice_id = notice_id,
            )

    except Exception as e:
        log.warning(f'[Notices] push error (non-fatal): {e}')


# ── Pages ─────────────────────────────────────────────────────

@notices_bp.route('/')
def notices_page():
    return render_template('modules/notices.html')


# ── GET notices ───────────────────────────────────────────────

@notices_bp.route('/api/notices', methods=['GET'])
def get_notices():
    """
    Fetch notices for a user's batch.
    Rules:
      • notice.target_year is NULL  → everyone sees it (central)
      • notice.target_sem  is NULL  → everyone sees it
      • otherwise must match program + year + semester query params
    """
    program = request.args.get('program', '').strip()
    year    = request.args.get('year', '').strip()
    sem     = request.args.get('semester', '').strip()
    limit   = min(int(request.args.get('limit', 20)), 50)

    sb = get_supabase_admin()
    try:
        q = sb.table('notices') \
              .select('*') \
              .eq('is_draft', False) \
              .order('pinned',     desc=True) \
              .order('created_at', desc=True) \
              .limit(limit)

        if program:
            q = q.eq('program', program)

        notices = q.execute().data or []

        # Client-side batch filter
        if year and sem:
            y, s = int(year), int(sem)
            notices = [
                n for n in notices
                if (not n.get('target_year') or n['target_year'] == y)
                and (not n.get('target_sem')  or n['target_sem']  == s)
            ]

        return jsonify({'success': True, 'data': notices, 'count': len(notices)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── POST notice ───────────────────────────────────────────────

@notices_bp.route('/api/notices', methods=['POST'])
def create_notice():
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    if not user_id:
        return jsonify({'error': 'user_id required'}), 401

    profile = _get_profile(user_id)
    if not profile:
        return jsonify({'error': 'Account not found. Please log in again.'}), 403

    title   = (data.get('title')   or '').strip()
    content = (data.get('content') or '').strip()

    if not title:
        return jsonify({'error': 'Title is required'}), 400
    if not content or content in ('<p><br></p>', '<p></p>'):
        return jsonify({'error': 'Notice content cannot be empty'}), 400

    sb = get_supabase_admin()
    try:
        payload = {
            'author_id':    user_id,
            'author_name':  profile.get('full_name', 'CR'),
            'title':        title,
            'content':      content,
            'content_text': _strip_html(content)[:500],
            'type':         data.get('type', 'general'),
            'program':      data.get('program') or profile.get('program', 'BBA'),
            'target_year':  data.get('target_year') or None,
            'target_sem':   data.get('target_sem')  or None,
            'is_draft':     bool(data.get('is_draft', False)),
            'pinned':       bool(data.get('pinned', False)),
        }

        resp  = sb.table('notices').insert(payload).execute()
        saved = resp.data[0] if resp.data else payload

        # ── Fire push immediately (non-blocking) ──────────────
        if not payload['is_draft']:
            _fire_push(saved)

        return jsonify({'success': True, 'data': resp.data}), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── PATCH notice ──────────────────────────────────────────────

@notices_bp.route('/api/notices/<notice_id>', methods=['PATCH'])
def update_notice(notice_id):
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    if not user_id:
        return jsonify({'error': 'user_id required'}), 401
    if not _get_profile(user_id):
        return jsonify({'error': 'Forbidden'}), 403

    allowed = ['title', 'content', 'type', 'pinned', 'is_draft']
    payload = {k: data[k] for k in allowed if k in data}

    if 'content' in payload:
        payload['content_text'] = _strip_html(payload['content'])[:500]

    payload['updated_at'] = datetime.now(timezone.utc).isoformat()

    sb = get_supabase_admin()
    try:
        resp = sb.table('notices').update(payload).eq('id', notice_id).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── DELETE notice ─────────────────────────────────────────────

@notices_bp.route('/api/notices/<notice_id>', methods=['DELETE'])
def delete_notice(notice_id):
    user_id = request.args.get('user_id', '').strip()
    if not _get_profile(user_id):
        return jsonify({'error': 'Forbidden'}), 403

    sb = get_supabase_admin()
    try:
        sb.table('notices').delete().eq('id', notice_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Offline sync — bulk upload drafts ────────────────────────

@notices_bp.route('/api/notices/sync', methods=['POST'])
def sync_offline_notices():
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    drafts  = data.get('drafts', [])

    if not user_id or not drafts:
        return jsonify({'error': 'user_id and drafts required'}), 400

    profile = _get_profile(user_id)
    if not profile:
        return jsonify({'error': 'Forbidden'}), 403

    sb = get_supabase_admin()
    synced, failed = [], []

    for draft in drafts:
        try:
            content = draft.get('content', '')
            payload = {
                'author_id':    user_id,
                'author_name':  profile.get('full_name', 'CR'),
                'title':        draft.get('title', 'Untitled'),
                'content':      content,
                'content_text': _strip_html(content)[:500],
                'type':         draft.get('type', 'general'),
                'program':      draft.get('program') or profile.get('program', 'BBA'),
                'target_year':  draft.get('target_year'),
                'target_sem':   draft.get('target_sem'),
                'is_draft':     False,
                'pinned':       False,
            }
            resp = sb.table('notices').insert(payload).execute()
            saved = resp.data[0] if resp.data else payload
            _fire_push(saved)
            synced.append(draft.get('local_id'))
        except Exception as e:
            failed.append({'local_id': draft.get('local_id'), 'error': str(e)})

    return jsonify({'success': True, 'synced': synced, 'failed': failed})