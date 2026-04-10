"""
app/auth/routes.py
══════════════════
Registration saves program/year/semester immediately to profile.
Welcome email sent via Resend API on successful registration.
Login always returns full profile from DB.

ID FORMAT:
  - student_id is a plain integer (any number, e.g. 12345).
  - Entered by the user at registration time.
  - Acts as their permanent identity number — never changes.
  - Must be numeric and unique across all profiles.
"""

from flask import Blueprint, jsonify, request, render_template, current_app
from core.supabase_client import get_supabase, get_supabase_admin

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login',    methods=['GET'])
def login():        return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET'])
def register():     return render_template('auth/register.html')

@auth_bp.route('/profile',  methods=['GET'])
def profile_page(): return render_template('modules/profile.html')


# ── Login ──────────────────────────────────────────────────────

@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data     = request.get_json() or {}
    email    = data.get('email',    '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    try:
        sb   = get_supabase()
        resp = sb.auth.sign_in_with_password({'email': email, 'password': password})
        user = resp.user
        sess = resp.session

        # Always fetch full profile so year/semester/program is current
        profile = {}
        try:
            p = get_supabase_admin().table('profiles').select('*') \
                    .eq('id', user.id).single().execute()
            profile = p.data or {}
        except Exception:
            pass

        return jsonify({
            'success':      True,
            'access_token': sess.access_token,
            'user': {
                'id':         user.id,
                'email':      user.email,
                'full_name':  profile.get('full_name')  or '',
                'role':       profile.get('role')       or 'student',
                'dept':       profile.get('dept')       or 'Management',
                'program':    profile.get('program')    or 'BBA',
                'year':       profile.get('year')       or 1,
                'semester':   profile.get('semester')   or 1,
                'student_id': profile.get('student_id') or None,
            },
        })
    except Exception as e:
        msg = str(e)
        if 'Invalid login credentials' in msg:
            return jsonify({'error': 'Wrong email or password'}), 401
        if 'Email not confirmed' in msg:
            return jsonify({'error': 'Please verify your email first'}), 401
        return jsonify({'error': msg}), 401


# ── Register ───────────────────────────────────────────────────

@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    data       = request.get_json() or {}
    email      = data.get('email',      '').strip()
    password   = data.get('password',   '')
    full_name  = data.get('full_name',  '').strip()
    dept       = data.get('dept',       'Management')
    program    = data.get('program',    'BBA')
    year       = int(data.get('year',      1))
    semester   = int(data.get('semester',  1))
    student_id = data.get('student_id',  None)   # plain integer from frontend

    # ── Basic required field checks ────────────────────────────
    if not all([email, password, full_name]):
        return jsonify({'error': 'Name, email and password are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    # ── Student ID validation ──────────────────────────────────
    # Must be present and must be a valid integer
    if student_id is None or str(student_id).strip() == '':
        return jsonify({'error': 'Student ID is required'}), 400
    try:
        student_id = int(student_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Student ID must be a number (e.g. 12345)'}), 400
    if student_id <= 0:
        return jsonify({'error': 'Student ID must be a positive number'}), 400

    # ── Year range check ───────────────────────────────────────
    max_year = 4 if program == 'BBA' else 2
    if not (1 <= year <= max_year):
        return jsonify({'error': f'{program} year must be 1–{max_year}'}), 400
    if semester not in [1, 2]:
        return jsonify({'error': 'Semester must be 1 or 2'}), 400

    try:
        sb = get_supabase()

        # ── Uniqueness check: student_id must not already exist ─
        try:
            existing = get_supabase_admin() \
                .table('profiles') \
                .select('id') \
                .eq('student_id', student_id) \
                .execute()
            if existing.data:
                return jsonify({
                    'error': f'Student ID {student_id} is already taken. '
                             f'Please use a different ID number.'
                }), 400
        except Exception as e:
            current_app.logger.warning(f'[Auth] student_id uniqueness check failed: {e}')
            # Non-fatal on check failure — Supabase unique constraint will still catch it

        # ── Create auth user ───────────────────────────────────
        resp = sb.auth.sign_up({
            'email':    email,
            'password': password,
            'options':  {'data': {'full_name': full_name}},
        })
        user = resp.user
        if not user:
            return jsonify({'error': 'Registration failed. Try again.'}), 400

        # ── Save profile with student_id ───────────────────────
        try:
            get_supabase_admin().table('profiles').upsert({
                'id':         user.id,
                'email':      email,
                'full_name':  full_name,
                'role':       'student',
                'dept':       dept,
                'program':    program,
                'year':       year,
                'semester':   semester,
                'student_id': student_id,   # ← permanent integer identity number
            }).execute()
        except Exception as e:
            current_app.logger.warning(f'[Auth] Profile upsert failed: {e}')

        # ── Send welcome email ─────────────────────────────────
        try:
            from core.mailer import send_welcome
            ok = send_welcome(to_email=email, user_name=full_name)
            if not ok:
                current_app.logger.warning(f'[Auth] Welcome email not sent to {email}')
        except Exception as e:
            current_app.logger.warning(f'[Auth] Welcome email error: {e}')
            # Non-fatal — registration still succeeds

        return jsonify({
            'success': True,
            'message': 'Account created! Check your email to verify, then sign in.',
        })

    except Exception as e:
        msg = str(e)
        if 'already registered' in msg or 'already exists' in msg:
            return jsonify({'error': 'This email is already registered'}), 400
        return jsonify({'error': msg}), 400


# ── Profile ────────────────────────────────────────────────────

@auth_bp.route('/api/profile', methods=['GET'])
def get_profile():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    try:
        resp = get_supabase_admin().table('profiles').select('*').eq('id', user_id).single().execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/api/profile', methods=['PATCH'])
def update_profile():
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    # Build update payload — student_id is NOT patchable after registration
    allowed = {'full_name', 'dept', 'program', 'year', 'semester', 'role',
               'push_subscription', 'avatar_url', 'bio'}
    payload = {k: v for k, v in data.items() if k in allowed}

    if not payload:
        return jsonify({'error': 'No valid fields to update'}), 400

    try:
        resp = get_supabase_admin().table('profiles').update(payload).eq('id', user_id).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500