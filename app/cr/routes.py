"""
app/cr/routes.py
════════════════
CR (Class Representative) Blueprint.
Handles: Notices, Class Cancellations, Extra Classes, Exam Schedules.
All endpoints check role_label = 'CR' or role = 'admin'.
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import datetime

cr_bp = Blueprint('cr', __name__)


def _get_author(data: dict) -> dict:
    """Extract author info from request payload."""
    return {
        'author_id':   data.get('author_id', ''),
        'author_name': data.get('author_name', 'CR'),
        'role_label':  data.get('role_label', 'CR'),
    }


def _program_filter(data: dict) -> dict:
    """Extract program/year/semester targeting."""
    return {
        'program':  data.get('program',  'ALL'),
        'year':     int(data.get('year',     0)),
        'semester': int(data.get('semester', 0)),
    }


# ── Pages ────────────────────────────────────────────────────

@cr_bp.route('/dashboard')
def cr_dashboard():
    return render_template('modules/cr_dashboard.html')


@cr_bp.route('/notices')
def notices_page():
    return render_template('modules/notices.html')


@cr_bp.route('/exams')
def exams_page():
    return render_template('modules/exams.html')


# ══════════════════════════════════════════════════════════════
# NOTICES API
# ══════════════════════════════════════════════════════════════

@cr_bp.route('/api/notices', methods=['GET'])
def get_notices():
    """Get notices — filtered by program/year/semester if provided."""
    program  = request.args.get('program',  '')
    year     = request.args.get('year',     '')
    semester = request.args.get('semester', '')
    limit    = int(request.args.get('limit', 50))

    sb = get_supabase_admin()
    try:
        q = sb.table('notices').select('*').order('is_pinned', desc=True) \
              .order('created_at', desc=True).limit(limit)

        # Filter: show notices for ALL or matching program
        # We fetch all and filter client-side for simplicity
        resp = q.execute()
        notices = resp.data or []

        # Filter by target if user has program context
        if program and program != 'ALL':
            notices = [
                n for n in notices
                if n.get('program') in ['ALL', program]
                   and (not year     or n.get('year', 0)     in [0, int(year)])
                   and (not semester or n.get('semester', 0) in [0, int(semester)])
            ]

        return jsonify({'success': True, 'data': notices})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cr_bp.route('/api/notices', methods=['POST'])
def create_notice():
    data = request.get_json() or {}

    if not data.get('title') or not data.get('body'):
        return jsonify({'error': 'title and body required'}), 400

    sb = get_supabase_admin()
    try:
        payload = {
            **_get_author(data),
            **_program_filter(data),
            'title':     data['title'].strip(),
            'body':      data['body'],
            'is_pinned': bool(data.get('is_pinned', False)),
        }
        resp = sb.table('notices').insert(payload).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cr_bp.route('/api/notices/<notice_id>', methods=['DELETE'])
def delete_notice(notice_id):
    sb = get_supabase_admin()
    try:
        sb.table('notices').delete().eq('id', notice_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cr_bp.route('/api/notices/<notice_id>/pin', methods=['PATCH'])
def toggle_pin(notice_id):
    data      = request.get_json() or {}
    is_pinned = bool(data.get('is_pinned', False))
    sb        = get_supabase_admin()
    try:
        resp = sb.table('notices').update({'is_pinned': is_pinned}) \
                 .eq('id', notice_id).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════
# CLASS CHANGES API (cancel / extra)
# ══════════════════════════════════════════════════════════════

@cr_bp.route('/api/class-changes', methods=['GET'])
def get_class_changes():
    """Get class changes for a date range."""
    from_date = request.args.get('from', datetime.today().strftime('%Y-%m-%d'))
    to_date   = request.args.get('to',   from_date)
    program   = request.args.get('program', '')

    sb = get_supabase_admin()
    try:
        q = sb.table('class_changes').select('*') \
              .gte('date', from_date) \
              .lte('date', to_date) \
              .order('date').order('time_start')

        resp    = q.execute()
        changes = resp.data or []

        if program and program != 'ALL':
            changes = [c for c in changes
                       if c.get('program') in ['ALL', program]]

        return jsonify({'success': True, 'data': changes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cr_bp.route('/api/class-changes', methods=['POST'])
def create_class_change():
    data        = request.get_json() or {}
    change_type = data.get('change_type', '')

    if change_type not in ('cancel', 'extra'):
        return jsonify({'error': 'change_type must be cancel or extra'}), 400
    if not data.get('course_code') or not data.get('date'):
        return jsonify({'error': 'course_code and date required'}), 400

    sb = get_supabase_admin()
    try:
        payload = {
            **_get_author(data),
            **_program_filter(data),
            'change_type':  change_type,
            'course_code':  data.get('course_code', '').strip(),
            'course_name':  data.get('course_name', ''),
            'teacher_code': data.get('teacher_code', ''),
            'teacher_name': data.get('teacher_name', ''),
            'room_no':      data.get('room_no', ''),
            'date':         data['date'],
            'time_start':   data.get('time_start', ''),
            'time_end':     data.get('time_end', ''),
            'reason':       data.get('reason', ''),
        }
        resp = sb.table('class_changes').insert(payload).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cr_bp.route('/api/class-changes/<change_id>', methods=['DELETE'])
def delete_class_change(change_id):
    sb = get_supabase_admin()
    try:
        sb.table('class_changes').delete().eq('id', change_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════
# EXAMS API
# ══════════════════════════════════════════════════════════════

@cr_bp.route('/api/exams', methods=['GET'])
def get_exams():
    program  = request.args.get('program',  '')
    year     = request.args.get('year',     '')
    semester = request.args.get('semester', '')
    upcoming = request.args.get('upcoming', '0') == '1'

    sb = get_supabase_admin()
    try:
        q = sb.table('exams').select('*').order('exam_date')

        if upcoming:
            today = datetime.today().strftime('%Y-%m-%d')
            q = q.gte('exam_date', today)

        resp  = q.execute()
        exams = resp.data or []

        if program and program != 'ALL':
            exams = [
                e for e in exams
                if e.get('program') in ['ALL', program]
                   and (not year     or e.get('year', 0)     in [0, int(year)])
                   and (not semester or e.get('semester', 0) in [0, int(semester)])
            ]

        # Add remaining_days
        today_date = datetime.today().date()
        for exam in exams:
            try:
                exam_date = datetime.strptime(exam['exam_date'], '%Y-%m-%d').date()
                exam['remaining_days'] = (exam_date - today_date).days
            except Exception:
                exam['remaining_days'] = None

        return jsonify({'success': True, 'data': exams})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cr_bp.route('/api/exams', methods=['POST'])
def create_exam():
    data = request.get_json() or {}

    if not data.get('course_code') or not data.get('exam_date'):
        return jsonify({'error': 'course_code and exam_date required'}), 400

    sb = get_supabase_admin()
    try:
        payload = {
            **_get_author(data),
            **_program_filter(data),
            'course_code': data.get('course_code', '').strip(),
            'course_name': data.get('course_name', ''),
            'exam_type':   data.get('exam_type',   'Midterm'),
            'exam_date':   data['exam_date'],
            'start_time':  data.get('start_time', ''),
            'end_time':    data.get('end_time',   ''),
            'room_no':     data.get('room_no',    ''),
            'notes':       data.get('notes',      ''),
        }
        resp = sb.table('exams').insert(payload).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cr_bp.route('/api/exams/<exam_id>', methods=['DELETE'])
def delete_exam(exam_id):
    sb = get_supabase_admin()
    try:
        sb.table('exams').delete().eq('id', exam_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════
# OFFLINE SYNC ENDPOINT
# Receives queued offline actions and processes them
# ══════════════════════════════════════════════════════════════

@cr_bp.route('/api/sync-queue', methods=['POST'])
def process_sync_queue():
    """
    Process offline-queued actions when user comes back online.
    Payload: { user_id, actions: [{type, payload, queued_at}] }
    """
    data    = request.get_json() or {}
    user_id = data.get('user_id', '')
    actions = data.get('actions', [])

    results = {'processed': 0, 'failed': 0, 'errors': []}

    for action in actions:
        action_type = action.get('type', '')
        payload     = action.get('payload', {})
        payload['author_id'] = user_id

        try:
            if action_type == 'create_notice':
                _handle_notice(payload)
            elif action_type == 'cancel_class':
                payload['change_type'] = 'cancel'
                _handle_class_change(payload)
            elif action_type == 'extra_class':
                payload['change_type'] = 'extra'
                _handle_class_change(payload)
            elif action_type == 'create_exam':
                _handle_exam(payload)
            else:
                results['errors'].append(f'Unknown action: {action_type}')
                results['failed'] += 1
                continue
            results['processed'] += 1
        except Exception as e:
            results['failed'] += 1
            results['errors'].append(str(e))

    return jsonify({'success': True, **results})


def _handle_notice(data):
    sb = get_supabase_admin()
    sb.table('notices').insert({
        **_get_author(data),
        **_program_filter(data),
        'title':     data.get('title', '').strip(),
        'body':      data.get('body', ''),
        'is_pinned': bool(data.get('is_pinned', False)),
    }).execute()


def _handle_class_change(data):
    sb = get_supabase_admin()
    sb.table('class_changes').insert({
        **_get_author(data),
        **_program_filter(data),
        'change_type':  data.get('change_type', 'cancel'),
        'course_code':  data.get('course_code', '').strip(),
        'course_name':  data.get('course_name', ''),
        'teacher_code': data.get('teacher_code', ''),
        'teacher_name': data.get('teacher_name', ''),
        'room_no':      data.get('room_no', ''),
        'date':         data.get('date', ''),
        'time_start':   data.get('time_start', ''),
        'time_end':     data.get('time_end', ''),
        'reason':       data.get('reason', ''),
    }).execute()


def _handle_exam(data):
    sb = get_supabase_admin()
    sb.table('exams').insert({
        **_get_author(data),
        **_program_filter(data),
        'course_code': data.get('course_code', '').strip(),
        'course_name': data.get('course_name', ''),
        'exam_type':   data.get('exam_type', 'Midterm'),
        'exam_date':   data.get('exam_date', ''),
        'start_time':  data.get('start_time', ''),
        'end_time':    data.get('end_time', ''),
        'room_no':     data.get('room_no', ''),
        'notes':       data.get('notes', ''),
    }).execute()
    