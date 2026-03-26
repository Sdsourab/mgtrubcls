from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin

guest_bp = Blueprint('guest', __name__)


# ── Pages ─────────────────────────────────────────────────────────────────────

@guest_bp.route('/')
def home():
    return render_template('guest/home.html')

@guest_bp.route('/faculty-finder')
def faculty_finder():
    return render_template('guest/faculty_finder.html')

@guest_bp.route('/room-availability')
def room_availability():
    return render_template('guest/room_availability.html')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_mappings(sb):
    """Return a dict {code: full_name} for fast lookup."""
    resp = sb.table('mappings').select('code,full_name').execute()
    return {row['code']: row['full_name'] for row in (resp.data or [])}


# ── APIs ──────────────────────────────────────────────────────────────────────

@guest_bp.route('/api/all-teachers', methods=['GET'])
def get_all_teachers():
    """Return all teachers — no auth needed."""
    sb = get_supabase_admin()
    try:
        resp = sb.table('mappings').select('*').eq('type', 'teacher').order('full_name').execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@guest_bp.route('/api/faculty-schedule', methods=['GET'])
def get_faculty_schedule():
    """Return full weekly schedule for a teacher, with course names enriched."""
    code = request.args.get('code', '').strip().upper()
    if not code:
        return jsonify({'success': False, 'error': 'teacher code required'}), 400

    sb = get_supabase_admin()
    try:
        mappings = _build_mappings(sb)

        resp = sb.table('routines').select('*') \
            .eq('teacher_code', code) \
            .order('day').order('time_start').execute()

        enriched = []
        for row in (resp.data or []):
            row['course_name']  = mappings.get(row.get('course_code', ''), row.get('course_code', ''))
            row['teacher_name'] = mappings.get(row.get('teacher_code', ''), row.get('teacher_code', ''))
            enriched.append(row)

        return jsonify({'success': True, 'data': enriched})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@guest_bp.route('/api/room-availability', methods=['GET'])
def get_room_availability():
    """Return room occupancy for a given day, with teacher/course names enriched."""
    day = request.args.get('day', '').strip()

    sb = get_supabase_admin()
    try:
        mappings = _build_mappings(sb)

        q = sb.table('routines').select('*')
        if day:
            q = q.eq('day', day)
        resp = q.order('room_no').order('time_start').execute()

        enriched = []
        for row in (resp.data or []):
            row['course_name']  = mappings.get(row.get('course_code', ''), row.get('course_code', ''))
            row['teacher_name'] = mappings.get(row.get('teacher_code', ''), row.get('teacher_code', ''))
            enriched.append(row)

        return jsonify({'success': True, 'data': enriched})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500