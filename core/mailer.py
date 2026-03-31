"""
core/mailer.py — UniSync Email Sender (Resend API)
"""
import resend
import os
from flask import render_template


def _get_resend_client():
    resend.api_key = os.environ.get("RESEND_API_KEY", "")


def _send(subject: str, to: str, template: str, **ctx) -> bool:
    try:
        _get_resend_client()
        html = render_template(template, **ctx)
        params = {
            "from": os.environ.get("MAIL_DEFAULT_SENDER", "UniSync <onboarding@resend.dev>"),
            "to": [to],
            "subject": subject,
            "html": html,
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"[Mailer] send failed → {to} | {e}")
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