/**
 * UniSync — Live Class Engine  v3
 * Card 1 (hero): HAPPENING NOW — currently running class
 * Card 2 (schedule): Today (8am-6pm) / Tomorrow (after 6pm) full list
 * Offline-first: caches in localStorage. Polls every 60s.
 */

const LiveEngine = (() => {
  'use strict';

  const DAYS     = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const WORKDAYS = new Set(['Sunday','Monday','Tuesday','Wednesday','Thursday']);

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

  function _now() {
    const d = new Date();
    const h = d.getHours(), m = d.getMinutes();
    return {
      day:  DAYS[d.getDay()],
      h, m,
      time: `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`,
      date: d,
    };
  }

  /* After 18:00 show tomorrow, else show today */
  function _getTarget() {
    const { h, day, date } = _now();
    if (h >= 18) {
      const tom = new Date(date);
      tom.setDate(date.getDate() + 1);
      return { day: DAYS[tom.getDay()], label: "Tomorrow's Classes", isTomorrow: true };
    }
    return { day, label: "Today's Classes", isTomorrow: false };
  }

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
        stroke-dasharray="${circ.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}"/>
    </svg>`;
  }

  function _noClass(title, sub) {
    return `<div class="no-class-state">
      <div class="no-class-title">${title}</div>
      <div class="no-class-sub">${sub}</div>
    </div>`;
  }

  /* Fetch routine with localStorage fallback */
  async function _fetchSchedule(day, program, year, semester) {
    const key = `sched_${day}_${program}_${year}_${semester}`;
    if (navigator.onLine) {
      try {
        const p   = new URLSearchParams({ day, program, year, semester });
        const res = await fetch(`/academic/api/routine?${p}`);
        const d   = await res.json();
        if (d.success) {
          localStorage.setItem(key, JSON.stringify({ data: d.data, ts: Date.now() }));
          return d.data;
        }
      } catch {}
    }
    try {
      const c = JSON.parse(localStorage.getItem(key) || 'null');
      if (c?.data) return c.data;
    } catch {}
    return [];
  }

  /* ── HERO CARD: Happening Now ─────────────────────────────── */
  async function _renderLive(user) {
    const el = document.getElementById('liveContent');
    if (!el) return;

    const { day, h, time } = _now();

    if (!WORKDAYS.has(day)) {
      el.innerHTML = _noClass('Weekend 🌴', `No classes — enjoy your ${day}!`);
      return;
    }
    if (h >= 18) {
      el.innerHTML = _noClass("Classes done for today ✓", "Tomorrow's schedule shown below ↓");
      return;
    }
    if (h < 8) {
      el.innerHTML = _noClass('Classes start at 8:00 AM', `${day} · Good morning!`);
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
      const data = await res.json();

      if (!data.success) { el.innerHTML = _noClass('Cannot connect', 'Check internet'); return; }

      if (data.is_holiday) {
        const b = document.getElementById('holidayBanner');
        const n = document.getElementById('holidayBannerName');
        if (b) b.classList.remove('hidden');
        if (n) n.textContent = data.holiday_name || 'Public Holiday';
        el.innerHTML = `<div class="no-class-state">
          <div class="no-class-title">🎉 ${data.holiday_name || 'Holiday'}</div>
          <div class="no-class-sub">No classes today!</div>
        </div>`;
        return;
      }

      if (!data.live?.length) {
        /* Show next class hint */
        const all     = await _fetchSchedule(day, user?.program||'BBA', user?.year||1, user?.semester||1);
        const nowMins = _toMins(time);
        const next    = all.find(c => _toMins(c.time_start) > nowMins);
        if (next) {
          const inMin = _toMins(next.time_start) - nowMins;
          el.innerHTML = `<div class="no-class-state">
            <div class="no-class-title">No class right now</div>
            <div class="no-class-sub">Next: <strong>${next.course_name || next.course_code}</strong>
             in ${inMin} min · Room ${next.room_no}</div>
          </div>`;
        } else {
          el.innerHTML = _noClass("All classes done today ✓", "See you tomorrow!");
        }
        return;
      }

      const cls      = data.live[0];
      const minsLeft = Math.max(0, _toMins(cls.time_end) - _toMins(time));

      el.innerHTML = `
      <div class="live-course-code">${cls.course_code}</div>
      <div class="live-course-name">${cls.course_name || cls.course_code}</div>
      <div class="live-meta">
        <div class="live-meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
          </svg>Room ${cls.room_no}
        </div>
        <div class="live-meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
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
      el.innerHTML = _noClass('Cannot connect', 'Schedule shown below ↓');
    }
  }

  /* ── SCHEDULE LIST: Today / Tomorrow ──────────────────────── */
  async function renderDaySchedule(user) {
    const wrap = document.getElementById('dayScheduleSection');
    if (!wrap) return;

    const t = _getTarget();

    /* Update stat card labels */
    const lbl = document.getElementById('classesStatLabel');
    const sub = document.getElementById('statClassesSub');
    if (lbl) lbl.textContent = t.isTomorrow ? "TOMORROW'S" : "TODAY'S CLASSES";
    if (sub) sub.textContent = `classes ${t.isTomorrow ? 'tomorrow' : 'today'}`;

    if (!WORKDAYS.has(t.day)) {
      document.getElementById('statTodayClasses').textContent = '0';
      wrap.innerHTML = '';
      return;
    }

    const classes = await _fetchSchedule(
      t.day, user?.program||'BBA', user?.year||1, user?.semester||1
    );

    document.getElementById('statTodayClasses').textContent = classes.length;

    if (!classes.length) {
      wrap.innerHTML = `
      <div class="section-header scroll-reveal" style="margin-top:20px;">
        <h2>${t.label}</h2><span class="section-sub">${t.day}</span>
      </div>
      <div style="padding:24px;text-align:center;color:var(--text-muted);
                  background:var(--bg-card);border:1px solid var(--border);
                  border-radius:var(--radius-lg);font-size:0.88rem;">
        No classes on ${t.day}.
      </div>`;
      return;
    }

    const { time } = _now();
    const nowMins  = _toMins(time);

    wrap.innerHTML = `
    <div class="section-header scroll-reveal" style="margin-top:20px;">
      <h2>${t.label}</h2>
      <span class="section-sub">${t.day} · ${classes.length} class${classes.length!==1?'es':''}</span>
    </div>
    <div class="schedule-list">
      ${classes.map(cls => {
        const s = _toMins(cls.time_start), e = _toMins(cls.time_end);
        let st = '', badge = '';
        if (!t.isTomorrow) {
          if (nowMins >= s && nowMins < e) {
            st = 'running';
            badge = `<span class="sched-badge running">🔴 NOW · ${e-nowMins}m left</span>`;
          } else if (nowMins >= e) {
            st = 'done';
            badge = `<span class="sched-badge done">✓ Done</span>`;
          } else if (s - nowMins <= 30) {
            badge = `<span class="sched-badge soon">⏰ In ${s-nowMins}m</span>`;
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
            <div class="sched-course">${cls.course_name||cls.course_code} ${badge}</div>
            <div class="sched-meta">🏛 Room ${cls.room_no||'—'}
              ${cls.teacher_name ? `· 👤 ${cls.teacher_name}` : ''}
            </div>
          </div>
        </div>`;
      }).join('')}
    </div>`;
  }

  /* ── Init ─────────────────────────────────────────────────── */
  function init() {
    const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;
    _renderLive(user);
    renderDaySchedule(user);
    setInterval(() => _renderLive(user),        60000);   // live card every 1m
    setInterval(() => renderDaySchedule(user), 300000);   // schedule every 5m
  }

  document.addEventListener('DOMContentLoaded', init);
  return { init, renderDaySchedule };
})();