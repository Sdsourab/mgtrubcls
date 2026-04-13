"""
app/campus/routes.py
────────────────────
Resources — semester-aware, teacher upload/delete.
Teachers can add resources for a specific semester.
Students see resources filtered by their semester.
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin

campus_bp = Blueprint('campus', __name__)


def _get_profile(user_id: str) -> dict:
    if not user_id:
        return {}
    try:
        sb  = get_supabase_admin()
        row = sb.table('profiles').select('*').eq('id', user_id).single().execute()
        return row.data or {}
    except Exception:
        return {}


@campus_bp.route('/resources')
def resources_page():
    return render_template('modules/resources.html')


@campus_bp.route('/api/resources', methods=['GET'])
def get_resources():
    dept     = request.args.get('dept', '')
    subject  = request.args.get('subject', '')
    program  = request.args.get('program', '')
    year     = request.args.get('year', '')
    semester = request.args.get('semester', '')

    sb = get_supabase_admin()
    try:
        q = sb.table('resources').select('*')
        if dept:
            q = q.eq('dept', dept)
        if subject:
            q = q.ilike('subject', f'%{subject}%')
        # Semester filter: show resources for this semester OR NULL (all semesters)
        if semester:
            q = q.or_(f'target_semester.eq.{semester},target_semester.is.null')
        if year:
            q = q.or_(f'target_year.eq.{year},target_year.is.null')
        if program:
            q = q.or_(f'program.eq.{program},program.is.null,program.eq.ALL')

        resp = q.order('created_at', desc=True).execute()
        return jsonify({'success': True, 'data': resp.data or []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@campus_bp.route('/api/resources', methods=['POST'])
def upload_resource():
    data    = request.get_json() or {}
    user_id = data.get('uploader_user_id', '').strip()
    profile = _get_profile(user_id) if user_id else {}
    role    = profile.get('role', 'student')

    sb = get_supabase_admin()
    try:
        target_year     = data.get('target_year')
        target_semester = data.get('target_semester')

        payload = {
            'dept':             data.get('dept', 'Management'),
            'subject':          data.get('subject', ''),
            'file_url':         data.get('file_url', ''),
            'title':            data.get('title', ''),
            'uploaded_by':      data.get('uploaded_by', 'Anonymous'),
            'uploader_user_id': user_id,
            'program':          data.get('program') or profile.get('program') or 'ALL',
            'target_year':      int(target_year)     if target_year     else None,
            'target_semester':  int(target_semester) if target_semester else None,
            'uploaded_by_role': role,
        }
        resp = sb.table('resources').insert(payload).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@campus_bp.route('/api/resources/<int:resource_id>', methods=['DELETE'])
def delete_resource(resource_id):
    user_id = request.args.get('user_id', '').strip()
    sb      = get_supabase_admin()

    try:
        row = sb.table('resources').select('uploader_user_id') \
                .eq('id', resource_id).single().execute()

        if not row.data:
            return jsonify({'success': False, 'error': 'Resource not found'}), 404

        stored_uid = (row.data.get('uploader_user_id') or '').strip()
        profile    = _get_profile(user_id)

        if profile.get('role') != 'admin':
            if stored_uid and stored_uid != user_id:
                return jsonify({'success': False, 'error': 'You can only delete your own resources'}), 403

        sb.table('resources').delete().eq('id', resource_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500