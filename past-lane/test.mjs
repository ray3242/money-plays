import { chromium } from 'playwright-core';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
const root = process.argv[2] || 'dist';
const srv = http.createServer((q, s) => {
  const base = path.resolve(root);
  const f = path.resolve(base, '.' + (q.url === '/' ? '/index.html' : q.url.split('?')[0]));
  if (!f.startsWith(base + path.sep) || !fs.existsSync(f)) { s.writeHead(404); return s.end(); }
  s.writeHead(200, { 'content-type': f.endsWith('.js') ? 'text/javascript' : 'text/html' }); s.end(fs.readFileSync(f));
}).listen(8765, '127.0.0.1');
const b = await chromium.launch({ executablePath: '/home/ubuntu/.local/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--mute-audio'] });
const errs = [];
async function run(name, vp, touch) {
  const ctx = await b.newContext({ viewport: vp, hasTouch: !!touch, isMobile: !!touch });
  const p = await ctx.newPage();
  p.on('console', (m) => { if (m.type() === 'error') errs.push(name + ': ' + m.text()); });
  p.on('pageerror', (e) => errs.push(name + ': ' + e.message));
  await p.goto('http://localhost:8765/');
  await p.waitForTimeout(1500);
  await p.screenshot({ path: `shots/${name}-menu.png` });
  await p.click('#btnPlay'); await p.waitForTimeout(600);
  await p.screenshot({ path: `shots/${name}-select.png` });
  await p.click('.card'); 
  // autopilot: steer to hold a lateral target, weave away from ghosts
  await p.evaluate(() => {
    const g = window.__pl; window.__auto = setInterval(() => {
      const t = g.track, P = g.P, i = (P.idx + 6) % t.M;
      let target = Math.sin(performance.now() / 2300) * (t.W - 3);
      for (const gh of g.ghosts) if (gh.d < 90) { const lat = (gh.x - t.px[P.idx]) * t.tz[P.idx] + (gh.z - t.pz[P.idx]) * -t.tx[P.idx]; target = lat > 0 ? -t.W + 2.5 : t.W - 2.5; }
      const want = Math.atan2(t.tx[i], t.tz[i]) + Math.max(-0.5, Math.min(0.5, (target - P.lat) * 0.06));
      let d = want - P.h; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI;
      g.keys.ArrowLeft = d > 0.03; g.keys.ArrowRight = d < -0.03;
      g.keys.ArrowDown = Math.abs(t.curv[(P.idx + 12) % t.M]) > 0.028 && P.speed > 38;
    }, 16);
  });
  for (const s of (touch ? [5, 40] : [5, 25, 50, 80])) {
    await p.waitForTimeout((s - (run.t || 0)) * 1000); run.t = s;
    await p.screenshot({ path: `shots/${name}-t${s}.png` });
    console.log(name, s, await p.evaluate(() => ({ mode: __pl.mode, lap: __pl.lap, score: Math.round(__pl.score), sh: __pl.shields, gh: __pl.ghosts.length, fps: Math.round(window.__fps), spd: Math.round(__pl.P.speed) })));
  }
  run.t = 0;
  for (let k = 0; k < 400; k++) { if (await p.evaluate(() => __pl.ghosts.some((g) => g.d < 45 && g.age > 2))) break; await p.waitForTimeout(30); }
  await p.screenshot({ path: `shots/${name}-ghost.png` });
  await ctx.close();
}
const which = process.argv[3] || 'desk';
if (which === 'desk') await run('desk', { width: 1280, height: 720 });
if (which === 'mob') await run('mob', { width: 844, height: 390 }, true);
if (which === 'port') await run('port', { width: 390, height: 844 }, true);
console.log('errors', errs);
await b.close(); srv.close();
