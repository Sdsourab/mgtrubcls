/**
 * UniSync — Warm Organic Background v2.0
 * Base: #FCF5E8 · Accents: #BC6F37 · #CDA96A · #8E8946 · #6A632B
 * Technique: SMIL SVG blob morphing + canvas drifting radial orbs
 */
(function () {
  'use strict';

  const BLOBS = [
    {
      fill: 'rgba(188,111,55,0.11)',
      size: 680, cx: -14, cy: -10,
      dur: 26, delay: 0,
      paths: [
        'M460,290C430,360,350,405,275,412C200,419,130,390,85,345C40,300,20,240,38,185C56,130,115,80,180,57C245,34,318,38,380,68C442,98,490,150,500,205C510,260,490,220,460,290Z',
        'M445,278C412,352,330,398,254,407C178,416,108,387,68,340C28,293,14,232,33,176C52,120,110,70,175,49C240,28,314,34,372,66C430,98,474,155,482,213C490,271,478,204,445,278Z',
        'M472,302C440,374,358,416,280,420C202,424,128,395,84,347C40,299,24,235,44,178C64,121,126,72,194,51C262,30,336,42,395,76C454,110,496,168,502,227C508,286,504,230,472,302Z',
      ],
    },
    {
      fill: 'rgba(205,169,106,0.09)',
      size: 560, cx: 52, cy: 44,
      dur: 33, delay: -11,
      paths: [
        'M405,270C376,338,304,382,238,392C172,402,112,375,74,330C36,285,22,225,40,170C58,115,108,68,166,46C224,24,290,26,345,54C400,82,440,136,452,194C464,252,434,202,405,270Z',
        'M418,281C388,351,314,393,246,401C178,409,116,380,78,335C40,290,28,228,48,172C68,116,120,70,180,50C240,30,308,34,364,64C420,94,458,150,468,210C478,270,448,211,418,281Z',
        'M392,258C362,328,290,374,223,385C156,396,95,369,57,324C19,279,8,218,28,163C48,108,100,62,160,42C220,22,288,28,344,58C400,88,440,144,450,203C460,262,422,188,392,258Z',
      ],
    },
    {
      fill: 'rgba(142,137,70,0.08)',
      size: 480, cx: 60, cy: 54,
      dur: 38, delay: -19,
      paths: [
        'M366,244C338,308,268,352,203,362C138,372,80,344,45,300C10,256,-2,198,16,144C34,90,86,46,146,28C206,10,274,16,328,48C382,80,420,136,428,194C436,252,394,180,366,244Z',
        'M378,255C350,318,282,360,217,370C152,380,93,352,58,308C23,264,12,206,32,152C52,98,106,56,168,40C230,24,298,32,352,66C406,100,442,158,448,218C454,278,406,192,378,255Z',
        'M354,233C325,298,255,344,189,355C123,366,63,339,28,295C-7,251,-16,192,4,137C24,82,78,38,140,22C202,6,272,14,328,48C384,82,420,140,426,200C432,260,383,168,354,233Z',
      ],
    },
    {
      fill: 'rgba(106,99,43,0.06)',
      size: 380, cx: 70, cy: 60,
      dur: 44, delay: -28,
      paths: [
        'M302,200C278,254,218,292,160,300C102,308,50,282,22,242C-6,202,-12,152,8,106C28,60,72,26,122,16C172,6,230,18,276,50C322,82,350,134,354,186C358,238,326,146,302,200Z',
        'M314,208C290,264,228,300,170,308C112,316,60,290,32,250C4,210,-4,158,16,112C36,66,82,34,134,26C186,18,244,32,290,66C336,100,360,154,362,208C364,262,338,152,314,208Z',
        'M290,192C266,248,204,286,146,295C88,304,36,279,10,239C-16,199,-20,148,2,102C24,56,70,24,122,16C174,8,234,22,280,56C326,90,350,146,352,200C354,254,314,136,290,192Z',
      ],
    },
  ];

  const ORB_CFGS = [
    { c:[188,111, 55], op:0.08, rMin:90,  rMax:180 },
    { c:[205,169,106], op:0.06, rMin:70,  rMax:150 },
    { c:[142,137, 70], op:0.05, rMin:100, rMax:200 },
    { c:[188,111, 55], op:0.04, rMin:60,  rMax:120 },
    { c:[106, 99, 43], op:0.05, rMin:80,  rMax:160 },
    { c:[205,169,106], op:0.04, rMin:50,  rMax:110 },
    { c:[188,111, 55], op:0.03, rMin:120, rMax:220 },
  ];

  function init() {
    const canvas = document.getElementById('bgCanvas');
    const blobWrap = document.getElementById('bgBlobs');
    if (!canvas || !blobWrap) return;

    /* Canvas orbs */
    const ctx = canvas.getContext('2d');
    let W, H, orbs = [];

    const resize = () => {
      W = canvas.width  = window.innerWidth;
      H = canvas.height = window.innerHeight;
      orbs = ORB_CFGS.map(cfg => ({
        x:  Math.random() * W,
        y:  Math.random() * H,
        r:  cfg.rMin + Math.random() * (cfg.rMax - cfg.rMin),
        vx: (Math.random() - 0.5) * 0.20,
        vy: (Math.random() - 0.5) * 0.20,
        c:  cfg.c,
        op: cfg.op,
      }));
    };
    resize();
    window.addEventListener('resize', resize, { passive: true });

    (function tick() {
      ctx.clearRect(0, 0, W, H);
      for (const o of orbs) {
        o.x += o.vx;  o.y += o.vy;
        if (o.x < -o.r)    o.x = W + o.r;
        if (o.x > W + o.r) o.x = -o.r;
        if (o.y < -o.r)    o.y = H + o.r;
        if (o.y > H + o.r) o.y = -o.r;
        const g = ctx.createRadialGradient(o.x, o.y, 0, o.x, o.y, o.r);
        g.addColorStop(0,   `rgba(${o.c},${o.op})`);
        g.addColorStop(0.5, `rgba(${o.c},${o.op * 0.45})`);
        g.addColorStop(1,   `rgba(${o.c},0)`);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(o.x, o.y, o.r, 0, Math.PI * 2);
        ctx.fill();
      }
      requestAnimationFrame(tick);
    })();

    /* SVG blob morphing */
    const NS = 'http://www.w3.org/2000/svg';
    BLOBS.forEach((cfg, i) => {
      const svg = document.createElementNS(NS, 'svg');
      svg.setAttribute('viewBox', '0 0 500 500');
      Object.assign(svg.style, {
        position: 'absolute', width: cfg.size + 'px', height: cfg.size + 'px',
        left: cfg.cx + '%', top: cfg.cy + '%',
        pointerEvents: 'none', willChange: 'transform', overflow: 'visible',
      });

      const path = document.createElementNS(NS, 'path');
      path.setAttribute('fill', cfg.fill);
      path.setAttribute('d', cfg.paths[0]);

      const aD = document.createElementNS(NS, 'animate');
      aD.setAttribute('attributeName', 'd');
      aD.setAttribute('dur', `${cfg.dur}s`);
      aD.setAttribute('repeatCount', 'indefinite');
      aD.setAttribute('calcMode', 'spline');
      aD.setAttribute('keyTimes', '0;0.33;0.66;1');
      aD.setAttribute('keySplines', '0.42 0 0.58 1;0.42 0 0.58 1;0.42 0 0.58 1');
      aD.setAttribute('values', [...cfg.paths, cfg.paths[0]].join(';'));
      aD.setAttribute('begin', `${cfg.delay}s`);
      path.appendChild(aD);
      svg.appendChild(path);

      const aT = document.createElementNS(NS, 'animateTransform');
      aT.setAttribute('attributeName', 'transform');
      aT.setAttribute('type', 'translate');
      aT.setAttribute('dur', `${cfg.dur * 1.7}s`);
      aT.setAttribute('repeatCount', 'indefinite');
      aT.setAttribute('calcMode', 'spline');
      aT.setAttribute('keyTimes', '0;0.5;1');
      aT.setAttribute('keySplines', '0.42 0 0.58 1;0.42 0 0.58 1');
      const dx = 14 + i * 6, dy = 10 + i * 5;
      aT.setAttribute('values', `0,0;${dx},${dy};0,0`);
      aT.setAttribute('begin', `${cfg.delay * 0.8}s`);
      svg.appendChild(aT);

      blobWrap.appendChild(svg);
    });
  }

  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', init)
    : init();
})();