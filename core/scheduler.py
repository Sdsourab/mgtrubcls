"""
UniSync — APScheduler Background Jobs
Job 1: Daily summary email at 7:00 PM
Job 2: Class alert 30 minutes after each class starts
"""
from flask_apscheduler import APScheduler
from datetime import datetime, date, timedelta

scheduler = APScheduler()


def start_scheduler(app):
    scheduler.init_app(app)

    # ── Job 1: Daily summary at 7 PM ─────────────────────────
    scheduler.add_job(
        id='daily_summary',
        func=job_daily_summary,
        args=[app],
        trigger='cron',
        hour=19,
        minute=0,
        replace_existing=True,
    )

    # ── Job 2: Class alert checker every 5 minutes ────────────
    # Checks if any class started ~30 mins ago and sends alert
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


def job_daily_summary(app):
    """Send tomorrow's schedule to all users at 7 PM."""
    with app.app_context():
        try:
            from core.supabase_client import get_supabase_admin
            from core.holidays import is_holiday
            from core.mailer import send_daily_summary

            tomorrow = date.today() + timedelta(days=1)
            day_name = tomorrow.strftime('%A')     # e.g. 'Monday'
            date_str = tomorrow.strftime('%d %b %Y')

            # Academic days only
            if day_name not in ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']:
                app.logger.info('[Scheduler] Tomorrow is a weekend, skipping summary.')
                return

            is_hol, hol_name = is_holiday(tomorrow)
            sb = get_supabase_admin()

            # Get all users
            users_resp = sb.table('profiles').select('*').execute()
            users = users_resp.data or []

            for user in users:
                if not user.get('email'):
                    continue

                program  = user.get('program', 'BBA')
                year     = user.get('year', 1)
                semester = user.get('semester', 1)

                # Get tomorrow's classes for user's program
                if is_hol:
                    classes = []
                else:
                    classes_resp = sb.table('routines').select('*')\
                        .eq('day', day_name)\
                        .in_('program', [program, 'ALL'])\
                        .order('time_start').execute()
                    classes = classes_resp.data or []

                    # Enrich course names
                    for cls in classes:
                        c = sb.table('mappings').select('full_name')\
                            .eq('code', cls.get('course_code', '')).execute()
                        t = sb.table('mappings').select('full_name')\
                            .eq('code', cls.get('teacher_code', '')).execute()
                        cls['course_name']  = c.data[0]['full_name'] if c.data else cls.get('course_code', '')
                        cls['teacher_name'] = t.data[0]['full_name'] if t.data else cls.get('teacher_code', '')

                # Get pending tasks
                tasks_resp = sb.table('tasks').select('*')\
                    .eq('user_id', user['id'])\
                    .neq('status', 'done')\
                    .order('deadline').execute()
                tasks = tasks_resp.data or []

                send_daily_summary(
                    to_email=user['email'],
                    user_name=user.get('full_name', 'Student'),
                    classes=classes,
                    tasks=tasks,
                    date_str=f'{day_name}, {date_str}',
                )

        except Exception as e:
            app.logger.error(f'[Scheduler] daily_summary error: {e}')


def job_class_alert_checker(app):
    """Send class alert if a class started exactly 30 mins ago."""
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

            # Target time = now - 30 min (classes that started 30 mins ago)
            target = now - timedelta(minutes=30)
            target_str = target.strftime('%H:%M')

            # Tolerance: ±3 minutes window
            low  = (target - timedelta(minutes=3)).strftime('%H:%M')
            high = (target + timedelta(minutes=3)).strftime('%H:%M')

            sb = get_supabase_admin()
            classes_resp = sb.table('routines').select('*')\
                .eq('day', day_name)\
                .gte('time_start', low)\
                .lte('time_start', high)\
                .execute()
            classes = classes_resp.data or []

            if not classes:
                return

            # Get all users and send alert per matching program
            users_resp = sb.table('profiles').select('*').execute()
            users = users_resp.data or []

            for cls in classes:
                # Enrich
                c = sb.table('mappings').select('full_name')\
                    .eq('code', cls.get('course_code', '')).execute()
                t = sb.table('mappings').select('full_name')\
                    .eq('code', cls.get('teacher_code', '')).execute()
                cls['course_name']  = c.data[0]['full_name'] if c.data else cls.get('course_code', '')
                cls['teacher_name'] = t.data[0]['full_name'] if t.data else cls.get('teacher_code', '')

                cls_program = cls.get('program', 'ALL')

                for user in users:
                    if not user.get('email'):
                        continue
                    user_program = user.get('program', 'BBA')
                    # Match if class is for this user's program or ALL
                    if cls_program not in [user_program, 'ALL']:
                        continue
                    send_class_alert(
                        to_email=user['email'],
                        user_name=user.get('full_name', 'Student'),
                        class_info=cls,
                    )

        except Exception as e:
            app.logger.error(f'[Scheduler] class_alert error: {e}')