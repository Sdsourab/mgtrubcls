/**
 * UniSync Service Worker v4.2
 *
 * KEY CHANGES:
 *  - Push event handler: fires even when app is CLOSED / screen OFF
 *  - /bus/ and /holidays/ added to dynamic (network-only) prefixes
 *  - notificationclick routes user to the correct URL
 */

const CACHE_VERSION = 'v4.2';
const CACHE_NAME    = 'unisync-' + CACHE_VERSION;
const OFFLINE_URL   = '/offline';

const PRECACHE = [
  '/offline',
  '/manifest.json',
  '/static/css/style.css',
  '/static/js/main.js',
];

// ── Install ─────────────────────────────────────────────────────
self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return Promise.allSettled(
        PRECACHE.map(function (url) {
          return cache.add(url).catch(function () {});
        })
      );
    }).then(function () { return self.skipWaiting(); })
  );
});

// ── Activate ─────────────────────────────────────────────────────
self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE_NAME; })
            .map(function (k)   { return caches.delete(k); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

// ── Fetch ─────────────────────────────────────────────────────────
var NETWORK_ONLY_PREFIXES = [
  '/api/', '/auth/', '/academic/', '/productivity/',
  '/campus/', '/admin/', '/guest/', '/planner/', '/notices/',
  '/classmanagement/', '/exams/', '/teachers/', '/push/',
  '/bus/', '/holidays/',
];

self.addEventListener('fetch', function (e) {
  var req  = e.request;
  var path = new URL(req.url).pathname;

  if (req.method !== 'GET') return;
  if (!req.url.startsWith(self.location.origin)) return;

  // Static assets → Cache First
  if (path.startsWith('/static/') || path === '/manifest.json') {
    e.respondWith(cacheFirst(req)); return;
  }

  // Dynamic routes → Network Only
  if (NETWORK_ONLY_PREFIXES.some(function (p) { return path.startsWith(p); })) {
    e.respondWith(fetch(req)); return;
  }

  // Navigation → Network with offline fallback
  if (req.mode === 'navigate') {
    e.respondWith(networkWithOffline(req)); return;
  }

  e.respondWith(networkFirst(req));
});

function cacheFirst(req) {
  return caches.match(req).then(function (c) {
    if (c) return c;
    return fetch(req).then(function (res) {
      if (res && res.status === 200)
        caches.open(CACHE_NAME).then(function (cache) { cache.put(req, res.clone()); });
      return res;
    });
  });
}

function networkFirst(req) {
  return fetch(req).then(function (res) {
    if (res && res.status === 200)
      caches.open(CACHE_NAME).then(function (cache) { cache.put(req, res.clone()); });
    return res;
  }).catch(function () { return caches.match(req); });
}

function networkWithOffline(req) {
  return fetch(req).then(function (res) {
    if (res && res.status === 200)
      caches.open(CACHE_NAME).then(function (cache) { cache.put(req, res.clone()); });
    return res;
  }).catch(function () {
    return caches.match(req).then(function (cached) {
      if (cached) return cached;
      return caches.match(OFFLINE_URL).then(function (offline) {
        if (offline) return offline;
        return new Response(
          '<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:3rem">'
          + '<h2>📚 Offline</h2><p>Network reconnect করুন।</p>'
          + '<button onclick="location.reload()">Retry</button></body></html>',
          { headers: { 'Content-Type': 'text/html;charset=utf-8' } }
        );
      });
    });
  });
}

// ── Background Sync ───────────────────────────────────────────────
self.addEventListener('sync', function (e) {
  if (e.tag === 'sync-pending-tasks' || e.tag === 'sync-attendance') {
    e.waitUntil(
      self.clients.matchAll({ type: 'window' }).then(function (clients) {
        clients.forEach(function (c) { c.postMessage({ type: 'SW_SYNC', tag: e.tag }); });
      })
    );
  }
});

// ── Push Notification ─────────────────────────────────────────────
// Fires even when the app is CLOSED and the screen is OFF.
// Server triggers this via core/push.py → pywebpush → VAPID.
self.addEventListener('push', function (e) {
  if (!e.data) return;

  var payload;
  try   { payload = e.data.json(); }
  catch { payload = { title: 'UniSync', body: e.data.text(), url: '/notices/' }; }

  var title = payload.title  || 'UniSync';
  var body  = payload.body   || 'নতুন আপডেট আছে।';
  var url   = payload.url    || '/notices/';
  var icon  = payload.icon   || '/static/icons/icon-192x192.png';
  var badge = payload.badge  || '/static/icons/badge-72x72.png';
  var tag   = payload.tag    || 'unisync-' + Date.now();

  e.waitUntil(
    self.registration.showNotification(title, {
      body:               body,
      icon:               icon,
      badge:              badge,
      tag:                tag,
      data:               { url: url, notice_id: payload.notice_id || '' },
      vibrate:            [200, 80, 200],
      renotify:           true,
      requireInteraction: false,
      actions: [
        { action: 'view',    title: '👁 View' },
        { action: 'dismiss', title: '✕ OK' },
      ],
    })
  );
});

// ── Notification click ────────────────────────────────────────────
self.addEventListener('notificationclick', function (e) {
  e.notification.close();
  if (e.action === 'dismiss') return;

  var target = (e.notification.data && e.notification.data.url)
    ? e.notification.data.url : '/notices/';

  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(function (clients) {
        for (var i = 0; i < clients.length; i++) {
          var c = clients[i];
          if ('focus' in c) {
            c.focus();
            if ('navigate' in c) c.navigate(target);
            return;
          }
        }
        if (self.clients.openWindow) return self.clients.openWindow(target);
      })
  );
});

// ── Push subscription change ──────────────────────────────────────
self.addEventListener('pushsubscriptionchange', function (e) {
  e.waitUntil(
    self.registration.pushManager.subscribe(e.oldSubscription.options)
      .then(function (newSub) {
        return self.clients.matchAll({ type: 'window' }).then(function (clients) {
          clients.forEach(function (c) {
            c.postMessage({ type: 'PUSH_SUBSCRIPTION_CHANGED', subscription: newSub.toJSON() });
          });
        });
      }).catch(function () {})
  );
});

// ── Message ───────────────────────────────────────────────────────
self.addEventListener('message', function (e) {
  if (!e.data) return;
  if (e.data.type === 'SKIP_WAITING') self.skipWaiting();
  if (e.data.type === 'CLEAR_CACHE') {
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) { return caches.delete(k); }));
    }).then(function () {
      if (e.source) e.source.postMessage({ type: 'CACHE_CLEARED' });
    });
  }
});