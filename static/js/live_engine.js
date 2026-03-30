/**
 * UniSync — Live Class Engine
 * Polls every 60s, respects user's program/year/semester
 */

const LiveEngine = (() => {

  function _t12h(t24) {
    if (!t24) return '';
    const [h, m] = String(t24).split(':').map(Number);
    if (isNaN(h)) return t24;
    const period = h < 12 ? 'AM' : 'PM';
    return `${h % 12 || 12}:${String(m).padStart(2,'0')} ${period}`;
  }

  const DAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];

  function getNow() {
    const now  = new Date();
    const day  = DAYS[now.getDay()];
    const h    = String(now.getHours()).padStart(2, '0');
    const m    = String(now.getMinutes()).padStart(2, '0');
    return { day, time: `${h}:${m}`, date: now };
  }

  function minsUntil(timeEnd) {
    if (!timeEnd) return 0;
    const { date } = getNow();
    const [endH, endM] = timeEnd.split(':').map(Number);
    const end = new Date(date);
    end.setHours(endH, endM, 0, 0);
    return Math.max(0, Math.floor((end - date) / 60000));
  }

  function buildRing(minsLeft, total = 90) {
    const pct = Math.min(1, minsLeft / total);
    const r   = 34, cx = 40, cy = 40;
    const circ  = 2 * Math.PI * r;
    const offset = circ * (1 - pct);
    return `
    <svg class="progress-ring-svg" width="80" height="80" viewBox="0 0 80 80">
      <defs>
        <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#7c6fff"/>
          <stop offset="100%" stop-color="#ec4899"/>
        </linearGradient>
      </defs>
      <circle class="progress-ring-bg" cx="${cx}" cy="${cy}" r="${r}"/>
      <circle class="progress-ring-fill" cx="${cx}" cy="${cy}" r="${r}"
        stroke-dasharray="${circ}" stroke-dashoffset="${offset}"/>
    </svg>`;
  }

  async function fetchLive() {
    const liveContent = document.getElementById('liveContent');
    if (!liveContent) return;

    const { day, time } = getNow();
    const ACADEMIC = ['Sunday','Monday','Tuesday','Wednesday','Thursday'];

    if (!ACADEMIC.includes(day)) {
      liveContent.innerHTML = renderNoClass('No Classes Today', `${day} is a weekend 🌴`);
      return;
    }

    const user = (typeof UniSync !== 'undefined') ? UniSync.getUser() : null;

    try {
      const params = new URLSearchParams({ day, time });
      if (user?.program)  params.set('program',  user.program);
      if (user?.year)     params.set('year',      user.year);
      if (user?.semester) params.set('semester',  user.semester);

      const res  = await fetch(`/academic/api/live-class?${params}`);
      const data = await res.json();

      if (!data.success) {
        liveContent.innerHTML = renderNoClass('Could not fetch', 'Check connection');
        return;
      }

      if (data.is_holiday) {
        liveContent.innerHTML = `
        <div class="no-class-state">
          <div class="no-class-title">🎉 ${data.holiday_name}</div>
          <div class="no-class-sub">No classes today — Holiday!</div>
        </div>`;
        return;
      }

      if (!data.live || !data.live.length) {
        liveContent.innerHTML = renderNoClass('No Ongoing Class', `${day} · ${time} — Free time!`);
        return;
      }

      const cls      = data.live[0];
      const minsLeft = minsUntil(cls.time_end || '17:00');
      const ring     = buildRing(minsLeft);

      liveContent.innerHTML = `
      <div class="live-course-code">${cls.course_code}</div>
      <div class="live-course-name">${cls.course_name || cls.course_code}</div>
      <div class="live-meta">
        <div class="live-meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          Room ${cls.room_no}
        </div>
        <div class="live-meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
          ${cls.teacher_name || cls.teacher_code}
        </div>
        <div class="live-meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          ${_t12h(cls.time_start)} – ${_t12h(cls.time_end)}
        </div>
      </div>
      <div class="live-timer-wrap">
        <div class="progress-ring-container">
          ${ring}
          <div class="ring-label">
            <div class="ring-mins">${minsLeft}</div>
            <div class="ring-sub">MINS LEFT</div>
          </div>
        </div>
        <button class="join-btn" onclick="UniSync.toast('Discussion board coming soon!','success')">
          Join Discussion
        </button>
      </div>`;

    } catch(e) {
      liveContent.innerHTML = renderNoClass('Cannot connect', 'Server may be offline');
    }
  }

  function renderNoClass(title, sub) {
    return `
    <div class="no-class-state">
      <div class="no-class-title">${title}</div>
      <div class="no-class-sub">${sub}</div>
    </div>`;
  }

  function init() {
    if (!document.getElementById('liveContent')) return;
    fetchLive();
    setInterval(fetchLive, 60000);
  }

  document.addEventListener('DOMContentLoaded', init);
  return { init, fetchLive, getNow };

})();