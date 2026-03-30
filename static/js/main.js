/**
 * UniSync — Core App Logic
 * Auth management, UI hydration, toast, sidebar
 */

const UniSync = (() => {

  // ── Auth ──────────────────────────────────────────────────

  function getUser() {
    try {
      const u = localStorage.getItem('us_user');
      return u ? JSON.parse(u) : null;
    } catch { return null; }
  }

  function getToken() {
    return localStorage.getItem('us_token') || '';
  }

  function isLoggedIn() {
    return !!getToken() && !!getUser();
  }

  function requireAuth() {
    if (!isLoggedIn()) {
      window.location.href = '/auth/login';
      return false;
    }
    hydrateUI();
    return true;
  }

  async function logout() {
    try {
      await fetch('/auth/api/logout', { method: 'POST' });
    } catch(e) {}
    localStorage.removeItem('us_token');
    localStorage.removeItem('us_user');
    window.location.href = '/auth/login';
  }

  // ── UI Hydration ──────────────────────────────────────────

  function hydrateUI() {
    const user = getUser();
    if (!user) return;

    const initial = ((user.full_name || user.email || '?')[0] || '?').toUpperCase();

    const els = {
      sidebarUserName: user.full_name || user.email || 'User',
      sidebarUserRole: user.role      || 'student',
    };
    Object.entries(els).forEach(([id, val]) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    });

    ['sidebarAvatar', 'mobileAvatar'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = initial;
    });

    // Show admin nav
    if (user.role === 'admin') {
      document.querySelectorAll('.admin-only').forEach(el => {
        el.classList.remove('hidden');
      });
    }
  }

  // ── Profile Modal ─────────────────────────────────────────

  function showProfile() {
    window.location.href = '/auth/profile';
  }

  // ── Sidebar ───────────────────────────────────────────────

  function toggleSidebar() {
    const sb = document.getElementById('sidebar');
    const ov = document.getElementById('sidebarOverlay');
    if (!sb) return;
    const isOpen = sb.classList.contains('open');
    if (isOpen) {
      sb.classList.remove('open');
      if (ov) ov.classList.remove('active');
      document.body.style.overflow = '';
    } else {
      sb.classList.add('open');
      if (ov) ov.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
  }


  // ── Scroll-reveal ─────────────────────────────────────────
  function initScrollReveal() {
    const els = document.querySelectorAll('.scroll-reveal');
    if (!els.length) return;
    if (!('IntersectionObserver' in window)) {
      els.forEach(el => el.classList.add('is-visible'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('is-visible');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -32px 0px' });
    els.forEach(el => io.observe(el));
  }

  // Close sidebar on mobile nav click
  document.addEventListener('DOMContentLoaded', () => {
    initScrollReveal();
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', () => {
        if (window.innerWidth < 769) {
          const sb = document.getElementById('sidebar');
          const ov = document.getElementById('sidebarOverlay');
          if (sb && sb.classList.contains('open')) {
            sb.classList.remove('open');
            if (ov) ov.classList.remove('active');
            document.body.style.overflow = '';
          }
        }
      });
    });
  });

  // ── Toast ─────────────────────────────────────────────────

  function toast(message, type = 'success', duration = 3500) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);

    setTimeout(() => {
      el.style.opacity   = '0';
      el.style.transform = 'translateX(100%)';
      el.style.transition = 'all 0.3s ease';
      setTimeout(() => el.remove(), 310);
    }, duration);
  }


  // ── 12-Hour Time Utilities ────────────────────────────────

  /**
   * Convert 24h "HH:MM" → 12h "12:00 PM"
   */
  function to12h(t24) {
    if (!t24) return '';
    const parts = String(t24).split(':');
    if (parts.length < 2) return t24;
    const h = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10);
    if (isNaN(h) || isNaN(m)) return t24;
    const period = h < 12 ? 'AM' : 'PM';
    const h12 = h % 12 || 12;
    return `${h12}:${String(m).padStart(2, '0')} ${period}`;
  }

  /**
   * Format a datetime string's time portion to 12h.
   * Handles "HH:MM", "HH:MM:SS", ISO strings.
   */
  function formatTime12h(val) {
    if (!val) return '';
    // If it looks like an ISO or datetime, grab HH:MM
    const match = String(val).match(/(\d{1,2}):(\d{2})/);
    if (match) return to12h(`${match[1].padStart(2,'0')}:${match[2]}`);
    return val;
  }

  // ── Update localStorage user profile ─────────────────────
  function updateStoredUser(patch) {
    try {
      const user = getUser() || {};
      const updated = { ...user, ...patch };
      localStorage.setItem('us_user', JSON.stringify(updated));
      hydrateUI();
    } catch(e) {}
  }

  // ── Public API ────────────────────────────────────────────

  return {
    getUser, getToken, isLoggedIn, requireAuth,
    logout, hydrateUI, showProfile, toggleSidebar, toast,
    to12h, formatTime12h, updateStoredUser
  };

})();