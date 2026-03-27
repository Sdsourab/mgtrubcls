from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from core.holidays import is_holiday, get_upcoming_holidays
from datetime import datetime, date

academic_bp = Blueprint('academic', __name__)


def _enrich(rows, sb):
    """Add course_name and teacher_name to rows."""
    for row in rows:
        try:
            c = sb.table('mappings').select('full_name')\
                .eq('code', row.get('course_code', '')).execute()
            row['course_name'] = c.data[0]['full_name'] if c.data else row.get('course_code', '')
        except Exception:
            row['course_name'] = row.get('course_code', '')

        try:
            t = sb.table('mappings').select('full_name')\
                .eq('code', row.get('teacher_code', '')).execute()
            row['teacher_name'] = t.data[0]['full_name'] if t.data else row.get('teacher_code', '')
        except Exception:
            row['teacher_name'] = row.get('teacher_code', '')
    return rows


def _ml_hint(time_str: str, classes: list) -> dict:
    """Rule-based smart suggestion engine."""
    if not time_str or not classes:
        return {}
    try:
        h, m = map(int, time_str.split(':'))
        q = h * 60 + m
    except Exception:
        return {}

    suggestions = []
    for cls in classes:
        try:
            sh, sm = map(int, (cls.get('time_start') or '00:00').split(':'))
            eh, em = map(int, (cls.get('time_end')   or '00:00').split(':'))
        except Exception:
            continue

        start  = sh * 60 + sm
        end    = eh * 60 + em
        late   = q - start
        remain = end - q
        course  = cls.get('course_name') or cls.get('course_code', 'Class')
        room    = cls.get('room_no', '?')

        if late <= 0:
            mins = abs(late)
            if   mins <= 5:  tip = f"⚡ '{course}' শুরু হবে {mins} মিনিটে — Room {room} এ যাও!"
            elif mins <= 15: tip = f"🏃 {mins} মিনিটে '{course}' শুরু। এখনই রওনা দাও।"
            elif mins <= 30: tip = f"🕐 {mins} মিনিট বাকি। '{course}' এর জন্য প্রস্তুত হও।"
            else:            tip = f"📖 {mins} মিনিট বাকি '{course}' শুরুর। Notes review করো।"
        elif 1 <= late <= 15:
            tip = f"🚶 '{course}' এ {late} মিনিট দেরি। Room {room} — intro এখনো চলছে।"
        elif 16 <= late <= 35:
            tip = f"⚠️ '{course}' এ {late} মিনিট দেরি। Room {room} এ যাও — core content শুরু।"
        elif remain > 15:
            tip = f"📝 '{course}' এ অনেক দেরি। {remain} মিনিট বাকি। Join করো বা notes নাও।"
        else:
            tip = f"🔔 '{course}' শেষ হবে {remain} মিনিটে। পরের class এর জন্য তৈরি হও।"

        suggestions.append({
            'course': course, 'room': room,
            'late_mins': max(0, late), 'remaining': remain,
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


# ── API: Routine ──────────────────────────────────────────────

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

        # If program/year/semester given, filter
        if program and year and semester:
            # Filter: show exact match OR program='ALL'
            # Supabase doesn't support OR across columns easily,
            # so we get all for program and filter in Python
            resp_prog = sb.table('routines').select('*')
            if day:
                resp_prog = resp_prog.eq('day', day)
            resp_prog = resp_prog.eq('program', program)\
                .eq('course_year', int(year))\
                .eq('course_semester', int(semester))\
                .order('time_start').execute()

            rows = _enrich(resp_prog.data or [], sb)
            return jsonify({'success': True, 'data': rows})
        else:
            resp = q.order('time_start').execute()
            rows = _enrich(resp.data or [], sb)
            return jsonify({'success': True, 'data': rows})

    except Exception as e:
        # Fallback: return all without filter
        try:
            q2 = sb.table('routines').select('*')
            if day:
                q2 = q2.eq('day', day)
            resp2 = q2.order('time_start').execute()
            rows2 = resp2.data or []
            return jsonify({'success': True, 'data': rows2, 'fallback': True})
        except Exception as e2:
            return jsonify({'success': False, 'error': str(e2)}), 500


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
        })

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*')\
            .eq('day', day)\
            .lte('time_start', time_now)\
            .gte('time_end',   time_now)

        if program and year and semester:
            q = q.eq('program', program)\
                 .eq('course_year', int(year))\
                 .eq('course_semester', int(semester))

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
        q = sb.table('routines').select('*')\
            .lt('time_start', tn)\
            .gt('time_end',   fn)

        if day:
            q = q.eq('day', day)
        if program and year and semester:
            q = q.eq('program', program)\
                 .eq('course_year', int(year))\
                 .eq('course_semester', int(semester))

        resp = q.order('time_start').execute()
        rows = _enrich(resp.data or [], sb)
        ml   = _ml_hint(fn, rows)
        return jsonify({
            'success': True, 'data': rows,
            'ml': ml, 'window': {'from': fn, 'to': tn}
        })
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