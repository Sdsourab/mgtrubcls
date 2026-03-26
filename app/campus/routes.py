from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin

campus_bp = Blueprint('campus', __name__)

@campus_bp.route('/resources')
def resources_page():
    return render_template('modules/resources.html')

@campus_bp.route('/api/resources', methods=['GET'])
def get_resources():
    dept = request.args.get('dept', '')
    subject = request.args.get('subject', '')
    sb = get_supabase_admin()
    try:
        q = sb.table('resources').select('*')
        if dept:
            q = q.eq('dept', dept)
        if subject:
            q = q.ilike('subject', f'%{subject}%')
        resp = q.order('created_at', desc=True).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@campus_bp.route('/api/resources', methods=['POST'])
def upload_resource():
    data = request.get_json()
    sb = get_supabase_admin()
    try:
        payload = {
            'dept': data.get('dept', 'Management'),
            'subject': data.get('subject', ''),
            'file_url': data.get('file_url', ''),
            'title': data.get('title', ''),
            'uploaded_by': data.get('uploaded_by', ''),
        }
        resp = sb.table('resources').insert(payload).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
