"""
app/classmanagement/routes.py
──────────────────────────────
CR-only: Cancel existing classes, add extra classes.
Changes broadcast to all students in the same cohort.
Supports offline queue sync.
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import date as _date

classmanagement_bp = Blueprint('classmanagement', __name__)


def _require_cr(user_id: str):
    """Returns (profile | None). None means unauthorized."""
    if not user_id:
        return None
    try:
        sb = get_supabase_admin()
        p = sb.table('profiles').select('*').eq('id', user_id).single().execute()
        profile = p.data or {}
        if profile.get('role') in ('cr', 'admin'):
            return profile
        return None
    except Exception:
        return None


# ── Page ──────────────────────────────────────────────────────

@classmanagement_bp.route('/')
def management_page():
    return render_template('modules/class_management.html')


# ── GET changes for a date range ─────────────────────────────

@classmanagement_bp.route('/api/class-changes', methods=['GET'])
def get_class_changes():
    """
    Fetch class changes (cancels + extras) for a specific cohort.
    Optional date filtering. Used by dashboard to show alerts.
    """
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

        resp = q.execute()
        rows = resp.data or []

        # Enrich with course/teacher full names
        try:
            map_resp = sb.table('mappings').select('code,full_name').execute()
            mapping  = {r['code']: r['full_name'] for r in (map_resp.data or [])}
            for row in rows:
                row['course_name']  = mapping.get(row.get('course_code', ''), row.get('course_code', ''))
                row['teacher_name'] = mapping.get(row.get('teacher_code', ''), row.get('teacher_code', ''))
        except Exception:
            pass

        return jsonify({'success': True, 'data': rows})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── POST: cancel a class ──────────────────────────────────────

@classmanagement_bp.route('/api/class-changes/cancel', methods=['POST'])
def cancel_class():
    """
    CR cancels a class for a specific date.
    Automatically creates a notice for the cohort.
    """
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    profile = _require_cr(user_id)
    if not profile:
        return jsonify({'error': 'Only CR or Admin can cancel classes'}), 403

    course_code = data.get('course_code', '').strip()
    change_date = data.get('change_date', '').strip()

    if not course_code or not change_date:
        return jsonify({'error': 'course_code and change_date required'}), 400

    sb = get_supabase_admin()
    try:
        # Resolve full course name for the auto-notice
        course_name = course_code
        try:
            m = sb.table('mappings').select('full_name').eq('code', course_code).execute()
            if m.data:
                course_name = m.data[0]['full_name']
        except Exception:
            pass

        payload = {
            'type':             'cancel',
            'course_code':      course_code,
            'teacher_code':     data.get('teacher_code', ''),
            'program':          data.get('program', profile.get('program', 'BBA')),
            'target_year':      data.get('year', profile.get('cr_for_year') or profile.get('year', 1)),
            'target_semester':  data.get('semester', profile.get('cr_for_semester') or profile.get('semester', 1)),
            'change_date':      change_date,
            'reason':           data.get('reason', ''),
            'created_by':       user_id,
            'created_by_name':  profile.get('full_name', 'CR'),
        }

        resp = sb.table('class_changes').insert(payload).execute()

        # Auto-publish cancellation notice
        try:
            notice_payload = {
                'author_id':   user_id,
                'author_name': profile.get('full_name', 'CR'),
                'title':       f'Class Cancelled: {course_name} — {change_date}',
                'content':     (
                    f'<p><strong>{course_name}</strong> class on '
                    f'<strong>{change_date}</strong> has been <strong style="color:#e53e3e">cancelled</strong>.</p>'
                    + (f'<p>Reason: {data.get("reason")}</p>' if data.get('reason') else '')
                    + f'<p><em>— {profile.get("full_name", "CR")}</em></p>'
                ),
                'content_text': f'{course_name} class cancelled on {change_date}. {data.get("reason", "")}',
                'type':        'class_cancel',
                'program':     payload['program'],
                'target_year': payload['target_year'],
                'target_sem':  payload['target_semester'],
                'is_draft':    False,
            }
            sb.table('notices').insert(notice_payload).execute()
        except Exception:
            pass  # notice creation is non-fatal

        return jsonify({'success': True, 'data': resp.data}), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── POST: add an extra class ──────────────────────────────────

@classmanagement_bp.route('/api/class-changes/extra', methods=['POST'])
def add_extra_class():
    """
    CR adds an extra class on a specific date/time.
    """
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    profile = _require_cr(user_id)
    if not profile:
        return jsonify({'error': 'Only CR or Admin can add extra classes'}), 403

    required = ['course_code', 'change_date', 'time_start', 'time_end']
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing: {", ".join(missing)}'}), 400

    sb = get_supabase_admin()
    try:
        course_name = data['course_code']
        try:
            m = sb.table('mappings').select('full_name').eq('code', data['course_code']).execute()
            if m.data:
                course_name = m.data[0]['full_name']
        except Exception:
            pass

        payload = {
            'type':            'extra',
            'course_code':     data['course_code'],
            'teacher_code':    data.get('teacher_code', ''),
            'program':         data.get('program', profile.get('program', 'BBA')),
            'target_year':     data.get('year', profile.get('cr_for_year') or profile.get('year', 1)),
            'target_semester': data.get('semester', profile.get('cr_for_semester') or profile.get('semester', 1)),
            'change_date':     data['change_date'],
            'time_start':      data['time_start'],
            'time_end':        data['time_end'],
            'room_no':         data.get('room_no', 'TBD'),
            'reason':          data.get('reason', ''),
            'created_by':      user_id,
            'created_by_name': profile.get('full_name', 'CR'),
        }

        resp = sb.table('class_changes').insert(payload).execute()

        # Auto-notice
        try:
            notice_payload = {
                'author_id':   user_id,
                'author_name': profile.get('full_name', 'CR'),
                'title':       f'Extra Class: {course_name} — {data["change_date"]}',
                'content': (
                    f'<p>An <strong style="color:#38a169">extra class</strong> for '
                    f'<strong>{course_name}</strong> has been scheduled.</p>'
                    f'<p>📅 <strong>Date:</strong> {data["change_date"]}<br>'
                    f'⏰ <strong>Time:</strong> {data["time_start"]} – {data["time_end"]}<br>'
                    f'🏛️ <strong>Room:</strong> {data.get("room_no", "TBD")}</p>'
                    + (f'<p>Note: {data.get("reason")}</p>' if data.get('reason') else '')
                ),
                'content_text': f'Extra class {course_name} on {data["change_date"]} {data["time_start"]}-{data["time_end"]}',
                'type':        'extra_class',
                'program':     payload['program'],
                'target_year': payload['target_year'],
                'target_sem':  payload['target_semester'],
                'is_draft':    False,
            }
            sb.table('notices').insert(notice_payload).execute()
        except Exception:
            pass

        return jsonify({'success': True, 'data': resp.data}), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── DELETE a change ───────────────────────────────────────────

@classmanagement_bp.route('/api/class-changes/<change_id>', methods=['DELETE'])
def delete_change(change_id):
    user_id = request.args.get('user_id', '')
    profile = _require_cr(user_id)
    if not profile:
        return jsonify({'error': 'Forbidden'}), 403

    sb = get_supabase_admin()
    try:
        sb.table('class_changes').delete().eq('id', change_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Batch sync offline changes ────────────────────────────────

@classmanagement_bp.route('/api/class-changes/sync', methods=['POST'])
def sync_offline_changes():
    """Sync a batch of offline-queued class changes."""
    data    = request.get_json() or {}
    user_id = data.get('user_id', '')
    actions = data.get('actions', [])

    profile = _require_cr(user_id)
    if not profile:
        return jsonify({'error': 'Forbidden'}), 403

    synced, failed = [], []
    for action in actions:
        try:
            action_type = action.get('type')
            if action_type == 'cancel':
                action['user_id'] = user_id
                # Reuse cancel logic
                sb = get_supabase_admin()
                payload = {
                    'type':            'cancel',
                    'course_code':     action.get('course_code'),
                    'program':         action.get('program', profile.get('program')),
                    'target_year':     action.get('year', profile.get('year')),
                    'target_semester': action.get('semester', profile.get('semester')),
                    'change_date':     action.get('change_date'),
                    'reason':          action.get('reason', ''),
                    'created_by':      user_id,
                    'created_by_name': profile.get('full_name', 'CR'),
                    'synced':          True,
                }
                sb.table('class_changes').insert(payload).execute()
                synced.append(action.get('local_id'))
        except Exception as e:
            failed.append({'local_id': action.get('local_id'), 'error': str(e)})

    return jsonify({'success': True, 'synced': synced, 'failed': failed})