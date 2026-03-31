"""
app/__init__.py — UniSync Flask App
Email: Brevo SMTP via smtplib
"""
from flask import Flask, render_template, redirect, url_for, request, jsonify
from config import config
import os


def _fmt12h(t: str) -> str:
    try:
        h, m = map(int, t.split(':'))
        return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    except Exception:
        return t


def create_app(config_name: str = None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app   = Flask(__name__,
                  template_folder=os.path.join(_root, 'templates'),
                  static_folder  =os.path.join(_root, 'static'))
    app.config.from_object(config[config_name])

    # ── Blueprints ──────────────────────────────────────────
    from app.auth.routes         import auth_bp
    from app.academic.routes     import academic_bp
    from app.productivity.routes import productivity_bp
    from app.campus.routes       import campus_bp
    from app.admin.routes        import admin_bp
    from app.guest.routes        import guest_bp
    from app.planner.routes      import planner_bp

    app.register_blueprint(auth_bp,         url_prefix='/auth')
    app.register_blueprint(academic_bp,     url_prefix='/academic')
    app.register_blueprint(productivity_bp, url_prefix='/productivity')
    app.register_blueprint(campus_bp,       url_prefix='/campus')
    app.register_blueprint(admin_bp,        url_prefix='/admin')
    app.register_blueprint(guest_bp,        url_prefix='/guest')
    app.register_blueprint(planner_bp,      url_prefix='/planner')

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')

    # ════════════════════════════════════════════════════════
    # STEP 1 — Diagnosis (config check, no email sent)
    # URL: /api/email-check
    # এখানে দেখবেন কোন variable set আছে, কোনটা নেই
    # ════════════════════════════════════════════════════════
    @app.route('/api/email-check')
    def email_check():
        from core.mailer import test_connection

        login      = app.config.get('BREVO_SMTP_LOGIN', '').strip()
        key        = app.config.get('BREVO_SMTP_KEY',   '').strip()
        from_email = app.config.get('MAIL_FROM_EMAIL',  '').strip()
        from_name  = app.config.get('MAIL_FROM_NAME',   '').strip()

        config_status = {
            'BREVO_SMTP_LOGIN':  login  or '❌ NOT SET',
            'BREVO_SMTP_KEY':    ('✅ set (' + key[:6] + '...)') if key else '❌ NOT SET',
            'MAIL_FROM_EMAIL':   from_email or '❌ NOT SET',
            'MAIL_FROM_NAME':    from_name  or '⚠️ not set (will use UniSync)',
        }

        conn = test_connection()

        return jsonify({
            'config':     config_status,
            'connection': conn,
            'next_step':  '/api/test-email?to=your@email.com' if conn['ok'] else 'Fix errors above first',
        })

    # ════════════════════════════════════════════════════════
    # STEP 2 — Send real test email, show FULL error
    # URL: /api/test-email?to=your@email.com
    # ════════════════════════════════════════════════════════
    @app.route('/api/test-email')
    def test_email():
        from core.mailer import send_raw, _render_html

        to = request.args.get('to', '').strip()
        if not to:
            return jsonify({
                'usage': {
                    'step1_check':  '/api/email-check',
                    'step2_send':   '/api/test-email?to=your@email.com',
                }
            }), 400

        # Render template
        try:
            html = _render_html('emails/welcome.html', user_name='Test User')
        except Exception as e:
            return jsonify({'ok': False, 'stage': 'template_render', 'error': str(e)}), 500

        # Send and return FULL result (error never hidden)
        result = send_raw(
            to_email   = to,
            subject    = '🧪 UniSync Email Test',
            html_body  = html,
        )

        if result['ok']:
            return jsonify({
                'ok':      True,
                'sent_to': to,
                'message': f"✅ Email sent to '{to}'. Inbox ও Spam folder চেক করুন।",
            })
        else:
            # Return every detail of the error
            return jsonify({
                'ok':    False,
                'stage': 'smtp_send',
                'error': result.get('error'),
                'fix':   result.get('fix', 'উপরের error দেখে fix করুন।'),
            }), 500

    # ════════════════════════════════════════════════════════
    # VERCEL CRON — Daily 7 PM BST (UTC 13:00, Sun-Thu)
    # vercel.json: "0 13 * * 0-4"
    # ════════════════════════════════════════════════════════
    @app.route('/api/cron/daily', methods=['GET', 'POST'])
    def cron_daily():
        from datetime import datetime, timedelta, timezone
        from core.mailer import send_daily_summary

        BST      = timezone(timedelta(hours=6))
        now_bst  = datetime.now(BST)
        tomorrow = (now_bst + timedelta(days=1)).date()
        day_name = tomorrow.strftime('%A')
        date_str = tomorrow.strftime('%d %b %Y')

        results  = {'sent': 0, 'skipped': 0, 'errors': [],
                    'day': day_name, 'at': now_bst.strftime('%H:%M BST')}

        if day_name not in ['Sunday','Monday','Tuesday','Wednesday','Thursday']:
            return jsonify({'ok': True, 'reason': 'weekend', **results}), 200

        try:
            from core.supabase_client import get_supabase_admin
            from core.holidays        import is_holiday

            is_hol, _ = is_holiday(tomorrow)
            sb    = get_supabase_admin()
            users = sb.table('profiles').select('*').execute().data or []

            for user in users:
                email = (user.get('email') or '').strip()
                if not email:
                    results['skipped'] += 1
                    continue

                classes = []
                if not is_hol:
                    try:
                        rows = sb.table('routines').select('*') \
                            .eq('day',             day_name) \
                            .eq('program',         user.get('program',  'BBA')) \
                            .eq('course_year',     user.get('year',     1)) \
                            .eq('course_semester', user.get('semester', 1)) \
                            .order('time_start').execute()
                        classes = rows.data or []
                    except Exception:
                        classes = []

                    for cls in classes:
                        try:
                            c = sb.table('mappings').select('full_name') \
                                .eq('code', cls.get('course_code','')).execute()
                            cls['course_name'] = c.data[0]['full_name'] if c.data else cls.get('course_code','')
                        except Exception:
                            cls['course_name'] = cls.get('course_code','')
                        try:
                            t = sb.table('mappings').select('full_name') \
                                .eq('code', cls.get('teacher_code','')).execute()
                            cls['teacher_name'] = t.data[0]['full_name'] if t.data else cls.get('teacher_code','')
                        except Exception:
                            cls['teacher_name'] = cls.get('teacher_code','')
                        cls['time_start_12h'] = _fmt12h(cls.get('time_start',''))
                        cls['time_end_12h']   = _fmt12h(cls.get('time_end',''))

                try:
                    tasks = sb.table('tasks').select('*') \
                        .eq('user_id', user['id']) \
                        .neq('status','done') \
                        .order('deadline').execute().data or []
                except Exception:
                    tasks = []

                ok = send_daily_summary(
                    to_email  = email,
                    user_name = user.get('full_name','Student'),
                    classes   = classes,
                    tasks     = tasks,
                    date_str  = f'{day_name}, {date_str}',
                )
                if ok:
                    results['sent'] += 1
                else:
                    results['errors'].append(email)

        except Exception as e:
            results['errors'].append(str(e))

        return jsonify({'ok': True, **results}), 200

    # ── Error handlers ──────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api') or request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        if request.path.startswith('/api') or request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({'error': 'Forbidden'}), 403

    return app