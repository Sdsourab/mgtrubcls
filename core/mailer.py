"""
core/mailer.py
══════════════
UniSync Email Sender — Vercel Serverless compatible.
Synchronous send, no threading, no nested app_context.
"""
from flask_mail import Message


def _mail():
    from app import mail
    return mail


def _render(template: str, **ctx) -> str:
    from flask import render_template
    return render_template(template, **ctx)


# ── Public helpers ─────────────────────────────────────────────

def send_welcome(to_email: str, user_name: str, **_):
    """Registration সফল হলে welcome email পাঠায়।"""
    try:
        html = _render('emails/welcome.html', user_name=user_name)
        msg  = Message(
            subject    = '🎓 Welcome to UniSync — Rabindra University',
            recipients = [to_email],
            html       = html,
        )
        _mail().send(msg)
        return True
    except Exception as e:
        _log_error(f'send_welcome → {to_email}', e)
        return False


def send_daily_summary(to_email: str, user_name: str,
                       classes: list, tasks: list, date_str: str, **_):
    """প্রতিদিন রাত ৭টায় আগামীকালের schedule + pending tasks email করে।"""
    try:
        html = _render(
            'emails/daily_summary.html',
            user_name = user_name,
            classes   = classes,
            tasks     = tasks,
            date_str  = date_str,
        )
        msg = Message(
            subject    = f'📚 UniSync — Tomorrow\'s Schedule ({date_str})',
            recipients = [to_email],
            html       = html,
        )
        _mail().send(msg)
        return True
    except Exception as e:
        _log_error(f'send_daily_summary → {to_email}', e)
        return False


def send_class_alert(to_email: str, user_name: str, class_info: dict, **_):
    """Class alert email।"""
    try:
        html = _render(
            'emails/class_alert.html',
            user_name  = user_name,
            class_info = class_info,
        )
        msg = Message(
            subject    = f'⏰ UniSync — Class Alert: {class_info.get("course_code","")}',
            recipients = [to_email],
            html       = html,
        )
        _mail().send(msg)
        return True
    except Exception as e:
        _log_error(f'send_class_alert → {to_email}', e)
        return False


def _log_error(where: str, err: Exception):
    try:
        from flask import current_app
        current_app.logger.error(f'[Mailer] {where}: {err}')
    except Exception:
        print(f'[Mailer] {where}: {err}')