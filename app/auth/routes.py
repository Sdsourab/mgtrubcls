"""
app/auth/routes.py
──────────────────
FIXED: api_login now always reads the full profile from `profiles` table
and returns it so the frontend can persist year/semester/program correctly.
This ensures semester settings survive browser reload and re-login.
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase, get_supabase_admin

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login',    methods=['GET'])
def login():    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET'])
def register(): return render_template('auth/register.html')

@auth_bp.route('/profile',  methods=['GET'])
def profile_page(): return render_template('modules/profile.html')


@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data     = request.get_json() or {}
    email    = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    try:
        sb   = get_supabase()
        resp = sb.auth.sign_in_with_password({"email": email, "password": password})
        user = resp.user
        sess = resp.session

        # Always fetch the full profile from DB so year/semester/program is current
        profile = {}
        try:
            sb_admin     = get_supabase_admin()
            profile_resp = sb_admin.table('profiles').select('*') \
                               .eq('id', user.id).single().execute()
            profile = profile_resp.data or {}
        except Exception:
            profile = {}

        return jsonify({
            'success':      True,
            'access_token': sess.access_token,
            'user': {
                'id':        user.id,
                'email':     user.email,
                'full_name': profile.get('full_name') or '',
                'role':      profile.get('role')      or 'student',
                'dept':      profile.get('dept')      or 'Management',
                'program':   profile.get('program')   or 'BBA',
                'year':      profile.get('year')      or 1,
                'semester':  profile.get('semester')  or 1,
            }
        })
    except Exception as e:
        msg = str(e)
        if 'Invalid login credentials' in msg:
            return jsonify({'error': 'Wrong email or password'}), 401
        if 'Email not confirmed' in msg:
            return jsonify({'error': 'Please verify your email first'}), 401
        return jsonify({'error': msg}), 401


@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    data      = request.get_json() or {}
    email     = data.get('email', '').strip()
    password  = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    dept      = data.get('dept', 'Management')
    program   = data.get('program', 'BBA')
    year      = int(data.get('year', 1))
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
            "email": email, "password": password,
            "options": {"data": {"full_name": full_name}}
        })
        user = resp.user
        if not user:
            return jsonify({'error': 'Registration failed. Try again.'}), 400

        try:
            sb.table('profiles').upsert({
                'id':        user.id,
                'email':     email,
                'full_name': full_name,
                'role':      'student',
                'dept':      dept,
                'program':   program,
                'year':      year,
                'semester':  semester,
            }).execute()
        except Exception:
            pass  # Profile upsert failure is non-fatal

        return jsonify({
            'success': True,
            'message': 'Registered! Check your email to verify, then login.'
        })
    except Exception as e:
        msg = str(e)
        if 'already registered' in msg or 'already exists' in msg:
            return jsonify({'error': 'This email is already registered'}), 400
        return jsonify({'error': msg}), 400


@auth_bp.route('/api/profile', methods=['GET'])
def get_profile():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    try:
        sb   = get_supabase_admin()
        resp = sb.table('profiles').select('*').eq('id', user_id).single().execute()
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

    if 'year' in payload:     payload['year']     = int(payload['year'])
    if 'semester' in payload: payload['semester'] = int(payload['semester'])

    if not payload:
        return jsonify({'error': 'Nothing to update'}), 400

    try:
        sb   = get_supabase_admin()
        resp = sb.table('profiles').update(payload).eq('id', user_id).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/api/logout', methods=['POST'])
def api_logout():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    return jsonify({'success': True})