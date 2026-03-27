/* UniSync — AI Personal Planner | Fixed AI API */

let allPlans = [];

document.addEventListener('DOMContentLoaded', () => {
  if (typeof UniSync !== 'undefined') UniSync.requireAuth();
  loadPlans();
  loadSavedKey();
  const today = new Date().toISOString().split('T')[0];
  ['cc_date','p_date'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = today;
  });
});

// ── AI Key Management ────────────────────────────────────────

function loadSavedKey() {
  const key   = localStorage.getItem('us_ai_key') || '';
  const inp   = document.getElementById('aiKeyInput');
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
    el.textContent = '🟢 Gemini key ready';
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

function toggleAiKeyVis() {
  const inp = document.getElementById('aiKeyInput');
  const btn = document.getElementById('toggleKeyBtn');
  if (!inp) return;
  inp.type        = inp.type === 'password' ? 'text' : 'password';
  if (btn) btn.textContent = inp.type === 'text' ? 'Hide' : 'Show';
}

// ── Plans CRUD ───────────────────────────────────────────────

async function loadPlans() {
  const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;
  if (!user) return;
  try {
    const res  = await fetch(`/planner/api/plans?user_id=${user.id}`);
    const data = await res.json();
    if (data.success) { allPlans = data.data; renderPlans(); }
  } catch(e) { console.error('loadPlans:', e); }
}

function renderPlans() {
  const list = document.getElementById('plansList');
  if (!list) return;
  if (!allPlans.length) {
    list.innerHTML = '<div class="empty-state"><p>No plans yet.</p></div>';
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
    <div class="plan-type-dot ${p.type}" style="background:${typeColor[p.type]||'var(--text-muted)'};"></div>
    <div class="plan-info">
      <div class="plan-title">${p.title}</div>
      <div class="plan-meta">
        ${p.date} · ${p.start_time}–${p.end_time}
        · <span style="text-transform:capitalize">${p.type}</span>
      </div>
      ${p.note ? `<div class="plan-meta" style="font-style:italic">${p.note}</div>` : ''}
    </div>
    <button class="btn-sm btn-danger" onclick="deletePlan('${p.id}')">✕</button>
  </div>`).join('');
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
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      if (typeof UniSync !== 'undefined') UniSync.toast('Plan saved!', 'success');
      document.getElementById('addPlanModal').classList.add('hidden');
      e.target.reset();
      loadPlans();
    } else {
      if (typeof UniSync !== 'undefined') UniSync.toast(data.error || 'Error', 'error');
    }
  } catch { if (typeof UniSync !== 'undefined') UniSync.toast('Connection error', 'error'); }
}

async function deletePlan(id) {
  if (!confirm('Delete this plan?')) return;
  try {
    await fetch(`/planner/api/plans/${id}`, {method: 'DELETE'});
    allPlans = allPlans.filter(p => p.id !== id);
    renderPlans();
    if (typeof UniSync !== 'undefined') UniSync.toast('Deleted', 'success');
  } catch { if (typeof UniSync !== 'undefined') UniSync.toast('Error', 'error'); }
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
    if (typeof UniSync !== 'undefined') UniSync.toast('Fill date, start and end time', 'warning');
    return;
  }

  const btn = document.getElementById('conflictBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Checking…'; }

  const resultDiv = document.getElementById('conflictResult');
  if (resultDiv) {
    resultDiv.innerHTML = '<div class="ts-loading">Checking conflicts…</div>';
    resultDiv.classList.remove('hidden');
  }

  try {
    const res  = await fetch('/planner/api/conflict-check', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        date, start_time: start, end_time: end,
        program: user?.program || 'BBA',
        year:    user?.year    || 1,
        semester:user?.semester|| 1,
      })
    });
    const data = await res.json();

    if (!data.success) {
      if (resultDiv) resultDiv.innerHTML = '<div class="ts-empty">Check failed. Try again.</div>';
      return;
    }

    if (!data.conflicts || !data.conflicts.length) {
      if (resultDiv) resultDiv.innerHTML = `
      <div style="padding:16px;background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.25);border-radius:var(--radius-sm);">
        <div style="color:var(--green);font-weight:700;margin-bottom:4px;">✅ No Conflicts!</div>
        <div style="font-size:0.84rem;color:var(--text-muted);">
          Your plan on ${data.day || ''} ${start}–${end} is free of university classes.
        </div>
      </div>`;
      return;
    }

    let html = `
    <div class="conflict-box">
      <div class="conflict-title">⚠️ ${data.conflicts.length} Conflict(s) Found</div>`;
    data.conflicts.forEach(c => {
      html += `<div class="conflict-item">
        📚 <strong>${c.course_code}</strong> — ${c.course_name || c.course_code}
        &nbsp;|&nbsp; ${c.time_slot} &nbsp;|&nbsp; Room ${c.room_no}
      </div>`;
    });
    html += `</div>`;

    const aiKey = localStorage.getItem('us_ai_key');
    if (aiKey) {
      html += `
      <div class="ai-suggestion-box">
        <div class="ai-suggestion-title">
          ✨ AI Smart Balance Suggestion
          <span id="aiSpinner" style="animation:blinkAnim 0.8s infinite;margin-left:6px;">⏳</span>
        </div>
        <div class="ai-suggestion-text" id="aiSuggText">Generating…</div>
      </div>`;
      if (resultDiv) resultDiv.innerHTML = html;

      const summary = data.conflicts.map(c =>
        `${c.course_code} (${c.course_name || c.course_code}) ${c.time_start}–${c.time_end}`
      ).join('; ');

      await callAI(aiKey, summary, date, start, end, data.day || '', user);
    } else {
      html += `
      <div style="margin-top:10px;padding:12px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:0.82rem;color:var(--text-muted);">
        💡 Add your Gemini or OpenAI API key above to get AI-powered suggestions.
      </div>`;
      if (resultDiv) resultDiv.innerHTML = html;
    }

  } catch(e) {
    if (resultDiv) resultDiv.innerHTML = `<div class="ts-empty">Error: ${e.message}</div>`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Check Conflicts'; }
  }
}

// ── AI API — Gemini + OpenAI ─────────────────────────────────

async function callAI(apiKey, conflictSummary, date, start, end, day, user) {
  const textEl    = document.getElementById('aiSuggText');
  const spinnerEl = document.getElementById('aiSpinner');

  const prompt =
    `I am a student at Rabindra University Bangladesh, Department of Management.\n` +
    `Program: ${user?.program || 'BBA'}, Year ${user?.year || 1}, Semester ${user?.semester || 1}.\n` +
    `I have a personal commitment on ${day} ${date} from ${start} to ${end}.\n` +
    `This conflicts with: ${conflictSummary}.\n\n` +
    `Give me 4-5 short, practical bullet points on:\n` +
    `- What to prioritise\n` +
    `- How to catch up on missed class\n` +
    `- A time management tip\n` +
    `Be concise and friendly. Start each bullet with an emoji.`;

  let result = '';
  let errorMsg = '';

  // ── Gemini ───────────────────────────────────────────────
  if (!apiKey.startsWith('sk-')) {
    try {
      const url  = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key=${apiKey}`;
      const resp = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.7, maxOutputTokens: 400 }
        })
      });
      const json = await resp.json();

      if (!resp.ok) {
        errorMsg = `Gemini: ${json?.error?.message || `HTTP ${resp.status}`}`;
      } else {
        result = json?.candidates?.[0]?.content?.parts?.[0]?.text || '';
        if (!result) errorMsg = 'Gemini returned empty response.';
      }
    } catch(e) {
      errorMsg = `Gemini network error: ${e.message}`;
    }
  }

  // ── OpenAI (fallback or primary if sk-) ───────────────────
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
          max_tokens:  400,
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
    } catch(e) {
      errorMsg = `OpenAI network error: ${e.message}`;
    }
  }

  // ── Show result ───────────────────────────────────────────
  if (spinnerEl) spinnerEl.remove();
  if (textEl) {
    if (result) {
      textEl.textContent = result;
    } else {
      textEl.innerHTML = `
      <span style="color:var(--red);">⚠️ ${errorMsg}</span><br>
      <span style="font-size:0.78rem;color:var(--text-muted);margin-top:4px;display:block;">
        Tip: Make sure your API key is correct and has access to the model.
        Gemini keys start with AIza… · OpenAI keys start with sk-…
      </span>`;
    }
  }
}