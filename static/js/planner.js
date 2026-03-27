/* UniSync — AI Personal Planner | Fully Fixed v2 */

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
  if (!key) {
    el.textContent = '⚪ No key saved';
    el.style.color = 'var(--text-muted)';
  } else if (key.startsWith('AIza')) {
    el.textContent = '🟢 Gemini key ready (gemini-2.0-flash)';
    el.style.color = 'var(--green)';
  } else if (key.startsWith('sk-')) {
    el.textContent = '🟢 OpenAI key ready';
    el.style.color = 'var(--green)';
  } else {
    el.textContent = '🟡 Key saved (format unknown)';
    el.style.color = 'var(--amber)';
  }
}

function clearAiKey() {
  localStorage.removeItem('us_ai_key');
  const inp = document.getElementById('aiKeyInput');
  if (inp) inp.value = '';
  refreshKeyStatus('');
  if (typeof UniSync !== 'undefined') UniSync.toast('API key cleared', 'success');
}

/* FIX: was toggleAiKey() in HTML — now unified as toggleAiKeyVis() */
function toggleAiKeyVis() {
  const inp = document.getElementById('aiKeyInput');
  const btn = document.getElementById('toggleKeyBtn');
  if (!inp) return;
  inp.type = inp.type === 'password' ? 'text' : 'password';
  if (btn) btn.textContent = inp.type === 'text' ? 'Hide' : 'Show';
}

// ── Semester Courses (current semester schedule) ─────────────

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

    // Group by day
    const DAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday'];
    const grouped = {};
    DAYS.forEach(d => grouped[d] = []);
    data.data.forEach(cls => {
      if (grouped[cls.day] !== undefined) grouped[cls.day].push(cls);
    });

    // Deduplicate unique courses for the summary strip
    const uniqueCourses = {};
    data.data.forEach(cls => {
      if (!uniqueCourses[cls.course_code]) {
        uniqueCourses[cls.course_code] = cls.course_name || cls.course_code;
      }
    });

    // Build HTML
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
      // Weekend or holiday
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
    if (aiKey) {
      html += `
      <div class="ai-suggestion-box">
        <div class="ai-suggestion-title">
          ✨ AI Smart Balance Suggestion
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
        💡 Add your Gemini or OpenAI API key above to get AI-powered conflict resolution advice.
      </div>`;
      if (resultDiv) resultDiv.innerHTML = html;
    }

  } catch (e) {
    if (resultDiv) resultDiv.innerHTML = `<div class="ts-empty">Error: ${e.message}</div>`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Check Conflicts'; }
  }
}

// ── AI API — Gemini 2.0 Flash + OpenAI ───────────────────────

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

  let result   = '';
  let errorMsg = '';

  // ── Gemini 2.0 Flash (FIX: was gemini-1.5-flash-latest which is removed) ──
  if (!apiKey.startsWith('sk-')) {
    try {
      const url  = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${apiKey}`;
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.7, maxOutputTokens: 500 }
        })
      });
      const json = await resp.json();

      if (!resp.ok) {
        // Try fallback model gemini-1.5-flash if 2.0-flash fails
        errorMsg = `Gemini: ${json?.error?.message || `HTTP ${resp.status}`}`;
        // Attempt fallback to gemini-1.5-flash
        const fallbackUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;
        const fbResp = await fetch(fallbackUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { temperature: 0.7, maxOutputTokens: 500 }
          })
        });
        const fbJson = await fbResp.json();
        if (fbResp.ok) {
          result   = fbJson?.candidates?.[0]?.content?.parts?.[0]?.text || '';
          errorMsg = result ? '' : 'Gemini returned empty response.';
        } else {
          errorMsg = `Gemini: ${fbJson?.error?.message || `HTTP ${fbResp.status}`}`;
        }
      } else {
        result = json?.candidates?.[0]?.content?.parts?.[0]?.text || '';
        if (!result) errorMsg = 'Gemini returned empty response.';
      }
    } catch (e) {
      errorMsg = `Gemini network error: ${e.message}`;
    }
  }

  // ── OpenAI (primary if sk-, fallback if Gemini failed) ──────
  if (!result && apiKey.startsWith('sk-')) {
    try {
      const resp = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          model:       'gpt-3.5-turbo',
          messages:    [{ role: 'user', content: prompt }],
          max_tokens:  500,
          temperature: 0.7,
        })
      });
      const json = await resp.json();

      if (!resp.ok) {
        errorMsg = `OpenAI: ${json?.error?.message || `HTTP ${resp.status}`}`;
      } else {
        result = json?.choices?.[0]?.message?.content || '';
        if (!result) errorMsg = 'OpenAI returned empty response.';
      }
    } catch (e) {
      errorMsg = `OpenAI network error: ${e.message}`;
    }
  }

  // ── Render result ─────────────────────────────────────────
  if (spinnerEl) spinnerEl.remove();
  if (textEl) {
    if (result) {
      // Format bullet points nicely
      const lines = result.split('\n').filter(l => l.trim());
      textEl.innerHTML = lines.map(line =>
        `<div style="margin-bottom:6px;">${escHtml(line)}</div>`
      ).join('');
    } else {
      textEl.innerHTML = `
        <span style="color:var(--red);">⚠️ ${escHtml(errorMsg)}</span><br>
        <span style="font-size:0.78rem;color:var(--text-muted);margin-top:6px;display:block;">
          Tip: Gemini keys start with <strong>AIza…</strong> · OpenAI keys start with <strong>sk-…</strong><br>
          Make sure your key is valid and has Generative Language API access enabled.
        </span>`;
    }
  }
}