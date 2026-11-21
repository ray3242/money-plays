# Submission kit

## Copy (all portals)

- **Title:** Past Lane
- **Tagline:** Every lap you drive comes back at you, head-on.
- **Description:** Past Lane is an arcade racer where your own past laps are the traffic. After each lap, a ghost of that lap drives the circuit in reverse on the exact line you took, so the fast line you drive now is the line you must avoid later. Hit a ghost and you lose a shield; skim past one for a near miss that builds your combo and fills your nitro. Clear six circuits, earn three stars on each, then see how many laps you can survive on a new daily track.
- **Controls:** Left/Right or A/D steer. Down/S brake. Space or Up nitro. P pause, R restart, M mute. Mobile: on-screen buttons.
- **Genre / tags:** Racing, Arcade, Driving, 3D, Car, Skill, Single player
- **AI disclosure:** Built with an AI coding agent (Devin). All code, procedural visuals and audio are AI-written; no third-party assets. Engine: Three.js (MIT).

## OpenGame Game Jam #1 (closes Dec 18 2026, 11:59 PM PT)

Rules: https://opengame.io/rules. The creator must sign in and publish personally; an agent may not do it for them.

```
npm i -g @opengamehq/cli
opengame setup            # sign in as yourself
npm install && npm run build
cd dist && opengame check . && opengame deploy .
```

Then open the deploy page it prints, confirm the details above, confirm the Racing & Sports track, and publish.

## CrazyGames

https://developer.crazygames.com. Upload the contents of `dist-crazygames/` (HTML5, SDK v3) and paste the copy above. A cover image and a gameplay video are required at submission; capture them on a real device.

## itch.io (optional)

Zip the contents of `dist/`, upload as an HTML game played in the browser, viewport 1280x720, fullscreen and mobile friendly enabled.
