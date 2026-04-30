"""
app/academic/routes.py
══════════════════════
CRITICAL FIX in get_routine():
  REMOVED the fallback that returned ALL classes when a
  semester had no classes that day.

  Before (wrong):
      if not rows and program and year and semester:
          rows = all_day_classes   # ← showed every batch's classes!

  After (correct):
      # no fallback — empty = no classes for this batch today
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from core.holidays import is_holiday, get_upcoming_holidays
from datetime import datetime, date

academic_bp = Blueprint('academic', __name__)


def _get_mapping(sb) -> dict:
    try:
        rows = sb.table('mappings').select('code,full_name').execute().data or []
        return {r['code']: r['full_name'] for r in rows}
    except Exception:
        return {}


def _enrich(rows: list, mapping: dict) -> list:
    for row in rows:
        row['course_name']  = mapping.get(row.get('course_code',  ''), row.get('course_code',  ''))
        row['teacher_name'] = mapping.get(row.get('teacher_code', ''), row.get('teacher_code', ''))
    return rows


def _fmt12h(t: str) -> str:
    try:
        h, m = map(int, str(t).split(':'))
        return f"{h%12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    except Exception:
        return t or ''


def _with_12h(rows):
    for r in rows:
        r['time_start_12h'] = _fmt12h(r.get('time_start', ''))
        r['time_end_12h']   = _fmt12h(r.get('time_end',   ''))
    return rows


def _apply_filters(q, program: str, year: str, semester: str):
    """
    Apply semester/year/program filters with NO fallback.
    If no rows match, the caller receives an empty list.
    """
    if program and year and semester:
        try:
            q = q.eq('program', program) \
                 .eq('course_year',     int(year)) \
                 .eq('course_semester', int(semester))
        except Exception:
            pass
    return q


# ── Pages ──────────────────────────────────────────────────────

@academic_bp.route('/routine')
def routine_page():
    return render_template('modules/routine.html')

@academic_bp.route('/courses')
def courses_page():
    return render_template('modules/courses.html')


# ── API: Routine ───────────────────────────────────────────────

@academic_bp.route('/api/routine', methods=['GET'])
def get_routine():
    day      = request.args.get('day',      '').strip()
    program  = request.args.get('program',  '').strip()
    year     = request.args.get('year',     '').strip()
    semester = request.args.get('semester', '').strip()

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*')
        if day:
            q = q.eq('day', day)
        q = _apply_filters(q, program, year, semester)
        rows = q.order('time_start').execute().data or []

        # ── NO FALLBACK ───────────────────────────────────────
        # If this batch has no classes today → return []
        # The frontend will show "No classes scheduled"
        # DO NOT fall back to showing all batches' classes.
        # ─────────────────────────────────────────────────────

        rows = _with_12h(_enrich(rows, _get_mapping(sb)))
        return jsonify({
            'success':       True,
            'data':          rows,
            'count':         len(rows),
            'no_class_today': len(rows) == 0,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'data': []}), 500


# ── API: Live class ────────────────────────────────────────────

@academic_bp.route('/api/live-class', methods=['GET'])
def get_live_class():
    day      = request.args.get('day',      '').strip()
    time_now = request.args.get('time',     '').strip()
    program  = request.args.get('program',  '').strip()
    year     = request.args.get('year',     '').strip()
    semester = request.args.get('semester', '').strip()

    if not day or not time_now:
        return jsonify({'success': False, 'error': 'day and time required'}), 400

    is_hol, hol_name = is_holiday(date.today())
    if is_hol:
        return jsonify({'success': True, 'live': [],
                        'is_holiday': True, 'holiday_name': hol_name})

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*') \
              .eq('day', day) \
              .lte('time_start', time_now) \
              .gte('time_end',   time_now)
        q = _apply_filters(q, program, year, semester)
        rows = _with_12h(_enrich(q.execute().data or [], _get_mapping(sb)))
        return jsonify({'success': True, 'live': rows, 'is_holiday': False})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Duration search ───────────────────────────────────────

@academic_bp.route('/api/duration-search', methods=['GET'])
def duration_search():
    from_t   = request.args.get('from',     '').strip()
    to_t     = request.args.get('to',       '').strip()
    day      = request.args.get('day',      '').strip()
    program  = request.args.get('program',  '').strip()
    year     = request.args.get('year',     '').strip()
    semester = request.args.get('semester', '').strip()

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
        q = sb.table('routines').select('*') \
              .lt('time_start', tn) \
              .gt('time_end',   fn)
        if day:
            q = q.eq('day', day)
        q = _apply_filters(q, program, year, semester)
        rows = _with_12h(_enrich(q.order('time_start').execute().data or [], _get_mapping(sb)))
        return jsonify({'success': True, 'data': rows,
                        'count': len(rows), 'window': {'from': fn, 'to': tn}})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Holiday check ─────────────────────────────────────────

@academic_bp.route('/api/holiday-check', methods=['GET'])
def holiday_check():
    date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        return jsonify({'error': 'Use YYYY-MM-DD'}), 400
    is_hol, name = is_holiday(d)
    return jsonify({
        'is_holiday': is_hol,
        'name':       name,
        'upcoming':   get_upcoming_holidays(30),
    })


# ── API: Mappings ──────────────────────────────────────────────

@academic_bp.route('/api/mappings', methods=['GET'])
def get_mappings():
    sb = get_supabase_admin()
    try:
        return jsonify({'success': True,
                        'data': sb.table('mappings').select('*').execute().data or []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Dashboard Schedule ────────────────────────────────────

@academic_bp.route('/api/dashboard-schedule', methods=['GET'])
def dashboard_schedule():
    """
    Returns classes for today/tomorrow.
    FIXED: If this batch has no classes → returns empty list + no_class_today=True
    NEVER falls back to showing other batches' classes.
    """
    try:
        from core.schedule_utils import get_schedule_target, fmt12h, classify_class_status
    except ImportError:
        return jsonify({'success': False, 'error': 'schedule_utils not found'}), 500

    target   = get_schedule_target()
    day_name = target['day_name']
    mode     = target['mode']
    bst_time = target['bst_time']
    label    = target['display_label']

    is_hol, hol_name = is_holiday(target['date'])
    if is_hol:
        return jsonify({
            'success':       True, 'mode': mode, 'day': day_name,
            'label':         label, 'bst_time': bst_time,
            'is_holiday':    True, 'holiday_name': hol_name,
            'no_class_today': False, 'classes': [],
        })

    program  = request.args.get('program',  '').strip()
    year     = request.args.get('year',     '').strip()
    semester = request.args.get('semester', '').strip()

    sb = get_supabase_admin()
    try:
        q = sb.table('routines').select('*').eq('day', day_name)
        q = _apply_filters(q, program, year, semester)
        rows = q.order('time_start').execute().data or []

        # ── NO FALLBACK ───────────────────────────────────────
        no_class_today = (len(rows) == 0)
        # ─────────────────────────────────────────────────────

        rows = _enrich(rows, _get_mapping(sb))
        enriched = []
        for cls in rows:
            ts = cls.get('time_start', '') or ''
            te = cls.get('time_end',   '') or ''
            cls['time_start_12h'] = fmt12h(ts)
            cls['time_end_12h']   = fmt12h(te)
            try:
                sh, sm = map(int, ts.split(':'))
                eh, em = map(int, te.split(':'))
                cls['duration_mins'] = (eh*60+em) - (sh*60+sm)
            except Exception:
                cls['duration_mins'] = 0
            cls.update(classify_class_status(ts, te, bst_time, mode))
            enriched.append(cls)

        return jsonify({
            'success':       True, 'mode': mode, 'day': day_name,
            'label':         label, 'bst_time': bst_time,
            'is_holiday':    False, 'holiday_name': None,
            'no_class_today': no_class_today,
            'classes':       enriched,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Time search (alias) ───────────────────────────────────

@academic_bp.route('/api/time-search', methods=['GET'])
def time_search():
    return duration_search()