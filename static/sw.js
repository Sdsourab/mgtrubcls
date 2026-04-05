/**
 * UniSync Service Worker — v3.0.0
 *
 * Mechanism adapted from Sdsourab/oclock:
 *   - Registered via absolute URL: new URL('sw.js', document.baseURI).href
 *   - Registered on window 'load' event (not DOMContentLoaded)
 *   - No scope option passed — browser infers '/' from SW file location
 *
 * Strategy:
 *   Cache-First  → /static/ assets
 *   Network-First → API, auth, dynamic Flask routes
 *   Offline page → /offline for navigation failures
 */

const CACHE_NAME  = 'unisync-v3.0.0';
const OFFLINE_URL = '/offline';

// Only pre-cache what we KNOW exists and will return 200.
// /offline is now a real registered Flask route — safe to cache.
// manifest is at /manifest.json (Flask route), NOT /static/manifest.json.
const PRECACHE = [
  '/offline',
  '/manifest.json',
  '/static/css/style.css',
  '/static/css/modules/pwa.css',
  '/static/css/modules/scroll-animations.css',
  '/static/js/main.js',
  '/static/js/offline-sync.js',
];

// ── Install ─────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  console.log('[SW] install v3.0.0');

  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache =>
        // allSettled: a 404 on one item doesn't abort the whole install
        Promise.allSettled(
          PRECACHE.map(url =>
            cache.add(url).catch(err =>
              console.warn('[SW] precache miss:', url, err.message)
            )
          )
        )
      )
      .then(() => self.skipWaiting())
  );
});

// ── Activate ─────────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
  console.log('[SW] activate v3.0.0');
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  if (!req.url.startsWith(self.location.origin)) return;

  const path = new URL(req.url).pathname;

  // Static assets → Cache First
  if (path.startsWith('/static/') || path.endsWith('.webmanifest') || path === '/manifest.json') {
    event.respondWith(cacheFirst(req));
    return;
  }

  // API / dynamic Flask routes → Network First (no caching)
  const dynamicPrefixes = ['/api/', '/auth/', '/academic/', '/productivity/',
    '/campus/', '/admin/', '/guest/', '/planner/', '/notices/',
    '/classmanagement/', '/exams/'];
  if (dynamicPrefixes.some(p => path.startsWith(p))) {
    event.respondWith(networkOnly(req));
    return;
  }

  // Navigation (HTML pages) → Network First with offline fallback
  if (req.mode === 'navigate') {
    event.respondWith(networkWithOfflineFallback(req));
    return;
  }

  // Everything else → Network First
  event.respondWith(networkFirst(req));
});

// ── Strategies ───────────────────────────────────────────────────────────────

async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (res && res.status === 200) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(req, res.clone());
    }
    return res;
  } catch (e) {
    throw e;
  }
}

async function networkFirst(req) {
  try {
    const res = await fetch(req);
    if (res && res.status === 200) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(req, res.clone());
    }
    return res;
  } catch {
    return caches.match(req);
  }
}

async function networkOnly(req) {
  // Never cache API calls — always live data
  return fetch(req);
}

async function networkWithOfflineFallback(req) {
  try {
    const res = await fetch(req);
    if (res && res.status === 200) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(req, res.clone());
    }
    return res;
  } catch {
    // Try cache first
    const cached = await caches.match(req);
    if (cached) return cached;

    // Serve the pre-cached offline page
    const offline = await caches.match(OFFLINE_URL);
    if (offline) return offline;

    // Last resort inline fallback
    return new Response(
      `<!DOCTYPE html><html><head><meta charset="UTF-8">
       <meta name="viewport" content="width=device-width,initial-scale=1">
       <title>UniSync — Offline</title>
       <style>body{font-family:Georgia,serif;background:#FCF5E8;color:#3C2A21;
       display:flex;align-items:center;justify-content:center;min-height:100vh;
       margin:0;text-align:center;padding:2rem;}
       button{margin-top:1.5rem;padding:.75rem 2rem;background:#3C2A21;
       color:#FCF5E8;border:none;border-radius:8px;cursor:pointer;font-size:1rem;}
       </style></head><body><div>
       <h1>📚 You're offline</h1>
       <p>UniSync কানেক্ট করতে পারছে না। নেটওয়ার্ক চেক করুন।</p>
       <button onclick="location.reload()">Retry</button>
       </div></body></html>`,
      { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
}

// ── Background Sync ───────────────────────────────────────────────────────────
self.addEventListener('sync', event => {
  if (event.tag === 'sync-pending-tasks' || event.tag === 'sync-attendance') {
    event.waitUntil(
      self.clients.matchAll({ type: 'window' }).then(clients =>
        clients.forEach(c => c.postMessage({ type: 'SW_SYNC', tag: event.tag }))
      )
    );
  }
});

// ── Push Notifications ────────────────────────────────────────────────────────
self.addEventListener('push', event => {
  if (!event.data) return;
  let payload;
  try { payload = event.data.json(); }
  catch { payload = { title: 'UniSync', body: event.data.text() }; }

  event.waitUntil(
    self.registration.showNotification(payload.title || 'UniSync', {
      body:    payload.body || 'New notification.',
      icon:    '/static/icons/icon-192x192.png',
      badge:   '/static/icons/badge-72x72.png',
      data:    payload.data || { url: '/dashboard' },
      vibrate: [200, 100, 200],
      tag:     payload.tag || 'unisync',
      renotify: true,
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  if (event.action === 'dismiss') return;
  const url = (event.notification.data && event.notification.data.url) || '/dashboard';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
      for (const c of clients) {
        if (c.url === url && 'focus' in c) return c.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});

// ── Message Handler ───────────────────────────────────────────────────────────
self.addEventListener('message', event => {
  const { type, payload } = event.data || {};
  if (type === 'SKIP_WAITING') self.skipWaiting();
  if (type === 'CLEAR_CACHE') {
    caches.keys()
      .then(keys => Promise.all(keys.map(k => caches.delete(k))))
      .then(() => event.source?.postMessage({ type: 'CACHE_CLEARED' }));
  }
});