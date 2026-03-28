/**
 * UniSync — AI Personal Planner  v4.0
 * ─────────────────────────────────────────────────────────────
 * KEY CHANGES:
 *  1. No user API key needed — AI powered by server-side DeepSeek
 *  2. Conflict checker BUG FIXED — year/semester=0 handled correctly
 *  3. Semester persists in localStorage across reload + re-login
 *  4. Conflict result shows full day schedule alongside conflicts
 *  5. AI advice includes full semester context
 */

'use strict';

let allPlans = [];

document.addEventListener('DOMContentLoaded', () => {
  if (typeof UniSync !== 'undefined') UniSync.requireAuth();

  // Sync user profile from DB on every load to keep semester fresh
  syncProfileFromDB().then(() => {
    loadPlans();
    loadSemesterCourses();
  });

  const today = new Date().toISOString().split('T')[0];
  ['cc_date', 'p_date'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = today;
  });
});

/* ================================================================
   PROFILE SYNC — keeps semester persistent and up-to-date
   ================================================================ */

/**
 * On every page load, fetches the latest profile from the DB
 * and merges it into localStorage. This ensures:
 *  - semester persists across browser reload
 *  - semester survives re-login (login always writes fresh profile)
 *  - if user updates profile on another device, it syncs here
 */
async function syncProfileFromDB() {
  const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;
  if (!user || !user.id) return;

  // If we already have valid year/semester locally, we're good
  // Still sync in background to catch profile changes
  try {
    const res  = await fetch(`/auth/api/profile?user_id=${user.id}`);
    const data = await res.json();
    if (data.success && data.data) {
      const profile = data.data;
      // Merge DB values into local user object
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
    // Network error — use cached local data, no problem
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
              <div class="sem-class-time">${cls.time_start}–${cls.time_end}</div>
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
   CONFLICT CHECKER (BUG FIXED)
   ================================================================ */

async function checkConflict() {
  const date  = (document.getElementById('cc_date')  || {}).value || '';
  const start = (document.getElementById('cc_start') || {}).value || '';
  const end   = (document.getElementById('cc_end')   || {}).value || '';
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

  // ── CRITICAL FIX: use real values, default to 0 only if truly missing ──
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

    // Weekend / holiday
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

    // ── Build result HTML ───────────────────────────────────
    let html = '';

    // -- Full day schedule strip ---
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
            <span style="color:var(--accent-light);font-weight:700;min-width:42px;">
              ${c.time_start}
            </span>
            <span style="flex:1;">${esc(c.course_name || c.course_code)}</span>
            <span style="color:var(--text-muted);font-size:0.75rem;">
              Rm ${c.room_no}
            </span>
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

    // -- Conflict / no-conflict result ---
    if (!conflicts.length) {
      html += `
      <div style="padding:14px;background:rgba(52,211,153,0.08);
                  border:1px solid rgba(52,211,153,0.25);border-radius:var(--radius-sm);">
        <div style="color:var(--green);font-weight:700;margin-bottom:4px;">✅ No Conflicts!</div>
        <div style="font-size:0.84rem;color:var(--text-muted);">
          Your plan ${start}–${end} on <strong>${dayLabel}</strong>
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
              &nbsp;|&nbsp; ${c.time_start}–${c.time_end}
              &nbsp;|&nbsp; Room ${c.room_no}
              ${c.teacher_name ? `&nbsp;|&nbsp; ${esc(c.teacher_name)}` : ''}
            </span>
          </div>`).join('')}
      </div>`;
    }

    // -- AI advice block (always shown) ---
    html += `
    <div class="ai-suggestion-box" style="margin-top:4px;">
      <div class="ai-suggestion-title" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
        <span>🤖 DeepSeek AI — Smart Advice</span>
        <span id="aiSpinner" style="display:inline-flex;align-items:center;gap:5px;
              font-size:0.74rem;color:var(--text-muted);font-weight:400;">
          <span style="width:10px;height:10px;border:2px solid var(--text-muted);
                       border-top-color:var(--accent);border-radius:50%;display:inline-block;
                       animation:spin 0.75s linear infinite;"></span>
          OpenRouter AI analysing your schedule…
        </span>
      </div>
      <div class="ai-suggestion-text" id="aiSuggText">
        Generating personalised advice via OpenRouter.ai…
      </div>
    </div>`;

    resultDiv.innerHTML = html;

    // -- Trigger AI advice ---
    const conflictSummary = conflicts.length
      ? conflicts.map(c => `${c.course_code} (${c.course_name || c.course_code}) ${c.time_start}–${c.time_end}`).join('; ')
      : 'None';

    await fetchAIAdvice({
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
   DEEPSEEK AI ADVICE — server-side call
   ================================================================ */

async function fetchAIAdvice(payload) {
  const textEl    = document.getElementById('aiSuggText');
  const spinnerEl = document.getElementById('aiSpinner');

  try {
    const res  = await fetch('/planner/api/ai-advice', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    const data = await res.json();

    if (spinnerEl) spinnerEl.remove();

    if (!textEl) return;

    if (data.success && data.advice) {
      const lines = data.advice.split('\n').filter(l => l.trim());
      textEl.innerHTML =
        lines.map(line =>
          `<div style="margin-bottom:9px;line-height:1.65;">${esc(line)}</div>`
        ).join('') +
        `<div style="margin-top:10px;font-size:0.69rem;color:var(--text-muted);
                     border-top:1px solid var(--border);padding-top:6px;">
           🤖 Powered by OpenRouter.ai — model: ${esc(data.model || 'openrouter')}
         </div>`;
    } else {
      textEl.innerHTML = `
        <div style="color:var(--amber);">⚠️ ${esc(data.error || 'AI advice unavailable.')}</div>
        <div style="font-size:0.78rem;color:var(--text-muted);margin-top:6px;">
          The conflict analysis above is still accurate and complete.
        </div>`;
    }
  } catch (e) {
    if (spinnerEl) spinnerEl.remove();
    if (textEl) textEl.innerHTML = `
      <div style="color:var(--text-muted);font-size:0.82rem;">
        AI advice unavailable (network error). The conflict data above is still accurate.
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
        ${p.date} · ${p.start_time}–${p.end_time}
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
    start_time: document.getElementById('p_start').value,
    end_time:   document.getElementById('p_end').value,
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
      <div class="ts-result-time">${c.time_slot}</div>
    </div>`).join('');

    // Advanced ML suggestions
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