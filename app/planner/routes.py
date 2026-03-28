"""
app/planner/routes.py
─────────────────────
Planner blueprint:
  - Plans CRUD
  - Conflict checker  (FIXED: handles year/semester=0 gracefully)
  - OpenRouter AI advice endpoint (server-side, key from Vercel env)

OpenRouter API:
  Base URL : https://openrouter.ai/api/v1/chat/completions
  Auth     : Bearer OPENROUTER_API_KEY  (set in Vercel → Settings → Env Vars)
  Models   : free tier uses  deepseek/deepseek-chat:free
             falls back to   meta-llama/llama-3.1-8b-instruct:free
             then            mistralai/mistral-7b-instruct:free
  Docs     : https://openrouter.ai/docs
"""

from flask import Blueprint, jsonify, request, render_template
from core.supabase_client import get_supabase_admin
from datetime import datetime
import os
import urllib.request
import urllib.error
import json as _json

planner_bp = Blueprint('planner', __name__)

# ── OpenRouter config ─────────────────────────────────────────
OPENROUTER_BASE = 'https://openrouter.ai/api/v1/chat/completions'

# Free-tier model waterfall — tried in order until one succeeds.
# All of these are free on OpenRouter (no per-token charge).
OPENROUTER_MODELS = [
    'deepseek/deepseek-chat:free',            # DeepSeek V3, very capable
    'deepseek/deepseek-r1:free',              # DeepSeek R1 reasoning model
    'meta-llama/llama-3.3-70b-instruct:free', # Llama 3.3 70B
    'meta-llama/llama-3.1-8b-instruct:free',  # Llama 3.1 8B, fast
    'mistralai/mistral-7b-instruct:free',     # Mistral 7B
    'google/gemma-2-9b-it:free',              # Gemma 2 9B
]


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


# ── Conflict Checker (FIXED) ──────────────────────────────────

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

    # Single bulk mapping lookup
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
        # Overlapping conflicts
        conflict_q = apply_filters(
            sb.table('routines').select('*')
              .eq('day', day_name)
              .lt('time_start', e)
              .gt('time_end',   s)
        )
        conflicts = enrich(conflict_q.execute().data or [])

        # Full day schedule for the user's semester
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


# ── OpenRouter AI Advice (server-side) ───────────────────────

@planner_bp.route('/api/ai-advice', methods=['POST'])
def ai_advice():
    """
    Calls OpenRouter.ai with a model waterfall (free-tier first).
    Key: OPENROUTER_API_KEY in Vercel environment variables.

    Request body (JSON):
      conflict_summary  : str   — e.g. "MGT-3103 09:00–10:30"
      day               : str   — e.g. "Monday"
      date              : str   — e.g. "2026-04-07"
      start             : str   — e.g. "09:00"
      end               : str   — e.g. "11:00"
      program           : str   — "BBA" | "MBA"
      year              : int
      semester          : int
      semester_classes  : list  — full day schedule rows

    Response (JSON):
      { success, advice, model }   on success
      { success, error }           on failure
    """
    api_key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not api_key:
        return jsonify({
            'success': False,
            'error':   (
                'AI is not configured. '
                'Add OPENROUTER_API_KEY to Vercel → Settings → Environment Variables.'
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

    # Build rich schedule context for the AI
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

    last_error = 'All OpenRouter models failed.'

    for model in OPENROUTER_MODELS:
        payload = {
            'model':       model,
            'messages':    [{'role': 'user', 'content': prompt}],
            'max_tokens':  700,
            'temperature': 0.72,
        }

        req = urllib.request.Request(
            OPENROUTER_BASE,
            data    = _json.dumps(payload).encode('utf-8'),
            headers = {
                'Content-Type':  'application/json',
                'Authorization': f'Bearer {api_key}',
                'HTTP-Referer':  'https://unisync.vercel.app',   # shown in OpenRouter dashboard
                'X-Title':       'UniSync — Rabindra University', # shown in OpenRouter dashboard
            },
            method = 'POST',
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = _json.loads(resp.read().decode('utf-8'))

                # Check for API-level error inside a 200 response (OpenRouter quirk)
                if 'error' in result:
                    last_error = f"{model}: {result['error'].get('message', str(result['error']))}"
                    continue

                choices = result.get('choices', [])
                if not choices:
                    last_error = f'{model}: empty choices'
                    continue

                text = choices[0].get('message', {}).get('content', '').strip()
                if not text:
                    last_error = f'{model}: empty content'
                    continue

                used_model = result.get('model', model)
                return jsonify({
                    'success': True,
                    'advice':  text,
                    'model':   used_model,
                })

        except urllib.error.HTTPError as he:
            status = he.code
            try:
                err_body = he.read().decode('utf-8', errors='replace')
                err_json = _json.loads(err_body)
                msg = err_json.get('error', {}).get('message', err_body)
            except Exception:
                msg = f'HTTP {status}'

            last_error = f'{model}: {msg}'

            # 401/403 = bad key → abort immediately, no point trying other models
            if status in (401, 403):
                return jsonify({
                    'success': False,
                    'error':   f'OpenRouter auth error: {msg}. Check your OPENROUTER_API_KEY.'
                }), 401

            # 429 rate limit / 503 overload → try next model
            continue

        except Exception as ex:
            last_error = f'{model}: {ex}'
            continue

    # All models exhausted
    return jsonify({'success': False, 'error': last_error}), 502