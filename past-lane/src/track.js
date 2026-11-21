import * as THREE from 'three';

export function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const THEMES = {
  sunset: { sky: [0x1b0b3a, 0xff5e62, 0xffc371], fog: 0xb0506a, ground: 0x2a1238, road: '#2b2438', line: '#ffd9a0', wall: 0xff3d81, scen: 'palms', sun: 0xffb36b, amb: 0.95, accent: '#ff5e9c', key: 0 },
  pines: { sky: [0x2c6fbb, 0x9fd3f5, 0xf4f1d0], fog: 0xb8dcea, ground: 0x3f7a3a, road: '#3a3d42', line: '#ffffff', wall: 0xffe14d, scen: 'pines', sun: 0xfff3d0, amb: 1.25, accent: '#ffe14d', key: 5 },
  docks: { sky: [0x02030c, 0x0b1440, 0x2a1a5e], fog: 0x0b1030, ground: 0x070a18, road: '#14161f', line: '#49e6ff', wall: 0x20e3ff, scen: 'city', sun: 0x8fa8ff, amb: 0.75, accent: '#20e3ff', key: 3 },
  salt: { sky: [0x4aa3e0, 0xcfeaf7, 0xffffff], fog: 0xe6f1f5, ground: 0xe9e4d8, road: '#4a4a50', line: '#ffffff', wall: 0xff6a2b, scen: 'rocks', sun: 0xffffff, amb: 1.35, accent: '#ff6a2b', key: 7 },
  aurora: { sky: [0x020818, 0x0c3b4a, 0x3dffb0], fog: 0x0d2a3a, ground: 0xb9d4e6, road: '#1c2530', line: '#aaffe6', wall: 0x3dffb0, scen: 'pines', sun: 0xa8ffe0, amb: 0.9, accent: '#3dffb0', key: 2 },
  canyon: { sky: [0x7a1f0f, 0xf08a4b, 0xffe0a3], fog: 0xd98a5a, ground: 0x9a4a2a, road: '#33262a', line: '#ffe0a3', wall: 0xffffff, scen: 'rocks', sun: 0xffd0a0, amb: 1.1, accent: '#ffb347', key: 9 },
};

export const CIRCUITS = [
  { id: 'c1', name: 'Sunset Loop', theme: 'sunset', seed: 11, laps: 4, pts: 8, vary: 0.22, radius: 150, width: 10 },
  { id: 'c2', name: 'Pine Ridge', theme: 'pines', seed: 27, laps: 5, pts: 10, vary: 0.34, radius: 165, width: 9.5 },
  { id: 'c3', name: 'Neon Docks', theme: 'docks', seed: 5, laps: 5, pts: 12, vary: 0.4, radius: 175, width: 9 },
  { id: 'c4', name: 'Salt Flats', theme: 'salt', seed: 73, laps: 6, pts: 9, vary: 0.3, radius: 200, width: 9 },
  { id: 'c5', name: 'Aurora Pass', theme: 'aurora', seed: 41, laps: 6, pts: 13, vary: 0.45, radius: 185, width: 8.5 },
  { id: 'c6', name: 'Redline Canyon', theme: 'canyon', seed: 98, laps: 7, pts: 14, vary: 0.48, radius: 195, width: 8 },
];

export function dailyCircuit() {
  const d = new Date();
  const n = d.getUTCFullYear() * 10000 + (d.getUTCMonth() + 1) * 100 + d.getUTCDate();
  const r = rng(n);
  const themes = Object.keys(THEMES);
  return {
    id: 'daily-' + n, name: 'Daily Circuit', theme: themes[Math.floor(r() * themes.length)], seed: n,
    laps: 6, pts: 9 + Math.floor(r() * 6), vary: 0.28 + r() * 0.2, radius: 160 + r() * 40, width: 9, daily: true,
  };
}

function canvasTex(w, h, draw) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

export function buildTrack(def) {
  const th = THEMES[def.theme];
  const r = rng(def.seed);
  const group = new THREE.Group();
  const ctrl = [];
  for (let i = 0; i < def.pts; i++) {
    const a = (i / def.pts) * Math.PI * 2;
    const rad = def.radius * (1 + (r() * 2 - 1) * def.vary);
    ctrl.push(new THREE.Vector3(Math.cos(a) * rad, 0, Math.sin(a) * rad * 0.8));
  }
  const curve = new THREE.CatmullRomCurve3(ctrl, true, 'centripetal');
  const length = curve.getLength();
  const M = Math.round(length / 2);
  const sp = curve.getSpacedPoints(M);
  const px = new Float32Array(M), pz = new Float32Array(M), tx = new Float32Array(M), tz = new Float32Array(M), curv = new Float32Array(M);
  for (let i = 0; i < M; i++) { px[i] = sp[i].x; pz[i] = sp[i].z; }
  for (let i = 0; i < M; i++) {
    const a = (i + M - 1) % M, b = (i + 1) % M;
    let dx = px[b] - px[a], dz = pz[b] - pz[a];
    const l = Math.hypot(dx, dz);
    tx[i] = dx / l; tz[i] = dz / l;
  }
  for (let i = 0; i < M; i++) {
    const a = (i + M - 3) % M, b = (i + 3) % M;
    const h1 = Math.atan2(tx[a], tz[a]), h2 = Math.atan2(tx[b], tz[b]);
    let d = h2 - h1;
    while (d > Math.PI) d -= Math.PI * 2;
    while (d < -Math.PI) d += Math.PI * 2;
    curv[i] = d / (6 * (length / M));
  }
  const W = def.width;
  const seg = length / M;

  // road
  const strip = (off0, off1, y, uScale, vScale) => {
    const pos = [], uv = [], idx = [];
    for (let i = 0; i <= M; i++) {
      const k = i % M;
      const nx = tz[k], nz = -tx[k];
      pos.push(px[k] + nx * off0, y, pz[k] + nz * off0, px[k] + nx * off1, y, pz[k] + nz * off1);
      uv.push(0, i * seg * vScale, uScale, i * seg * vScale);
      if (i < M) { const o = i * 2; idx.push(o, o + 1, o + 2, o + 1, o + 3, o + 2); }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx);
    g.computeVertexNormals();
    return g;
  };
  const roadTex = canvasTex(256, 256, (c, w, h) => {
    c.fillStyle = th.road; c.fillRect(0, 0, w, h);
    for (let i = 0; i < 1400; i++) {
      c.fillStyle = `rgba(${r() > 0.5 ? 255 : 0},${r() > 0.5 ? 255 : 0},${r() > 0.5 ? 255 : 0},0.035)`;
      c.fillRect(r() * w, r() * h, 2, 2);
    }
    c.fillStyle = th.line;
    c.fillRect(6, 0, 6, h); c.fillRect(w - 12, 0, 6, h);
    c.globalAlpha = 0.75;
    c.fillRect(w / 2 - 3, 0, 6, h * 0.5);
    c.globalAlpha = 0.3;
    c.fillRect(w / 4 - 2, h * 0.25, 4, h * 0.3); c.fillRect((3 * w) / 4 - 2, h * 0.25, 4, h * 0.3);
  });
  const road = new THREE.Mesh(strip(W, -W, 0.02, 1, 1 / 12), new THREE.MeshStandardMaterial({ map: roadTex, roughness: 0.85, metalness: 0.05, side: THREE.DoubleSide }));
  group.add(road);
  const curbTex = canvasTex(64, 64, (c, w, h) => {
    c.fillStyle = '#f4f4f4'; c.fillRect(0, 0, w, h);
    c.fillStyle = '#e02b3c'; c.fillRect(0, 0, w, h / 2);
  });
  const curbMat = new THREE.MeshStandardMaterial({ map: curbTex, roughness: 0.7, side: THREE.DoubleSide });
  group.add(new THREE.Mesh(strip(W + 1.4, W, 0.05, 1, 1 / 5), curbMat));
  group.add(new THREE.Mesh(strip(-W, -W - 1.4, 0.05, 1, 1 / 5), curbMat));

  // glowing walls
  const wall = (off) => {
    const pos = [], idx = [];
    for (let i = 0; i <= M; i++) {
      const k = i % M;
      const nx = tz[k], nz = -tx[k];
      const x = px[k] + nx * off, z = pz[k] + nz * off;
      pos.push(x, 0, z, x, 1.1, z);
      if (i < M) { const o = i * 2; idx.push(o, o + 1, o + 2, o + 1, o + 3, o + 2); }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setIndex(idx);
    return new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: th.wall, side: THREE.DoubleSide, transparent: true, opacity: 0.85 }));
  };
  group.add(wall(W + 1.5), wall(-W - 1.5));

  // ground
  const ground = new THREE.Mesh(new THREE.CircleGeometry(1400, 48), new THREE.MeshStandardMaterial({ color: th.ground, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -0.05;
  group.add(ground);

  // start line + gantry
  const nx0 = tz[0], nz0 = -tx[0];
  const chk = canvasTex(128, 32, (c, w, h) => {
    for (let x = 0; x < 16; x++) for (let y = 0; y < 4; y++) { c.fillStyle = (x + y) % 2 ? '#111' : '#fff'; c.fillRect(x * 8, y * 8, 8, 8); }
  });
  const line = new THREE.Mesh(new THREE.PlaneGeometry(W * 2, 3), new THREE.MeshBasicMaterial({ map: chk }));
  line.rotation.x = -Math.PI / 2; line.rotation.z = -Math.atan2(tx[0], tz[0]);
  line.position.set(px[0], 0.04, pz[0]);
  group.add(line);
  const gm = new THREE.MeshStandardMaterial({ color: 0x22242c, roughness: 0.5, metalness: 0.6 });
  for (const s of [-1, 1]) {
    const p = new THREE.Mesh(new THREE.BoxGeometry(0.8, 9, 0.8), gm);
    p.position.set(px[0] + nx0 * s * (W + 2.4), 4.5, pz[0] + nz0 * s * (W + 2.4));
    group.add(p);
  }
  const beam = new THREE.Mesh(new THREE.BoxGeometry(W * 2 + 5.6, 1.6, 1), new THREE.MeshBasicMaterial({ color: th.wall }));
  beam.position.set(px[0], 9, pz[0]); beam.rotation.y = Math.atan2(tx[0], tz[0]) + Math.PI / 2 + Math.PI / 2;
  beam.rotation.y = Math.atan2(nx0, nz0) + Math.PI / 2;
  group.add(beam);

  // scenery
  const distToTrack = (x, z) => {
    let best = 1e9;
    for (let i = 0; i < M; i += 3) { const d = (px[i] - x) ** 2 + (pz[i] - z) ** 2; if (d < best) best = d; }
    return Math.sqrt(best);
  };
  const spots = [];
  for (let i = 0; i < M; i += 2) {
    for (const s of [-1, 1]) {
      if (r() < 0.45) continue;
      const off = s * (W + 6 + r() * r() * 70);
      const x = px[i] + tz[i] * off, z = pz[i] - tx[i] * off;
      if (distToTrack(x, z) > W + 5) spots.push([x, z, r(), r()]);
    }
  }
  for (let i = 0; i < 260; i++) {
    const a = r() * Math.PI * 2, d = def.radius * (1.5 + r() * 2.2);
    const x = Math.cos(a) * d, z = Math.sin(a) * d;
    if (distToTrack(x, z) > W + 8) spots.push([x, z, r(), r() + 0.6]);
  }
  const dummy = new THREE.Object3D();
  const inst = (geo, mat, list, fn) => {
    const m = new THREE.InstancedMesh(geo, mat, list.length);
    list.forEach((s, i) => { fn(s, dummy); dummy.updateMatrix(); m.setMatrixAt(i, dummy.matrix); });
    m.instanceMatrix.needsUpdate = true;
    group.add(m);
    return m;
  };
  if (th.scen === 'pines' || th.scen === 'palms') {
    const leaf = th.scen === 'pines' ? (def.theme === 'aurora' ? 0x2f6f66 : 0x1f6b3a) : 0x1d4d4f;
    const trunkG = new THREE.CylinderGeometry(0.35, 0.5, 1, 6);
    inst(trunkG, new THREE.MeshStandardMaterial({ color: 0x5a3b28, roughness: 1 }), spots, (s, d) => {
      const h = th.scen === 'palms' ? 7 + s[2] * 5 : 2.5;
      d.position.set(s[0], h / 2, s[1]); d.scale.set(1, h, 1); d.rotation.set(0, 0, 0);
    });
    if (th.scen === 'pines') {
      const cg = new THREE.ConeGeometry(1, 1, 7);
      const cm = new THREE.MeshStandardMaterial({ color: leaf, roughness: 0.9, flatShading: true });
      for (let k = 0; k < 3; k++) inst(cg, cm, spots, (s, d) => {
        const sc = 1 + s[2] * 1.4;
        d.position.set(s[0], 2.5 + k * 2.1 * sc + 1.6 * sc, s[1]);
        d.scale.set((3.4 - k * 0.9) * sc, 3.6 * sc, (3.4 - k * 0.9) * sc); d.rotation.set(0, s[3] * 6, 0);
      });
    } else {
      const fg = new THREE.ConeGeometry(1, 1, 5);
      const fm = new THREE.MeshStandardMaterial({ color: leaf, roughness: 0.8, flatShading: true });
      for (let k = 0; k < 5; k++) inst(fg, fm, spots, (s, d) => {
        const h = 7 + s[2] * 5, a = s[3] * 6 + (k * Math.PI * 2) / 5;
        d.position.set(s[0] + Math.cos(a) * 1.8, h - 0.2, s[1] + Math.sin(a) * 1.8);
        d.scale.set(0.9, 4.6, 0.35); d.rotation.set(0, 0, 0); d.rotation.order = 'YXZ';
        d.rotation.y = -a + Math.PI / 2; d.rotation.x = 1.9;
      });
    }
  } else if (th.scen === 'city') {
    const wt = canvasTex(64, 128, (c, w, h) => {
      c.fillStyle = '#0a0d1c'; c.fillRect(0, 0, w, h);
      for (let y = 4; y < h; y += 10) for (let x = 4; x < w; x += 10) {
        if (r() < 0.55) { c.fillStyle = r() < 0.5 ? '#ffd27a' : (r() < 0.5 ? '#49e6ff' : '#ff4fa3'); c.globalAlpha = 0.4 + r() * 0.6; c.fillRect(x, y, 5, 6); }
      }
    });
    const far = spots.filter((s, i) => i % 2 === 0);
    inst(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ map: wt }), far, (s, d) => {
      const h = 10 + s[2] * s[2] * 60, w = 7 + s[3] * 8;
      d.position.set(s[0], h / 2, s[1]); d.scale.set(w, h, w); d.rotation.set(0, s[3] * 3, 0);
    });
  } else {
    const rockC = def.theme === 'canyon' ? 0xb5532c : 0xbfb49e;
    inst(new THREE.DodecahedronGeometry(1, 0), new THREE.MeshStandardMaterial({ color: rockC, roughness: 1, flatShading: true }), spots, (s, d) => {
      const big = def.theme === 'canyon' ? 3 + s[2] * s[2] * 22 : 1 + s[2] * s[2] * 7;
      d.position.set(s[0], big * 0.4, s[1]); d.scale.set(big, big * (0.7 + s[3] * (def.theme === 'canyon' ? 1.8 : 0.5)), big); d.rotation.set(s[2] * 3, s[3] * 6, 0);
    });
  }
  // light posts along track
  const posts = [];
  for (let i = 0; i < M; i += 14) posts.push([i, (i / 14) % 2 ? 1 : -1]);
  inst(new THREE.BoxGeometry(0.3, 6, 0.3), gm, posts, (s, d) => {
    const off = s[1] * (W + 3);
    d.position.set(px[s[0]] + tz[s[0]] * off, 3, pz[s[0]] - tx[s[0]] * off); d.scale.set(1, 1, 1); d.rotation.set(0, 0, 0);
  });
  inst(new THREE.SphereGeometry(0.55, 8, 6), new THREE.MeshBasicMaterial({ color: th.wall }), posts, (s, d) => {
    const off = s[1] * (W + 3);
    d.position.set(px[s[0]] + tz[s[0]] * off, 6.2, pz[s[0]] - tx[s[0]] * off); d.scale.set(1, 1, 1); d.rotation.set(0, 0, 0);
  });

  // sky
  const sky = new THREE.Mesh(new THREE.SphereGeometry(1300, 24, 16), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { top: { value: new THREE.Color(th.sky[0]) }, mid: { value: new THREE.Color(th.sky[1]) }, bot: { value: new THREE.Color(th.sky[2]) } },
    vertexShader: 'varying vec3 vp; void main(){ vp = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
    fragmentShader: 'varying vec3 vp; uniform vec3 top; uniform vec3 mid; uniform vec3 bot; void main(){ float h = normalize(vp).y; vec3 c = h > 0.18 ? mix(mid, top, smoothstep(0.18, 0.75, h)) : mix(bot, mid, smoothstep(-0.02, 0.18, h)); gl_FragColor = vec4(c, 1.0); }',
  }));
  group.add(sky);
  const sun = new THREE.Mesh(new THREE.CircleGeometry(90, 40), new THREE.MeshBasicMaterial({ color: th.sun, fog: false, transparent: true, opacity: def.theme === 'docks' ? 0.5 : 0.95 }));
  sun.position.set(-700, 150, -900); sun.lookAt(0, 0, 0);
  group.add(sun);
  if (def.theme === 'docks' || def.theme === 'aurora' || def.theme === 'sunset') {
    const sg = new THREE.BufferGeometry(), sv = [];
    for (let i = 0; i < 900; i++) {
      const a = r() * Math.PI * 2, e = 0.15 + r() * 1.3;
      sv.push(Math.cos(a) * Math.cos(e) * 1200, Math.sin(e) * 1200, Math.sin(a) * Math.cos(e) * 1200);
    }
    sg.setAttribute('position', new THREE.Float32BufferAttribute(sv, 3));
    group.add(new THREE.Points(sg, new THREE.PointsMaterial({ color: 0xffffff, size: 3, sizeAttenuation: false, fog: false, transparent: true, opacity: 0.8 })));
  }

  return { def, th, group, M, px, pz, tx, tz, curv, W, length, seg };
}

// nearest sample index near a hint
export function nearest(t, x, z, hint) {
  let best = hint, bd = 1e12;
  for (let o = -10; o <= 10; o++) {
    const i = (hint + o + t.M) % t.M;
    const d = (t.px[i] - x) ** 2 + (t.pz[i] - z) ** 2;
    if (d < bd) { bd = d; best = i; }
  }
  return best;
}
