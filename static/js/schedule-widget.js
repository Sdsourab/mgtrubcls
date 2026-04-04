/**
 * UniSync Dashboard — Class Schedule Widget
 * File: static/js/schedule-widget.js
 *
 * Features:
 *  • Fetches /academic/api/dashboard-schedule with user's profile params
 *  • Renders today or tomorrow's classes based on BST time (handled server-side)
 *  • Shows LIVE / UPCOMING / DONE status per class
 *  • Progress bar for currently running classes
 *  • Auto-refreshes every 5 minutes to update live status
 *  • Empty state, holiday state, error state with retry
 *  • Zero dependencies — pure Vanilla JS
 */

(function ScheduleWidget() {
  'use strict';

  // ── Configuration ──────────────────────────────────────────────────────────
  const API_ENDPOINT    = '/academic/api/dashboard-schedule';
  const REFRESH_MS      = 5 * 60 * 1000;   // 5 minutes
  const LIVE_TICK_MS    = 60 * 1000;        // 1 minute — update progress bars

  // ── DOM refs (populated after DOMContentLoaded) ────────────────────────────
  let $body, $loading, $title, $subtitle, $modeBadge, $count, $footer, $footerTime;

  // ── State ──────────────────────────────────────────────────────────────────
  let currentData     = null;
  let refreshTimer    = null;
  let liveTickTimer   = null;

  // ── Boot ───────────────────────────────────────────────────────────────────
  function init() {
    $body       = document.getElementById('scheduleBody');
    $loading    = document.getElementById('scheduleLoading');
    $title      = document.getElementById('scheduleTitle');
    $subtitle   = document.getElementById('scheduleSubtitle');
    $modeBadge  = document.getElementById('scheduleModeBadge');
    $count      = document.getElementById('scheduleCount');
    $footer     = document.getElementById('scheduleFooter');
    $footerTime = document.getElementById('scheduleFooterTime');

    if (!$body) return;  // Widget not on this page

    loadSchedule();

    // Auto-refresh every 5 minutes
    refreshTimer = setInterval(loadSchedule, REFRESH_MS);

    // Refresh when tab regains focus (user may have been away)
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) loadSchedule();
    });
  }

  // ── Fetch ──────────────────────────────────────────────────────────────────
  async function loadSchedule() {
    showLoading();

    // Build query params from user profile stored by UniSync auth system
    const params = buildQueryParams();
    const url    = params ? `${API_ENDPOINT}?${params}` : API_ENDPOINT;

    try {
      const res  = await fetch(url, { credentials: 'same-origin' });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();

      if (!data.success) {
        throw new Error(data.error || 'Unknown error from server');
      }

      currentData = data;
      render(data);

    } catch (err) {
      console.error('[Schedule] Fetch error:', err);
      renderError(err.message);
    }
  }

  // ── Build query params from UniSync global user object ─────────────────────
  function buildQueryParams() {
    try {
      // UniSync.getUser() returns the user object cached from Supabase auth
      const user = (window.UniSync && typeof window.UniSync.getUser === 'function')
        ? window.UniSync.getUser()
        : null;

      if (!user) return '';

      // Profile fields may be on user directly or in user.profile
      const profile = user.profile || user;
      const program  = profile.program  || '';
      const year     = profile.year     || profile.course_year     || '';
      const semester = profile.semester || profile.course_semester || '';

      if (!program || !year || !semester) return '';

      return new URLSearchParams({ program, year, semester }).toString();
    } catch (e) {
      return '';
    }
  }

  // ── Render dispatcher ──────────────────────────────────────────────────────
  function render(data) {
    updateHeader(data);

    if (data.is_holiday) {
      renderHoliday(data.holiday_name);
      return;
    }

    if (!data.classes || data.classes.length === 0) {
      renderEmpty(data.mode, data.day);
      return;
    }

    renderClasses(data.classes, data.mode, data.bst_time);
    startLiveTick(data.classes, data.mode);
  }

  // ── Header ─────────────────────────────────────────────────────────────────
  function updateHeader(data) {
    const isToday = data.mode === 'today';

    // Title
    $title.textContent = isToday ? "Today's Classes" : "Tomorrow's Classes";

    // Subtitle
    $subtitle.textContent = data.day || '';

    // Mode badge
    $modeBadge.textContent    = isToday ? 'Today' : 'Tomorrow';
    $modeBadge.className      = `schedule-mode-badge ${isToday ? 'mode-today' : 'mode-tomorrow'}`;

    // Count pill
    if (data.classes && data.classes.length > 0) {
      $count.textContent    = `${data.classes.length} class${data.classes.length !== 1 ? 'es' : ''}`;
      $count.style.display  = 'inline-flex';
    } else {
      $count.style.display  = 'none';
    }

    // Footer time
    if (data.bst_time) {
      $footerTime.textContent = `BST ${data.bst_time}`;
      $footer.style.display   = 'flex';
    }
  }

  // ── Class List ─────────────────────────────────────────────────────────────
  function renderClasses(classes, mode, bstTime) {
    const list = document.createElement('div');
    list.className = 'schedule-list';
    list.id        = 'scheduleList';

    classes.forEach(cls => {
      list.appendChild(buildClassCard(cls, mode));
    });

    replaceBody(list);
  }

  // ── Single Class Card ──────────────────────────────────────────────────────
  function buildClassCard(cls, mode) {
    const status   = cls.status   || 'upcoming';   // 'live' | 'upcoming' | 'done'
    const progress = cls.progress || 0;
    const duration = cls.duration_mins || 0;

    const card = document.createElement('div');
    card.className = `class-card status-${status}`;
    card.setAttribute('data-course', cls.course_code || '');

    // ── Time column ──────────────────────────────────────────────────────────
    const timeCol = document.createElement('div');
    timeCol.className = 'class-time';
    timeCol.innerHTML = `
      <span class="time-start">${esc(cls.time_start_12h || '')}</span>
      <span class="time-dot"></span>
      <span class="time-end">${esc(cls.time_end_12h || '')}</span>
    `;

    // ── Info column ──────────────────────────────────────────────────────────
    const infoCol = document.createElement('div');
    infoCol.className = 'class-info';

    const courseName = cls.course_name || cls.course_code || 'Class';
    const room       = cls.room_no     || '—';
    const teacher    = cls.teacher_name || cls.teacher_code || '';

    // Meta chips
    const metaChips = [
      room    ? `<span class="class-meta-chip">🏫 Room ${esc(room)}</span>` : '',
      teacher ? `<span class="class-meta-chip">👤 ${esc(teacher)}</span>`   : '',
      duration > 0 ? `<span class="class-meta-chip">⏱ ${duration}m</span>` : '',
    ].filter(Boolean).join('');

    // Progress bar (only for live classes)
    const progressHTML = (status === 'live') ? `
      <div class="class-progress-wrap">
        <div class="class-progress-bar">
          <div class="class-progress-fill" style="width:${progress}%" id="prog-${esc(cls.course_code || Math.random())}"></div>
        </div>
        <div class="class-progress-label" id="prog-label-${esc(cls.course_code || '')}">
          ${progress}% complete · ${cls.mins_left || 0} min left
        </div>
      </div>
    ` : '';

    // Upcoming countdown (show if ≤ 60 min away)
    const countdownHTML = (status === 'upcoming' && cls.mins_until !== null && cls.mins_until <= 60 && mode === 'today') ? `
      <div style="margin-top:0.35rem;">
        <span class="class-meta-chip" style="background:rgba(160,82,45,0.12);color:#A0522D;">
          ⏳ In ${cls.mins_until} min
        </span>
      </div>
    ` : '';

    infoCol.innerHTML = `
      <div class="class-course-name">${esc(courseName)}</div>
      <div class="class-meta">${metaChips}</div>
      ${progressHTML}
      ${countdownHTML}
    `;

    // ── Status column ────────────────────────────────────────────────────────
    const statusCol = document.createElement('div');
    statusCol.className = 'class-status-col';

    const statusLabels = { live: '● Live', upcoming: 'Soon', done: 'Done' };
    const durationLabel = duration > 0 ? `${Math.floor(duration / 60) > 0 ? Math.floor(duration/60)+'h ' : ''}${duration % 60 > 0 ? (duration%60)+'m' : ''}` : '';

    statusCol.innerHTML = `
      <span class="status-badge ${status}">${statusLabels[status] || status}</span>
      ${durationLabel ? `<span class="class-duration">${durationLabel}</span>` : ''}
    `;

    card.appendChild(timeCol);
    card.appendChild(infoCol);
    card.appendChild(statusCol);

    return card;
  }

  // ── Empty State ────────────────────────────────────────────────────────────
  function renderEmpty(mode, day) {
    const isToday = mode === 'today';
    const dayLabel = day || (isToday ? 'today' : 'tomorrow');

    const el = document.createElement('div');
    el.className = 'schedule-empty';

    const configs = {
      Saturday: { icon: '🌴', title: 'Weekend!',     msg: `No classes on Saturday. Rest up!` },
      Friday:   { icon: '🕌', title: 'Day Off',       msg: `Friday is a holiday. Enjoy your break!` },
      default:  { icon: '📭', title: 'No Classes',    msg: `No classes scheduled for ${dayLabel}. Free day!` },
    };

    const conf = configs[day] || configs.default;

    el.innerHTML = `
      <div class="schedule-empty-icon">${conf.icon}</div>
      <h4>${conf.title}</h4>
      <p>${conf.msg}</p>
    `;

    replaceBody(el);
  }

  // ── Holiday State ──────────────────────────────────────────────────────────
  function renderHoliday(holidayName) {
    const el = document.createElement('div');
    el.className = 'schedule-empty is-holiday';
    el.innerHTML = `
      <div class="schedule-empty-icon">🎉</div>
      <h4>Public Holiday</h4>
      <p>${esc(holidayName || 'Today is a holiday')} — No classes scheduled.</p>
    `;
    replaceBody(el);
  }

  // ── Error State ────────────────────────────────────────────────────────────
  function renderError(message) {
    const el = document.createElement('div');
    el.className = 'schedule-error';
    el.innerHTML = `
      <div style="font-size:1.75rem;">⚠️</div>
      <p>Couldn't load schedule</p>
      <button class="schedule-retry-btn" onclick="ScheduleWidgetRefresh()">Retry</button>
    `;

    // Expose refresh globally for the inline onclick
    window.ScheduleWidgetRefresh = loadSchedule;

    replaceBody(el);

    // Hide footer on error
    $footer.style.display = 'none';
    $count.style.display  = 'none';
  }

  // ── Loading State ──────────────────────────────────────────────────────────
  function showLoading() {
    $body.innerHTML = `
      <div class="schedule-loading">
        <div class="schedule-spinner"></div>
        <p>Fetching your schedule…</p>
      </div>
    `;
  }

  // ── Live Tick — update progress bars every minute ──────────────────────────
  function startLiveTick(classes, mode) {
    if (liveTickTimer) clearInterval(liveTickTimer);
    if (mode !== 'today') return;

    // Only tick if there are live or upcoming classes
    const hasActiveClasses = classes.some(c => c.status === 'live' || c.status === 'upcoming');
    if (!hasActiveClasses) return;

    liveTickTimer = setInterval(() => {
      // Re-fetch to get updated statuses (simpler and more accurate than client-side calc)
      loadSchedule();
    }, LIVE_TICK_MS);
  }

  // ── Utility ────────────────────────────────────────────────────────────────
  function replaceBody(el) {
    $body.innerHTML = '';
    $body.appendChild(el);
  }

  /** Escape HTML to prevent XSS from database values */
  function esc(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // ── Initialize on DOM ready ────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();