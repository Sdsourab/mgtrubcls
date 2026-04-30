"""
app/notices/routes.py
─────────────────────
FIXED:
  1. Central notices (program=NULL, target_year=NULL) now correctly
     visible to every user — DB filter was excluding them before.
  2. _fire_push() called immediately after notice is saved.
  3. Batch-specific notice → push_to_batch()
     Central notice (no target) → push_to_all()
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import datetime, timezone
import logging, re

log = logging.getLogger(__name__)
notices_bp = Blueprint('notices', __name__)


def _get_profile(user_id: str) -> dict:
    if not user_id:
        return {}
    try:
        r = get_supabase_admin() \
              .table('profiles').select('*') \
              .eq('id', user_id).single().execute()
        return r.data or {}
    except Exception:
        return {}


def _strip_html(html: str) -> str:
    return re.sub(r'<[^>]+>', ' ', html or '').strip()


def _fire_push(notice: dict) -> None:
    """Non-blocking push after save. Errors are silent."""
    try:
        from core.push import push_to_batch, push_to_all

        EMOJI = {'general':'📢','exam':'📝','class':'📅',
                 'resource':'📁','urgent':'🚨','result':'🏆'}
        nid     = str(notice.get('id', ''))
        emoji   = EMOJI.get(notice.get('type', 'general'), '📢')
        title   = f"{emoji} {notice.get('title', 'New Notice')}"
        body    = (notice.get('content_text') or 'Tap to view')[:120]
        url     = f"/notices/?highlight={nid}"
        program = notice.get('program', '')
        tyear   = notice.get('target_year')
        tsem    = notice.get('target_sem')

        if tyear and tsem and program:
            push_to_batch(program=program, year=int(tyear), semester=int(tsem),
                          title=title, body=body, url=url, notice_id=nid)
        else:
            push_to_all(title=title, body=body, url=url, notice_id=nid)
    except Exception as e:
        log.warning(f'[Notices] push non-fatal: {e}')


# ── Page ──────────────────────────────────────────────────────

@notices_bp.route('/')
def notices_page():
    return render_template('modules/notices.html')


# ── GET notices ───────────────────────────────────────────────

@notices_bp.route('/api/notices', methods=['GET'])
def get_notices():
    """
    Returns notices for a user's batch.

    FIXED LOGIC:
      A notice is visible if:
        • notice.program IS NULL  (central — all programs see it)
        • OR notice.program = user's program
      AND:
        • notice.target_year IS NULL  (central — all years see it)
        • OR notice.target_year = user's year
      AND:
        • notice.target_sem IS NULL   (central — all sems see it)
        • OR notice.target_sem = user's semester
    """
    program = request.args.get('program',  '').strip()
    year    = request.args.get('year',     '').strip()
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

        # ── FIXED: fetch both central + batch-specific notices ──
        # Do NOT filter by program at DB level (would exclude program=NULL)
        # Filter in Python instead.
        # If no program provided, return everything.
        notices = q.execute().data or []

        # Python-level batch filter
        if program or year or sem:
            filtered = []
            y = int(year) if year else None
            s = int(sem)  if sem  else None
            for n in notices:
                n_prog  = n.get('program')
                n_year  = n.get('target_year')
                n_sem   = n.get('target_sem')

                prog_ok  = (not n_prog)  or (not program) or (n_prog  == program)
                year_ok  = (n_year is None) or (y is None) or (n_year == y)
                sem_ok   = (n_sem  is None) or (s is None) or (n_sem  == s)

                if prog_ok and year_ok and sem_ok:
                    filtered.append(n)
            notices = filtered

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
        return jsonify({'error': 'Account not found.'}), 403

    title   = (data.get('title')   or '').strip()
    content = (data.get('content') or '').strip()
    if not title:
        return jsonify({'error': 'Title required'}), 400
    if not content or content in ('<p><br></p>', '<p></p>'):
        return jsonify({'error': 'Content cannot be empty'}), 400

    sb = get_supabase_admin()
    try:
        payload = {
            'author_id':    user_id,
            'author_name':  profile.get('full_name', 'CR'),
            'title':        title,
            'content':      content,
            'content_text': _strip_html(content)[:500],
            'type':         data.get('type', 'general'),
            'program':      data.get('program') or None,   # None = central (all programs)
            'target_year':  data.get('target_year') or None,
            'target_sem':   data.get('target_sem')  or None,
            'is_draft':     bool(data.get('is_draft', False)),
            'pinned':       bool(data.get('pinned',   False)),
        }
        resp  = sb.table('notices').insert(payload).execute()
        saved = resp.data[0] if resp.data else payload

        # ── Push immediately ─────────────────────────────────
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
    if not user_id or not _get_profile(user_id):
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
    if not user_id or not _get_profile(user_id):
        return jsonify({'error': 'Forbidden'}), 403
    sb = get_supabase_admin()
    try:
        sb.table('notices').delete().eq('id', notice_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Offline sync ──────────────────────────────────────────────

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
                'program':      draft.get('program') or None,
                'target_year':  draft.get('target_year'),
                'target_sem':   draft.get('target_sem'),
                'is_draft':     False,
                'pinned':       False,
            }
            resp  = sb.table('notices').insert(payload).execute()
            saved = resp.data[0] if resp.data else payload
            _fire_push(saved)
            synced.append(draft.get('local_id'))
        except Exception as e:
            failed.append({'local_id': draft.get('local_id'), 'error': str(e)})

    return jsonify({'success': True, 'synced': synced, 'failed': failed})