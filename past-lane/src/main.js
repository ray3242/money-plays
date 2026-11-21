import * as THREE from 'three';
import { buildTrack, nearest, CIRCUITS, THEMES, dailyCircuit } from './track.js';
import { audio } from './audio.js';

const $ = (id) => document.getElementById(id);
const SAVE_KEY = 'pastlane.v1';
let save = { best: {}, stars: {}, muted: false, seenHelp: false };
try { save = Object.assign(save, JSON.parse(localStorage.getItem(SAVE_KEY) || '{}')); } catch (e) {}
const persist = () => { try { localStorage.setItem(SAVE_KEY, JSON.stringify(save)); } catch (e) {} };
audio.setMuted(save.muted);

// optional portal SDK bridge (only active when a portal SDK script is present)
const portal = {
  sdk: () => (window.CrazyGames && window.CrazyGames.SDK) || null,
  ready: null,
  init() { const s = this.sdk(); if (s && s.init) this.ready = Promise.resolve().then(() => s.init()).then(() => s, () => null); },
  call(fn) { if (this.ready) this.ready.then((s) => { try { if (s && s.game && s.game[fn]) s.game[fn](); } catch (e) {} }); },
};
portal.init();

const renderer = new THREE.WebGLRenderer({ canvas: $('c'), antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(62, 1, 0.3, 3000);
const hemi = new THREE.HemisphereLight(0xffffff, 0x444466, 1);
const dir = new THREE.DirectionalLight(0xffffff, 1.6);
dir.position.set(-0.5, 1, -0.6);
scene.add(hemi, dir);

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  document.body.classList.toggle('portrait', h > w);
}
window.addEventListener('resize', resize);

// ---------- car models ----------
const boxG = new THREE.BoxGeometry(1, 1, 1);
const wheelG = new THREE.CylinderGeometry(0.42, 0.42, 0.36, 12).rotateZ(Math.PI / 2);
function makeCar(ghost, color) {
  const g = new THREE.Group();
  const body = ghost
    ? new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.8 })
    : new THREE.MeshStandardMaterial({ color, roughness: 0.3, metalness: 0.6 });
  const dark = ghost ? new THREE.MeshBasicMaterial({ color: 0x0a0a12, transparent: true, opacity: 0.8 }) : new THREE.MeshStandardMaterial({ color: 0x101018, roughness: 0.2, metalness: 0.8 });
  const add = (mat, sx, sy, sz, x, y, z) => { const m = new THREE.Mesh(boxG, mat); m.scale.set(sx, sy, sz); m.position.set(x, y, z); g.add(m); return m; };
  add(body, 1.9, 0.5, 4.2, 0, 0.55, 0);
  add(body, 1.7, 0.28, 1.0, 0, 0.72, 1.75);
  add(dark, 1.5, 0.48, 1.9, 0, 1.0, -0.25);
  add(body, 2.0, 0.1, 0.5, 0, 1.25, -2.0);
  add(body, 0.12, 0.4, 0.3, 0.8, 1.02, -2.0); add(body, 0.12, 0.4, 0.3, -0.8, 1.02, -2.0);
  const lightMat = new THREE.MeshBasicMaterial({ color: ghost ? 0xffffff : 0xfff2c0 });
  add(lightMat, 0.4, 0.14, 0.1, 0.62, 0.62, 2.12); add(lightMat, 0.4, 0.14, 0.1, -0.62, 0.62, 2.12);
  const tail = new THREE.MeshBasicMaterial({ color: 0xff2030 });
  add(tail, 1.6, 0.12, 0.1, 0, 0.7, -2.12);
  g.userData.wheels = [];
  for (const [x, z] of [[0.95, 1.35], [-0.95, 1.35], [0.95, -1.35], [-0.95, -1.35]]) {
    const w = new THREE.Mesh(wheelG, dark); w.position.set(x, 0.42, z); g.add(w); g.userData.wheels.push(w);
  }
  if (ghost) {
    const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 40, 6, 1, true), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending, depthWrite: false, fog: false }));
    beam.position.y = 21; g.add(beam);
    const ring = new THREE.Mesh(new THREE.RingGeometry(2.4, 2.9, 24), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6, side: THREE.DoubleSide, depthWrite: false }));
    ring.rotation.x = -Math.PI / 2; ring.position.y = 0.08; g.add(ring);
    g.userData.mats = [body, dark, beam.material, ring.material];
  } else {
    const flame = new THREE.Mesh(new THREE.ConeGeometry(0.35, 2.4, 8).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0x66ddff, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false }));
    flame.position.set(0, 0.6, -3.3); flame.visible = false; g.add(flame); g.userData.flame = flame;
    const sh = new THREE.Mesh(new THREE.SphereGeometry(3, 16, 10), new THREE.MeshBasicMaterial({ color: 0x66ddff, transparent: true, opacity: 0.0, blending: THREE.AdditiveBlending, depthWrite: false }));
    sh.position.y = 0.8; g.add(sh); g.userData.shield = sh;
  }
  return g;
}
const playerCar = makeCar(false, 0xf2f2f7);
scene.add(playerCar);
const GHOST_COLORS = [0xff3b6b, 0xffa02e, 0xb565ff, 0x2ee6ff, 0x7dff5a, 0xff5ad1, 0xfff04d, 0x5a8bff, 0xff7a5a, 0x4dffc3];

// ---------- state ----------
const REC_HZ = 30, GHOST_SPEED = 0.6, MAX_GHOSTS = 10, MAX_SHIELDS = 3;
const VDC = [0.5, 0.25, 0.75, 0.375, 0.625, 0.125, 0.875, 0.3125, 0.6875, 0.4375];
let track = null, def = null, mode = 'menu', selected = 0;
const circuits = [...CIRCUITS, dailyCircuit()];
const P = { x: 0, z: 0, h: 0, vx: 0, vz: 0, speed: 0, idx: 0, lat: 0 };
let ghosts = [], rec = [], recT = 0;
let lap = 1, half = false, prog = 0, far = 0, raceT = 0, lapT = 0, bestLap = 0, score = 0, shields = 3, nitro = 0, combo = 0, comboT = 0, invuln = 0, shake = 0, nearCount = 0, countdown = 0, cdShown = -1, skid = 0, camH = 0, msgT = 0, wrongT = 0, scrapeT = 0;
const keys = {};
const touch = { left: false, right: false, brake: false, nitro: false };

function unlocked(i) { return i === 0 || circuits[i].daily || (save.stars[circuits[i - 1].id] || 0) > 0; }

function loadCircuit(i) {
  selected = i; def = circuits[i];
  if (track) {
    scene.remove(track.group);
    track.group.traverse((o) => { if (o.isInstancedMesh) o.dispose(); if (o.geometry) o.geometry.dispose(); if (o.material) { if (o.material.map) o.material.map.dispose(); o.material.dispose(); } });
  }
  track = buildTrack(def);
  scene.add(track.group);
  const th = track.th;
  scene.fog = new THREE.Fog(th.fog, 80, 720);
  hemi.intensity = th.amb; hemi.color.set(th.sky[1]).lerp(new THREE.Color(0xffffff), 0.6); hemi.groundColor.set(th.ground);
  dir.color.set(th.sun);
  document.documentElement.style.setProperty('--accent', th.accent);
  clearGhosts();
  placePlayer();
}
function clearGhosts() {
  for (const g of ghosts) {
    scene.remove(g.mesh);
    g.mesh.traverse((o) => { if (o.geometry && o.geometry !== boxG && o.geometry !== wheelG) o.geometry.dispose(); if (o.material) o.material.dispose(); });
  }
  ghosts = [];
}
function placePlayer() {
  const i = 3;
  P.idx = i; P.x = track.px[i]; P.z = track.pz[i]; P.h = Math.atan2(track.tx[i], track.tz[i]); P.vx = P.vz = P.speed = 0; P.lat = 0;
  camH = P.h;
  playerCar.position.set(P.x, 0, P.z); playerCar.rotation.set(0, P.h, 0);
}

function startRace() {
  audio.init(); audio.music(track.th.key);
  clearGhosts(); placePlayer();
  rec = []; recT = 0; lap = 1; half = false; prog = 0; far = 0; raceT = 0; lapT = 0; bestLap = 0; score = 0; shields = MAX_SHIELDS; nitro = 0.35; combo = 0; invuln = 0; nearCount = 0; shake = 0;
  countdown = 3.2; cdShown = -1; mode = 'countdown';
  show('hud'); $('touch').style.display = isTouch ? 'block' : 'none';
  updateHud(true);
  if (!save.seenHelp) { banner('Dodge your own past laps', 3.2); save.seenHelp = true; persist(); }
}

function addGhost() {
  if (rec.length < REC_HZ * 3 * 3) return;
  const data = new Float32Array(rec);
  const k = ghosts.length;
  let g;
  if (k >= MAX_GHOSTS) { g = ghosts.shift(); ghosts.push(g); } else {
    g = { mesh: makeCar(true, GHOST_COLORS[k % GHOST_COLORS.length]) };
    scene.add(g.mesh); ghosts.push(g);
  }
  g.data = data; g.n = data.length / 3; g.t = VDC[k % VDC.length] * g.n; g.age = 0; g.minD = 1e9; g.hit = false; g.x = 0; g.z = 0; g.d = 1e9;
}

function banner(text, t = 1.6, cls = '') {
  const b = $('banner'); b.textContent = text; b.className = 'on ' + cls; msgT = t;
}

// ---------- simulation ----------
const DT = 1 / 120;
function step() {
  const t = track;
  if (mode === 'countdown') {
    countdown -= DT;
    const n = Math.ceil(countdown - 0.2);
    if (n !== cdShown) { cdShown = n; if (n > 0) { banner(String(n), 0.9, 'big'); audio.beep(false); } else { banner('GO!', 0.9, 'big'); audio.beep(true); } }
    if (countdown <= 0.2) { mode = 'race'; portal.call('gameplayStart'); }
    return;
  }
  if (mode !== 'race') return;
  raceT += DT; lapT += DT;
  const left = keys.ArrowLeft || keys.KeyA || touch.left, right = keys.ArrowRight || keys.KeyD || touch.right;
  const brake = keys.ArrowDown || keys.KeyS || touch.brake;
  const wantNitro = (keys.Space || keys.ShiftLeft || keys.ShiftRight || keys.ArrowUp || keys.KeyW || touch.nitro) && nitro > 0.02;
  const steer = (right ? 1 : 0) - (left ? 1 : 0);
  const fx = Math.sin(P.h), fz = Math.cos(P.h);
  let vf = P.vx * fx + P.vz * fz, vl = P.vx * -fz + P.vz * fx;
  const top = wantNitro ? 84 : 62;
  if (brake) vf -= 60 * DT * Math.sign(vf || 1) * (vf > 0 ? 1 : 0);
  else vf += (top - vf) * (wantNitro ? 1.5 : 0.7) * DT + (vf < 20 ? 14 * DT : 0);
  if (wantNitro) nitro = Math.max(0, nitro - DT * 0.28);
  vf = Math.max(0, vf);
  const grip = 5.5 - Math.min(2.5, Math.abs(steer) * vf * 0.03);
  vl *= Math.exp(-grip * DT);
  P.h -= steer * (1.75 - vf * 0.006) * Math.min(1, vf / 12) * DT;
  const nfx = Math.sin(P.h), nfz = Math.cos(P.h);
  P.vx = nfx * vf + -nfz * vl; P.vz = nfz * vf + nfx * vl;
  // heading change converts some forward velocity into lateral slip
  const cross = fx * nfz - fz * nfx;
  P.vx += -nfz * cross * vf * 0.35; P.vz += nfx * cross * vf * 0.35;
  P.x += P.vx * DT; P.z += P.vz * DT;
  P.speed = Math.hypot(P.vx, P.vz);
  skid = Math.min(1, Math.abs(vl) / 9);

  // track constraint
  const prev = P.idx;
  P.idx = nearest(t, P.x, P.z, P.idx);
  const i = P.idx, nx = t.tz[i], nz = -t.tx[i];
  const lat = (P.x - t.px[i]) * nx + (P.z - t.pz[i]) * nz;
  P.lat = lat;
  const lim = t.W + 0.4;
  if (Math.abs(lat) > lim) {
    const over = Math.abs(lat) - lim, s = Math.sign(lat);
    P.x -= nx * over * s; P.z -= nz * over * s;
    const vn = P.vx * nx + P.vz * nz;
    if (vn * s > 0) {
      P.vx -= nx * vn * 1.25; P.vz -= nz * vn * 1.25;
      const hit = Math.abs(vn);
      const drag = Math.max(0.55, 1 - hit * 0.02);
      P.vx *= drag; P.vz *= drag;
      // nudge heading along the wall
      const th = Math.atan2(t.tx[i], t.tz[i]);
      let dh = th - P.h; while (dh > Math.PI) dh -= 2 * Math.PI; while (dh < -Math.PI) dh += 2 * Math.PI;
      if (Math.abs(dh) < Math.PI / 2) P.h += dh * 0.25;
      if (hit > 4) { shake = Math.max(shake, Math.min(0.6, hit * 0.03)); if (scrapeT <= 0) { audio.scrape(); scrapeT = 0.2; } }
    }
  }
  scrapeT -= DT;

  // progress
  let di = P.idx - prev; if (di > t.M / 2) di -= t.M; if (di < -t.M / 2) di += t.M;
  prog += di;
  if (prog > far) { score += (prog - far) * t.seg * (1 + combo * 0.1); far = prog; }
  if (far > t.M * 0.45) half = true;
  if (half && far > t.M * 0.9 && prev > t.M * 0.8 && P.idx < t.M * 0.2) { prog -= t.M; far = Math.max(0, prog); lapDone(); if (mode !== 'race') return; }
  const dot = nfx * t.tx[i] + nfz * t.tz[i];
  wrongT = dot < -0.3 && P.speed > 5 ? wrongT + DT : 0;

  // record
  recT += DT;
  while (recT >= 1 / REC_HZ) { recT -= 1 / REC_HZ; rec.push(P.x, P.z, P.h); }

  // ghosts
  invuln = Math.max(0, invuln - DT);
  if (combo > 0) { comboT -= DT; if (comboT <= 0) combo = 0; }
  for (const g of ghosts) {
    g.age += DT;
    g.t += DT * REC_HZ * GHOST_SPEED;
    const u = g.n - 1 - (g.t % g.n), u0 = Math.floor(u), f = u - u0;
    const a = ((u0 % g.n) + g.n) % g.n, b = (a + 1) % g.n;
    const jump = Math.hypot(g.data[a * 3] - g.data[b * 3], g.data[a * 3 + 1] - g.data[b * 3 + 1]);
    g.x = g.data[a * 3] + (g.data[b * 3] - g.data[a * 3]) * f;
    g.z = g.data[a * 3 + 1] + (g.data[b * 3 + 1] - g.data[a * 3 + 1]) * f;
    let ha = g.data[a * 3 + 2], hb = g.data[b * 3 + 2], dh = hb - ha;
    while (dh > Math.PI) dh -= 2 * Math.PI; while (dh < -Math.PI) dh += 2 * Math.PI;
    g.h = ha + dh * f + Math.PI;
    g.seam = jump > 6 ? 0.4 : Math.max(0, (g.seam || 0) - DT);
    const d = Math.hypot(g.x - P.x, g.z - P.z);
    g.d = d;
    const solid = g.age > 1.5 && g.seam <= 0;
    if (d < 14) {
      if (solid) g.minD = Math.min(g.minD, d);
      if (solid && d < 2.3 && invuln <= 0 && !g.hit) { crash(g); if (mode !== 'race') return; }
    } else {
      if (g.minD < 5.2 && !g.hit) nearMiss(g.minD);
      g.minD = 1e9; g.hit = false;
    }
  }
}

function nearMiss(d) {
  combo = Math.min(9, combo + 1); comboT = 5; nearCount++;
  const pts = Math.round((d < 3.4 ? 250 : 120) * combo);
  score += pts; nitro = Math.min(1, nitro + (d < 3.4 ? 0.3 : 0.2));
  banner((d < 3.4 ? 'PAPER THIN! ' : 'NEAR MISS ') + '+' + pts, 1.1, 'good');
  audio.near(combo);
}
function crash(g) {
  g.hit = true; shields--; invuln = 2.2; combo = 0; shake = 1;
  P.vx *= 0.25; P.vz *= 0.25;
  audio.crash();
  $('flash').className = 'on'; setTimeout(() => ($('flash').className = ''), 120);
  if (shields <= 0) return finish(false);
  banner('You hit your past self', 1.4, 'bad');
}
function lapDone() {
  half = false;
  if (!bestLap || lapT < bestLap) bestLap = lapT;
  const bonus = 500 * lap; score += bonus;
  addGhost(); rec = []; recT = 0; lapT = 0;
  if (lap >= def.laps) return finish(true);
  lap++;
  audio.lap();
  banner(lap === def.laps ? 'FINAL LAP' : `LAP ${lap}  +${bonus}`, 1.6, 'good');
}
function finish(won) {
  mode = 'over'; portal.call('gameplayStop');
  if (won) score += shields * 1000;
  score = Math.round(score);
  const id = def.id, old = save.best[id] || 0, isBest = score > old;
  if (isBest) save.best[id] = score;
  let stars = 0;
  if (won) stars = shields >= MAX_SHIELDS ? 3 : shields === 2 ? 2 : 1;
  if (def.daily) stars = lap > 10 ? 3 : lap > 6 ? 2 : lap > 3 ? 1 : 0;
  save.stars[id] = Math.max(save.stars[id] || 0, stars);
  persist();
  if (won || (def.daily && stars)) { audio.win(); if (stars === 3) portal.call('happytime'); } else audio.lose();
  $('overTitle').textContent = won ? 'Circuit clear' : def.daily ? `Out on lap ${lap}` : 'Wrecked by your past';
  $('overStars').textContent = '★'.repeat(stars) + '☆'.repeat(3 - stars);
  $('overScore').textContent = score.toLocaleString();
  $('overBest').textContent = isBest ? 'New best!' : 'Best ' + old.toLocaleString();
  $('overStats').textContent = `${nearCount} near misses · best lap ${bestLap ? bestLap.toFixed(2) + 's' : '-'} · ${ghosts.length} ghosts on track`;
  const nxt = selected + 1 < circuits.length && unlocked(selected + 1) && won;
  $('btnNext').style.display = nxt ? '' : 'none';
  setTimeout(() => { if (mode === 'over') show('over'); }, 900);
}

// ---------- rendering ----------
const mm = $('map'), mctx = mm.getContext('2d');
let mapBox = null;
function drawMap() {
  const t = track, w = mm.width, h = mm.height;
  if (!mapBox || mapBox.t !== t) {
    let x0 = 1e9, x1 = -1e9, z0 = 1e9, z1 = -1e9;
    for (let i = 0; i < t.M; i++) { x0 = Math.min(x0, t.px[i]); x1 = Math.max(x1, t.px[i]); z0 = Math.min(z0, t.pz[i]); z1 = Math.max(z1, t.pz[i]); }
    const s = Math.min((w - 20) / (x1 - x0), (h - 20) / (z1 - z0));
    mapBox = { t, s, ox: w / 2 - ((x0 + x1) / 2) * s, oz: h / 2 - ((z0 + z1) / 2) * s };
  }
  const { s, ox, oz } = mapBox, X = (x) => w - (x * s + ox), Z = (z) => z * s + oz;
  mctx.clearRect(0, 0, w, h);
  mctx.lineJoin = 'round';
  mctx.beginPath();
  for (let i = 0; i <= t.M; i += 2) { const k = i % t.M; i ? mctx.lineTo(X(t.px[k]), Z(t.pz[k])) : mctx.moveTo(X(t.px[k]), Z(t.pz[k])); }
  mctx.closePath();
  mctx.strokeStyle = 'rgba(0,0,0,0.55)'; mctx.lineWidth = 9; mctx.stroke();
  mctx.strokeStyle = 'rgba(255,255,255,0.85)'; mctx.lineWidth = 4; mctx.stroke();
  ghosts.forEach((g, k) => {
    mctx.fillStyle = '#' + GHOST_COLORS[k % GHOST_COLORS.length].toString(16).padStart(6, '0');
    mctx.beginPath(); mctx.arc(X(g.x), Z(g.z), 5, 0, 7); mctx.fill();
  });
  mctx.fillStyle = '#fff'; mctx.strokeStyle = '#000'; mctx.lineWidth = 2;
  mctx.beginPath(); mctx.arc(X(P.x), Z(P.z), 6, 0, 7); mctx.fill(); mctx.stroke();
}

let hudCache = {};
function setText(id, v) { if (hudCache[id] !== v) { hudCache[id] = v; $(id).textContent = v; } }
function updateHud(force) {
  if (force) hudCache = {};
  setText('lap', def.laps === Infinity ? `LAP ${lap}` : `LAP ${Math.min(lap, def.laps)}/${def.laps}`);
  setText('score', Math.round(score).toLocaleString());
  setText('speed', String(Math.round(P.speed * 3.6)));
  setText('shields', '◆'.repeat(Math.max(0, shields)) + '◇'.repeat(MAX_SHIELDS - Math.max(0, shields)));
  setText('combo', combo > 1 ? 'x' + combo : '');
  $('nitroFill').style.transform = `scaleX(${nitro.toFixed(3)})`;
  $('nitroBar').classList.toggle('ready', nitro > 0.02);
  // oncoming warning
  let warn = 0, side = 0;
  const fx = Math.sin(P.h), fz = Math.cos(P.h);
  for (const g of ghosts) {
    if (g.age < 1 || g.d > 150) continue;
    const dx = g.x - P.x, dz = g.z - P.z, ahead = dx * fx + dz * fz;
    if (ahead > 5) { const w = 1 - g.d / 150; if (w > warn) { warn = w; side = dx * -fz + dz * fx; } }
  }
  const wEl = $('warn');
  wEl.style.opacity = mode === 'race' ? Math.min(1, warn * 1.6).toFixed(2) : 0;
  wEl.style.transform = `translateX(${Math.max(-1, Math.min(1, side / 12)) * 120}px) scale(${0.7 + warn * 0.7})`;
  $('wrong').style.display = wrongT > 0.6 ? 'block' : 'none';
}

let menuA = 0;
function render(dt, now) {
  const t = track;
  if (mode === 'menu' || mode === 'select') {
    menuA += dt * 0.12;
    const i = Math.floor(((menuA * 40) % t.M + t.M) % t.M), j = (i + 12) % t.M;
    camera.position.lerp(new THREE.Vector3(t.px[i] + t.tz[i] * 3, 7, t.pz[i] - t.tx[i] * 3), Math.min(1, dt * 2));
    camera.lookAt(t.px[j], 1, t.pz[j]);
    camera.fov = 62; camera.updateProjectionMatrix();
    playerCar.visible = false;
  } else {
    playerCar.visible = !(invuln > 0 && Math.floor(now / 80) % 2 === 0) || mode !== 'race';
    playerCar.position.set(P.x, 0, P.z);
    const steerVis = ((keys.ArrowRight || keys.KeyD || touch.right ? 1 : 0) - (keys.ArrowLeft || keys.KeyA || touch.left ? 1 : 0)) * (mode === 'race' ? 1 : 0);
    playerCar.rotation.set(0, P.h - steerVis * skid * 0.25, steerVis * 0.05 * Math.min(1, P.speed / 40));
    for (const w of playerCar.userData.wheels) w.rotation.x += P.speed * dt * 2.4;
    const boosting = P.speed > 64;
    playerCar.userData.flame.visible = boosting;
    playerCar.userData.flame.scale.z = 0.7 + Math.random() * 0.6;
    playerCar.userData.shield.material.opacity = invuln > 0 ? 0.18 : 0;
    let dh = P.h - camH; while (dh > Math.PI) dh -= 2 * Math.PI; while (dh < -Math.PI) dh += 2 * Math.PI;
    camH += dh * Math.min(1, dt * 5.5);
    const tall = camera.aspect < 1 ? Math.min(1, (1 - camera.aspect) * 2) : 0;
    const cx = Math.sin(camH), cz = Math.cos(camH), dist = 8.5 + P.speed * 0.03 + tall * 5;
    shake = Math.max(0, shake - dt * 2.2);
    const sx = (Math.random() - 0.5) * shake * 1.2, sy = (Math.random() - 0.5) * shake * 1.2;
    camera.position.set(P.x - cx * dist + sx, 3.6 + tall * 2.2 + sy, P.z - cz * dist);
    camera.lookAt(P.x + cx * 8, 1.2, P.z + cz * 8);
    const fov = 60 + tall * 22 + P.speed * 0.3 + (boosting ? 6 : 0);
    camera.fov += (fov - camera.fov) * Math.min(1, dt * 4); camera.updateProjectionMatrix();
    for (const g of ghosts) {
      g.mesh.position.set(g.x, 0, g.z); g.mesh.rotation.y = g.h;
      const a = Math.min(1, g.age / 1.5) * (g.seam > 0 ? 0.25 : 1);
      const m = g.mesh.userData.mats;
      m[0].opacity = 0.85 * a; m[1].opacity = 0.85 * a; m[2].opacity = 0.6 * a; m[3].opacity = (0.4 + 0.3 * Math.sin(now / 90)) * a;
    }
    drawMap(); updateHud();
  }
  if (msgT > 0) { msgT -= dt; if (msgT <= 0) $('banner').className = ''; }
  audio.engine(Math.min(1, P.speed / 84), mode === 'race', skid, P.speed > 64);
  renderer.render(scene, camera);
}

let last = performance.now(), acc = 0, fpsAcc = 0, fpsN = 0;
function frame(now) {
  requestAnimationFrame(frame);
  let dt = Math.min(0.1, (now - last) / 1000); last = now;
  if (mode !== 'paused') {
    acc += dt;
    while (acc >= DT) { step(); acc -= DT; }
  }
  fpsAcc += dt; fpsN++;
  if (fpsAcc > 1) { window.__fps = fpsN / fpsAcc; fpsAcc = 0; fpsN = 0; }
  render(dt, now);
}

// ---------- UI ----------
function show(id) {
  for (const s of ['menu', 'select', 'hud', 'pause', 'over', 'help']) $(s).style.display = s === id || (s === 'hud' && (id === 'pause' || id === 'over')) ? '' : 'none';
  if (id !== 'hud' && id !== 'pause' && id !== 'over') $('touch').style.display = 'none';
}
function openSelect() {
  mode = 'select';
  const list = $('list'); list.innerHTML = '';
  circuits.forEach((c, i) => {
    const ok = unlocked(i), b = document.createElement('button');
    b.className = 'card' + (ok ? '' : ' locked') + (i === selected ? ' sel' : '');
    b.style.setProperty('--c', THEMES[c.theme].accent);
    const st = save.stars[c.id] || 0;
    b.innerHTML = `<span class="cn">${c.daily ? '∞ ' : i + 1 + '. '}${c.name}</span><span class="cs">${ok ? '★'.repeat(st) + '☆'.repeat(3 - st) : 'LOCKED'}</span><span class="cd">${c.daily ? 'New track every day · survive' : c.laps + ' laps'}${save.best[c.id] ? ' · best ' + save.best[c.id].toLocaleString() : ''}</span>`;
    b.disabled = !ok;
    b.onclick = () => { audio.init(); audio.click(); if (i !== selected) loadCircuit(i); startRace(); };
    b.onmouseenter = b.onfocus = () => { if (ok && i !== selected && mode === 'select') { loadCircuit(i); list.querySelectorAll('.card').forEach((x, k) => x.classList.toggle('sel', k === i)); } };
    list.appendChild(b);
  });
  show('select');
}
function toMenu() { mode = 'menu'; clearGhosts(); portal.call('gameplayStop'); show('menu'); }
function pause(p) {
  if (p && (mode === 'race' || mode === 'countdown')) { pause.prev = mode; mode = 'paused'; show('pause'); audio.engine(0, false, 0, false); portal.call('gameplayStop'); }
  else if (!p && mode === 'paused') { mode = pause.prev; show('hud'); $('touch').style.display = isTouch ? 'block' : 'none'; last = performance.now(); if (mode === 'race') portal.call('gameplayStart'); }
}
function setMuteLabel() { for (const e of document.querySelectorAll('.mute')) e.textContent = audio.muted ? 'Sound: Off' : 'Sound: On'; }
const click = (id, fn) => { $(id).onclick = () => { audio.init(); audio.click(); fn(); }; };
click('btnPlay', openSelect);
click('btnHelp', () => show('help'));
click('btnHelpBack', () => show('menu'));
click('btnBack', toMenu);
click('btnResume', () => pause(false));
click('btnRestart', startRace);
click('btnQuit', toMenu);
click('btnAgain', startRace);
click('btnNext', () => { loadCircuit(selected + 1); startRace(); });
click('btnMenu', openSelect);
click('btnPause', () => pause(true));
for (const e of document.querySelectorAll('.mute')) e.onclick = () => { audio.init(); save.muted = audio.toggleMute(); persist(); setMuteLabel(); };
setMuteLabel();

window.addEventListener('keydown', (e) => {
  if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.code)) e.preventDefault();
  if (e.repeat) return;
  keys[e.code] = true;
  if (e.code === 'Escape' || e.code === 'KeyP') pause(mode !== 'paused');
  if (e.code === 'KeyM') { save.muted = audio.toggleMute(); persist(); setMuteLabel(); }
  if (e.code === 'KeyR' && (mode === 'race' || mode === 'paused' || mode === 'over')) startRace();
  if ((e.code === 'Enter' || e.code === 'Space') && mode === 'over' && $('over').style.display !== 'none') startRace();
  if (e.code === 'Enter' && mode === 'menu') openSelect();
});
window.addEventListener('keyup', (e) => { keys[e.code] = false; });
window.addEventListener('blur', () => { for (const k in keys) keys[k] = false; pause(true); });
document.addEventListener('visibilitychange', () => { if (document.hidden) pause(true); });

let isTouch = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
if (isTouch) document.body.classList.add('touch');
const bindTouch = (id, key) => {
  const el = $(id);
  const on = (e) => { e.preventDefault(); touch[key] = true; el.classList.add('down'); };
  const off = (e) => { e.preventDefault(); touch[key] = false; el.classList.remove('down'); };
  el.addEventListener('pointerdown', on); el.addEventListener('pointerup', off); el.addEventListener('pointercancel', off); el.addEventListener('pointerleave', off);
};
bindTouch('tL', 'left'); bindTouch('tR', 'right'); bindTouch('tB', 'brake'); bindTouch('tN', 'nitro');
window.addEventListener('touchstart', () => { if (!isTouch) { isTouch = true; document.body.classList.add('touch'); if (mode === 'race' || mode === 'countdown') $('touch').style.display = 'block'; } }, { passive: true });
document.addEventListener('contextmenu', (e) => e.preventDefault());

resize();
loadCircuit(Math.max(0, circuits.findIndex((c, i) => !c.daily && unlocked(i) && !(save.stars[c.id] > 0))));
show('menu');
requestAnimationFrame(frame);
window.__pl = { P, get mode() { return mode; }, get ghosts() { return ghosts; }, get lap() { return lap; }, get score() { return score; }, get shields() { return shields; }, get track() { return track; }, keys, startRace, loadCircuit, set shields(v) { shields = v; } };
