/**
 * UniSync — Live Engine
 * Polls every 60 seconds to check current class
 * and updates the dashboard "Happening Now" hero card.
 */

const LiveEngine = (() => {

  const DAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];

  function getNow() {
    const now = new Date();
    const day  = DAYS[now.getDay()];
    const h    = String(now.getHours()).padStart(2, '0');
    const m    = String(now.getMinutes()).padStart(2, '0');
    const time = `${h}:${m}`;
    return { day, time, hour: now.getHours(), minute: now.getMinutes(), date: now };
  }

  function minsUntil(timeEnd) {
    const { date } = getNow();
    const [endH, endM] = timeEnd.split(':').map(Number);
    const end = new Date(date);
    end.setHours(endH, endM, 0, 0);
    return Math.max(0, Math.floor((end - date) / 60000));
  }

  function buildProgressRing(minsLeft, slotMinutes = 90) {
    const pct = Math.min(1, minsLeft / slotMinutes);
    const r = 34, cx = 40, cy = 40;
    const circumference = 2 * Math.PI * r;
    const offset = circumference * (1 - pct);

    return `
    <svg class="progress-ring-svg" width="80" height="80" viewBox="0 0 80 80">
      <defs>
        <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#7c6fff"/>
          <stop offset="100%" stop-color="#ec4899"/>
        </linearGradient>
      </defs>
      <circle class="progress-ring-bg" cx="${cx}" cy="${cy}" r="${r}"/>
      <circle class="progress-ring-fill"
        cx="${cx}" cy="${cy}" r="${r}"
        stroke-dasharray="${circumference}"
        stroke-dashoffset="${offset}"
      />
    </svg>`;
  }

  async function fetchLiveClass() {
    const liveCard = document.getElementById('liveContent');
    if (!liveCard) return;

    const { day, time } = getNow();

    // Academic day check
    const academicDays = ['Sunday','Monday','Tuesday','Wednesday','Thursday'];
    if (!academicDays.includes(day)) {
      liveCard.innerHTML = renderNoClass(`No classes today (${day})`, 'Enjoy your day off! 📚');
      return;
    }

    try {
      const res = await fetch(`/academic/api/live-class?day=${day}&time=${time}`);
      const data = await res.json();

      if (!data.success) {
        liveCard.innerHTML = renderNoClass('Could not fetch schedule', 'Check your connection');
        return;
      }

      if (!data.live || !data.live.length) {
        liveCard.innerHTML = renderNoClass('No Ongoing Class', `${day} · ${time} — No class at this time`);
        return;
      }

      const cls = data.live[0];
      const minsLeft = minsUntil(cls.time_end || '17:00');
      const ring = buildProgressRing(minsLeft);

      liveCard.innerHTML = `
      <div class="live-course-code">${cls.course_code}</div>
      <div class="live-course-name">${cls.course_name || cls.course_code}</div>
      <div class="live-meta">
        <div class="live-meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          Room ${cls.room_no}
        </div>
        <div class="live-meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
          ${cls.teacher_name || cls.teacher_code}
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
        <button class="join-btn" onclick="UniSync.toast('Discussion board coming soon!', 'success')">
          Join Discussion
        </button>
      </div>`;

    } catch(e) {
      liveCard.innerHTML = renderNoClass('Could not fetch schedule', 'Backend might not be running');
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
    const liveCard = document.getElementById('liveContent');
    if (!liveCard) return;

    fetchLiveClass();
    // Poll every 60 seconds
    setInterval(fetchLiveClass, 60000);
  }

  // Auto-init when DOM is ready
  document.addEventListener('DOMContentLoaded', init);

  return { init, fetchLiveClass, getNow };

})();
