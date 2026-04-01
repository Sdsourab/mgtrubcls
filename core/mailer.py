"""
core/mailer.py — UniSync Email via Resend API
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Resend (resend.com) — instant activation, no SMTP needed.
Free: 3000 emails/month. Works on Vercel serverless perfectly.
"""
import os
import resend


def _setup():
    """Configure Resend API key from Flask config or env."""
    try:
        from flask import current_app
        key = current_app.config.get('RESEND_API_KEY', '')
    except RuntimeError:
        key = ''
    if not key:
        key = os.environ.get('RESEND_API_KEY', '')
    resend.api_key = key
    return key


def _from_addr():
    """Get sender address."""
    try:
        from flask import current_app
        return current_app.config.get('MAIL_FROM', 'UniSync <onboarding@resend.dev>')
    except RuntimeError:
        return os.environ.get('MAIL_FROM', 'UniSync <onboarding@resend.dev>')


def _render(template: str, **ctx) -> str:
    from flask import render_template
    return render_template(template, **ctx)


def send_raw(to_email: str, subject: str, html: str) -> dict:
    """
    Send email via Resend API.
    Returns: {'ok': bool, 'id': str|None, 'error': str|None}
    """
    api_key = _setup()

    if not api_key:
        return {
            'ok':    False,
            'error': 'RESEND_API_KEY not set',
            'fix':   'Vercel → Settings → Environment Variables → RESEND_API_KEY',
        }

    try:
        resp = resend.Emails.send({
            'from':    _from_addr(),
            'to':      [to_email],
            'subject': subject,
            'html':    html,
        })
        # Resend returns {'id': 'email_id'} on success
        if resp and resp.get('id'):
            return {'ok': True, 'id': resp['id'], 'error': None}
        else:
            return {'ok': False, 'error': f'Unexpected response: {resp}'}

    except resend.exceptions.ResendError as e:
        msg = str(e)
        fix = 'Resend dashboard → API Keys চেক করুন।'
        if '401' in msg or 'Unauthorized' in msg:
            fix = 'RESEND_API_KEY ভুল। resend.com → API Keys → নতুন key তৈরি করুন।'
        elif '422' in msg or 'validation' in msg.lower():
            fix = 'MAIL_FROM ঠিক নেই। Format: "UniSync <onboarding@resend.dev>"'
        elif '429' in msg:
            fix = 'Rate limit — কিছুক্ষণ পরে চেষ্টা করুন।'
        return {'ok': False, 'error': msg, 'fix': fix}

    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}'}


def _send(subject: str, to: str, template: str, **ctx) -> bool:
    """Render Jinja2 template and send via Resend."""
    try:
        html = _render(template, **ctx)
    except Exception as e:
        _log(f'Template error [{template}]: {e}')
        return False

    result = send_raw(to_email=to, subject=subject, html=html)
    if not result['ok']:
        _log(f'Send failed → {to} | {result.get("error")}')
    return result['ok']


def _log(msg: str):
    try:
        from flask import current_app
        current_app.logger.error(f'[Mailer] {msg}')
    except Exception:
        print(f'[Mailer] {msg}')


def test_connection() -> dict:
    """
    Verify RESEND_API_KEY is valid without sending an email.
    Uses Resend's /domains endpoint as a lightweight check.
    """
    api_key = _setup()

    if not api_key:
        return {
            'ok':      False,
            'message': 'RESEND_API_KEY not set',
            'fix':     'Vercel → Settings → Environment Variables → RESEND_API_KEY এ Resend API key দিন',
        }

    try:
        # List domains — lightweight authenticated request
        resend.Domains.list()
        return {
            'ok':      True,
            'message': '✅ Resend API key valid. Email system ready.',
            'from':    _from_addr(),
        }
    except resend.exceptions.ResendError as e:
        msg = str(e)
        if '401' in msg or 'Unauthorized' in msg:
            return {
                'ok':      False,
                'message': f'Invalid API key: {msg}',
                'fix':     'resend.com → API Keys → নতুন key তৈরি করুন এবং Vercel এ দিন।',
            }
        return {'ok': False, 'message': msg}
    except Exception as e:
        return {'ok': False, 'message': f'{type(e).__name__}: {e}'}


# ── Public API ───────────────────────────────────────────────

def send_welcome(to_email: str, user_name: str, **_) -> bool:
    return _send(
        '🎓 Welcome to UniSync — Rabindra University',
        to_email, 'emails/welcome.html',
        user_name=user_name,
    )


def send_daily_summary(to_email: str, user_name: str,
                       classes: list, tasks: list, date_str: str, **_) -> bool:
    return _send(
        f"📚 UniSync — Tomorrow's Schedule ({date_str})",
        to_email, 'emails/daily_summary.html',
        user_name=user_name, classes=classes,
        tasks=tasks, date_str=date_str,
    )


def send_class_alert(to_email: str, user_name: str, class_info: dict, **_) -> bool:
    return _send(
        f"⏰ Class Alert: {class_info.get('course_code', '')} — UniSync",
        to_email, 'emails/class_alert.html',
        user_name=user_name, class_info=class_info,
    )