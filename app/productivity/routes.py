from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import datetime, timezone

productivity_bp = Blueprint('productivity', __name__)

@productivity_bp.route('/tasks')
def tasks_page():
    return render_template('modules/tasks.html')

@productivity_bp.route('/api/tasks', methods=['GET'])
def get_tasks():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    sb = get_supabase_admin()
    try:
        resp = sb.table('tasks').select('*').eq('user_id', user_id).order('deadline').execute()
        tasks = resp.data

        # Auto-flag urgent tasks (deadline within 2 hours)
        now = datetime.now(timezone.utc)
        for t in tasks:
            if t.get('deadline') and t.get('status') != 'done':
                try:
                    dl = datetime.fromisoformat(t['deadline'].replace('Z', '+00:00'))
                    diff = (dl - now).total_seconds() / 3600
                    if 0 < diff <= 2:
                        t['urgent_flag'] = True
                    else:
                        t['urgent_flag'] = False
                except Exception:
                    t['urgent_flag'] = False
            else:
                t['urgent_flag'] = False

        return jsonify({'success': True, 'data': tasks})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@productivity_bp.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.get_json()
    required = ['user_id', 'title']
    if not all(k in data for k in required):
        return jsonify({'error': 'user_id and title are required'}), 400

    sb = get_supabase_admin()
    try:
        payload = {
            'user_id': data['user_id'],
            'title': data['title'],
            'description': data.get('description', ''),
            'deadline': data.get('deadline'),
            'priority': data.get('priority', 'medium'),
            'status': 'pending',
            'course_code': data.get('course_code', ''),
        }
        resp = sb.table('tasks').insert(payload).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@productivity_bp.route('/api/tasks/<task_id>', methods=['PATCH'])
def update_task(task_id):
    data = request.get_json()
    sb = get_supabase_admin()
    try:
        resp = sb.table('tasks').update(data).eq('id', task_id).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@productivity_bp.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    sb = get_supabase_admin()
    try:
        sb.table('tasks').delete().eq('id', task_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@productivity_bp.route('/api/unicover', methods=['POST'])
def generate_cover():
    """Generate UniCover data by fetching user profile + course info."""
    data = request.get_json()
    user_id = data.get('user_id')
    course_code = data.get('course_code', '')

    sb = get_supabase_admin()
    try:
        profile_resp = sb.table('profiles').select('*').eq('id', user_id).single().execute()
        profile = profile_resp.data

        course_resp = sb.table('mappings').select('full_name').eq('code', course_code).execute()
        course_name = course_resp.data[0]['full_name'] if course_resp.data else course_code

        return jsonify({
            'success': True,
            'cover_data': {
                'student_name': profile.get('full_name', ''),
                'student_id': profile.get('student_id', ''),
                'dept': profile.get('dept', ''),
                'batch': profile.get('batch', ''),
                'course_code': course_code,
                'course_name': course_name,
                'university': 'Rabindra University, Bangladesh',
                'department': 'Department of Management',
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@productivity_bp.route('/unicover')
def unicover_page():
    return render_template('modules/unicover.html')
