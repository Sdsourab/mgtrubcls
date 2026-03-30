"""
UniSync — APScheduler Background Jobs (core/scheduler.py)
=========================================================
Job 1 : Daily summary email at 7:00 PM every academic day
Job 2 : Class alert 30 minutes after each class starts (checks every 5 min)

Both jobs run in persistent background threads inside the Flask process.
They work even when the user's browser is closed.
"""
from flask_apscheduler import APScheduler
from datetime import datetime, date, timedelta

scheduler = APScheduler()


def start_scheduler(app):
    scheduler.init_app(app)

    # ── Job 1: Daily summary at 7 PM ──────────────────────────────────
    scheduler.add_job(
        id='daily_summary',
        func=job_daily_summary,
        args=[app],
        trigger='cron',
        hour=19,
        minute=0,
        replace_existing=True,
    )

    # ── Job 2: Class alert checker every 5 minutes ────────────────────
    scheduler.add_job(
        id='class_alert_checker',
        func=job_class_alert_checker,
        args=[app],
        trigger='interval',
        minutes=5,
        replace_existing=True,
    )

    scheduler.start()
    app.logger.info('[Scheduler] Started — daily_summary + class_alert_checker')


def _format_time_12h(time_str: str) -> str:
    """Convert 24h 'HH:MM' → 12h '12:00 PM' format."""
    try:
        h, m = map(int, time_str.split(':'))
        period = 'AM' if h < 12 else 'PM'
        h12 = h % 12 or 12
        return f'{h12}:{m:02d} {period}'
    except Exception:
        return time_str


def job_daily_summary(app):
    """Send tomorrow's schedule to all users at 7 PM every academic evening."""
    with app.app_context():
        try:
            from core.supabase_client import get_supabase_admin
            from core.holidays import is_holiday
            from core.mailer import send_daily_summary

            tomorrow = date.today() + timedelta(days=1)
            day_name = tomorrow.strftime('%A')   # 'Monday', 'Tuesday', etc.
            date_str = tomorrow.strftime('%d %b %Y')

            # Academic days: Sun–Thu
            if day_name not in ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']:
                app.logger.info('[Scheduler] Tomorrow is weekend — skipping daily summary.')
                return

            is_hol, hol_name = is_holiday(tomorrow)
            sb = get_supabase_admin()

            # Fetch all profiles that have an email address
            users_resp = sb.table('profiles').select('*').execute()
            users = users_resp.data or []

            sent_count = 0
            for user in users:
                email = user.get('email', '')
                if not email:
                    continue

                program  = user.get('program', 'BBA')
                year     = user.get('year', 1)
                semester = user.get('semester', 1)

                # ── Get tomorrow's classes ─────────────────────────────
                if is_hol:
                    classes = []
                else:
                    try:
                        classes_resp = sb.table('routines').select('*') \
                            .eq('day', day_name) \
                            .eq('program', program) \
                            .eq('course_year', year) \
                            .eq('course_semester', semester) \
                            .order('time_start').execute()
                        classes = classes_resp.data or []
                    except Exception:
                        classes = []

                    # Enrich with full names + 12h times
                    for cls in classes:
                        try:
                            c = sb.table('mappings').select('full_name') \
                                .eq('code', cls.get('course_code', '')).execute()
                            cls['course_name'] = c.data[0]['full_name'] if c.data else cls.get('course_code', '')
                        except Exception:
                            cls['course_name'] = cls.get('course_code', '')

                        try:
                            t = sb.table('mappings').select('full_name') \
                                .eq('code', cls.get('teacher_code', '')).execute()
                            cls['teacher_name'] = t.data[0]['full_name'] if t.data else cls.get('teacher_code', '')
                        except Exception:
                            cls['teacher_name'] = cls.get('teacher_code', '')

                        # Convert times to 12h format for email display
                        cls['time_start_12h'] = _format_time_12h(cls.get('time_start', ''))
                        cls['time_end_12h']   = _format_time_12h(cls.get('time_end', ''))

                # ── Get pending tasks ──────────────────────────────────
                try:
                    tasks_resp = sb.table('tasks').select('*') \
                        .eq('user_id', user['id']) \
                        .neq('status', 'done') \
                        .order('deadline').execute()
                    tasks = tasks_resp.data or []
                except Exception:
                    tasks = []

                send_daily_summary(
                    to_email=email,
                    user_name=user.get('full_name', 'Student'),
                    classes=classes,
                    tasks=tasks,
                    date_str=f'{day_name}, {date_str}',
                    app=app,
                )
                sent_count += 1

            app.logger.info(f'[Scheduler] Daily summary sent to {sent_count} users.')

        except Exception as e:
            app.logger.error(f'[Scheduler] daily_summary error: {e}')


def job_class_alert_checker(app):
    """Send class-started alert if a class began ~30 minutes ago."""
    with app.app_context():
        try:
            from core.supabase_client import get_supabase_admin
            from core.mailer import send_class_alert
            from core.holidays import is_holiday

            now      = datetime.now()
            day_name = now.strftime('%A')

            if day_name not in ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']:
                return

            is_hol, _ = is_holiday(now.date())
            if is_hol:
                return

            # Target: classes that started exactly 30 min ago (±3 min window)
            target     = now - timedelta(minutes=30)
            low        = (target - timedelta(minutes=3)).strftime('%H:%M')
            high       = (target + timedelta(minutes=3)).strftime('%H:%M')

            sb = get_supabase_admin()
            classes_resp = sb.table('routines').select('*') \
                .eq('day', day_name) \
                .gte('time_start', low) \
                .lte('time_start', high) \
                .execute()
            classes = classes_resp.data or []

            if not classes:
                return

            # Enrich class info
            for cls in classes:
                try:
                    c = sb.table('mappings').select('full_name') \
                        .eq('code', cls.get('course_code', '')).execute()
                    cls['course_name'] = c.data[0]['full_name'] if c.data else cls.get('course_code', '')
                except Exception:
                    cls['course_name'] = cls.get('course_code', '')

                try:
                    t = sb.table('mappings').select('full_name') \
                        .eq('code', cls.get('teacher_code', '')).execute()
                    cls['teacher_name'] = t.data[0]['full_name'] if t.data else cls.get('teacher_code', '')
                except Exception:
                    cls['teacher_name'] = cls.get('teacher_code', '')

                cls['time_start_12h'] = _format_time_12h(cls.get('time_start', ''))
                cls['time_end_12h']   = _format_time_12h(cls.get('time_end', ''))

            users_resp = sb.table('profiles').select('*').execute()
            users = users_resp.data or []

            for cls in classes:
                cls_program = cls.get('program', 'ALL')
                cls_year    = cls.get('course_year', 0)
                cls_sem     = cls.get('course_semester', 0)

                for user in users:
                    email = user.get('email', '')
                    if not email:
                        continue

                    user_program = user.get('program', 'BBA')
                    user_year    = user.get('year', 0)
                    user_sem     = user.get('semester', 0)

                    # Match by program + year + semester
                    if cls_program not in [user_program, 'ALL']:
                        continue
                    if cls_year and cls_year != user_year:
                        continue
                    if cls_sem and cls_sem != user_sem:
                        continue

                    send_class_alert(
                        to_email=email,
                        user_name=user.get('full_name', 'Student'),
                        class_info=cls,
                        app=app,
                    )

        except Exception as e:
            app.logger.error(f'[Scheduler] class_alert error: {e}')