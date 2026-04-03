/**
 * UniSync — Offline Sync Engine
 * IndexedDB queue for offline actions. Auto-syncs on reconnect.
 * Safe to load before DOM — all IDB ops are async.
 */

const OfflineSync = (() => {
  'use strict';

  const DB_NAME = 'us-offline-db', DB_VER = 2, STORE = 'queue';
  let _db = null;

  /* ── Open DB ────────────────────────────────────────────── */
  function _open() {
    if (_db) return Promise.resolve(_db);
    return new Promise((res, rej) => {
      const r = indexedDB.open(DB_NAME, DB_VER);
      r.onupgradeneeded = e => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE)) {
          const s = db.createObjectStore(STORE, { keyPath: 'local_id' });
          s.createIndex('status', 'status', { unique: false });
        }
      };
      r.onsuccess = e => { _db = e.target.result; res(_db); };
      r.onerror   = e => rej(e.target.error);
    });
  }

  function _op(req) {
    return new Promise((res, rej) => {
      req.onsuccess = e => res(e.target.result);
      req.onerror   = e => rej(e.target.error);
    });
  }

  /* ── Public: queue an action ───────────────────────────── */
  async function queue(type, payload) {
    await _open();
    const action = {
      local_id:   `${type}-${Date.now()}-${Math.random().toString(36).slice(2,7)}`,
      type, payload,
      status:     'pending',
      created_at: new Date().toISOString(),
      retries:    0,
    };
    await _op(_db.transaction(STORE,'readwrite').objectStore(STORE).add(action));
    _badge();
    /* Register background sync */
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.ready
        .then(r => r.sync?.register('sync-offline-actions'))
        .catch(() => {});
    }
    return action;
  }

  /* ── Public: get pending ───────────────────────────────── */
  async function getPending() {
    await _open();
    return new Promise((res, rej) => {
      const r = _db.transaction(STORE,'readonly')
                   .objectStore(STORE)
                   .index('status')
                   .getAll('pending');
      r.onsuccess = e => res(e.target.result || []);
      r.onerror   = e => rej(e.target.error);
    });
  }

  async function getAll() {
    await _open();
    return _op(_db.transaction(STORE,'readonly').objectStore(STORE).getAll());
  }

  async function markSynced(local_id) {
    await _open();
    const s = _db.transaction(STORE,'readwrite').objectStore(STORE);
    const r = await _op(s.get(local_id));
    if (r) { r.status = 'synced'; r.synced_at = new Date().toISOString(); await _op(s.put(r)); }
  }

  async function markFailed(local_id, err) {
    await _open();
    const s = _db.transaction(STORE,'readwrite').objectStore(STORE);
    const r = await _op(s.get(local_id));
    if (r) {
      r.retries++;
      r.status     = r.retries >= 3 ? 'failed' : 'pending';
      r.last_error = err;
      await _op(s.put(r));
    }
  }

  /* ── Sync ──────────────────────────────────────────────── */
  let _syncing = false;

  async function syncNow() {
    if (_syncing || !navigator.onLine) return { synced: 0, failed: 0 };
    _syncing = true;

    const pending = await getPending();
    if (!pending.length) { _syncing = false; return { synced: 0, failed: 0 }; }

    let user;
    try { user = JSON.parse(localStorage.getItem('us_user')); } catch {}
    if (!user?.id) { _syncing = false; return { synced: 0, failed: pending.length }; }

    const ENDPOINTS = {
      'create_notice': { url: '/notices/api/notices/sync',             key: 'drafts'  },
      'cancel_class':  { url: '/classmanagement/api/class-changes/sync', key: 'actions' },
      'extra_class':   { url: '/classmanagement/api/class-changes/sync', key: 'actions' },
      'create_exam':   { url: '/exams/api/exams/sync',                  key: 'exams'   },
    };

    const groups = {};
    for (const a of pending) {
      const ep = ENDPOINTS[a.type];
      if (!ep) continue;
      groups[a.type] = groups[a.type] || { ...ep, actions: [] };
      groups[a.type].actions.push(a);
    }

    let total = 0, failed = 0;

    for (const { url, key, actions } of Object.values(groups)) {
      try {
        const resp = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: user.id,
            [key]: actions.map(a => ({ ...a.payload, local_id: a.local_id })),
          }),
        });
        if (resp.ok) {
          const result = await resp.json();
          for (const id of (result.synced || [])) { await markSynced(id); total++; }
          for (const f  of (result.failed || [])) { await markFailed(f.local_id, f.error); failed++; }
        } else {
          for (const a of actions) { await markFailed(a.local_id, `HTTP ${resp.status}`); failed++; }
        }
      } catch (e) {
        for (const a of actions) { await markFailed(a.local_id, e.message); failed++; }
      }
    }

    _badge();
    _syncing = false;

    if (total > 0 && typeof UniSync !== 'undefined' && UniSync.toast) {
      UniSync.toast(`✅ ${total} offline action${total!==1?'s':''} synced`, 'success', 4000);
    }
    return { synced: total, failed };
  }

  /* ── Badge ─────────────────────────────────────────────── */
  async function _badge() {
    try {
      const p = await getPending();
      const n = p.length;
      const b = document.getElementById('offlineQueueBadge');
      if (b) b.textContent = n > 0 ? n : '';
      const bar = document.getElementById('offlineBar');
      if (bar) bar.classList.toggle('has-queue', n > 0);
    } catch {}
  }

  /* ── Online / offline ──────────────────────────────────── */
  window.addEventListener('online', () => {
    document.body.classList.remove('is-offline');
    const lbl = document.getElementById('offlineBarLabel');
    if (lbl) lbl.textContent = 'Syncing…';
    setTimeout(syncNow, 1500);
  });
  window.addEventListener('offline', () => {
    document.body.classList.add('is-offline');
    const lbl = document.getElementById('offlineBarLabel');
    if (lbl) lbl.textContent = 'Offline Mode';
  });

  /* SW message trigger */
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', e => {
      if (e.data?.type === 'SW_SYNC_NOW') syncNow();
    });
  }

  /* Periodic sync every 3 min */
  setInterval(() => { if (navigator.onLine) syncNow(); }, 3 * 60 * 1000);

  /* Init state */
  if (!navigator.onLine) document.body.classList.add('is-offline');
  document.addEventListener('DOMContentLoaded', _badge);

  return { queue, syncNow, getPending, getAll, markSynced };
})();