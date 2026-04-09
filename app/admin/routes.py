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


@admin_bp.route('/api/send-welcome-all', methods=['POST'])
def send_welcome_all():
    """
    Send a welcome email to ALL existing registered users.
    Used to verify the mail system is 100% working.

    POST body (optional):
      { "dry_run": true }   →  lists users without sending emails

    Response:
      {
        "success": true,
        "total":   12,
        "sent":    10,
        "failed":  2,
        "results": [
          { "email": "...", "name": "...", "ok": true  },
          { "email": "...", "name": "...", "ok": false, "error": "..." }
        ]
      }
    """
    from core.mailer import send_welcome

    data    = request.get_json() or {}
    dry_run = bool(data.get('dry_run', False))

    sb = get_supabase_admin()
    try:
        resp = sb.table('profiles')\
                 .select('id, email, full_name')\
                 .execute()
        profiles = resp.data or []
    except Exception as e:
        return jsonify({'success': False, 'error': f'Could not fetch profiles: {e}'}), 500

    if not profiles:
        return jsonify({
            'success': True,
            'message': 'No registered users found.',
            'total': 0, 'sent': 0, 'failed': 0, 'results': []
        })

    results = []
    sent    = 0
    failed  = 0

    for p in profiles:
        email = (p.get('email') or '').strip()
        name  = (p.get('full_name') or 'Student').strip() or 'Student'

        if not email:
            failed += 1
            results.append({'email': '(missing)', 'name': name, 'ok': False, 'error': 'No email in profile'})
            continue

        if dry_run:
            results.append({'email': email, 'name': name, 'ok': None, 'dry_run': True})
            continue

        try:
            ok = send_welcome(to_email=email, user_name=name)
            if ok:
                sent += 1
                results.append({'email': email, 'name': name, 'ok': True})
            else:
                failed += 1
                results.append({'email': email, 'name': name, 'ok': False, 'error': 'Mailer returned False'})
        except Exception as e:
            failed += 1
            results.append({'email': email, 'name': name, 'ok': False, 'error': str(e)})

    if dry_run:
        return jsonify({
            'success':  True,
            'dry_run':  True,
            'message':  f'Dry run — {len(profiles)} users found. No emails sent.',
            'total':    len(profiles),
            'sent':     0,
            'failed':   0,
            'results':  results,
        })

    return jsonify({
        'success': True,
        'total':   len(profiles),
        'sent':    sent,
        'failed':  failed,
        'message': f'Done! {sent} emails sent, {failed} failed.',
        'results': results,
    })