# Instructions for the AI agent working in this kit

You are making long-form YouTube videos: **"<CITY> – 3D TIMELAPSE – <start> to <end>"**. A low-poly 3D city grows over centuries in **one continuous drone flight**, with no voiceover, only a music score. Everything is code. Read `README.md` for the commands and `STYLE-REFERENCE.md` for the look. `cities/babylon` is the approved worked example; match its quality.

## Non-negotiables
- **100% code.** No AI-generated images or video, no stock footage. Geometry, textures, HUD and music are all generated.
- **Render with `node tools/render.mjs <slug> --fps 60`** (local GPU). Check with a handful of `snapshot` stills first; a full render is long, so only start it once the stills look right.
- **Topics: cities a global audience knows by name** (Rome, Athens, Jerusalem, Venice, Paris…). Before choosing one, search YouTube for "<city> 3D timelapse" to see who already covered it and how; find an angle (era, events) that isn't a copy.
- **Facts are checked.** Every caption, date and landmark comes from a source you read (Wikipedia is the minimum). Note the source per caption in SPEC.md. Say "about", "reportedly", "may have" where historians disagree. The upload description carries an "illustrative reconstruction; extents and populations approximate" disclaimer.
- **Text is perfectly straight** (never rotated), sits on a soft dark backing, and must pass the contrast check.

## Workflow per episode
1. `node tools/new-city.mjs <slug> "<NAME>" "<span>"`.
2. **Research → SPEC.md**, before code:
   - the setting: coast, rivers and hills; the plan of the walls and quarters; the key landmarks with rough sizes and positions in metres (x east, z south)
   - a beat table: video time, year, era label + flag, what happens on screen
   - the captions with their sources
   - target 4–8 minutes
3. **scene.js**: replace the Babylon specifics (the sections below). Keep the engine untouched unless something is genuinely missing; if you extend it, extend `shared/engine.js` too.
4. **music.mjs**: compose a fresh score in a mode or colour that fits the city and follows the beats (swells on builds, timpani and gong on disasters, thinning at declines). Never reuse another episode's score. Loudness -14 LUFS.
5. **Check:** `npx --yes hyperframes@0.8.162 check --json` (zero errors). Then about 15 snapshot stills across the timeline. Look at every one: composition, empty frames, glitches, text legibility, landmarks actually visible when their label shows.
6. **Render** with `node tools/render.mjs <slug> --fps 60`. Spot-check frames from the MP4 with ffmpeg before calling it done.
7. Fill `UPLOAD.md`: title, description with chapters matching the beats, disclaimer, tags.

## How scene.js is organised (Babylon as the example)
- **Land:** `heightAt(x, z)` (terrain height), the water features (`riverX`, `CANALS`, coast functions), `wetness()` (green belt vs desert). The water plane at y = 0 shows wherever the terrain dips below 0.
- **Plan:** `CORE` (where growth starts), wall outlines (`RECT`, `OUTER`, polylines), `SITES` (landmark footprints that keep houses out).
- **Time:**
  - `RK`: city radius over video time; `DK`: density.
  - `YK`: video time → year (negative = BC). Fast in quiet centuries, slow round landmarks, **frozen during events**.
  - `T`: the event and build times.
- **Text:** `ERAS` (bottom-left label + SVG flag), `FLAGS`, `TITLE`, `LANDMARKS` (serif name with hairlines), `CAPTIONS` (2 lines), `CARDS` (chapter titles).
- **Lots and lives:** each house lot gets a list of lives. A life is born when the city reaches it, can be ignited (`ign` chars it and spawns flames) and dies, leaves a ruin, and is rebuilt. Events are applied in order. Population is computed from the houses alive, scaled to a historical peak.
- **Landmarks:** `landmarks()` gives `box()` and `grow(obj, a, b, mode, {off, offB, offTo})`. Build staged monuments (plot → scaffold → walls → roof or dome) from boxes, cones and cylinders, and decay them to rubble with `offTo`.
- **Events:** `flames()` for fires, `puffs()` for smoke and dust, a flood plane, armies (instanced boxes on a path), camps (instanced tents).
- **Camera:** `cameraPath([[t, [pos], [target]], ...])`. Keys about 8–12 s apart; it's a C1 Hermite in time, so it never jerks. Go wide for growth phases, swoop low to each landmark as it's built, and pull back for the ending.

## Look rules (from the reference + the approved episodes)
- **Low-poly, solid colours:** no textures, flat shading on trees and roofs. Palette per city: the local building material (terracotta roofs, mudbrick, marble, timber…) against the land.
- **Tilt-shift blur and soft shadows are always on;** the engine handles both. The camera mostly looks across the city at 30–50° down, sun behind-left.
- **Everything appears by growing out of the ground,** never popping in. Forest and fields are cleared as the city reaches them. Declines leave ruin mounds, and the land dries or regrows.
- **HUD never moves:**
  - year bottom-right (`AD 212`, `680 BC`, plain `1203` after AD 1000)
  - era label + flag bottom-left
  - `c. 34,000` population top-right
  - one landmark label or caption at a time
- **Fade in from black on the empty land** with the title, and end on a wide pull-out with the title card and a fade to black.

## Pitfalls already hit (don't repeat)
- **A large ground plane covering the river.** Any "far ground" must be a ring outside the terrain square, never a plane under the city, or rivers turn into dry beige strips.
- **Colours in custom GLSL are linear.** Wrap authored sRGB values in `Ls()` (pow 2.2), or the ground looks washed out.
- **Bright land (desert, snow, marble) makes white text fail contrast.** The kit's index.html already has corner shading and backings; keep them, and re-run the check.
- **Watch the glare:** low water roughness plus strong normal noise gives white glare bands, and flood planes need roughness ≥ 0.6.
- **Palms and trees must be cleared from landmark sites when the site is built** (see `clearAt`). Otherwise trees grow through temples.
- **The opening town must be visible.** The starting radius `RK[0]` must cover real lots, not just landmark sites.
- **Fonts must load from files** (`assets/fonts` via @font-face), or another machine substitutes others.
- **Ship audio as m4a,** not wav (smaller, and it is what index.html points at).
- **If a GPU capture shows tinted rectangular bands, re-render that stretch.** Compare a few frames against `snapshot` stills.
