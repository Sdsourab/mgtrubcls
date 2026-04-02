/**
 * UniSync — Offline Sync Engine  (offline-sync.js)
 * ─────────────────────────────────────────────────────────────
 * Queues any action taken while offline into IndexedDB.
 * When connection is restored (or SW triggers a sync event),
 * all pending actions are batched and sent to the server.
 *
 * Usage:
 *   await OfflineSync.queue('create_notice', { title, content, ... });
 *   await OfflineSync.queue('cancel_class',  { course_code, change_date, ... });
 *   await OfflineSync.queue('create_exam',   { course_code, exam_date, ... });
 *   await OfflineSync.syncNow();   // called automatically on 'online' event
 *
 * Exposes: OfflineSync.queue | syncNow | getPending | getAll | clearSynced
 * ─────────────────────────────────────────────────────────────
 */

const OfflineSync = (() => {
  'use strict';

  const DB_NAME    = 'unisync-offline-db';
  const DB_VERSION = 2;
  const STORE      = 'action-queue';

  let _db    = null;
  let _syncing = false;

  // ── IndexedDB bootstrap ─────────────────────────────────────
  function _openDB() {
    if (_db) return Promise.resolve(_db);
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);

      req.onupgradeneeded = e => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE)) {
          const store = db.createObjectStore(STORE, { keyPath: 'local_id' });
          store.createIndex('status',     'status',     { unique: false });
          store.createIndex('type',       'type',       { unique: false });
          store.createIndex('created_at', 'created_at', { unique: false });
        }
      };

      req.onsuccess = e => {
        _db = e.target.result;
        _db.onversionchange = () => { _db.close(); _db = null; };
        resolve(_db);
      };

      req.onerror = e => reject(e.target.error);
    });
  }

  function _tx(mode = 'readonly') {
    return _db.transaction(STORE, mode).objectStore(STORE);
  }

  function _idbOp(req) {
    return new Promise((resolve, reject) => {
      req.onsuccess = e => resolve(e.target.result);
      req.onerror   = e => reject(e.target.error);
    });
  }

  // ── Queue an offline action ─────────────────────────────────
  async function queue(type, payload) {
    const db = await _openDB();
    const action = {
      local_id:   `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      type,
      payload:    { ...payload },
      status:     'pending',
      retries:    0,
      created_at: new Date().toISOString(),
    };

    await _idbOp(_tx('readwrite').add(action));

    // Update UI badge
    _refreshBadge();

    // Register background sync with SW (if supported)
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.ready
        .then(reg => {
          if ('sync' in reg) return reg.sync.register('sync-offline-actions');
        })
        .catch(() => {});
    }

    _log(`Queued "${type}" (local_id: ${action.local_id})`);
    return action;
  }

  // ── Retrieve all pending actions ────────────────────────────
  async function getPending() {
    await _openDB();
    return new Promise((resolve, reject) => {
      const req = _tx('readonly').index('status').getAll('pending');
      req.onsuccess = e => resolve(e.target.result || []);
      req.onerror   = e => reject(e.target.error);
    });
  }

  // ── Retrieve ALL actions (for debug / settings page) ────────
  async function getAll() {
    await _openDB();
    return _idbOp(_tx('readonly').getAll());
  }

  // ── Mark a single action as synced ─────────────────────────
  async function markSynced(local_id) {
    await _openDB();
    const store  = _tx('readwrite');
    const record = await _idbOp(store.get(local_id));
    if (record) {
      record.status    = 'synced';
      record.synced_at = new Date().toISOString();
      await _idbOp(_tx('readwrite').put(record));
    }
  }

  // ── Mark a single action as failed ─────────────────────────
  async function markFailed(local_id, errorMsg) {
    await _openDB();
    const store  = _tx('readwrite');
    const record = await _idbOp(store.get(local_id));
    if (record) {
      record.retries++;
      // After 3 retries, mark permanently failed
      record.status      = record.retries >= 3 ? 'failed' : 'pending';
      record.last_error  = errorMsg;
      record.last_retry  = new Date().toISOString();
      await _idbOp(_tx('readwrite').put(record));
    }
  }

  // ── Delete synced records older than 7 days ─────────────────
  async function clearSynced() {
    await _openDB();
    const all = await getAll();
    const cutoff = Date.now() - 7 * 24 * 3600 * 1000;
    for (const r of all) {
      if (r.status === 'synced' && new Date(r.synced_at).getTime() < cutoff) {
        await _idbOp(_tx('readwrite').delete(r.local_id));
      }
    }
  }

  // ── Main sync function ──────────────────────────────────────
  async function syncNow() {
    if (_syncing || !navigator.onLine) return { synced: 0, failed: 0, skipped: 0 };
    _syncing = true;

    const pending = await getPending();
    if (!pending.length) {
      _syncing = false;
      return { synced: 0, failed: 0, skipped: 0 };
    }

    const user = _getUser();
    if (!user?.id) {
      _syncing = false;
      return { synced: 0, failed: 0, skipped: pending.length };
    }

    _log(`Starting sync: ${pending.length} pending actions`);
    _setSyncIndicator('syncing');

    let totalSynced = 0, totalFailed = 0;

    // Group actions by endpoint type for batch requests
    const groups = {};
    for (const action of pending) {
      const endpoint = _endpointFor(action.type);
      if (!endpoint) continue;
      groups[endpoint] = groups[endpoint] || { endpoint, payloadKey: _payloadKey(action.type), actions: [] };
      groups[endpoint].actions.push(action);
    }

    for (const { endpoint, payloadKey, actions } of Object.values(groups)) {
      try {
        const body = {
          user_id: user.id,
          [payloadKey]: actions.map(a => ({
            ...a.payload,
            local_id: a.local_id,
          })),
        };

        const resp = await fetch(endpoint, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify(body),
          // Don't cache sync requests
          cache: 'no-store',
        });

        if (resp.ok) {
          const result = await resp.json();
          const syncedIds = result.synced || [];

          for (const id of syncedIds) {
            await markSynced(id);
            totalSynced++;
          }
          for (const f of (result.failed || [])) {
            await markFailed(f.local_id, f.error);
            totalFailed++;
          }
        } else {
          // HTTP error — mark all as failed
          for (const action of actions) {
            await markFailed(action.local_id, `HTTP ${resp.status}`);
            totalFailed++;
          }
        }
      } catch (networkErr) {
        _log(`Network error during sync to ${endpoint}:`, networkErr);
        for (const action of actions) {
          await markFailed(action.local_id, networkErr.message);
          totalFailed++;
        }
      }
    }

    _refreshBadge();
    _setSyncIndicator(totalFailed > 0 ? 'error' : 'synced');
    _syncing = false;

    if (totalSynced > 0) {
      _toast(`✅ ${totalSynced} offline action${totalSynced !== 1 ? 's' : ''} synced successfully`, 'success');
    }
    if (totalFailed > 0) {
      _toast(`⚠️ ${totalFailed} action${totalFailed !== 1 ? 's' : ''} failed to sync`, 'warning');
    }

    // Clean up old synced records
    clearSynced().catch(() => {});

    _log(`Sync complete: ${totalSynced} synced, ${totalFailed} failed`);
    return { synced: totalSynced, failed: totalFailed };
  }

  // ── Endpoint map ────────────────────────────────────────────
  function _endpointFor(type) {
    const MAP = {
      'create_notice': '/notices/api/notices/sync',
      'cancel_class':  '/classmanagement/api/class-changes/sync',
      'extra_class':   '/classmanagement/api/class-changes/sync',
      'create_exam':   '/exams/api/exams/sync',
    };
    return MAP[type] || null;
  }

  function _payloadKey(type) {
    if (type === 'create_notice')        return 'drafts';
    if (type.includes('class'))          return 'actions';
    if (type === 'create_exam')          return 'exams';
    return 'actions';
  }

  // ── Badge count refresh ──────────────────────────────────────
  async function _refreshBadge() {
    try {
      const pending = await getPending();
      const count   = pending.length;

      // Badge on offline bar
      const badge = document.getElementById('offlineQueueBadge');
      if (badge) badge.textContent = count || '';

      // Queue count in bar text
      const queueText = document.getElementById('offlineQueueCount');
      if (queueText) queueText.textContent = count;

      // Show/hide the bar if online but queue not empty
      if (count > 0 && navigator.onLine) {
        const bar = document.getElementById('offlineBar');
        if (bar) {
          bar.classList.add('has-queue');
          const label = bar.querySelector('.offline-bar-label');
          if (label) label.textContent = `${count} action${count !== 1 ? 's' : ''} pending sync`;
        }
      }
    } catch (e) { /* silent */ }
  }

  // ── Sync indicator state ──────────────────────────────────────
  function _setSyncIndicator(state) {
    const dot = document.getElementById('offlineSyncDot');
    if (!dot) return;
    dot.className = `sync-dot sync-dot--${state}`;
    dot.title = { syncing: 'Syncing…', synced: 'Synced', error: 'Sync failed' }[state] || '';
  }

  // ── Utility helpers ──────────────────────────────────────────
  function _getUser() {
    try { return JSON.parse(localStorage.getItem('us_user')); } catch { return null; }
  }

  function _toast(msg, type) {
    if (typeof UniSync !== 'undefined' && UniSync.toast) {
      UniSync.toast(msg, type, 4500);
    }
  }

  function _log(...args) {
    if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') {
      console.log('[OfflineSync]', ...args);
    }
  }

  // ── Online / offline event listeners ────────────────────────
  window.addEventListener('online', () => {
    document.body.classList.remove('is-offline');
    const bar = document.getElementById('offlineBar');
    if (bar) bar.classList.remove('is-offline-active');
    _toast('🌐 Back online! Syncing…', 'info');
    // Small delay to let network stabilise
    setTimeout(() => syncNow(), 1500);
  });

  window.addEventListener('offline', () => {
    document.body.classList.add('is-offline');
    const bar = document.getElementById('offlineBar');
    if (bar) bar.classList.add('is-offline-active');
    _toast('📡 You are offline. Actions will sync when connection returns.', 'warning');
  });

  // ── Listen for SW background sync trigger ───────────────────
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', event => {
      if (event.data?.type === 'SW_SYNC_NOW') {
        _log('Background sync triggered by service worker');
        syncNow();
      }
    });
  }

  // ── Periodic sync attempt (every 3 min while page is open) ──
  setInterval(() => {
    if (navigator.onLine) syncNow();
  }, 3 * 60 * 1000);

  // ── Init: set correct online/offline state ───────────────────
  if (!navigator.onLine) {
    document.body.classList.add('is-offline');
  }

  // Refresh badge on load
  document.addEventListener('DOMContentLoaded', () => {
    _refreshBadge();
  });

  // ── Public API ───────────────────────────────────────────────
  return {
    queue,
    syncNow,
    getPending,
    getAll,
    markSynced,
    clearSynced,
  };

})();