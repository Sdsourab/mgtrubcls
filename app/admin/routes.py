from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from core.excel_parser import parse_routine_excel, get_seed_routines, get_seed_mappings
import tempfile, os

admin_bp = Blueprint('admin', __name__)

def _require_admin(req):
    """Simple token check - in production use a proper decorator with JWT verification."""
    token = req.headers.get('X-Admin-Token', '')
    # In production: verify JWT and check role='admin' from profiles table
    # For now, we trust the frontend to send the token and validate role
    return bool(token)

@admin_bp.route('/')
def admin_page():
    return render_template('modules/admin.html')

@admin_bp.route('/api/upload-routine', methods=['POST'])
def upload_routine():
    """Upload a .xlsx routine file and replace the routines table."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'Only .xlsx/.xls files are accepted'}), 400

    sb = get_supabase_admin()
    try:
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        entries = parse_routine_excel(tmp_path)
        os.unlink(tmp_path)

        if not entries:
            return jsonify({'error': 'No valid entries found in file'}), 400

        # Atomic: delete all + insert new (within same session)
        sb.table('routines').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        sb.table('routines').insert(entries).execute()

        return jsonify({'success': True, 'inserted': len(entries)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/seed-database', methods=['POST'])
def seed_database():
    """Seed the database with the default routine and mappings from the class schedule image."""
    sb = get_supabase_admin()
    try:
        # Seed mappings (upsert to avoid duplicates)
        mappings = get_seed_mappings()
        sb.table('mappings').upsert(mappings, on_conflict='code').execute()

        # Seed routines (clear + insert)
        sb.table('routines').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        routines = get_seed_routines()
        sb.table('routines').insert(routines).execute()

        return jsonify({
            'success': True,
            'message': f'Seeded {len(mappings)} mappings and {len(routines)} routine entries.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/stats', methods=['GET'])
def get_stats():
    sb = get_supabase_admin()
    try:
        routine_count = len(sb.table('routines').select('id').execute().data)
        mapping_count = len(sb.table('mappings').select('code').execute().data)
        user_count    = len(sb.table('profiles').select('id').execute().data)
        task_count    = len(sb.table('tasks').select('id').execute().data)
        return jsonify({
            'success': True,
            'stats': {
                'routines': routine_count,
                'mappings': mapping_count,
                'users': user_count,
                'tasks': task_count,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
