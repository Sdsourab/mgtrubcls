"""
app/exams/routes.py
────────────────────
Exam schedule management.
CR: create / update / delete exam entries.
All students: view exams for their cohort + countdown.
Offline: schedule cached; countdown recalculated client-side.

Route order matters in Flask:
  /api/exams/upcoming and /api/exams/sync MUST be registered
  BEFORE /api/exams/<exam_id> so they are not swallowed.
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import date as _date, datetime, timezone
import re as _re

exams_bp = Blueprint('exams', __name__)


# ── Auth helper ───────────────────────────────────────────────

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


def _days_remaining(exam_date_str: str):
    """Return int days remaining from today, or None on parse error."""
    try:
        exam_dt = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
        return (exam_dt - _date.today()).days
    except Exception:
        return None


def _enrich_exams(exams, mapping):
    """Add days_remaining, is_today, is_urgent, and course_name to each exam."""
    today = _date.today()
    for exam in exams:
        d = _days_remaining(exam.get('exam_date', ''))
        exam['days_remaining'] = d
        exam['is_today']   = d == 0
        exam['is_tomorrow'] = d == 1
        exam['is_urgent']  = d is not None and 0 <= d <= 7
        if not exam.get('course_name'):
            exam['course_name'] = mapping.get(
                exam.get('course_code', ''), exam.get('course_code', '')
            )
    return exams


# ── Page ──────────────────────────────────────────────────────

@exams_bp.route('/')
def exams_page():
    return render_template('modules/exams.html')


# ── IMPORTANT: static sub-paths BEFORE /<exam_id> ─────────────

@exams_bp.route('/api/exams/upcoming', methods=['GET'])
def get_upcoming_summary():
    """Dashboard widget: next 5 exams within 7 days with urgent flag."""
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

        exams = q.execute().data or []

        # Enrich with mapping
        try:
            mapping = {r['code']: r['full_name']
                       for r in (sb.table('mappings').select('code,full_name').execute().data or [])}
        except Exception:
            mapping = {}

        _enrich_exams(exams, mapping)
        has_urgent = any(e.get('is_urgent') for e in exams)
        return jsonify({'success': True, 'data': exams, 'has_urgent': has_urgent})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exams_bp.route('/api/exams/sync', methods=['POST'])
def sync_offline_exams():
    """Batch sync exams queued offline by CR."""
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    exams   = data.get('exams', [])

    profile = _require_cr(user_id)
    if not profile:
        return jsonify({'error': 'Forbidden'}), 403

    if not exams:
        return jsonify({'success': True, 'synced': [], 'failed': []})

    sb = get_supabase_admin()
    synced, failed = [], []

    for exam in exams:
        local_id = exam.get('local_id')
        try:
            course_code = exam.get('course_code', '')
            course_name = exam.get('course_name', '')
            if not course_name:
                try:
                    m = sb.table('mappings').select('full_name').eq('code', course_code).execute()
                    course_name = m.data[0]['full_name'] if m.data else course_code
                except Exception:
                    course_name = course_code

            payload = {
                'program':     exam.get('program', profile.get('program', 'BBA')),
                'target_year': exam.get('year', profile.get('cr_for_year') or profile.get('year', 1)),
                'target_sem':  exam.get('semester', profile.get('cr_for_semester') or profile.get('semester', 1)),
                'course_code': course_code,
                'course_name': course_name,
                'exam_date':   exam.get('exam_date', ''),
                'start_time':  exam.get('start_time', ''),
                'end_time':    exam.get('end_time', ''),
                'room_no':     exam.get('room_no', 'TBD'),
                'exam_type':   exam.get('exam_type', 'other'),
                'notes':       exam.get('notes', ''),
                'created_by':  user_id,
            }
            sb.table('exam_schedules').insert(payload).execute()
            synced.append(local_id)
        except Exception as e:
            failed.append({'local_id': local_id, 'error': str(e)})

    return jsonify({'success': True, 'synced': synced, 'failed': failed})


# ── GET exam list ──────────────────────────────────────────────

@exams_bp.route('/api/exams', methods=['GET'])
def get_exams():
    """Fetch upcoming exam schedule for a cohort."""
    program      = request.args.get('program', 'BBA')
    year         = request.args.get('year')
    sem          = request.args.get('semester')
    from_dt      = request.args.get('from', _date.today().isoformat())
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

        exams = q.execute().data or []

        try:
            mapping = {r['code']: r['full_name']
                       for r in (sb.table('mappings').select('code,full_name').execute().data or [])}
        except Exception:
            mapping = {}

        _enrich_exams(exams, mapping)
        return jsonify({'success': True, 'data': exams, 'count': len(exams)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── POST: create exam ──────────────────────────────────────────

@exams_bp.route('/api/exams', methods=['POST'])
def create_exam():
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    profile = _require_cr(user_id)
    if not profile:
        return jsonify({'error': 'Only CR or Admin can publish exam schedules'}), 403

    missing = [f for f in ('course_code', 'exam_date', 'exam_type') if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing: {", ".join(missing)}'}), 400

    sb = get_supabase_admin()
    try:
        course_code = data['course_code']
        course_name = data.get('course_name', '')
        if not course_name:
            try:
                m = sb.table('mappings').select('full_name').eq('code', course_code).execute()
                course_name = m.data[0]['full_name'] if m.data else course_code
            except Exception:
                course_name = course_code

        payload = {
            'program':     data.get('program', profile.get('program', 'BBA')),
            'target_year': data.get('year', profile.get('cr_for_year') or profile.get('year', 1)),
            'target_sem':  data.get('semester', profile.get('cr_for_semester') or profile.get('semester', 1)),
            'course_code': course_code,
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

        # Auto-publish a pinned exam notice
        try:
            LABELS = {'midterm': 'Midterm Exam', 'final': 'Final Exam',
                      'quiz': 'Quiz', 'viva': 'Viva', 'other': 'Exam'}
            label   = LABELS.get(data['exam_type'], 'Exam')
            time_str = (f'<br>⏰ <strong>Time:</strong> {data["start_time"]} – {data["end_time"]}'
                        if data.get('start_time') else '')
            room_str = (f'<br>🏛️ <strong>Room:</strong> {data["room_no"]}'
                        if data.get('room_no') else '')
            sb.table('notices').insert({
                'author_id':    user_id,
                'author_name':  profile.get('full_name', 'CR'),
                'title':        f'📝 {label}: {course_name} — {data["exam_date"]}',
                'content':      (f'<p><strong>{label}</strong> for <strong>{course_name}</strong>'
                                 f' has been scheduled.</p>'
                                 f'<p>📅 <strong>Date:</strong> {data["exam_date"]}'
                                 f'{time_str}{room_str}</p>'
                                 + (f'<p><em>Notes: {data["notes"]}</em></p>' if data.get('notes') else '')),
                'content_text': f'{label} {course_name} on {data["exam_date"]}',
                'type':         'exam',
                'program':      payload['program'],
                'target_year':  payload['target_year'],
                'target_sem':   payload['target_sem'],
                'is_draft':     False,
                'pinned':       True,
            }).execute()
        except Exception:
            pass  # notice is non-fatal

        return jsonify({'success': True, 'data': resp.data}), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── PATCH exam — must come AFTER static sub-paths ─────────────

@exams_bp.route('/api/exams/<exam_id>', methods=['PATCH'])
def update_exam(exam_id):
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    if not _require_cr(user_id):
        return jsonify({'error': 'Forbidden'}), 403

    allowed = ['exam_date', 'start_time', 'end_time', 'room_no', 'exam_type', 'notes', 'course_name']
    payload = {k: data[k] for k in allowed if k in data}
    if not payload:
        return jsonify({'error': 'Nothing to update'}), 400

    sb = get_supabase_admin()
    try:
        resp = sb.table('exam_schedules').update(payload).eq('id', exam_id).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── DELETE exam ───────────────────────────────────────────────

@exams_bp.route('/api/exams/<exam_id>', methods=['DELETE'])
def delete_exam(exam_id):
    user_id = request.args.get('user_id', '').strip()
    if not _require_cr(user_id):
        return jsonify({'error': 'Forbidden'}), 403

    sb = get_supabase_admin()
    try:
        sb.table('exam_schedules').delete().eq('id', exam_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500