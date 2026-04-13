"""
app/classmanagement/routes.py
──────────────────────────────
Class management — CR AND Teacher can:
  • Cancel a class on a specific date
  • Add an extra class
  • Update room number / time for a class slot
  • Broadcast notice to affected batch
  • Push notification to all subscribed users in the batch

Route order: static sub-paths BEFORE /<change_id>
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import date as _date

classmanagement_bp = Blueprint('classmanagement', __name__)


# ─────────────────────────────────────────────────────────────
# Auth helper — CR, Admin, OR Teacher
# ─────────────────────────────────────────────────────────────

def _require_cr_or_teacher(user_id: str):
    """Return profile dict if CR, admin, or teacher. Else None."""
    if not user_id:
        return None
    try:
        sb = get_supabase_admin()
        p  = sb.table('profiles').select('*').eq('id', user_id).single().execute()
        profile = p.data or {}
        if profile.get('role') in ('cr', 'admin', 'teacher'):
            return profile
        return None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _resolve_course_name(sb, course_code: str) -> str:
    try:
        m = sb.table('mappings').select('full_name').eq('code', course_code).execute()
        return m.data[0]['full_name'] if m.data else course_code
    except Exception:
        return course_code


def _publish_notice(sb, user_id: str, profile: dict, title: str,
                    content: str, content_text: str, notice_type: str,
                    program: str, year: int, semester: int):
    """Auto-create a notice for the batch. Non-fatal."""
    try:
        author_name = profile.get('full_name', 'CR')
        role        = profile.get('role', 'cr')
        if role == 'teacher':
            author_name += ' (Teacher)'

        sb.table('notices').insert({
            'author_id':    user_id,
            'author_name':  author_name,
            'title':        title,
            'content':      content,
            'content_text': content_text,
            'type':         notice_type,
            'program':      program,
            'target_year':  year,
            'target_sem':   semester,
            'is_draft':     False,
            'pinned':       False,
        }).execute()
    except Exception:
        pass


def _push_notify_batch(sb, program: str, year: int, semester: int,
                       title: str, body: str):
    """
    Send Web Push to all subscribed users in this batch.
    Non-fatal — push failure never breaks the main operation.
    """
    try:
        import json, pywebpush
        # Get subscriptions for users in this batch
        profiles = sb.table('profiles') \
                     .select('id') \
                     .eq('program', program) \
                     .eq('year', year) \
                     .eq('semester', semester) \
                     .execute().data or []

        user_ids = [p['id'] for p in profiles]
        if not user_ids:
            return

        # Batch fetch subscriptions
        subs = sb.table('push_subscriptions') \
                 .select('subscription_json') \
                 .in_('user_id', user_ids) \
                 .execute().data or []

        import os
        vapid_private = os.environ.get('VAPID_PRIVATE_KEY', '')
        vapid_claims  = {'sub': 'mailto:' + os.environ.get('MAIL_FROM_EMAIL', 'admin@unisync.bd')}

        payload = json.dumps({'title': title, 'body': body, 'icon': '/static/icons/icon-192x192.png'})

        for row in subs:
            try:
                sub_info = json.loads(row['subscription_json'])
                pywebpush.webpush(
                    subscription_info    = sub_info,
                    data                 = payload,
                    vapid_private_key    = vapid_private,
                    vapid_claims         = vapid_claims,
                )
            except Exception:
                pass  # Individual push failure is non-fatal
    except Exception:
        pass  # Push module unavailable — skip silently


# ─────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────

@classmanagement_bp.route('/')
def management_page():
    return render_template('modules/class_management.html')


# ─────────────────────────────────────────────────────────────
# GET: class changes for a batch
# ─────────────────────────────────────────────────────────────

@classmanagement_bp.route('/api/class-changes', methods=['GET'])
def get_class_changes():
    program = request.args.get('program', 'BBA')
    year    = request.args.get('year')
    sem     = request.args.get('semester')
    from_dt = request.args.get('from', _date.today().isoformat())
    to_dt   = request.args.get('to')

    sb = get_supabase_admin()
    try:
        q = sb.table('class_changes').select('*') \
              .eq('program', program) \
              .gte('change_date', from_dt) \
              .order('change_date')
        if year:
            q = q.eq('target_year', int(year))
        if sem:
            q = q.eq('target_semester', int(sem))
        if to_dt:
            q = q.lte('change_date', to_dt)

        rows = q.execute().data or []

        # Enrich names
        try:
            mapping = {r['code']: r['full_name']
                       for r in (sb.table('mappings').select('code,full_name').execute().data or [])}
            for row in rows:
                row['course_name']  = mapping.get(row.get('course_code', ''), row.get('course_code', ''))
                row['teacher_name'] = mapping.get(row.get('teacher_code', ''), row.get('teacher_code', ''))
        except Exception:
            pass

        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# POST: Cancel class
# ─────────────────────────────────────────────────────────────

@classmanagement_bp.route('/api/class-changes/cancel', methods=['POST'])
def cancel_class():
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    profile = _require_cr_or_teacher(user_id)
    if not profile:
        return jsonify({'error': 'Only CR, Teacher, or Admin can cancel classes'}), 403

    course_code = data.get('course_code', '').strip()
    change_date = data.get('change_date', '').strip()
    if not course_code or not change_date:
        return jsonify({'error': 'course_code and change_date are required'}), 400

    sb          = get_supabase_admin()
    course_name = _resolve_course_name(sb, course_code)
    program     = data.get('program', profile.get('program', 'BBA'))
    year        = int(data.get('year', profile.get('cr_for_year') or profile.get('year', 1)))
    semester    = int(data.get('semester', profile.get('cr_for_semester') or profile.get('semester', 1)))
    reason      = data.get('reason', '')
    author      = profile.get('full_name', 'CR/Teacher')

    try:
        payload = {
            'type':            'cancel',
            'course_code':     course_code,
            'teacher_code':    data.get('teacher_code', ''),
            'program':         program,
            'target_year':     year,
            'target_semester': semester,
            'change_date':     change_date,
            'reason':          reason,
            'created_by':      user_id,
            'created_by_name': author,
        }
        resp = sb.table('class_changes').insert(payload).execute()

        reason_html = f'<p><em>Reason: {reason}</em></p>' if reason else ''
        notice_title = f'❌ Class Cancelled: {course_name} — {change_date}'
        notice_content = (
            f'<p><strong>{course_name}</strong> class on <strong>{change_date}</strong> '
            f'has been <strong style="color:#e53e3e">cancelled</strong>.</p>'
            f'{reason_html}'
            f'<p style="color:#718096;font-size:.85em;">— {author}</p>'
        )
        _publish_notice(sb, user_id, profile,
                        title=notice_title,
                        content=notice_content,
                        content_text=f'{course_name} class cancelled on {change_date}. {reason}',
                        notice_type='class_cancel',
                        program=program, year=year, semester=semester)

        _push_notify_batch(sb, program, year, semester,
                           title=notice_title,
                           body=f'{course_name} — {change_date} class cancelled. {reason}')

        return jsonify({'success': True, 'data': resp.data}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# POST: Extra class
# ─────────────────────────────────────────────────────────────

@classmanagement_bp.route('/api/class-changes/extra', methods=['POST'])
def add_extra_class():
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()

    profile = _require_cr_or_teacher(user_id)
    if not profile:
        return jsonify({'error': 'Only CR, Teacher, or Admin can add extra classes'}), 403

    missing = [f for f in ('course_code', 'change_date', 'time_start', 'time_end') if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing: {", ".join(missing)}'}), 400

    sb          = get_supabase_admin()
    course_code = data['course_code']
    course_name = _resolve_course_name(sb, course_code)
    program     = data.get('program', profile.get('program', 'BBA'))
    year        = int(data.get('year', profile.get('cr_for_year') or profile.get('year', 1)))
    semester    = int(data.get('semester', profile.get('cr_for_semester') or profile.get('semester', 1)))
    reason      = data.get('reason', '')
    author      = profile.get('full_name', 'CR/Teacher')

    try:
        payload = {
            'type':            'extra',
            'course_code':     course_code,
            'teacher_code':    data.get('teacher_code', ''),
            'program':         program,
            'target_year':     year,
            'target_semester': semester,
            'change_date':     data['change_date'],
            'time_start':      data['time_start'],
            'time_end':        data['time_end'],
            'room_no':         data.get('room_no', 'TBD'),
            'reason':          reason,
            'created_by':      user_id,
            'created_by_name': author,
        }
        resp = sb.table('class_changes').insert(payload).execute()

        note_html = f'<p><em>Note: {reason}</em></p>' if reason else ''
        room      = data.get('room_no', 'TBD')
        notice_title = f'📅 Extra Class: {course_name} — {data["change_date"]}'
        notice_content = (
            f'<p>An <strong style="color:#38a169">extra class</strong> for '
            f'<strong>{course_name}</strong> has been scheduled.</p>'
            f'<p>📅 <strong>Date:</strong> {data["change_date"]}<br>'
            f'⏰ <strong>Time:</strong> {data["time_start"]} – {data["time_end"]}<br>'
            f'🏛 <strong>Room:</strong> {room}</p>'
            f'{note_html}'
            f'<p style="color:#718096;font-size:.85em;">— {author}</p>'
        )
        _publish_notice(sb, user_id, profile,
                        title=notice_title,
                        content=notice_content,
                        content_text=f'Extra class {course_name} on {data["change_date"]} {data["time_start"]}–{data["time_end"]}',
                        notice_type='extra_class',
                        program=program, year=year, semester=semester)

        _push_notify_batch(sb, program, year, semester,
                           title=notice_title,
                           body=f'{course_name} extra class on {data["change_date"]} at {data["time_start"]}, Room {room}')

        return jsonify({'success': True, 'data': resp.data}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# POST: Update room / time for an existing routine slot
# ─────────────────────────────────────────────────────────────

@classmanagement_bp.route('/api/update-slot', methods=['POST'])
def update_slot():
    """
    Teacher or CR updates room number or time for a routine slot.
    Publishes a notice to the affected batch.
    """
    data       = request.get_json() or {}
    user_id    = data.get('user_id', '').strip()
    routine_id = data.get('routine_id', '').strip()

    profile = _require_cr_or_teacher(user_id)
    if not profile:
        return jsonify({'error': 'Only CR, Teacher, or Admin can update slots'}), 403

    if not routine_id:
        return jsonify({'error': 'routine_id required'}), 400

    sb = get_supabase_admin()

    # Fetch existing slot
    try:
        existing_row = sb.table('routines').select('*').eq('id', routine_id).single().execute()
        existing = existing_row.data or {}
    except Exception:
        return jsonify({'error': 'Routine slot not found'}), 404

    if not existing:
        return jsonify({'error': 'Routine slot not found'}), 404

    # Build update payload — only update provided fields
    update_fields = {}
    if data.get('room_no'):
        update_fields['room_no'] = data['room_no'].strip()
    if data.get('time_start'):
        update_fields['time_start'] = data['time_start'].strip()
    if data.get('time_end'):
        update_fields['time_end'] = data['time_end'].strip()

    if not update_fields:
        return jsonify({'error': 'Nothing to update (room_no, time_start, time_end)'}), 400

    try:
        sb.table('routines').update(update_fields).eq('id', routine_id).execute()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    # Notify batch
    course_code = existing.get('course_code', '')
    course_name = _resolve_course_name(sb, course_code)
    program     = data.get('program', existing.get('program', 'BBA'))
    year        = int(data.get('year', existing.get('course_year', 1)))
    semester    = int(data.get('semester', existing.get('course_semester', 1)))
    author      = profile.get('full_name', 'Teacher')
    day         = existing.get('day', '')

    changes_desc = []
    if 'room_no' in update_fields:
        changes_desc.append(f'Room: {existing.get("room_no","?")} → {update_fields["room_no"]}')
    if 'time_start' in update_fields or 'time_end' in update_fields:
        new_start = update_fields.get('time_start', existing.get('time_start', ''))
        new_end   = update_fields.get('time_end',   existing.get('time_end', ''))
        changes_desc.append(f'Time: {new_start} – {new_end}')

    notice_title   = f'🔄 Slot Updated: {course_name} ({day})'
    notice_content = (
        f'<p>The following change has been made to <strong>{course_name}</strong> ({day}):</p>'
        f'<ul>' + ''.join(f'<li>{c}</li>' for c in changes_desc) + '</ul>'
        f'<p style="color:#718096;font-size:.85em;">— {author}</p>'
    )
    _publish_notice(sb, user_id, profile,
                    title=notice_title,
                    content=notice_content,
                    content_text=f'{course_name} slot updated: ' + ', '.join(changes_desc),
                    notice_type='general',
                    program=program, year=year, semester=semester)

    _push_notify_batch(sb, program, year, semester,
                       title=notice_title,
                       body=f'{course_name} — ' + ', '.join(changes_desc))

    return jsonify({'success': True, 'updated': update_fields})


# ─────────────────────────────────────────────────────────────
# POST: Offline sync
# ─────────────────────────────────────────────────────────────

@classmanagement_bp.route('/api/class-changes/sync', methods=['POST'])
def sync_offline_changes():
    data    = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    actions = data.get('actions', [])

    profile = _require_cr_or_teacher(user_id)
    if not profile:
        return jsonify({'error': 'Forbidden'}), 403

    if not actions:
        return jsonify({'success': True, 'synced': [], 'failed': []})

    sb = get_supabase_admin()
    synced, failed = [], []

    for action in actions:
        local_id    = action.get('local_id')
        action_type = action.get('type', 'cancel')
        try:
            course_code = action.get('course_code', '')
            program     = action.get('program', profile.get('program', 'BBA'))
            year        = int(action.get('year', profile.get('year', 1)))
            semester    = int(action.get('semester', profile.get('semester', 1)))

            payload = {
                'type':            action_type,
                'course_code':     course_code,
                'teacher_code':    action.get('teacher_code', ''),
                'program':         program,
                'target_year':     year,
                'target_semester': semester,
                'change_date':     action.get('change_date', ''),
                'reason':          action.get('reason', ''),
                'created_by':      user_id,
                'created_by_name': profile.get('full_name', 'CR'),
            }
            if action_type == 'extra':
                payload['time_start'] = action.get('time_start', '')
                payload['time_end']   = action.get('time_end', '')
                payload['room_no']    = action.get('room_no', 'TBD')

            sb.table('class_changes').insert(payload).execute()
            synced.append(local_id)
        except Exception as e:
            failed.append({'local_id': local_id, 'error': str(e)})

    return jsonify({'success': True, 'synced': synced, 'failed': failed})


# ─────────────────────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────────────────────

@classmanagement_bp.route('/api/class-changes/<change_id>', methods=['DELETE'])
def delete_change(change_id):
    user_id = request.args.get('user_id', '').strip()
    if not _require_cr_or_teacher(user_id):
        return jsonify({'error': 'Forbidden'}), 403
    sb = get_supabase_admin()
    try:
        sb.table('class_changes').delete().eq('id', change_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500