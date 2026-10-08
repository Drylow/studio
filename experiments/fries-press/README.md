# Fries / Hydraulic Press

Original 63.6-second vertical pixel-chef animation. Three loads (48, 96, 192 fries), a hydraulic press, irregular food fractures and golden oil runoff. Text is English. The chef carries the tray on a supporting palm, then returns with the approved happy spatula and confetti.

## Run

```powershell
npm ci
npm run build
npm run verify
npm run check
npx --yes hyperframes@0.8.140 preview --background --port 3004
npm run render
python qa_frames.py
```

Studio: `http://localhost:3004/#project/fries-press`.
Final export: `fries-hydraulic-press-final.mp4` (local, ignored by Git).

The settled initial piles and sound-event schedule are frozen in `assets/piles.json` and `assets/events.json`. `build-piles.mjs` regenerates them with a seeded rigid-body simulation; `model.mjs` defines all absolute-time states. `scene.mjs` renders analytic deformation, fragments and fluid ribbons without accumulating simulation state while seeking. The oil amount is cartoon exaggeration, not a physical measurement.

All picture assets are code geometry; approved chef, confetti, lettering and palette come from the earlier Chocolate composition. New hydraulic, wet squeeze and oil foley is frozen locally; crunch and tray foley reuses the existing library. No music, speech, reference footage or reference sound is included.

The app frontend and existing finished videos are unchanged. Verification details belong in `QA.md`.
