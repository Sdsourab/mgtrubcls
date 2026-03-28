/**
 * ai-preloader.js — UniSync Background AI Model Loader
 * ──────────────────────────────────────────────────────
 * Loads Xenova/Phi-3-mini-4k-instruct into the browser cache
 * silently in the background as soon as the user visits the site.
 *
 * By the time they reach the AI Planner page and click
 * "Check Conflicts", the model is already warm and ready.
 *
 * Strategy:
 *  1. Wait 3s after page load (don't compete with critical resources)
 *  2. Load Transformers.js dynamically
 *  3. Initialise the pipeline — this triggers model download + cache
 *  4. Store the ready pipeline on window.__aiPipeline
 *  5. Dispatch a custom "ai-ready" event so any page can listen
 *
 * Model: Xenova/Phi-3-mini-4k-instruct (q4, ~600 MB, cached after first load)
 * Subsequent visits: model served from browser cache (<1 s warm-up)
 */

(function () {
  'use strict';

  // Global state — shared with planner.js
  window.__aiState = window.__aiState || {
    pipeline: null,
    status:   'idle',   // idle | loading | ready | error
    error:    null,
  };

  // Don't double-load if already started
  if (window.__aiState.status !== 'idle') return;

  async function preloadAI() {
    if (window.__aiState.status !== 'idle') return;
    window.__aiState.status = 'loading';
    _broadcastStatus('loading');

    try {
      const { pipeline, env } = await import(
        'https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2/dist/transformers.min.js'
      );

      env.allowRemoteModels   = true;
      env.useBrowserCache     = true;   // cache model weights in IndexedDB
      env.allowLocalModels    = false;

      // Progress callback — lets the badge show download %
      const pipe = await pipeline(
        'text-generation',
        'Xenova/Phi-3-mini-4k-instruct',
        {
          dtype:  'q4',
          device: 'wasm',
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

    } catch (err) {
      window.__aiState.status = 'error';
      window.__aiState.error  = err.message || String(err);
      _broadcastStatus('error', null, window.__aiState.error);
    }
  }

  /** Dispatch a custom event + update any visible AI status badge. */
  function _broadcastStatus(status, pct, errMsg) {
    // Custom event — planner.js listens to this
    window.dispatchEvent(new CustomEvent('ai-status', {
      detail: { status, pct: pct ?? null, error: errMsg ?? null },
    }));

    // Update the status badge if it exists on this page
    _updateBadge(status, pct, errMsg);
  }

  function _updateBadge(status, pct, errMsg) {
    const dot  = document.getElementById('aiBadgeDot');
    const text = document.getElementById('aiBadgeText');
    const sub  = document.getElementById('aiBadgeSub');
    if (!dot || !text) return;

    if (status === 'loading') {
      dot.style.background   = 'var(--amber)';
      dot.style.boxShadow    = '0 0 6px var(--amber)';
      dot.style.animation    = 'pulse-green 1.8s infinite';
      text.style.color       = 'var(--amber)';
      text.textContent       = pct !== null
        ? `AI Loading… ${pct}%`
        : 'AI Loading…';
      if (sub) sub.textContent = '— Downloading model · runs 100% in your browser · no API key needed';

    } else if (status === 'ready') {
      dot.style.background   = 'var(--green)';
      dot.style.boxShadow    = '0 0 6px var(--green)';
      dot.style.animation    = 'pulse-green 1.8s infinite';
      text.style.color       = 'var(--green)';
      text.textContent       = '🤖 AI Ready';
      if (sub) sub.textContent = '— Transformers.js · Phi-3-mini · runs entirely in your browser';

    } else if (status === 'error') {
      dot.style.background   = 'var(--red, #f87171)';
      dot.style.boxShadow    = 'none';
      dot.style.animation    = 'none';
      text.style.color       = 'var(--red, #f87171)';
      text.textContent       = 'AI Unavailable';
      if (sub) sub.textContent = errMsg ? `— ${errMsg}` : '— Could not load model in this browser';
    }
  }

  // Wait 3 s after page load so critical resources get priority
  if (document.readyState === 'complete') {
    setTimeout(preloadAI, 3000);
  } else {
    window.addEventListener('load', () => setTimeout(preloadAI, 3000));
  }

  // Also re-run _updateBadge when the planner page injects its badge
  // (the badge elements don't exist on other pages, so this is safe)
  window.addEventListener('ai-status', () => {
    _updateBadge(
      window.__aiState.status,
      null,
      window.__aiState.error
    );
  });

})();