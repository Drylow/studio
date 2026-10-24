# Reference study: "CONSTANTINOPLE – 3D TIMELAPSE – 680 BC to AD 1453"

- Channel **How Cities Grew** (1.84K subs when studied), uploaded 2026-10-15; **398K views** in 9 days.
- 8:34 (514 s), 3840×2160 at **60 fps**. Made in **Blender**; the creator says it was too big for their PC, so they rented GPUs.
- No voiceover. Music is CC-BY (Kevin MacLeod ×4, Scott Buckley "Uprising") plus CC0 SFX: construction, earthquake, fire, cannons, rocks.
- Watch it here: https://www.youtube.com/watch?v=i3MoF4bPiUQ (the video file is not in this kit).

## 1. Structure

**One continuous camera move for 8.5 minutes.** Scene detection at threshold 0.3 found zero cuts. The camera is a drone that never stops: it glides wide over the whole peninsula, swoops low over a landmark, then climbs back out. It changes subject with long curved travels, never a cut.

Chapters (from the description) map 1:1 onto the era label in the HUD:

| t | era label | what happens on screen |
|---|---|---|
| 0:00 | THRACIAN SHORE | Fade in from black on an empty forested hill. Title "CONSTANTINOPLE / 680 BC – AD 1453" centred. |
| 0:04 | GREEK BYZANTION | First buildings: agora, temple, acropolis wall. Houses spread fast; the camera pulls back as the town fills the hill. |
| 0:28 | ROMAN BYZANTIUM | SPQR flag. The camera dives to the Hippodrome; it builds in stages (foundations → stands → arcades). A 2-line serif caption explains it. |
| 0:47 | CONSTANTINOPLE, THE NEW ROME | Chi-Rho flag. Great Palace blocks rise. Forum of Constantine with the column. Low pass along the wall, then a wide reveal of the grown city. |
| 1:32 | (same) | Theodosian Walls: the camera rides along the wall as it is built tower by tower. 447 earthquake: towers crumble (dust), then rebuild, moat fills with water. |
| 2:13 | AGE OF JUSTINIAN | Hagia Sophia: an empty plot → scaffolding → walls → domes (2:16-2:24). Then a wide "THE GOLDEN AGE" title card over the peninsula. Harbour with walls and boats. |
| 2:58 | MIDDLE BYZANTINE | Great Palace grows into a full complex. Population drops 450K → 44K → climbs again. Blachernae palace. |
| 3:37 | (same) | "THE FOURTH CRUSADE": hundreds of low-poly flame cones + black smoke columns (3:42-4:00); houses burn down to ruins and gardens. |
| 4:01 | LATIN OCCUPATION | Flag change. Great Palace decays: red roofs vanish, grey ruins. Population 270K → 70K. |
| 4:19 | PALAIOLOGAN CONSTANTINOPLE | Caption on the ruined palace. City shrinks into villages amid fields. Galata tower built across the water. |
| 5:45 | (same) | Siege of 1453: the Ottoman fleet, the chain across the Golden Horn, naval fight (smoke puffs, splashes), the Ottoman camp (tents, red pavilions), cannons breaching the wall with dust clouds. |
| 7:27 | OTTOMAN CONSTANTINOPLE | "THE FALL OF CONSTANTINOPLE" title. Hagia Sophia gets a minaret. Venetian ships escape. Slow wide pull-out, fade to black at 8:32. |

**Pacing.** The year counter runs fast in growth phases (up to about 20 years/s), slows to about 1 year/s around landmarks, and **freezes** (AD 447, 1203, 1453) during events. Events get 20-100 s; quiet growth gets 10-20 s.

## 2. Look (what makes it read as "premium")

- **Low-poly, flat-shaded, toy-model look.** Trees are faceted icospheres on thin trunks, with cypress cones mixed in. Houses are boxes + hip roofs. No textures; everything is a solid colour.
- **Palette:** grass olive-green #5f8a3a → #4d7a2e; trees dark green #2f5e2c; terracotta roofs #c8643c / #d9744a; walls cream #e9dcc4 / #d8c6a8; dirt roads beige #b9a27c. Water has **two tones**: turquoise shallows #2fb3c0 near shore, deep blue #1f6f9a offshore, with a pale sand rim.
- **Lighting:** a warm low-ish sun from one side, long soft **cast shadows** (each tree throws a big shadow blob), strong ambient occlusion between houses, light haze in the far distance.
- **Tilt-shift depth of field is the signature.** The focus band is the middle of the frame. The bottom 15% and top 10% are heavily blurred, so the city looks like a miniature model.
- **Mild bloom and grade:** slightly warm, slightly desaturated, soft contrast. Vignette very light.
- **Density:** at full size tens of thousands of houses (instancing). Streets show as beige lines between blocks; gardens and trees fill the gaps.
- **Small life:** sailboats and galleys drift on the water; fires, smoke and dust are simple particle cones/puffs.

## 3. How things appear (10 fps strip in `hires/popstrip.jpg`)

- Every building **grows out of the ground**: scale from 0 → 1 over about 0.3 s, roughly ease-out. Trees appear the same way, small first.
- New houses appear in **clusters along roads**, from the core outward. Hundreds per second in boom phases, staggered so it never feels like a block swap.
- Big landmarks are **staged**: foundation outline/dirt plot → scaffolding (brown timber lattice) → walls → roof/dome.
- Decline is the reverse: roofs disappear (grey ruins), then buildings sink away, and gardens/fields replace houses.
- Destruction: fire cones flicker on houses, black smoke columns drift, then the houses are swapped for ruins.

## 4. HUD (constant, never moves)

All white, no boxes. Text has a faint dark shadow for legibility. 1080p sizes:

- **Year**, bottom-right: a condensed bold sans (DIN Condensed Bold look), ~95 px cap height, letter-spaced. Format `680 BC` / `AD 212`; after AD 1000 just `1203`.
- **Era label**, bottom-left: the same DIN family, medium, ~36 px, caps, tracking ~0.08 em. Above it sits a **flag tile** (~135×80, the era's banner: SPQR, Chi-Rho, Palaiologan, Ottoman crescent).
- **Population**, top-right: a person glyph + `c. 3,500`, DIN ~40 px. It counts smoothly.
- **Opening title**: a Trajan/Cinzel-style serif, wide-tracked caps `CONSTANTINOPLE`, with a small `680 BC – AD 1453` under it, centred. It fades in over the forest and fades out after 3 s.
- **Landmark name**: the same serif, ~60 px, tracked caps, centred low (y≈880), with a thin hairline rule on each side. It fades in/out over about 4 s, often a little transparent over the scene.
- **Explanatory caption**: a 2-line serif sentence (Marcellus/Cormorant style), ~32 px, centred, with a short gold rule above and below. It stays about 5-6 s.
- **Small object label** ("Ottoman Fleet", "Ottoman Camp"): a small sans, placed in-world near the thing.
- **Chapter title card** ("THE GOLDEN AGE", "THE FOURTH CRUSADE"): the serif with a tiny "EASTERN ROME" kicker above it, centred low. Same fade.

## 5. Audio

- Integrated **-14.1 LUFS**, LRA 7.9. It starts silent and swells over the first 20 s.
- Orchestral/ambient cinematic music, changing per era with crossfades. It darkens for the crusade and siege, and turns to mourning for the fall.
- SFX sit under the music: hammering and stone on building beats, a rumble for the earthquake, crackle for fire, cannon booms and splashes.

## 6. What we must match in code (Three.js inside HyperFrames)

1. Instanced low-poly houses (box + hip roof, colour jitter), tens of thousands, each with its own spawn time → grow-in in the vertex shader. One draw call per type.
2. Procedural coastline terrain + two-tone water shader (depth-based shallows) + sand rim.
3. Low-poly icosphere trees and cypresses, instanced, with cast shadows.
4. Soft shadow map with a big frustum, plus SSAO/GTAO, plus a **tilt-shift blur pass**, plus bloom, plus grading/vignette.
5. Staged landmark builds (plot → scaffold → walls → dome) as scripted keyframes.
6. One continuous camera spline with eased speed: wide → swoop → climb.
7. HUD in HTML/CSS (DIN-like condensed font + Cinzel-like serif, shipped as @font-face files so every machine renders the same).
8. Data-driven timeline: year curve, population curve, era/flag table, landmark/caption cues → one config file per city.
9. 60 fps; 1080p is the default, 4K if the machine can handle it.
