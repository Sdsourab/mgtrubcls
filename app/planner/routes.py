"""
app/planner/routes.py
─────────────────────
Planner blueprint:
  - Plans CRUD
  - Conflict checker  (handles year/semester=0 gracefully)
  - AI advice endpoint — powered by Groq API (server-side)

Groq API:
  Base URL : https://api.groq.com/openai/v1/chat/completions
  Auth     : Bearer GROQ_API_KEY  (set in .env or Vercel → Settings → Env Vars)
  Models   : Free-tier waterfall — tried in order until one succeeds.
  Docs     : https://console.groq.com/docs
  Sign up  : https://console.groq.com  (free, no credit card needed)

Why Groq instead of OpenRouter?
  - OpenRouter free endpoints are heavily rate-limited and go offline frequently.
  - Groq free tier is generous, extremely fast (LPU inference), and reliable.
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import datetime
import os
import urllib.request
import urllib.error
import json as _json

planner_bp = Blueprint('planner', __name__)

# ── Groq config ───────────────────────────────────────────────
GROQ_BASE = 'https://api.groq.com/openai/v1/chat/completions'

# Free-tier model waterfall — tried in order until one succeeds.
# NOTE: mixtral-8x7b-32768 removed — deprecated by Groq as of 2025.
GROQ_MODELS = [
    'llama-3.3-70b-versatile',   # Llama 3.3 70B  — best quality, very fast on Groq
    'llama-3.1-8b-instant',      # Llama 3.1 8B   — ultra-fast fallback
    'gemma2-9b-it',              # Gemma 2 9B     — reliable fallback
    'llama3-70b-8192',           # Llama 3 70B    — last resort
]

def _get_groq_key():
    """Read GROQ_API_KEY at request-time (not module load) for Vercel compatibility."""
    return os.environ.get('GROQ_API_KEY', '').strip()


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


# ── Groq AI Advice (server-side) ─────────────────────────────

@planner_bp.route('/api/ai-advice', methods=['POST'])
def ai_advice():
    """
    Calls Groq API with a free-model waterfall.
    Key is read server-side from GROQ_API_KEY env var at request-time.

    Request body (JSON):
      conflict_summary  : str
      day, date, start, end, program, year, semester : str/int
      semester_classes  : list

    Response:
      { success, advice, model }   on success
      { success, error, details }  on failure
    """
    api_key = _get_groq_key()

    if not api_key:
        return jsonify({
            'success': False,
            'error':   (
                'GROQ_API_KEY is not configured. '
                'Get a free key at https://console.groq.com → API Keys, '
                'then add GROQ_API_KEY in Vercel → Settings → Environment Variables.'
            )
        }), 503

    body             = request.get_json() or {}
    conflict_summary = body.get('conflict_summary', 'None')
    day              = body.get('day', '')
    date_str         = body.get('date', '')
    start            = body.get('start', '')
    end              = body.get('end', '')
    program          = body.get('program', 'BBA')
    year             = body.get('year', 1)
    semester         = body.get('semester', 1)
    semester_classes = body.get('semester_classes', [])

    if semester_classes:
        sched_lines = [
            f"  • {c.get('course_name', c.get('course_code', '?'))} "
            f"({c.get('course_code', '?')}) "
            f"{c.get('time_start', '?')}–{c.get('time_end', '?')} "
            f"Room {c.get('room_no', '?')}"
            for c in semester_classes
        ]
        schedule_ctx = "\n".join(sched_lines)
    else:
        schedule_ctx = "  (no classes scheduled for this day)"

    prompt = (
        f"I am a student at Rabindra University, Bangladesh — Department of Management.\n"
        f"Program: {program}, Year {year}, Semester {semester}.\n\n"
        f"My full class schedule for {day}:\n{schedule_ctx}\n\n"
        f"I want to schedule a personal commitment on {day} {date_str} "
        f"from {start} to {end}.\n"
        f"Conflicts with my classes: {conflict_summary}.\n\n"
        f"Give me 4–5 short, practical bullet points covering:\n"
        f"- Which commitment to prioritise and why\n"
        f"- How to catch up on any missed class material\n"
        f"- A concrete time management tip for this situation\n"
        f"- Encouragement to stay on track\n"
        f"Be concise, friendly, and encouraging. "
        f"Start each bullet with a relevant emoji."
    )

    all_errors = []

    for model in GROQ_MODELS:
        payload = {
            'model':       model,
            'messages':    [{'role': 'user', 'content': prompt}],
            'max_tokens':  700,
            'temperature': 0.72,
        }

        req = urllib.request.Request(
            GROQ_BASE,
            data    = _json.dumps(payload).encode('utf-8'),
            headers = {
                'Content-Type':  'application/json',
                'Authorization': f'Bearer {api_key}',
            },
            method = 'POST',
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = _json.loads(resp.read().decode('utf-8'))

                if 'error' in result:
                    err_msg = result['error'].get('message', str(result['error']))
                    all_errors.append(f'{model}: {err_msg}')
                    continue

                choices = result.get('choices', [])
                if not choices:
                    all_errors.append(f'{model}: empty choices')
                    continue

                text = choices[0].get('message', {}).get('content', '').strip()
                if not text:
                    all_errors.append(f'{model}: empty content')
                    continue

                return jsonify({
                    'success': True,
                    'advice':  text,
                    'model':   result.get('model', model),
                })

        except urllib.error.HTTPError as he:
            status = he.code
            try:
                err_body = he.read().decode('utf-8', errors='replace')
                err_json = _json.loads(err_body)
                msg = err_json.get('error', {}).get('message', err_body)
            except Exception:
                msg = f'HTTP {status}'

            all_errors.append(f'{model}: {msg}')

            if status in (401, 403):
                return jsonify({
                    'success': False,
                    'error':   f'Groq auth error: {msg}. Check your GROQ_API_KEY.',
                    'details': all_errors,
                }), 401

            continue

        except Exception as ex:
            all_errors.append(f'{model}: {ex}')
            continue

    return jsonify({
        'success': False,
        'error':   'All Groq models failed. Please try again later.',
        'details': all_errors,
    }), 502