/**
 * UniSync — AI Personal Planner
 * ─────────────────────────────
 * Auto-detects API provider from key prefix:
 *   AIza…  → Google Gemini   (tries 2.0-flash → 1.5-flash → 1.5-pro auto)
 *   xai-…  → Grok (xAI)      (free tier, grok-3-mini or grok-beta)
 *   sk-…   → OpenAI           (gpt-4o-mini with gpt-3.5-turbo fallback)
 *   other  → Tries Gemini first, then Grok, then fails gracefully
 */

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

// ── AI Key Management ────────────────────────────────────────

function detectProvider(key) {
  if (!key) return null;
  if (key.startsWith('AIza'))  return 'gemini';
  if (key.startsWith('xai-'))  return 'grok';
  if (key.startsWith('sk-'))   return 'openai';
  return 'unknown';
}

function loadSavedKey() {
  const key = localStorage.getItem('us_ai_key') || '';
  const inp = document.getElementById('aiKeyInput');
  if (inp) inp.value = key;
  refreshKeyStatus(key);
}

function onAiKeyInput(val) {
  const trimmed = val.trim();
  if (trimmed) localStorage.setItem('us_ai_key', trimmed);
  else         localStorage.removeItem('us_ai_key');
  refreshKeyStatus(trimmed);
}

function refreshKeyStatus(key) {
  const el = document.getElementById('aiKeyStatus');
  if (!el) return;
  const provider = detectProvider(key);
  const labels = {
    gemini:  '🟢 Gemini key ready (auto-selects best model)',
    grok:    '🟢 Grok (xAI) key ready — free tier',
    openai:  '🟢 OpenAI key ready',
    unknown: '🟡 Key saved — will try Gemini → Grok → OpenAI',
    null:    '⚪ No key saved — add any AI API key above',
  };
  el.textContent = labels[provider] || labels[null];
  el.style.color = provider ? (provider === 'unknown' ? 'var(--amber)' : 'var(--green)') : 'var(--text-muted)';
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

// ── Multi-AI Router ───────────────────────────────────────────

/**
 * Tries providers in order based on key type.
 * Returns { result, provider } or throws on all failures.
 */
async function callAI(apiKey, conflictSummary, date, start, end, day, user) {
  const textEl    = document.getElementById('aiSuggText');
  const spinnerEl = document.getElementById('aiSpinner');

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

  const provider = detectProvider(apiKey);

  let result   = '';
  let errorMsg = '';

  // ── GEMINI (AIza… OR unknown → try Gemini first) ─────────────────────────
  if (provider === 'gemini' || provider === 'unknown') {
    const GEMINI_MODELS = [
      'gemini-2.0-flash',
      'gemini-1.5-flash',
      'gemini-1.5-pro',
      'gemini-2.0-flash-lite',
    ];

    for (const model of GEMINI_MODELS) {
      if (result) break;
      try {
        const url  = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
        const resp = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { temperature: 0.72, maxOutputTokens: 600 }
          })
        });
        const json = await resp.json();
        if (resp.ok) {
          const text = json?.candidates?.[0]?.content?.parts?.[0]?.text || '';
          if (text) { result = text; break; }
        } else {
          errorMsg = `Gemini (${model}): ${json?.error?.message || `HTTP ${resp.status}`}`;
          // If 404/model not found, try next model; other errors = break
          if (resp.status !== 404 && resp.status !== 400) break;
        }
      } catch (e) {
        errorMsg = `Gemini network error: ${e.message}`;
        break;
      }
    }
  }

  // ── GROK / xAI (xai-… OR unknown fallback after Gemini) ──────────────────
  if (!result && (provider === 'grok' || provider === 'unknown')) {
    const GROK_MODELS = ['grok-3-mini', 'grok-beta', 'grok-2-latest'];
    for (const model of GROK_MODELS) {
      if (result) break;
      try {
        const resp = await fetch('https://api.x.ai/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type':  'application/json',
            'Authorization': `Bearer ${apiKey}`,
          },
          body: JSON.stringify({
            model,
            messages:    [{ role: 'user', content: prompt }],
            max_tokens:  600,
            temperature: 0.72,
          })
        });
        const json = await resp.json();
        if (resp.ok) {
          const text = json?.choices?.[0]?.message?.content || '';
          if (text) { result = text; break; }
        } else {
          errorMsg = `Grok (${model}): ${json?.error?.message || `HTTP ${resp.status}`}`;
          if (resp.status !== 404 && resp.status !== 400) break;
        }
      } catch (e) {
        errorMsg = `Grok network error: ${e.message}`;
        break;
      }
    }
  }

  // ── OPENAI (sk-… OR unknown final fallback) ───────────────────────────────
  if (!result && (provider === 'openai' || provider === 'unknown')) {
    const OAI_MODELS = ['gpt-4o-mini', 'gpt-3.5-turbo'];
    for (const model of OAI_MODELS) {
      if (result) break;
      try {
        const resp = await fetch('https://api.openai.com/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type':  'application/json',
            'Authorization': `Bearer ${apiKey}`,
          },
          body: JSON.stringify({
            model,
            messages:    [{ role: 'user', content: prompt }],
            max_tokens:  600,
            temperature: 0.72,
          })
        });
        const json = await resp.json();
        if (resp.ok) {
          const text = json?.choices?.[0]?.message?.content || '';
          if (text) { result = text; break; }
        } else {
          errorMsg = `OpenAI (${model}): ${json?.error?.message || `HTTP ${resp.status}`}`;
          if (resp.status !== 404) break;
        }
      } catch (e) {
        errorMsg = `OpenAI network error: ${e.message}`;
        break;
      }
    }
  }

  // ── Render result ─────────────────────────────────────────
  if (spinnerEl) spinnerEl.remove();
  if (textEl) {
    if (result) {
      const lines = result.split('\n').filter(l => l.trim());
      textEl.innerHTML = lines.map(line =>
        `<div style="margin-bottom:7px;line-height:1.55;">${escHtml(line)}</div>`
      ).join('');
    } else {
      textEl.innerHTML = `
        <span style="color:var(--red);">⚠️ ${escHtml(errorMsg || 'All AI providers failed.')}</span><br>
        <span style="font-size:0.78rem;color:var(--text-muted);margin-top:6px;display:block;">
          Key prefixes: <strong>AIza…</strong> = Gemini &nbsp;·&nbsp;
          <strong>xai-…</strong> = Grok (free) &nbsp;·&nbsp;
          <strong>sk-…</strong> = OpenAI<br>
          Make sure your key is valid and has API access enabled.
        </span>`;
    }
  }
}

// ── Semester Courses ─────────────────────────────────────────

async function loadSemesterCourses() {
  const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;
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

    if (!data.success || !data.data || !data.data.length) {
      container.innerHTML = `
        <div class="ts-empty" style="text-align:center;padding:20px;">
          No classes found for <strong>${user.program || 'BBA'} · Year ${user.year || 1} · Sem ${user.semester || 1}</strong>.<br>
          <span style="font-size:0.78rem;color:var(--text-muted);">Update your profile if your year/semester is wrong.</span>
        </div>`;
      return;
    }

    const DAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday'];
    const grouped = {};
    DAYS.forEach(d => grouped[d] = []);
    data.data.forEach(cls => {
      if (grouped[cls.day] !== undefined) grouped[cls.day].push(cls);
    });

    const uniqueCourses = {};
    data.data.forEach(cls => {
      if (!uniqueCourses[cls.course_code]) {
        uniqueCourses[cls.course_code] = cls.course_name || cls.course_code;
      }
    });

    let html = `
      <div class="sem-course-summary">
        <div class="sem-course-chips">
          ${Object.entries(uniqueCourses).map(([code, name]) => `
            <span class="sem-chip" title="${name}">${code}</span>
          `).join('')}
        </div>
        <div style="font-size:0.72rem;color:var(--text-muted);margin-top:6px;">
          ${Object.keys(uniqueCourses).length} course(s) · ${data.data.length} class slot(s)
          · <em>${user.program} Year ${user.year} Sem ${user.semester}</em>
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
            </div>
          `).join('')}
        </div>`;
    });

    html += `</div>`;
    container.innerHTML = html;

  } catch (e) {
    container.innerHTML = `<div class="ts-empty">Failed to load schedule: ${e.message}</div>`;
  }
}

// ── Plans CRUD ───────────────────────────────────────────────

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
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      if (typeof UniSync !== 'undefined') UniSync.toast('Plan saved!', 'success');
      document.getElementById('addPlanModal').classList.add('hidden');
      e.target.reset();
      loadPlans();
    } else {
      if (typeof UniSync !== 'undefined') UniSync.toast(data.error || 'Error saving plan', 'error');
    }
  } catch {
    if (typeof UniSync !== 'undefined') UniSync.toast('Connection error', 'error');
  }
}

async function deletePlan(id) {
  if (!confirm('Delete this plan?')) return;
  try {
    await fetch(`/planner/api/plans/${id}`, { method: 'DELETE' });
    allPlans = allPlans.filter(p => p.id !== id);
    renderPlans();
    if (typeof UniSync !== 'undefined') UniSync.toast('Deleted', 'success');
  } catch {
    if (typeof UniSync !== 'undefined') UniSync.toast('Error deleting', 'error');
  }
}

function openAddPlan() {
  document.getElementById('addPlanModal').classList.remove('hidden');
}

// ── Conflict Checker ─────────────────────────────────────────

async function checkConflict() {
  const date  = (document.getElementById('cc_date')  || {}).value || '';
  const start = (document.getElementById('cc_start') || {}).value || '';
  const end   = (document.getElementById('cc_end')   || {}).value || '';
  const user  = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;

  if (!date || !start || !end) {
    if (typeof UniSync !== 'undefined') UniSync.toast('Please fill date, start and end time', 'warning');
    return;
  }
  if (start >= end) {
    if (typeof UniSync !== 'undefined') UniSync.toast('Start time must be before end time', 'warning');
    return;
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
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date,
        start_time: start,
        end_time:   end,
        program:  user?.program  || 'BBA',
        year:     user?.year     || 1,
        semester: user?.semester || 1,
      })
    });
    const data = await res.json();

    if (!data.success) {
      if (resultDiv) resultDiv.innerHTML = `
        <div class="ts-empty">⚠️ Check failed: ${data.error || 'Unknown error'}. Try again.</div>`;
      return;
    }

    if (data.message) {
      if (resultDiv) resultDiv.innerHTML = `
        <div style="padding:14px;background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.25);border-radius:var(--radius-sm);">
          <div style="color:var(--green);font-weight:700;">✅ ${data.message}</div>
        </div>`;
      return;
    }

    if (!data.conflicts || !data.conflicts.length) {
      const dayLabel = data.day ? `<strong>${data.day}</strong>` : '';
      if (resultDiv) resultDiv.innerHTML = `
        <div style="padding:16px;background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.25);border-radius:var(--radius-sm);">
          <div style="color:var(--green);font-weight:700;margin-bottom:4px;">✅ No Conflicts!</div>
          <div style="font-size:0.84rem;color:var(--text-muted);">
            Your plan on ${dayLabel} ${start}–${end} is free of your semester's classes.
          </div>
        </div>`;
      return;
    }

    let html = `
    <div class="conflict-box">
      <div class="conflict-title">⚠️ ${data.conflicts.length} Conflict(s) Found on ${data.day || ''}</div>`;
    data.conflicts.forEach(c => {
      html += `
      <div class="conflict-item">
        📚 <strong>${c.course_code}</strong> — ${c.course_name || c.course_code}
        <span style="color:var(--text-muted);font-size:0.8rem;">
          &nbsp;|&nbsp; ${c.time_start}–${c.time_end} &nbsp;|&nbsp; Room ${c.room_no}
          ${c.teacher_name ? `&nbsp;|&nbsp; ${c.teacher_name}` : ''}
        </span>
      </div>`;
    });
    html += `</div>`;

    const aiKey = localStorage.getItem('us_ai_key');
    const provider = detectProvider(aiKey);

    if (aiKey) {
      const providerLabel = {
        gemini:  '✨ Gemini AI',
        grok:    '✨ Grok AI',
        openai:  '✨ OpenAI',
        unknown: '✨ AI',
      }[provider] || '✨ AI';

      html += `
      <div class="ai-suggestion-box">
        <div class="ai-suggestion-title">
          ${providerLabel} Smart Balance Suggestion
          <span id="aiSpinner" style="margin-left:6px;">⏳</span>
        </div>
        <div class="ai-suggestion-text" id="aiSuggText">Generating personalised advice…</div>
      </div>`;
      if (resultDiv) resultDiv.innerHTML = html;

      const summary = data.conflicts.map(c =>
        `${c.course_code} (${c.course_name || c.course_code}) ${c.time_start}–${c.time_end}`
      ).join('; ');

      await callAI(aiKey, summary, date, start, end, data.day || '', user);
    } else {
      html += `
      <div style="margin-top:10px;padding:12px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:0.82rem;color:var(--text-muted);">
        💡 Add a Gemini (<strong>AIza…</strong>), Grok (<strong>xai-…</strong>), or OpenAI (<strong>sk-…</strong>) API key above to get AI-powered conflict resolution advice.
      </div>`;
      if (resultDiv) resultDiv.innerHTML = html;
    }

  } catch (e) {
    if (resultDiv) resultDiv.innerHTML = `<div class="ts-empty">Error: ${e.message}</div>`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Check Conflicts'; }
  }
}

// ── Duration Search ML Suggestions Renderer ──────────────────

async function runDurationSearch() {
  const from   = document.getElementById('dsFrom').value;
  const to     = document.getElementById('dsTo').value;
  const day    = document.getElementById('dsDay').value;
  const resDiv = document.getElementById('dsResults');
  const _user  = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;

  if (!from || !to) { UniSync.toast('Select both From and To time', 'warning'); return; }
  if (from >= to)   { UniSync.toast('From must be before To', 'warning'); return; }

  resDiv.innerHTML = '<div class="ts-loading">Searching your schedule…</div>';
  resDiv.classList.remove('hidden');

  try {
    const params = new URLSearchParams({from, to});
    if (day) params.set('day', day);
    if (_user?.program)  params.set('program',  _user.program);
    if (_user?.year)     params.set('year',      _user.year);
    if (_user?.semester) params.set('semester',  _user.semester);

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

    // ── Advanced ML Suggestions Block ─────────────────────────────────────────
    if (data.ml?.suggestions?.length) {
      const sessionLabel = {
        morning_peak:   '🌅 Morning Peak — High focus window',
        mid_morning:    '☀️ Mid-Morning — Optimal learning time',
        post_lunch_dip: '😴 Post-Lunch Dip — Stay active!',
        afternoon:      '🌤️ Afternoon — Moderate energy',
        off_hours:      '🌙 Off Hours',
      }[data.ml.session_type] || '🧠 Current Session';

      html += `
      <div class="ml-suggestion-box" style="margin-top:14px;">
        <div class="ml-suggestion-title" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px;">
          <span>🧠 Advanced ML Smart Suggestions</span>
          <span style="font-size:0.68rem;color:var(--text-muted);font-weight:400;">${sessionLabel}</span>
        </div>`;

      data.ml.suggestions.forEach((s, idx) => {
        // Urgency bar fill
        const pct  = Math.round(s.urgency_score * 100);
        const barColor =
          pct >= 70 ? 'var(--red)' :
          pct >= 45 ? 'var(--amber)' :
          'var(--green)';

        html += `
        <div class="ml-suggestion-item" style="
            border-left: 3px solid ${barColor};
            padding: 10px 12px;
            margin-bottom: 8px;
            background: var(--bg-elevated);
            border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
        ">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:5px;">
            <span style="font-weight:600;font-size:0.83rem;">#${s.rank} ${s.priority}</span>
            <span style="font-size:0.7rem;color:var(--text-muted);">
              Urgency: ${pct}%
              ${s.fatigue_factor < 0.9 ? ' · ⚡ Fatigue detected' : ''}
            </span>
          </div>
          <div style="font-size:0.83rem;margin-bottom:4px;">${escHtml(s.suggestion)}</div>
          <div style="
              height:3px;background:var(--bg-card);border-radius:3px;margin:6px 0;
          ">
            <div style="height:3px;width:${pct}%;background:${barColor};border-radius:3px;transition:width 0.6s ease;"></div>
          </div>
          <div style="font-size:0.76rem;color:var(--text-muted);font-style:italic;">
            💡 ${escHtml(s.context_tip)}
          </div>
        </div>`;
      });

      html += `
        <div style="font-size:0.68rem;color:var(--text-muted);margin-top:6px;text-align:right;">
          ML v${data.ml.ml_version || '2.0'} · ${data.ml.total_classes} class(es) analysed
        </div>
      </div>`;
    }

    resDiv.innerHTML = html;
  } catch(e) {
    resDiv.innerHTML = '<div class="ts-empty">Connection error.</div>';
  }
}