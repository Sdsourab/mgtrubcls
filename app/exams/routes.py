"""
app/exams/routes.py
────────────────────
Exam schedule management.
CR: create/update/delete exam entries.
All students: view exams for their cohort + countdown.
Offline: schedule cached, countdown works without internet.
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import date as _date, datetime, timezone

exams_bp = Blueprint('exams', __name__)


def _require_cr(user_id: str):
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

@exams_bp.route('/')
def exams_page():
    return render_template('modules/exams.html')


# ── GET exam schedule ─────────────────────────────────────────

@exams_bp.route('/api/exams', methods=['GET'])
def get_exams():
    """
    Fetch upcoming exams for a cohort.
    Includes 'days_remaining' computed field.
    """
    program = request.args.get('program', 'BBA')
    year    = request.args.get('year')
    sem     = request.args.get('semester')
    from_dt = request.args.get('from', _date.today().isoformat())
    include_past = request.args.get('include_past', 'false').lower() == 'true'

    sb = get_supabase_admin()
    try:
        q = sb.table('exam_schedules') \
              .select('*') \
              .eq('program', program) \
              .order('exam_date')

        if year:
            q = q.eq('target_year', int(year))
        if sem:
            q = q.eq('target_sem', int(sem))
        if not include_past:
            q = q.gte('exam_date', from_dt)

        resp = q.execute()
        exams = resp.data or []

        # Compute days_remaining for each exam
        today = _date.today()
        for exam in exams:
            try:
                exam_dt = datetime.strptime(exam['exam_date'], '%Y-%m-%d').date()
                exam['days_remaining'] = (exam_dt - today).days
                exam['is_today']       = exam_dt == today
                exam['is_tomorrow']    = (exam_dt - today).days == 1
                exam['is_urgent']      = 0 <= exam['days_remaining'] <= 3
            except Exception:
                exam['days_remaining'] = None

        # Also enrich with full course names
        try:
            map_resp = sb.table('mappings').select('code,full_name').execute()
            mapping  = {r['code']: r['full_name'] for r in (map_resp.data or [])}
            for exam in exams:
                if not exam.get('course_name'):
                    exam['course_name'] = mapping.get(exam.get('course_code', ''), exam.get('course_code', ''))
        except Exception:
            pass

        return jsonify({'success': True, 'data': exams, 'count': len(exams)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── POST: create exam entry ───────────────────────────────────

@exams_bp.route('/api/exams', methods=['POST'])
def create_exam():
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    profile = _require_cr(user_id)
    if not profile:
        return jsonify({'error': 'Only CR or Admin can publish exam schedules'}), 403

    required = ['course_code', 'exam_date', 'exam_type']
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing: {", ".join(missing)}'}), 400

    sb = get_supabase_admin()
    try:
        # Resolve course name
        course_name = data.get('course_name', '')
        if not course_name:
            try:
                m = sb.table('mappings').select('full_name').eq('code', data['course_code']).execute()
                if m.data:
                    course_name = m.data[0]['full_name']
            except Exception:
                course_name = data['course_code']

        payload = {
            'program':     data.get('program', profile.get('program', 'BBA')),
            'target_year': data.get('year', profile.get('cr_for_year') or profile.get('year', 1)),
            'target_sem':  data.get('semester', profile.get('cr_for_semester') or profile.get('semester', 1)),
            'course_code': data['course_code'],
            'course_name': course_name,
            'exam_date':   data['exam_date'],
            'start_time':  data.get('start_time', ''),
            'end_time':    data.get('end_time', ''),
            'room_no':     data.get('room_no', 'TBD'),
            'exam_type':   data['exam_type'],
            'notes':       data.get('notes', ''),
            'created_by':  user_id,
        }

        resp = sb.table('exam_schedules').insert(payload).execute()

        # Auto-publish exam notice
        try:
            exam_type_label = {
                'midterm': 'Midterm Exam',
                'final':   'Final Exam',
                'quiz':    'Quiz',
                'viva':    'Viva',
                'other':   'Exam',
            }.get(data['exam_type'], 'Exam')

            notice = {
                'author_id':   user_id,
                'author_name': profile.get('full_name', 'CR'),
                'title':       f'📝 {exam_type_label}: {course_name} — {data["exam_date"]}',
                'content': (
                    f'<p><strong>{exam_type_label}</strong> for '
                    f'<strong>{course_name}</strong> has been scheduled.</p>'
                    f'<p>📅 <strong>Date:</strong> {data["exam_date"]}'
                    + (f'<br>⏰ <strong>Time:</strong> {data.get("start_time", "")} – {data.get("end_time", "")}' if data.get('start_time') else '')
                    + (f'<br>🏛️ <strong>Room:</strong> {data.get("room_no", "TBD")}' if data.get('room_no') else '')
                    + '</p>'
                    + (f'<p><em>Notes: {data.get("notes")}</em></p>' if data.get('notes') else '')
                ),
                'content_text': f'{exam_type_label} {course_name} on {data["exam_date"]}',
                'type':        'exam',
                'program':     payload['program'],
                'target_year': payload['target_year'],
                'target_sem':  payload['target_sem'],
                'is_draft':    False,
                'pinned':      True,  # Exam notices are pinned
            }
            sb.table('notices').insert(notice).execute()
        except Exception:
            pass

        return jsonify({'success': True, 'data': resp.data}), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── PATCH exam ────────────────────────────────────────────────

@exams_bp.route('/api/exams/<exam_id>', methods=['PATCH'])
def update_exam(exam_id):
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    if not _require_cr(user_id):
        return jsonify({'error': 'Forbidden'}), 403

    allowed = ['exam_date', 'start_time', 'end_time', 'room_no', 'exam_type', 'notes', 'course_name']
    payload = {k: data[k] for k in allowed if k in data}

    sb = get_supabase_admin()
    try:
        resp = sb.table('exam_schedules').update(payload).eq('id', exam_id).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── DELETE exam ───────────────────────────────────────────────

@exams_bp.route('/api/exams/<exam_id>', methods=['DELETE'])
def delete_exam(exam_id):
    user_id = request.args.get('user_id', '')
    if not _require_cr(user_id):
        return jsonify({'error': 'Forbidden'}), 403

    sb = get_supabase_admin()
    try:
        sb.table('exam_schedules').delete().eq('id', exam_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET upcoming exams summary (for dashboard widget) ─────────

@exams_bp.route('/api/exams/upcoming', methods=['GET'])
def get_upcoming_summary():
    """Returns next 3 exams + any exam within 7 days (urgent flag)."""
    program = request.args.get('program', 'BBA')
    year    = request.args.get('year')
    sem     = request.args.get('semester')
    today   = _date.today().isoformat()

    sb = get_supabase_admin()
    try:
        q = sb.table('exam_schedules') \
              .select('*') \
              .eq('program', program) \
              .gte('exam_date', today) \
              .order('exam_date') \
              .limit(5)

        if year:
            q = q.eq('target_year', int(year))
        if sem:
            q = q.eq('target_sem', int(sem))

        resp = q.execute()
        exams = resp.data or []

        today_dt = _date.today()
        for exam in exams:
            try:
                exam_dt = datetime.strptime(exam['exam_date'], '%Y-%m-%d').date()
                exam['days_remaining'] = (exam_dt - today_dt).days
                exam['is_urgent']      = exam['days_remaining'] <= 7
            except Exception:
                exam['days_remaining'] = None
                exam['is_urgent'] = False

        has_urgent = any(e.get('is_urgent') for e in exams)
        return jsonify({'success': True, 'data': exams, 'has_urgent': has_urgent})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500