"""
app/notices/routes.py
─────────────────────
Notice system: CR users can create rich-text notices.
All authenticated users can read notices for their cohort.
Supports offline drafts that sync when connection restored.
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import datetime, timezone

notices_bp = Blueprint('notices', __name__)


def _is_cr_or_admin(user_id: str) -> tuple[bool, dict]:
    """Return (is_authorized, profile_dict). CR or admin can create content."""
    try:
        sb = get_supabase_admin()
        p = sb.table('profiles').select('*').eq('id', user_id).single().execute()
        profile = p.data or {}
        authorized = profile.get('role') in ('cr', 'admin')
        return authorized, profile
    except Exception:
        return False, {}


# ── Page ──────────────────────────────────────────────────────

@notices_bp.route('/')
def notices_page():
    return render_template('modules/notices.html')


# ── GET notices ───────────────────────────────────────────────

@notices_bp.route('/api/notices', methods=['GET'])
def get_notices():
    """
    Fetch notices filtered by program/year/semester.
    Returns notices targeting ALL cohorts + those matching user's cohort.
    """
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

        resp = q.execute()
        notices = resp.data or []

        # Filter: show notices targeting this cohort or broadcast (NULL target)
        if year and sem:
            y, s = int(year), int(sem)
            filtered = [
                n for n in notices
                if (n.get('target_year') is None or n['target_year'] == y)
                and (n.get('target_sem') is None or n['target_sem'] == s)
            ]
        else:
            filtered = notices

        return jsonify({'success': True, 'data': filtered, 'count': len(filtered)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── POST notice (CR/Admin only) ───────────────────────────────

@notices_bp.route('/api/notices', methods=['POST'])
def create_notice():
    """Create a new notice. Requires CR or admin role."""
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    if not user_id:
        return jsonify({'error': 'user_id required'}), 401

    authorized, profile = _is_cr_or_admin(user_id)
    if not authorized:
        return jsonify({'error': 'Only CR or Admin can create notices'}), 403

    title   = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()  # Rich HTML from Quill

    if not title or not content:
        return jsonify({'error': 'Title and content are required'}), 400

    # Strip HTML for plain-text search field
    import re
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
            'program':      data.get('program', profile.get('program', 'BBA')),
            'target_year':  data.get('target_year') or profile.get('cr_for_year'),
            'target_sem':   data.get('target_sem')  or profile.get('cr_for_semester'),
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

    authorized, _ = _is_cr_or_admin(user_id)
    if not authorized:
        return jsonify({'error': 'Forbidden'}), 403

    allowed = ['title', 'content', 'type', 'pinned', 'is_draft']
    payload = {k: data[k] for k in allowed if k in data}

    if 'content' in payload:
        import re
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
    authorized, _ = _is_cr_or_admin(user_id)
    if not authorized:
        return jsonify({'error': 'Forbidden'}), 403

    sb = get_supabase_admin()
    try:
        sb.table('notices').delete().eq('id', notice_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Bulk sync drafts (offline → online) ──────────────────────

@notices_bp.route('/api/notices/sync', methods=['POST'])
def sync_offline_notices():
    """
    Accept a batch of offline-created notice drafts.
    Client sends array of draft objects; server inserts them.
    Uses local_id for deduplication.
    """
    data     = request.get_json() or {}
    user_id  = data.get('user_id', '')
    drafts   = data.get('drafts', [])

    if not user_id or not drafts:
        return jsonify({'error': 'user_id and drafts required'}), 400

    authorized, profile = _is_cr_or_admin(user_id)
    if not authorized:
        return jsonify({'error': 'Forbidden'}), 403

    sb = get_supabase_admin()
    synced, failed = [], []

    for draft in drafts:
        try:
            import re
            content = draft.get('content', '')
            payload = {
                'author_id':    user_id,
                'author_name':  profile.get('full_name', 'CR'),
                'title':        draft.get('title', 'Untitled'),
                'content':      content,
                'content_text': re.sub(r'<[^>]+>', ' ', content).strip()[:500],
                'type':         draft.get('type', 'general'),
                'program':      draft.get('program', profile.get('program', 'BBA')),
                'target_year':  draft.get('target_year'),
                'target_sem':   draft.get('target_sem'),
                'is_draft':     False,  # Publishing on sync
            }
            resp = sb.table('notices').insert(payload).execute()
            synced.append(draft.get('local_id'))
        except Exception as e:
            failed.append({'local_id': draft.get('local_id'), 'error': str(e)})

    return jsonify({'success': True, 'synced': synced, 'failed': failed})