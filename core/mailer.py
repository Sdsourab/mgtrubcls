"""
core/mailer.py
══════════════
UniSync Email Sender — Vercel Serverless compatible.

threading.Thread বাদ দেওয়া হয়েছে কারণ Vercel Serverless এ
background thread কাজ করে না। সব email এখন synchronous।
"""
from flask import current_app, render_template
from flask_mail import Message


def _get_mail():
    from app import mail
    return mail


# ── Public helpers ────────────────────────────────────────────

def send_daily_summary(to_email: str, user_name: str, classes: list,
                       tasks: list, date_str: str, app=None):
    """প্রতিদিন রাত ৭টায় আগামীকালের schedule + pending tasks email করে।"""
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
            _get_mail().send(msg)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f'[Mailer] daily_summary failed → {to_email}: {e}')
        except Exception:
            print(f'[Mailer] daily_summary failed → {to_email}: {e}')
        return False


def send_welcome(to_email: str, user_name: str, app=None):
    """Registration সফল হলে সাথে সাথে welcome email পাঠায়।"""
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
            _get_mail().send(msg)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f'[Mailer] welcome failed → {to_email}: {e}')
        except Exception:
            print(f'[Mailer] welcome failed → {to_email}: {e}')
        return False


def send_class_alert(to_email: str, user_name: str, class_info: dict, app=None):
    """Class শুরুর ৩০ মিনিট পরে alert email পাঠায়।"""
    try:
        _app = app or current_app._get_current_object()
        with _app.app_context():
            html_body = render_template(
                'emails/class_alert.html',
                user_name=user_name,
                class_info=class_info,
            )
            msg = Message(
                subject=f'⏰ UniSync — Class Alert: {class_info.get("course_code", "")}',
                recipients=[to_email],
                html=html_body,
            )
            _get_mail().send(msg)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f'[Mailer] class_alert failed → {to_email}: {e}')
        except Exception:
            print(f'[Mailer] class_alert failed → {to_email}: {e}')
        return False