"""
app/teachers/routes.py
══════════════════════
Teacher portal:
  GET  /teachers/profile        → teacher profile page (HTML)
  GET  /teachers/api/profile    → fetch teacher profile + auto-scheduled classes
  PATCH /teachers/api/profile   → update teacher profile (degree, designation, teacher_code)
  GET  /teachers/api/schedule   → fetch all routines for this teacher (from routines table)
  POST /teachers/api/assign-course     → teacher assigns themselves to a course slot in routines
  POST /teachers/api/cancel-class      → cancel a class → writes class_changes + notice for batch
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import date as _date

teachers_bp = Blueprint('teachers', __name__)


# ── Helpers ───────────────────────────────────────────────────

def _get_teacher_profile(user_id: str) -> dict | None:
    """Return teacher_profiles row for given user_id, or None."""
    if not user_id:
        return None
    try:
        sb  = get_supabase_admin()
        row = sb.table('teacher_profiles') \
                .select('*') \
                .eq('user_id', user_id) \
                .single() \
                .execute()
        return row.data or None
    except Exception:
        return None


def _get_base_profile(user_id: str) -> dict:
    """Return profiles row for user_id."""
    try:
        sb  = get_supabase_admin()
        row = sb.table('profiles') \
                .select('id, full_name, email, role') \
                .eq('id', user_id) \
                .single() \
                .execute()
        return row.data or {}
    except Exception:
        return {}


def _require_teacher(user_id: str) -> dict | None:
    """Return teacher profile if user is a verified teacher, else None."""
    base = _get_base_profile(user_id)
    if base.get('role') not in ('teacher', 'admin'):
        return None
    return _get_teacher_profile(user_id)


def _enrich_routine(rows: list, sb) -> list:
    """Add course_name from mappings to routine rows."""
    try:
        mapping = {
            r['code']: r['full_name']
            for r in (sb.table('mappings').select('code,full_name').execute().data or [])
        }
    except Exception:
        mapping = {}
    for row in rows:
        row['course_name'] = mapping.get(row.get('course_code', ''), row.get('course_code', ''))
    return rows


def _fmt12h(t: str) -> str:
    try:
        h, m = map(int, t.split(':'))
        return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    except Exception:
        return t


# ── Page ──────────────────────────────────────────────────────

@teachers_bp.route('/profile')
def teacher_profile_page():
    return render_template('teachers/profile.html')


# ── API: Get full teacher profile + schedule ──────────────────

@teachers_bp.route('/api/profile', methods=['GET'])
def get_teacher_profile():
    user_id = request.args.get('user_id', '').strip()
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    base    = _get_base_profile(user_id)
    profile = _get_teacher_profile(user_id)

    if not profile:
        # Return base info so frontend knows what fields to collect
        return jsonify({
            'success':  True,
            'profile':  None,
            'base':     base,
            'schedule': [],
        })

    teacher_code = profile.get('teacher_code', '')
    sb           = get_supabase_admin()
    schedule     = []

    if teacher_code:
        try:
            rows = sb.table('routines') \
                     .select('*') \
                     .eq('teacher_code', teacher_code) \
                     .order('day') \
                     .order('time_start') \
                     .execute().data or []
            rows = _enrich_routine(rows, sb)
            for r in rows:
                r['time_start_12h'] = _fmt12h(r.get('time_start', ''))
                r['time_end_12h']   = _fmt12h(r.get('time_end', ''))
            schedule = rows
        except Exception:
            pass

    return jsonify({
        'success':  True,
        'profile':  profile,
        'base':     base,
        'schedule': schedule,
    })


# ── API: Update teacher profile ───────────────────────────────

@teachers_bp.route('/api/profile', methods=['PATCH'])
def update_teacher_profile():
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    base = _get_base_profile(user_id)
    if base.get('role') not in ('teacher', 'admin'):
        return jsonify({'error': 'Teacher account required'}), 403

    sb = get_supabase_admin()

    # Upsert teacher_profiles row
    payload = {
        'user_id':     user_id,
        'degree':      data.get('degree', ''),
        'designation': data.get('designation', ''),
        'teacher_code': data.get('teacher_code', ''),
        'bio':         data.get('bio', ''),
    }

    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        sb.table('teacher_profiles') \
          .upsert(payload, on_conflict='user_id') \
          .execute()

        # Also update full_name in profiles if provided
        if data.get('full_name'):
            sb.table('profiles') \
              .update({'full_name': data['full_name']}) \
              .eq('id', user_id) \
              .execute()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Get teacher's schedule (routines) ────────────────────

@teachers_bp.route('/api/schedule', methods=['GET'])
def get_teacher_schedule():
    """
    Fetch all routine slots assigned to this teacher.
    Can also filter by ?day=Monday
    """
    user_id      = request.args.get('user_id', '').strip()
    day          = request.args.get('day', '').strip()
    teacher_code = request.args.get('teacher_code', '').strip()

    # If teacher_code not passed, look it up from profile
    if not teacher_code and user_id:
        profile = _get_teacher_profile(user_id)
        teacher_code = (profile or {}).get('teacher_code', '')

    if not teacher_code:
        return jsonify({'success': True, 'data': []})

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*').eq('teacher_code', teacher_code)
        if day:
            q = q.eq('day', day)
        rows = q.order('day').order('time_start').execute().data or []
        rows = _enrich_routine(rows, sb)
        for r in rows:
            r['time_start_12h'] = _fmt12h(r.get('time_start', ''))
            r['time_end_12h']   = _fmt12h(r.get('time_end', ''))
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Assign teacher to a routine slot ─────────────────────

@teachers_bp.route('/api/assign-course', methods=['POST'])
def assign_course():
    """
    Teacher sets themselves as the teacher for a routine slot.
    If routine_id provided → update existing slot.
    If not → create new slot.
    """
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    profile = _require_teacher(user_id)
    if profile is None:
        return jsonify({'error': 'Teacher account required'}), 403

    teacher_code = profile.get('teacher_code', '') or data.get('teacher_code', '')
    if not teacher_code:
        return jsonify({'error': 'Teacher code not set in your profile'}), 400

    sb          = get_supabase_admin()
    routine_id  = data.get('routine_id', '').strip()

    if routine_id:
        # Update an existing slot to assign this teacher
        try:
            sb.table('routines') \
              .update({'teacher_code': teacher_code}) \
              .eq('id', routine_id) \
              .execute()
            return jsonify({'success': True, 'action': 'updated'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    else:
        # Insert a brand-new routine slot
        required = ['day', 'time_start', 'time_end', 'course_code', 'room_no']
        missing  = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400

        try:
            payload = {
                'day':            data['day'],
                'time_start':     data['time_start'],
                'time_end':       data['time_end'],
                'course_code':    data['course_code'],
                'teacher_code':   teacher_code,
                'room_no':        data['room_no'],
                'program':        data.get('program', 'BBA'),
                'course_year':    int(data.get('course_year', 1)),
                'course_semester': int(data.get('course_semester', 1)),
                'time_slot':      f"{data['time_start']}-{data['time_end']}",
                'session':        data.get('session', '2025-26'),
            }
            resp = sb.table('routines').insert(payload).execute()
            return jsonify({'success': True, 'action': 'created', 'data': resp.data}), 201
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Teacher cancels a class → notifies that batch ────────

@teachers_bp.route('/api/cancel-class', methods=['POST'])
def teacher_cancel_class():
    """
    Teacher cancels one of their classes for a specific date.
    Creates a class_changes record AND a notice targeting that batch.
    """
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    base    = _get_base_profile(user_id)
    profile = _require_teacher(user_id)

    if profile is None:
        return jsonify({'error': 'Teacher account required'}), 403

    teacher_code = profile.get('teacher_code', '')
    course_code  = data.get('course_code', '').strip()
    change_date  = data.get('change_date', '').strip()

    if not course_code or not change_date:
        return jsonify({'error': 'course_code and change_date are required'}), 400

    # Verify this teacher actually teaches this course
    sb = get_supabase_admin()
    if teacher_code:
        try:
            check = sb.table('routines') \
                      .select('id') \
                      .eq('teacher_code', teacher_code) \
                      .eq('course_code', course_code) \
                      .execute()
            if not check.data:
                return jsonify({'error': 'You are not assigned to this course'}), 403
        except Exception:
            pass  # Let it through if check fails — non-fatal

    # Resolve course full name
    course_name = course_code
    try:
        m = sb.table('mappings').select('full_name').eq('code', course_code).execute()
        if m.data:
            course_name = m.data[0]['full_name']
    except Exception:
        pass

    program  = data.get('program', 'BBA')
    year     = int(data.get('year', 1))
    semester = int(data.get('semester', 1))
    reason   = data.get('reason', '').strip()

    teacher_display = base.get('full_name', 'Teacher')
    reason_html = f'<p><em>Reason: {reason}</em></p>' if reason else ''

    try:
        # 1. Insert into class_changes
        sb.table('class_changes').insert({
            'type':            'cancel',
            'course_code':     course_code,
            'teacher_code':    teacher_code,
            'program':         program,
            'target_year':     year,
            'target_semester': semester,
            'change_date':     change_date,
            'reason':          reason,
            'created_by':      user_id,
            'created_by_name': teacher_display,
        }).execute()

        # 2. Publish a notice so the batch sees it on their dashboard
        try:
            sb.table('notices').insert({
                'author_id':    user_id,
                'author_name':  teacher_display,
                'title':        f'Class Cancelled: {course_name} — {change_date}',
                'content': (
                    f'<p><strong>{course_name}</strong> class on '
                    f'<strong>{change_date}</strong> has been '
                    f'<strong style="color:#e53e3e">cancelled</strong> '
                    f'by {teacher_display}.</p>'
                    f'{reason_html}'
                ),
                'content_text': f'{course_name} class cancelled on {change_date}. {reason}',
                'type':         'class_cancel',
                'program':      program,
                'target_year':  year,
                'target_sem':   semester,
                'is_draft':     False,
                'pinned':       False,
            }).execute()
        except Exception:
            pass  # Non-fatal — class_changes already recorded

        return jsonify({'success': True, 'message': f'Class cancelled and batch notified.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500