/**
 * UniSync — In-App Notification Popup v3.0
 * ══════════════════════════════════════════
 *
 * WHAT THIS DOES (app is OPEN):
 *   Polls /notices/api/notices every 30s for new content.
 *   Shows one glassmorphism popup at a time (serial queue).
 *   "OK" dismisses current → next popup slides in immediately.
 *   Notices stay in their respective tabs unchanged.
 *
 * WHAT THE SERVICE WORKER DOES (app CLOSED / screen OFF):
 *   sw.js + Web Push handles background delivery automatically.
 *   Server triggers this in core/push.py after notice is saved.
 *   This file does NOT touch background push.
 *
 * BATCH RULES:
 *   notice.target_year = null  →  central, every user sees it
 *   notice.target_sem  = null  →  central, every user sees it
 *   otherwise: must match user.program + course_year + course_semester
 *
 * MANUAL TRIGGER (e.g. WebSocket):
 *   UniSyncNotif.push({ id, title, content, type, created_at })
 */

(function () {
    'use strict';

    /* ── Constants ───────────────────────────────────────── */
    const POLL_INTERVAL = 30_000;      // 30 seconds
    const SEEN_KEY      = 'us_notif_seen_v3';
    const MAX_SEEN      = 500;

    /* ── State ───────────────────────────────────────────── */
    let _queue   = [];       // pending notices
    let _showing = false;    // is a popup visible?
    let _seen    = _loadSeen();

    /* ── Seen-IDs persistence ────────────────────────────── */
    function _loadSeen() {
        try { return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || '[]')); }
        catch (e) { return new Set(); }
    }
    function _saveSeen() {
        const arr = [..._seen];
        if (arr.length > MAX_SEEN) arr.splice(0, arr.length - MAX_SEEN);
        try { localStorage.setItem(SEEN_KEY, JSON.stringify(arr)); } catch (e) {}
    }
    function _markSeen(id) {
        _seen.add(String(id));
        _saveSeen();
    }

    /* ── Current user ────────────────────────────────────── */
    function _user() {
        try { return JSON.parse(localStorage.getItem('us_user') || 'null'); }
        catch (e) { return null; }
    }

    /* ── Batch match ─────────────────────────────────────── */
    function _matchesBatch(notice, user) {
        if (!notice.target_year && !notice.target_sem) return true; // central
        if (!user) return false;
        const pOk = !notice.program    || notice.program    === (user.program || '');
        const yOk = !notice.target_year|| notice.target_year === (user.course_year || user.year || 0);
        const sOk = !notice.target_sem || notice.target_sem  === (user.course_semester || user.semester || 0);
        return pOk && yOk && sOk;
    }

    /* ── Type styling ────────────────────────────────────── */
    function _meta(type) {
        return ({
            general:  { icon:'📢', label:'Notice',           color:'#BC6F37' },
            exam:     { icon:'📝', label:'Exam Update',       color:'#7B4FAB' },
            class:    { icon:'📅', label:'Class Update',      color:'#2563EB' },
            resource: { icon:'📁', label:'New Resource',      color:'#16A34A' },
            urgent:   { icon:'🚨', label:'Urgent Notice',     color:'#DC2626' },
            result:   { icon:'🏆', label:'Result Published',  color:'#D97706' },
        })[type] || { icon:'📢', label:'Notice', color:'#BC6F37' };
    }

    /* ── Markdown → HTML ─────────────────────────────────── */
    function _md(raw) {
        if (!raw) return '';
        return raw
            .replace(/```([\s\S]*?)```/g,
                '<pre style="background:rgba(0,0,0,.07);border-radius:6px;padding:9px 11px;font-size:.73rem;overflow-x:auto;white-space:pre-wrap;word-break:break-word;font-family:ui-monospace,monospace;margin:.4em 0">$1</pre>')
            .replace(/`([^`]+)`/g,
                '<code style="background:rgba(0,0,0,.07);border-radius:3px;padding:1px 5px;font-size:.82em;font-family:ui-monospace,monospace">$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\*([^*]+)\*/g,     '<em>$1</em>')
            .replace(/^### (.+)$/gm, '<div style="font-weight:700;font-size:.88rem;color:#111;margin:.5em 0 .2em">$1</div>')
            .replace(/^## (.+)$/gm,  '<div style="font-weight:700;font-size:.92rem;color:#111;margin:.5em 0 .2em">$1</div>')
            .replace(/^# (.+)$/gm,   '<div style="font-weight:800;font-size:.96rem;color:#111;margin:.5em 0 .2em">$1</div>')
            .replace(/^[-•] (.+)$/gm,
                '<div style="display:flex;gap:7px;margin:.15em 0;align-items:flex-start"><span style="color:#BC6F37;flex-shrink:0;margin-top:.1em">•</span><span>$1</span></div>')
            .replace(/^\d+\. (.+)$/gm,
                '<div style="display:flex;gap:7px;margin:.15em 0;align-items:flex-start"><span style="color:#BC6F37;flex-shrink:0;font-weight:600">—</span><span>$1</span></div>')
            .replace(/^> (.+)$/gm,
                '<div style="border-left:3px solid #BC6F37;padding-left:10px;margin:.3em 0;color:#555;font-style:italic">$1</div>')
            .replace(/\n\n/g, '<br><br>')
            .replace(/\n/g,   '<br>');
    }

    function _ago(iso) {
        if (!iso) return '';
        const s = Math.floor((Date.now() - new Date(iso)) / 1000);
        if (s < 60)    return 'just now';
        if (s < 3600)  return Math.floor(s / 60) + 'm ago';
        if (s < 86400) return Math.floor(s / 3600) + 'h ago';
        return Math.floor(s / 86400) + 'd ago';
    }

    /* ── One-time CSS injection ──────────────────────────── */
    function _css() {
        if (document.getElementById('_unp_css')) return;
        const el = document.createElement('style');
        el.id = '_unp_css';
        el.textContent = `
        #_unp_host {
            position:fixed;
            bottom:72px; right:14px;
            z-index:99995;
            width:min(400px,calc(100vw - 24px));
            pointer-events:none;
        }
        @media(min-width:768px){ #_unp_host{bottom:22px;right:22px;} }

        ._unp {
            pointer-events:all;
            position:relative;
            background:rgba(255,255,255,.80);
            backdrop-filter:blur(32px) saturate(200%);
            -webkit-backdrop-filter:blur(32px) saturate(200%);
            border:1px solid rgba(255,255,255,.9);
            border-radius:20px;
            overflow:hidden;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,.75),
                0 10px 44px rgba(0,0,0,.20),
                0 2px 10px rgba(0,0,0,.10);
            font-family:'Outfit',-apple-system,BlinkMacSystemFont,sans-serif;
            animation:_unpIn .36s cubic-bezier(.34,1.56,.64,1) both;
        }
        ._unp.out {
            animation:_unpOut .26s ease both;
            pointer-events:none;
        }
        @keyframes _unpIn  { from{opacity:0;transform:scale(.85) translateY(18px)} to{opacity:1;transform:none} }
        @keyframes _unpOut { from{opacity:1;transform:none} to{opacity:0;transform:scale(.9) translateY(12px)} }

        ._unp_scroll {
            max-height:220px;
            overflow-y:auto;
            padding:8px 16px 0;
            font-size:.78rem;
            color:rgba(0,0,0,.62);
            line-height:1.68;
        }
        ._unp_scroll::-webkit-scrollbar{width:3px}
        ._unp_scroll::-webkit-scrollbar-thumb{background:rgba(0,0,0,.14);border-radius:4px}

        ._unp_q {
            position:absolute;top:-8px;right:-8px;
            min-width:20px;height:20px;
            background:#BC6F37;color:#fff;
            font-size:.6rem;font-weight:800;
            border-radius:10px;padding:0 5px;
            display:flex;align-items:center;justify-content:center;
            border:2.5px solid rgba(255,255,255,.95);
            z-index:2;
        }

        ._unp_ok {
            flex:1;padding:9px 0;border-radius:12px;border:none;
            font-family:inherit;font-size:.78rem;font-weight:700;
            cursor:pointer;color:#fff;letter-spacing:.01em;
            transition:opacity .18s,transform .14s;
        }
        ._unp_ok:hover{opacity:.86} ._unp_ok:active{transform:scale(.97)}

        ._unp_view {
            padding:9px 14px;border-radius:12px;
            background:rgba(0,0,0,.055);border:1px solid rgba(0,0,0,.08);
            font-family:inherit;font-size:.76rem;font-weight:600;
            color:rgba(0,0,0,.52);cursor:pointer;
            transition:background .14s,transform .14s;
        }
        ._unp_view:hover{background:rgba(0,0,0,.09)} ._unp_view:active{transform:scale(.97)}

        ._unp_more {
            padding:5px 16px 0;
            font-size:.7rem;font-weight:700;cursor:pointer;user-select:none;
        }
        ._unp_more:hover{opacity:.7}
        `;
        document.head.appendChild(el);
    }

    /* ── Host container ──────────────────────────────────── */
    function _host() {
        let h = document.getElementById('_unp_host');
        if (!h) {
            h = document.createElement('div');
            h.id = '_unp_host';
            h.setAttribute('aria-live', 'polite');
            h.setAttribute('role', 'region');
            h.setAttribute('aria-label', 'Notifications');
            document.body.appendChild(h);
        }
        return h;
    }

    /* ── Dismiss ─────────────────────────────────────────── */
    function _close(card, onDone) {
        card.classList.add('out');
        card.addEventListener('animationend', () => {
            card.remove();
            _showing = false;
            if (typeof onDone === 'function') onDone();
            else setTimeout(_next, 60);
        }, { once: true });
    }

    /* ── Update badge + OK label while a popup is visible ── */
    function _refresh() {
        const badge = document.getElementById('_unp_badge');
        const ok    = document.getElementById('_unp_ok_btn');
        const q     = _queue.length;
        if (badge) badge.textContent = q > 0 ? '+' + q : '';
        if (ok && q > 0)
            ok.innerHTML = `OK &nbsp;<span style="opacity:.7;font-weight:500">· Next (${q})</span>`;
        else if (ok)
            ok.textContent = 'OK';
    }

    /* ── Build and show one card ─────────────────────────── */
    function _next() {
        if (_showing || _queue.length === 0) return;
        _showing = true;

        const n      = _queue.shift();
        const m      = _meta(n.type || 'general');
        const raw    = (n.content || n.content_text || n.message || '').trim();
        const isLong = raw.length > 320;
        const preview = isLong ? raw.slice(0, 320) + '…' : raw;
        const qLeft   = _queue.length;

        const card = document.createElement('div');
        card.className = '_unp';
        card.setAttribute('role', 'alert');

        /* Queue badge */
        if (qLeft > 0) {
            const badge = document.createElement('div');
            badge.id = '_unp_badge';
            badge.className = '_unp_q';
            badge.textContent = '+' + qLeft;
            card.appendChild(badge);
        }

        /* Card body */
        const body = document.createElement('div');
        body.innerHTML = `
            <div style="height:3px;background:linear-gradient(90deg,${m.color},${m.color}60,transparent)"></div>

            <div style="display:flex;align-items:center;gap:10px;padding:12px 15px 9px;border-bottom:1px solid rgba(0,0,0,.055)">
                <div style="width:33px;height:33px;border-radius:9px;flex-shrink:0;
                    background:${m.color}14;border:1px solid ${m.color}28;
                    display:flex;align-items:center;justify-content:center;font-size:.9rem">${m.icon}</div>
                <div style="flex:1;min-width:0">
                    <div style="font-size:.58rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase;color:${m.color};margin-bottom:1px">${m.label}</div>
                    <div style="font-size:.63rem;color:rgba(0,0,0,.38);font-weight:500">${_ago(n.created_at)}</div>
                </div>
                <button id="_unp_x" aria-label="Dismiss"
                    style="width:26px;height:26px;border-radius:50%;background:rgba(0,0,0,.06);
                    border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;
                    font-size:.68rem;color:rgba(0,0,0,.45);flex-shrink:0;transition:background .14s">✕</button>
            </div>

            <div style="font-weight:700;font-size:.88rem;color:rgba(0,0,0,.84);
                padding:10px 16px 0;letter-spacing:-.01em;line-height:1.35">
                ${n.title || 'New Notification'}
            </div>

            <div class="_unp_scroll" id="_unp_scroll">${_md(preview)}</div>

            ${isLong ? `<div class="_unp_more" id="_unp_more" style="color:${m.color}">Read more →</div>` : ''}

            <div style="display:flex;gap:8px;padding:11px 15px 15px">
                <button class="_unp_ok" id="_unp_ok_btn" style="background:${m.color}">
                    ${qLeft > 0 ? `OK <span style="opacity:.7;font-weight:500">· Next (${qLeft})</span>` : 'OK'}
                </button>
                <button class="_unp_view">View Notice →</button>
            </div>
        `;
        card.appendChild(body);
        _host().appendChild(card);

        /* Wire events */
        body.querySelector('#_unp_x').onclick = () => _close(card);
        body.querySelector('#_unp_x').onmouseenter = function () { this.style.background = 'rgba(0,0,0,.12)'; };
        body.querySelector('#_unp_x').onmouseleave = function () { this.style.background = 'rgba(0,0,0,.06)'; };

        body.querySelector('#_unp_ok_btn').onclick = () => _close(card);   // shows next automatically

        body.querySelector('._unp_view').onclick = () =>
            _close(card, () => { window.location.href = '/notices/'; });

        if (isLong) {
            let exp = false;
            body.querySelector('#_unp_more').onclick = function () {
                exp = !exp;
                body.querySelector('#_unp_scroll').innerHTML = _md(exp ? raw : preview);
                this.textContent = exp ? 'Show less ←' : 'Read more →';
            };
        }
    }

    /* ── Enqueue one notice ──────────────────────────────── */
    function _enqueue(notice) {
        const id = String(notice.id || notice.notice_id || '');
        if (id && _seen.has(id)) return;
        if (id) _markSeen(id);
        _queue.push(notice);
        _refresh();
        if (!_showing) _next();
    }

    /* ── Poll server ─────────────────────────────────────── */
    async function _poll() {
        const user  = _user();
        const token = localStorage.getItem('us_token');
        if (!user || !token) return;

        const qs = new URLSearchParams({
            limit:    '20',
            program:  user.program                                    || '',
            year:     String(user.course_year       || user.year      || ''),
            semester: String(user.course_semester   || user.semester  || ''),
        });

        try {
            const res  = await fetch('/notices/api/notices?' + qs, {
                headers: { 'X-User-Id': user.id }
            });
            if (!res.ok) return;
            const { data = [] } = await res.json();

            /* Enqueue unseen, oldest-first so they display chronologically */
            [...data].reverse().forEach(n => {
                if (_seen.has(String(n.id || ''))) return;
                if (!_matchesBatch(n, user)) return;
                _enqueue(n);
            });
        } catch (e) { /* silent */ }
    }

    /* ── Public API ──────────────────────────────────────── */
    window.UniSyncNotif = {
        /**
         * Manually push a notice (e.g. via WebSocket).
         * @param {{id,title,content,type,created_at}} notice
         */
        push(notice) {
            _css();
            _enqueue(notice);
        },
        /** Force an immediate poll */
        pollNow: _poll,
    };

    /* ── Boot ────────────────────────────────────────────── */
    function _boot() {
        _css();
        setTimeout(_poll, 4500);                  // wait for auth to settle
        setInterval(_poll, POLL_INTERVAL);
    }

    if (document.readyState === 'loading')
        document.addEventListener('DOMContentLoaded', _boot);
    else
        _boot();

}());