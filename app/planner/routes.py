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
    Check if a personal plan conflicts with university classes.
    Returns conflicting classes so the frontend can call AI API.
    """
    data       = request.get_json()
    plan_date  = data.get('date', '')
    start_time = data.get('start_time', '')
    end_time   = data.get('end_time', '')
    program    = data.get('program', 'BBA')

    if not all([plan_date, start_time, end_time]):
        return jsonify({'error': 'date, start_time, end_time required'}), 400

    try:
        d = datetime.strptime(plan_date, '%Y-%m-%d')
        day_name = d.strftime('%A')
    except Exception:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    if day_name not in ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']:
        return jsonify({'success': True, 'conflicts': [], 'message': 'No university classes on this day.'})

    # Normalize times
    def norm(t):
        p = t.split(':')
        return f"{p[0].zfill(2)}:{p[1].zfill(2)}"

    s = norm(start_time)
    e = norm(end_time)

    sb = get_supabase_admin()
    try:
        # Overlap: class_start < plan_end AND class_end > plan_start
        resp = sb.table('routines').select('*')\
            .eq('day', day_name)\
            .in_('program', [program, 'ALL'])\
            .lt('time_start', e)\
            .gt('time_end', s)\
            .execute()

        rows = resp.data or []
        for row in rows:
            c = sb.table('mappings').select('full_name').eq('code', row.get('course_code', '')).execute()
            t = sb.table('mappings').select('full_name').eq('code', row.get('teacher_code', '')).execute()
            row['course_name']  = c.data[0]['full_name'] if c.data else row.get('course_code', '')
            row['teacher_name'] = t.data[0]['full_name'] if t.data else row.get('teacher_code', '')

        return jsonify({'success': True, 'conflicts': rows, 'day': day_name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500