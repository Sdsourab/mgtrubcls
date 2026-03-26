/**
 * UniSync — Main Application Logic
 * Handles: Auth state, user session, toast notifications,
 * sidebar toggling, and utility functions.
 */

const UniSync = (() => {

  // ===================== AUTH =====================
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

  // ===================== UI HYDRATION =====================
  function hydrateUI() {
    const user = getUser();
    if (!user) return;

    const initial = (user.full_name || user.email || '?')[0].toUpperCase();

    // Sidebar
    const nameEl  = document.getElementById('sidebarUserName');
    const roleEl  = document.getElementById('sidebarUserRole');
    const avEl    = document.getElementById('sidebarAvatar');
    const mobAvEl = document.getElementById('mobileAvatar');

    if (nameEl) nameEl.textContent = user.full_name || user.email || 'User';
    if (roleEl) roleEl.textContent = user.role || 'student';
    if (avEl)   avEl.textContent   = initial;
    if (mobAvEl) mobAvEl.textContent = initial;

    // Show admin nav if role === admin
    if (user.role === 'admin') {
      document.querySelectorAll('.admin-only').forEach(el => el.classList.remove('hidden'));
    }
  }

  // ===================== PROFILE MODAL =====================
  function showProfile() {
    const user = getUser();
    if (!user) return;
    const modal = document.getElementById('profileModal');
    if (!modal) return;

    const initial = (user.full_name || user.email || '?')[0].toUpperCase();
    const avEl = document.getElementById('profileAvatarLg');
    if (avEl) avEl.textContent = initial;

    const fields = { pm_name: user.full_name, pm_email: user.email, pm_role: user.role, pm_dept: user.dept, pm_batch: user.batch };
    Object.entries(fields).forEach(([id, val]) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val || '—';
    });

    modal.classList.remove('hidden');
  }

  // ===================== SIDEBAR =====================
  function toggleSidebar() {
    const sb = document.getElementById('sidebar');
    const ov = document.getElementById('sidebarOverlay');
    if (!sb) return;
    const isOpen = sb.classList.contains('open');
    if (isOpen) {
      sb.classList.remove('open');
      ov.classList.remove('active');
      document.body.style.overflow = '';
    } else {
      sb.classList.add('open');
      ov.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
  }

  // Close sidebar on nav item click (mobile)
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', () => {
        if (window.innerWidth < 769) {
          const sb = document.getElementById('sidebar');
          const ov = document.getElementById('sidebarOverlay');
          if (sb && sb.classList.contains('open')) {
            sb.classList.remove('open');
            ov.classList.remove('active');
            document.body.style.overflow = '';
          }
        }
      });
    });
  });

  // ===================== TOAST =====================
  function toast(message, type = 'success', duration = 3000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);

    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transform = 'translateX(100%)';
      el.style.transition = 'all 0.3s ease';
      setTimeout(() => el.remove(), 300);
    }, duration);
  }

  // ===================== PUBLIC API =====================
  return { getUser, getToken, isLoggedIn, requireAuth, logout, hydrateUI, showProfile, toggleSidebar, toast };

})();
