"""
core/mailer.py — UniSync Email Sender
══════════════════════════════════════
Brevo SMTP দিয়ে email পাঠানো হয়।
Python built-in smtplib ব্যবহার করা হয়েছে — কোনো extra package লাগবে না।

সম্পূর্ণ synchronous, Vercel Serverless compatible।
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.utils          import formataddr


# ── Brevo SMTP Config ──────────────────────────────────────────
SMTP_HOST  = 'smtp-relay.brevo.com'
SMTP_PORT  = 587


def _get_config():
    """Get Brevo credentials from Flask config or environment."""
    try:
        from flask import current_app
        cfg = current_app.config
        return {
            'login':      cfg.get('BREVO_SMTP_LOGIN',  os.environ.get('BREVO_SMTP_LOGIN', '')),
            'key':        cfg.get('BREVO_SMTP_KEY',    os.environ.get('BREVO_SMTP_KEY',   '')),
            'from_name':  cfg.get('MAIL_FROM_NAME',    os.environ.get('MAIL_FROM_NAME',   'UniSync')),
            'from_email': cfg.get('MAIL_FROM_EMAIL',   os.environ.get('MAIL_FROM_EMAIL',  '')),
        }
    except RuntimeError:
        # Outside app context — read from environment directly
        return {
            'login':      os.environ.get('BREVO_SMTP_LOGIN',  ''),
            'key':        os.environ.get('BREVO_SMTP_KEY',    ''),
            'from_name':  os.environ.get('MAIL_FROM_NAME',    'UniSync'),
            'from_email': os.environ.get('MAIL_FROM_EMAIL',   ''),
        }


def _render(template: str, **ctx) -> str:
    """Render a Jinja2 HTML template."""
    from flask import render_template
    return render_template(template, **ctx)


def _send_smtp(to_email: str, subject: str, html_body: str) -> tuple[bool, str]:
    """
    Core SMTP send function using Brevo.
    Returns (success: bool, error_message: str).
    """
    cfg = _get_config()

    login      = cfg['login'].strip()
    key        = cfg['key'].strip()
    from_name  = cfg['from_name']
    from_email = cfg['from_email'].strip() or login

    # ── Validation ────────────────────────────────────────────
    if not login:
        return False, 'BREVO_SMTP_LOGIN not set in environment variables'
    if not key:
        return False, 'BREVO_SMTP_KEY not set in environment variables'
    if not to_email:
        return False, 'Recipient email is empty'

    # ── Build email ───────────────────────────────────────────
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = formataddr((from_name, from_email))
    msg['To']      = to_email
    msg['X-Mailer'] = 'UniSync/1.0'

    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    # ── Send via Brevo SMTP ───────────────────────────────────
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(login, key)
            server.sendmail(from_email, [to_email], msg.as_string())
        return True, ''
    except smtplib.SMTPAuthenticationError:
        return False, 'Authentication failed — BREVO_SMTP_KEY ভুল আছে। Brevo dashboard থেকে SMTP password copy করুন।'
    except smtplib.SMTPConnectError as e:
        return False, f'Cannot connect to Brevo SMTP: {e}'
    except smtplib.SMTPException as e:
        return False, f'SMTP error: {e}'
    except OSError as e:
        return False, f'Network error: {e}'
    except Exception as e:
        return False, f'Unexpected error: {e}'


def _send(subject: str, to: str, template: str, **ctx) -> bool:
    """Render template and send email. Returns True on success."""
    try:
        html = _render(template, **ctx)
    except Exception as e:
        _log(f'Template render failed [{template}]', e)
        return False

    ok, err = _send_smtp(to_email=to, subject=subject, html_body=html)
    if not ok:
        _log(f'Send failed → {to}', Exception(err))
    return ok


def _log(where: str, err: Exception):
    try:
        from flask import current_app
        current_app.logger.error(f'[Mailer] {where}: {err}')
    except Exception:
        print(f'[Mailer] {where}: {err}')


# ══════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════

def send_welcome(to_email: str, user_name: str, **_) -> bool:
    """Registration এর পরপরই welcome email পাঠায়।"""
    return _send(
        subject   = '🎓 Welcome to UniSync — Rabindra University',
        to        = to_email,
        template  = 'emails/welcome.html',
        user_name = user_name,
    )


def send_daily_summary(to_email: str, user_name: str,
                       classes: list, tasks: list, date_str: str, **_) -> bool:
    """প্রতিদিন রাত ৭টায় আগামীকালের class + pending tasks।"""
    return _send(
        subject   = f'📚 UniSync — Tomorrow\'s Schedule ({date_str})',
        to        = to_email,
        template  = 'emails/daily_summary.html',
        user_name = user_name,
        classes   = classes,
        tasks     = tasks,
        date_str  = date_str,
    )


def send_class_alert(to_email: str, user_name: str, class_info: dict, **_) -> bool:
    """Class শুরুর alert email।"""
    return _send(
        subject    = f'⏰ Class Alert: {class_info.get("course_code", "")} — UniSync',
        to         = to_email,
        template   = 'emails/class_alert.html',
        user_name  = user_name,
        class_info = class_info,
    )


def test_connection() -> tuple[bool, str]:
    """
    Email config ঠিক আছে কিনা check করে — actual email পাঠায় না।
    Returns (ok: bool, message: str)
    """
    cfg   = _get_config()
    login = cfg['login'].strip()
    key   = cfg['key'].strip()

    if not login:
        return False, 'BREVO_SMTP_LOGIN not configured'
    if not key:
        return False, 'BREVO_SMTP_KEY not configured'

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(login, key)
        return True, f'Connected to Brevo SMTP successfully. Login: {login}'
    except smtplib.SMTPAuthenticationError:
        return False, 'Authentication failed — BREVO_SMTP_KEY ভুল। Brevo dashboard → SMTP & API → SMTP → Password দেখুন।'
    except Exception as e:
        return False, str(e)