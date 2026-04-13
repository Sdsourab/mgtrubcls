/**
 * UniSync — Live Class Engine  v5
 * ─────────────────────────────────────────────────────────────
 * Hero card: "HAPPENING NOW" — currently running class
 * Schedule section: Today (08:00–18:00) or Tomorrow (after 18:00)
 * + Upcoming Classes section (next 7 days)
 *
 * CR Integration:
 *  - Extra classes (change_type='extra') shown as green "Extra Class" card
 *  - Cancelled classes (change_type='cancel') shown with red strikethrough
 *
 * Offline-first: every successful API call is cached in localStorage.
 * Falls back to cache automatically when offline.
 * Polls every 60s for live card, every 5min for schedule list.
 * ─────────────────────────────────────────────────────────────
 */

const LiveEngine = (() => {
  'use strict';

  const DAYS     = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const WORKDAYS = new Set(['Sunday','Monday','Tuesday','Wednesday','Thursday']);

  // ── Time helpers ─────────────────────────────────────────────

  function _t12h(t24) {
    if (!t24) return '';
    const [h, m] = String(t24).split(':').map(Number);
    if (isNaN(h)) return t24;
    return `${h % 12 || 12}:${String(m).padStart(2,'0')} ${h < 12 ? 'AM' : 'PM'}`;
  }

  function _toMins(t) {
    if (!t) return 0;
    const [h, m] = String(t).split(':').map(Number);
    return (h || 0) * 60 + (m || 0);
  }

  function _nowInfo() {
    const d = new Date();
    const h = d.getHours(), m = d.getMinutes();
    return {
      day:  DAYS[d.getDay()],
      h, m,
      time: `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`,
      date: d,
    };
  }

  function _dateStr(d) {
    // Returns YYYY-MM-DD for a Date object
    return d.toISOString().split('T')[0];
  }

  /**
   * Time logic:
   *  00:00–17:59  →  show TODAY
   *  18:00–23:59  →  show TOMORROW (plan ahead)
   */
  function _getTarget() {
    const { h, day, date } = _nowInfo();
    if (h >= 18) {
      const tom = new Date(date);
      tom.setDate(date.getDate() + 1);
      return { day: DAYS[tom.getDay()], label: "Tomorrow's Classes", isTomorrow: true, dateObj: tom };
    }
    return { day, label: "Today's Classes", isTomorrow: false, dateObj: date };
  }

  // ── Progress ring SVG ─────────────────────────────────────────

  function _ring(minsLeft, total = 90) {
    const pct    = Math.min(1, Math.max(0, minsLeft / total));
    const r = 34, cx = 40, cy = 40;
    const circ   = 2 * Math.PI * r;
    const offset = circ * (1 - pct);
    return `<svg class="progress-ring-svg" width="80" height="80" viewBox="0 0 80 80">
      <defs><linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#CDA96A"/>
        <stop offset="100%" stop-color="#BC6F37"/>
      </linearGradient></defs>
      <circle class="progress-ring-bg" cx="${cx}" cy="${cy}" r="${r}"/>
      <circle class="progress-ring-fill" cx="${cx}" cy="${cy}" r="${r}"
        stroke-dasharray="${circ.toFixed(1)}"
        stroke-dashoffset="${offset.toFixed(1)}"/>
    </svg>`;
  }

  function _noClass(title, sub) {
    return `<div class="no-class-state">
      <div class="no-class-title">${title}</div>
      <div class="no-class-sub">${sub}</div>
    </div>`;
  }

  // ── Fetch with localStorage cache ─────────────────────────────

  async function _fetchSchedule(day, program, year, semester) {
    const p = program  || 'BBA';
    const y = year     || 1;
    const s = semester || 1;
    const key = `sched_v2_${day}_${p}_${y}_${s}`;

    if (navigator.onLine) {
      try {
        const params = new URLSearchParams({ day, program: p, year: y, semester: s });
        const res    = await fetch(`/academic/api/routine?${params}`);
        if (res.ok) {
          const data = await res.json();
          if (data.success && Array.isArray(data.data)) {
            localStorage.setItem(key, JSON.stringify({ data: data.data, ts: Date.now() }));
            return data.data;
          }
        }
      } catch {}
    }

    // Offline fallback
    try {
      const cached = JSON.parse(localStorage.getItem(key) || 'null');
      if (cached?.data) return cached.data;
    } catch {}
    return [];
  }

  // ── Fetch class changes (cancel/extra) for a date ─────────────

  async function _fetchClassChanges(dateStr, program) {
    const p = program || 'BBA';
    const key = `class_changes_${dateStr}_${p}`;

    if (navigator.onLine) {
      try {
        const params = new URLSearchParams({ from: dateStr, to: dateStr, program: p });
        const res = await fetch(`/cr/api/class-changes?${params}`);
        if (res.ok) {
          const data = await res.json();
          if (data.success && Array.isArray(data.data)) {
            localStorage.setItem(key, JSON.stringify({ data: data.data, ts: Date.now() }));
            return data.data;
          }
        }
      } catch {}
    }

    // Offline fallback
    try {
      const cached = JSON.parse(localStorage.getItem(key) || 'null');
      if (cached?.data) return cached.data;
    } catch {}
    return [];
  }

  // ── Fetch class changes for a range (upcoming) ────────────────

  async function _fetchClassChangesRange(fromDate, toDate, program) {
    const p = program || 'BBA';
    const key = `class_changes_range_${fromDate}_${toDate}_${p}`;

    if (navigator.onLine) {
      try {
        const params = new URLSearchParams({ from: fromDate, to: toDate, program: p });
        const res = await fetch(`/cr/api/class-changes?${params}`);
        if (res.ok) {
          const data = await res.json();
          if (data.success && Array.isArray(data.data)) {
            localStorage.setItem(key, JSON.stringify({ data: data.data, ts: Date.now() }));
            return data.data;
          }
        }
      } catch {}
    }

    try {
      const cached = JSON.parse(localStorage.getItem(key) || 'null');
      if (cached?.data) return cached.data;
    } catch {}
    return [];
  }

  // ── HERO: Happening Now ───────────────────────────────────────

  async function _renderLive(user) {
    const el = document.getElementById('liveContent');
    if (!el) return;

    const { day, h, time } = _nowInfo();

    if (!WORKDAYS.has(day)) {
      el.innerHTML = _noClass('Weekend 🌴', `No classes — enjoy your ${day}!`);
      return;
    }

    if (h >= 18) {
      el.innerHTML = _noClass("Classes done for today ✓", "Tomorrow's schedule shown below ↓");
      return;
    }

    if (h < 8) {
      el.innerHTML = _noClass('Classes start at 8:00 AM', 'Good morning! 🌅');
      return;
    }

    if (!navigator.onLine) {
      el.innerHTML = _noClass('Offline 📡', 'Cached schedule shown below ↓');
      return;
    }

    try {
      const p = new URLSearchParams({ day, time });
      if (user?.program)  p.set('program',  user.program);
      if (user?.year)     p.set('year',      user.year);
      if (user?.semester) p.set('semester',  user.semester);

      const res  = await fetch(`/academic/api/live-class?${p}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (!data.success) {
        el.innerHTML = _noClass('Cannot connect', 'Check internet');
        return;
      }

      if (data.is_holiday) {
        const banner = document.getElementById('holidayBanner');
        const name   = document.getElementById('holidayBannerName');
        if (banner) banner.classList.remove('hidden');
        if (name)   name.textContent = data.holiday_name || 'Public Holiday';
        el.innerHTML = `<div class="no-class-state">
          <div class="no-class-title">🎉 ${data.holiday_name || 'Holiday'}</div>
          <div class="no-class-sub">No classes today!</div>
        </div>`;
        return;
      }

      if (!data.live?.length) {
        const all     = await _fetchSchedule(day, user?.program, user?.year, user?.semester);
        const nowMins = _toMins(time);
        const next    = all.find(c => _toMins(c.time_start) > nowMins);
        if (next) {
          const inMin = _toMins(next.time_start) - nowMins;
          el.innerHTML = `<div class="no-class-state">
            <div class="no-class-title">No class right now</div>
            <div class="no-class-sub">
              Next: <strong>${next.course_name || next.course_code}</strong>
              in ${inMin} min · Room ${next.room_no}
            </div>
          </div>`;
        } else {
          el.innerHTML = _noClass("All classes done today ✓", "See you tomorrow!");
        }
        return;
      }

      // ── Running class ─────────────────────────────────────────
      const cls      = data.live[0];
      const minsLeft = Math.max(0, _toMins(cls.time_end) - _toMins(time));

      el.innerHTML = `
      <div class="live-course-code">${cls.course_code}</div>
      <div class="live-course-name">${cls.course_name || cls.course_code}</div>
      <div class="live-meta">
        <div class="live-meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
          </svg>Room ${cls.room_no || '—'}
        </div>
        <div class="live-meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>${cls.teacher_name || cls.teacher_code || '—'}
        </div>
        <div class="live-meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>${_t12h(cls.time_start)} – ${_t12h(cls.time_end)}
        </div>
      </div>
      <div class="live-timer-wrap">
        <div class="progress-ring-container">
          ${_ring(minsLeft)}
          <div class="ring-label">
            <div class="ring-mins">${minsLeft}</div>
            <div class="ring-sub">MINS LEFT</div>
          </div>
        </div>
      </div>`;

    } catch {
      el.innerHTML = _noClass('Cannot connect', 'Cached schedule shown below ↓');
    }
  }

  // ── Build a single schedule card HTML ─────────────────────────

  function _buildSchedItem(cls, nowMins, isTomorrow, isExtra, isCancelled) {
    const s = _toMins(cls.time_start);
    const e = _toMins(cls.time_end);

    let st = '', badge = '';

    if (isCancelled) {
      // Cancelled class — red strikethrough
      st = 'cancelled';
      badge = `<span class="sched-badge cancelled">✕ Cancelled</span>`;
    } else if (isExtra) {
      // Extra class — green badge
      badge = `<span class="sched-badge extra">＋ Extra Class</span>`;
    } else if (!isTomorrow) {
      if (nowMins >= s && nowMins < e) {
        st    = 'running';
        badge = `<span class="sched-badge running">🔴 NOW · ${e - nowMins}m left</span>`;
      } else if (nowMins >= e) {
        st    = 'done';
        badge = `<span class="sched-badge done">✓ Done</span>`;
      } else if (s - nowMins > 0 && s - nowMins <= 30) {
        badge = `<span class="sched-badge soon">⏰ In ${s - nowMins}m</span>`;
      }
    }

    const courseDisplay = isCancelled
      ? `<span class="sched-course-cancelled">${cls.course_name || cls.course_code}</span>`
      : (cls.course_name || cls.course_code);

    const reasonHtml = (isCancelled && cls.reason)
      ? `<div class="sched-cancel-reason">Reason: ${cls.reason}</div>`
      : '';

    return `
    <div class="sched-item ${st}${isExtra ? ' extra-class' : ''}">
      <div class="sched-time">
        <div class="sched-t-start">${_t12h(cls.time_start)}</div>
        <div class="sched-t-end">${_t12h(cls.time_end)}</div>
      </div>
      <div class="sched-divider">
        <div class="sched-dot ${st}${isExtra ? ' extra' : ''}${isCancelled ? ' cancelled' : ''}"></div>
        <div class="sched-line"></div>
      </div>
      <div class="sched-body">
        <div class="sched-course">
          ${courseDisplay}
          ${badge}
        </div>
        <div class="sched-meta">
          🏛 Room ${cls.room_no || '—'}
          ${cls.teacher_name ? `· 👤 ${cls.teacher_name}` : (cls.teacher_code ? `· 👤 ${cls.teacher_code}` : '')}
        </div>
        ${reasonHtml}
      </div>
    </div>`;
  }

  // ── Schedule list: Today / Tomorrow ───────────────────────────

  async function renderDaySchedule(user) {
    const wrap = document.getElementById('dayScheduleSection');
    if (!wrap) return;

    const t = _getTarget();

    // Update stat card labels
    const lbl = document.getElementById('classesStatLabel');
    const sub = document.getElementById('statClassesSub');
    if (lbl) lbl.textContent = t.isTomorrow ? "TOMORROW'S" : "TODAY'S CLASSES";
    if (sub) sub.textContent = `classes ${t.isTomorrow ? 'tomorrow' : 'today'}`;

    if (!WORKDAYS.has(t.day)) {
      const el = document.getElementById('statTodayClasses');
      if (el) el.textContent = '0';
      wrap.innerHTML = '';
      return;
    }

    const [classes, changes] = await Promise.all([
      _fetchSchedule(t.day, user?.program, user?.year, user?.semester),
      _fetchClassChanges(_dateStr(t.dateObj), user?.program),
    ]);

    // Build a map of cancelled classes by course_code + time_start
    const cancelMap = {};
    const extraList = [];
    for (const ch of changes) {
      if (ch.change_type === 'cancel') {
        // Key: course_code (time_start optional match)
        const k = ch.course_code + (ch.time_start ? '_' + ch.time_start : '');
        cancelMap[k] = ch;
        // Also store by code only as fallback
        cancelMap[ch.course_code] = ch;
      } else if (ch.change_type === 'extra') {
        extraList.push(ch);
      }
    }

    // Merge: mark regular classes as cancelled if matched
    const mergedClasses = classes.map(cls => {
      const k1 = cls.course_code + '_' + cls.time_start;
      const k2 = cls.course_code;
      if (cancelMap[k1]) return { ...cls, _cancelled: true, _cancelData: cancelMap[k1] };
      if (cancelMap[k2]) return { ...cls, _cancelled: true, _cancelData: cancelMap[k2] };
      return cls;
    });

    // Count non-cancelled + extra
    const visibleCount = mergedClasses.length + extraList.length;
    const countEl = document.getElementById('statTodayClasses');
    if (countEl) countEl.textContent = visibleCount;

    if (!mergedClasses.length && !extraList.length) {
      wrap.innerHTML = `
      <div class="section-header scroll-reveal" style="margin-top:20px;">
        <h2>${t.label}</h2>
        <span class="section-sub">${t.day}</span>
      </div>
      <div style="padding:24px;text-align:center;color:var(--text-muted);
                  background:var(--bg-card);border:1px solid var(--border);
                  border-radius:var(--radius-lg);font-size:0.88rem;">
        No classes scheduled for ${t.day}.
      </div>`;
      return;
    }

    const { time } = _nowInfo();
    const nowMins  = _toMins(time);

    // Combine regular (with cancel flag) + extra, then sort by time_start
    const allItems = [
      ...mergedClasses.map(cls => ({ ...cls, _isExtra: false })),
      ...extraList.map(cls => ({ ...cls, _isExtra: true, _cancelled: false })),
    ].sort((a, b) => _toMins(a.time_start) - _toMins(b.time_start));

    wrap.innerHTML = `
    <div class="section-header scroll-reveal" style="margin-top:20px;">
      <h2>${t.label}</h2>
      <span class="section-sub">${t.day} · ${visibleCount} class${visibleCount !== 1 ? 'es' : ''}</span>
    </div>
    <div class="schedule-list">
      ${allItems.map(cls =>
        _buildSchedItem(cls, nowMins, t.isTomorrow, cls._isExtra, cls._cancelled)
      ).join('')}
    </div>`;
  }

  // ── Upcoming Classes (next 7 days) ────────────────────────────

  async function renderUpcomingClasses(user) {
    const wrap = document.getElementById('upcomingClassesSection');
    if (!wrap) return;

    const today = new Date();
    // Start from tomorrow (or day after tomorrow if already showing tomorrow)
    const startOffset = today.getHours() >= 18 ? 2 : 1;
    const startDate = new Date(today);
    startDate.setDate(today.getDate() + startOffset);

    const endDate = new Date(today);
    endDate.setDate(today.getDate() + 7);

    const fromStr = _dateStr(startDate);
    const toStr   = _dateStr(endDate);

    // Fetch class changes for the next 7 days
    const changes = await _fetchClassChangesRange(fromStr, toStr, user?.program);

    if (!changes.length) {
      wrap.style.display = 'none';
      return;
    }

    // Group changes by date
    const byDate = {};
    for (const ch of changes) {
      if (!byDate[ch.date]) byDate[ch.date] = [];
      byDate[ch.date].push(ch);
    }

    const sortedDates = Object.keys(byDate).sort();
    if (!sortedDates.length) {
      wrap.style.display = 'none';
      return;
    }

    wrap.style.display = '';

    const itemsHtml = sortedDates.map(dateStr => {
      const d = new Date(dateStr + 'T00:00:00');
      const dayName = DAYS[d.getDay()];
      const dateLabel = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });

      const dayItems = byDate[dateStr].sort((a, b) => _toMins(a.time_start) - _toMins(b.time_start));

      return `
      <div class="upcoming-date-group">
        <div class="upcoming-date-header">
          <span class="upcoming-day-name">${dayName}</span>
          <span class="upcoming-date-label">${dateLabel}</span>
        </div>
        ${dayItems.map(ch => {
          const isCancel = ch.change_type === 'cancel';
          const isExtra  = ch.change_type === 'extra';
          return `
          <div class="upcoming-item ${isCancel ? 'cancelled' : ''} ${isExtra ? 'extra-class' : ''}">
            <div class="upcoming-item-left">
              <div class="upcoming-time">${_t12h(ch.time_start)}</div>
              <div class="upcoming-time-end">${_t12h(ch.time_end)}</div>
            </div>
            <div class="upcoming-item-dot ${isCancel ? 'cancelled' : isExtra ? 'extra' : ''}"></div>
            <div class="upcoming-item-body">
              <div class="upcoming-course ${isCancel ? 'text-cancelled' : ''}">
                ${isCancel ? `<span class="upcoming-course-strike">${ch.course_name || ch.course_code}</span>` : (ch.course_name || ch.course_code)}
                <span class="upcoming-badge ${isCancel ? 'cancelled' : 'extra'}">
                  ${isCancel ? '✕ Cancelled' : '＋ Extra Class'}
                </span>
              </div>
              <div class="upcoming-meta">
                ${ch.room_no ? `🏛 Room ${ch.room_no}` : ''}
                ${ch.teacher_name ? ` · 👤 ${ch.teacher_name}` : (ch.teacher_code ? ` · 👤 ${ch.teacher_code}` : '')}
              </div>
              ${isCancel && ch.reason ? `<div class="upcoming-reason">Reason: ${ch.reason}</div>` : ''}
            </div>
          </div>`;
        }).join('')}
      </div>`;
    }).join('');

    wrap.innerHTML = `
    <div class="section-header scroll-reveal" style="margin-top:20px;">
      <h2>📅 Upcoming Class Changes</h2>
      <span class="section-sub">Next 7 days</span>
    </div>
    <div class="upcoming-list schedule-card">
      ${itemsHtml}
    </div>`;
  }

  // ── Init ──────────────────────────────────────────────────────

  function init() {
    const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;

    _renderLive(user);
    renderDaySchedule(user);
    renderUpcomingClasses(user);

    // Live card: refresh every 60s
    setInterval(() => _renderLive(user), 60 * 1000);
    // Schedule list: refresh every 5 min to update running/done badges
    setInterval(() => renderDaySchedule(user), 5 * 60 * 1000);
    // Upcoming: refresh every 10 min
    setInterval(() => renderUpcomingClasses(user), 10 * 60 * 1000);
  }

  document.addEventListener('DOMContentLoaded', init);

  return { init, renderDaySchedule, renderUpcomingClasses };
})();