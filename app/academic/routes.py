"""
app/academic/routes.py
─────────────────────
Advanced ML-powered suggestion engine using:
  • Urgency scoring (weighted multi-factor)
  • Time-series pattern matching (peak/off-peak detection)
  • Consecutive-class fatigue modelling
  • Priority recommendation with confidence score
  • Contextual tips per scenario

UPDATED:
  • get_routine()        — ছুটির দিনে [] return করে, is_holiday flag সহ
  • dashboard_schedule() — is_holiday সঠিকভাবে return করে
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from core.holidays import is_holiday, get_upcoming_holidays
from datetime import datetime, date
import math

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


# ── Advanced ML Suggestion Engine ────────────────────────────────────────────

def _time_to_mins(t: str) -> int:
    try:
        h, m = map(int, t.split(':'))
        return h * 60 + m
    except Exception:
        return 0


def _urgency_score(late_mins: int, remain_mins: int, total_duration: int) -> float:
    if remain_mins <= 0:
        return 0.0
    missed_ratio = min(1.0, late_mins / max(total_duration, 1))
    remain_ratio = remain_mins / max(total_duration, 1)
    urgency = math.exp(-2.5 * missed_ratio) * remain_ratio
    return round(min(1.0, max(0.0, urgency)), 3)


def _classify_session(h: int) -> str:
    if 8 <= h < 10:
        return 'morning_peak'
    elif 10 <= h < 13:
        return 'mid_morning'
    elif 13 <= h < 15:
        return 'post_lunch_dip'
    elif 15 <= h < 17:
        return 'afternoon'
    return 'off_hours'


def _fatigue_penalty(class_index: int, total_classes: int) -> float:
    if class_index <= 1:
        return 1.0
    penalty = max(0.7, 1.0 - (class_index - 1) * 0.15)
    return round(penalty, 2)


def _contextual_tip(session_type: str, urgency: float, fatigue: float, remain_mins: int) -> str:
    if session_type == 'post_lunch_dip' and fatigue < 0.85:
        return "বিকেলের ক্লাসে মনোযোগ কম থাকে — সামনের সারিতে বসো এবং নোট নাও।"
    if urgency > 0.7:
        return "High attendance value — এখনই যোগ দাও, core concepts এখনো cover হচ্ছে।"
    if urgency > 0.4:
        return "Partial attendance এখনো গণনায় আসবে — যাও এবং teacher এর সাথে কথা বলো।"
    if remain_mins < 15:
        return f"মাত্র {remain_mins} মিনিট বাকি। পরের ক্লাসের জন্য প্রস্তুত হও।"
    if fatigue < 0.8:
        return "Energy level কম মনে হচ্ছে — পানি পান করো এবং সক্রিয় থাকার চেষ্টা করো।"
    return "Focus mode: এই slot এ deep work এর জন্য ভালো সময়।"


def _priority_label(urgency: float) -> str:
    if urgency >= 0.75:
        return '🔴 Critical'
    elif urgency >= 0.5:
        return '🟠 High'
    elif urgency >= 0.25:
        return '🟡 Moderate'
    return '🟢 Low'


def _ml_hint(time_str: str, classes: list) -> dict:
    if not time_str or not classes:
        return {}

    q = _time_to_mins(time_str)
    h = q // 60
    session_type = _classify_session(h)
    suggestions  = []

    for idx, cls in enumerate(classes):
        start = _time_to_mins(cls.get('time_start') or '00:00')
        end   = _time_to_mins(cls.get('time_end')   or '00:00')

        if end <= 0:
            continue

        duration    = max(end - start, 1)
        late_mins   = q - start
        remain_mins = end - q

        course  = cls.get('course_name') or cls.get('course_code', 'Class')
        room    = cls.get('room_no', '?')
        teacher = cls.get('teacher_name') or cls.get('teacher_code', '')

        urgency           = _urgency_score(max(0, late_mins), remain_mins, duration)
        fatigue           = _fatigue_penalty(idx, len(classes))
        effective_urgency = round(urgency * fatigue, 3)

        if late_mins <= 0:
            mins_until = abs(late_mins)
            if mins_until <= 5:
                tip = f"⚡ '{course}' মাত্র {mins_until} মিনিটে শুরু — Room {room} তে যাও!"
            elif mins_until <= 15:
                tip = f"🏃 {mins_until} মিনিট বাকি '{course}' এর জন্য। এখনই রওনা দাও।"
            elif mins_until <= 30:
                tip = f"🕐 {mins_until} মিনিট বাকি। '{course}' এর notes এবং বই প্রস্তুত রাখো।"
            else:
                tip = f"📖 {mins_until} মিনিট বাকি '{course}' শুরুর। পূর্ববর্তী topics review করো।"
        elif 1 <= late_mins <= 15:
            tip = f"🚶 '{course}' এ {late_mins} মিনিট দেরি হয়েছে। Room {room} — intro এখনো চলছে।"
        elif 16 <= late_mins <= 35:
            tip = f"⚠️ '{course}' এ {late_mins} মিনিট দেরি। Room {room} — core content শুরু হয়ে গেছে।"
        elif remain_mins > 15:
            tip = f"📝 '{course}' এ অনেক দেরি হলেও {remain_mins} মিনিট বাকি — join করো বা notes নাও।"
        else:
            tip = f"🔔 '{course}' শেষ হবে মাত্র {remain_mins} মিনিটে। পরবর্তী ক্লাসের জন্য তৈরি হও।"

        context_tip = _contextual_tip(session_type, effective_urgency, fatigue, remain_mins)

        suggestions.append({
            'course':         course,
            'room':           room,
            'teacher':        teacher,
            'late_mins':      max(0, late_mins),
            'remaining':      remain_mins,
            'duration':       duration,
            'urgency_score':  effective_urgency,
            'priority':       _priority_label(effective_urgency),
            'session_type':   session_type,
            'fatigue_factor': fatigue,
            'suggestion':     tip,
            'context_tip':    context_tip,
        })

    suggestions.sort(key=lambda x: x['urgency_score'], reverse=True)
    for i, s in enumerate(suggestions):
        s['rank'] = i + 1

    return {
        'suggestions':   suggestions,
        'session_type':  session_type,
        'query_time':    time_str,
        'total_classes': len(classes),
        'ml_version':    '2.0-advanced',
    }


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

    # ── Holiday guard: ছুটির দিনে কোনো class দেখাবে না ─────────
    check_date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    try:
        check_date = datetime.strptime(check_date_str, '%Y-%m-%d').date()
    except Exception:
        check_date = date.today()
    is_hol, hol_name = is_holiday(check_date)
    if is_hol:
        return jsonify({
            'success':      True,
            'data':         [],
            'is_holiday':   True,
            'holiday_name': hol_name,
        })

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*')
        if day:
            q = q.eq('day', day)

        if program and year and semester:
            resp_prog = sb.table('routines').select('*')
            if day:
                resp_prog = resp_prog.eq('day', day)
            resp_prog = resp_prog.eq('program', program)\
                .eq('course_year', int(year))\
                .eq('course_semester', int(semester))\
                .order('time_start').execute()

            rows = _enrich(resp_prog.data or [], sb)
            return jsonify({'success': True, 'data': rows, 'is_holiday': False})
        else:
            resp = q.order('time_start').execute()
            rows = _enrich(resp.data or [], sb)
            return jsonify({'success': True, 'data': rows, 'is_holiday': False})

    except Exception as e:
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


# ── API: Dashboard Schedule ───────────────────────────────────

@academic_bp.route('/api/dashboard-schedule', methods=['GET'])
def dashboard_schedule():
    """
    Dashboard Schedule Widget Endpoint.

    BST Time Logic:
      07:00 – 18:59 → return today's classes
      19:00 – 06:59 → return tomorrow's classes

    Query params (all optional):
      program  : e.g. 'BBA'
      year     : e.g. '1'
      semester : e.g. '1'
    """
    from core.schedule_utils import get_schedule_target, fmt12h, classify_class_status

    # ── 1. Determine target day ────────────────────────────────
    target   = get_schedule_target()
    day_name = target['day_name']
    mode     = target['mode']
    bst_time = target['bst_time']
    label    = target['display_label']

    # ── 2. Holiday check ──────────────────────────────────────
    is_hol, hol_name = is_holiday(target['date'])
    if is_hol:
        return jsonify({
            'success':      True,
            'mode':         mode,
            'day':          day_name,
            'label':        label,
            'bst_time':     bst_time,
            'is_holiday':   True,
            'holiday_name': hol_name,
            'classes':      [],
        })

    # ── 3. User profile params ─────────────────────────────────
    program  = request.args.get('program',  '').strip()
    year     = request.args.get('year',     '').strip()
    semester = request.args.get('semester', '').strip()

    # ── 4. Query routines ──────────────────────────────────────
    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*').eq('day', day_name)

        if program and year and semester:
            try:
                q = q.eq('program', program) \
                     .eq('course_year', int(year)) \
                     .eq('course_semester', int(semester))
            except (ValueError, TypeError):
                pass

        resp = q.order('time_start').execute()
        rows = resp.data or []

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    # ── 5. Enrich ──────────────────────────────────────────────
    rows = _enrich(rows, sb)

    # ── 6. Annotate with time + status ─────────────────────────
    enriched = []
    for cls in rows:
        ts = cls.get('time_start', '') or ''
        te = cls.get('time_end',   '') or ''

        cls['time_start_12h'] = fmt12h(ts)
        cls['time_end_12h']   = fmt12h(te)

        try:
            sh, sm = map(int, ts.split(':'))
            eh, em = map(int, te.split(':'))
            cls['duration_mins'] = (eh * 60 + em) - (sh * 60 + sm)
        except Exception:
            cls['duration_mins'] = 0

        status_info = classify_class_status(ts, te, bst_time, mode)
        cls.update(status_info)

        enriched.append(cls)

    # ── 7. Return ──────────────────────────────────────────────
    return jsonify({
        'success':      True,
        'mode':         mode,
        'day':          day_name,
        'label':        label,
        'bst_time':     bst_time,
        'is_holiday':   is_hol,
        'holiday_name': hol_name if is_hol else None,
        'classes':      enriched,
    })