# City time-lapse kit

3D "watch a city grow over centuries" videos, made **100% in code**: HTML + JavaScript + Three.js, rendered by [HyperFrames](https://hyperframes.heygen.com). There is no voiceover; the music is generated in code too.

`cities/babylon` is a complete, finished episode ("BABYLON – 3D TIMELAPSE – 1900 BC to AD 200", 5 min, 1080p60). Use it as the worked example and the template for every new city.

## What's inside

| Path | What it is |
|---|---|
| `shared/engine.js` | The engine: renderer + post FX (ambient occlusion, tilt-shift miniature blur, bloom, ACES, SMAA); instanced buildings that grow out of the ground, burn and collapse (shadows included); ground texture with roads that draw on in time; scripted landmarks; the one-take camera; the HUD (year, era + flag, population, titles, captions) |
| `shared/lib/` | Three.js r181, postprocessing, N8AO, vendored so no install is needed |
| `shared/fonts/` | Barlow Condensed (HUD), Cinzel (titles), Cormorant Garamond (captions), all OFL |
| `cities/babylon/` | The full example: `scene.js` (the city), `index.html` (HUD), `music.mjs` (score), `SPEC.md` (beats + fact-checked captions), `UPLOAD.md` (YouTube title/description/tags) |
| `tools/new-city.mjs` | `node tools/new-city.mjs rome "ROME" "753 BC – AD 2026"` → `cities/rome/`, self-contained |
| `tools/render.mjs` | Renders a city to MP4 on this machine, using the GPU |
| `CLAUDE.md` | The full how-to for an AI coding agent (Claude Code, etc.): workflow, style rules, pitfalls |
| `STYLE-REFERENCE.md` | Frame-by-frame study of the reference video the look is based on |

## Setup (once)

1. **Node 20+** and **ffmpeg** on the PATH.
2. HyperFrames is fetched by `npx` on first use (pinned to `hyperframes@0.8.162`). It downloads a headless Chrome the first time.
3. A GPU helps a lot: the scenes are WebGL and render with `--browser-gpu --gpu`.

## Make a video

```bash
node tools/new-city.mjs rome "ROME" "753 BC – AD 2026"
cd cities/rome
# 1. write SPEC.md (beats, years, captions + sources)    2. rework scene.js    3. compose the score:
node music.mjs                                        # -> assets/music.m4a (-14 LUFS)
npx --yes hyperframes@0.8.162 check --json            # lint, contrast, runtime errors
npx --yes hyperframes@0.8.162 snapshot . --at 5,30,60,120 --no-end --timeout 180000 --describe false -o snaps   # a few stills to look at
npx --yes hyperframes@0.8.162 preview                 # interactive scrubbing in the browser
cd ../..
node tools/render.mjs rome --fps 60          # -> cities/rome/renders/rome.mp4
```

A 5-minute 1080p60 episode is about 18,000 frames, so it takes a while on a single desktop GPU. Use `--fps 30` or a shorter test (temporarily lower the root `data-duration` in index.html) for drafts, and `--workers 2` if the PC struggles.

To try the example as-is: `node tools/render.mjs babylon`.

## Licences

See `LICENSES.md`. The code in `cities/` and `shared/engine.js` and the generated music are yours to use. The bundled libraries and fonts keep their own (permissive) licences.
