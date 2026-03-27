/**
 * UniSync — AI Personal Planner  v3.0
 * ─────────────────────────────────────────────────────────────
 * TRUE WATERFALL AI — quota/rate-limit ALWAYS falls through:
 *
 *   AIza…  → Gemini (all models) → Grok → OpenAI
 *   xai-…  → Grok  (all models) → Gemini → OpenAI
 *   sk-…   → OpenAI (all models) → Gemini → Grok
 *   other  → Gemini → Grok → OpenAI
 *
 *  429 quota / rate-limit → ALWAYS continues to next provider.
 *  401/403 auth errors    → skip that provider, try next.
 */

'use strict';

let allPlans = [];

document.addEventListener('DOMContentLoaded', () => {
  if (typeof UniSync !== 'undefined') UniSync.requireAuth();
  loadPlans();
  loadSemesterCourses();
  loadSavedKey();
  const today = new Date().toISOString().split('T')[0];
  ['cc_date', 'p_date'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = today;
  });
});

/* ================================================================
   AI KEY MANAGEMENT
   ================================================================ */

function detectProvider(key) {
  if (!key) return null;
  const k = (key || '').trim();
  if (k.startsWith('AIza'))  return 'gemini';
  if (k.startsWith('xai-'))  return 'grok';
  if (k.startsWith('sk-'))   return 'openai';
  return 'unknown';
}

function loadSavedKey() {
  const key = localStorage.getItem('us_ai_key') || '';
  const inp = document.getElementById('aiKeyInput');
  if (inp) inp.value = key;
  refreshKeyStatus(key);
}

function onAiKeyInput(val) {
  const trimmed = (val || '').trim();
  if (trimmed) localStorage.setItem('us_ai_key', trimmed);
  else         localStorage.removeItem('us_ai_key');
  refreshKeyStatus(trimmed);
}

function refreshKeyStatus(key) {
  const el = document.getElementById('aiKeyStatus');
  if (!el) return;
  const p = detectProvider(key);
  const map = {
    gemini:  '🟢 Gemini key — auto-tries all models, then Grok → OpenAI on quota',
    grok:    '🟢 Grok (xAI) key — free tier, then Gemini → OpenAI as fallback',
    openai:  '🟢 OpenAI key — then Gemini → Grok as fallback',
    unknown: '🟡 Key saved — tries Gemini → Grok → OpenAI in order',
  };
  el.textContent = key ? (map[p] || map.unknown) : '⚪ No key — paste any Gemini / Grok / OpenAI API key';
  el.style.color = !key ? 'var(--text-muted)' : p === 'unknown' ? 'var(--amber)' : 'var(--green)';
}

function clearAiKey() {
  localStorage.removeItem('us_ai_key');
  const inp = document.getElementById('aiKeyInput');
  if (inp) inp.value = '';
  refreshKeyStatus('');
  if (typeof UniSync !== 'undefined') UniSync.toast('API key cleared', 'success');
}

function toggleAiKeyVis() {
  const inp = document.getElementById('aiKeyInput');
  const btn = document.getElementById('toggleKeyBtn');
  if (!inp) return;
  inp.type = inp.type === 'password' ? 'text' : 'password';
  if (btn) btn.textContent = inp.type === 'text' ? 'Hide' : 'Show';
}

/* ================================================================
   WATERFALL AI ENGINE
   ================================================================ */

/**
 * tryGemini — tries every Gemini model in order.
 * 429 quota / 503 overload / 404 model-not-found → continue to next model.
 * 401/403 auth error → return { fatal, error }.
 * Returns { text, model } on success, null when all models exhausted.
 */
async function tryGemini(apiKey, prompt) {
  const MODELS = [
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
    'gemini-1.5-flash',
    'gemini-1.5-flash-8b',
    'gemini-1.5-pro',
  ];
  for (const model of MODELS) {
    try {
      const url  = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
      const resp = await fetch(url, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.72, maxOutputTokens: 600 },
        }),
      });
      const json = await resp.json();

      if (resp.ok) {
        const text = json?.candidates?.[0]?.content?.parts?.[0]?.text || '';
        if (text) return { text, model: `Gemini / ${model}` };
        continue; // empty → try next model
      }

      const status = resp.status;
      const msg    = json?.error?.message || `HTTP ${status}`;

      // Auth failure — abort Gemini entirely
      if (status === 401 || status === 403)
        return { fatal: true, error: `Gemini auth error: ${msg}` };

      // Quota / overload / model not found → try next model
      console.warn(`[Gemini] ${model} skipped (${status}): ${msg}`);
    } catch (e) {
      console.warn(`[Gemini] ${model} network error: ${e.message}`);
      // network error → try next model
    }
  }
  return null; // all Gemini models exhausted
}

/**
 * tryGrok — tries xAI Grok models in order (free-tier first).
 */
async function tryGrok(apiKey, prompt) {
  const MODELS = [
    'grok-3-mini',
    'grok-3-mini-fast',
    'grok-beta',
    'grok-2-mini',
    'grok-2-latest',
  ];
  for (const model of MODELS) {
    try {
      const resp = await fetch('https://api.x.ai/v1/chat/completions', {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model,
          messages:    [{ role: 'user', content: prompt }],
          max_tokens:  600,
          temperature: 0.72,
        }),
      });
      const json = await resp.json();

      if (resp.ok) {
        const text = json?.choices?.[0]?.message?.content || '';
        if (text) return { text, model: `Grok / ${model}` };
        continue;
      }

      const status = resp.status;
      const msg    = json?.error?.message || `HTTP ${status}`;
      if (status === 401 || status === 403)
        return { fatal: true, error: `Grok auth error: ${msg}` };
      console.warn(`[Grok] ${model} skipped (${status}): ${msg}`);
    } catch (e) {
      console.warn(`[Grok] ${model} network error: ${e.message}`);
    }
  }
  return null;
}

/**
 * tryOpenAI — tries OpenAI models in order.
 */
async function tryOpenAI(apiKey, prompt) {
  const MODELS = ['gpt-4o-mini', 'gpt-3.5-turbo', 'gpt-4o'];
  for (const model of MODELS) {
    try {
      const resp = await fetch('https://api.openai.com/v1/chat/completions', {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model,
          messages:    [{ role: 'user', content: prompt }],
          max_tokens:  600,
          temperature: 0.72,
        }),
      });
      const json = await resp.json();

      if (resp.ok) {
        const text = json?.choices?.[0]?.message?.content || '';
        if (text) return { text, model: `OpenAI / ${model}` };
        continue;
      }

      const status = resp.status;
      const msg    = json?.error?.message || `HTTP ${status}`;
      if (status === 401 || status === 403)
        return { fatal: true, error: `OpenAI auth error: ${msg}` };
      console.warn(`[OpenAI] ${model} skipped (${status}): ${msg}`);
    } catch (e) {
      console.warn(`[OpenAI] ${model} network error: ${e.message}`);
    }
  }
  return null;
}

/**
 * callAI — TRUE WATERFALL ROUTER
 *
 * Builds a 3-provider chain ordered by detected key type.
 * If any provider returns null (exhausted) it moves to the next one.
 * Updates the spinner label live so the user can see what's happening.
 */
async function callAI(apiKey, conflictSummary, date, start, end, day, user) {
  const textEl    = document.getElementById('aiSuggText');
  const spinnerEl = document.getElementById('aiSpinner');
  const spinLabel = document.getElementById('aiSpinLabel');

  const prompt =
    `I am a student at Rabindra University Bangladesh, Department of Management.\n` +
    `Program: ${user?.program || 'BBA'}, Year ${user?.year || 1}, Semester ${user?.semester || 1}.\n` +
    `I have a personal commitment on ${day} ${date} from ${start} to ${end}.\n` +
    `This conflicts with these university classes: ${conflictSummary}.\n\n` +
    `Give me 4-5 short, practical bullet points on:\n` +
    `- Which commitment to prioritise and why\n` +
    `- How to catch up on any missed class material\n` +
    `- A concrete time management tip for this situation\n` +
    `Be concise, friendly and encouraging. Start each bullet with a relevant emoji.`;

  /* Build provider chain — primary first, fallbacks after */
  const ALL = {
    gemini: [
      { name: 'Gemini', fn: () => tryGemini(apiKey, prompt) },
      { name: 'Grok',   fn: () => tryGrok(apiKey, prompt)   },
      { name: 'OpenAI', fn: () => tryOpenAI(apiKey, prompt) },
    ],
    grok: [
      { name: 'Grok',   fn: () => tryGrok(apiKey, prompt)   },
      { name: 'Gemini', fn: () => tryGemini(apiKey, prompt) },
      { name: 'OpenAI', fn: () => tryOpenAI(apiKey, prompt) },
    ],
    openai: [
      { name: 'OpenAI', fn: () => tryOpenAI(apiKey, prompt) },
      { name: 'Gemini', fn: () => tryGemini(apiKey, prompt) },
      { name: 'Grok',   fn: () => tryGrok(apiKey, prompt)   },
    ],
    unknown: [
      { name: 'Gemini', fn: () => tryGemini(apiKey, prompt) },
      { name: 'Grok',   fn: () => tryGrok(apiKey, prompt)   },
      { name: 'OpenAI', fn: () => tryOpenAI(apiKey, prompt) },
    ],
  };

  const chain    = ALL[detectProvider(apiKey)] || ALL.unknown;
  let resultText = '';
  let usedModel  = '';
  let lastError  = 'All AI providers exhausted.';

  for (const step of chain) {
    if (spinLabel) spinLabel.textContent = `Trying ${step.name}…`;

    const res = await step.fn();

    if (!res) {
      // Provider exhausted (quota / all models failed) → waterfall continues
      lastError = `${step.name} quota/unavailable — trying next provider…`;
      continue;
    }
    if (res.fatal) {
      // Auth error for this provider → skip it, try next
      lastError = res.error;
      continue;
    }
    if (res.text) {
      resultText = res.text;
      usedModel  = res.model;
      break;
    }
  }

  /* ── Render ── */
  if (spinnerEl) spinnerEl.remove();

  if (!textEl) return;

  if (resultText) {
    const lines = resultText.split('\n').filter(l => l.trim());
    textEl.innerHTML =
      lines.map(line =>
        `<div style="margin-bottom:8px;line-height:1.6;">${escHtml(line)}</div>`
      ).join('') +
      `<div style="margin-top:10px;font-size:0.69rem;color:var(--text-muted);
                   border-top:1px solid var(--border);padding-top:6px;">
         ✦ Powered by ${escHtml(usedModel)}
       </div>`;
  } else {
    textEl.innerHTML = `
      <div style="color:var(--red);margin-bottom:8px;">⚠️ ${escHtml(lastError)}</div>
      <div style="font-size:0.78rem;color:var(--text-muted);line-height:1.7;">
        <strong>Supported key formats:</strong><br>
        <code style="color:var(--accent-light);">AIza…</code> → Gemini &nbsp;·&nbsp;
        <code style="color:var(--accent-light);">xai-…</code> → Grok (free) &nbsp;·&nbsp;
        <code style="color:var(--accent-light);">sk-…</code> → OpenAI<br>
        <span style="display:block;margin-top:4px;">
          If one provider's quota is exceeded, the others are tried automatically.
        </span>
      </div>`;
  }
}

/* ================================================================
   SEMESTER COURSES
   ================================================================ */

async function loadSemesterCourses() {
  const user      = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;
  const container = document.getElementById('semesterCoursesBox');
  if (!container) return;

  if (!user) {
    container.innerHTML = '<div class="ts-empty">Please log in to see your schedule.</div>';
    return;
  }
  container.innerHTML = '<div class="ts-loading">Loading your semester schedule…</div>';

  try {
    const params = new URLSearchParams({
      program:  user.program  || 'BBA',
      year:     user.year     || 1,
      semester: user.semester || 1,
    });
    const res  = await fetch(`/academic/api/routine?${params}`);
    const data = await res.json();

    if (!data.success || !data.data?.length) {
      container.innerHTML = `
        <div class="ts-empty" style="text-align:center;padding:20px;">
          No classes found for
          <strong>${user.program || 'BBA'} · Year ${user.year || 1} · Sem ${user.semester || 1}</strong>.<br>
          <span style="font-size:0.78rem;color:var(--text-muted);">
            Update your profile if your year/semester is wrong.
          </span>
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
          ${Object.keys(uniqueCourses).length} course(s) ·
          ${data.data.length} class slot(s) ·
          <em>${user.program} Year ${user.year} Sem ${user.semester}</em>
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

    html += `</div>`;
    container.innerHTML = html;

  } catch (e) {
    container.innerHTML = `<div class="ts-empty">Failed to load schedule: ${e.message}</div>`;
  }
}

/* ================================================================
   PLANS CRUD
   ================================================================ */

async function loadPlans() {
  const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;
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
    work:     'var(--cyan)',
    other:    'var(--text-muted)',
  };
  list.innerHTML = allPlans.map(p => `
  <div class="plan-item">
    <div class="plan-type-dot ${p.type}" style="background:${typeColor[p.type] || 'var(--text-muted)'};"></div>
    <div class="plan-info">
      <div class="plan-title">${escHtml(p.title)}</div>
      <div class="plan-meta">
        ${p.date} · ${p.start_time}–${p.end_time}
        · <span style="text-transform:capitalize">${p.type}</span>
      </div>
      ${p.note ? `<div class="plan-meta" style="font-style:italic">${escHtml(p.note)}</div>` : ''}
    </div>
    <button class="btn-sm btn-danger" onclick="deletePlan('${p.id}')">✕</button>
  </div>`).join('');
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function submitPlan(e) {
  e.preventDefault();
  const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;
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
      UniSync?.toast('Plan saved!', 'success');
      document.getElementById('addPlanModal').classList.add('hidden');
      e.target.reset();
      loadPlans();
    } else {
      UniSync?.toast(data.error || 'Error saving plan', 'error');
    }
  } catch {
    UniSync?.toast('Connection error', 'error');
  }
}

async function deletePlan(id) {
  if (!confirm('Delete this plan?')) return;
  try {
    await fetch(`/planner/api/plans/${id}`, { method: 'DELETE' });
    allPlans = allPlans.filter(p => p.id !== id);
    renderPlans();
    UniSync?.toast('Deleted', 'success');
  } catch {
    UniSync?.toast('Error deleting', 'error');
  }
}

function openAddPlan() {
  document.getElementById('addPlanModal').classList.remove('hidden');
}

/* ================================================================
   CONFLICT CHECKER
   ================================================================ */

async function checkConflict() {
  const date  = (document.getElementById('cc_date')  || {}).value || '';
  const start = (document.getElementById('cc_start') || {}).value || '';
  const end   = (document.getElementById('cc_end')   || {}).value || '';
  const user  = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;

  if (!date || !start || !end) {
    UniSync?.toast('Please fill date, start and end time', 'warning'); return;
  }
  if (start >= end) {
    UniSync?.toast('Start time must be before end time', 'warning'); return;
  }

  const btn = document.getElementById('conflictBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Checking…'; }

  const resultDiv = document.getElementById('conflictResult');
  if (resultDiv) {
    resultDiv.innerHTML = '<div class="ts-loading">Checking conflicts against your semester schedule…</div>';
    resultDiv.classList.remove('hidden');
  }

  try {
    const res  = await fetch('/planner/api/conflict-check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date,
        start_time: start,
        end_time:   end,
        program:  user?.program  || 'BBA',
        year:     user?.year     || 1,
        semester: user?.semester || 1,
      }),
    });
    const data = await res.json();

    if (!data.success) {
      resultDiv && (resultDiv.innerHTML =
        `<div class="ts-empty">⚠️ Check failed: ${data.error || 'Unknown error'}. Try again.</div>`);
      return;
    }

    if (data.message) {
      resultDiv && (resultDiv.innerHTML = `
        <div style="padding:14px;background:rgba(52,211,153,0.08);
                    border:1px solid rgba(52,211,153,0.25);border-radius:var(--radius-sm);">
          <div style="color:var(--green);font-weight:700;">✅ ${data.message}</div>
        </div>`);
      return;
    }

    if (!data.conflicts?.length) {
      const dayLabel = data.day ? `<strong>${data.day}</strong>` : '';
      resultDiv && (resultDiv.innerHTML = `
        <div style="padding:16px;background:rgba(52,211,153,0.08);
                    border:1px solid rgba(52,211,153,0.25);border-radius:var(--radius-sm);">
          <div style="color:var(--green);font-weight:700;margin-bottom:4px;">✅ No Conflicts!</div>
          <div style="font-size:0.84rem;color:var(--text-muted);">
            Your plan on ${dayLabel} ${start}–${end} is free of your semester's classes.
          </div>
        </div>`);
      return;
    }

    /* Build conflict list */
    let html = `
    <div class="conflict-box">
      <div class="conflict-title">⚠️ ${data.conflicts.length} Conflict(s) Found on ${data.day || ''}</div>`;
    data.conflicts.forEach(c => {
      html += `
      <div class="conflict-item">
        📚 <strong>${c.course_code}</strong> — ${c.course_name || c.course_code}
        <span style="color:var(--text-muted);font-size:0.8rem;">
          &nbsp;|&nbsp; ${c.time_start}–${c.time_end}
          &nbsp;|&nbsp; Room ${c.room_no}
          ${c.teacher_name ? `&nbsp;|&nbsp; ${c.teacher_name}` : ''}
        </span>
      </div>`;
    });
    html += `</div>`;

    const aiKey = localStorage.getItem('us_ai_key');
    if (aiKey) {
      const pName = { gemini:'Gemini', grok:'Grok', openai:'OpenAI', unknown:'AI' }[detectProvider(aiKey)] || 'AI';

      html += `
      <div class="ai-suggestion-box" style="margin-top:12px;">
        <div class="ai-suggestion-title" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
          ✨ AI Smart Balance Suggestion
          <span id="aiSpinner" style="display:inline-flex;align-items:center;gap:5px;
                font-size:0.74rem;color:var(--text-muted);font-weight:400;">
            <span style="width:10px;height:10px;border:2px solid var(--text-muted);
                         border-top-color:var(--accent);border-radius:50%;
                         display:inline-block;animation:spin 0.75s linear infinite;"></span>
            <span id="aiSpinLabel">Trying ${pName}…</span>
          </span>
        </div>
        <div class="ai-suggestion-text" id="aiSuggText">
          Connecting — will fall back across all providers if quota is exceeded…
        </div>
      </div>`;

      if (resultDiv) resultDiv.innerHTML = html;

      const summary = data.conflicts.map(c =>
        `${c.course_code} (${c.course_name || c.course_code}) ${c.time_start}–${c.time_end}`
      ).join('; ');

      await callAI(aiKey, summary, date, start, end, data.day || '', user);

    } else {
      html += `
      <div style="margin-top:10px;padding:13px;background:var(--bg-elevated);
                  border:1px solid var(--border);border-radius:var(--radius-sm);
                  font-size:0.82rem;color:var(--text-muted);line-height:1.7;">
        💡 Add a Gemini <code>(AIza…)</code>, Grok <code>(xai-…)</code>,
        or OpenAI <code>(sk-…)</code> API key above to get AI-powered advice.<br>
        <span style="font-size:0.75rem;">
          Quota exceeded? No problem — the other providers are tried automatically.
        </span>
      </div>`;
      if (resultDiv) resultDiv.innerHTML = html;
    }

  } catch (e) {
    resultDiv && (resultDiv.innerHTML = `<div class="ts-empty">Error: ${e.message}</div>`);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Check Conflicts'; }
  }
}

/* ================================================================
   DURATION SEARCH — ADVANCED ML SUGGESTION RENDERER
   ================================================================ */

async function runDurationSearch() {
  const from   = document.getElementById('dsFrom').value;
  const to     = document.getElementById('dsTo').value;
  const day    = document.getElementById('dsDay').value;
  const resDiv = document.getElementById('dsResults');
  const _user  = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;

  if (!from || !to) { UniSync?.toast('Select both From and To time', 'warning'); return; }
  if (from >= to)   { UniSync?.toast('From must be before To', 'warning');        return; }

  resDiv.innerHTML = '<div class="ts-loading">Searching your schedule…</div>';
  resDiv.classList.remove('hidden');

  try {
    const params = new URLSearchParams({ from, to });
    if (day)              params.set('day',      day);
    if (_user?.program)   params.set('program',  _user.program);
    if (_user?.year)      params.set('year',      _user.year);
    if (_user?.semester)  params.set('semester',  _user.semester);

    const res  = await fetch(`/academic/api/duration-search?${params}`);
    const data = await res.json();

    if (!data.success) { resDiv.innerHTML = '<div class="ts-empty">Search failed.</div>'; return; }

    if (!data.data.length) {
      resDiv.innerHTML = '<div class="ts-empty">✅ No classes in this time window for your semester.</div>';
      return;
    }

    let html = data.data.map(c => `
    <div class="ts-result-item">
      <div class="ts-result-code">${c.course_code}</div>
      <div class="ts-result-info">
        <div class="ts-result-name">${c.course_name || c.course_code}</div>
        <div class="ts-result-meta">Room ${c.room_no} · ${c.teacher_name || c.teacher_code} · ${c.day}</div>
      </div>
      <div class="ts-result-time">${c.time_slot}</div>
    </div>`).join('');

    /* ── Advanced ML Suggestions Block ── */
    if (data.ml?.suggestions?.length) {
      const sessionEmoji = {
        morning_peak:   '🌅', mid_morning: '☀️',
        post_lunch_dip: '😴', afternoon:   '🌤️', off_hours: '🌙',
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
          ? `<span style="color:var(--amber);font-size:0.68rem;">
               ⚡ Fatigue ${Math.round((1 - s.fatigue_factor) * 100)}%
             </span>`
          : '';

        html += `
        <div style="margin-bottom:10px;padding:11px 14px;background:var(--bg-card);
                    border-left:3px solid ${barColor};
                    border-radius:0 var(--radius-sm) var(--radius-sm) 0;">
          <div style="display:flex;align-items:center;justify-content:space-between;
                      gap:6px;margin-bottom:5px;flex-wrap:wrap;">
            <span style="font-weight:600;font-size:0.82rem;">#${s.rank || ''} ${s.priority || ''}</span>
            <div style="display:flex;align-items:center;gap:8px;">
              ${fatigueNote}
              <span style="font-size:0.69rem;color:var(--text-muted);">Urgency ${pct}%</span>
            </div>
          </div>
          <div style="font-size:0.83rem;margin-bottom:6px;line-height:1.5;">
            ${escHtml(s.suggestion)}
          </div>
          <div style="height:3px;background:var(--bg-elevated);border-radius:3px;margin:6px 0;">
            <div style="height:3px;width:${pct}%;background:${barColor};
                        border-radius:3px;transition:width 0.7s ease;"></div>
          </div>
          ${s.context_tip ? `
          <div style="font-size:0.75rem;color:var(--text-muted);font-style:italic;
                      border-top:1px solid var(--border);padding-top:5px;margin-top:4px;">
            💡 ${escHtml(s.context_tip)}
          </div>` : ''}
        </div>`;
      });

      html += `
        <div style="font-size:0.68rem;color:var(--text-muted);text-align:right;margin-top:4px;">
          ML ${escHtml(data.ml.ml_version || '2.0')} ·
          ${data.ml.total_classes || 0} class(es) analysed ·
          Query ${escHtml(data.ml.query_time || '')}
        </div>
      </div>`;
    }

    resDiv.innerHTML = html;

  } catch (e) {
    resDiv.innerHTML = '<div class="ts-empty">Connection error. Check server.</div>';
  }
}