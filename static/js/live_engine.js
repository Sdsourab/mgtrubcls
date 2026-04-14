/**
 * UniSync — Live Class Engine  v5.0
 * ──────────────────────────────────────────────────────────────
 * Hero card  : "HAPPENING NOW" — currently running class
 * Schedule   : Today (00:00–17:59) or Tomorrow (18:00–23:59)
 *
 * NEW in v5:
 *   • Fetches class_changes for today/tomorrow
 *   • Cancelled classes → red strikethrough, "CANCELLED" badge
 *   • Extra classes    → green card, "EXTRA CLASS" badge
 *   • Both appear inline with regular schedule, sorted by time
 *
 * Offline-first: every successful fetch cached in localStorage.
 * Polls every 60s (live card) / 5min (schedule list).
 */

const LiveEngine = (() => {
  'use strict';

  const DAYS     = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const WORKDAYS = new Set(['Sunday','Monday','Tuesday','Wednesday','Thursday']);

  // ── Time helpers ────────────────────────────────────────────

  function _t12h(t24) {
    if (!t24) return '';
    var parts = String(t24).split(':').map(Number);
    var h = parts[0], m = parts[1] || 0;
    if (isNaN(h)) return t24;
    return (h % 12 || 12) + ':' + String(m).padStart(2,'0') + ' ' + (h < 12 ? 'AM' : 'PM');
  }

  function _toMins(t) {
    if (!t) return 0;
    var parts = String(t).split(':').map(Number);
    return (parts[0] || 0) * 60 + (parts[1] || 0);
  }

  function _nowInfo() {
    var d = new Date();
    var h = d.getHours(), m = d.getMinutes();
    return {
      day:  DAYS[d.getDay()],
      h: h, m: m,
      time: String(h).padStart(2,'0') + ':' + String(m).padStart(2,'0'),
      date: d,
      dateStr: d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0'),
    };
  }

  function _getTarget() {
    var info = _nowInfo();
    if (info.h >= 18) {
      var tom = new Date(info.date);
      tom.setDate(info.date.getDate() + 1);
      var tomStr = tom.getFullYear() + '-' + String(tom.getMonth()+1).padStart(2,'0') + '-' + String(tom.getDate()).padStart(2,'0');
      return { day: DAYS[tom.getDay()], label: "Tomorrow's Classes", isTomorrow: true, dateStr: tomStr };
    }
    return { day: info.day, label: "Today's Classes", isTomorrow: false, dateStr: info.dateStr };
  }

  // ── Progress ring ─────────────────────────────────────────────

  function _ring(minsLeft, total) {
    total = total || 90;
    var pct  = Math.min(1, Math.max(0, minsLeft / total));
    var r    = 34, cx = 40, cy = 40;
    var circ = 2 * Math.PI * r;
    var off  = circ * (1 - pct);
    return '<svg class="progress-ring-svg" width="80" height="80" viewBox="0 0 80 80">'
      + '<defs><linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">'
      + '<stop offset="0%" stop-color="#CDA96A"/>'
      + '<stop offset="100%" stop-color="#BC6F37"/>'
      + '</linearGradient></defs>'
      + '<circle class="progress-ring-bg" cx="' + cx + '" cy="' + cy + '" r="' + r + '"/>'
      + '<circle class="progress-ring-fill" cx="' + cx + '" cy="' + cy + '" r="' + r + '"'
      + ' stroke-dasharray="' + circ.toFixed(1) + '"'
      + ' stroke-dashoffset="' + off.toFixed(1) + '"/>'
      + '</svg>';
  }

  function _noClass(title, sub) {
    return '<div class="no-class-state">'
      + '<div class="no-class-title">' + title + '</div>'
      + '<div class="no-class-sub">' + sub + '</div>'
      + '</div>';
  }

  // ── Fetch helpers ─────────────────────────────────────────────

  async function _fetchRoutine(day, program, year, semester) {
    var p = program  || 'BBA';
    var y = year     || 1;
    var s = semester || 1;
    var key = 'sched_v5_' + day + '_' + p + '_' + y + '_' + s;

    if (navigator.onLine) {
      try {
        var params = new URLSearchParams({ day: day, program: p, year: y, semester: s });
        var res    = await fetch('/academic/api/routine?' + params);
        if (res.ok) {
          var data = await res.json();
          if (data.success && Array.isArray(data.data)) {
            localStorage.setItem(key, JSON.stringify({ data: data.data, ts: Date.now() }));
            return data.data;
          }
        }
      } catch(e) {}
    }

    // Offline fallback
    try {
      var cached = JSON.parse(localStorage.getItem(key) || 'null');
      if (cached && cached.data) return cached.data;
    } catch(e) {}
    return [];
  }

  async function _fetchClassChanges(dateStr, program, year, semester) {
    /**
     * Fetch class_changes (cancel + extra) for a specific date.
     * Returns array of change objects.
     */
    var key = 'changes_v5_' + dateStr + '_' + (program||'BBA') + '_' + (year||1) + '_' + (semester||1);

    if (navigator.onLine) {
      try {
        var params = new URLSearchParams({
          from:     dateStr,
          to:       dateStr,
          program:  program  || 'BBA',
          year:     year     || 1,
          semester: semester || 1,
        });
        var res = await fetch('/classmanagement/api/class-changes?' + params);
        if (res.ok) {
          var data = await res.json();
          if (data.success && Array.isArray(data.data)) {
            localStorage.setItem(key, JSON.stringify({ data: data.data, ts: Date.now() }));
            return data.data;
          }
        }
      } catch(e) {}
    }

    try {
      var cached = JSON.parse(localStorage.getItem(key) || 'null');
      if (cached && cached.data) return cached.data;
    } catch(e) {}
    return [];
  }

  // ── Merge routine + class_changes ─────────────────────────────

  function _mergeSchedule(regularClasses, classChanges, dateStr) {
    /**
     * Merges regular classes with class_changes for a specific date.
     *
     * Logic:
     *   • For each regular class, check if there's a 'cancel' change
     *     → if yes, mark it as cancelled (keep in list, show strikethrough)
     *   • For each 'extra' change, add as a new item with type='extra'
     *
     * Returns sorted array of schedule items.
     */

    // Build cancel lookup by course_code
    var cancels = {};
    var extras  = [];

    (classChanges || []).forEach(function(ch) {
      if (ch.change_date !== dateStr) return;
      if (ch.type === 'cancel') {
        cancels[ch.course_code] = ch;
      } else if (ch.type === 'extra') {
        extras.push(ch);
      }
    });

    // Process regular classes
    var items = (regularClasses || []).map(function(cls) {
      var isCancelled = !!cancels[cls.course_code];
      return Object.assign({}, cls, {
        _itemType:    isCancelled ? 'cancelled' : 'regular',
        _cancelInfo:  isCancelled ? cancels[cls.course_code] : null,
        _sortKey:     cls.time_start || '00:00',
      });
    });

    // Add extra classes
    extras.forEach(function(ex) {
      items.push({
        course_code:    ex.course_code,
        course_name:    ex.course_name || ex.course_code,
        teacher_code:   ex.teacher_code || '',
        teacher_name:   ex.teacher_name || ex.teacher_code || '',
        time_start:     ex.time_start   || '',
        time_end:       ex.time_end     || '',
        room_no:        ex.room_no      || 'TBD',
        _itemType:      'extra',
        _extraInfo:     ex,
        _sortKey:       ex.time_start   || '00:00',
      });
    });

    // Sort by time
    items.sort(function(a, b) {
      return a._sortKey.localeCompare(b._sortKey);
    });

    return items;
  }

  // ── Render a single schedule item ─────────────────────────────

  function _renderSchedItem(cls, nowMins, isTomorrow) {
    var s = _toMins(cls.time_start);
    var e = _toMins(cls.time_end);
    var itemType = cls._itemType || 'regular';

    var st    = '';
    var badge = '';

    if (itemType === 'cancelled') {
      // Red strikethrough card
      var reason = (cls._cancelInfo && cls._cancelInfo.reason) ? cls._cancelInfo.reason : '';
      return '<div class="sched-item cancelled-item">'
        + '<div class="sched-time">'
          + '<div class="sched-t-start" style="color:#E53E3E;opacity:.7;">' + _t12h(cls.time_start) + '</div>'
          + '<div class="sched-t-end">' + _t12h(cls.time_end) + '</div>'
        + '</div>'
        + '<div class="sched-divider">'
          + '<div class="sched-dot" style="background:#E53E3E;opacity:.5;"></div>'
          + '<div class="sched-line" style="background:rgba(229,62,62,.2);"></div>'
        + '</div>'
        + '<div class="sched-body cancelled-body">'
          + '<div class="sched-course">'
            + '<span style="text-decoration:line-through;opacity:.6;">' + (cls.course_name || cls.course_code) + '</span>'
            + '<span class="sched-badge" style="background:rgba(229,62,62,.12);color:#C53030;border:1px solid rgba(229,62,62,.25);">❌ CANCELLED</span>'
          + '</div>'
          + '<div class="sched-meta" style="opacity:.6;">'
            + '🏛 Room ' + (cls.room_no || '—')
            + (cls.teacher_name ? ' · 👤 ' + cls.teacher_name : '')
          + '</div>'
          + (reason ? '<div style="font-size:.72rem;color:#C53030;margin-top:3px;">💬 ' + reason + '</div>' : '')
        + '</div>'
      + '</div>';
    }

    if (itemType === 'extra') {
      // Green extra class card
      var extraInfo = cls._extraInfo || {};
      var note = extraInfo.reason || '';
      return '<div class="sched-item extra-item">'
        + '<div class="sched-time">'
          + '<div class="sched-t-start" style="color:#38A169;">' + _t12h(cls.time_start) + '</div>'
          + '<div class="sched-t-end">' + _t12h(cls.time_end) + '</div>'
        + '</div>'
        + '<div class="sched-divider">'
          + '<div class="sched-dot" style="background:#38A169;box-shadow:0 0 0 3px rgba(56,161,105,.2);"></div>'
          + '<div class="sched-line" style="background:rgba(56,161,105,.2);"></div>'
        + '</div>'
        + '<div class="sched-body extra-body">'
          + '<div class="sched-course">'
            + (cls.course_name || cls.course_code)
            + '<span class="sched-badge" style="background:rgba(56,161,105,.12);color:#276749;border:1px solid rgba(56,161,105,.25);">📅 EXTRA CLASS</span>'
          + '</div>'
          + '<div class="sched-meta">'
            + '🏛 Room ' + (cls.room_no || 'TBD')
            + (cls.teacher_name ? ' · 👤 ' + cls.teacher_name : '')
          + '</div>'
          + (note ? '<div style="font-size:.72rem;color:#276749;margin-top:3px;">💬 ' + note + '</div>' : '')
        + '</div>'
      + '</div>';
    }

    // Regular class — live / upcoming / done badges
    if (!isTomorrow) {
      if (nowMins >= s && nowMins < e) {
        st    = 'running';
        badge = '<span class="sched-badge running">🔴 NOW · ' + (e - nowMins) + 'm left</span>';
      } else if (nowMins >= e) {
        st    = 'done';
        badge = '<span class="sched-badge done">✓ Done</span>';
      } else if (s - nowMins > 0 && s - nowMins <= 30) {
        badge = '<span class="sched-badge soon">⏰ In ' + (s - nowMins) + 'm</span>';
      }
    }

    return '<div class="sched-item ' + st + '">'
      + '<div class="sched-time">'
        + '<div class="sched-t-start">' + _t12h(cls.time_start) + '</div>'
        + '<div class="sched-t-end">'   + _t12h(cls.time_end)   + '</div>'
      + '</div>'
      + '<div class="sched-divider">'
        + '<div class="sched-dot ' + st + '"></div>'
        + '<div class="sched-line"></div>'
      + '</div>'
      + '<div class="sched-body">'
        + '<div class="sched-course">'
          + (cls.course_name || cls.course_code)
          + badge
        + '</div>'
        + '<div class="sched-meta">'
          + '🏛 Room ' + (cls.room_no || '—')
          + (cls.teacher_name ? ' · 👤 ' + cls.teacher_name : '')
        + '</div>'
      + '</div>'
    + '</div>';
  }

  // ── HERO: Happening Now ───────────────────────────────────────

  async function _renderLive(user) {
    var el = document.getElementById('liveContent');
    if (!el) return;

    var info = _nowInfo();

    if (!WORKDAYS.has(info.day)) {
      el.innerHTML = _noClass('Weekend 🌴', 'No classes — enjoy your ' + info.day + '!');
      return;
    }

    if (info.h >= 18) {
      el.innerHTML = _noClass('Classes done for today ✓', "Tomorrow's schedule shown below ↓");
      return;
    }

    if (info.h < 8) {
      el.innerHTML = _noClass('Classes start at 9:00 AM', 'Good morning! 🌅');
      return;
    }

    if (!navigator.onLine) {
      el.innerHTML = _noClass('Offline 📡', 'Cached schedule shown below ↓');
      return;
    }

    try {
      var p = new URLSearchParams({ day: info.day, time: info.time });
      if (user && user.program)  p.set('program',  user.program);
      if (user && user.year)     p.set('year',      user.year);
      if (user && user.semester) p.set('semester',  user.semester);

      var res  = await fetch('/academic/api/live-class?' + p);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();

      if (!data.success) {
        el.innerHTML = _noClass('Cannot connect', 'Check internet');
        return;
      }

      if (data.is_holiday) {
        var banner = document.getElementById('holidayBanner');
        var name   = document.getElementById('holidayBannerName');
        if (banner) banner.classList.remove('hidden');
        if (name)   name.textContent = data.holiday_name || 'Public Holiday';
        el.innerHTML = '<div class="no-class-state">'
          + '<div class="no-class-title">🎉 ' + (data.holiday_name || 'Holiday') + '</div>'
          + '<div class="no-class-sub">No classes today!</div>'
          + '</div>';
        return;
      }

      if (!data.live || !data.live.length) {
        // Check for cancelled status of next class
        var all     = await _fetchRoutine(info.day, user && user.program, user && user.year, user && user.semester);
        var changes = await _fetchClassChanges(info.dateStr, user && user.program, user && user.year, user && user.semester);
        var nowMins = _toMins(info.time);

        // Build cancel set
        var cancelCodes = new Set((changes || []).filter(function(c){ return c.type === 'cancel'; }).map(function(c){ return c.course_code; }));

        var next = null;
        for (var i = 0; i < all.length; i++) {
          if (_toMins(all[i].time_start) > nowMins && !cancelCodes.has(all[i].course_code)) {
            next = all[i]; break;
          }
        }

        if (next) {
          var inMin = _toMins(next.time_start) - nowMins;
          el.innerHTML = '<div class="no-class-state">'
            + '<div class="no-class-title">No class right now</div>'
            + '<div class="no-class-sub">Next: <strong>' + (next.course_name || next.course_code) + '</strong>'
            + ' in ' + inMin + ' min · Room ' + next.room_no + '</div>'
            + '</div>';
        } else {
          el.innerHTML = _noClass('All classes done today ✓', 'See you tomorrow!');
        }
        return;
      }

      var cls = data.live[0];
      var minsLeft = Math.max(0, _toMins(cls.time_end) - _toMins(info.time));

      el.innerHTML =
        '<div class="live-course-code">' + cls.course_code + '</div>'
        + '<div class="live-course-name">' + (cls.course_name || cls.course_code) + '</div>'
        + '<div class="live-meta">'
          + '<div class="live-meta-item">'
            + '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">'
            + '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>'
            + '</svg>Room ' + (cls.room_no || '—')
          + '</div>'
          + '<div class="live-meta-item">'
            + '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">'
            + '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'
            + '</svg>' + (cls.teacher_name || cls.teacher_code || '—')
          + '</div>'
          + '<div class="live-meta-item">'
            + '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">'
            + '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'
            + '</svg>' + _t12h(cls.time_start) + ' – ' + _t12h(cls.time_end)
          + '</div>'
        + '</div>'
        + '<div class="live-timer-wrap">'
          + '<div class="progress-ring-container">'
            + _ring(minsLeft)
            + '<div class="ring-label">'
              + '<div class="ring-mins">' + minsLeft + '</div>'
              + '<div class="ring-sub">MINS LEFT</div>'
            + '</div>'
          + '</div>'
        + '</div>';

    } catch(e) {
      el.innerHTML = _noClass('Cannot connect', 'Cached schedule shown below ↓');
    }
  }

  // ── Schedule list: Today / Tomorrow with class_changes ────────

  async function renderDaySchedule(user) {
    var wrap = document.getElementById('dayScheduleSection');
    if (!wrap) return;

    var t = _getTarget();

    // Update stat labels
    var lbl = document.getElementById('classesStatLabel');
    var sub = document.getElementById('statClassesSub');
    if (lbl) lbl.textContent = t.isTomorrow ? "TOMORROW'S" : "TODAY'S CLASSES";
    if (sub) sub.textContent = 'classes ' + (t.isTomorrow ? 'tomorrow' : 'today');

    if (!WORKDAYS.has(t.day)) {
      var el = document.getElementById('statTodayClasses');
      if (el) el.textContent = '0';
      wrap.innerHTML = '';
      return;
    }

    var prog = (user && user.program)  || 'BBA';
    var yr   = (user && user.year)     || 1;
    var sem  = (user && user.semester) || 1;

    // Fetch both regular schedule AND class_changes in parallel
    var results = await Promise.allSettled([
      _fetchRoutine(t.day, prog, yr, sem),
      _fetchClassChanges(t.dateStr, prog, yr, sem),
    ]);

    var regularClasses = (results[0].status === 'fulfilled') ? results[0].value : [];
    var classChanges   = (results[1].status === 'fulfilled') ? results[1].value : [];

    // Merge
    var merged = _mergeSchedule(regularClasses, classChanges, t.dateStr);

    // Count stats: regular + extra, not counting cancelled
    var countEl = document.getElementById('statTodayClasses');
    var activeCount = merged.filter(function(c){ return c._itemType !== 'cancelled'; }).length;
    if (countEl) countEl.textContent = activeCount;

    if (!merged.length) {
      wrap.innerHTML =
        '<div class="section-header scroll-reveal" style="margin-top:20px;">'
          + '<h2>' + t.label + '</h2>'
          + '<span class="section-sub">' + t.day + '</span>'
        + '</div>'
        + '<div style="padding:24px;text-align:center;color:var(--text-muted);'
          + 'background:var(--bg-card);border:1px solid var(--border);'
          + 'border-radius:var(--radius-lg);font-size:0.88rem;">'
          + 'No classes scheduled for ' + t.day + '.'
        + '</div>';
      return;
    }

    var info    = _nowInfo();
    var nowMins = _toMins(info.time);

    var totalCount = regularClasses.length;
    var extraCount = classChanges.filter(function(c){ return c.type === 'extra'; }).length;
    var cancelCount = classChanges.filter(function(c){ return c.type === 'cancel'; }).length;

    var subLabel = t.day + ' · ' + totalCount + ' class' + (totalCount !== 1 ? 'es' : '');
    if (extraCount)  subLabel += ' + ' + extraCount + ' extra';
    if (cancelCount) subLabel += ' · ' + cancelCount + ' cancelled';

    wrap.innerHTML =
      '<div class="section-header scroll-reveal" style="margin-top:20px;">'
        + '<h2>' + t.label + '</h2>'
        + '<span class="section-sub">' + subLabel + '</span>'
      + '</div>'
      + '<div class="schedule-list">'
        + merged.map(function(cls) {
            return _renderSchedItem(cls, nowMins, t.isTomorrow);
          }).join('')
      + '</div>';
  }

  // ── Init ──────────────────────────────────────────────────────

  function init() {
    var user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;

    _renderLive(user);
    renderDaySchedule(user);

    // Refresh intervals
    setInterval(function() { _renderLive(user); },         60 * 1000);      // live card: every 60s
    setInterval(function() { renderDaySchedule(user); },   5 * 60 * 1000);  // schedule: every 5min
  }

  document.addEventListener('DOMContentLoaded', init);

  return { init: init, renderDaySchedule: renderDaySchedule };
})();