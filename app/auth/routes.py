"""
app/auth/routes.py
══════════════════
Handles student AND teacher registration/login.
New: /auth/become-cr      → CR registration page
     /auth/api/become-cr  → self-service CR (max 2 per batch, auto-check)
     /auth/api/cr-status  → batch CR count check
     /auth/api/resign-cr  → CR resign
"""

from flask import Blueprint, jsonify, request, render_template, current_app
from core.supabase_client import get_supabase, get_supabase_admin

auth_bp = Blueprint('auth', __name__)

MAX_CR_PER_BATCH = 2   # প্রতি batch এ সর্বোচ্চ এতজন CR হতে পারবে


# ── Pages ──────────────────────────────────────────────────────

@auth_bp.route('/login',    methods=['GET'])
def login():        return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET'])
def register():     return render_template('auth/register.html')

@auth_bp.route('/profile',  methods=['GET'])
def profile_page(): return render_template('modules/profile.html')

@auth_bp.route('/become-cr', methods=['GET'])
def become_cr_page(): return render_template('auth/become_cr.html')


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
        return jsonify({'error': f'{program} year must be 1-{max_year}'}), 400
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

        return jsonify({'success': True,
                        'message': 'Account created! Verify your email then sign in.'})

    except Exception as e:
        msg = str(e)
        if 'already registered' in msg or 'already exists' in msg:
            return jsonify({'error': 'This email is already registered'}), 400
        return jsonify({'error': msg}), 400


# ── Teacher Register ───────────────────────────────────────────

@auth_bp.route('/api/register-teacher', methods=['POST'])
def api_register_teacher():
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
        try:
            sba.table('profiles').upsert({
                'id':        user.id,
                'email':     email,
                'full_name': full_name,
                'role':      'teacher',
                'dept':      'Management',
            }).execute()
        except Exception as e:
            current_app.logger.warning(f'[Auth] Teacher profile upsert: {e}')

        try:
            sba.table('teacher_profiles').upsert({
                'user_id':      user.id,
                'degree':       degree,
                'designation':  designation,
                'teacher_code': teacher_code,
            }, on_conflict='user_id').execute()
        except Exception:
            pass

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

        return jsonify({'success': True,
                        'message': 'Teacher account created! Verify email then sign in.'})

    except Exception as e:
        msg = str(e)
        if 'already registered' in msg or 'already exists' in msg:
            return jsonify({'error': 'This email is already registered'}), 400
        return jsonify({'error': msg}), 400


# ═══════════════════════════════════════════════════════════════
# CR SELF-REGISTRATION SYSTEM
# প্রতি batch (program + year + semester) এ max 2 জন CR
# কোনো admin intervention লাগবে না
# ═══════════════════════════════════════════════════════════════

@auth_bp.route('/api/cr-status', methods=['GET'])
def cr_status():
    """
    Batch এর CR count এবং current user CR কিনা জানায়।
    GET /auth/api/cr-status?program=BBA&year=3&semester=1&user_id=<uuid>
    """
    program  = request.args.get('program',  '').strip()
    year     = request.args.get('year',     '').strip()
    semester = request.args.get('semester', '').strip()
    user_id  = request.args.get('user_id',  '').strip()

    if not program or not year or not semester:
        return jsonify({'error': 'program, year, semester required'}), 400

    sb = get_supabase_admin()
    try:
        rows = sb.table('profiles') \
                 .select('id, full_name') \
                 .eq('role', 'cr') \
                 .eq('program', program) \
                 .eq('year', int(year)) \
                 .eq('semester', int(semester)) \
                 .execute().data or []

        cr_count        = len(rows)
        is_already_cr   = any(r['id'] == user_id for r in rows)
        slots_available = MAX_CR_PER_BATCH - cr_count

        return jsonify({
            'success':         True,
            'batch':           f'{program} Year {year} Semester {semester}',
            'cr_count':        cr_count,
            'max_cr':          MAX_CR_PER_BATCH,
            'slots_available': max(0, slots_available),
            'is_already_cr':   is_already_cr,
            'can_register':    slots_available > 0 and not is_already_cr,
            'current_crs':     [r['full_name'] for r in rows],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/api/become-cr', methods=['POST'])
def become_cr():
    """
    Self-service CR registration.
    User এর নিজের profile থেকে batch নেয় — max 2 জন enforce করে।
    Admin এর কিছু করতে হবে না।
    """
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    if not user_id:
        return jsonify({'error': 'user_id required'}), 401

    sb = get_supabase_admin()

    # User profile load
    try:
        p       = sb.table('profiles').select('*').eq('id', user_id).single().execute()
        profile = p.data or {}
    except Exception:
        return jsonify({'error': 'User not found'}), 404

    if not profile:
        return jsonify({'error': 'Profile not found. Complete registration first.'}), 404

    current_role = profile.get('role', 'student')

    if current_role in ('cr', 'admin'):
        return jsonify({'error': 'You are already a CR or Admin.'}), 400
    if current_role == 'teacher':
        return jsonify({'error': 'Teachers cannot be CR.'}), 400

    program  = profile.get('program')
    year     = profile.get('year')
    semester = profile.get('semester')

    if not all([program, year, semester]):
        return jsonify({
            'error': 'Please complete your profile (program, year, semester) first.'
        }), 400

    # Batch এ কতজন CR আছে check
    try:
        existing = sb.table('profiles') \
                     .select('id, full_name') \
                     .eq('role', 'cr') \
                     .eq('program', program) \
                     .eq('year', year) \
                     .eq('semester', semester) \
                     .execute().data or []
    except Exception as e:
        return jsonify({'error': f'Database error: {e}'}), 500

    if len(existing) >= MAX_CR_PER_BATCH:
        names = ' এবং '.join(c.get('full_name', 'Unknown') for c in existing)
        return jsonify({
            'error': f'এই batch এ ইতিমধ্যে {MAX_CR_PER_BATCH} জন CR আছেন: {names}। '
                     f'আর CR নেওয়া সম্ভব নয়।'
        }), 409

    # Role update — cr_for_year / cr_for_semester optional columns
    update_payload = {'role': 'cr'}
    try:
        # Try to set the extra columns if they exist
        sb.table('profiles').update({
            'role':             'cr',
            'cr_for_year':     year,
            'cr_for_semester': semester,
        }).eq('id', user_id).execute()
    except Exception:
        # Columns may not exist — just update role
        try:
            sb.table('profiles').update({'role': 'cr'}).eq('id', user_id).execute()
        except Exception as e2:
            return jsonify({'error': str(e2)}), 500

    return jsonify({
        'success':  True,
        'new_role': 'cr',
        'message':  (
            f'আপনি এখন {program} Year {year} Semester {semester} এর CR! '
            f'এখন থেকে Notice দিতে পারবেন এবং ক্লাস ম্যানেজ করতে পারবেন।'
        ),
    })


@auth_bp.route('/api/resign-cr', methods=['POST'])
def resign_cr():
    """CR নিজে resign করতে পারবে — role student এ ফিরে যাবে।"""
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    if not user_id:
        return jsonify({'error': 'user_id required'}), 401

    sb = get_supabase_admin()
    try:
        p = sb.table('profiles').select('role').eq('id', user_id).single().execute()
        if not p.data or p.data.get('role') != 'cr':
            return jsonify({'error': 'You are not a CR.'}), 400

        sb.table('profiles').update({'role': 'student'}).eq('id', user_id).execute()
        return jsonify({'success': True, 'message': 'CR role resigned. You are now a student.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Profile CRUD ───────────────────────────────────────────────

@auth_bp.route('/api/profile-check', methods=['GET'])
def profile_check():
    user_id = request.args.get('user_id', '').strip()
    if not user_id:
        return jsonify({'complete': False, 'reason': 'no_user_id'}), 400

    try:
        p = get_supabase_admin().table('profiles').select('*') \
                .eq('id', user_id).single().execute()
        profile = p.data or {}
    except Exception:
        return jsonify({'complete': False, 'reason': 'profile_not_found'}), 200

    role     = profile.get('role', 'student')
    complete = bool(
        profile.get('full_name') and (
            role == 'teacher' or
            (profile.get('program') and profile.get('year') and profile.get('semester'))
        )
    )
    return jsonify({'complete': complete, 'role': role,
                    'reason': 'ok' if complete else 'incomplete_profile'})


@auth_bp.route('/api/profile', methods=['GET'])
def get_profile():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    try:
        resp = get_supabase_admin().table('profiles').select('*') \
                   .eq('id', user_id).single().execute()
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
        resp = get_supabase_admin().table('profiles').update(payload) \
                   .eq('id', user_id).execute()
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


# ── Admin Bypass (Code-based access) ──────────────────────────

@auth_bp.route('/admin-bypass', methods=['GET'])
def admin_bypass_page():
    return render_template('auth/admin_bypass.html')


@auth_bp.route('/api/admin-bypass', methods=['POST'])
def api_admin_bypass():
    """
    Validate a bypass code from admin_codes table.
    On success → return a synthetic admin session token + user object
    so the frontend can store it in localStorage and enter the admin panel.
    """
    import uuid, secrets
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()

    if not code:
        return jsonify({'success': False, 'error': 'Code দিন।'}), 400

    sb = get_supabase_admin()
    try:
        result = sb.table('admin_codes') \
                   .select('id, code, label, is_active') \
                   .eq('code', code) \
                   .eq('is_active', True) \
                   .limit(1) \
                   .execute()

        if not result.data:
            return jsonify({'success': False, 'error': 'ভুল code। আবার চেষ্টা করুন।'}), 401

        # Build a synthetic admin user object for localStorage
        admin_user = {
            'id':         'admin-bypass-' + str(uuid.uuid4())[:8],
            'email':      'admin@unisync.local',
            'full_name':  'Admin',
            'role':       'admin',
            'program':    'BBA',
            'year':       1,
            'semester':   1,
        }
        # A simple token — just needs to exist in localStorage for requireAuth()
        token = 'bypass-' + secrets.token_urlsafe(32)

        return jsonify({'success': True, 'token': token, 'user': admin_user})

    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error: ' + str(e)}), 500