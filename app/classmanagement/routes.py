"""
app/classmanagement/routes.py
──────────────────────────────
CR-only: Cancel existing classes, add extra classes.
Changes broadcast to all students in the same cohort via auto-notice.
Offline sync endpoint handles both 'cancel' and 'extra' action types.
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import date as _date

classmanagement_bp = Blueprint('classmanagement', __name__)


def _require_cr(user_id: str):
    """Return profile dict if CR/admin, else None."""
    if not user_id:
        return None
    try:
        sb = get_supabase_admin()
        p  = sb.table('profiles').select('*').eq('id', user_id).single().execute()
        profile = p.data or {}
        return profile if profile.get('role') in ('cr', 'admin') else None
    except Exception:
        return None


def _resolve_course_name(sb, course_code: str) -> str:
    """Lookup full course name from mappings table."""
    try:
        m = sb.table('mappings').select('full_name').eq('code', course_code).execute()
        return m.data[0]['full_name'] if m.data else course_code
    except Exception:
        return course_code


def _publish_notice(sb, user_id: str, profile: dict, title: str, content: str,
                    content_text: str, notice_type: str, program: str,
                    year: int, semester: int):
    """Create an auto-notice for a class change. Non-fatal on failure."""
    try:
        sb.table('notices').insert({
            'author_id':    user_id,
            'author_name':  profile.get('full_name', 'CR'),
            'title':        title,
            'content':      content,
            'content_text': content_text,
            'type':         notice_type,
            'program':      program,
            'target_year':  year,
            'target_sem':   semester,
            'is_draft':     False,
            'pinned':       False,
        }).execute()
    except Exception:
        pass


# ── Page ──────────────────────────────────────────────────────

@classmanagement_bp.route('/')
def management_page():
    return render_template('modules/class_management.html')


# ── GET: fetch class changes ───────────────────────────────────

@classmanagement_bp.route('/api/class-changes', methods=['GET'])
def get_class_changes():
    """Fetch changes (cancels + extras) for a cohort in a date range."""
    program = request.args.get('program', 'BBA')
    year    = request.args.get('year')
    sem     = request.args.get('semester')
    from_dt = request.args.get('from', _date.today().isoformat())
    to_dt   = request.args.get('to')

    sb = get_supabase_admin()
    try:
        q = sb.table('class_changes').select('*') \
              .eq('program', program) \
              .gte('change_date', from_dt) \
              .order('change_date')
        if year:
            q = q.eq('target_year', int(year))
        if sem:
            q = q.eq('target_semester', int(sem))
        if to_dt:
            q = q.lte('change_date', to_dt)

        rows = q.execute().data or []

        # Enrich with full course/teacher names
        try:
            mapping = {r['code']: r['full_name']
                       for r in (sb.table('mappings').select('code,full_name').execute().data or [])}
            for row in rows:
                row['course_name']  = mapping.get(row.get('course_code', ''), row.get('course_code', ''))
                row['teacher_name'] = mapping.get(row.get('teacher_code', ''), row.get('teacher_code', ''))
        except Exception:
            pass

        return jsonify({'success': True, 'data': rows})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── IMPORTANT: static sub-paths BEFORE /<change_id> ──────────

@classmanagement_bp.route('/api/class-changes/cancel', methods=['POST'])
def cancel_class():
    """CR cancels a class on a specific date. Auto-publishes a notice."""
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    profile = _require_cr(user_id)
    if not profile:
        return jsonify({'error': 'Only CR or Admin can cancel classes'}), 403

    course_code = data.get('course_code', '').strip()
    change_date = data.get('change_date', '').strip()
    if not course_code or not change_date:
        return jsonify({'error': 'course_code and change_date are required'}), 400

    sb          = get_supabase_admin()
    course_name = _resolve_course_name(sb, course_code)
    program     = data.get('program', profile.get('program', 'BBA'))
    year        = int(data.get('year', profile.get('cr_for_year') or profile.get('year', 1)))
    semester    = int(data.get('semester', profile.get('cr_for_semester') or profile.get('semester', 1)))
    reason      = data.get('reason', '')

    try:
        payload = {
            'type':            'cancel',
            'course_code':     course_code,
            'teacher_code':    data.get('teacher_code', ''),
            'program':         program,
            'target_year':     year,
            'target_semester': semester,
            'change_date':     change_date,
            'reason':          reason,
            'created_by':      user_id,
            'created_by_name': profile.get('full_name', 'CR'),
        }
        resp = sb.table('class_changes').insert(payload).execute()

        reason_html = f'<p>Reason: {reason}</p>' if reason else ''
        _publish_notice(
            sb, user_id, profile,
            title        = f'Class Cancelled: {course_name} — {change_date}',
            content      = (f'<p><strong>{course_name}</strong> class on <strong>{change_date}</strong> '
                            f'has been <strong style="color:#e53e3e">cancelled</strong>.</p>'
                            f'{reason_html}'
                            f'<p><em>— {profile.get("full_name", "CR")}</em></p>'),
            content_text = f'{course_name} class cancelled on {change_date}. {reason}',
            notice_type  = 'class_cancel',
            program      = program, year=year, semester=semester,
        )
        return jsonify({'success': True, 'data': resp.data}), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@classmanagement_bp.route('/api/class-changes/extra', methods=['POST'])
def add_extra_class():
    """CR schedules an extra class. Auto-publishes a notice."""
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    profile = _require_cr(user_id)
    if not profile:
        return jsonify({'error': 'Only CR or Admin can add extra classes'}), 403

    missing = [f for f in ('course_code', 'change_date', 'time_start', 'time_end') if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing: {", ".join(missing)}'}), 400

    sb          = get_supabase_admin()
    course_code = data['course_code']
    course_name = _resolve_course_name(sb, course_code)
    program     = data.get('program', profile.get('program', 'BBA'))
    year        = int(data.get('year', profile.get('cr_for_year') or profile.get('year', 1)))
    semester    = int(data.get('semester', profile.get('cr_for_semester') or profile.get('semester', 1)))
    reason      = data.get('reason', '')

    try:
        payload = {
            'type':            'extra',
            'course_code':     course_code,
            'teacher_code':    data.get('teacher_code', ''),
            'program':         program,
            'target_year':     year,
            'target_semester': semester,
            'change_date':     data['change_date'],
            'time_start':      data['time_start'],
            'time_end':        data['time_end'],
            'room_no':         data.get('room_no', 'TBD'),
            'reason':          reason,
            'created_by':      user_id,
            'created_by_name': profile.get('full_name', 'CR'),
        }
        resp = sb.table('class_changes').insert(payload).execute()

        note_html = f'<p>Note: {reason}</p>' if reason else ''
        _publish_notice(
            sb, user_id, profile,
            title        = f'Extra Class: {course_name} — {data["change_date"]}',
            content      = (f'<p>An <strong style="color:#38a169">extra class</strong> for '
                            f'<strong>{course_name}</strong> has been scheduled.</p>'
                            f'<p>📅 <strong>Date:</strong> {data["change_date"]}<br>'
                            f'⏰ <strong>Time:</strong> {data["time_start"]} – {data["time_end"]}<br>'
                            f'🏛️ <strong>Room:</strong> {data.get("room_no", "TBD")}</p>'
                            f'{note_html}'),
            content_text = (f'Extra class {course_name} on {data["change_date"]} '
                            f'{data["time_start"]}–{data["time_end"]}'),
            notice_type  = 'extra_class',
            program      = program, year=year, semester=semester,
        )
        return jsonify({'success': True, 'data': resp.data}), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@classmanagement_bp.route('/api/class-changes/sync', methods=['POST'])
def sync_offline_changes():
    """
    Batch sync of offline-queued class changes (both 'cancel' and 'extra').
    Called by offline-sync.js when connection is restored.
    """
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    actions = data.get('actions', [])

    profile = _require_cr(user_id)
    if not profile:
        return jsonify({'error': 'Forbidden'}), 403

    if not actions:
        return jsonify({'success': True, 'synced': [], 'failed': []})

    sb = get_supabase_admin()
    synced, failed = [], []

    for action in actions:
        local_id    = action.get('local_id')
        action_type = action.get('type', 'cancel')
        try:
            course_code = action.get('course_code', '')
            course_name = _resolve_course_name(sb, course_code)
            program     = action.get('program', profile.get('program', 'BBA'))
            year        = int(action.get('year', profile.get('year', 1)))
            semester    = int(action.get('semester', profile.get('semester', 1)))

            payload = {
                'type':            action_type,
                'course_code':     course_code,
                'teacher_code':    action.get('teacher_code', ''),
                'program':         program,
                'target_year':     year,
                'target_semester': semester,
                'change_date':     action.get('change_date', ''),
                'reason':          action.get('reason', ''),
                'created_by':      user_id,
                'created_by_name': profile.get('full_name', 'CR'),
            }

            if action_type == 'extra':
                payload['time_start'] = action.get('time_start', '')
                payload['time_end']   = action.get('time_end', '')
                payload['room_no']    = action.get('room_no', 'TBD')

            sb.table('class_changes').insert(payload).execute()
            synced.append(local_id)

        except Exception as e:
            failed.append({'local_id': local_id, 'error': str(e)})

    return jsonify({'success': True, 'synced': synced, 'failed': failed})


# ── DELETE ────────────────────────────────────────────────────

@classmanagement_bp.route('/api/class-changes/<change_id>', methods=['DELETE'])
def delete_change(change_id):
    user_id = request.args.get('user_id', '').strip()
    if not _require_cr(user_id):
        return jsonify({'error': 'Forbidden'}), 403
    sb = get_supabase_admin()
    try:
        sb.table('class_changes').delete().eq('id', change_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500