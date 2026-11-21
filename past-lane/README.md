# Past Lane

An HTML5 arcade racer where your own past laps are the traffic. After each lap, a ghost of that lap drives the circuit in reverse, on the exact line you took. Dodge them, skim past for near-miss combos and nitro.

- Six circuits plus a daily track generated from the UTC date (survival mode).
- Three.js, no asset files: tracks, scenery, textures, sound and music are all generated in code.
- Static build: `index.html` + `game.js` (about 520 KB). Keyboard and touch. Progress in `localStorage`.

Play it: https://ray3242.github.io/money-plays/past-lane/play/ (`play/` is a committed copy of `dist/`).

## Build

```
npm install
npm run build              # dist/  (OpenGame, itch.io, any static host)
npm run build:crazygames   # dist-crazygames/  (loads the CrazyGames SDK v3; gameplayStart/Stop + happytime wired)
npm test                   # headless smoke test with an autopilot, screenshots in shots/
```

`dist/` passes `opengame check .`. The smoke test expects Chrome at the path set in `test.mjs`.

## Controls

Left/Right or A/D steer, Down/S brake, Space or Up nitro, P pause, R restart, M mute. On touch devices: on-screen buttons.

## AI disclosure

Design, code, procedural art and audio were written by an AI coding agent (Devin) starting Nov 21 2026, for the OpenGame Game Jam #1. No pre-existing game code or third-party assets; the only dependency is Three.js (MIT).

See [SUBMISSION.md](SUBMISSION.md) for the submission text and steps.
