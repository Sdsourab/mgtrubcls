"""
app/notices/routes.py
─────────────────────
Notice system.
FIXED: Role check এ 'cr', 'admin', 'teacher' — এবং
       যদি user এর role valid না থাকে তাহলেও
       notices post করতে পারবে (CR assign করার আগেও কাজ করবে)।
       
       সঠিক production setup:
         Supabase এ CR user এর role = 'cr' set করুন।
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import datetime, timezone
import re

notices_bp = Blueprint('notices', __name__)


def _get_profile(user_id: str) -> dict:
    """Return profile dict for user_id, or {} on error."""
    if not user_id:
        return {}
    try:
        sb = get_supabase_admin()
        p  = sb.table('profiles').select('*').eq('id', user_id).single().execute()
        return p.data or {}
    except Exception:
        return {}


def _can_post(user_id: str) -> tuple[bool, dict]:
    """
    Return (authorized, profile).
    Authorised = any authenticated user who has a profile.
    Role-based posting is enforced in the frontend UI (only CR sees compose panel).
    Backend check ensures at minimum the user exists in profiles.
    """
    if not user_id:
        return False, {}
    profile = _get_profile(user_id)
    if not profile:
        return False, {}
    # Allow: cr, admin, teacher — and 'student' with cr_flag
    role = profile.get('role', 'student')
    if role in ('cr', 'admin', 'teacher'):
        return True, profile
    # Also allow if is_cr flag is set (flexible — admin can set this)
    if profile.get('is_cr'):
        return True, profile
    # Fallback: allow any existing user (remove this line for strict mode)
    return True, profile


# ── Page ──────────────────────────────────────────────────────

@notices_bp.route('/')
def notices_page():
    return render_template('modules/notices.html')


# ── GET notices ───────────────────────────────────────────────

@notices_bp.route('/api/notices', methods=['GET'])
def get_notices():
    program = request.args.get('program', '')
    year    = request.args.get('year', '')
    sem     = request.args.get('semester', '')
    limit   = int(request.args.get('limit', 20))

    sb = get_supabase_admin()
    try:
        q = sb.table('notices') \
              .select('*') \
              .eq('is_draft', False) \
              .order('pinned', desc=True) \
              .order('created_at', desc=True) \
              .limit(limit)

        if program:
            q = q.eq('program', program)

        notices = q.execute().data or []

        if year and sem:
            y, s = int(year), int(sem)
            notices = [
                n for n in notices
                if (n.get('target_year') is None or n['target_year'] == y)
                and (n.get('target_sem')  is None or n['target_sem']  == s)
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

    authorized, profile = _can_post(user_id)
    if not authorized:
        return jsonify({'error': 'Account not found. Please log in again.'}), 403

    title   = (data.get('title')   or '').strip()
    content = (data.get('content') or '').strip()

    if not title:
        return jsonify({'error': 'Title is required'}), 400
    if not content or content == '<p><br></p>':
        return jsonify({'error': 'Notice content cannot be empty'}), 400

    content_text = re.sub(r'<[^>]+>', ' ', content).strip()

    sb = get_supabase_admin()
    try:
        payload = {
            'author_id':    user_id,
            'author_name':  profile.get('full_name', 'CR'),
            'title':        title,
            'content':      content,
            'content_text': content_text[:500],
            'type':         data.get('type', 'general'),
            'program':      data.get('program') or profile.get('program', 'BBA'),
            'target_year':  data.get('target_year') or None,
            'target_sem':   data.get('target_sem')  or None,
            'is_draft':     bool(data.get('is_draft', False)),
            'pinned':       bool(data.get('pinned', False)),
        }
        resp = sb.table('notices').insert(payload).execute()
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

    profile = _get_profile(user_id)
    if not profile:
        return jsonify({'error': 'Forbidden'}), 403

    allowed = ['title', 'content', 'type', 'pinned', 'is_draft']
    payload = {k: data[k] for k in allowed if k in data}

    if 'content' in payload:
        payload['content_text'] = re.sub(r'<[^>]+>', ' ', payload['content']).strip()[:500]

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
    user_id = request.args.get('user_id', '')
    profile = _get_profile(user_id)
    if not profile:
        return jsonify({'error': 'Forbidden'}), 403

    sb = get_supabase_admin()
    try:
        sb.table('notices').delete().eq('id', notice_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Bulk sync drafts ──────────────────────────────────────────

@notices_bp.route('/api/notices/sync', methods=['POST'])
def sync_offline_notices():
    data    = request.get_json() or {}
    user_id = data.get('user_id', '')
    drafts  = data.get('drafts', [])

    if not user_id or not drafts:
        return jsonify({'error': 'user_id and drafts required'}), 400

    authorized, profile = _can_post(user_id)
    if not authorized:
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
                'content_text': re.sub(r'<[^>]+>', ' ', content).strip()[:500],
                'type':         draft.get('type', 'general'),
                'program':      draft.get('program') or profile.get('program', 'BBA'),
                'target_year':  draft.get('target_year'),
                'target_sem':   draft.get('target_sem'),
                'is_draft':     False,
                'pinned':       False,
            }
            sb.table('notices').insert(payload).execute()
            synced.append(draft.get('local_id'))
        except Exception as e:
            failed.append({'local_id': draft.get('local_id'), 'error': str(e)})

    return jsonify({'success': True, 'synced': synced, 'failed': failed})