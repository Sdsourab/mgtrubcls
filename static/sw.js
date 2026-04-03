/**
 * UniSync Service Worker  v4
 * Cache strategies:
 *   /static/**  →  Cache First
 *   /api/**     →  Network First + cache fallback
 *   pages       →  Network First + cache fallback
 *
 * IMPORTANT: does NOT pre-cache auth-gated pages at install
 * (they redirect to login and can't be cached without credentials)
 */

const VER          = 'v4';
const STATIC_CACHE = `us-static-${VER}`;
const API_CACHE    = `us-api-${VER}`;
const PAGE_CACHE   = `us-pages-${VER}`;

/* Only pre-cache pure static assets — no HTML pages */
const PRECACHE = [
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/js/live_engine.js',
  '/static/js/offline-sync.js',
  '/static/manifest.json',
];

/* ── Install ────────────────────────────────────────────────── */
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => Promise.allSettled(
        PRECACHE.map(url =>
          fetch(url, { cache: 'reload' })
            .then(r => r.ok ? cache.put(url, r) : null)
            .catch(() => null)
        )
      ))
      .then(() => self.skipWaiting())
  );
});

/* ── Activate: delete old caches ────────────────────────────── */
self.addEventListener('activate', event => {
  const keep = new Set([STATIC_CACHE, API_CACHE, PAGE_CACHE]);
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => !keep.has(k)).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

/* ── Fetch routing ──────────────────────────────────────────── */
self.addEventListener('fetch', event => {
  const req = event.request;
  const url = new URL(req.url);

  if (req.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;

  /* Static assets → Cache First */
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(req, STATIC_CACHE));
    return;
  }

  /* API routes → Network First + API cache */
  if (url.pathname.includes('/api/')) {
    event.respondWith(networkFirstAPI(req));
    return;
  }

  /* HTML pages → Network First + page cache */
  event.respondWith(networkFirstPage(req));
});

async function cacheFirst(req, cacheName) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      const c = await caches.open(cacheName);
      c.put(req, resp.clone());
    }
    return resp;
  } catch {
    return new Response('Asset unavailable.', { status: 503 });
  }
}

async function networkFirstAPI(req) {
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      const c = await caches.open(API_CACHE);
      c.put(req, resp.clone());
    }
    return resp;
  } catch {
    const cached = await caches.match(req);
    if (cached) {
      const h = new Headers(cached.headers);
      h.set('X-Served-Offline', 'true');
      const body = await cached.clone().blob();
      return new Response(body, { status: cached.status, headers: h });
    }
    return new Response(
      JSON.stringify({ success: false, offline: true, error: 'You are offline' }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

async function networkFirstPage(req) {
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      const c = await caches.open(PAGE_CACHE);
      c.put(req, resp.clone());
    }
    return resp;
  } catch {
    const cached = await caches.match(req);
    return cached || new Response(
      `<!DOCTYPE html><html><head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Offline — UniSync</title>
        <style>
          body{font-family:sans-serif;background:#FCF5E8;display:flex;flex-direction:column;
               align-items:center;justify-content:center;min-height:100vh;text-align:center;
               gap:16px;padding:24px;margin:0;color:#2C1810}
          h1{color:#BC6F37;font-size:1.8rem}
          p{color:#6B5240;max-width:300px;line-height:1.6}
          button{padding:12px 28px;background:#BC6F37;color:#fff;border:none;
                 border-radius:8px;font-size:1rem;cursor:pointer}
        </style>
      </head><body>
        <div style="font-size:3rem">📡</div>
        <h1>You're Offline</h1>
        <p>UniSync needs internet to load this page. Please reconnect and try again.</p>
        <button onclick="location.reload()">Try Again</button>
      </body></html>`,
      { status: 503, headers: { 'Content-Type': 'text/html' } }
    );
  }
}

/* ── Background Sync ────────────────────────────────────────── */
self.addEventListener('sync', event => {
  if (event.tag === 'sync-offline-actions') {
    event.waitUntil(
      self.clients.matchAll({ includeUncontrolled: true, type: 'window' })
        .then(clients => clients.forEach(c => c.postMessage({ type: 'SW_SYNC_NOW' })))
    );
  }
});

/* ── Push Notifications ─────────────────────────────────────── */
self.addEventListener('push', event => {
  let data = {};
  try { data = event.data?.json() || {}; } catch {}
  const icons = { exam:'📝', class_cancel:'❌', extra_class:'📅', urgent:'🚨', general:'📢' };
  const icon  = icons[data.type] || '📢';
  event.waitUntil(
    self.registration.showNotification(`${icon} ${data.title || 'UniSync'}`, {
      body:    data.body || 'New update from UniSync',
      icon:    '/static/icons/icon-192.png',
      badge:   '/static/icons/icon-192.png',
      vibrate: [100, 50, 200],
      tag:     data.tag || 'us-notif',
      data:    { url: data.url || '/dashboard' },
      actions: [{ action: 'view', title: 'View' }, { action: 'dismiss', title: 'Dismiss' }],
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  if (event.action === 'dismiss') return;
  const url = event.notification.data?.url || '/dashboard';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      const w = list.find(c => c.url.includes(self.location.origin));
      if (w) { w.navigate(url); return w.focus(); }
      return clients.openWindow(url);
    })
  );
});

/* SW update message from page */
self.addEventListener('message', event => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
});