/* UniSync — AI Personal Planner + Fixed AI API */

let allPlans = [];

document.addEventListener('DOMContentLoaded', () => {
    UniSync.requireAuth();
    loadPlans();
    loadAiKey();
    const today = new Date().toISOString().split('T')[0];
    ['cc_date','p_date'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = today;
    });
});

// ── AI Key ───────────────────────────────────────────────────

function saveAiKey(val) {
    if (val && val.trim()) localStorage.setItem('us_ai_key', val.trim());
    else                   localStorage.removeItem('us_ai_key');
}

function loadAiKey() {
    const key = localStorage.getItem('us_ai_key') || '';
    const inp = document.getElementById('aiKeyInput');
    if (inp) inp.value = key;
    updateAiKeyStatus(key);
}

function updateAiKeyStatus(key) {
    const statusEl = document.getElementById('aiKeyStatus');
    if (!statusEl) return;
    if (!key) {
        statusEl.textContent = 'No key saved';
        statusEl.style.color = 'var(--text-muted)';
    } else if (key.startsWith('AIza') || key.startsWith('AI')) {
        statusEl.textContent = '✓ Gemini key detected';
        statusEl.style.color = 'var(--green)';
    } else if (key.startsWith('sk-')) {
        statusEl.textContent = '✓ OpenAI key detected';
        statusEl.style.color = 'var(--green)';
    } else {
        statusEl.textContent = '⚠ Key format unknown';
        statusEl.style.color = 'var(--amber)';
    }
}

function clearAiKey() {
    localStorage.removeItem('us_ai_key');
    const inp = document.getElementById('aiKeyInput');
    if (inp) inp.value = '';
    updateAiKeyStatus('');
    UniSync.toast('AI key cleared', 'success');
}

function toggleAiKey() {
    const inp = document.getElementById('aiKeyInput');
    const btn = event.target;
    inp.type    = inp.type === 'password' ? 'text' : 'password';
    btn.textContent = inp.type === 'text' ? 'Hide' : 'Show';
}

function onAiKeyInput(val) {
    saveAiKey(val);
    updateAiKeyStatus(val.trim());
}

// ── Plans CRUD ───────────────────────────────────────────────

async function loadPlans() {
    const user = UniSync.getUser();
    if (!user) return;
    try {
        const res  = await fetch(`/planner/api/plans?user_id=${user.id}`);
        const data = await res.json();
        if (data.success) { allPlans = data.data; renderPlans(); }
    } catch(e) { console.error(e); }
}

function renderPlans() {
    const list = document.getElementById('plansList');
    if (!allPlans.length) {
        list.innerHTML = '<div class="empty-state"><p>No plans yet. Add your first plan!</p></div>';
        return;
    }
    list.innerHTML = allPlans.map(p => `
    <div class="plan-item">
        <div class="plan-type-dot ${p.type}"></div>
        <div class="plan-info">
            <div class="plan-title">${p.title}</div>
            <div class="plan-meta">
                ${new Date(p.date).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})}
                · ${p.start_time}–${p.end_time}
                · <span style="text-transform:capitalize;">${p.type}</span>
            </div>
            ${p.note ? `<div class="plan-meta" style="font-style:italic;margin-top:1px;">${p.note}</div>` : ''}
        </div>
        <button class="btn-sm btn-danger" onclick="deletePlan('${p.id}')">✕</button>
    </div>`).join('');
}

async function submitPlan(e) {
    e.preventDefault();
    const user = UniSync.getUser();
    const payload = {
        user_id:    user.id,
        title:      document.getElementById('p_title').value,
        type:       document.getElementById('p_type').value,
        date:       document.getElementById('p_date').value,
        start_time: document.getElementById('p_start').value,
        end_time:   document.getElementById('p_end').value,
        note:       document.getElementById('p_note').value,
    };
    try {
        const res  = await fetch('/planner/api/plans', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            UniSync.toast('Plan saved!', 'success');
            document.getElementById('addPlanModal').classList.add('hidden');
            document.querySelector('#addPlanModal form').reset();
            loadPlans();
        } else { UniSync.toast(data.error || 'Error', 'error'); }
    } catch { UniSync.toast('Connection error', 'error'); }
}

async function deletePlan(id) {
    if (!confirm('Delete this plan?')) return;
    try {
        await fetch(`/planner/api/plans/${id}`, {method:'DELETE'});
        UniSync.toast('Deleted', 'success');
        allPlans = allPlans.filter(p => p.id !== id);
        renderPlans();
    } catch { UniSync.toast('Error', 'error'); }
}

function openAddPlan() {
    document.getElementById('addPlanModal').classList.remove('hidden');
}

// ── Conflict Checker ─────────────────────────────────────────

async function checkConflict() {
    const date  = document.getElementById('cc_date').value;
    const start = document.getElementById('cc_start').value;
    const end   = document.getElementById('cc_end').value;
    const user  = UniSync.getUser();

    if (!date || !start || !end) {
        UniSync.toast('Fill in date, start and end time', 'warning');
        return;
    }

    const btn = event.target;
    btn.disabled = true; btn.textContent = 'Checking…';

    const resultDiv = document.getElementById('conflictResult');
    resultDiv.innerHTML = '<div class="ts-loading">Checking conflicts…</div>';
    resultDiv.classList.remove('hidden');

    try {
        const res  = await fetch('/planner/api/conflict-check', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({
                date, start_time: start, end_time: end,
                program: user?.program || 'BBA',
            })
        });
        const data = await res.json();

        if (!data.success) {
            resultDiv.innerHTML = '<div class="ts-empty">Check failed.</div>';
            btn.disabled = false; btn.textContent = 'Check Conflicts';
            return;
        }

        if (!data.conflicts.length) {
            resultDiv.innerHTML = `
            <div style="padding:14px;background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.25);border-radius:var(--radius-sm);">
                <div style="color:var(--green);font-weight:700;margin-bottom:4px;">✅ No Conflicts!</div>
                <div style="font-size:0.84rem;color:var(--text-muted);">
                    Your plan on ${data.day} ${start}–${end} is free of university classes.
                </div>
            </div>`;
            btn.disabled = false; btn.textContent = 'Check Conflicts';
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
            <div class="ai-suggestion-box" id="aiSuggBox">
                <div class="ai-suggestion-title">
                    <span>✨ AI Smart Balance Suggestion</span>
                    <span id="aiLoadingDot" style="animation:blinkAnim 0.8s infinite;">⏳</span>
                </div>
                <div class="ai-suggestion-text" id="aiSuggestionText">
                    Generating personalised suggestion…
                </div>
            </div>`;
            resultDiv.innerHTML = html;

            const conflictSummary = data.conflicts.map(c =>
                `${c.course_code} (${c.course_name || c.course_code}) from ${c.time_start} to ${c.time_end}`
            ).join('; ');

            await fetchAiSuggestion(aiKey, conflictSummary, date, start, end, data.day, user);
        } else {
            html += `
            <div style="margin-top:10px;padding:12px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:0.82rem;color:var(--text-muted);">
                💡 Save your AI API key above to get smart time-balance suggestions from AI.
            </div>`;
            resultDiv.innerHTML = html;
        }

    } catch(e) {
        resultDiv.innerHTML = '<div class="ts-empty">Connection error. Try again.</div>';
    }
    btn.disabled = false; btn.textContent = 'Check Conflicts';
}

// ── AI API Call (Gemini + OpenAI, CORS-safe) ─────────────────

async function fetchAiSuggestion(apiKey, conflictSummary, date, start, end, dayName, user) {
    const prompt =
        `I am a university student at Rabindra University Bangladesh, Department of Management.\n` +
        `I am in ${user?.program || 'BBA'} Year ${user?.year || 1} Semester ${user?.semester || 1}.\n` +
        `I have a personal plan on ${dayName}, ${date} from ${start} to ${end}.\n` +
        `It conflicts with: ${conflictSummary}.\n\n` +
        `Give me a SHORT Smart Balance Suggestion (4-5 bullet points) with:\n` +
        `- What to prioritise\n` +
        `- How to catch up on missed class\n` +
        `- A practical time management tip\n` +
        `Be concise, practical, student-friendly. Start each bullet with an emoji.`;

    const textEl    = document.getElementById('aiSuggestionText');
    const loadingEl = document.getElementById('aiLoadingDot');

    try {
        let result = '';

        // ── Try Gemini (key starts with AIza or AI) ──────────
        if (!apiKey.startsWith('sk-')) {
            try {
                const geminiUrl =
                    `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key=${apiKey}`;
                const geminiResp = await fetch(geminiUrl, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        contents: [{
                            parts: [{ text: prompt }]
                        }],
                        generationConfig: {
                            temperature:     0.7,
                            maxOutputTokens: 400,
                        }
                    })
                });

                if (!geminiResp.ok) {
                    const errData = await geminiResp.json();
                    const errMsg  = errData?.error?.message || `HTTP ${geminiResp.status}`;
                    throw new Error(`Gemini error: ${errMsg}`);
                }

                const geminiData = await geminiResp.json();
                result = geminiData?.candidates?.[0]?.content?.parts?.[0]?.text || '';

                if (!result && geminiData?.error) {
                    throw new Error(geminiData.error.message || 'Gemini returned no content');
                }
            } catch(geminiErr) {
                console.warn('Gemini failed:', geminiErr.message);
                // If it's not an OpenAI key either, show the error
                if (!apiKey.startsWith('sk-')) {
                    if (textEl) {
                        textEl.textContent = `⚠️ ${geminiErr.message}\n\nMake sure your Gemini API key is valid and has the Generative Language API enabled.`;
                    }
                    if (loadingEl) loadingEl.remove();
                    return;
                }
            }
        }

        // ── Try OpenAI (key starts with sk-) ─────────────────
        if (!result && apiKey.startsWith('sk-')) {
            try {
                const openaiResp = await fetch('https://api.openai.com/v1/chat/completions', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${apiKey}`
                    },
                    body: JSON.stringify({
                        model:      'gpt-3.5-turbo',
                        messages:   [{ role: 'user', content: prompt }],
                        max_tokens: 400,
                        temperature: 0.7,
                    })
                });

                if (!openaiResp.ok) {
                    const errData = await openaiResp.json();
                    throw new Error(errData?.error?.message || `OpenAI HTTP ${openaiResp.status}`);
                }

                const openaiData = await openaiResp.json();
                result = openaiData?.choices?.[0]?.message?.content || '';
            } catch(openaiErr) {
                if (textEl) {
                    textEl.textContent = `⚠️ OpenAI Error: ${openaiErr.message}`;
                }
                if (loadingEl) loadingEl.remove();
                return;
            }
        }

        // ── Show result ───────────────────────────────────────
        if (textEl) {
            if (result) {
                textEl.textContent = result;
            } else {
                textEl.textContent = '⚠️ AI returned an empty response. Check your API key.';
            }
        }
    } catch(e) {
        if (textEl) textEl.textContent = `⚠️ Error: ${e.message}`;
    } finally {
        if (loadingEl) loadingEl.remove();
    }
}