let ctx = null, master, engGain, engOsc = [], engFilter, skidGain, nitroGain, musicGain;
let muted = false, musicTimer = null, step = 0, nextT = 0, key = 0;

function noiseBuf() {
  const b = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate), d = b.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  return b;
}
let nbuf;
export const audio = {
  get muted() { return muted; },
  init() {
    if (ctx) { if (ctx.state === 'suspended') ctx.resume(); return; }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    ctx = new AC();
    master = ctx.createGain(); master.gain.value = muted ? 0 : 0.8; master.connect(ctx.destination);
    nbuf = noiseBuf();
    engFilter = ctx.createBiquadFilter(); engFilter.type = 'lowpass'; engFilter.frequency.value = 500;
    engGain = ctx.createGain(); engGain.gain.value = 0;
    engFilter.connect(engGain); engGain.connect(master);
    for (const [type, det] of [['sawtooth', 0], ['square', 7], ['sawtooth', -1200]]) {
      const o = ctx.createOscillator(); o.type = type; o.detune.value = det; o.frequency.value = 60;
      const g = ctx.createGain(); g.gain.value = det === -1200 ? 0.5 : 0.22;
      o.connect(g); g.connect(engFilter); o.start(); engOsc.push(o);
    }
    const mk = (freq, q, type) => {
      const s = ctx.createBufferSource(); s.buffer = nbuf; s.loop = true;
      const f = ctx.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q;
      const g = ctx.createGain(); g.gain.value = 0;
      s.connect(f); f.connect(g); g.connect(master); s.start();
      return g;
    };
    skidGain = mk(1900, 3, 'bandpass');
    nitroGain = mk(700, 0.6, 'highpass');
    musicGain = ctx.createGain(); musicGain.gain.value = 0.32; musicGain.connect(master);
  },
  toggleMute() { muted = !muted; if (master) master.gain.value = muted ? 0 : 0.8; return muted; },
  setMuted(m) { muted = m; if (master) master.gain.value = muted ? 0 : 0.8; },
  engine(speed01, on, skid, nitro) {
    if (!ctx) return;
    const t = ctx.currentTime;
    const gear = (speed01 * 4) % 1, f = 55 + speed01 * 95 + gear * 28;
    for (const o of engOsc) o.frequency.setTargetAtTime(f, t, 0.04);
    engFilter.frequency.setTargetAtTime(350 + speed01 * 1700, t, 0.05);
    engGain.gain.setTargetAtTime(on ? 0.1 + speed01 * 0.1 : 0, t, 0.08);
    skidGain.gain.setTargetAtTime(on ? Math.min(0.28, skid * 0.3) : 0, t, 0.05);
    nitroGain.gain.setTargetAtTime(on && nitro ? 0.22 : 0, t, 0.08);
  },
  tone(freq, dur, type = 'triangle', vol = 0.25, slide = 0, delay = 0) {
    if (!ctx) return;
    const t = ctx.currentTime + delay, o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type; o.frequency.setValueAtTime(freq, t);
    if (slide) o.frequency.exponentialRampToValueAtTime(Math.max(20, freq * slide), t + dur);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(master); o.start(t); o.stop(t + dur + 0.05);
  },
  burst(dur, freq, vol = 0.5) {
    if (!ctx) return;
    const t = ctx.currentTime, s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
    s.buffer = nbuf; f.type = 'lowpass'; f.frequency.setValueAtTime(freq, t); f.frequency.exponentialRampToValueAtTime(80, t + dur);
    g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    s.connect(f); f.connect(g); g.connect(master); s.start(t); s.stop(t + dur + 0.05);
  },
  click() { this.tone(660, 0.07, 'square', 0.12); },
  crash() { this.burst(0.5, 2500, 0.7); this.tone(90, 0.4, 'sawtooth', 0.4, 0.4); },
  scrape() { this.burst(0.15, 1800, 0.25); },
  near(combo) { this.tone(500 + combo * 70, 0.18, 'sawtooth', 0.16, 2.2); },
  lap() { [0, 4, 7, 12].forEach((s, i) => this.tone(440 * 2 ** (s / 12), 0.22, 'triangle', 0.22, 0, i * 0.08)); },
  win() { [0, 4, 7, 12, 16, 19, 24].forEach((s, i) => this.tone(392 * 2 ** (s / 12), 0.3, 'triangle', 0.24, 0, i * 0.1)); },
  lose() { [0, -3, -7, -12].forEach((s, i) => this.tone(330 * 2 ** (s / 12), 0.35, 'sawtooth', 0.18, 0, i * 0.16)); },
  beep(hi) { this.tone(hi ? 880 : 440, hi ? 0.5 : 0.18, 'square', 0.18); },
  music(k) {
    key = k;
    if (!ctx || musicTimer) return;
    nextT = ctx.currentTime + 0.1;
    const bass = [0, 0, 7, 0, 3, 3, 10, 3, 5, 5, 12, 5, 7, 7, 10, 12];
    const arp = [12, 15, 19, 24, 19, 15, 12, 19, 15, 19, 22, 27, 22, 19, 15, 22];
    musicTimer = setInterval(() => {
      if (!ctx) return;
      while (nextT < ctx.currentTime + 0.25) {
        const base = 55 * 2 ** (key / 12), bar = Math.floor(step / 16) % 4, s = step % 16;
        const sh = [0, 0, -4, -2][bar];
        const note = (semi, dur, type, vol) => {
          const o = ctx.createOscillator(), g = ctx.createGain();
          o.type = type; o.frequency.value = base * 2 ** ((semi + sh) / 12);
          g.gain.setValueAtTime(0.0001, nextT); g.gain.exponentialRampToValueAtTime(vol, nextT + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, nextT + dur);
          o.connect(g); g.connect(musicGain); o.start(nextT); o.stop(nextT + dur + 0.02);
        };
        if (s % 2 === 0) note(bass[s], 0.2, 'sawtooth', 0.3);
        note(arp[s] + 12, 0.12, 'square', 0.07);
        if (s % 4 === 2) {
          const n = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
          n.buffer = nbuf; f.type = 'highpass'; f.frequency.value = 6000;
          g.gain.setValueAtTime(0.12, nextT); g.gain.exponentialRampToValueAtTime(0.0001, nextT + 0.06);
          n.connect(f); f.connect(g); g.connect(musicGain); n.start(nextT); n.stop(nextT + 0.08);
        }
        if (s % 4 === 0) {
          const o = ctx.createOscillator(), g = ctx.createGain();
          o.frequency.setValueAtTime(140, nextT); o.frequency.exponentialRampToValueAtTime(40, nextT + 0.14);
          g.gain.setValueAtTime(0.5, nextT); g.gain.exponentialRampToValueAtTime(0.0001, nextT + 0.16);
          o.connect(g); g.connect(musicGain); o.start(nextT); o.stop(nextT + 0.2);
        }
        nextT += 0.125; step++;
      }
    }, 60);
  },
  suspend(s) { if (ctx) { if (s) ctx.suspend(); else ctx.resume(); } },
};
