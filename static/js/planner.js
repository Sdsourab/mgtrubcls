/**
 * UniSync — AI Personal Planner  v5.1
 * ─────────────────────────────────────────────────────────────
 * KEY CHANGES v5.1:
 *  1. AI model is preloaded by ai-preloader.js (loaded from base.html)
 *  2. By the time user opens Planner, model is already warm/cached
 *  3. fetchAIAdvice() reads window.__aiState.pipeline — no duplicate load
 *  4. Listens to "ai-status" event to update badge in real-time
 *  5. Groq / server-side AI completely removed — now uses MiniLM-L6-v2 (23 MB)
 */

'use strict';

/* ── 12-hour time utility ── */
function to12h(t) {
  if (!t) return '';
  const [h, m] = String(t).split(':').map(Number);
  if (isNaN(h)) return t;
  const period = h < 12 ? 'AM' : 'PM';
  return `${h % 12 || 12}:${String(m).padStart(2,'0')} ${period}`;
}
function fmtRange(s, e) { return `${to12h(s)} – ${to12h(e)}`; }


let allPlans = [];

/* ================================================================
   DOM READY
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
  if (typeof UniSync !== 'undefined') UniSync.requireAuth();

  syncProfileFromDB().then(() => {
    loadPlans();
    loadSemesterCourses();
  });

  const today = new Date().toISOString().split('T')[0];
  ['cc_date', 'p_date'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = today;
  });

  // Sync badge with current preloader state immediately
  _syncBadgeFromState();

  // Listen for future state changes (model downloading / ready / error)
  window.addEventListener('ai-status', _syncBadgeFromState);
});

/* ================================================================
   AI STATUS BADGE SYNC
   ================================================================ */

function _syncBadgeFromState() {
  const state = window.__aiState || { status: 'idle' };
  const dot   = document.getElementById('aiBadgeDot');
  const text  = document.getElementById('aiBadgeText');
  const sub   = document.getElementById('aiBadgeSub');
  if (!dot || !text) return;

  if (state.status === 'idle' || state.status === 'loading') {
    dot.style.background  = 'var(--amber)';
    dot.style.boxShadow   = '0 0 6px var(--amber)';
    dot.style.animation   = 'pulse-green 1.8s infinite';
    text.style.color      = 'var(--amber)';
    text.textContent      = 'AI Loading…';
    if (sub) sub.textContent = '— Downloading model · runs 100% in your browser';

  } else if (state.status === 'ready') {
    dot.style.background  = 'var(--green)';
    dot.style.boxShadow   = '0 0 6px var(--green)';
    dot.style.animation   = 'pulse-green 1.8s infinite';
    text.style.color      = 'var(--green)';
    text.textContent      = '🤖 AI Ready';
    if (sub) sub.textContent = '— Transformers.js · MiniLM-L6-v2 · semantic AI · runs entirely in your browser';

  } else if (state.status === 'error') {
    dot.style.background  = 'var(--red, #f87171)';
    dot.style.boxShadow   = 'none';
    dot.style.animation   = 'none';
    text.style.color      = 'var(--red, #f87171)';
    text.textContent      = 'AI Unavailable';
    if (sub) sub.textContent = state.error
      ? `— ${state.error}`
      : '— Could not load AI model in this browser';
  }
}

/* ================================================================
   PROFILE SYNC
   ================================================================ */

async function syncProfileFromDB() {
  const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;
  if (!user || !user.id) return;

  try {
    const res  = await fetch(`/auth/api/profile?user_id=${user.id}`);
    const data = await res.json();
    if (data.success && data.data) {
      const profile = data.data;
      const merged = {
        ...user,
        full_name: profile.full_name || user.full_name,
        role:      profile.role      || user.role,
        dept:      profile.dept      || user.dept,
        program:   profile.program   || user.program  || 'BBA',
        year:      profile.year      || user.year     || 1,
        semester:  profile.semester  || user.semester || 1,
      };
      localStorage.setItem('us_user', JSON.stringify(merged));
    }
  } catch (e) {
    console.warn('Profile sync failed, using cached data:', e.message);
  }
}

/* ================================================================
   SEMESTER COURSES
   ================================================================ */

async function loadSemesterCourses() {
  const user      = getUser();
  const container = document.getElementById('semesterCoursesBox');
  if (!container) return;

  if (!user) {
    container.innerHTML = '<div class="ts-empty">Please log in to see your schedule.</div>';
    return;
  }

  const prog = user.program  || 'BBA';
  const yr   = user.year     || 1;
  const sem  = user.semester || 1;

  container.innerHTML = `<div class="ts-loading">Loading ${prog} Year ${yr} Sem ${sem} schedule…</div>`;

  try {
    const params = new URLSearchParams({ program: prog, year: yr, semester: sem });
    const res    = await fetch(`/academic/api/routine?${params}`);
    const data   = await res.json();

    if (!data.success || !data.data?.length) {
      container.innerHTML = `
        <div class="ts-empty" style="text-align:center;padding:20px;">
          No classes found for <strong>${prog} · Year ${yr} · Sem ${sem}</strong>.<br>
          <a href="/auth/profile" style="color:var(--accent-light);font-size:0.8rem;">
            Update your profile →
          </a>
        </div>`;
      return;
    }

    const DAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday'];
    const grouped = {};
    DAYS.forEach(d => grouped[d] = []);
    data.data.forEach(cls => { if (grouped[cls.day] !== undefined) grouped[cls.day].push(cls); });

    const uniqueCourses = {};
    data.data.forEach(cls => {
      if (!uniqueCourses[cls.course_code])
        uniqueCourses[cls.course_code] = cls.course_name || cls.course_code;
    });

    let html = `
      <div class="sem-course-summary">
        <div class="sem-course-chips">
          ${Object.entries(uniqueCourses).map(([code, name]) =>
            `<span class="sem-chip" title="${name}">${code}</span>`).join('')}
        </div>
        <div style="font-size:0.72rem;color:var(--text-muted);margin-top:6px;">
          ${Object.keys(uniqueCourses).length} course(s) · ${data.data.length} slot(s) ·
          <em>${prog} Year ${yr} Sem ${sem}</em>
        </div>
      </div>
      <div class="sem-day-grid">`;

    DAYS.forEach(day => {
      const classes = grouped[day];
      if (!classes.length) return;
      html += `
        <div class="sem-day-col">
          <div class="sem-day-header">${day}</div>
          ${classes.map(cls => `
            <div class="sem-class-item">
              <div class="sem-class-time">${to12h(cls.time_start)} – ${to12h(cls.time_end)}</div>
              <div class="sem-class-name">${cls.course_name || cls.course_code}</div>
              <div class="sem-class-meta">${cls.course_code} · Rm ${cls.room_no}</div>
              <div class="sem-class-teacher">${cls.teacher_name || cls.teacher_code || ''}</div>
            </div>`).join('')}
        </div>`;
    });

    html += '</div>';
    container.innerHTML = html;

  } catch (e) {
    container.innerHTML = `<div class="ts-empty">Failed to load schedule: ${e.message}</div>`;
  }
}

/* ================================================================
   CONFLICT CHECKER
   ================================================================ */

async function checkConflict() {
  const date  = (document.getElementById('cc_date') || {}).value || '';
  const _cc   = (typeof getCC === 'function') ? getCC() : {start:'', end:''};
  const start = _cc.start;
  const end   = _cc.end;
  const user  = getUser();

  if (!date || !start || !end) {
    toast('Please fill date, start and end time', 'warning'); return;
  }
  if (start >= end) {
    toast('Start time must be before end time', 'warning'); return;
  }

  const btn = document.getElementById('conflictBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Checking…'; }

  const resultDiv = document.getElementById('conflictResult');
  if (resultDiv) {
    resultDiv.innerHTML = '<div class="ts-loading">Checking conflicts against your semester schedule…</div>';
    resultDiv.classList.remove('hidden');
  }

  const prog = user?.program  || 'BBA';
  const yr   = parseInt(user?.year     || 0);
  const sem  = parseInt(user?.semester || 0);

  try {
    const res  = await fetch('/planner/api/conflict-check', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        date,
        start_time: start,
        end_time:   end,
        program:    prog,
        year:       yr,
        semester:   sem,
      }),
    });
    const data = await res.json();

    if (!data.success) {
      resultDiv.innerHTML =
        `<div class="ts-empty">⚠️ Check failed: ${esc(data.error || 'Unknown error')}. Try again.</div>`;
      return;
    }

    if (data.message) {
      resultDiv.innerHTML = `
        <div style="padding:14px;background:rgba(52,211,153,0.08);
                    border:1px solid rgba(52,211,153,0.25);border-radius:var(--radius-sm);">
          <div style="color:var(--green);font-weight:700;">✅ ${esc(data.message)}</div>
        </div>`;
      return;
    }

    const conflicts       = data.conflicts       || [];
    const semesterClasses = data.semester_classes || [];
    const dayLabel        = data.day || '';

    let html = '';

    // Full day schedule strip
    if (semesterClasses.length) {
      html += `
      <div style="margin-bottom:14px;padding:12px 14px;background:var(--bg-elevated);
                  border:1px solid var(--border);border-radius:var(--radius-sm);">
        <div style="font-size:0.72rem;font-weight:700;letter-spacing:0.08em;
                    text-transform:uppercase;color:var(--text-muted);margin-bottom:8px;">
          📅 Your classes on ${dayLabel}
        </div>
        ${semesterClasses.map(c => `
          <div style="display:flex;align-items:center;gap:10px;padding:6px 0;
                      border-bottom:1px solid var(--border);font-size:0.82rem;">
            <span style="color:var(--accent-light);font-weight:700;min-width:90px;">
              ${to12h(c.time_start)}
            </span>
            <span style="flex:1;">${esc(c.course_name || c.course_code)}</span>
            <span style="color:var(--text-muted);font-size:0.75rem;">Rm ${c.room_no}</span>
          </div>`).join('')}
      </div>`;
    } else {
      html += `
      <div style="margin-bottom:14px;padding:11px;background:var(--bg-elevated);
                  border:1px solid var(--border);border-radius:var(--radius-sm);
                  font-size:0.82rem;color:var(--text-muted);">
        ℹ️ No classes found for <strong>${prog} Year ${yr} Sem ${sem}</strong> on ${dayLabel}.
        <a href="/auth/profile" style="color:var(--accent-light);">Check your profile →</a>
      </div>`;
    }

    // Conflict result
    if (!conflicts.length) {
      html += `
      <div style="padding:14px;background:rgba(52,211,153,0.08);
                  border:1px solid rgba(52,211,153,0.25);border-radius:var(--radius-sm);">
        <div style="color:var(--green);font-weight:700;margin-bottom:4px;">✅ No Conflicts!</div>
        <div style="font-size:0.84rem;color:var(--text-muted);">
          Your plan ${to12h(start)} – ${to12h(end)} on <strong>${dayLabel}</strong>
          does not overlap with any of your semester's classes.
        </div>
      </div>`;
    } else {
      html += `
      <div class="conflict-box" style="margin-bottom:12px;">
        <div class="conflict-title">⚠️ ${conflicts.length} Conflict(s) on ${dayLabel}</div>
        ${conflicts.map(c => `
          <div class="conflict-item">
            📚 <strong>${esc(c.course_code)}</strong> — ${esc(c.course_name || c.course_code)}
            <span style="color:var(--text-muted);font-size:0.8rem;">
              &nbsp;|&nbsp; ${to12h(c.time_start)} – ${to12h(c.time_end)}
              &nbsp;|&nbsp; Room ${c.room_no}
              ${c.teacher_name ? `&nbsp;|&nbsp; ${esc(c.teacher_name)}` : ''}
            </span>
          </div>`).join('')}
      </div>`;
    }

    // AI advice block
    const aiState  = window.__aiState || {};
    const aiReady  = aiState.status === 'ready';
    const aiStatus = aiReady
      ? 'AI analysing your schedule…'
      : (aiState.status === 'loading' ? 'AI model loading… please wait' : 'AI unavailable');

    html += `
    <div class="ai-suggestion-box" style="margin-top:4px;">
      <div class="ai-suggestion-title" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
        <span>🤖 AI Smart Advice</span>
        <span id="aiSpinner" style="display:inline-flex;align-items:center;gap:5px;
              font-size:0.74rem;color:var(--text-muted);font-weight:400;">
          <span style="width:10px;height:10px;border:2px solid var(--text-muted);
                       border-top-color:var(--accent);border-radius:50%;display:inline-block;
                       animation:spin 0.75s linear infinite;"></span>
          ${aiStatus}
        </span>
      </div>
      <div class="ai-suggestion-text" id="aiSuggText">
        ${aiReady ? 'Generating personalised advice…' : 'Waiting for AI model…'}
      </div>
    </div>`;

    resultDiv.innerHTML = html;

    const conflictSummary = conflicts.length
      ? conflicts.map(c =>
          `${c.course_code} (${c.course_name || c.course_code}) ${to12h(c.time_start)}–${to12h(c.time_end)}`
        ).join('; ')
      : 'None';

    fetchAIAdvice({
      conflict_summary:  conflictSummary,
      day:               dayLabel,
      date,
      start,
      end,
      program:           prog,
      year:              yr,
      semester:          sem,
      semester_classes:  semesterClasses,
    });

  } catch (e) {
    resultDiv.innerHTML = `<div class="ts-empty">Error: ${esc(e.message)}</div>`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Check Conflicts'; }
  }
}

/* ================================================================
   AI ADVICE — semantic similarity via window.__aiEngine
   (MiniLM-L6-v2 · 23 MB · loaded by ai-preloader.js)
   ================================================================ */

/**
 * Build a semantic context string from the conflict-check payload.
 * This is embedded and compared against the ADVICE_DB in ai-preloader.js.
 */
function buildContext(payload) {
  const {
    conflict_summary, day, start, end,
    program, year, semester, semester_classes,
  } = payload;

  const hasConflict = conflict_summary &&
    !conflict_summary.toLowerCase().includes('none') &&
    conflict_summary.toLowerCase() !== 'no conflict';

  const conflictPart = hasConflict
    ? `class schedule conflict overlap ${conflict_summary}`
    : 'no conflict free time available clear window';

  const hour      = parseInt((start || '08').split(':')[0], 10);
  const timeOfDay = hour < 12 ? 'morning early hours' : hour < 15 ? 'afternoon mid-day' : 'evening night';

  const classDensity = (semester_classes || []).length > 3
    ? 'multiple classes busy day heavy schedule'
    : 'light schedule few classes';

  return [
    `${program || 'BBA'} Year ${year || 1} Semester ${semester || 1}`,
    'Rabindra University Bangladesh student',
    day || '',
    timeOfDay,
    conflictPart,
    classDensity,
  ].filter(Boolean).join(' ');
}

/**
 * Wait for AI engine to be ready (max 60 s for the 23 MB model),
 * then use semantic similarity to fetch the 4 most relevant tips.
 */
async function fetchAIAdvice(payload) {
  const textEl    = document.getElementById('aiSuggText');
  const spinnerEl = document.getElementById('aiSpinner');
  if (!textEl) return;

  // Poll until model ready — 23 MB model typically loads in < 15 s
  const MAX_WAIT = 60_000;
  const INTERVAL = 500;
  let waited = 0;

  while (
    (!window.__aiState ||
      window.__aiState.status === 'loading' ||
      window.__aiState.status === 'idle') &&
    waited < MAX_WAIT
  ) {
    await new Promise(r => setTimeout(r, INTERVAL));
    waited += INTERVAL;
    if (spinnerEl) {
      const pct  = window.__aiState?._pct;
      const node = spinnerEl.childNodes[1];
      if (node) node.nodeValue = pct ? ` AI loading… ${pct}%` : ' AI loading…';
    }
  }

  try {
    const state = window.__aiState || {};
    if (state.status !== 'ready' || !state.pipeline) {
      throw new Error(state.error || 'AI not available in this browser.');
    }
    if (!window.__aiEngine) {
      throw new Error('AI engine not initialised. Please refresh the page.');
    }

    if (spinnerEl) {
      spinnerEl.innerHTML = `
        <span style="width:10px;height:10px;border:2px solid var(--text-muted);
                     border-top-color:var(--accent);border-radius:50%;display:inline-block;
                     animation:spin 0.75s linear infinite;"></span>
        Matching advice…`;
    }

    const contextStr = buildContext(payload);
    const tips       = await window.__aiEngine.suggest(contextStr, 4);

    if (spinnerEl) spinnerEl.remove();

    if (!tips || !tips.length) throw new Error('No relevant advice found.');

    textEl.innerHTML =
      tips.map(tip =>
        `<div style="margin-bottom:9px;line-height:1.65;">${esc(tip)}</div>`
      ).join('') +
      `<div style="margin-top:10px;font-size:0.69rem;color:var(--text-muted);
                   border-top:1px solid var(--border);padding-top:6px;">
         🤖 Transformers.js · MiniLM-L6-v2 · semantic AI · runs entirely in your browser
       </div>`;

  } catch (err) {
    if (spinnerEl) spinnerEl.remove();
    textEl.innerHTML = `
      <div style="color:var(--amber);">⚠️ ${esc(err.message || 'AI advice unavailable.')}</div>
      <div style="font-size:0.78rem;color:var(--text-muted);margin-top:6px;">
        The conflict analysis above is still accurate and complete.
      </div>`;
  }
}

/* ================================================================
   PLANS CRUD
   ================================================================ */

async function loadPlans() {
  const user = getUser();
  if (!user) return;
  try {
    const res  = await fetch(`/planner/api/plans?user_id=${user.id}`);
    const data = await res.json();
    if (data.success) { allPlans = data.data; renderPlans(); }
  } catch (e) { console.error('loadPlans:', e); }
}

function renderPlans() {
  const list = document.getElementById('plansList');
  if (!list) return;
  if (!allPlans.length) {
    list.innerHTML = '<div class="empty-state"><p>No plans yet. Click "Add Plan" to start.</p></div>';
    return;
  }
  const typeColor = {
    personal: 'var(--accent-light)',
    tuition:  'var(--amber)',
    work:     'var(--cyan, #22d3ee)',
    other:    'var(--text-muted)',
  };
  list.innerHTML = allPlans.map(p => `
  <div class="plan-item">
    <div class="plan-type-dot" style="background:${typeColor[p.type] || 'var(--text-muted)'};
         width:8px;height:8px;border-radius:50%;flex-shrink:0;"></div>
    <div class="plan-info" style="flex:1;min-width:0;">
      <div class="plan-title">${esc(p.title)}</div>
      <div class="plan-meta">
        ${p.date} · ${to12h(p.start_time)} – ${to12h(p.end_time)}
        · <span style="text-transform:capitalize">${p.type}</span>
      </div>
      ${p.note ? `<div class="plan-meta" style="font-style:italic;">${esc(p.note)}</div>` : ''}
    </div>
    <button class="btn-sm btn-danger" onclick="deletePlan('${p.id}')"
            style="flex-shrink:0;">✕</button>
  </div>`).join('');
}

async function submitPlan(e) {
  e.preventDefault();
  const user = getUser();
  if (!user) return;
  const payload = {
    user_id:    user.id,
    title:      document.getElementById('p_title').value,
    type:       document.getElementById('p_type').value,
    date:       document.getElementById('p_date').value,
    start_time: (typeof getPlanTimes === 'function' ? getPlanTimes().start : document.getElementById('p_start')?.value) || '',
    end_time:   (typeof getPlanTimes === 'function' ? getPlanTimes().end   : document.getElementById('p_end')?.value)   || '',
    note:       (document.getElementById('p_note') || {}).value || '',
  };
  try {
    const res  = await fetch('/planner/api/plans', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.success) {
      toast('Plan saved!', 'success');
      document.getElementById('addPlanModal').classList.add('hidden');
      e.target.reset();
      loadPlans();
    } else {
      toast(data.error || 'Error saving plan', 'error');
    }
  } catch { toast('Connection error', 'error'); }
}

async function deletePlan(id) {
  if (!confirm('Delete this plan?')) return;
  try {
    await fetch(`/planner/api/plans/${id}`, { method: 'DELETE' });
    allPlans = allPlans.filter(p => p.id !== id);
    renderPlans();
    toast('Plan deleted.', 'success');
  } catch { toast('Error deleting', 'error'); }
}

function openAddPlan() {
  document.getElementById('addPlanModal').classList.remove('hidden');
}

/* ================================================================
   DURATION SEARCH — ADVANCED ML SUGGESTIONS
   ================================================================ */

async function runDurationSearch() {
  const from   = document.getElementById('dsFrom').value;
  const to     = document.getElementById('dsTo').value;
  const day    = document.getElementById('dsDay').value;
  const resDiv = document.getElementById('dsResults');
  const user   = getUser();

  if (!from || !to) { toast('Select both From and To time', 'warning'); return; }
  if (from >= to)   { toast('From must be before To', 'warning');        return; }

  resDiv.innerHTML = '<div class="ts-loading">Searching your schedule…</div>';
  resDiv.classList.remove('hidden');

  try {
    const prog = user?.program  || 'BBA';
    const yr   = user?.year     || 1;
    const sem  = user?.semester || 1;

    const params = new URLSearchParams({ from, to, program: prog, year: yr, semester: sem });
    if (day) params.set('day', day);

    const res  = await fetch(`/academic/api/duration-search?${params}`);
    const data = await res.json();

    if (!data.success) { resDiv.innerHTML = '<div class="ts-empty">Search failed.</div>'; return; }

    if (!data.data.length) {
      resDiv.innerHTML = '<div class="ts-empty">✅ No classes in this time window for your semester.</div>';
      return;
    }

    let html = data.data.map(c => `
    <div class="ts-result-item">
      <div class="ts-result-code">${esc(c.course_code)}</div>
      <div class="ts-result-info">
        <div class="ts-result-name">${esc(c.course_name || c.course_code)}</div>
        <div class="ts-result-meta">Room ${c.room_no} · ${esc(c.teacher_name || c.teacher_code)} · ${c.day}</div>
      </div>
      <div class="ts-result-time">${to12h(c.time_start)}–${to12h(c.time_end)}</div>
    </div>`).join('');

    if (data.ml?.suggestions?.length) {
      const sessionEmoji = {
        morning_peak: '🌅', mid_morning: '☀️',
        post_lunch_dip: '😴', afternoon: '🌤️', off_hours: '🌙',
      }[data.ml.session_type] || '🧠';

      const sessionLabel = {
        morning_peak:   'Morning Peak — High focus window',
        mid_morning:    'Mid-Morning — Optimal learning time',
        post_lunch_dip: 'Post-Lunch Dip — Stay active!',
        afternoon:      'Afternoon — Moderate energy',
        off_hours:      'Off Hours',
      }[data.ml.session_type] || 'Current Session';

      html += `
      <div class="ml-suggestion-box" style="margin-top:16px;border-radius:var(--radius-sm);
           background:var(--bg-elevated);border:1px solid var(--border-strong);padding:16px;">
        <div style="display:flex;align-items:center;justify-content:space-between;
                    flex-wrap:wrap;gap:8px;margin-bottom:12px;">
          <div style="font-weight:700;font-size:0.9rem;">🧠 Advanced ML Smart Suggestions</div>
          <div style="font-size:0.7rem;color:var(--text-muted);background:var(--bg-card);
                      padding:3px 10px;border-radius:20px;border:1px solid var(--border);">
            ${sessionEmoji} ${sessionLabel}
          </div>
        </div>`;

      data.ml.suggestions.forEach(s => {
        const pct = Math.round((s.urgency_score || 0) * 100);
        const barColor = pct >= 70 ? 'var(--red)' : pct >= 45 ? 'var(--amber)' : 'var(--green)';
        const fatigueNote = (s.fatigue_factor != null && s.fatigue_factor < 0.9)
          ? `<span style="color:var(--amber);font-size:0.68rem;">⚡ Fatigue ${Math.round((1 - s.fatigue_factor) * 100)}%</span>`
          : '';

        html += `
        <div style="margin-bottom:10px;padding:11px 14px;background:var(--bg-card);
                    border-left:3px solid ${barColor};
                    border-radius:0 var(--radius-sm) var(--radius-sm) 0;">
          <div style="display:flex;align-items:center;justify-content:space-between;
                      gap:6px;margin-bottom:5px;flex-wrap:wrap;">
            <span style="font-weight:600;font-size:0.82rem;">#${s.rank || ''} ${esc(s.priority || '')}</span>
            <div style="display:flex;align-items:center;gap:8px;">
              ${fatigueNote}
              <span style="font-size:0.69rem;color:var(--text-muted);">Urgency ${pct}%</span>
            </div>
          </div>
          <div style="font-size:0.83rem;margin-bottom:6px;line-height:1.5;">${esc(s.suggestion)}</div>
          <div style="height:3px;background:var(--bg-elevated);border-radius:3px;margin:6px 0;">
            <div style="height:3px;width:${pct}%;background:${barColor};
                        border-radius:3px;transition:width 0.7s ease;"></div>
          </div>
          ${s.context_tip ? `
          <div style="font-size:0.75rem;color:var(--text-muted);font-style:italic;
                      border-top:1px solid var(--border);padding-top:5px;margin-top:4px;">
            💡 ${esc(s.context_tip)}
          </div>` : ''}
        </div>`;
      });

      html += `
        <div style="font-size:0.68rem;color:var(--text-muted);text-align:right;margin-top:4px;">
          ML ${esc(data.ml.ml_version || '2.0')} · ${data.ml.total_classes || 0} class(es) analysed
        </div>
      </div>`;
    }

    resDiv.innerHTML = html;
  } catch (e) {
    resDiv.innerHTML = '<div class="ts-empty">Connection error. Check server.</div>';
  }
}

/* ================================================================
   HELPERS
   ================================================================ */

function getUser() {
  try {
    const u = localStorage.getItem('us_user');
    return u ? JSON.parse(u) : null;
  } catch { return null; }
}

function toast(msg, type) {
  if (typeof UniSync !== 'undefined') UniSync.toast(msg, type);
}

function esc(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}