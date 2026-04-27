/**
 * UniSync Service Worker — v4.1.0
 *
 * Caching strategy:
 *   Cache-First   → /static/ assets
 *   Network-First → API, auth, dynamic Flask routes
 *   Offline page  → /offline for navigation failures
 *
 * Push Notifications:
 *   • Displays notification with title, body, icon, badge
 *   • Click opens relevant URL (default: /notices/)
 *   • Action buttons: "View" and "Dismiss"
 *   • Works when app is CLOSED and SCREEN is OFF
 */

const CACHE_VERSION = 'v4.1.0';
const CACHE_NAME    = 'unisync-' + CACHE_VERSION;
const OFFLINE_URL   = '/offline';

const PRECACHE = [
  '/offline',
  '/manifest.json',
  '/static/css/style.css',
  '/static/css/modules/pwa.css',
  '/static/css/modules/scroll-animations.css',
  '/static/js/main.js',
  '/static/js/offline-sync.js',
];

// ── Install ──────────────────────────────────────────────────
self.addEventListener('install', function (event) {
  console.log('[SW] install ' + CACHE_VERSION);
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function (cache) {
        return Promise.allSettled(
          PRECACHE.map(function (url) {
            return cache.add(url).catch(function (err) {
              console.warn('[SW] precache miss:', url, err.message);
            });
          })
        );
      })
      .then(function () { return self.skipWaiting(); })
  );
});

// ── Activate ─────────────────────────────────────────────────
self.addEventListener('activate', function (event) {
  console.log('[SW] activate ' + CACHE_VERSION);
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(
          keys.filter(function (k) { return k !== CACHE_NAME; })
              .map(function (k) { return caches.delete(k); })
        );
      })
      .then(function () { return self.clients.claim(); })
  );
});

// ── Fetch ─────────────────────────────────────────────────────
self.addEventListener('fetch', function (event) {
  var req = event.request;
  if (req.method !== 'GET') return;
  if (!req.url.startsWith(self.location.origin)) return;

  var path = new URL(req.url).pathname;

  // Static assets → Cache First
  if (path.startsWith('/static/') || path === '/manifest.json') {
    event.respondWith(cacheFirst(req));
    return;
  }

  // Dynamic Flask routes → Network Only (never cache)
  var dynamicPrefixes = [
    '/api/', '/auth/', '/academic/', '/productivity/',
    '/campus/', '/admin/', '/guest/', '/planner/', '/notices/',
    '/classmanagement/', '/exams/', '/teachers/', '/push/',
    '/bus/', '/holidays/',
  ];
  if (dynamicPrefixes.some(function (p) { return path.startsWith(p); })) {
    event.respondWith(networkOnly(req));
    return;
  }

  // Navigation → Network First with offline fallback
  if (req.mode === 'navigate') {
    event.respondWith(networkWithOfflineFallback(req));
    return;
  }

  // Everything else → Network First
  event.respondWith(networkFirst(req));
});

// ── Caching strategies ────────────────────────────────────────
function cacheFirst(req) {
  return caches.match(req).then(function (cached) {
    if (cached) return cached;
    return fetch(req).then(function (res) {
      if (res && res.status === 200) {
        caches.open(CACHE_NAME).then(function (c) { c.put(req, res.clone()); });
      }
      return res;
    });
  });
}

function networkFirst(req) {
  return fetch(req).then(function (res) {
    if (res && res.status === 200) {
      caches.open(CACHE_NAME).then(function (c) { c.put(req, res.clone()); });
    }
    return res;
  }).catch(function () {
    return caches.match(req);
  });
}

function networkOnly(req) {
  return fetch(req);
}

function networkWithOfflineFallback(req) {
  return fetch(req).then(function (res) {
    if (res && res.status === 200) {
      caches.open(CACHE_NAME).then(function (c) { c.put(req, res.clone()); });
    }
    return res;
  }).catch(function () {
    return caches.match(req).then(function (cached) {
      if (cached) return cached;
      return caches.match(OFFLINE_URL).then(function (offline) {
        if (offline) return offline;
        return new Response(
          '<!DOCTYPE html><html><head><meta charset="UTF-8">'
          + '<meta name="viewport" content="width=device-width,initial-scale=1">'
          + '<title>UniSync — Offline</title>'
          + '<style>body{font-family:Georgia,serif;background:#FAF5E9;color:#3C2A21;'
          + 'display:flex;align-items:center;justify-content:center;min-height:100vh;'
          + 'margin:0;text-align:center;padding:2rem;}'
          + 'h1{font-size:1.5rem}p{color:#7a6050}'
          + 'button{margin-top:1.5rem;padding:.75rem 2rem;background:#BC6F37;'
          + 'color:#fff;border:none;border-radius:10px;cursor:pointer;font-size:1rem;}'
          + '</style></head><body><div>'
          + '<h1>📚 আপনি offline আছেন</h1>'
          + '<p>UniSync কানেক্ট করতে পারছে না।<br>নেটওয়ার্ক চেক করুন।</p>'
          + '<button onclick="location.reload()">Retry</button>'
          + '</div></body></html>',
          { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
        );
      });
    });
  });
}

// ── Background Sync ───────────────────────────────────────────
self.addEventListener('sync', function (event) {
  if (event.tag === 'sync-pending-tasks' || event.tag === 'sync-attendance') {
    event.waitUntil(
      self.clients.matchAll({ type: 'window' }).then(function (clients) {
        clients.forEach(function (c) {
          c.postMessage({ type: 'SW_SYNC', tag: event.tag });
        });
      })
    );
  }
});

// ── Push Notifications ────────────────────────────────────────
// This fires even when the app is CLOSED or the SCREEN is OFF.
// Payload sent from core/push.py via pywebpush → VAPID.
self.addEventListener('push', function (event) {
  if (!event.data) return;

  var payload;
  try {
    payload = event.data.json();
  } catch (e) {
    payload = { title: 'UniSync', body: event.data.text(), url: '/notices/' };
  }

  var title = payload.title  || 'UniSync';
  var body  = payload.body   || 'নতুন আপডেট আছে।';
  var url   = payload.url    || '/notices/';
  var icon  = payload.icon   || '/static/icons/icon-192x192.png';
  var badge = payload.badge  || '/static/icons/badge-72x72.png';
  var tag   = payload.tag    || ('unisync-' + Date.now());

  var options = {
    body:               body,
    icon:               icon,
    badge:              badge,
    tag:                tag,
    data:               { url: url, notice_id: payload.notice_id || '' },
    vibrate:            [180, 80, 180, 80, 180],
    renotify:           true,
    requireInteraction: false,
    actions: [
      { action: 'view',    title: '👁 View' },
      { action: 'dismiss', title: '✕ Dismiss' },
    ],
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// ── Notification Click ────────────────────────────────────────
self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  if (event.action === 'dismiss') return;

  var targetUrl = (event.notification.data && event.notification.data.url)
    ? event.notification.data.url
    : '/notices/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(function (clients) {
        for (var i = 0; i < clients.length; i++) {
          var c = clients[i];
          if ('focus' in c) {
            c.focus();
            if ('navigate' in c) c.navigate(targetUrl);
            return;
          }
        }
        if (self.clients.openWindow) {
          return self.clients.openWindow(targetUrl);
        }
      })
  );
});

// ── Push subscription change ──────────────────────────────────
self.addEventListener('pushsubscriptionchange', function (event) {
  event.waitUntil(
    self.registration.pushManager.subscribe(event.oldSubscription.options)
      .then(function (newSub) {
        return self.clients.matchAll({ type: 'window' }).then(function (clients) {
          clients.forEach(function (c) {
            c.postMessage({
              type:         'PUSH_SUBSCRIPTION_CHANGED',
              subscription: newSub.toJSON(),
            });
          });
        });
      })
      .catch(function (err) {
        console.warn('[SW] pushsubscriptionchange resubscribe failed:', err);
      })
  );
});

// ── Message Handler ───────────────────────────────────────────
self.addEventListener('message', function (event) {
  var data = event.data || {};
  if (data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (data.type === 'CLEAR_CACHE') {
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.map(function (k) { return caches.delete(k); }));
      })
      .then(function () {
        if (event.source) event.source.postMessage({ type: 'CACHE_CLEARED' });
      });
  }
});