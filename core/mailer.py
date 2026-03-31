"""
core/mailer.py — UniSync Email Sender
Vercel Serverless compatible: synchronous, no threading.
"""
from flask import render_template
from flask_mail import Message


def _mail():
    from app import mail
    return mail


def _send(subject: str, to: str, template: str, **ctx) -> bool:
    """Core send — renders template and sends via Flask-Mail."""
    try:
        html = render_template(template, **ctx)
        msg  = Message(subject=subject, recipients=[to], html=html)
        _mail().send(msg)
        return True
    except Exception as e:
        _log(f'send failed → {to} | {template}', e)
        return False


def send_welcome(to_email: str, user_name: str, **_):
    return _send(
        subject  = '🎓 Welcome to UniSync — Rabindra University',
        to       = to_email,
        template = 'emails/welcome.html',
        user_name = user_name,
    )


def send_daily_summary(to_email: str, user_name: str,
                       classes: list, tasks: list, date_str: str, **_):
    return _send(
        subject   = f'📚 UniSync — Tomorrow\'s Schedule ({date_str})',
        to        = to_email,
        template  = 'emails/daily_summary.html',
        user_name = user_name,
        classes   = classes,
        tasks     = tasks,
        date_str  = date_str,
    )


def send_class_alert(to_email: str, user_name: str, class_info: dict, **_):
    return _send(
        subject    = f'⏰ UniSync — Class Alert: {class_info.get("course_code","")}',
        to         = to_email,
        template   = 'emails/class_alert.html',
        user_name  = user_name,
        class_info = class_info,
    )


def _log(where: str, err: Exception):
    try:
        from flask import current_app
        current_app.logger.error(f'[Mailer] {where}: {err}')
    except Exception:
        print(f'[Mailer] {where}: {err}')