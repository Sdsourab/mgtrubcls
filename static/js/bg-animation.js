/**
 * UniSync — Organic Background Animation
 * Earthy palette: FCF5E8 · CDA96A · BC6F37 · 8E8946 · 6A632B
 * Slowly morphing SVG blobs + floating orbs — 60 fps, GPU-accelerated
 */

(function () {
  'use strict';

  const BLOBS = [
    {
      color: 'rgba(142, 137, 70, 0.13)',   // olive
      size: 520,
      x: -8, y: -6,
      duration: 28,
      delay: 0,
      paths: [
        'M421.7,294.2C393.1,357.8,322.3,394.5,257.1,402.6C191.9,410.8,131.8,390.4,91.3,349.4C50.7,308.3,29.5,246.5,43.8,192.2C58.1,137.9,108,91.1,163.5,63.7C219,36.4,280.2,28.4,336.2,50.1C392.2,71.8,443,123.2,456.4,183.5C469.9,243.9,450.4,230.6,421.7,294.2Z',
        'M398.5,278.5C368.9,345.2,294.5,391.4,227.8,401.5C161.1,411.6,101.9,385.6,63.8,341.1C25.7,296.7,9.6,233.9,26.7,178.8C43.8,123.7,94.4,76.2,153.8,53.2C213.2,30.2,281.4,31.7,337.1,57.8C392.8,83.9,436,134.6,447.6,193.2C459.2,251.8,428.1,211.7,398.5,278.5Z',
        'M440.2,308.9C408.3,374.1,333.2,407.8,263.7,412.5C194.2,417.3,130.3,393.1,86.5,350.5C42.7,307.9,19.1,246.9,30.8,191.9C42.5,136.9,89.4,88,144.3,59.2C199.2,30.4,262.1,21.7,321.1,45.1C380.1,68.5,435.1,123.9,455.3,187.4C475.6,250.9,472.2,243.8,440.2,308.9Z',
      ],
    },
    {
      color: 'rgba(188, 111, 55, 0.10)',   // terracotta
      size: 460,
      x: 55, y: 48,
      duration: 34,
      delay: -12,
      paths: [
        'M388.5,272.4C358.7,338.7,285.4,381.8,218.7,389.6C151.9,397.5,91.6,369.9,54.3,323.8C17,277.7,2.6,212.9,20.8,157.4C39,101.9,90.6,55.8,149.8,33C209,10.2,275.8,10.7,331.1,38.2C386.4,65.7,430.1,120.2,442.7,180.7C455.3,241.2,418.4,206.1,388.5,272.4Z',
        'M410.3,288.1C381.5,351.3,310.8,391.5,246.2,402.6C181.7,413.8,123.4,395.9,83.2,358.2C43,320.5,20.9,263,32.1,208.4C43.3,153.8,87.7,102.2,140.6,70.3C193.5,38.4,255,26.2,312,44.5C369,62.8,421.5,111.6,437.6,168.5C453.7,225.4,439.1,224.9,410.3,288.1Z',
        'M375.2,261.7C344.8,329.2,272.3,374.4,205.6,385.8C138.9,397.2,78,375,40.3,333.3C2.6,291.6,-11.7,230.3,8.3,174.8C28.3,119.3,82,69.5,143.4,44.9C204.7,20.3,273.7,21,333,50.8C392.3,80.6,442,139.4,451.9,200.5C461.8,261.5,405.6,194.1,375.2,261.7Z',
      ],
    },
    {
      color: 'rgba(106, 99, 43, 0.09)',    // dark olive
      size: 400,
      x: 30, y: 60,
      duration: 40,
      delay: -20,
      paths: [
        'M356.2,240.8C329.3,302.7,259.7,342.1,196.5,351.8C133.3,361.5,76.8,341.5,43.2,302.2C9.6,263,-.9,204.4,16.5,151.9C33.9,99.4,79.2,52.8,132.9,27.8C186.6,2.8,249,-.3,302,24.5C355,49.3,398.4,101.8,410.4,159.1C422.4,216.4,383.1,178.9,356.2,240.8Z',
        'M371.8,255.2C345.2,315.8,278.1,353.4,216.3,362.8C154.5,372.1,97.8,353.1,63.1,314.5C28.4,275.9,15.6,217.8,31.3,164.7C47,111.6,91.2,63.4,143.9,37.5C196.7,11.5,258,7.8,312.3,31.9C366.6,56,413.8,108,425.5,165.1C437.3,222.3,398.4,194.6,371.8,255.2Z',
        'M342.1,228.3C314.8,291.4,244.8,333.7,181.2,344.2C117.6,354.7,60.3,333.4,26.4,294.1C-7.5,254.7,-17.2,197.1,0.8,144.7C18.8,92.3,64.9,44.9,118.7,19.8C172.5,-5.2,234,1.6,287.5,27.2C341,52.7,386.3,97.1,400.1,148.4C414,199.7,369.4,165.2,342.1,228.3Z',
      ],
    },
  ];

  const ORB_COLORS = [
    'rgba(188, 111, 55, 0.06)',
    'rgba(142, 137, 70, 0.07)',
    'rgba(205, 169, 106, 0.05)',
  ];

  function init() {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let W, H, orbs;

    function resize() {
      W = canvas.width  = window.innerWidth;
      H = canvas.height = window.innerHeight;
      initOrbs();
    }

    function initOrbs() {
      orbs = Array.from({ length: 5 }, (_, i) => ({
        x:  Math.random() * W,
        y:  Math.random() * H,
        r:  80 + Math.random() * 140,
        vx: (Math.random() - 0.5) * 0.18,
        vy: (Math.random() - 0.5) * 0.18,
        color: ORB_COLORS[i % ORB_COLORS.length],
      }));
    }

    resize();
    window.addEventListener('resize', resize);

    // ── SVG path morphing for blobs ────────────────────────────────────
    const svgNS = 'http://www.w3.org/2000/svg';
    const blobContainer = document.getElementById('bgBlobs');
    if (!blobContainer) return;

    BLOBS.forEach((cfg, bi) => {
      const svgEl = document.createElementNS(svgNS, 'svg');
      svgEl.setAttribute('viewBox', '0 0 470 470');
      svgEl.style.cssText = `
        position: absolute;
        width: ${cfg.size}px;
        height: ${cfg.size}px;
        left: ${cfg.x}%;
        top: ${cfg.y}%;
        opacity: 1;
        pointer-events: none;
        will-change: transform;
      `;

      const path = document.createElementNS(svgNS, 'path');
      path.setAttribute('fill', cfg.color);
      path.setAttribute('d', cfg.paths[0]);

      // SMIL animate between paths
      const animate = document.createElementNS(svgNS, 'animate');
      animate.setAttribute('attributeName', 'd');
      animate.setAttribute('dur', `${cfg.duration}s`);
      animate.setAttribute('repeatCount', 'indefinite');
      animate.setAttribute('calcMode', 'spline');
      animate.setAttribute('keySplines', '0.45 0 0.55 1; 0.45 0 0.55 1; 0.45 0 0.55 1');
      animate.setAttribute('values', [...cfg.paths, cfg.paths[0]].join(';'));
      animate.setAttribute('begin', `${cfg.delay}s`);

      path.appendChild(animate);
      svgEl.appendChild(path);

      // Float the whole blob slowly
      const floatAnim = document.createElementNS(svgNS, 'animateTransform');
      floatAnim.setAttribute('attributeName', 'transform');
      floatAnim.setAttribute('type', 'translate');
      floatAnim.setAttribute('dur', `${cfg.duration * 1.4}s`);
      floatAnim.setAttribute('repeatCount', 'indefinite');
      floatAnim.setAttribute('calcMode', 'spline');
      floatAnim.setAttribute('keySplines', '0.45 0 0.55 1; 0.45 0 0.55 1');
      const dx = 18 + bi * 8, dy = 14 + bi * 6;
      floatAnim.setAttribute('values', `0,0; ${dx},${dy}; 0,0`);
      floatAnim.setAttribute('begin', `${cfg.delay * 0.8}s`);
      svgEl.appendChild(floatAnim);

      blobContainer.appendChild(svgEl);
    });

    // ── Canvas orbs ────────────────────────────────────────────────────
    function drawOrbs() {
      ctx.clearRect(0, 0, W, H);
      orbs.forEach(orb => {
        orb.x += orb.vx;
        orb.y += orb.vy;
        if (orb.x < -orb.r)    orb.x = W + orb.r;
        if (orb.x > W + orb.r) orb.x = -orb.r;
        if (orb.y < -orb.r)    orb.y = H + orb.r;
        if (orb.y > H + orb.r) orb.y = -orb.r;

        const g = ctx.createRadialGradient(orb.x, orb.y, 0, orb.x, orb.y, orb.r);
        g.addColorStop(0, orb.color.replace(')', ', 1)').replace('rgba', 'rgba').replace(/, [^,]+\)$/, `, 0.8)`));
        g.addColorStop(1, orb.color.replace(/[\d.]+\)$/, '0)'));
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(orb.x, orb.y, orb.r, 0, Math.PI * 2);
        ctx.fill();
      });
      requestAnimationFrame(drawOrbs);
    }

    drawOrbs();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();