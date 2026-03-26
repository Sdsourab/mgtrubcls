from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin

academic_bp = Blueprint('academic', __name__)

@academic_bp.route('/routine')
def routine_page():
    return render_template('modules/routine.html')

@academic_bp.route('/api/routine', methods=['GET'])
def get_routine():
    """Return full routine optionally filtered by day."""
    day = request.args.get('day', '')
    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*, mappings!routines_course_code_fkey(full_name), teacher:mappings!routines_teacher_code_fkey(full_name)')
        if day:
            q = q.eq('day', day)
        resp = q.order('time_start').execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        # Fallback: return basic routine without joins
        try:
            q2 = sb.table('routines').select('*')
            if day:
                q2 = q2.eq('day', day)
            resp2 = q2.order('time_start').execute()
            return jsonify({'success': True, 'data': resp2.data})
        except Exception as e2:
            return jsonify({'success': False, 'error': str(e2)}), 500

@academic_bp.route('/api/live-class', methods=['GET'])
def get_live_class():
    """Return the currently running class based on day and time."""
    day = request.args.get('day', '')
    time_now = request.args.get('time', '')  # HH:MM format

    if not day or not time_now:
        return jsonify({'success': False, 'error': 'day and time params required'}), 400

    sb = get_supabase_admin()
    try:
        resp = sb.table('routines').select('*').eq('day', day)\
            .lte('time_start', time_now).gte('time_end', time_now).execute()
        data = resp.data
        if not data:
            return jsonify({'success': True, 'live': None})

        # Enrich with mappings
        enriched = []
        for row in data:
            c_resp = sb.table('mappings').select('full_name').eq('code', row['course_code']).execute()
            t_resp = sb.table('mappings').select('full_name').eq('code', row['teacher_code']).execute()
            row['course_name'] = c_resp.data[0]['full_name'] if c_resp.data else row['course_code']
            row['teacher_name'] = t_resp.data[0]['full_name'] if t_resp.data else row['teacher_code']
            enriched.append(row)

        return jsonify({'success': True, 'live': enriched})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@academic_bp.route('/api/time-search', methods=['GET'])
def time_search():
    """Find classes at a specific time."""
    time_query = request.args.get('time', '')
    day = request.args.get('day', '')

    if not time_query:
        return jsonify({'error': 'time param required'}), 400

    # Normalize HH:MM
    parts = time_query.split(':')
    if len(parts) == 2:
        hour = parts[0].zfill(2)
        minute = parts[1].zfill(2)
        time_norm = f"{hour}:{minute}"
    else:
        return jsonify({'error': 'Invalid time format. Use HH:MM'}), 400

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*').lte('time_start', time_norm).gte('time_end', time_norm)
        if day:
            q = q.eq('day', day)
        resp = q.execute()

        enriched = []
        for row in resp.data:
            c_resp = sb.table('mappings').select('full_name').eq('code', row['course_code']).execute()
            t_resp = sb.table('mappings').select('full_name').eq('code', row['teacher_code']).execute()
            row['course_name'] = c_resp.data[0]['full_name'] if c_resp.data else row['course_code']
            row['teacher_name'] = t_resp.data[0]['full_name'] if t_resp.data else row['teacher_code']
            enriched.append(row)

        return jsonify({'success': True, 'data': enriched})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@academic_bp.route('/api/mappings', methods=['GET'])
def get_mappings():
    sb = get_supabase_admin()
    try:
        resp = sb.table('mappings').select('*').execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@academic_bp.route('/courses')
def courses_page():
    return render_template('modules/courses.html')
