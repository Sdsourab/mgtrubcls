from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from core.supabase_client import get_supabase, get_supabase_admin

auth_bp = Blueprint('auth', __name__)


def _friendly_error(e: Exception) -> str:
    """Convert raw Supabase/Python errors into user-friendly Bengali/English messages."""
    msg = str(e).lower()

    if "invalid api key" in msg or "apikey" in msg:
        return "Server configuration error. Please contact the admin."
    if "user already registered" in msg or "already been registered" in msg:
        return "This email is already registered. Please log in."
    if "invalid login credentials" in msg or "invalid email or password" in msg:
        return "Invalid email or password."
    if "email not confirmed" in msg:
        return "Please verify your email address first."
    if "password should be at least" in msg:
        return "Password must be at least 6 characters."
    if "unable to validate email" in msg or "invalid email" in msg:
        return "Please enter a valid email address."
    if "rate limit" in msg or "too many" in msg:
        return "Too many attempts. Please wait a minute and try again."
    if "network" in msg or "connection" in msg or "timeout" in msg:
        return "Connection error. Please check your internet and try again."

    # Return the raw error for debugging (remove in production if desired)
    return str(e)


@auth_bp.route('/login', methods=['GET'])
def login():
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET'])
def register():
    return render_template('auth/register.html')


@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400

    email    = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    try:
        sb   = get_supabase()
        resp = sb.auth.sign_in_with_password({"email": email, "password": password})
        user         = resp.user
        session_data = resp.session

        if not user:
            return jsonify({'error': 'Login failed. Please try again.'}), 401

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
        return jsonify({'error': _friendly_error(e)}), 401


@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400

    email     = data.get('email', '').strip()
    password  = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    dept      = data.get('dept', 'Management')
    program   = data.get('program', 'BBA')
    year      = int(data.get('year', 1))
    semester  = int(data.get('semester', 1))

    if not all([email, password, full_name]):
        return jsonify({'error': 'All fields are required'}), 400

    # Validate year range
    max_year = 4 if program == 'BBA' else 2
    if not (1 <= year <= max_year):
        return jsonify({'error': f'{program} year must be 1–{max_year}'}), 400

    if semester not in [1, 2]:
        return jsonify({'error': 'Semester must be 1 or 2'}), 400

    try:
        sb   = get_supabase()
        resp = sb.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"full_name": full_name}}
        })
        user = resp.user

        if not user:
            return jsonify({'error': 'Registration failed. Email may already be registered.'}), 400

        # Save extended profile
        sb_admin = get_supabase_admin()
        sb_admin.table('profiles').upsert({
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
            'message': 'Registration successful! Please check your email to verify your account.'
        })

    except Exception as e:
        return jsonify({'error': _friendly_error(e)}), 400