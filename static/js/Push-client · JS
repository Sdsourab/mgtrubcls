/**
 * UniSync — Push Notification Client (push-client.js)
 * ─────────────────────────────────────────────────────
 * Asks for notification permission and saves push subscription
 * to Supabase so the server can send push alerts.
 *
 * NOTE: Service Worker is already registered in base.html.
 * This file ONLY handles push subscription — does NOT re-register SW.
 */

(function () {
  'use strict';

  const VAPID_PUBLIC_KEY = window.__VAPID_PUBLIC_KEY || '';

  function urlBase64ToUint8Array(b64) {
    const padding = '='.repeat((4 - (b64.length % 4)) % 4);
    const base64  = (b64 + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw     = atob(base64);
    const out     = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  async function subscribeToPush() {
    // Needs SW, PushManager, and a VAPID key
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    if (!VAPID_PUBLIC_KEY) return;

    try {
      const reg = await navigator.serviceWorker.ready;

      let sub = await reg.pushManager.getSubscription();

      if (!sub) {
        if (Notification.permission === 'denied') return;
        if (Notification.permission === 'default') {
          const perm = await Notification.requestPermission();
          if (perm !== 'granted') return;
        }
        sub = await reg.pushManager.subscribe({
          userVisibleOnly:      true,
          applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
        });
      }

      const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;
      if (!user?.id) return;

      await fetch('/campus/api/push-subscribe', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ user_id: user.id, subscription: sub.toJSON() }),
      });

    } catch (err) {
      // Silent fail — push is non-critical
    }
  }

  // Run after page fully loads, with a delay to not interrupt UX
  window.addEventListener('load', () => {
    const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;
    if (!user) return;
    setTimeout(subscribeToPush, 5000); // 5s delay
  });

})();