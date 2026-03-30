"""
UniSync — Email Sender (core/mailer.py)
=======================================
Supports Flask-Mail via SMTP (Gmail App Password or any SMTP).
All sends run in a background thread so they never block the web process.
"""
import threading
from flask import current_app, render_template
from flask_mail import Message


def _get_mail():
    from app import mail
    return mail


def _send_async(app, msg):
    """Send email in a background thread with its own app context."""
    with app.app_context():
        try:
            _get_mail().send(msg)
        except Exception as e:
            app.logger.error(f'[Mailer] Async send failed: {e}')


def _dispatch(app, msg):
    """Fire-and-forget: send email without blocking the caller."""
    t = threading.Thread(target=_send_async, args=(app, msg), daemon=True)
    t.start()


# ── Public helpers ────────────────────────────────────────────────────────────

def send_daily_summary(to_email: str, user_name: str, classes: list,
                       tasks: list, date_str: str, app=None):
    """
    Send the daily summary email (tomorrow's schedule + pending tasks).
    Called by the APScheduler job every evening at 7 PM.
    Pass `app` when calling outside an active app context.
    """
    try:
        _app = app or current_app._get_current_object()
        with _app.app_context():
            html_body = render_template(
                'emails/daily_summary.html',
                user_name=user_name,
                classes=classes,
                tasks=tasks,
                date_str=date_str,
            )
        msg = Message(
            subject=f'📚 UniSync — Tomorrow\'s Schedule ({date_str})',
            recipients=[to_email],
            html=html_body,
        )
        _dispatch(_app, msg)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f'[Mailer] daily_summary failed for {to_email}: {e}')
        except Exception:
            print(f'[Mailer] daily_summary failed for {to_email}: {e}')
        return False


def send_class_alert(to_email: str, user_name: str, class_info: dict, app=None):
    """
    Send a class-started alert (30 min after class begins).
    """
    try:
        _app = app or current_app._get_current_object()
        with _app.app_context():
            html_body = render_template(
                'emails/class_alert.html',
                user_name=user_name,
                class_info=class_info,
            )
        msg = Message(
            subject=f'⏰ UniSync — Class Reminder: {class_info.get("course_code", "")}',
            recipients=[to_email],
            html=html_body,
        )
        _dispatch(_app, msg)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f'[Mailer] class_alert failed for {to_email}: {e}')
        except Exception:
            print(f'[Mailer] class_alert failed for {to_email}: {e}')
        return False


def send_welcome(to_email: str, user_name: str, app=None):
    """Send a welcome email immediately after successful registration."""
    try:
        _app = app or current_app._get_current_object()
        with _app.app_context():
            html_body = render_template(
                'emails/welcome.html',
                user_name=user_name,
            )
        msg = Message(
            subject='🎓 Welcome to UniSync — Rabindra University',
            recipients=[to_email],
            html=html_body,
        )
        _dispatch(_app, msg)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f'[Mailer] welcome failed for {to_email}: {e}')
        except Exception:
            print(f'[Mailer] welcome failed for {to_email}: {e}')
        return False