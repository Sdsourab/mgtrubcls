/**
 * UniSync Service Worker — v2.1.0
 * Strategy:
 *   • Cache-First  → static assets (CSS, JS, fonts, images)
 *   • Network-First → API routes, dynamic Flask blueprints
 *   • Offline fallback → /offline for navigation failures
 *
 * Scope: / (granted via Service-Worker-Allowed header in Flask + vercel.json)
 *
 * FIX v2.1.0:
 *   - Changed /static/manifest.json → /manifest.json in STATIC_PRECACHE
 *     (manifest is served at root via Flask route, not from /static/)
 */

// ─── Cache Configuration ────────────────────────────────────────────────────
const CACHE_VERSION   = 'v2.1.0';
const STATIC_CACHE    = `unisync-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE   = `unisync-dynamic-${CACHE_VERSION}`;
const OFFLINE_URL     = '/offline';

/**
 * Static assets pre-cached on install.
 * Update CACHE_VERSION whenever these files change to bust the cache.
 *
 * FIX: manifest lives at /manifest.json (Flask route), NOT /static/manifest.json
 */
const STATIC_PRECACHE = [
  '/',
  '/offline',
  '/static/css/style.css',
  '/static/css/modules/auth.css',
  '/static/css/modules/pwa.css',
  '/static/css/modules/scroll-animations.css',
  '/static/js/main.js',
  '/static/js/bg-animation.js',
  '/static/js/live_engine.js',
  '/static/js/offline-sync.js',
  '/manifest.json',   // ← FIXED: was /static/manifest.json (404)
];

/** URL prefixes that should NEVER be cached (always network-first) */
const API_PREFIXES = [
  '/api/',
  '/auth/',
  '/academic/',
  '/productivity/',
  '/campus/',
  '/admin/',
  '/guest/',
  '/planner/',
  '/notices/',
  '/classmanagement/',
  '/exams/',
];

/** File extensions that are always static and safe to cache-first */
const STATIC_EXTENSIONS = ['.css', '.js', '.woff', '.woff2', '.ttf', '.ico', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function isApiRequest(url) {
  const path = new URL(url).pathname;
  return API_PREFIXES.some(prefix => path.startsWith(prefix));
}

function isStaticAsset(url) {
  const path = new URL(url).pathname;
  // Explicit /static/ path OR known file extension
  if (path.startsWith('/static/')) return true;
  return STATIC_EXTENSIONS.some(ext => path.endsWith(ext));
}

function isNavigationRequest(request) {
  return request.mode === 'navigate';
}

// ─── Install ─────────────────────────────────────────────────────────────────

self.addEventListener('install', event => {
  console.log(`[SW] Installing ${CACHE_VERSION}`);

  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => {
      // allSettled: if one URL fails (404), others still cache — SW still installs
      return Promise.allSettled(
        STATIC_PRECACHE.map(url =>
          cache.add(url).catch(err =>
            console.warn(`[SW] Pre-cache failed for ${url}:`, err)
          )
        )
      );
    }).then(() => {
      console.log('[SW] Pre-cache complete');
      return self.skipWaiting();
    })
  );
});

// ─── Activate ────────────────────────────────────────────────────────────────

self.addEventListener('activate', event => {
  console.log(`[SW] Activating ${CACHE_VERSION}`);

  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys
          .filter(key => key !== STATIC_CACHE && key !== DYNAMIC_CACHE)
          .map(key => {
            console.log(`[SW] Deleting old cache: ${key}`);
            return caches.delete(key);
          })
      );
    }).then(() => {
      console.log('[SW] Old caches cleared. Claiming clients.');
      return self.clients.claim();
    })
  );
});

// ─── Fetch ───────────────────────────────────────────────────────────────────

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = request.url;

  // Skip non-GET requests and cross-origin requests
  if (request.method !== 'GET') return;
  if (!url.startsWith(self.location.origin)) return;

  // ── 1. Static Assets → Cache First ────────────────────────────────────────
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // ── 2. API / Blueprint Routes → Network First ──────────────────────────────
  if (isApiRequest(url)) {
    event.respondWith(networkFirst(request));
    return;
  }

  // ── 3. Navigation (HTML pages) → Network First with Offline Fallback ───────
  if (isNavigationRequest(request)) {
    event.respondWith(networkFirstWithOfflineFallback(request));
    return;
  }

  // ── 4. Everything else → Network First ────────────────────────────────────
  event.respondWith(networkFirst(request));
});

// ─── Strategy: Cache First ────────────────────────────────────────────────────
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.error('[SW] Cache-first network error:', error);
    throw error;
  }
}

// ─── Strategy: Network First ──────────────────────────────────────────────────
async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) {
      console.warn('[SW] Network failed, serving from cache:', request.url);
      return cached;
    }
    throw error;
  }
}

// ─── Strategy: Network First + Offline Fallback ───────────────────────────────
async function networkFirstWithOfflineFallback(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) {
      console.warn('[SW] Serving cached page:', request.url);
      return cached;
    }

    console.warn('[SW] Offline fallback triggered for:', request.url);
    const offlinePage = await caches.match(OFFLINE_URL);
    if (offlinePage) return offlinePage;

    return new Response(
      `<!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>UniSync — Offline</title>
        <style>
          body { font-family: Georgia, serif; background: #FCF5E8; color: #3C2A21;
                 display: flex; align-items: center; justify-content: center;
                 min-height: 100vh; margin: 0; text-align: center; padding: 2rem; }
          h1 { font-size: 2rem; margin-bottom: 0.5rem; }
          p  { color: #7C5C4B; }
          button { margin-top: 1.5rem; padding: 0.75rem 2rem; background: #3C2A21;
                   color: #FCF5E8; border: none; border-radius: 8px; cursor: pointer;
                   font-size: 1rem; }
        </style>
      </head>
      <body>
        <div>
          <h1>📚 You're offline</h1>
          <p>UniSync couldn't connect. Check your network and try again.</p>
          <button onclick="location.reload()">Retry</button>
        </div>
      </body>
      </html>`,
      { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
}

// ─── Background Sync ──────────────────────────────────────────────────────────
self.addEventListener('sync', event => {
  console.log('[SW] Background sync event:', event.tag);

  if (event.tag === 'sync-pending-tasks') {
    event.waitUntil(syncPendingTasks());
  }
  if (event.tag === 'sync-attendance') {
    event.waitUntil(syncPendingRequests('attendance'));
  }
});

async function syncPendingTasks() {
  try {
    const clients = await self.clients.matchAll({ type: 'window' });
    clients.forEach(client =>
      client.postMessage({ type: 'SW_SYNC', tag: 'sync-pending-tasks' })
    );
  } catch (err) {
    console.error('[SW] Background sync failed:', err);
    throw err;
  }
}

async function syncPendingRequests(tag) {
  const clients = await self.clients.matchAll({ type: 'window' });
  clients.forEach(client =>
    client.postMessage({ type: 'SW_SYNC', tag })
  );
}

// ─── Push Notifications ───────────────────────────────────────────────────────
self.addEventListener('push', event => {
  if (!event.data) return;

  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: 'UniSync', body: event.data.text() };
  }

  const options = {
    body:    payload.body    || 'You have a new notification.',
    icon:    payload.icon    || '/static/icons/icon-192x192.png',
    badge:   payload.badge   || '/static/icons/badge-72x72.png',
    data:    payload.data    || { url: '/' },
    actions: payload.actions || [
      { action: 'open',    title: 'Open UniSync' },
      { action: 'dismiss', title: 'Dismiss' },
    ],
    vibrate: [200, 100, 200],
    tag:     payload.tag || 'unisync-notification',
    renotify: true,
  };

  event.waitUntil(
    self.registration.showNotification(payload.title || 'UniSync', options)
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();

  if (event.action === 'dismiss') return;

  const targetUrl = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(clients => {
        for (const client of clients) {
          if (client.url === targetUrl && 'focus' in client) {
            return client.focus();
          }
        }
        if (self.clients.openWindow) {
          return self.clients.openWindow(targetUrl);
        }
      })
  );
});

// ─── Message Handler ──────────────────────────────────────────────────────────
self.addEventListener('message', event => {
  const { type, payload } = event.data || {};

  if (type === 'SKIP_WAITING') {
    console.log('[SW] SKIP_WAITING received — activating now');
    self.skipWaiting();
  }

  if (type === 'CACHE_URLS' && Array.isArray(payload)) {
    event.waitUntil(
      caches.open(DYNAMIC_CACHE).then(cache => cache.addAll(payload))
    );
  }

  if (type === 'CLEAR_CACHE') {
    event.waitUntil(
      caches.keys().then(keys =>
        Promise.all(keys.map(key => caches.delete(key)))
      ).then(() => {
        event.source && event.source.postMessage({ type: 'CACHE_CLEARED' });
      })
    );
  }
});