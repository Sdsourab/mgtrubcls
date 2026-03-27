"""
UniSync — Email Sender
Uses Flask-Mail. Import `mail` from app and call these helpers.
"""
from flask import current_app, render_template
from flask_mail import Message


def _get_mail():
    from app import mail
    return mail


def send_daily_summary(to_email: str, user_name: str, classes: list, tasks: list, date_str: str):
    """Send the 7 PM daily summary email."""
    mail = _get_mail()
    try:
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
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f'[Mailer] daily_summary failed for {to_email}: {e}')
        return False


def send_class_alert(to_email: str, user_name: str, class_info: dict):
    """Send the 'class started 30 mins ago' alert."""
    mail = _get_mail()
    try:
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
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f'[Mailer] class_alert failed for {to_email}: {e}')
        return False