from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import datetime

planner_bp = Blueprint('planner', __name__)


@planner_bp.route('/')
def planner_page():
    return render_template('modules/planner.html')


@planner_bp.route('/api/plans', methods=['GET'])
def get_plans():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    sb = get_supabase_admin()
    try:
        resp = sb.table('plans').select('*')\
            .eq('user_id', user_id)\
            .order('date').order('start_time').execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@planner_bp.route('/api/plans', methods=['POST'])
def create_plan():
    data    = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    sb = get_supabase_admin()
    try:
        payload = {
            'user_id':    user_id,
            'title':      data.get('title', ''),
            'type':       data.get('type', 'personal'),   # personal/tuition/work/other
            'date':       data.get('date', ''),
            'start_time': data.get('start_time', ''),
            'end_time':   data.get('end_time', ''),
            'note':       data.get('note', ''),
        }
        resp = sb.table('plans').insert(payload).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@planner_bp.route('/api/plans/<plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    sb = get_supabase_admin()
    try:
        sb.table('plans').delete().eq('id', plan_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@planner_bp.route('/api/conflict-check', methods=['POST'])
def conflict_check():
    """
    Check if a personal plan conflicts with the user's own semester classes.
    Filters by program + course_year + course_semester so only relevant
    classes (not all programs/years) are checked.
    """
    data       = request.get_json()
    plan_date  = data.get('date', '')
    start_time = data.get('start_time', '')
    end_time   = data.get('end_time', '')
    program    = data.get('program', 'BBA')

    # FIX: also accept year and semester so we filter to the user's own semester
    try:
        course_year     = int(data.get('year', 0))
        course_semester = int(data.get('semester', 0))
    except (TypeError, ValueError):
        course_year     = 0
        course_semester = 0

    if not all([plan_date, start_time, end_time]):
        return jsonify({'error': 'date, start_time, end_time required'}), 400

    try:
        d = datetime.strptime(plan_date, '%Y-%m-%d')
        day_name = d.strftime('%A')
    except Exception:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # University classes only run Sun–Thu
    if day_name not in ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']:
        return jsonify({
            'success': True,
            'conflicts': [],
            'day': day_name,
            'message': f'No university classes on {day_name}.'
        })

    # Normalize times to HH:MM
    def norm(t):
        p = t.split(':')
        return f"{p[0].zfill(2)}:{p[1].zfill(2)}"

    try:
        s = norm(start_time)
        e = norm(end_time)
    except Exception:
        return jsonify({'error': 'Invalid time format. Use HH:MM'}), 400

    if s >= e:
        return jsonify({'error': 'start_time must be before end_time'}), 400

    sb = get_supabase_admin()
    try:
        # FIX: filter by program + course_year + course_semester (user's own semester only)
        # Overlap condition: class_start < plan_end AND class_end > plan_start
        q = sb.table('routines').select('*')\
            .eq('day', day_name)\
            .lt('time_start', e)\
            .gt('time_end', s)

        if program:
            q = q.eq('program', program)

        # Only filter by year/semester if user has valid values set
        if course_year > 0:
            q = q.eq('course_year', course_year)
        if course_semester > 0:
            q = q.eq('course_semester', course_semester)

        resp = q.execute()
        rows = resp.data or []

        # Enrich with course/teacher names
        for row in rows:
            try:
                c = sb.table('mappings').select('full_name')\
                    .eq('code', row.get('course_code', '')).execute()
                row['course_name'] = c.data[0]['full_name'] if c.data else row.get('course_code', '')
            except Exception:
                row['course_name'] = row.get('course_code', '')

            try:
                t = sb.table('mappings').select('full_name')\
                    .eq('code', row.get('teacher_code', '')).execute()
                row['teacher_name'] = t.data[0]['full_name'] if t.data else row.get('teacher_code', '')
            except Exception:
                row['teacher_name'] = row.get('teacher_code', '')

        return jsonify({'success': True, 'conflicts': rows, 'day': day_name})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500