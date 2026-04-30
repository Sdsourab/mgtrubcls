/**
 * UniSync In-App Notification Popup v3.1
 * ══════════════════════════════════════
 * FIXED:
 *   - user.year / user.semester used correctly
 *     (was wrongly reading user.course_year / user.course_semester)
 *   - Central notices (target_year=null OR target_sem=null) shown to all
 *   - Serial queue: one popup at a time, OK → next immediately
 *   - Markdown formatting on content
 *   - "OK" dismisses current → next in queue shows
 *   - Background push (screen off) handled by sw.js — NOT this file
 */
(function () {
    'use strict';

    var POLL_MS  = 30000;
    var SEEN_KEY = 'us_notif_seen_v4';
    var MAX_SEEN = 500;

    var _queue   = [];
    var _showing = false;
    var _seen    = _loadSeen();

    function _loadSeen() {
        try { return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || '[]')); }
        catch (e) { return new Set(); }
    }
    function _saveSeen() {
        var arr = Array.from(_seen);
        if (arr.length > MAX_SEEN) arr = arr.slice(arr.length - MAX_SEEN);
        try { localStorage.setItem(SEEN_KEY, JSON.stringify(arr)); } catch (e) {}
    }
    function _markSeen(id) { _seen.add(String(id)); _saveSeen(); }

    // ── User — FIXED: user.year / user.semester ────────────────
    function _user() {
        try { return JSON.parse(localStorage.getItem('us_user') || 'null'); }
        catch (e) { return null; }
    }

    // ── Batch match — FIXED ─────────────────────────────────────
    // Matches if notice is central (null target) OR matches user batch.
    function _matches(notice, user) {
        // No target at all → central notice, visible to everyone
        if (!notice.target_year && !notice.target_sem) return true;
        if (!user) return false;

        // FIXED: read user.year and user.semester (not course_year/course_semester)
        var uYear = user.year     || user.course_year     || 0;
        var uSem  = user.semester || user.course_semester || 0;
        var uProg = user.program  || '';
        var nProg = notice.program || '';

        var progOk = !nProg || !uProg || nProg === uProg;
        var yearOk = !notice.target_year || notice.target_year === uYear;
        var semOk  = !notice.target_sem  || notice.target_sem  === uSem;

        return progOk && yearOk && semOk;
    }

    // ── Type meta ───────────────────────────────────────────────
    function _meta(type) {
        var MAP = {
            general:  { icon:'📢', label:'Notice',           color:'#BC6F37' },
            exam:     { icon:'📝', label:'Exam Update',       color:'#7B4FAB' },
            class:    { icon:'📅', label:'Class Update',      color:'#2563EB' },
            resource: { icon:'📁', label:'New Resource',      color:'#16A34A' },
            urgent:   { icon:'🚨', label:'Urgent Notice',     color:'#DC2626' },
            result:   { icon:'🏆', label:'Result Published',  color:'#D97706' },
        };
        return MAP[type] || MAP.general;
    }

    // ── Markdown formatter ──────────────────────────────────────
    function _md(raw) {
        if (!raw) return '';
        return raw
          .replace(/```([\s\S]*?)```/g,
            '<pre style="background:rgba(0,0,0,.07);border-radius:6px;padding:8px 10px;font-size:.74rem;overflow-x:auto;white-space:pre-wrap;font-family:monospace;margin:.4em 0">$1</pre>')
          .replace(/`([^`]+)`/g,
            '<code style="background:rgba(0,0,0,.07);border-radius:3px;padding:1px 5px;font-size:.82em;font-family:monospace">$1</code>')
          .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
          .replace(/\*([^*]+)\*/g,     '<em>$1</em>')
          .replace(/^### (.+)$/gm, '<div style="font-weight:700;font-size:.87rem;color:#111;margin:.4em 0 .15em">$1</div>')
          .replace(/^## (.+)$/gm,  '<div style="font-weight:700;font-size:.92rem;color:#111;margin:.4em 0 .15em">$1</div>')
          .replace(/^# (.+)$/gm,   '<div style="font-weight:800;font-size:.96rem;color:#111;margin:.4em 0 .15em">$1</div>')
          .replace(/^[-•] (.+)$/gm,
            '<div style="display:flex;gap:7px;margin:.12em 0;align-items:flex-start"><span style="color:#BC6F37;flex-shrink:0">•</span><span>$1</span></div>')
          .replace(/^\d+\. (.+)$/gm,
            '<div style="display:flex;gap:7px;margin:.12em 0;align-items:flex-start"><span style="color:#BC6F37;flex-shrink:0;font-weight:600">—</span><span>$1</span></div>')
          .replace(/^> (.+)$/gm,
            '<div style="border-left:3px solid #BC6F37;padding-left:9px;margin:.25em 0;color:#555;font-style:italic">$1</div>')
          .replace(/\n\n/g, '<br><br>')
          .replace(/\n/g, '<br>');
    }

    function _ago(iso) {
        if (!iso) return '';
        var s = Math.floor((Date.now() - new Date(iso)) / 1000);
        if (s < 60)    return 'just now';
        if (s < 3600)  return Math.floor(s / 60) + 'm ago';
        if (s < 86400) return Math.floor(s / 3600) + 'h ago';
        return Math.floor(s / 86400) + 'd ago';
    }

    // ── Inject CSS once ─────────────────────────────────────────
    function _css() {
        if (document.getElementById('_unp_css')) return;
        var s = document.createElement('style');
        s.id = '_unp_css';
        s.textContent = [
          '#_unp_host{position:fixed;bottom:72px;right:14px;z-index:99995;',
          'width:min(400px,calc(100vw - 24px));pointer-events:none;}',
          '@media(min-width:768px){#_unp_host{bottom:22px;right:22px;}}',
          '._unp{pointer-events:all;position:relative;',
          'background:rgba(255,255,255,.80);',
          'backdrop-filter:blur(32px) saturate(200%);',
          '-webkit-backdrop-filter:blur(32px) saturate(200%);',
          'border:1px solid rgba(255,255,255,.88);border-radius:20px;overflow:hidden;',
          'box-shadow:inset 0 1px 0 rgba(255,255,255,.7),0 10px 44px rgba(0,0,0,.20),0 2px 10px rgba(0,0,0,.10);',
          'font-family:"Outfit",-apple-system,BlinkMacSystemFont,sans-serif;',
          'animation:_unpIn .36s cubic-bezier(.34,1.56,.64,1) both;}',
          '._unp.out{animation:_unpOut .26s ease both;pointer-events:none;}',
          '@keyframes _unpIn{from{opacity:0;transform:scale(.85) translateY(18px)}to{opacity:1;transform:none}}',
          '@keyframes _unpOut{from{opacity:1;transform:none}to{opacity:0;transform:scale(.9) translateY(12px)}}',
          '._unp_scroll{max-height:220px;overflow-y:auto;padding:8px 16px 0;',
          'font-size:.78rem;color:rgba(0,0,0,.62);line-height:1.68;}',
          '._unp_scroll::-webkit-scrollbar{width:3px}',
          '._unp_scroll::-webkit-scrollbar-thumb{background:rgba(0,0,0,.14);border-radius:4px}',
          '._unp_q{position:absolute;top:-8px;right:-8px;min-width:20px;height:20px;',
          'background:#BC6F37;color:#fff;font-size:.6rem;font-weight:800;',
          'border-radius:10px;padding:0 5px;display:flex;align-items:center;',
          'justify-content:center;border:2.5px solid rgba(255,255,255,.95);z-index:2;}',
          '._unp_ok{flex:1;padding:9px 0;border-radius:12px;border:none;',
          'font-family:inherit;font-size:.78rem;font-weight:700;cursor:pointer;',
          'color:#fff;transition:opacity .18s,transform .14s;}',
          '._unp_ok:hover{opacity:.86} ._unp_ok:active{transform:scale(.97)}',
          '._unp_sec{padding:9px 14px;border-radius:12px;',
          'background:rgba(0,0,0,.055);border:1px solid rgba(0,0,0,.08);',
          'font-family:inherit;font-size:.76rem;font-weight:600;',
          'color:rgba(0,0,0,.52);cursor:pointer;transition:background .14s,transform .14s;}',
          '._unp_sec:hover{background:rgba(0,0,0,.09)} ._unp_sec:active{transform:scale(.97)}',
        ].join('');
        document.head.appendChild(s);
    }

    // ── Container ────────────────────────────────────────────────
    function _host() {
        var h = document.getElementById('_unp_host');
        if (!h) {
            h = document.createElement('div');
            h.id = '_unp_host';
            h.setAttribute('aria-live', 'polite');
            document.body.appendChild(h);
        }
        return h;
    }

    // ── Dismiss ──────────────────────────────────────────────────
    function _close(card, cb) {
        card.classList.add('out');
        card.addEventListener('animationend', function () {
            card.remove();
            _showing = false;
            if (typeof cb === 'function') cb();
            else setTimeout(_next, 60);
        }, { once: true });
    }

    // ── Refresh queue badge + OK button text ─────────────────────
    function _refresh() {
        var badge = document.getElementById('_unp_badge');
        var ok    = document.getElementById('_unp_ok_btn');
        var q     = _queue.length;
        if (badge) badge.textContent = q > 0 ? '+' + q : '';
        if (ok) ok.innerHTML = q > 0
            ? 'OK <span style="opacity:.65;font-weight:400">· Next (' + q + ')</span>'
            : 'OK';
    }

    // ── Build and show one popup ─────────────────────────────────
    function _next() {
        if (_showing || _queue.length === 0) return;
        _showing = true;

        var n       = _queue.shift();
        var m       = _meta(n.type || 'general');
        var raw     = (n.content || n.content_text || n.message || '').trim();
        var isLong  = raw.length > 320;
        var preview = isLong ? raw.slice(0, 320) + '…' : raw;
        var qLeft   = _queue.length;

        var card = document.createElement('div');
        card.className = '_unp';
        card.setAttribute('role', 'alert');

        // Queue badge
        if (qLeft > 0) {
            var badge = document.createElement('div');
            badge.id = '_unp_badge';
            badge.className = '_unp_q';
            badge.textContent = '+' + qLeft;
            card.appendChild(badge);
        }

        var body = document.createElement('div');
        var okLabel = qLeft > 0
            ? 'OK <span style="opacity:.65;font-weight:400">· Next (' + qLeft + ')</span>'
            : 'OK';

        body.innerHTML =
          '<div style="height:3px;background:linear-gradient(90deg,' + m.color + ',' + m.color + '60,transparent)"></div>'
          + '<div style="display:flex;align-items:center;gap:10px;padding:12px 15px 9px;border-bottom:1px solid rgba(0,0,0,.055)">'
          +   '<div style="width:33px;height:33px;border-radius:9px;flex-shrink:0;background:' + m.color + '14;border:1px solid ' + m.color + '28;display:flex;align-items:center;justify-content:center;font-size:.9rem">' + m.icon + '</div>'
          +   '<div style="flex:1;min-width:0">'
          +     '<div style="font-size:.58rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase;color:' + m.color + ';margin-bottom:1px">' + m.label + '</div>'
          +     '<div style="font-size:.63rem;color:rgba(0,0,0,.38);font-weight:500">' + _ago(n.created_at) + '</div>'
          +   '</div>'
          +   '<button id="_unp_x" aria-label="Dismiss" style="width:26px;height:26px;border-radius:50%;background:rgba(0,0,0,.06);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:.68rem;color:rgba(0,0,0,.46);flex-shrink:0;transition:background .14s">✕</button>'
          + '</div>'
          + '<div style="font-weight:700;font-size:.88rem;color:rgba(0,0,0,.84);padding:10px 16px 0;letter-spacing:-.01em;line-height:1.35">' + (n.title || 'New Notification') + '</div>'
          + '<div class="_unp_scroll" id="_unp_scroll">' + _md(preview) + '</div>'
          + (isLong ? '<div id="_unp_more" style="padding:5px 16px 0;font-size:.7rem;font-weight:700;cursor:pointer;color:' + m.color + '">Read more →</div>' : '')
          + '<div style="display:flex;gap:8px;padding:11px 15px 15px">'
          +   '<button class="_unp_ok" id="_unp_ok_btn" style="background:' + m.color + '">' + okLabel + '</button>'
          +   '<button class="_unp_sec" id="_unp_view">View Notice →</button>'
          + '</div>';

        card.appendChild(body);
        _host().appendChild(card);

        // Events
        var xBtn   = body.querySelector('#_unp_x');
        var okBtn  = body.querySelector('#_unp_ok_btn');
        var vwBtn  = body.querySelector('#_unp_view');

        xBtn.onclick  = function () { _close(card); };
        xBtn.onmouseenter = function () { xBtn.style.background = 'rgba(0,0,0,.12)'; };
        xBtn.onmouseleave = function () { xBtn.style.background = 'rgba(0,0,0,.06)'; };

        // OK = dismiss current, _close() auto-calls _next()
        okBtn.onclick = function () { _close(card); };

        vwBtn.onclick = function () {
            _close(card, function () { window.location.href = '/notices/'; });
        };

        if (isLong) {
            var moreEl  = body.querySelector('#_unp_more');
            var scrollEl = body.querySelector('#_unp_scroll');
            var expanded = false;
            moreEl.onclick = function () {
                expanded = !expanded;
                scrollEl.innerHTML = _md(expanded ? raw : preview);
                moreEl.textContent = expanded ? 'Show less ←' : 'Read more →';
            };
        }
    }

    // ── Enqueue ──────────────────────────────────────────────────
    function _enqueue(notice) {
        var id = String(notice.id || notice.notice_id || '');
        if (id && _seen.has(id)) return;
        if (id) _markSeen(id);
        _queue.push(notice);
        _refresh();
        if (!_showing) _next();
    }

    // ── Poll ─────────────────────────────────────────────────────
    function _poll() {
        var user  = _user();
        var token = localStorage.getItem('us_token');
        if (!user || !token) return;

        // FIXED: use user.year and user.semester
        var uYear = user.year     || user.course_year     || '';
        var uSem  = user.semester || user.course_semester || '';

        var qs = new URLSearchParams({
            limit:    '20',
            program:  user.program || '',
            year:     String(uYear),
            semester: String(uSem),
        });

        fetch('/notices/api/notices?' + qs, { headers: { 'X-User-Id': user.id } })
          .then(function (res) { if (res.ok) return res.json(); })
          .then(function (data) {
              if (!data || !data.data) return;
              // Oldest-first → queue in chronological order
              var items = (data.data || []).slice().reverse();
              items.forEach(function (n) {
                  if (_seen.has(String(n.id || ''))) return;
                  if (!_matches(n, user)) return;
                  _enqueue(n);
              });
          })
          .catch(function () {});
    }

    // ── Public API ───────────────────────────────────────────────
    window.UniSyncNotif = {
        /**
         * Manually push a notice (e.g. via WebSocket real-time).
         * @param {{id, title, content, type, created_at}} notice
         */
        push: function (notice) {
            _css();
            _enqueue(notice);
        },
        pollNow: _poll,
    };

    // ── Boot ─────────────────────────────────────────────────────
    function _boot() {
        _css();
        setTimeout(_poll, 4500);          // let auth settle first
        setInterval(_poll, POLL_MS);
    }

    if (document.readyState === 'loading')
        document.addEventListener('DOMContentLoaded', _boot);
    else
        _boot();

}());