"""
core/mailer.py — UniSync Email via Brevo SMTP
Python smtplib — no Flask-Mail needed.
"""
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.utils          import formataddr

SMTP_HOST = 'smtp-relay.brevo.com'
SMTP_PORT = 587


def _creds():
    """Read Brevo credentials — from Flask config or env directly."""
    try:
        from flask import current_app
        c = current_app.config
        return (
            c.get('BREVO_SMTP_LOGIN',  os.environ.get('BREVO_SMTP_LOGIN',  '')).strip(),
            c.get('BREVO_SMTP_KEY',    os.environ.get('BREVO_SMTP_KEY',    '')).strip(),
            c.get('MAIL_FROM_NAME',    os.environ.get('MAIL_FROM_NAME',    'UniSync')),
            c.get('MAIL_FROM_EMAIL',   os.environ.get('MAIL_FROM_EMAIL',   '')).strip(),
        )
    except RuntimeError:
        return (
            os.environ.get('BREVO_SMTP_LOGIN',  '').strip(),
            os.environ.get('BREVO_SMTP_KEY',    '').strip(),
            os.environ.get('MAIL_FROM_NAME',    'UniSync'),
            os.environ.get('MAIL_FROM_EMAIL',   '').strip(),
        )


def send_raw(to_email: str, subject: str, html_body: str) -> dict:
    """
    Send email via Brevo SMTP.
    Returns dict: {ok, error, detail}
    'error' is always the full real error — never hidden.
    """
    login, key, from_name, from_email = _creds()
    from_email = from_email or login

    # ── Config validation ────────────────────────────────────
    if not login:
        return {'ok': False, 'error': 'BREVO_SMTP_LOGIN is empty',
                'fix': 'Vercel → Settings → Environment Variables → BREVO_SMTP_LOGIN এ Brevo login email দিন'}
    if not key:
        return {'ok': False, 'error': 'BREVO_SMTP_KEY is empty',
                'fix': 'Vercel → Settings → Environment Variables → BREVO_SMTP_KEY এ Brevo SMTP password দিন'}
    if not to_email:
        return {'ok': False, 'error': 'to_email is empty'}

    # ── Build message ────────────────────────────────────────
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = formataddr((from_name, from_email))
    msg['To']      = to_email
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    # ── SMTP send ────────────────────────────────────────────
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=25) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(login, key)
            srv.sendmail(from_email, [to_email], msg.as_string())
        return {'ok': True, 'error': None}

    except smtplib.SMTPAuthenticationError as e:
        return {'ok': False,
                'error': f'Authentication failed (535): {e}',
                'fix': 'Brevo dashboard → SMTP & API → SMTP tab → Password এ নতুন key copy করুন। Login হলো আপনার Brevo account email।'}
    except smtplib.SMTPRecipientsRefused as e:
        return {'ok': False, 'error': f'Recipient refused: {e}'}
    except smtplib.SMTPSenderRefused as e:
        return {'ok': False,
                'error': f'Sender refused: {e}',
                'fix': 'MAIL_FROM_EMAIL টা Brevo তে verified হতে হবে। Brevo → Senders & Domains এ check করুন।'}
    except smtplib.SMTPConnectError as e:
        return {'ok': False, 'error': f'Cannot connect to smtp-relay.brevo.com:587 — {e}'}
    except smtplib.SMTPException as e:
        return {'ok': False, 'error': f'SMTP error: {e}'}
    except OSError as e:
        return {'ok': False, 'error': f'Network/OS error: {e}',
                'fix': 'Vercel outbound SMTP blocked হতে পারে। Port 587 allow করতে Vercel support contact করুন।'}
    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}'}


def _render_html(template: str, **ctx) -> str:
    from flask import render_template
    return render_template(template, **ctx)


def _send(subject: str, to: str, template: str, **ctx) -> bool:
    try:
        html = _render_html(template, **ctx)
    except Exception as e:
        _log(f'Template error [{template}]: {e}')
        return False
    result = send_raw(to_email=to, subject=subject, html_body=html)
    if not result['ok']:
        _log(f'Send failed → {to}: {result.get("error")}')
    return result['ok']


def _log(msg: str):
    try:
        from flask import current_app
        current_app.logger.error(f'[Mailer] {msg}')
    except Exception:
        print(f'[Mailer] {msg}')


def test_connection() -> dict:
    """
    Test Brevo SMTP connection without sending an email.
    Returns {ok, message, login, fix?}
    """
    login, key, _, _ = _creds()

    if not login:
        return {'ok': False, 'message': 'BREVO_SMTP_LOGIN not set',
                'fix': 'Vercel → Settings → Environment Variables → BREVO_SMTP_LOGIN'}
    if not key:
        return {'ok': False, 'message': 'BREVO_SMTP_KEY not set',
                'fix': 'Vercel → Settings → Environment Variables → BREVO_SMTP_KEY'}
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(login, key)
        return {'ok': True, 'message': f'✅ Brevo SMTP connected. Login: {login}'}
    except smtplib.SMTPAuthenticationError as e:
        return {'ok': False,
                'message': f'Authentication failed: {e}',
                'fix': 'BREVO_SMTP_KEY ভুল। Brevo → SMTP & API → SMTP → Password copy করুন।'}
    except Exception as e:
        return {'ok': False, 'message': str(e)}


# ── Public send functions ────────────────────────────────────

def send_welcome(to_email: str, user_name: str, **_) -> bool:
    return _send('🎓 Welcome to UniSync — Rabindra University',
                 to_email, 'emails/welcome.html', user_name=user_name)


def send_daily_summary(to_email: str, user_name: str,
                       classes: list, tasks: list, date_str: str, **_) -> bool:
    return _send(f"📚 UniSync — Tomorrow's Schedule ({date_str})",
                 to_email, 'emails/daily_summary.html',
                 user_name=user_name, classes=classes,
                 tasks=tasks, date_str=date_str)


def send_class_alert(to_email: str, user_name: str, class_info: dict, **_) -> bool:
    return _send(f"⏰ Class Alert: {class_info.get('course_code','')} — UniSync",
                 to_email, 'emails/class_alert.html',
                 user_name=user_name, class_info=class_info)