/**
 * UniSync — Live Class Engine  v4
 * ─────────────────────────────────────────────────────────────
 * Hero card: "HAPPENING NOW" — currently running class
 * Schedule section: Today (08:00–18:00) or Tomorrow (after 18:00)
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
      return { day: DAYS[tom.getDay()], label: "Tomorrow's Classes", isTomorrow: true };
    }
    return { day, label: "Today's Classes", isTomorrow: false };
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
    // Guard: if any param is missing/undefined, use defaults
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
        // Also show the holiday banner
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
        // No class running — find next class
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

    const classes = await _fetchSchedule(
      t.day,
      user?.program  || 'BBA',
      user?.year     || 1,
      user?.semester || 1
    );

    const countEl = document.getElementById('statTodayClasses');
    if (countEl) countEl.textContent = classes.length;

    if (!classes.length) {
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

    const { time }   = _nowInfo();
    const nowMins    = _toMins(time);

    wrap.innerHTML = `
    <div class="section-header scroll-reveal" style="margin-top:20px;">
      <h2>${t.label}</h2>
      <span class="section-sub">${t.day} · ${classes.length} class${classes.length !== 1 ? 'es' : ''}</span>
    </div>
    <div class="schedule-list">
      ${classes.map(cls => {
        const s = _toMins(cls.time_start);
        const e = _toMins(cls.time_end);

        let st = '', badge = '';
        if (!t.isTomorrow) {
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

        return `
        <div class="sched-item ${st}">
          <div class="sched-time">
            <div class="sched-t-start">${_t12h(cls.time_start)}</div>
            <div class="sched-t-end">${_t12h(cls.time_end)}</div>
          </div>
          <div class="sched-divider">
            <div class="sched-dot ${st}"></div>
            <div class="sched-line"></div>
          </div>
          <div class="sched-body">
            <div class="sched-course">
              ${cls.course_name || cls.course_code}
              ${badge}
            </div>
            <div class="sched-meta">
              🏛 Room ${cls.room_no || '—'}
              ${cls.teacher_name ? `· 👤 ${cls.teacher_name}` : ''}
            </div>
          </div>
        </div>`;
      }).join('')}
    </div>`;
  }

  // ── Init ──────────────────────────────────────────────────────

  function init() {
    // Wait for UniSync to be available (it's loaded before this file)
    const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;

    _renderLive(user);
    renderDaySchedule(user);

    // Live card: refresh every 60s
    setInterval(() => _renderLive(user), 60 * 1000);
    // Schedule list: refresh every 5 min to update running/done badges
    setInterval(() => renderDaySchedule(user), 5 * 60 * 1000);
  }

  document.addEventListener('DOMContentLoaded', init);

  // Expose for dashboard to call if needed
  return { init, renderDaySchedule };
})();