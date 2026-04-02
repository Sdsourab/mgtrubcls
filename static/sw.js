/**
 * UniSync Service Worker  —  sw.js
 * ─────────────────────────────────────────────────────────────
 * Cache Strategies:
 *   Static assets  →  Cache First  (CSS, JS, fonts)
 *   API calls      →  Network First + fallback cache
 *   HTML pages     →  Network First + fallback cache + offline page
 *
 * Features:
 *   • Background Sync  (queued offline actions auto-retry)
 *   • Push Notifications
 *   • Cache versioning  (old caches auto-deleted on activate)
 *   • Stale-While-Revalidate for non-critical API data
 * ─────────────────────────────────────────────────────────────
 */

const VERSION      = 'v3';
const STATIC_CACHE = `us-static-${VERSION}`;
const API_CACHE    = `us-api-${VERSION}`;
const PAGE_CACHE   = `us-pages-${VERSION}`;

// ── Assets to pre-cache at install time ────────────────────────
const PRECACHE_STATIC = [
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/js/live_engine.js',
  '/static/js/offline-sync.js',
  '/static/js/bg-animation.js',
  '/static/manifest.json',
];

const PRECACHE_PAGES = [
  '/dashboard',
  '/academic/routine',
  '/productivity/tasks',
  '/notices/',
  '/exams/',
];

// ── API routes to cache aggressively ──────────────────────────
const API_CACHE_PATTERNS = [
  '/academic/api/routine',
  '/academic/api/holiday-check',
  '/academic/api/mappings',
  '/productivity/api/tasks',
  '/notices/api/notices',
  '/exams/api/exams',
  '/exams/api/exams/upcoming',
  '/classmanagement/api/class-changes',
  '/auth/api/profile',
];

// ─────────────────────────────────────────────────────────────
// INSTALL
// ─────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    Promise.all([
      caches.open(STATIC_CACHE).then(cache =>
        cache.addAll(PRECACHE_STATIC.map(url =>
          new Request(url, { cache: 'reload' })
        ))
      ),
      caches.open(PAGE_CACHE).then(cache =>
        // Attempt to pre-cache pages — ignore failures (user may not be logged in)
        Promise.allSettled(
          PRECACHE_PAGES.map(url =>
            fetch(url).then(r => r.ok ? cache.put(url, r) : null).catch(() => null)
          )
        )
      ),
    ]).then(() => self.skipWaiting())
  );
});

// ─────────────────────────────────────────────────────────────
// ACTIVATE  — evict stale caches
// ─────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
  const keep = new Set([STATIC_CACHE, API_CACHE, PAGE_CACHE]);
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => !keep.has(k)).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ─────────────────────────────────────────────────────────────
// FETCH  — routing logic
// ─────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle same-origin GET requests
  if (request.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;

  // ── Static assets: Cache First ──────────────────────────────
  if (
    url.pathname.startsWith('/static/') ||
    url.pathname === '/static/manifest.json'
  ) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // ── API calls: Network First + cache fallback ───────────────
  const isApiRoute = API_CACHE_PATTERNS.some(p => url.pathname.startsWith(p));
  if (url.pathname.includes('/api/') || isApiRoute) {
    event.respondWith(networkFirstAPI(request));
    return;
  }

  // ── HTML pages: Network First + stale cache fallback ────────
  event.respondWith(networkFirstPage(request));
});

// ─────────────────────────────────────────────────────────────
// STRATEGY IMPLEMENTATIONS
// ─────────────────────────────────────────────────────────────

/** Cache First: serve from cache, fetch & update if missing */
async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Asset unavailable offline.', {
      status: 503,
      headers: { 'Content-Type': 'text/plain' },
    });
  }
}

/** Network First for API: try network, fall back to cache, return offline JSON */
async function networkFirstAPI(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) {
      // Tag the response so client knows it's stale
      const headers = new Headers(cached.headers);
      headers.set('X-Cache-Status', 'STALE');
      headers.set('X-Served-Offline', 'true');
      const body = await cached.clone().blob();
      return new Response(body, {
        status:  cached.status,
        headers,
      });
    }
    // Total fallback: structured offline response
    return new Response(
      JSON.stringify({
        success: false,
        offline: true,
        cached:  false,
        error:   'No internet connection and no cached data available.',
      }),
      {
        status:  503,
        headers: { 'Content-Type': 'application/json', 'X-Served-Offline': 'true' },
      }
    );
  }
}

/** Network First for pages: try network, fall back to cached page */
async function networkFirstPage(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(PAGE_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;

    // Try root cached page as shell fallback
    const shell = await caches.match('/dashboard');
    return shell || new Response(
      `<!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Offline — UniSync</title>
        <style>
          body{font-family:'Outfit',sans-serif;background:#FCF5E8;color:#2C1810;
               display:flex;flex-direction:column;align-items:center;
               justify-content:center;min-height:100vh;text-align:center;gap:16px;margin:0;padding:24px}
          h1{font-size:2rem;font-weight:800;color:#BC6F37}
          p{font-size:0.95rem;color:#6B5240;max-width:320px;line-height:1.6}
          a{color:#BC6F37;font-weight:600}
          .icon{font-size:3.5rem}
        </style>
      </head>
      <body>
        <div class="icon">📡</div>
        <h1>You're Offline</h1>
        <p>UniSync needs a connection to load this page for the first time.<br>
           Try going to <a href="/dashboard">Dashboard</a> which may be cached.</p>
        <button onclick="location.reload()"
          style="padding:12px 24px;background:#BC6F37;color:white;border:none;
                 border-radius:8px;font-weight:600;cursor:pointer;margin-top:8px;">
          Try Again
        </button>
      </body>
      </html>`,
      { status: 503, headers: { 'Content-Type': 'text/html' } }
    );
  }
}

// ─────────────────────────────────────────────────────────────
// BACKGROUND SYNC
// ─────────────────────────────────────────────────────────────
self.addEventListener('sync', event => {
  if (event.tag === 'sync-offline-actions') {
    event.waitUntil(triggerClientSync());
  }
});

async function triggerClientSync() {
  const clientList = await self.clients.matchAll({
    includeUncontrolled: true,
    type: 'window',
  });
  clientList.forEach(client => {
    client.postMessage({ type: 'SW_SYNC_NOW', source: 'background-sync' });
  });
}

// ─────────────────────────────────────────────────────────────
// PUSH NOTIFICATIONS
// ─────────────────────────────────────────────────────────────
self.addEventListener('push', event => {
  let data = {};
  try { data = event.data?.json() || {}; } catch { data = { title: 'UniSync', body: event.data?.text() }; }

  const TYPE_ICONS = {
    exam:         '📝',
    class_cancel: '❌',
    extra_class:  '📅',
    urgent:       '🚨',
    general:      '📢',
  };
  const icon = TYPE_ICONS[data.type] || '📢';

  const options = {
    body:    data.body    || 'You have a new update from UniSync.',
    icon:    '/static/icons/icon-192.png',
    badge:   '/static/icons/icon-192.png',
    vibrate: [100, 50, 200, 50, 100],
    tag:     data.tag     || `us-${data.type || 'general'}-${Date.now()}`,
    renotify: true,
    data:    {
      url:  data.url  || '/notices/',
      type: data.type || 'general',
    },
    actions: [
      { action: 'view',    title: 'View Now' },
      { action: 'dismiss', title: 'Dismiss'  },
    ],
  };

  event.waitUntil(
    self.registration.showNotification(`${icon} ${data.title || 'UniSync'}`, options)
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  if (event.action === 'dismiss') return;

  const targetUrl = event.notification.data?.url || '/dashboard';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      const existing = list.find(c => c.url.includes(self.location.origin));
      if (existing) {
        existing.navigate(targetUrl);
        return existing.focus();
      }
      return clients.openWindow(targetUrl);
    })
  );
});

// ─────────────────────────────────────────────────────────────
// SW UPDATE MESSAGE
// ─────────────────────────────────────────────────────────────
self.addEventListener('message', event => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});