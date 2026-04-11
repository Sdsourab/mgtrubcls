"""
app/auth/routes.py
══════════════════
Handles student AND teacher registration/login.
– /auth/api/register          → student registration
– /auth/api/register-teacher  → teacher registration (role='teacher')
– /auth/api/profile-check     → returns whether profile is complete (for auto-redirect)
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

        profile = {}
        try:
            p = get_supabase_admin().table('profiles').select('*') \
                    .eq('id', user.id).single().execute()
            profile = p.data or {}
        except Exception:
            pass

        role = profile.get('role') or 'student'

        return jsonify({
            'success':      True,
            'access_token': sess.access_token,
            'user': {
                'id':        user.id,
                'email':     user.email,
                'full_name': profile.get('full_name') or '',
                'role':      role,
                'dept':      profile.get('dept')      or 'Management',
                'program':   profile.get('program')   or 'BBA',
                'year':      profile.get('year')      or 1,
                'semester':  profile.get('semester')  or 1,
                # profile_complete lets the frontend decide whether to redirect to registration
                'profile_complete': bool(
                    profile.get('full_name') and (
                        role == 'teacher' or
                        (profile.get('program') and profile.get('year') and profile.get('semester'))
                    )
                ),
            },
        })
    except Exception as e:
        msg = str(e)
        if 'Invalid login credentials' in msg:
            return jsonify({'error': 'Wrong email or password'}), 401
        if 'Email not confirmed' in msg:
            return jsonify({'error': 'Please verify your email first'}), 401
        return jsonify({'error': msg}), 401


# ── Student Register ───────────────────────────────────────────

@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    data      = request.get_json() or {}
    email     = data.get('email',     '').strip()
    password  = data.get('password',  '')
    full_name = data.get('full_name', '').strip()
    dept      = data.get('dept',      'Management')
    program   = data.get('program',   'BBA')
    year      = int(data.get('year',     1))
    semester  = int(data.get('semester', 1))

    if not all([email, password, full_name]):
        return jsonify({'error': 'All fields are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    max_year = 4 if program == 'BBA' else 2
    if not (1 <= year <= max_year):
        return jsonify({'error': f'{program} year must be 1–{max_year}'}), 400
    if semester not in [1, 2]:
        return jsonify({'error': 'Semester must be 1 or 2'}), 400

    try:
        sb   = get_supabase()
        resp = sb.auth.sign_up({
            'email':    email,
            'password': password,
            'options':  {'data': {'full_name': full_name}},
        })
        user = resp.user
        if not user:
            return jsonify({'error': 'Registration failed. Try again.'}), 400

        try:
            get_supabase_admin().table('profiles').upsert({
                'id':        user.id,
                'email':     email,
                'full_name': full_name,
                'role':      'student',
                'dept':      dept,
                'program':   program,
                'year':      year,
                'semester':  semester,
            }).execute()
        except Exception as e:
            current_app.logger.warning(f'[Auth] Profile upsert failed: {e}')

        try:
            from core.mailer import send_welcome
            send_welcome(to_email=email, user_name=full_name)
        except Exception:
            pass

        return jsonify({
            'success': True,
            'message': 'Account created! Check your email to verify, then sign in.',
        })

    except Exception as e:
        msg = str(e)
        if 'already registered' in msg or 'already exists' in msg:
            return jsonify({'error': 'This email is already registered'}), 400
        return jsonify({'error': msg}), 400


# ── Teacher Register ───────────────────────────────────────────

@auth_bp.route('/api/register-teacher', methods=['POST'])
def api_register_teacher():
    """
    Register a new teacher account.
    Creates Supabase auth user + profiles row (role='teacher')
    + teacher_profiles row (degree, designation, teacher_code).
    """
    data         = request.get_json() or {}
    email        = data.get('email',        '').strip()
    password     = data.get('password',     '')
    full_name    = data.get('full_name',    '').strip()
    degree       = data.get('degree',       '').strip()
    designation  = data.get('designation',  '').strip()
    teacher_code = data.get('teacher_code', '').strip().upper()

    if not all([email, password, full_name]):
        return jsonify({'error': 'Name, email and password are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    try:
        sb   = get_supabase()
        resp = sb.auth.sign_up({
            'email':    email,
            'password': password,
            'options':  {'data': {'full_name': full_name}},
        })
        user = resp.user
        if not user:
            return jsonify({'error': 'Registration failed. Try again.'}), 400

        sba = get_supabase_admin()

        # Save base profile with role='teacher'
        try:
            sba.table('profiles').upsert({
                'id':        user.id,
                'email':     email,
                'full_name': full_name,
                'role':      'teacher',
                'dept':      'Management',
            }).execute()
        except Exception as e:
            current_app.logger.warning(f'[Auth] Teacher profile upsert failed: {e}')

        # Save teacher-specific profile
        try:
            sba.table('teacher_profiles').upsert({
                'user_id':     user.id,
                'degree':      degree,
                'designation': designation,
                'teacher_code': teacher_code,
            }, on_conflict='user_id').execute()
        except Exception as e:
            current_app.logger.warning(f'[Auth] teacher_profiles upsert failed: {e}')

        # If teacher_code given, also update the mapping entry if it exists
        if teacher_code and full_name:
            try:
                sba.table('mappings').upsert({
                    'code':      teacher_code,
                    'full_name': full_name,
                    'type':      'teacher',
                }, on_conflict='code').execute()
            except Exception:
                pass

        try:
            from core.mailer import send_welcome
            send_welcome(to_email=email, user_name=full_name)
        except Exception:
            pass

        return jsonify({
            'success': True,
            'message': 'Teacher account created! Check your email to verify, then sign in.',
        })

    except Exception as e:
        msg = str(e)
        if 'already registered' in msg or 'already exists' in msg:
            return jsonify({'error': 'This email is already registered'}), 400
        return jsonify({'error': msg}), 400


# ── Profile completeness check ─────────────────────────────────

@auth_bp.route('/api/profile-check', methods=['GET'])
def profile_check():
    """
    Returns whether the user's profile is complete enough to use the app.
    Used by dashboard to auto-redirect incomplete profiles to /auth/register.
    """
    user_id = request.args.get('user_id', '').strip()
    if not user_id:
        return jsonify({'complete': False, 'reason': 'no_user_id'}), 400

    try:
        p = get_supabase_admin().table('profiles').select('*') \
                .eq('id', user_id).single().execute()
        profile = p.data or {}
    except Exception:
        return jsonify({'complete': False, 'reason': 'profile_not_found'}), 200

    role = profile.get('role', 'student')

    if role == 'teacher':
        complete = bool(profile.get('full_name'))
    else:
        complete = bool(
            profile.get('full_name') and
            profile.get('program') and
            profile.get('year') and
            profile.get('semester')
        )

    return jsonify({
        'complete': complete,
        'role':     role,
        'reason':   'ok' if complete else 'incomplete_profile',
    })


# ── Profile CRUD ───────────────────────────────────────────────

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
    user_id = data.get('user_id', '')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    allowed = ['full_name', 'year', 'semester', 'program', 'dept']
    payload = {k: data[k] for k in allowed if k in data and data[k] is not None}
    if 'year'     in payload: payload['year']     = int(payload['year'])
    if 'semester' in payload: payload['semester'] = int(payload['semester'])
    if not payload:
        return jsonify({'error': 'Nothing to update'}), 400

    try:
        resp = get_supabase_admin().table('profiles').update(payload).eq('id', user_id).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Logout ─────────────────────────────────────────────────────

@auth_bp.route('/api/logout', methods=['POST'])
def api_logout():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    return jsonify({'success': True})