from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from core.holidays import is_holiday, get_upcoming_holidays
from datetime import datetime, date

academic_bp = Blueprint('academic', __name__)


def _enrich(rows, sb):
    for row in rows:
        c = sb.table('mappings').select('full_name').eq('code', row.get('course_code', '')).execute()
        t = sb.table('mappings').select('full_name').eq('code', row.get('teacher_code', '')).execute()
        row['course_name']  = c.data[0]['full_name'] if c.data else row.get('course_code', '')
        row['teacher_name'] = t.data[0]['full_name'] if t.data else row.get('teacher_code', '')
    return rows


def _ml_suggestion(time_str: str, classes: list) -> dict:
    if not time_str or not classes:
        return {}
    try:
        h, m = map(int, time_str.split(':'))
        query_mins = h * 60 + m
    except Exception:
        return {}

    suggestions = []
    for cls in classes:
        try:
            sh, sm = map(int, cls.get('time_start', '00:00').split(':'))
            eh, em = map(int, cls.get('time_end',   '00:00').split(':'))
        except Exception:
            continue
        start_mins = sh * 60 + sm
        end_mins   = eh * 60 + em
        late_mins  = query_mins - start_mins
        remaining  = end_mins - query_mins
        course     = cls.get('course_name', cls.get('course_code', 'Class'))
        room       = cls.get('room_no', '?')
        teacher    = cls.get('teacher_name', cls.get('teacher_code', ''))

        if late_mins <= 0:
            mins_until = abs(late_mins)
            if   mins_until <= 5:  tip = f"⚡ '{course}' starts in {mins_until} min — go to Room {room} NOW!"
            elif mins_until <= 15: tip = f"🏃 '{course}' starts in {mins_until} min. Head to Room {room}."
            elif mins_until <= 30: tip = f"🕐 '{course}' in {mins_until} min. Wrap up and get ready."
            else:                  tip = f"📖 {mins_until} min before '{course}'. Good time to review notes."
        elif 1 <= late_mins <= 15:
            tip = f"🚶 {late_mins} min late for '{course}'. Go to Room {room} — intro still on."
        elif 16 <= late_mins <= 30:
            tip = f"⚠️ {late_mins} min late for '{course}'. Join Room {room} now — core content starting."
        elif 31 <= late_mins <= 50:
            tip = f"📝 Missed {late_mins} min of '{course}'. {remaining} min left. Join or get notes."
        elif remaining > 20:
            tip = f"⏳ Very late for '{course}'. {remaining} min left. Join for the summary."
        else:
            tip = f"🔔 '{course}' ends in {remaining} min. Prepare for next class."

        suggestions.append({
            'course': course, 'room': room, 'teacher': teacher,
            'late_mins': max(0, late_mins), 'remaining': remaining, 'suggestion': tip,
        })
    return {'suggestions': suggestions}


# ── Pages ─────────────────────────────────────────────────────

@academic_bp.route('/routine')
def routine_page():  return render_template('modules/routine.html')

@academic_bp.route('/courses')
def courses_page():  return render_template('modules/courses.html')


# ── API: Routine filtered by user's year+semester ─────────────

@academic_bp.route('/api/routine', methods=['GET'])
def get_routine():
    day      = request.args.get('day', '')
    program  = request.args.get('program', '')
    year     = request.args.get('year', '')
    semester = request.args.get('semester', '')

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*')
        if day:     q = q.eq('day', day)
        if program: q = q.eq('program', program)
        if year:    q = q.eq('course_year', int(year))
        if semester:q = q.eq('course_semester', int(semester))
        resp = q.order('time_start').execute()
        rows = _enrich(resp.data or [], sb)
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Live class ───────────────────────────────────────────

@academic_bp.route('/api/live-class', methods=['GET'])
def get_live_class():
    day      = request.args.get('day', '')
    time_now = request.args.get('time', '')
    program  = request.args.get('program', '')
    year     = request.args.get('year', '')
    semester = request.args.get('semester', '')

    if not day or not time_now:
        return jsonify({'success': False, 'error': 'day and time required'}), 400

    is_hol, hol_name = is_holiday(date.today())
    if is_hol:
        return jsonify({
            'success': True, 'live': None,
            'is_holiday': True, 'holiday_name': hol_name,
            'message': f'No classes today — {hol_name} 🎉',
        })

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*').eq('day', day)\
              .lte('time_start', time_now).gte('time_end', time_now)
        if program: q = q.eq('program', program)
        if year:    q = q.eq('course_year', int(year))
        if semester:q = q.eq('course_semester', int(semester))
        resp = q.execute()
        data = _enrich(resp.data or [], sb)
        return jsonify({'success': True, 'live': data, 'is_holiday': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Duration search ──────────────────────────────────────

@academic_bp.route('/api/duration-search', methods=['GET'])
def duration_search():
    from_t   = request.args.get('from', '')
    to_t     = request.args.get('to', '')
    day      = request.args.get('day', '')
    program  = request.args.get('program', '')
    year     = request.args.get('year', '')
    semester = request.args.get('semester', '')

    if not from_t or not to_t:
        return jsonify({'error': 'from and to required'}), 400

    def norm(t):
        p = t.split(':')
        return f"{p[0].zfill(2)}:{p[1].zfill(2)}"

    try:
        fn, tn = norm(from_t), norm(to_t)
    except Exception:
        return jsonify({'error': 'Use HH:MM format'}), 400

    if fn >= tn:
        return jsonify({'error': 'From must be before To'}), 400

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*').lt('time_start', tn).gt('time_end', fn)
        if day:     q = q.eq('day', day)
        if program: q = q.eq('program', program)
        if year:    q = q.eq('course_year', int(year))
        if semester:q = q.eq('course_semester', int(semester))
        resp = q.order('time_start').execute()
        rows = _enrich(resp.data or [], sb)
        ml   = _ml_suggestion(fn, rows)
        return jsonify({'success': True, 'data': rows, 'ml': ml, 'window': {'from': fn, 'to': tn}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Time-point search ────────────────────────────────────

@academic_bp.route('/api/time-search', methods=['GET'])
def time_search():
    tq       = request.args.get('time', '')
    day      = request.args.get('day', '')
    program  = request.args.get('program', '')
    year     = request.args.get('year', '')
    semester = request.args.get('semester', '')

    if not tq: return jsonify({'error': 'time required'}), 400
    p = tq.split(':')
    if len(p) != 2: return jsonify({'error': 'Use HH:MM'}), 400
    tn = f"{p[0].zfill(2)}:{p[1].zfill(2)}"

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*').lte('time_start', tn).gte('time_end', tn)
        if day:     q = q.eq('day', day)
        if program: q = q.eq('program', program)
        if year:    q = q.eq('course_year', int(year))
        if semester:q = q.eq('course_semester', int(semester))
        resp = q.execute()
        rows = _enrich(resp.data or [], sb)
        ml   = _ml_suggestion(tn, rows)
        return jsonify({'success': True, 'data': rows, 'ml': ml})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Holiday check ────────────────────────────────────────

@academic_bp.route('/api/holiday-check', methods=['GET'])
def holiday_check():
    date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        return jsonify({'error': 'Use YYYY-MM-DD'}), 400
    is_hol, name = is_holiday(d)
    return jsonify({'is_holiday': is_hol, 'name': name, 'upcoming': get_upcoming_holidays(30)})


@academic_bp.route('/api/mappings', methods=['GET'])
def get_mappings():
    sb = get_supabase_admin()
    try:
        resp = sb.table('mappings').select('*').execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500