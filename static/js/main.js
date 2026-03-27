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

  // Close sidebar on mobile nav click
  document.addEventListener('DOMContentLoaded', () => {
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

  // ── Public API ────────────────────────────────────────────

  return {
    getUser, getToken, isLoggedIn, requireAuth,
    logout, hydrateUI, showProfile, toggleSidebar, toast
  };

})();