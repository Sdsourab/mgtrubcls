"""
app/planner/routes.py
─────────────────────
Planner blueprint:
  - Plans CRUD
  - Conflict checker  (handles year/semester=0 gracefully)

Note: AI advice is now handled entirely client-side using Transformers.js.
No external AI API key is required.
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import datetime

planner_bp = Blueprint('planner', __name__)


# ── Page ──────────────────────────────────────────────────────

@planner_bp.route('/')
def planner_page():
    return render_template('modules/planner.html')


# ── Plans CRUD ────────────────────────────────────────────────

@planner_bp.route('/api/plans', methods=['GET'])
def get_plans():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    sb = get_supabase_admin()
    try:
        resp = sb.table('plans').select('*') \
            .eq('user_id', user_id) \
            .order('date').order('start_time').execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@planner_bp.route('/api/plans', methods=['POST'])
def create_plan():
    data    = request.get_json() or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    sb = get_supabase_admin()
    try:
        payload = {
            'user_id':    user_id,
            'title':      data.get('title', ''),
            'type':       data.get('type', 'personal'),
            'date':       data.get('date', ''),
            'start_time': data.get('start_time', ''),
            'end_time':   data.get('end_time', ''),
            'note':       data.get('note', ''),
        }
        resp = sb.table('plans').insert(payload).execute()
        return jsonify({'success': True, 'data': resp.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@planner_bp.route('/api/plans/<plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    sb = get_supabase_admin()
    try:
        sb.table('plans').delete().eq('id', plan_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Conflict Checker ──────────────────────────────────────────

@planner_bp.route('/api/conflict-check', methods=['POST'])
def conflict_check():
    """
    FIXED:
    - year=0 / semester=0 no longer produces empty results.
    - Single bulk mapping query instead of N individual queries.
    - Returns semester_classes (full day schedule) alongside conflicts.
    """
    data       = request.get_json() or {}
    plan_date  = data.get('date', '')
    start_time = data.get('start_time', '')
    end_time   = data.get('end_time', '')
    program    = data.get('program', 'BBA')

    try:
        course_year     = int(data.get('year', 0))
        course_semester = int(data.get('semester', 0))
    except (TypeError, ValueError):
        course_year, course_semester = 0, 0

    if not all([plan_date, start_time, end_time]):
        return jsonify({'error': 'date, start_time, end_time required'}), 400

    try:
        d        = datetime.strptime(plan_date, '%Y-%m-%d')
        day_name = d.strftime('%A')
    except Exception:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    if day_name not in ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']:
        return jsonify({
            'success': True, 'conflicts': [], 'semester_classes': [],
            'day': day_name,
            'message': f'No university classes on {day_name}.'
        })

    def norm(t):
        p = t.split(':')
        return f"{p[0].zfill(2)}:{p[1].zfill(2)}"

    try:
        s = norm(start_time)
        e = norm(end_time)
    except Exception:
        return jsonify({'error': 'Invalid time format. Use HH:MM'}), 400

    if s >= e:
        return jsonify({'error': 'start_time must be before end_time'}), 400

    sb = get_supabase_admin()

    try:
        map_resp = sb.table('mappings').select('code,full_name').execute()
        mapping  = {r['code']: r['full_name'] for r in (map_resp.data or [])}
    except Exception:
        mapping = {}

    def enrich(rows):
        for row in rows:
            row['course_name']  = mapping.get(row.get('course_code',  ''), row.get('course_code',  ''))
            row['teacher_name'] = mapping.get(row.get('teacher_code', ''), row.get('teacher_code', ''))
        return rows

    def apply_filters(q):
        if program:
            q = q.eq('program', program)
        if course_year > 0:
            q = q.eq('course_year', course_year)
        if course_semester > 0:
            q = q.eq('course_semester', course_semester)
        return q

    try:
        conflict_q = apply_filters(
            sb.table('routines').select('*')
              .eq('day', day_name)
              .lt('time_start', e)
              .gt('time_end',   s)
        )
        conflicts = enrich(conflict_q.execute().data or [])

        sched_q = apply_filters(
            sb.table('routines').select('*').eq('day', day_name)
        ).order('time_start')
        semester_classes = enrich(sched_q.execute().data or [])

        return jsonify({
            'success':          True,
            'conflicts':        conflicts,
            'semester_classes': semester_classes,
            'day':              day_name,
            'plan_window':      {'start': s, 'end': e},
        })

    except Exception as ex:
        return jsonify({'success': False, 'error': str(ex)}), 500