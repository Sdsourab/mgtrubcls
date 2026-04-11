"""
app/admin/routes.py
═══════════════════
Admin panel with database-backed authentication.
– POST /admin/api/login          → email + password → session token
– POST /admin/api/logout         → invalidate session token
– POST /admin/api/forgot-password → send reset email
– POST /admin/api/reset-password  → set new password with token
– GET  /admin/api/verify          → check if a session token is valid
All mutating admin endpoints require X-Admin-Token header.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, render_template
from werkzeug.security import generate_password_hash, check_password_hash

from core.supabase_client import get_supabase_admin
from core.excel_parser import parse_routine_excel, parse_routine_word, get_seed_routines, get_seed_mappings
from core.mailer import send_raw
import tempfile

admin_bp = Blueprint('admin', __name__)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _now_utc():
    return datetime.now(timezone.utc)


def _verify_admin_token(token: str) -> bool:
    """Return True if token exists and has not expired."""
    if not token:
        return False
    sb = get_supabase_admin()
    try:
        row = sb.table('admin_sessions') \
                .select('expires_at') \
                .eq('token', token) \
                .single() \
                .execute()
        if not row.data:
            return False
        exp = datetime.fromisoformat(row.data['expires_at'])
        # Make aware if naive
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp > _now_utc()
    except Exception:
        return False


def _require_token():
    """Return (True, None) or (False, error_response)."""
    token = request.headers.get('X-Admin-Token', '').strip()
    if not _verify_admin_token(token):
        return False, (jsonify({'error': 'Unauthorized — invalid or expired session'}), 401)
    return True, None


# ─────────────────────────────────────────────────────────────
# Admin page (GET)
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/')
def admin_page():
    return render_template('modules/admin.html')


# ─────────────────────────────────────────────────────────────
# Auth endpoints
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/api/login', methods=['POST'])
def admin_login():
    data     = request.get_json() or {}
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    sb = get_supabase_admin()
    try:
        row = sb.table('admin_accounts') \
                .select('id, email, password_hash') \
                .eq('email', email) \
                .single() \
                .execute()
    except Exception:
        return jsonify({'error': 'Invalid credentials'}), 401

    if not row.data:
        return jsonify({'error': 'Invalid credentials'}), 401

    if not check_password_hash(row.data['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401

    # Create session — valid for 8 hours
    token   = secrets.token_urlsafe(40)
    expires = (_now_utc() + timedelta(hours=8)).isoformat()
    try:
        sb.table('admin_sessions').insert({
            'token':      token,
            'email':      email,
            'expires_at': expires,
        }).execute()
    except Exception as e:
        return jsonify({'error': f'Session error: {e}'}), 500

    return jsonify({'success': True, 'token': token, 'email': email})


@admin_bp.route('/api/logout', methods=['POST'])
def admin_logout():
    token = request.headers.get('X-Admin-Token', '').strip()
    if token:
        try:
            get_supabase_admin().table('admin_sessions') \
                .delete().eq('token', token).execute()
        except Exception:
            pass
    return jsonify({'success': True})


@admin_bp.route('/api/verify', methods=['GET'])
def admin_verify():
    token = request.headers.get('X-Admin-Token', '').strip()
    if _verify_admin_token(token):
        return jsonify({'valid': True})
    return jsonify({'valid': False}), 401


@admin_bp.route('/api/forgot-password', methods=['POST'])
def admin_forgot_password():
    data  = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    sb = get_supabase_admin()

    # Silently succeed even if email not found (security: don't reveal existence)
    try:
        row = sb.table('admin_accounts').select('id').eq('email', email).single().execute()
        account_exists = bool(row.data)
    except Exception:
        account_exists = False

    if account_exists:
        reset_token = secrets.token_urlsafe(32)
        expires     = (_now_utc() + timedelta(hours=1)).isoformat()
        try:
            # Upsert so only one active reset token per email
            sb.table('admin_password_resets').upsert({
                'email':      email,
                'token':      reset_token,
                'expires_at': expires,
                'used':       False,
            }, on_conflict='email').execute()

            # Build reset link — derive base URL from request
            base = request.host_url.rstrip('/')
            reset_link = f"{base}/admin/?reset_token={reset_token}"

            # Send reset email
            html = f"""
            <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px;">
              <h2 style="color:#1a1a2e;">UniSync Admin — Password Reset</h2>
              <p>A password reset was requested for <strong>{email}</strong>.</p>
              <p style="margin:24px 0;">
                <a href="{reset_link}"
                   style="display:inline-block;padding:12px 28px;background:#BC6F37;color:#fff;
                          border-radius:8px;text-decoration:none;font-weight:700;">
                  Reset Password
                </a>
              </p>
              <p style="color:#888;font-size:.85rem;">
                This link expires in 1 hour. If you didn't request this, ignore this email.
              </p>
            </div>"""
            send_raw(to_email=email, subject='UniSync Admin — Password Reset', html=html)
        except Exception:
            pass  # Don't leak errors

    return jsonify({
        'success': True,
        'message': 'If that email exists, a reset link has been sent.'
    })


@admin_bp.route('/api/reset-password', methods=['POST'])
def admin_reset_password():
    data         = request.get_json() or {}
    reset_token  = data.get('reset_token', '').strip()
    new_password = data.get('new_password', '')

    if not reset_token or not new_password:
        return jsonify({'error': 'Token and new password are required'}), 400
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    sb = get_supabase_admin()
    try:
        row = sb.table('admin_password_resets') \
                .select('*') \
                .eq('token', reset_token) \
                .eq('used', False) \
                .single() \
                .execute()
    except Exception:
        return jsonify({'error': 'Invalid or expired reset token'}), 400

    if not row.data:
        return jsonify({'error': 'Invalid or expired reset token'}), 400

    exp = datetime.fromisoformat(row.data['expires_at'])
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < _now_utc():
        return jsonify({'error': 'Reset token has expired'}), 400

    email         = row.data['email']
    password_hash = generate_password_hash(new_password)

    try:
        sb.table('admin_accounts') \
          .update({'password_hash': password_hash}) \
          .eq('email', email) \
          .execute()

        sb.table('admin_password_resets') \
          .update({'used': True}) \
          .eq('token', reset_token) \
          .execute()

        # Revoke all active sessions for this admin
        sb.table('admin_sessions').delete().eq('email', email).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'success': True, 'message': 'Password updated. Please log in again.'})


# ─────────────────────────────────────────────────────────────
# Existing admin API endpoints (all now require token)
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/api/stats', methods=['GET'])
def get_stats():
    ok, err = _require_token()
    if not ok:
        return err

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


@admin_bp.route('/api/seed-database', methods=['POST'])
def seed_database():
    ok, err = _require_token()
    if not ok:
        return err

    sb = get_supabase_admin()
    try:
        mappings = get_seed_mappings()
        sb.table('mappings').upsert(mappings, on_conflict='code').execute()

        try:
            sb.table('routines').delete() \
              .neq('id', '00000000-0000-0000-0000-000000000000').execute()
        except Exception:
            pass

        routines = get_seed_routines()
        for i in range(0, len(routines), 20):
            sb.table('routines').insert(routines[i:i+20]).execute()

        return jsonify({
            'success': True,
            'message': f'Seeded {len(mappings)} mappings and {len(routines)} routine entries.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/upload-routine', methods=['POST'])
def upload_routine():
    ok, err = _require_token()
    if not ok:
        return err

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file     = request.files['file']
    filename = (file.filename or '').lower()

    if filename.endswith('.docx'):
        suffix = '.docx'
        parser = parse_routine_word
    elif filename.endswith(('.xlsx', '.xls')):
        suffix = '.xlsx'
        parser = parse_routine_excel
    else:
        return jsonify({'error': 'Only .docx (Word) or .xlsx/.xls accepted'}), 400

    sb       = get_supabase_admin()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        entries = parser(tmp_path)

        if not entries:
            return jsonify({'error': 'No entries found. Use official RUB format: '
                            'Day | Room No. | time-slot columns, '
                            'cells like PKP (MGT-3102).'}), 400

        try:
            mappings = get_seed_mappings()
            sb.table('mappings').upsert(mappings, on_conflict='code').execute()
        except Exception:
            pass

        sb.table('routines').delete() \
          .neq('id', '00000000-0000-0000-0000-000000000000').execute()

        for i in range(0, len(entries), 20):
            sb.table('routines').insert(entries[i:i+20]).execute()

        return jsonify({
            'success':  True,
            'inserted': len(entries),
            'format':   'word' if suffix == '.docx' else 'excel',
            'message':  f'Uploaded {len(entries)} routine entries.',
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if tmp_path:
            try: os.unlink(tmp_path)
            except Exception: pass


@admin_bp.route('/api/send-welcome-all', methods=['POST'])
def send_welcome_all():
    ok, err = _require_token()
    if not ok:
        return err

    from core.mailer import send_welcome

    data    = request.get_json() or {}
    dry_run = bool(data.get('dry_run', False))

    sb = get_supabase_admin()
    try:
        resp     = sb.table('profiles').select('id, email, full_name').execute()
        profiles = resp.data or []
    except Exception as e:
        return jsonify({'success': False, 'error': f'Could not fetch profiles: {e}'}), 500

    if not profiles:
        return jsonify({'success': True, 'message': 'No users found.',
                        'total': 0, 'sent': 0, 'failed': 0, 'results': []})

    results, sent, failed = [], 0, 0

    for p in profiles:
        email = (p.get('email') or '').strip()
        name  = (p.get('full_name') or 'Student').strip() or 'Student'
        if not email:
            failed += 1
            results.append({'email': '(missing)', 'name': name, 'ok': False, 'error': 'No email'})
            continue
        if dry_run:
            results.append({'email': email, 'name': name, 'ok': None, 'dry_run': True})
            continue
        try:
            ok2 = send_welcome(to_email=email, user_name=name)
            if ok2:
                sent += 1
                results.append({'email': email, 'name': name, 'ok': True})
            else:
                failed += 1
                results.append({'email': email, 'name': name, 'ok': False, 'error': 'Mailer returned False'})
        except Exception as e:
            failed += 1
            results.append({'email': email, 'name': name, 'ok': False, 'error': str(e)})

    if dry_run:
        return jsonify({'success': True, 'dry_run': True,
                        'message': f'Dry run — {len(profiles)} users found.',
                        'total': len(profiles), 'sent': 0, 'failed': 0, 'results': results})

    return jsonify({'success': True, 'total': len(profiles),
                    'sent': sent, 'failed': failed,
                    'message': f'Done! {sent} sent, {failed} failed.',
                    'results': results})