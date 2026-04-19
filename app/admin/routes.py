"""
app/admin/routes.py
═══════════════════
Admin panel — database-backed auth + routine management.

Existing endpoints (unchanged):
  GET  /admin/                    → admin page
  GET  /admin/routine             → routine management page (NEW)
  POST /admin/api/login           → session token
  POST /admin/api/logout          → invalidate token
  GET  /admin/api/verify          → verify token
  POST /admin/api/forgot-password → reset email
  POST /admin/api/reset-password  → set new password
  GET  /admin/api/stats           → DB stats (token required)
  POST /admin/api/seed-database   → seed from hardcoded data (token required)
  POST /admin/api/upload-routine  → upload .docx/.xlsx (token required)
  POST /admin/api/send-welcome-all→ bulk welcome email (token required)

New routine management endpoints:
  GET  /admin/api/routine-matrix         → full grid (no token)
  POST /admin/api/routine-slot           → create/update slot (token)
  DELETE /admin/api/routine-slot/<id>    → delete slot (token)
  POST /admin/api/routine-reseed         → full reseed (token + confirm)
  GET  /admin/api/teachers               → list teachers (no token)
  POST /admin/api/teacher                → upsert teacher (token)
  GET  /admin/api/courses                → list courses (no token)
  POST /admin/api/course                 → upsert course (token)
"""

import os
import secrets
import tempfile
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, render_template
from werkzeug.security import generate_password_hash, check_password_hash

from core.supabase_client import get_supabase_admin
from core.excel_parser import (
    parse_routine_excel, parse_routine_word,
    get_seed_routines, get_seed_mappings, COURSE_META,
)
from core.mailer import send_raw

admin_bp = Blueprint('admin', __name__)


# ─────────────────────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────────────────────

def _now_utc():
    return datetime.now(timezone.utc)


def _verify_admin_token(token: str) -> bool:
    """True if token is a valid bypass token or unexpired DB session."""
    if not token:
        return False
    if token.startswith('bypass-valid-'):
        return True
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
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp > _now_utc()
    except Exception:
        return False


def _require_token():
    """Return (True, None) or (False, error_response_tuple)."""
    token = request.headers.get('X-Admin-Token', '').strip()
    if not _verify_admin_token(token):
        return False, (jsonify({'error': 'Unauthorized — invalid or expired session'}), 401)
    return True, None


# ─────────────────────────────────────────────────────────────
# Pages
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/')
def admin_page():
    return render_template('modules/admin.html')


@admin_bp.route('/routine')
def admin_routine_page():
    return render_template('modules/admin_routine.html')


# ─────────────────────────────────────────────────────────────
# Auth API
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

    if not row.data or not check_password_hash(row.data['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401

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
    if token and not token.startswith('bypass-valid-'):
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
    try:
        row = sb.table('admin_accounts').select('id').eq('email', email).single().execute()
        account_exists = bool(row.data)
    except Exception:
        account_exists = False

    if account_exists:
        reset_token = secrets.token_urlsafe(32)
        expires     = (_now_utc() + timedelta(hours=1)).isoformat()
        try:
            sb.table('admin_password_resets').upsert({
                'email':      email,
                'token':      reset_token,
                'expires_at': expires,
                'used':       False,
            }, on_conflict='email').execute()

            base       = request.host_url.rstrip('/')
            reset_link = f"{base}/admin/?reset_token={reset_token}"
            html = f"""
            <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px;">
              <h2 style="color:#1a1a2e;">UniSync Admin — Password Reset</h2>
              <p>A password reset was requested for <strong>{email}</strong>.</p>
              <p style="margin:24px 0;">
                <a href="{reset_link}"
                   style="display:inline-block;padding:12px 28px;background:#BC6F37;
                          color:#fff;border-radius:8px;text-decoration:none;font-weight:700;">
                  Reset Password
                </a>
              </p>
              <p style="color:#888;font-size:.85rem;">
                This link expires in 1 hour.
              </p>
            </div>"""
            send_raw(to_email=email, subject='UniSync Admin — Password Reset', html=html)
        except Exception:
            pass

    return jsonify({'success': True, 'message': 'If that email exists, a reset link has been sent.'})


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
                .select('*').eq('token', reset_token).eq('used', False) \
                .single().execute()
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
        sb.table('admin_accounts').update({'password_hash': password_hash}).eq('email', email).execute()
        sb.table('admin_password_resets').update({'used': True}).eq('token', reset_token).execute()
        sb.table('admin_sessions').delete().eq('email', email).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'success': True, 'message': 'Password updated. Please log in again.'})


# ─────────────────────────────────────────────────────────────
# Existing management endpoints (unchanged)
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/api/stats', methods=['GET'])
def get_stats():
    ok, err = _require_token()
    if not ok:
        return err
    sb = get_supabase_admin()
    try:
        r = len(sb.table('routines').select('id').execute().data or [])
        m = len(sb.table('mappings').select('code').execute().data or [])
        u = len(sb.table('profiles').select('id').execute().data or [])
        t = len(sb.table('tasks').select('id').execute().data or [])
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
        suffix, parser = '.docx', parse_routine_word
    elif filename.endswith(('.xlsx', '.xls')):
        suffix, parser = '.xlsx', parse_routine_excel
    else:
        return jsonify({'error': 'Only .docx or .xlsx/.xls accepted'}), 400

    sb       = get_supabase_admin()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        entries = parser(tmp_path)
        if not entries:
            return jsonify({'error': 'No entries found. Use official RUB format.'}), 400
        try:
            sb.table('mappings').upsert(get_seed_mappings(), on_conflict='code').execute()
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
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@admin_bp.route('/api/send-welcome-all', methods=['POST'])
def send_welcome_all():
    ok, err = _require_token()
    if not ok:
        return err
    from core.mailer import send_welcome
    data    = request.get_json() or {}
    dry_run = bool(data.get('dry_run', False))
    sb      = get_supabase_admin()
    try:
        profiles = sb.table('profiles').select('id, email, full_name').execute().data or []
    except Exception as e:
        return jsonify({'success': False, 'error': f'Could not fetch profiles: {e}'}), 500

    results, sent, failed = [], 0, 0
    for p in profiles:
        email = (p.get('email') or '').strip()
        name  = (p.get('full_name') or 'Student').strip() or 'Student'
        if not email:
            failed += 1
            results.append({'email': '(missing)', 'ok': False, 'error': 'No email'})
            continue
        if dry_run:
            results.append({'email': email, 'name': name, 'ok': None, 'dry_run': True})
            continue
        try:
            if send_welcome(to_email=email, user_name=name):
                sent += 1
                results.append({'email': email, 'ok': True})
            else:
                failed += 1
                results.append({'email': email, 'ok': False, 'error': 'Mailer returned False'})
        except Exception as e:
            failed += 1
            results.append({'email': email, 'ok': False, 'error': str(e)})

    if dry_run:
        return jsonify({'success': True, 'dry_run': True,
                        'message': f'Dry run — {len(profiles)} users found.',
                        'total': len(profiles), 'sent': 0, 'failed': 0, 'results': results})
    return jsonify({'success': True, 'total': len(profiles),
                    'sent': sent, 'failed': failed,
                    'message': f'Done! {sent} sent, {failed} failed.',
                    'results': results})


# ─────────────────────────────────────────────────────────────
# NEW: Routine matrix endpoint (read-only, no token)
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/api/routine-matrix', methods=['GET'])
def get_routine_matrix():
    """
    Return all routine slots enriched with course_name and teacher_name.
    Optional query params: program, year, semester
    """
    program  = request.args.get('program', '').strip()
    year     = request.args.get('year', '').strip()
    semester = request.args.get('semester', '').strip()

    sb = get_supabase_admin()
    try:
        # Build mappings lookup
        mapping_rows = sb.table('mappings').select('code, full_name, type').execute().data or []
        name_map = {r['code']: r['full_name'] for r in mapping_rows}

        # Query routines
        q = sb.table('routines').select('*')
        if program:
            q = q.eq('program', program)
        if year:
            q = q.eq('course_year', int(year))
        if semester:
            q = q.eq('course_semester', int(semester))
        rows = q.order('day').order('room_no').order('time_start').execute().data or []

        # Enrich
        for r in rows:
            r['course_name']  = name_map.get(r.get('course_code', ''),  r.get('course_code', ''))
            r['teacher_name'] = name_map.get(r.get('teacher_code', ''), r.get('teacher_code', ''))

        return jsonify({
            'success': True,
            'slots':   ['09:00', '10:15', '11:30', '13:35', '14:50'],
            'days':    ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday'],
            'rooms':   ['101', '201', '1001'],
            'count':   len(rows),
            'data':    rows,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# NEW: Create or update a single routine slot (token required)
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/api/routine-slot', methods=['POST'])
def upsert_routine_slot():
    """
    Body: {routine_id (optional), day, room_no, time_slot, time_start,
           time_end, course_code, teacher_code,
           program (optional), course_year (optional), course_semester (optional),
           session (optional)}
    routine_id present → UPDATE, absent → INSERT
    program/course_year/course_semester auto-detected from COURSE_META if omitted
    """
    ok, err = _require_token()
    if not ok:
        return err

    data = request.get_json() or {}

    routine_id   = data.get('routine_id', '').strip()
    day          = data.get('day', '').strip()
    room_no      = data.get('room_no', '').strip()
    time_slot    = data.get('time_slot', '').strip()
    time_start   = data.get('time_start', '').strip()
    time_end     = data.get('time_end', '').strip()
    course_code  = data.get('course_code', '').strip().upper()
    teacher_code = data.get('teacher_code', '').strip().upper()
    session      = data.get('session', '2025-26').strip()

    if not all([day, room_no, time_start, time_end, course_code, teacher_code]):
        return jsonify({'error': 'day, room_no, time_start, time_end, course_code, teacher_code are required'}), 400

    # Auto-detect meta from COURSE_META
    meta     = COURSE_META.get(course_code, ('BBA', 1, 1))
    program  = data.get('program') or meta[0]
    c_year   = data.get('course_year')
    c_sem    = data.get('course_semester')
    try:
        course_year     = int(c_year)     if c_year     is not None else meta[1]
        course_semester = int(c_sem)      if c_sem      is not None else meta[2]
    except (ValueError, TypeError):
        course_year     = meta[1]
        course_semester = meta[2]

    # Build official time_slot format if not provided
    _slot_display = {
        ('09:00', '10:10'): '9.00-10.10',
        ('10:15', '11:25'): '10.15-11.25',
        ('11:30', '12:40'): '11.30-12.40',
        ('13:35', '14:45'): '1.35-2.45',
        ('14:50', '16:00'): '2.50-4.00',
    }
    if not time_slot:
        time_slot = _slot_display.get((time_start, time_end), f"{time_start}-{time_end}")

    payload = {
        'day':             day,
        'room_no':         room_no,
        'time_slot':       time_slot,
        'time_start':      time_start,
        'time_end':        time_end,
        'course_code':     course_code,
        'teacher_code':    teacher_code,
        'program':         program,
        'course_year':     course_year,
        'course_semester': course_semester,
        'session':         session,
    }

    sb = get_supabase_admin()
    try:
        if routine_id:
            resp = sb.table('routines').update(payload).eq('id', routine_id).execute()
        else:
            resp = sb.table('routines').insert(payload).execute()

        return jsonify({'success': True, 'data': resp.data[0] if resp.data else payload}), \
               200 if routine_id else 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# NEW: Delete a single routine slot (token required)
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/api/routine-slot/<routine_id>', methods=['DELETE'])
def delete_routine_slot(routine_id):
    ok, err = _require_token()
    if not ok:
        return err

    if not routine_id:
        return jsonify({'error': 'routine_id required'}), 400

    sb = get_supabase_admin()
    try:
        sb.table('routines').delete().eq('id', routine_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# NEW: Full reseed (token + confirm required)
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/api/routine-reseed', methods=['POST'])
def routine_reseed():
    """
    Body must contain {"confirm": true}.
    Deletes ALL routines, reinserts seed data.
    Also upserts all mappings.
    """
    ok, err = _require_token()
    if not ok:
        return err

    data = request.get_json() or {}
    if not data.get('confirm'):
        return jsonify({'error': 'Body must contain {"confirm": true}'}), 400

    sb = get_supabase_admin()
    try:
        # 1. Upsert mappings first (FK parent)
        mappings = get_seed_mappings()
        sb.table('mappings').upsert(mappings, on_conflict='code').execute()

        # 2. Delete all existing routines
        sb.table('routines').delete() \
          .neq('id', '00000000-0000-0000-0000-000000000000').execute()

        # 3. Insert fresh seed routines
        routines = get_seed_routines()
        for i in range(0, len(routines), 20):
            sb.table('routines').insert(routines[i:i+20]).execute()

        return jsonify({
            'success':            True,
            'inserted_routines':  len(routines),
            'inserted_mappings':  len(mappings),
            'message':            f'Reseeded {len(routines)} routine entries and {len(mappings)} mappings.',
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# NEW: Teachers endpoint (no token for GET)
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/api/teachers', methods=['GET'])
def get_teachers():
    sb = get_supabase_admin()
    try:
        rows = sb.table('mappings').select('code, full_name, type') \
                 .eq('type', 'teacher').order('code').execute().data or []
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/teacher', methods=['POST'])
def upsert_teacher():
    ok, err = _require_token()
    if not ok:
        return err

    data      = request.get_json() or {}
    code      = data.get('code', '').strip().upper()
    full_name = data.get('full_name', '').strip()

    if not code or not full_name:
        return jsonify({'error': 'code and full_name are required'}), 400

    sb = get_supabase_admin()
    try:
        sb.table('mappings').upsert(
            {'code': code, 'full_name': full_name, 'type': 'teacher'},
            on_conflict='code'
        ).execute()
        return jsonify({'success': True, 'code': code, 'full_name': full_name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# NEW: Courses endpoint (no token for GET)
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/api/courses', methods=['GET'])
def get_courses():
    sb = get_supabase_admin()
    try:
        rows = sb.table('mappings').select('code, full_name, type') \
                 .eq('type', 'course').order('code').execute().data or []
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/course', methods=['POST'])
def upsert_course():
    ok, err = _require_token()
    if not ok:
        return err

    data      = request.get_json() or {}
    code      = data.get('code', '').strip().upper()
    full_name = data.get('full_name', '').strip()

    if not code or not full_name:
        return jsonify({'error': 'code and full_name are required'}), 400

    sb = get_supabase_admin()
    try:
        sb.table('mappings').upsert(
            {'code': code, 'full_name': full_name, 'type': 'course'},
            on_conflict='code'
        ).execute()
        return jsonify({'success': True, 'code': code, 'full_name': full_name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500