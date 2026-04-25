/**
 * UniSync Notification Popup Engine
 * ===================================
 * Glassmorphism popup that fires when:
 *   - A new notice is created
 *   - A class schedule update happens
 *   - A new resource is uploaded
 *
 * Polls /notices/api/notices every 30s and shows popup for new items.
 * Supports full markdown-ish text formatting.
 *
 * Usage: auto-starts once DOM is ready. No manual call needed.
 * Depends on: UniSync global (localStorage: us_user, us_token)
 */

(function () {
    'use strict';

    /* ── Config ─────────────────────────────────────────────── */
    const POLL_MS        = 30_000;   // poll every 30s
    const MAX_STACK      = 3;        // max visible popups at once
    const AUTO_CLOSE_MS  = 12_000;   // auto-dismiss after 12s
    const STORAGE_KEY    = 'us_seen_notices';

    /* ── State ───────────────────────────────────────────────── */
    let _pollTimer   = null;
    let _activeCount = 0;
    let _seenIds     = new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'));

    /* ── Container ───────────────────────────────────────────── */
    function ensureContainer() {
        let c = document.getElementById('notif-popup-container');
        if (!c) {
            c = document.createElement('div');
            c.id = 'notif-popup-container';
            c.setAttribute('role', 'region');
            c.setAttribute('aria-label', 'Notifications');
            c.setAttribute('aria-live', 'polite');
            Object.assign(c.style, {
                position:  'fixed',
                bottom:    '20px',
                right:     '20px',
                zIndex:    '99990',
                display:   'flex',
                flexDirection: 'column-reverse',
                gap:       '10px',
                maxWidth:  'min(420px, calc(100vw - 32px))',
                width:     '100%',
            });
            document.body.appendChild(c);
        }
        return c;
    }

    /* ── Markdown-ish formatter ──────────────────────────────── */
    function formatText(raw) {
        if (!raw) return '';
        let t = raw
            /* code blocks */
            .replace(/```([\s\S]*?)```/g,
                '<pre style="background:rgba(0,0,0,.08);border-radius:6px;padding:8px 10px;font-family:monospace;font-size:.78rem;overflow-x:auto;white-space:pre-wrap;word-break:break-word;">$1</pre>')
            /* inline code */
            .replace(/`([^`]+)`/g,
                '<code style="background:rgba(0,0,0,.08);border-radius:4px;padding:1px 5px;font-family:monospace;font-size:.83em;">$1</code>')
            /* bold */
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            /* italic */
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            /* headings */
            .replace(/^### (.+)$/gm,
                '<div style="font-weight:700;font-size:.9rem;margin:.5em 0 .25em;color:var(--text-primary,#1a1a1a)">$1</div>')
            .replace(/^## (.+)$/gm,
                '<div style="font-weight:700;font-size:.95rem;margin:.5em 0 .25em;color:var(--text-primary,#1a1a1a)">$1</div>')
            .replace(/^# (.+)$/gm,
                '<div style="font-weight:800;font-size:1rem;margin:.5em 0 .25em;color:var(--text-primary,#1a1a1a)">$1</div>')
            /* bullet lists */
            .replace(/^[-•] (.+)$/gm,
                '<div style="display:flex;gap:6px;margin:.15em 0"><span style="color:var(--terra,#BC6F37);flex-shrink:0">•</span><span>$1</span></div>')
            /* numbered lists */
            .replace(/^\d+\. (.+)$/gm,
                '<div style="display:flex;gap:6px;margin:.15em 0"><span style="color:var(--terra,#BC6F37);flex-shrink:0;font-weight:600">—</span><span>$1</span></div>')
            /* blockquote */
            .replace(/^> (.+)$/gm,
                '<div style="border-left:3px solid var(--terra,#BC6F37);padding-left:10px;margin:.3em 0;color:var(--text-secondary,#555);font-style:italic">$1</div>')
            /* double newline → paragraph break */
            .replace(/\n\n/g, '<br><br>')
            /* single newline */
            .replace(/\n/g, '<br>');
        return t;
    }

    /* ── Notice type metadata ────────────────────────────────── */
    function typeInfo(type) {
        const MAP = {
            notice:   { icon: '📢', label: 'Notice',          color: '#BC6F37' },
            class:    { icon: '📅', label: 'Class Update',    color: '#2a6a9a' },
            resource: { icon: '📁', label: 'New Resource',    color: '#4a8c4a' },
            exam:     { icon: '📝', label: 'Exam Update',     color: '#8e4a9a' },
            urgent:   { icon: '🚨', label: 'Urgent Notice',   color: '#c0392b' },
            result:   { icon: '🏆', label: 'Result Published', color: '#c0872b' },
        };
        return MAP[type] || MAP['notice'];
    }

    /* ── Time ago ────────────────────────────────────────────── */
    function timeAgo(isoStr) {
        if (!isoStr) return 'just now';
        const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
        if (diff < 60)   return 'just now';
        if (diff < 3600) return Math.floor(diff/60) + 'm ago';
        if (diff < 86400)return Math.floor(diff/3600) + 'h ago';
        return Math.floor(diff/86400) + 'd ago';
    }

    /* ── Build popup DOM ─────────────────────────────────────── */
    function buildPopup(notice) {
        const info = typeInfo(notice.notice_type || notice.type || 'notice');
        const id   = notice.id || notice.notice_id || Math.random().toString(36).slice(2);
        const wrap = document.createElement('div');
        wrap.id = 'notif-' + id;
        wrap.setAttribute('role', 'alert');

        /* Outer glow ring */
        wrap.style.cssText = `
            position: relative;
            border-radius: 18px;
            box-shadow:
                0 0 0 1px rgba(255,255,255,.55),
                0 4px 32px rgba(0,0,0,.18),
                0 1px 4px rgba(0,0,0,.12),
                0 0 0 3px ${info.color}22;
            animation: notifSlideIn .4s cubic-bezier(.34,1.56,.64,1);
            transform-origin: bottom right;
            overflow: visible;
        `;

        /* Card itself */
        const card = document.createElement('div');
        card.style.cssText = `
            background: rgba(255,255,255,.72);
            backdrop-filter: blur(24px) saturate(180%);
            -webkit-backdrop-filter: blur(24px) saturate(180%);
            border: 1px solid rgba(255,255,255,.78);
            border-radius: 18px;
            overflow: hidden;
            font-family: 'Outfit', -apple-system, sans-serif;
            max-height: 480px;
            display: flex;
            flex-direction: column;
        `;

        /* Top color accent strip */
        const strip = document.createElement('div');
        strip.style.cssText = `
            height: 3px;
            background: linear-gradient(90deg, ${info.color}, ${info.color}88);
        `;

        /* Header row */
        const header = document.createElement('div');
        header.style.cssText = `
            display: flex; align-items: center; gap: 10px;
            padding: 13px 16px 10px;
            border-bottom: 1px solid rgba(0,0,0,.06);
            flex-shrink: 0;
        `;

        /* Icon badge */
        const iconBadge = document.createElement('div');
        iconBadge.style.cssText = `
            width: 34px; height: 34px; border-radius: 9px;
            background: ${info.color}18;
            border: 1px solid ${info.color}30;
            display: flex; align-items: center; justify-content: center;
            font-size: 1rem; flex-shrink: 0;
        `;
        iconBadge.textContent = info.icon;

        const headerMeta = document.createElement('div');
        headerMeta.style.cssText = 'flex:1;min-width:0;';
        const typeLbl = document.createElement('div');
        typeLbl.style.cssText = `
            font-size: .6rem; font-weight: 800; letter-spacing: .12em;
            text-transform: uppercase; color: ${info.color}; margin-bottom: 1px;
        `;
        typeLbl.textContent = info.label;
        const timeStr = document.createElement('div');
        timeStr.style.cssText = `
            font-size: .65rem; color: rgba(0,0,0,.4); font-weight: 500;
        `;
        timeStr.textContent = timeAgo(notice.created_at);
        headerMeta.append(typeLbl, timeStr);

        /* Close button */
        const closeBtn = document.createElement('button');
        closeBtn.style.cssText = `
            width: 26px; height: 26px; border-radius: 50%;
            background: rgba(0,0,0,.06); border: none; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            font-size: .75rem; color: rgba(0,0,0,.5); flex-shrink: 0;
            transition: background .15s;
        `;
        closeBtn.innerHTML = '✕';
        closeBtn.setAttribute('aria-label', 'Dismiss notification');
        closeBtn.onmouseenter = () => closeBtn.style.background = 'rgba(0,0,0,.12)';
        closeBtn.onmouseleave = () => closeBtn.style.background = 'rgba(0,0,0,.06)';
        closeBtn.onclick = () => dismissPopup(wrap.id);

        header.append(iconBadge, headerMeta, closeBtn);

        /* Title */
        const titleEl = document.createElement('div');
        titleEl.style.cssText = `
            font-weight: 700; font-size: .9rem; color: rgba(0,0,0,.85);
            padding: 10px 16px 0; line-height: 1.35; flex-shrink: 0;
            letter-spacing: -.01em;
        `;
        titleEl.textContent = notice.title || 'New Notification';

        /* Body — scrollable */
        const bodyEl = document.createElement('div');
        bodyEl.style.cssText = `
            font-size: .78rem; color: rgba(0,0,0,.62); line-height: 1.65;
            padding: 7px 16px 0; overflow-y: auto; flex: 1;
            max-height: 200px;
        `;
        const fullContent = formatText(notice.content || notice.message || '');
        /* Show first 280 chars summary, full in expand */
        const rawFull  = (notice.content || notice.message || '').trim();
        const isLong   = rawFull.length > 280;
        const preview  = isLong ? rawFull.slice(0, 280) + '…' : rawFull;
        bodyEl.innerHTML = formatText(preview);

        /* Expand link if long */
        let expandEl = null;
        if (isLong) {
            expandEl = document.createElement('div');
            expandEl.style.cssText = `
                padding: 4px 16px 0;
                font-size: .72rem; font-weight: 600; color: ${info.color};
                cursor: pointer; flex-shrink: 0;
            `;
            expandEl.textContent = 'Read more →';
            let expanded = false;
            expandEl.onclick = () => {
                expanded = !expanded;
                bodyEl.innerHTML = formatText(expanded ? rawFull : preview);
                expandEl.textContent = expanded ? '← Show less' : 'Read more →';
            };
        }

        /* Action buttons */
        const actions = document.createElement('div');
        actions.style.cssText = `
            display: flex; gap: 7px; padding: 11px 16px 14px; flex-shrink: 0;
        `;

        const viewBtn = document.createElement('button');
        viewBtn.style.cssText = `
            flex: 1; padding: 8px 0; border-radius: 10px; border: none;
            background: ${info.color}; color: #fff;
            font-family: inherit; font-size: .76rem; font-weight: 700;
            cursor: pointer; transition: opacity .18s; letter-spacing: -.005em;
        `;
        viewBtn.textContent = 'View Notice';
        viewBtn.onmouseenter = () => viewBtn.style.opacity = '.85';
        viewBtn.onmouseleave = () => viewBtn.style.opacity = '1';
        viewBtn.onclick = () => {
            window.location.href = '/notices/';
            dismissPopup(wrap.id);
        };

        const dimBtn = document.createElement('button');
        dimBtn.style.cssText = `
            padding: 8px 14px; border-radius: 10px;
            background: rgba(0,0,0,.06); border: 1px solid rgba(0,0,0,.08);
            font-family: inherit; font-size: .76rem; font-weight: 600;
            cursor: pointer; color: rgba(0,0,0,.5); transition: background .15s;
        `;
        dimBtn.textContent = 'Dismiss';
        dimBtn.onmouseenter = () => dimBtn.style.background = 'rgba(0,0,0,.1)';
        dimBtn.onmouseleave = () => dimBtn.style.background = 'rgba(0,0,0,.06)';
        dimBtn.onclick = () => dismissPopup(wrap.id);

        actions.append(viewBtn, dimBtn);

        /* Auto-close progress bar */
        const progBar = document.createElement('div');
        progBar.style.cssText = `
            height: 2px; background: rgba(0,0,0,.06); flex-shrink: 0;
        `;
        const progInner = document.createElement('div');
        progInner.style.cssText = `
            height: 100%;
            background: ${info.color}66;
            transition: width linear ${AUTO_CLOSE_MS}ms;
            width: 100%;
        `;
        progBar.appendChild(progInner);

        /* Assemble */
        card.append(strip, header, titleEl, bodyEl);
        if (expandEl) card.appendChild(expandEl);
        card.append(actions, progBar);
        wrap.appendChild(card);

        /* Trigger progress */
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                progInner.style.width = '0%';
            });
        });

        return wrap;
    }

    /* ── Dismiss ─────────────────────────────────────────────── */
    function dismissPopup(elemId) {
        const el = document.getElementById(elemId);
        if (!el) return;
        el.style.animation = 'notifSlideOut .3s ease forwards';
        el.addEventListener('animationend', () => {
            el.remove();
            _activeCount = Math.max(0, _activeCount - 1);
        }, { once: true });
    }

    /* ── Show popup ──────────────────────────────────────────── */
    function showPopup(notice) {
        if (_activeCount >= MAX_STACK) return;
        const container = ensureContainer();
        const popup = buildPopup(notice);
        container.appendChild(popup);
        _activeCount++;

        /* Auto-dismiss */
        const timer = setTimeout(() => dismissPopup(popup.id), AUTO_CLOSE_MS);

        /* Pause auto-dismiss on hover */
        popup.addEventListener('mouseenter', () => clearTimeout(timer));
    }

    /* ── Persist seen IDs ────────────────────────────────────── */
    function markSeen(id) {
        _seenIds.add(String(id));
        /* Keep only last 200 to avoid unbounded growth */
        const arr = [..._seenIds];
        if (arr.length > 200) arr.splice(0, arr.length - 200);
        _seenIds = new Set(arr);
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify([..._seenIds])); } catch(e) {}
    }

    /* ── Poll ────────────────────────────────────────────────── */
    async function poll() {
        const userRaw = localStorage.getItem('us_user');
        const token   = localStorage.getItem('us_token');
        if (!userRaw || !token) return;

        let user;
        try { user = JSON.parse(userRaw); } catch(e) { return; }
        if (!user || !user.id) return;

        try {
            const res = await fetch(
                `/notices/api/notices?limit=10&user_id=${user.id}&program=${user.program||''}&year=${user.course_year||''}&semester=${user.course_semester||''}`,
                { headers: { 'X-User-Id': user.id, 'X-Token': token } }
            );
            if (!res.ok) return;
            const data = await res.json();
            const notices = (data.data || []).slice(0, 10);

            /* Show popups for new ones (newest first, up to MAX_STACK) */
            let shown = 0;
            for (const n of notices) {
                const nid = String(n.id || n.notice_id || '');
                if (!nid || _seenIds.has(nid)) continue;
                if (shown >= MAX_STACK) break;
                showPopup(n);
                markSeen(nid);
                shown++;
            }
        } catch(e) {
            /* silent fail */
        }
    }

    /* ── Inject CSS keyframes ────────────────────────────────── */
    function injectCSS() {
        if (document.getElementById('notif-popup-css')) return;
        const style = document.createElement('style');
        style.id = 'notif-popup-css';
        style.textContent = `
            @keyframes notifSlideIn {
                from { opacity:0; transform:scale(.88) translateY(16px); }
                to   { opacity:1; transform:scale(1)   translateY(0); }
            }
            @keyframes notifSlideOut {
                from { opacity:1; transform:scale(1)   translateY(0); }
                to   { opacity:0; transform:scale(.88) translateY(12px); }
            }
            #notif-popup-container::-webkit-scrollbar { display:none; }
        `;
        document.head.appendChild(style);
    }

    /* ── Public API — trigger manually ──────────────────────── */
    window.UniSyncNotif = {
        /**
         * Manually show a notification popup.
         * @param {object} notice — { title, content, notice_type, created_at }
         */
        show(notice) {
            injectCSS();
            showPopup(notice);
        },

        /** Force a poll right now */
        pollNow: poll,

        /** Dismiss all visible popups */
        dismissAll() {
            document.querySelectorAll('[id^="notif-"]').forEach(el => {
                if (el.id !== 'notif-popup-container') dismissPopup(el.id);
            });
        },
    };

    /* ── Auto-start ──────────────────────────────────────────── */
    function start() {
        injectCSS();
        /* Initial poll after 3s (give page time to load auth) */
        setTimeout(poll, 3000);
        _pollTimer = setInterval(poll, POLL_MS);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }

})();    