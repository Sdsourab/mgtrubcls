from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from core.supabase_client import get_supabase, get_supabase_admin

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET'])
def login():
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET'])
def register():
    return render_template('auth/register.html')

@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email    = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    try:
        sb       = get_supabase()
        resp     = sb.auth.sign_in_with_password({"email": email, "password": password})
        user     = resp.user
        session_data = resp.session

        sb_admin     = get_supabase_admin()
        profile_resp = sb_admin.table('profiles').select('*').eq('id', user.id).single().execute()
        profile      = profile_resp.data if profile_resp.data else {}

        return jsonify({
            'success': True,
            'access_token': session_data.access_token,
            'user': {
                'id':        user.id,
                'email':     user.email,
                'full_name': profile.get('full_name', ''),
                'role':      profile.get('role', 'student'),
                'dept':      profile.get('dept', ''),
                'batch':     profile.get('batch', ''),
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 401


@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    email     = data.get('email', '').strip()
    password  = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    dept      = data.get('dept', 'Management')
    program   = data.get('program', 'BBA')   # NEW
    year      = int(data.get('year', 1))      # NEW
    semester  = int(data.get('semester', 1))  # NEW

    if not all([email, password, full_name]):
        return jsonify({'error': 'All fields are required'}), 400

    # Validate year range
    max_year = 4 if program == 'BBA' else 2
    if not (1 <= year <= max_year):
        return jsonify({'error': f'{program} year must be 1–{max_year}'}), 400

    if semester not in [1, 2]:
        return jsonify({'error': 'Semester must be 1 or 2'}), 400

    try:
        sb = get_supabase()
        resp = sb.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"full_name": full_name}}
        })
        user = resp.user

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

        return jsonify({
            'success': True,
            'message': 'Registration successful. Please verify your email.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400