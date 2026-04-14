"""
app/push/routes.py
══════════════════
Web Push subscription management + class reminder cron.

Endpoints:
  POST /api/push/subscribe        → save browser push subscription
  POST /api/push/unsubscribe      → remove subscription
  GET  /api/push/status           → check if user is subscribed
  POST /api/cron/push-reminders   → 30-min class reminder (Vercel cron)
"""

from flask import Blueprint, jsonify, request
from core.supabase_client import get_supabase_admin
import json

push_bp = Blueprint('push', __name__)


# ─────────────────────────────────────────────────────────────
# Subscribe
# ─────────────────────────────────────────────────────────────

@push_bp.route('/api/push/subscribe', methods=['POST'])
def subscribe():
    """
    Save browser PushSubscription to Supabase.
    Body: { user_id: str, subscription: PushSubscription.toJSON() }
    """
    data     = request.get_json() or {}
    user_id  = data.get('user_id',    '').strip()
    sub_data = data.get('subscription', {})

    if not user_id or not sub_data:
        return jsonify({'error': 'user_id and subscription required'}), 400

    endpoint = sub_data.get('endpoint', '')
    if not endpoint:
        return jsonify({'error': 'Invalid subscription — no endpoint'}), 400

    sub_json = json.dumps(sub_data)
    sb = get_supabase_admin()

    try:
        # Upsert — same user + endpoint → update; new → insert
        sb.table('push_subscriptions').upsert({
            'user_id':           user_id,
            'endpoint':          endpoint,
            'subscription_json': sub_json,
        }, on_conflict='user_id,endpoint').execute()

        return jsonify({'success': True, 'message': 'Push subscription saved.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# Unsubscribe
# ─────────────────────────────────────────────────────────────

@push_bp.route('/api/push/unsubscribe', methods=['POST'])
def unsubscribe():
    """Remove push subscription by endpoint."""
    data     = request.get_json() or {}
    user_id  = data.get('user_id',  '').strip()
    endpoint = data.get('endpoint', '').strip()

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    sb = get_supabase_admin()
    try:
        q = sb.table('push_subscriptions').delete().eq('user_id', user_id)
        if endpoint:
            q = q.eq('endpoint', endpoint)
        q.execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# Status check
# ─────────────────────────────────────────────────────────────

@push_bp.route('/api/push/status', methods=['GET'])
def push_status():
    """Check if a user has push subscriptions saved."""
    user_id = request.args.get('user_id', '').strip()
    if not user_id:
        return jsonify({'subscribed': False}), 400

    sb = get_supabase_admin()
    try:
        rows = sb.table('push_subscriptions') \
                 .select('id') \
                 .eq('user_id', user_id) \
                 .execute().data or []
        return jsonify({'subscribed': len(rows) > 0, 'count': len(rows)})
    except Exception as e:
        return jsonify({'subscribed': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# 30-minute Class Reminder Cron
# Called by Vercel cron every 5 minutes to check upcoming classes
# ─────────────────────────────────────────────────────────────

@push_bp.route('/api/cron/push-reminders', methods=['GET', 'POST'])
def push_reminders():
    """
    Vercel Cron — runs every 5 minutes (*/5 * * * 0-4).
    Finds classes starting in the next 25–35 minute window (BST)
    and sends push reminders to subscribed students.
    Uses sent_push_alerts for deduplication.
    """
    from datetime import datetime, timedelta, timezone, date as _date
    from core.push import push_to_batch

    BST = timezone(timedelta(hours=6))
    now_bst = datetime.now(BST)

    # Only run on class days (Sun–Thu)
    if now_bst.weekday() not in (6, 0, 1, 2, 3):  # Sun=6 Mon=0 Tue=1 Wed=2 Thu=3
        return jsonify({'ok': True, 'reason': 'weekend'}), 200

    # Window: classes starting 25–35 min from now
    window_start = now_bst + timedelta(minutes=25)
    window_end   = now_bst + timedelta(minutes=35)
    ws_str = f"{window_start.hour:02d}:{window_start.minute:02d}"
    we_str = f"{window_end.hour:02d}:{window_end.minute:02d}"

    today_str = now_bst.strftime('%Y-%m-%d')
    day_name  = now_bst.strftime('%A')

    sb = get_supabase_admin()
    results = {'sent': 0, 'skipped': 0, 'errors': []}

    try:
        # Find classes in this window today
        classes = sb.table('routines') \
                    .select('*') \
                    .eq('day', day_name) \
                    .gte('time_start', ws_str) \
                    .lte('time_start', we_str) \
                    .execute().data or []

        for cls in classes:
            course_code  = cls.get('course_code', '')
            time_start   = cls.get('time_start', '')
            program      = cls.get('program', 'ALL')
            course_year  = cls.get('course_year', 0)
            course_sem   = cls.get('course_semester', 0)
            room         = cls.get('room_no', '?')

            # Resolve course name
            course_name = course_code
            try:
                m = sb.table('mappings').select('full_name').eq('code', course_code).execute()
                if m.data:
                    course_name = m.data[0]['full_name']
            except Exception:
                pass

            # Dedup key: date + course_code + time_start
            alert_key = f"reminder_{today_str}_{course_code}_{time_start}"
            try:
                dup = sb.table('sent_push_alerts') \
                        .select('id') \
                        .eq('alert_key', alert_key) \
                        .execute()
                if dup.data:
                    results['skipped'] += 1
                    continue
            except Exception:
                pass

            # If program/year/sem unknown, skip batch push
            if not course_year or not course_sem or program == 'ALL':
                results['skipped'] += 1
                continue

            # Check if this class is cancelled today
            try:
                cancel = sb.table('class_changes') \
                           .select('id') \
                           .eq('course_code', course_code) \
                           .eq('change_date', today_str) \
                           .eq('type', 'cancel') \
                           .execute()
                if cancel.data:
                    results['skipped'] += 1
                    continue  # Class cancelled — don't remind
            except Exception:
                pass

            # Convert time_start to 12h for display
            try:
                h, m_val = map(int, time_start.split(':'))
                ampm  = 'AM' if h < 12 else 'PM'
                h12   = h % 12 or 12
                time_12h = f"{h12}:{m_val:02d} {ampm}"
            except Exception:
                time_12h = time_start

            title = f'⏰ Class in 30 min — {course_name}'
            body  = f'{time_12h} · Room {room}'

            r = push_to_batch(
                program  = program,
                year     = course_year,
                semester = course_sem,
                title    = title,
                body     = body,
                url      = '/academic/routine',
            )
            results['sent'] += r.get('sent', 0)

            # Mark as sent
            try:
                sb.table('sent_push_alerts').insert({
                    'alert_key': alert_key,
                    'user_id':   None,   # batch alert — no single user
                }).execute()
            except Exception:
                pass

    except Exception as e:
        results['errors'].append(str(e))

    return jsonify({'ok': True, **results}), 200