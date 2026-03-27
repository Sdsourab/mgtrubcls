/* UniSync — AI Personal Planner JS */

let allPlans = [];

document.addEventListener('DOMContentLoaded', () => {
    UniSync.requireAuth();
    loadPlans();
    loadAiKey();
    // Pre-fill today
    const today = new Date().toISOString().split('T')[0];
    const dateInputs = ['cc_date','p_date'];
    dateInputs.forEach(id => { const el = document.getElementById(id); if(el) el.value = today; });
});

// ── AI Key ──────────────────────────────────────────────────

function saveAiKey(val) {
    if (val) localStorage.setItem('us_ai_key', val);
    else     localStorage.removeItem('us_ai_key');
}
function loadAiKey() {
    const key = localStorage.getItem('us_ai_key') || '';
    const inp = document.getElementById('aiKeyInput');
    if (inp) inp.value = key;
}
function clearAiKey() {
    localStorage.removeItem('us_ai_key');
    document.getElementById('aiKeyInput').value = '';
    UniSync.toast('AI key cleared', 'success');
}
function toggleAiKey() {
    const inp = document.getElementById('aiKeyInput');
    const btn = event.target;
    if (inp.type === 'password') { inp.type = 'text';     btn.textContent = 'Hide'; }
    else                         { inp.type = 'password'; btn.textContent = 'Show'; }
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
    list.innerHTML = allPlans.map(p => {
        const typeColors = {personal:'var(--accent-light)',tuition:'var(--amber)',work:'var(--cyan)',other:'var(--text-muted)'};
        const color = typeColors[p.type] || 'var(--text-muted)';
        return `
        <div class="plan-item">
            <div class="plan-type-dot ${p.type}"></div>
            <div class="plan-info">
                <div class="plan-title">${p.title}</div>
                <div class="plan-meta">${p.date} · ${p.start_time}–${p.end_time} · ${p.type}</div>
                ${p.note ? `<div class="plan-meta" style="margin-top:2px;font-style:italic;">${p.note}</div>` : ''}
            </div>
            <button class="btn-sm btn-danger" onclick="deletePlan('${p.id}')">✕</button>
        </div>`;
    }).join('');
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

// ── Conflict Checker + AI ────────────────────────────────────

async function checkConflict() {
    const date  = document.getElementById('cc_date').value;
    const start = document.getElementById('cc_start').value;
    const end   = document.getElementById('cc_end').value;
    const user  = UniSync.getUser();

    if (!date || !start || !end) {
        UniSync.toast('Please fill in date, start and end time', 'warning');
        return;
    }

    const resultDiv = document.getElementById('conflictResult');
    resultDiv.innerHTML = '<div class="ts-loading">Checking conflicts…</div>';
    resultDiv.classList.remove('hidden');

    try {
        const res  = await fetch('/planner/api/conflict-check', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({
                date, start_time: start, end_time: end,
                program: user?.program || 'BBA'
            })
        });
        const data = await res.json();

        if (!data.success) {
            resultDiv.innerHTML = '<div class="ts-empty">Check failed. Try again.</div>';
            return;
        }

        if (!data.conflicts.length) {
            resultDiv.innerHTML = `
            <div style="padding:14px;background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.25);border-radius:var(--radius-sm);">
                <div style="color:var(--green);font-weight:700;margin-bottom:4px;">✅ No Conflicts!</div>
                <div style="font-size:0.84rem;color:var(--text-muted);">Your plan on ${data.day} from ${start} to ${end} is free of university classes.</div>
            </div>`;
            return;
        }

        // Build conflict display
        let html = `
        <div class="conflict-box">
            <div class="conflict-title">⚠️ ${data.conflicts.length} Conflict(s) Detected</div>`;
        data.conflicts.forEach(c => {
            html += `<div class="conflict-item">
                📚 <strong>${c.course_code}</strong> — ${c.course_name || c.course_code}
                &nbsp;|&nbsp; ${c.time_slot} &nbsp;|&nbsp; Room ${c.room_no}
            </div>`;
        });
        html += `</div>`;

        // Try AI if key exists
        const aiKey = localStorage.getItem('us_ai_key');
        if (aiKey) {
            html += `<div class="ai-suggestion-box">
                <div class="ai-suggestion-title">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="14" height="14">
                        <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 15h-2v-2h2zm0-4h-2V7h2z"/>
                    </svg>
                    AI Smart Balance Suggestion
                </div>
                <div class="ai-suggestion-text" id="aiSuggestionText">Generating suggestion…</div>
            </div>`;
            resultDiv.innerHTML = html;
            fetchAiSuggestion(aiKey, data.conflicts, date, start, end, data.day);
        } else {
            html += `<div style="margin-top:10px;font-size:0.8rem;color:var(--text-muted);">
                💡 Add your AI API key above to get smart time-balance suggestions.
            </div>`;
            resultDiv.innerHTML = html;
        }

    } catch { resultDiv.innerHTML = '<div class="ts-empty">Connection error.</div>'; }
}

async function fetchAiSuggestion(apiKey, conflicts, date, start, end, dayName) {
    const conflictSummary = conflicts.map(c =>
        `${c.course_code} (${c.course_name || c.course_code}) from ${c.time_start} to ${c.time_end} in Room ${c.room_no}`
    ).join(', ');

    const prompt = `I am a university student at Rabindra University Bangladesh, Department of Management.
I have a personal commitment on ${dayName}, ${date} from ${start} to ${end}.
It conflicts with these university classes: ${conflictSummary}.

Please give me a SHORT, practical "Smart Balance Suggestion" (3-5 bullet points) on how to manage this conflict. 
Include: what to prioritize, how to catch up on missed class content, and a time tip.
Be concise and student-friendly. Use bullet points starting with an emoji.`;

    try {
        let suggestion = '';

        // Try Gemini first
        if (apiKey.startsWith('AI') || apiKey.length > 30) {
            try {
                const geminiRes = await fetch(
                    `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`,
                    {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            contents: [{ parts: [{ text: prompt }] }]
                        })
                    }
                );
                const geminiData = await geminiRes.json();
                suggestion = geminiData?.candidates?.[0]?.content?.parts?.[0]?.text || '';
            } catch {}
        }

        // Fallback: OpenAI
        if (!suggestion && apiKey.startsWith('sk-')) {
            const openaiRes = await fetch('https://api.openai.com/v1/chat/completions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${apiKey}`
                },
                body: JSON.stringify({
                    model: 'gpt-3.5-turbo',
                    messages: [{ role: 'user', content: prompt }],
                    max_tokens: 300
                })
            });
            const openaiData = await openaiRes.json();
            suggestion = openaiData?.choices?.[0]?.message?.content || '';
        }

        const el = document.getElementById('aiSuggestionText');
        if (el) el.textContent = suggestion || 'Could not generate suggestion. Check your API key.';

    } catch(e) {
        const el = document.getElementById('aiSuggestionText');
        if (el) el.textContent = 'AI request failed. Check your API key and internet connection.';
    }
}