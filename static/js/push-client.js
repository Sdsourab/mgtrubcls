/**
 * UniSync — Push Notification Client  v2.0
 * ─────────────────────────────────────────
 * Handles:
 *   1. Requesting notification permission (with gentle prompt)
 *   2. Subscribing to Web Push via PushManager
 *   3. Saving subscription to /api/push/subscribe
 *   4. Re-syncing subscription on every page load (keeps DB fresh)
 *   5. Unsubscribing via /api/push/unsubscribe
 *
 * Loaded in base.html via <script defer>.
 * Service Worker is already registered by base.html — this file
 * does NOT re-register the SW.
 */

(function () {
  'use strict';

  // ── Helpers ──────────────────────────────────────────────────

  function urlBase64ToUint8Array(b64) {
    var padding = '='.repeat((4 - (b64.length % 4)) % 4);
    var base64  = (b64 + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw     = atob(base64);
    var out     = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  function getUser() {
    try {
      var raw = localStorage.getItem('us_user');
      return raw ? JSON.parse(raw) : null;
    } catch(e) { return null; }
  }

  function getVapidKey() {
    return window.__VAPID_PUBLIC_KEY || '';
  }

  // ── Save subscription to backend ────────────────────────────

  async function saveSub(sub, userId) {
    try {
      var res = await fetch('/api/push/subscribe', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ user_id: userId, subscription: sub.toJSON() }),
      });
      if (!res.ok) {
        console.warn('[Push] save failed:', res.status);
      }
    } catch(e) {
      console.warn('[Push] save error:', e);
    }
  }

  // ── Main subscribe flow ──────────────────────────────────────

  async function subscribeToPush(showPrompt) {
    var vapidKey = getVapidKey();
    if (!vapidKey) {
      // VAPID key not configured on server — skip silently
      return;
    }

    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      return; // Browser doesn't support push
    }

    var user = getUser();
    if (!user || !user.id) return;

    try {
      var reg = await navigator.serviceWorker.ready;

      // Check existing subscription first
      var existing = await reg.pushManager.getSubscription();
      if (existing) {
        // Already subscribed — just re-sync with server (silent)
        await saveSub(existing, user.id);
        return;
      }

      // Need permission
      var perm = Notification.permission;

      if (perm === 'denied') {
        return; // User explicitly denied — respect that
      }

      if (perm === 'default') {
        if (!showPrompt) return; // Don't ask automatically every page load

        // Ask permission
        var granted = await Notification.requestPermission();
        if (granted !== 'granted') return;
      }

      // Subscribe
      var sub = await reg.pushManager.subscribe({
        userVisibleOnly:      true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      });

      await saveSub(sub, user.id);

      console.log('[Push] Subscribed successfully');

      // Show success toast if UniSync.toast is available
      if (window.UniSync && UniSync.toast) {
        UniSync.toast('🔔 Push notifications enabled!', 'success', 3000);
      }

    } catch(err) {
      console.warn('[Push] Subscribe error:', err.message);
    }
  }

  // ── Unsubscribe ─────────────────────────────────────────────

  window.unsubscribePush = async function() {
    var user = getUser();
    if (!user || !user.id) return;

    try {
      var reg      = await navigator.serviceWorker.ready;
      var existing = await reg.pushManager.getSubscription();

      if (existing) {
        var endpoint = existing.endpoint;
        await existing.unsubscribe();

        // Remove from server
        await fetch('/api/push/unsubscribe', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ user_id: user.id, endpoint: endpoint }),
        });

        if (window.UniSync && UniSync.toast) {
          UniSync.toast('🔕 Push notifications disabled.', 'info', 3000);
        }
      }
    } catch(e) {
      console.warn('[Push] Unsubscribe error:', e);
    }
  };

  // ── Check status ─────────────────────────────────────────────

  window.isPushSubscribed = async function() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return false;
    try {
      var reg = await navigator.serviceWorker.ready;
      var sub = await reg.pushManager.getSubscription();
      return !!sub;
    } catch(e) {
      return false;
    }
  };

  // ── Auto-run on page load ────────────────────────────────────
  // Strategy:
  //   • On load: silently re-sync if already subscribed (keeps DB fresh)
  //   • After 8 seconds on first visit today: show permission prompt ONCE
  //     (localStorage flag prevents repeated prompts)

  window.addEventListener('load', function() {
    var user = getUser();
    if (!user) return;

    // Delay to let the page fully render first
    setTimeout(async function() {
      var vapidKey = getVapidKey();
      if (!vapidKey) return;

      if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;

      // Silent re-sync (no prompt)
      await subscribeToPush(false);

      // First-time prompt logic: show once per day
      var promptKey = 'push_prompted_' + new Date().toDateString();
      var alreadyPrompted = localStorage.getItem(promptKey);

      if (!alreadyPrompted && Notification.permission === 'default') {
        localStorage.setItem(promptKey, '1');

        // Show a gentle in-app prompt after 8s
        setTimeout(function() {
          _showPushBanner();
        }, 3000);
      }

    }, 5000);
  });

  // ── Gentle in-app push prompt banner ─────────────────────────

  function _showPushBanner() {
    // Don't show if user already denied
    if (Notification.permission === 'denied') return;
    if (Notification.permission === 'granted') return;

    var vapidKey = getVapidKey();
    if (!vapidKey) return;

    // Create banner
    var banner = document.createElement('div');
    banner.id  = 'pushPromptBanner';
    banner.style.cssText = [
      'position:fixed',
      'bottom:80px',       // above mobile bottom nav
      'left:50%',
      'transform:translateX(-50%)',
      'background:#1a1a2e',
      'color:#e8e0d0',
      'padding:14px 18px',
      'border-radius:14px',
      'font-family:Outfit,sans-serif',
      'font-size:.85rem',
      'box-shadow:0 8px 32px rgba(0,0,0,.4)',
      'z-index:9000',
      'display:flex',
      'align-items:center',
      'gap:14px',
      'max-width:360px',
      'width:calc(100% - 40px)',
      'border:1px solid rgba(188,111,55,.3)',
      'animation:slideUpBanner .3s ease',
    ].join(';');

    banner.innerHTML =
      '<span style="font-size:1.4rem;flex-shrink:0;">🔔</span>'
      + '<div style="flex:1;min-width:0;">'
      +   '<div style="font-weight:700;margin-bottom:3px;">Class notifications</div>'
      +   '<div style="font-size:.75rem;color:#9a9080;line-height:1.4;">Get notified 30 min before class, and when CR posts updates.</div>'
      + '</div>'
      + '<div style="display:flex;flex-direction:column;gap:6px;flex-shrink:0;">'
      +   '<button id="pushEnableBtn" style="padding:6px 14px;background:linear-gradient(135deg,#BC6F37,#CDA96A);color:#fff;border:none;border-radius:8px;font-family:Outfit,sans-serif;font-size:.78rem;font-weight:700;cursor:pointer;white-space:nowrap;">Enable</button>'
      +   '<button id="pushDismissBtn" style="padding:5px 14px;background:transparent;color:#9a9080;border:1px solid rgba(255,255,255,.1);border-radius:8px;font-family:Outfit,sans-serif;font-size:.75rem;cursor:pointer;white-space:nowrap;">Not now</button>'
      + '</div>';

    // Add animation keyframe if not already present
    if (!document.getElementById('pushBannerStyle')) {
      var style = document.createElement('style');
      style.id  = 'pushBannerStyle';
      style.textContent = '@keyframes slideUpBanner{from{opacity:0;transform:translateX(-50%) translateY(20px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}';
      document.head.appendChild(style);
    }

    document.body.appendChild(banner);

    banner.querySelector('#pushEnableBtn').addEventListener('click', function() {
      banner.remove();
      subscribeToPush(true);  // This time with prompt = true
    });

    banner.querySelector('#pushDismissBtn').addEventListener('click', function() {
      banner.remove();
    });

    // Auto-dismiss after 12 seconds
    setTimeout(function() {
      if (document.getElementById('pushPromptBanner')) {
        banner.style.animation = 'none';
        banner.style.opacity   = '0';
        banner.style.transition = 'opacity .3s';
        setTimeout(function() { banner.remove(); }, 300);
      }
    }, 12000);
  }

})();