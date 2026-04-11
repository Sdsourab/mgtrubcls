from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin

campus_bp = Blueprint('campus', __name__)


@campus_bp.route('/resources')
def resources_page():
    return render_template('modules/resources.html')


@campus_bp.route('/api/resources', methods=['GET'])
def get_resources():
    dept    = request.args.get('dept', '')
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
    data = request.get_json() or {}
    sb   = get_supabase_admin()
    try:
        payload = {
            'dept':             data.get('dept', 'Management'),
            'subject':          data.get('subject', ''),
            'file_url':         data.get('file_url', ''),
            'title':            data.get('title', ''),
            'uploaded_by':      data.get('uploaded_by', ''),
            'uploader_user_id': data.get('uploader_user_id', ''),
        }
        resp = sb.table('resources').insert(payload).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@campus_bp.route('/api/resources/<int:resource_id>', methods=['DELETE'])
def delete_resource(resource_id):
    """
    Only the original uploader can delete their resource.
    The caller must pass ?user_id=<uuid> so we can verify ownership.
    """
    user_id = request.args.get('user_id', '').strip()
    sb      = get_supabase_admin()

    try:
        # Fetch the resource first
        row = sb.table('resources').select('uploader_user_id') \
                .eq('id', resource_id).single().execute()

        if not row.data:
            return jsonify({'success': False, 'error': 'Resource not found'}), 404

        stored_uid = (row.data.get('uploader_user_id') or '').strip()

        # If we have a stored user_id, enforce ownership
        if stored_uid and stored_uid != user_id:
            return jsonify({'success': False, 'error': 'You can only delete your own resources'}), 403

        sb.table('resources').delete().eq('id', resource_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500