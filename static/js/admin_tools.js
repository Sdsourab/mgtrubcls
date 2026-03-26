/**
 * UniSync — Admin Tools JS
 * Excel upload drag-drop handler and admin utilities.
 */

// Drag-over styling for upload zone
document.addEventListener('DOMContentLoaded', () => {
  const zone = document.getElementById('uploadZone');
  if (!zone) return;

  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.style.borderColor = 'var(--accent)';
    zone.style.background = 'rgba(124,111,255,0.05)';
  });

  zone.addEventListener('dragleave', () => {
    zone.style.borderColor = '';
    zone.style.background = '';
  });

  zone.addEventListener('drop', (e) => {
    zone.style.borderColor = '';
    zone.style.background = '';
  });
});
