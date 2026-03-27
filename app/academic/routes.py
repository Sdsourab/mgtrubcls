from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from core.holidays import is_holiday, get_upcoming_holidays
from datetime import datetime, date

academic_bp = Blueprint('academic', __name__)

# ── Helper ────────────────────────────────────────────────────

def _enrich_rows(rows, sb):
    """Add course_name and teacher_name to routine rows."""
    for row in rows:
        c = sb.table('mappings').select('full_name').eq('code', row.get('course_code', '')).execute()
        t = sb.table('mappings').select('full_name').eq('code', row.get('teacher_code', '')).execute()
        row['course_name']  = c.data[0]['full_name'] if c.data else row.get('course_code', '')
        row['teacher_name'] = t.data[0]['full_name'] if t.data else row.get('teacher_code', '')
    return rows


def _ml_suggestion(time_str: str, classes: list) -> dict:
    """
    Rule-based heuristic engine.
    Given a time (HH:MM) and list of classes for that time window,
    return a practical suggestion.
    """
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
            # Class hasn't started yet
            mins_until = abs(late_mins)
            if mins_until <= 10:
                tip = f"⚡ '{course}' starts in {mins_until} min — head to Room {room} now!"
            elif mins_until <= 30:
                tip = f"🕐 '{course}' starts in {mins_until} min. Finish what you're doing and get ready."
            else:
                tip = f"📖 You have {mins_until} min before '{course}'. Great time to review notes!"

        elif 1 <= late_mins <= 15:
            tip = f"🚶 You are {late_mins} min late for '{course}'. Head to Room {room} — lecture intro is still on."

        elif 16 <= late_mins <= 30:
            tip = f"⚠️ You missed {late_mins} min of '{course}'. Join now in Room {room} — core content is starting."

        elif 31 <= late_mins <= 50:
            tip = (
                f"📝 You missed {late_mins} min of '{course}'. "
                f"Only {remaining} min left. Join if you can, or get notes from a classmate."
            )

        elif late_mins > 50 and remaining > 20:
            tip = f"⏳ You are very late for '{course}'. {remaining} min remaining. Join for the summary or wait for the next class."

        elif remaining <= 10:
            tip = f"🔔 '{course}' ends in {remaining} min. Prepare for the next class — check your routine."

        else:
            tip = f"📚 '{course}' with {teacher} | Room {room} | {remaining} min remaining."

        suggestions.append({
            'course':     course,
            'room':       room,
            'teacher':    teacher,
            'late_mins':  late_mins if late_mins > 0 else 0,
            'remaining':  remaining,
            'suggestion': tip,
        })

    return {'suggestions': suggestions}


# ── Pages ─────────────────────────────────────────────────────

@academic_bp.route('/routine')
def routine_page():
    return render_template('modules/routine.html')

@academic_bp.route('/courses')
def courses_page():
    return render_template('modules/courses.html')


# ── API: Full routine with program/year/semester filter ────────

@academic_bp.route('/api/routine', methods=['GET'])
def get_routine():
    day      = request.args.get('day', '')
    program  = request.args.get('program', '')
    year     = request.args.get('year', '')
    semester = request.args.get('semester', '')

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*')
        if day:
            q = q.eq('day', day)
        if program:
            # show rows matching the user's program OR 'ALL'
            q = q.in_('program', [program, 'ALL'])
        resp = q.order('time_start').execute()
        rows = resp.data or []
        rows = _enrich_rows(rows, sb)
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Live class (with holiday check) ──────────────────────

@academic_bp.route('/api/live-class', methods=['GET'])
def get_live_class():
    day      = request.args.get('day', '')
    time_now = request.args.get('time', '')
    program  = request.args.get('program', '')

    if not day or not time_now:
        return jsonify({'success': False, 'error': 'day and time required'}), 400

    # Holiday check
    today = date.today()
    is_hol, hol_name = is_holiday(today)
    if is_hol:
        return jsonify({
            'success':    True,
            'live':       None,
            'is_holiday': True,
            'holiday_name': hol_name,
            'message':    f'No classes today — {hol_name} 🎉',
        })

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*')\
            .eq('day', day)\
            .lte('time_start', time_now)\
            .gte('time_end',   time_now)
        if program:
            q = q.in_('program', [program, 'ALL'])
        resp = q.execute()
        data = _enrich_rows(resp.data or [], sb)

        return jsonify({'success': True, 'live': data, 'is_holiday': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Time search (single time point) ─────────────────────

@academic_bp.route('/api/time-search', methods=['GET'])
def time_search():
    time_query = request.args.get('time', '')
    day        = request.args.get('day', '')
    program    = request.args.get('program', '')

    if not time_query:
        return jsonify({'error': 'time param required'}), 400

    parts = time_query.split(':')
    if len(parts) != 2:
        return jsonify({'error': 'Use HH:MM format'}), 400

    time_norm = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*')\
            .lte('time_start', time_norm)\
            .gte('time_end',   time_norm)
        if day:
            q = q.eq('day', day)
        if program:
            q = q.in_('program', [program, 'ALL'])
        resp = q.execute()
        rows = _enrich_rows(resp.data or [], sb)

        # Generate ML suggestions
        ml = _ml_suggestion(time_norm, rows)

        return jsonify({'success': True, 'data': rows, 'ml': ml})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Duration search (time window) ────────────────────────

@academic_bp.route('/api/duration-search', methods=['GET'])
def duration_search():
    """
    Find all classes active within a time window.
    Params: from=HH:MM, to=HH:MM, day=, program=
    A class is "in window" if it overlaps with [from, to].
    """
    from_time = request.args.get('from', '')
    to_time   = request.args.get('to', '')
    day       = request.args.get('day', '')
    program   = request.args.get('program', '')

    if not from_time or not to_time:
        return jsonify({'error': 'from and to params required'}), 400

    def norm(t):
        p = t.split(':')
        return f"{p[0].zfill(2)}:{p[1].zfill(2)}"

    try:
        from_norm = norm(from_time)
        to_norm   = norm(to_time)
    except Exception:
        return jsonify({'error': 'Invalid time format. Use HH:MM'}), 400

    if from_norm >= to_norm:
        return jsonify({'error': 'From time must be before To time'}), 400

    sb = get_supabase_admin()
    try:
        # Overlap condition: class_start < to AND class_end > from
        q = sb.table('routines').select('*')\
            .lt('time_start', to_norm)\
            .gt('time_end',   from_norm)
        if day:
            q = q.eq('day', day)
        if program:
            q = q.in_('program', [program, 'ALL'])
        resp = q.order('time_start').execute()
        rows = _enrich_rows(resp.data or [], sb)

        # ML hint for the FROM time
        ml = _ml_suggestion(from_norm, rows)

        return jsonify({'success': True, 'data': rows, 'ml': ml, 'window': {'from': from_norm, 'to': to_norm}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Holiday info ─────────────────────────────────────────

@academic_bp.route('/api/holiday-check', methods=['GET'])
def holiday_check():
    date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        return jsonify({'error': 'Use YYYY-MM-DD format'}), 400

    is_hol, name = is_holiday(d)
    upcoming = get_upcoming_holidays(30)
    return jsonify({'is_holiday': is_hol, 'name': name, 'upcoming': upcoming})


# ── API: Mappings ─────────────────────────────────────────────

@academic_bp.route('/api/mappings', methods=['GET'])
def get_mappings():
    sb = get_supabase_admin()
    try:
        resp = sb.table('mappings').select('*').execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500