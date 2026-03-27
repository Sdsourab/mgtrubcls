from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase, get_supabase_admin

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login',    methods=['GET'])
def login():    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET'])
def register(): return render_template('auth/register.html')


@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data     = request.get_json()
    email    = data.get('email', '').strip()
    password = data.get('password', '')
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    try:
        sb   = get_supabase()
        resp = sb.auth.sign_in_with_password({"email": email, "password": password})
        user = resp.user
        sess = resp.session
        profile_resp = sb.table('profiles').select('*').eq('id', user.id).single().execute()
        profile = profile_resp.data or {}
        return jsonify({
            'success':      True,
            'access_token': sess.access_token,
            'user': {
                'id':        user.id,
                'email':     user.email,
                'full_name': profile.get('full_name', ''),
                'role':      profile.get('role', 'student'),
                'dept':      profile.get('dept', ''),
                'program':   profile.get('program', 'BBA'),
                'year':      profile.get('year', 1),
                'semester':  profile.get('semester', 1),
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 401


@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    data      = request.get_json()
    email     = data.get('email', '').strip()
    password  = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    dept      = data.get('dept', 'Management')
    program   = data.get('program', 'BBA')
    year      = int(data.get('year', 1))
    semester  = int(data.get('semester', 1))

    if not all([email, password, full_name]):
        return jsonify({'error': 'All fields are required'}), 400

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
        sb.table('profiles').upsert({
            'id': user.id, 'email': email, 'full_name': full_name,
            'role': 'student', 'dept': dept,
            'program': program, 'year': year, 'semester': semester,
        }).execute()
        return jsonify({'success': True, 'message': 'Registration successful. Please verify your email.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@auth_bp.route('/api/profile', methods=['GET'])
def get_profile():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    sb = get_supabase_admin()
    try:
        resp = sb.table('profiles').select('*').eq('id', user_id).single().execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/api/profile', methods=['PATCH'])
def update_profile():
    """User can update full_name, year, semester."""
    data    = request.get_json()
    user_id = data.get('user_id', '')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    allowed = ['full_name', 'year', 'semester', 'program', 'dept']
    payload = {k: v for k, v in data.items() if k in allowed and v is not None}

    if 'year' in payload:
        payload['year'] = int(payload['year'])
    if 'semester' in payload:
        payload['semester'] = int(payload['semester'])

    # Validate
    if 'program' in payload and 'year' in payload:
        max_year = 4 if payload['program'] == 'BBA' else 2
        if not (1 <= payload['year'] <= max_year):
            return jsonify({'error': f'Year must be 1–{max_year} for {payload["program"]}'}), 400

    sb = get_supabase_admin()
    try:
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
@auth_bp.route('/profile')
def profile_page():
    return render_template('modules/profile.html')