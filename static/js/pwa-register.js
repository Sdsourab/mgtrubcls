/**
 * UniSync PWA — Service Worker Registration
 * File: static/js/pwa-register.js
 *
 * Drop a single <script src="/static/js/pwa-register.js" defer></script>
 * anywhere in base.html (before </body>).
 *
 * Features:
 *  • Registers /sw.js at root scope (/)
 *  • Detects SW updates and shows a toast prompt to refresh
 *  • Provides installPrompt handling for the "Add to Home Screen" banner
 *  • Exposes window.UniSyncPWA for programmatic access
 */

(function () {
  'use strict';

  // ── Guard ──────────────────────────────────────────────────────────────────
  if (!('serviceWorker' in navigator)) {
    console.warn('[PWA] Service Workers not supported in this browser.');
    return;
  }

  // ── State ──────────────────────────────────────────────────────────────────
  let newWorkerWaiting = null;
  let installPromptEvent = null;

  // ── Registration ───────────────────────────────────────────────────────────
  async function registerSW() {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
        // 'classic' is the default; use 'module' only if sw.js uses ES modules
        type: 'classic',
        // Re-check SW script every 24h even with HTTP cache
        updateViaCache: 'none',
      });

      console.log('[PWA] Service Worker registered. Scope:', registration.scope);

      // ── Detect new SW waiting to activate ─────────────────────────────────
      registration.addEventListener('updatefound', () => {
        const newWorker = registration.installing;
        if (!newWorker) return;

        newWorker.addEventListener('statechange', () => {
          if (
            newWorker.state === 'installed' &&
            navigator.serviceWorker.controller
          ) {
            // New SW is waiting — existing content is still served from old SW
            newWorkerWaiting = newWorker;
            showUpdateToast();
          }
        });
      });

      // ── Detect SW already waiting on load (e.g. page refreshed) ───────────
      if (registration.waiting && navigator.serviceWorker.controller) {
        newWorkerWaiting = registration.waiting;
        showUpdateToast();
      }

      // ── Listen for SW-controlled page refresh ──────────────────────────────
      let refreshing = false;
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (!refreshing) {
          refreshing = true;
          window.location.reload();
        }
      });

      // ── Listen for messages from SW ────────────────────────────────────────
      navigator.serviceWorker.addEventListener('message', handleSWMessage);

      // ── Periodic update check (every 60 minutes) ───────────────────────────
      setInterval(() => {
        registration.update().catch(() => {});
      }, 60 * 60 * 1000);

      // ── Expose global reference ────────────────────────────────────────────
      window.UniSyncPWA = {
        registration,
        skipWaiting:        skipWaiting,
        requestInstall:     requestInstall,
        isInstalled:        isInstalled,
        isOnline:           () => navigator.onLine,
        clearCache:         clearCache,
      };

      return registration;

    } catch (error) {
      console.error('[PWA] Service Worker registration failed:', error);
    }
  }

  // ── Update Toast ───────────────────────────────────────────────────────────
  function showUpdateToast() {
    // Try to use UniSync's existing toast() function first
    if (window.UniSync && typeof window.UniSync.toast === 'function') {
      window.UniSync.toast(
        '🔄 New version available — click to update',
        'info',
        8000,
        () => skipWaiting()   // tap-to-refresh callback
      );
      return;
    }

    // Fallback: build a minimal toast
    const toast = document.createElement('div');
    toast.id = 'pwa-update-toast';
    toast.setAttribute('role', 'alert');
    toast.style.cssText = `
      position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%);
      background: #3C2A21; color: #FCF5E8; padding: 0.875rem 1.5rem;
      border-radius: 12px; font-family: 'Outfit', sans-serif; font-size: 0.9rem;
      box-shadow: 0 8px 32px rgba(60,42,33,0.35); z-index: 99999;
      cursor: pointer; display: flex; align-items: center; gap: 0.75rem;
      animation: pwaSlideUp 0.35s cubic-bezier(.22,.68,0,1.2) both;
    `;

    // Inject keyframe once
    if (!document.getElementById('pwa-toast-style')) {
      const style = document.createElement('style');
      style.id = 'pwa-toast-style';
      style.textContent = `
        @keyframes pwaSlideUp {
          from { opacity: 0; transform: translateX(-50%) translateY(20px); }
          to   { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
      `;
      document.head.appendChild(style);
    }

    toast.innerHTML = `
      <span>🔄 Update available</span>
      <button style="background:#FCF5E8;color:#3C2A21;border:none;border-radius:6px;
                     padding:0.35rem 0.85rem;cursor:pointer;font-weight:600;font-size:0.85rem;">
        Refresh
      </button>
      <button style="background:transparent;color:#c9a98a;border:none;cursor:pointer;
                     font-size:1.1rem;line-height:1;" aria-label="Dismiss">✕</button>
    `;

    const [, refreshBtn, dismissBtn] = toast.querySelectorAll('span, button, button');
    refreshBtn.addEventListener('click', () => { skipWaiting(); toast.remove(); });
    dismissBtn.addEventListener('click', () => toast.remove());

    document.body.appendChild(toast);

    // Auto-dismiss after 12s
    setTimeout(() => toast.remove(), 12000);
  }

  // ── Skip Waiting → triggers controllerchange → page reload ─────────────────
  function skipWaiting() {
    if (newWorkerWaiting) {
      newWorkerWaiting.postMessage({ type: 'SKIP_WAITING' });
    }
  }

  // ── Install Prompt (Add to Home Screen) ────────────────────────────────────
  window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    installPromptEvent = e;
    console.log('[PWA] Install prompt captured. Call UniSyncPWA.requestInstall()');

    // Show your own install button if you have one
    const btn = document.getElementById('pwa-install-btn');
    if (btn) btn.classList.remove('hidden');
  });

  window.addEventListener('appinstalled', () => {
    console.log('[PWA] App installed to home screen.');
    installPromptEvent = null;
    const btn = document.getElementById('pwa-install-btn');
    if (btn) btn.classList.add('hidden');
  });

  async function requestInstall() {
    if (!installPromptEvent) {
      console.warn('[PWA] No install prompt available.');
      return false;
    }
    installPromptEvent.prompt();
    const { outcome } = await installPromptEvent.userChoice;
    console.log('[PWA] Install outcome:', outcome);
    if (outcome === 'accepted') installPromptEvent = null;
    return outcome === 'accepted';
  }

  // ── isInstalled Detection ──────────────────────────────────────────────────
  function isInstalled() {
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true  // iOS Safari
    );
  }

  // ── Online / Offline Banner ────────────────────────────────────────────────
  function createOfflineBanner() {
    const banner = document.createElement('div');
    banner.id = 'pwa-offline-banner';
    banner.setAttribute('role', 'status');
    banner.setAttribute('aria-live', 'polite');
    banner.style.cssText = `
      display: none; position: fixed; top: 0; left: 0; right: 0;
      background: #8B1A1A; color: #fff; text-align: center;
      padding: 0.5rem 1rem; font-family: 'Outfit', sans-serif;
      font-size: 0.875rem; z-index: 99998; letter-spacing: 0.03em;
    `;
    banner.textContent = '⚠️ You are offline — some features may be unavailable';
    document.body.appendChild(banner);
    return banner;
  }

  function setupNetworkMonitoring() {
    // Wait until body exists
    if (!document.body) {
      document.addEventListener('DOMContentLoaded', setupNetworkMonitoring);
      return;
    }

    const banner = createOfflineBanner();

    function updateStatus() {
      if (navigator.onLine) {
        banner.style.display = 'none';
        document.body.style.paddingTop = '';
      } else {
        banner.style.display = 'block';
        document.body.style.paddingTop = banner.offsetHeight + 'px';
      }
    }

    window.addEventListener('online',  updateStatus);
    window.addEventListener('offline', updateStatus);
    updateStatus(); // initial check
  }

  // ── Handle Messages from SW ────────────────────────────────────────────────
  function handleSWMessage(event) {
    const { type, tag } = event.data || {};

    if (type === 'SW_SYNC') {
      console.log('[PWA] SW requested sync:', tag);
      // Trigger the offline-sync.js flush if it exposes a global
      if (window.OfflineSync && typeof window.OfflineSync.flush === 'function') {
        window.OfflineSync.flush(tag);
      }
    }

    if (type === 'CACHE_CLEARED') {
      console.log('[PWA] Cache cleared by SW.');
    }
  }

  // ── Clear all caches (dev helper / logout hook) ────────────────────────────
  function clearCache() {
    if (navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({ type: 'CLEAR_CACHE' });
    }
  }

  // ── Boot ───────────────────────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      registerSW();
      setupNetworkMonitoring();
    });
  } else {
    registerSW();
    setupNetworkMonitoring();
  }

})();