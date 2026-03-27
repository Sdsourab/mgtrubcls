from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from core.excel_parser import parse_routine_excel, get_seed_routines, get_seed_mappings
import tempfile, os

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
def admin_page():
    return render_template('modules/admin.html')


@admin_bp.route('/api/seed-database', methods=['POST'])
def seed_database():
    sb = get_supabase_admin()
    try:
        # Seed mappings
        mappings = get_seed_mappings()
        sb.table('mappings').upsert(mappings, on_conflict='code').execute()

        # Clear routines and re-seed with correct metadata
        try:
            sb.table('routines').delete()\
              .neq('id', '00000000-0000-0000-0000-000000000000').execute()
        except Exception:
            pass

        routines = get_seed_routines()
        # Insert in batches of 20
        for i in range(0, len(routines), 20):
            batch = routines[i:i+20]
            sb.table('routines').insert(batch).execute()

        return jsonify({
            'success': True,
            'message': f'Seeded {len(mappings)} mappings and {len(routines)} routine entries with program/year/semester data.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/stats', methods=['GET'])
def get_stats():
    sb = get_supabase_admin()
    try:
        r = len(sb.table('routines').select('id').execute().data)
        m = len(sb.table('mappings').select('code').execute().data)
        u = len(sb.table('profiles').select('id').execute().data)
        t = len(sb.table('tasks').select('id').execute().data)
        return jsonify({'success': True, 'stats': {
            'routines': r, 'mappings': m, 'users': u, 'tasks': t
        }})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/upload-routine', methods=['POST'])
def upload_routine():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'Only .xlsx/.xls accepted'}), 400

    sb = get_supabase_admin()
    try:
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        entries = parse_routine_excel(tmp_path)
        os.unlink(tmp_path)

        if not entries:
            return jsonify({'error': 'No valid entries found'}), 400

        sb.table('routines').delete()\
          .neq('id', '00000000-0000-0000-0000-000000000000').execute()
        sb.table('routines').insert(entries).execute()
        return jsonify({'success': True, 'inserted': len(entries)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500