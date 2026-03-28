/**
 * ai-preloader.js — UniSync Smart AI Engine v8.0
 * ──────────────────────────────────────────────
 * Model  : Xenova/all-MiniLM-L6-v2  (feature-extraction, ~23 MB)
 * Why    : 23 MB loads in seconds vs 600 MB (Phi-3-mini). No generative AI
 *          needed — semantic similarity finds the MOST RELEVANT advice from
 *          a curated knowledge base. More reliable, no hallucinations.
 *
 * How it works:
 *  1. Page loads → wait 2s → silently download 23 MB embedding model
 *  2. Pre-compute embeddings for every advice entry in the knowledge base
 *  3. When user triggers Conflict Checker → buildContext(payload)
 *  4. Embed that context string → cosine-similarity vs all advice entries
 *  5. Return top-4 most semantically relevant tips
 *
 * API:  window.__aiEngine.suggest(contextText, k=4) → Promise<string[]>
 * State: window.__aiState  { status, pipeline, error }
 */

(function () {
  'use strict';

  // ── Global shared state (read by planner.js) ──────────────────────────────
  window.__aiState = window.__aiState || {
    status:   'idle',   // idle | loading | ready | error
    pipeline: null,
    error:    null,
  };

  if (window.__aiState.status !== 'idle') return;  // already started

  // ═══════════════════════════════════════════════════════════════════════════
  //  ADVICE KNOWLEDGE BASE
  //  Each entry:
  //    context — semantic description of WHEN this advice applies
  //    tip     — the actual advice shown to the student
  // ═══════════════════════════════════════════════════════════════════════════
  const ADVICE_DB = [

    // ── Schedule conflicts ────────────────────────────────────────────────
    {
      context: 'class schedule conflict overlap time collision personal plan university',
      tip: '⚠️ Class conflict detected! Shift your plan 30–45 min after class ends for a smooth transition.',
    },
    {
      context: 'multiple classes conflict double booking busy day overlapping schedule',
      tip: '📅 Multiple conflicts found — split your plan into 2 shorter sessions fitted around free slots.',
    },
    {
      context: 'cannot reschedule important deadline class conflict attend',
      tip: '🔁 Attend class first — 50-min of focused learning compounds daily. Reschedule the plan for after.',
    },
    {
      context: 'conflict exam test day important assessment cannot skip class',
      tip: '📖 Exam/test day conflict! Prioritise your class — even 30 min of revision in the remaining time helps.',
    },

    // ── No conflict / free slots ──────────────────────────────────────────
    {
      context: 'no conflict free time available clear window good timing no class overlap',
      tip: '✨ No conflicts — this is your prime focus window. Lock in, eliminate distractions, and get it done.',
    },
    {
      context: 'small gap free slot short window between classes 30 minutes',
      tip: '⏰ Short window? Perfect for reviewing yesterday\'s notes or responding to academic messages.',
    },

    // ── Study & academic ──────────────────────────────────────────────────
    {
      context: 'study revision review notes academic lecture exam preparation spaced repetition',
      tip: '📚 Review lecture notes within 24 hrs — spaced repetition boosts retention by 5× according to research.',
    },
    {
      context: 'assignment homework project deadline submission task completion',
      tip: '✅ Break your assignment into 25-min Pomodoro blocks. Consistent small progress beats last-minute rushes.',
    },
    {
      context: 'exam test preparation final midterm upcoming semester academic',
      tip: '🎯 Make a revision table — list every topic, colour-code by difficulty, tackle one topic per session.',
    },
    {
      context: 'missed class absence absent catch up lecture content notes',
      tip: '📝 Missed class? Borrow a classmate\'s notes AND watch a relevant YouTube lecture the same day.',
    },
    {
      context: 'group work team project collaboration coordination group meeting',
      tip: '👥 Schedule group sessions early in the week — leaves Thursday free for individual revision.',
    },

    // ── Time management ───────────────────────────────────────────────────
    {
      context: 'morning early hours productive focus energy time management peak performance',
      tip: '🌅 Morning = your sharpest hours. Tackle the hardest task before 11 AM while focus is at its peak.',
    },
    {
      context: 'afternoon post-lunch sluggish low energy recovery fatigue mid-day',
      tip: '☀️ Afternoon energy dip is normal — schedule lighter tasks now, save deep work for morning or evening.',
    },
    {
      context: 'evening night review consolidate learning day summary before sleep',
      tip: '🌙 10 min before bed: review what you studied today. Sleep consolidates memory — it\'s free revision.',
    },
    {
      context: 'time management planning priorities urgent important schedule blocks',
      tip: '⏱️ Try time-blocking: assign every hour a specific task. Unplanned time almost always gets wasted.',
    },

    // ── Wellbeing ─────────────────────────────────────────────────────────
    {
      context: 'stress overloaded too much workload overwhelmed burnout exhausted',
      tip: '🧘 Overwhelmed? Apply the 2-minute rule — if it takes under 2 mins, do it now; otherwise schedule it.',
    },
    {
      context: 'balance rest breaks self care social activities wellbeing mental health',
      tip: '⚖️ Breaks are productive! Even 30 min of leisure daily prevents burnout and sharpens concentration.',
    },
    {
      context: 'motivation encouragement success achievement progress forward momentum goals',
      tip: '🌟 Scheduling your time proactively puts you ahead of 90% of your peers — keep this habit going!',
    },

    // ── Work / tuition ────────────────────────────────────────────────────
    {
      context: 'tuition teaching private work income job part-time balance university studies',
      tip: '💼 Balancing tuition/work with studies? Block dedicated study hours and protect them like a class.',
    },

    // ── Weekend / holiday ─────────────────────────────────────────────────
    {
      context: 'weekend friday holiday no class rest day recreation personal planning leisure',
      tip: '🌴 Weekend plan! Great time for longer project sessions, assignment drafts, or a full recharge.',
    },

    // ── University specific ───────────────────────────────────────────────
    {
      context: 'Rabindra University Bangladesh BBA MBA management department semester campus routine',
      tip: '🏛️ Check the academic portal regularly — routine changes and special notices are posted frequently.',
    },
    {
      context: 'personal plan tuition work type schedule variety diverse activities balance',
      tip: '📋 Mixing personal, tuition, and study plans throughout the week prevents monotony and boosts output.',
    },
  ];

  // ═══════════════════════════════════════════════════════════════════════════
  //  MATH HELPERS
  // ═══════════════════════════════════════════════════════════════════════════

  function cosineSimilarity(a, b) {
    let dot = 0, na = 0, nb = 0;
    for (let i = 0; i < a.length; i++) {
      dot += a[i] * b[i];
      na  += a[i] * a[i];
      nb  += b[i] * b[i];
    }
    return dot / (Math.sqrt(na) * Math.sqrt(nb) + 1e-10);
  }

  // ═══════════════════════════════════════════════════════════════════════════
  //  AI ENGINE  (window.__aiEngine)
  // ═══════════════════════════════════════════════════════════════════════════

  const engine = {
    _indexBuilt:   false,
    _dbEmbeddings: [],   // parallel array to ADVICE_DB

    /** Embed a text string using the loaded MiniLM pipeline. */
    async _embed(text) {
      const out = await window.__aiState.pipeline(text, {
        pooling:   'mean',
        normalize: true,
      });
      // out.data is a Float32Array — convert to plain Array for math ops
      return Array.from(out.data);
    },

    /** Pre-compute and cache embeddings for every ADVICE_DB entry. */
    async _buildIndex() {
      if (this._indexBuilt) return;
      this._dbEmbeddings = [];
      for (const entry of ADVICE_DB) {
        this._dbEmbeddings.push(await this._embed(entry.context));
      }
      this._indexBuilt = true;
    },

    /**
     * Main API — returns the top-k most relevant advice strings for the given
     * user context.
     *
     * @param {string} contextText - e.g. "conflict Monday BBA morning free slot"
     * @param {number} k           - number of tips to return (default 4)
     * @returns {Promise<string[]>}
     */
    async suggest(contextText, k = 4) {
      await this._buildIndex();

      const queryEmb = await this._embed(contextText);

      const scored = ADVICE_DB.map((entry, i) => ({
        tip:   entry.tip,
        score: cosineSimilarity(queryEmb, this._dbEmbeddings[i]),
      }));

      scored.sort((a, b) => b.score - a.score);
      return scored.slice(0, k).map(s => s.tip);
    },
  };

  // Expose globally so planner.js (and any other page) can call it
  window.__aiEngine = engine;

  // ═══════════════════════════════════════════════════════════════════════════
  //  MODEL LOADER
  // ═══════════════════════════════════════════════════════════════════════════

  async function preloadAI() {
    if (window.__aiState.status !== 'idle') return;
    window.__aiState.status = 'loading';
    _broadcastStatus('loading');

    try {
      const { pipeline, env } = await import(
        'https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2/dist/transformers.min.js'
      );

      env.allowRemoteModels = true;
      env.useBrowserCache   = true;   // cache weights in IndexedDB — instant on repeat visits
      env.allowLocalModels  = false;

      const pipe = await pipeline(
        'feature-extraction',            // embedding, NOT text-generation
        'Xenova/all-MiniLM-L6-v2',      // 23 MB q8 — downloads in seconds
        {
          progress_callback: (info) => {
            if (info.status === 'downloading') {
              const pct = info.total
                ? Math.round((info.loaded / info.total) * 100)
                : null;
              _broadcastStatus('loading', pct);
            }
          },
        }
      );

      window.__aiState.pipeline = pipe;
      window.__aiState.status   = 'ready';
      window.__aiState.error    = null;
      _broadcastStatus('ready');

      // Kick off index building in background so first suggest() call is instant
      engine._buildIndex().catch(err => console.warn('[AI] Index build error:', err));

    } catch (err) {
      window.__aiState.status = 'error';
      window.__aiState.error  = err.message || String(err);
      _broadcastStatus('error', null, window.__aiState.error);
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  //  STATUS BROADCAST + BADGE UPDATE
  // ═══════════════════════════════════════════════════════════════════════════

  function _broadcastStatus(status, pct, errMsg) {
    window.dispatchEvent(new CustomEvent('ai-status', {
      detail: { status, pct: pct ?? null, error: errMsg ?? null },
    }));
    _updateBadge(status, pct, errMsg);
  }

  function _updateBadge(status, pct, errMsg) {
    const dot  = document.getElementById('aiBadgeDot');
    const text = document.getElementById('aiBadgeText');
    const sub  = document.getElementById('aiBadgeSub');
    if (!dot || !text) return;

    if (status === 'loading') {
      dot.style.background = 'var(--amber)';
      dot.style.boxShadow  = '0 0 6px var(--amber)';
      dot.style.animation  = 'pulse-green 1.8s infinite';
      text.style.color     = 'var(--amber)';
      text.textContent     = pct !== null ? `AI Loading… ${pct}%` : 'AI Loading…';
      if (sub) sub.textContent = '— Downloading MiniLM model · 23 MB · no API key needed';

    } else if (status === 'ready') {
      dot.style.background = 'var(--green)';
      dot.style.boxShadow  = '0 0 6px var(--green)';
      dot.style.animation  = 'pulse-green 1.8s infinite';
      text.style.color     = 'var(--green)';
      text.textContent     = '🤖 AI Ready';
      if (sub) sub.textContent = '— Transformers.js · MiniLM-L6-v2 · semantic AI · 100% browser-native';

    } else if (status === 'error') {
      dot.style.background = 'var(--red, #f87171)';
      dot.style.boxShadow  = 'none';
      dot.style.animation  = 'none';
      text.style.color     = 'var(--red, #f87171)';
      text.textContent     = 'AI Unavailable';
      if (sub) sub.textContent = errMsg ? `— ${errMsg}` : '— Could not load model in this browser';
    }
  }

  // ── Start loading 2 s after page load (non-blocking) ─────────────────────
  if (document.readyState === 'complete') {
    setTimeout(preloadAI, 2000);
  } else {
    window.addEventListener('load', () => setTimeout(preloadAI, 2000));
  }

  // Re-sync badge whenever status changes (e.g. planner page mounts late)
  window.addEventListener('ai-status', () => {
    _updateBadge(window.__aiState.status, null, window.__aiState.error);
  });

})();