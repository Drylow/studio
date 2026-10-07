# Final export — 8 October 2026

Current output: `chocolate-crazy-tools-final.mp4`, SHA-256
`03d3e15ac915a32d489b7fb1181fbaf43beadcb7bebd18de8a543683f6d52385`.
66.7 seconds, 1080×1920, 60fps, 4,002 frames, 147.8 MB.

The minute-plus edit keeps two quantities per mechanism and three rapid salvos
at each quantity. Each salvo has different seeded fractures. The final user
correction moves all three smaller tool sprites into a compact horizontal
footer, replacing round captions; the action is centred again. Current tool:
dark green border and arrow. Completed tool: green tick. Future tools stay
visible from frame zero. Footer cards remain clear of flying chocolate.

Strict hardware preview checks passed at 13 timestamps after the footer edit,
with no errors or warnings. Earlier timing checks passed at 23 timestamps.
Final rendering completed with hardware screenshot capture and encoding:
`--quality delivery --fps 60 --workers 2 --browser-gpu --gpu --strict-all`.
Total wall time 5m57s; capture 306.5s, encode 39.2s, assemble 2.9s.

All 4,002 decoded frames were viewed across 67 numbered contact sheets. Reviewed
the palm arrival, each reload and contact, spring compression and retraction,
upward jackhammer, irregular tumbling fragments and the spatula celebration.
The compact footer stays unobstructed, with the active marker changing at the
tool transitions and completed-tool ticks retained. Some chips leave the frame
at the sides during stronger impacts. Automated checks cover every frame:
minimum title coverage 0.99793, minimum tool-icon coverage 1.0, correct active
tool on all frames. The original palette, English bitmap labels and white
chef sleeve remain consistent in the contact-sheet review.

Physics verification: 123 bars, 1,715 closed irregular fragments, 515,339 stored
poses; minimum vertex height 0.00274, maximum horizontal radius 7.751, conserved
volume and unit quaternions. All cracks follow contacts, with 1,625 landing
events grouped into 337 accents. Existing frozen SFX are reused. PCM peak
−2.73 dBFS, no clipped samples; final AAC peak −3.6 dBFS, mean −33.7 dBFS.
These are measured checks, not a claim of human headphone listening.

Preview on port 3003 was reopened and its 66.7-second timeline verified. A
previous preview hot reload timed out; a fresh preview server resolved it.
No music, reference footage/audio or social-media publication. The static-object
debris collision approximation documented in README remains.

## Previous short delivery — 8 October 2026

Current output: `chocolate-crazy-tools.mp4`, SHA-256
`2e6e09f59f21310cf9603094bc6fc4dd775f6c09b5fc2d2accbe646e6ea61069`.
23.3 seconds, 1080×1920, 60fps, 1,398 frames, 49.9 MB.

The user selected a spring boxing glove followed by an upward jackhammer, with
fewer quantity steps. Two trials per tool replace the five fork-only trials:
fork 1 / 4, glove 4 / 8, jackhammer 8 / 16. The normal palm arrival and happy
spatula finish are retained. The earlier fork-only MP4 remains available as a
previous export; this is the current composition.

All 1,398 decoded frames were viewed in 24 numbered contact sheets. Reviewed
spring compression, rapid horizontal punch, retraction, upward chisel movement,
food contacts, transitions, tumbling and celebration. Some flying chips exit
the side of the frame during the stronger actions; titles stay unobstructed.
The white sleeve, original Watermelon palette and English bitmap labels remain.

The strict hardware preview check passed at 28 timestamps with no errors or
warnings. `qa_frames.py` verifies the quantity and tool-title field on every
exported frame; minimum coverage 1.0. Export used HyperFrames 0.8.140,
`--quality delivery --fps 60 --workers 2 --browser-gpu --gpu --strict-all`,
hardware screenshot capture and encoding; completed in 85.3 seconds.

Physics verification passed: 41 bars, 573 closed irregular geometries, 171,972
stored poses, volume error below 1e-6, unit-quaternion error below 2e-5, no early
fractures and contact checks for all three tools. Minimum vertex height 0.00314;
maximum horizontal radius 6.604 units. The spring stroke and 22Hz upward chisel
poses share one absolute-time function between physics and rendering.

Three new original SFX sources add spring compression, a boxing thump and rapid
mechanical percussion. All 41 primary chocolate cracks follow tool contacts;
544 landing events share 114 restrained groups. PCM peak −2.73 dBFS, no clipped
samples. Final decoded AAC peak −3.6 dBFS, mean −33.0 dBFS. These are measured
checks, not a claim of human headphone listening. No music or reference audio.

The dense piles retain the stylised static-object collision approximation and
support guard documented below. The glove's extra damping keeps projected
fragments near the tabletop. Studio preview was reopened in Codex and verified
to show the spring-glove chapter and the revised 23.3-second timeline. No social
media publishing was performed.

## Previous delivery — 7 October 2026

Reviewed output: `chocolate-giant-fork.mp4`, SHA-256
`ac38feeb0737844a7af50e54de7b8374ce7cfa40e29cd8289206ca7bbc51586d`.

27.8 seconds, 1080×1920, 60fps, 1,668 frames. H.264 Main, yuv420p,
stereo AAC at 48kHz. HyperFrames 0.8.140 hardware capture and encoding completed
with `--quality delivery --fps 60 --workers 2 --browser-gpu --gpu --strict-all`.

## Visual review

All 1,668 decoded frames were viewed in 28 numbered contact sheets, including
each trial change and the happy spatula finish. The chocolate stack stays below
the title at 16 bars; the white sleeve and palm are visible beneath the first
bar. Oblique fragments fall around the board, then clear before the next trial.
The original Watermelon palette, chef arm, tabletop, bitmap text and celebration
are retained. On-screen labels are English. The complete image is drawn on a
216×384 grid and enlarged without smoothing.

`qa_frames.py` verified frame count, dimensions, rate, duration, audio presence
and title coverage throughout the exported file. Minimum title coverage: 1.0.
The strict hardware preview check passed at 14 contact, transition and finish
timestamps with zero errors or warnings. Canvas text was checked visually and
through exported pixels, beyond the DOM checks.

Review sheets and reports remain in the ignored `qa/` folder. Initial problems
with a hidden sleeve, an oversized stack and excessive debris travel were
corrected before this export.

## Contact and sound

`npm run verify` passed: 31 intact bars, 435 convex fracture geometries,
226,371 stored poses, finite unit quaternions, conserved geometry volume,
positive closed-face winding, contact-height checks, no premature fracture,
and no pieces below the support plane. Maximum horizontal radius: 5.686 units.

All 31 major crunch accents follow actual fork contact. 240 landing events
share 85 short groups; their gain stays below the primary cracks. Three original
food-foley sources supply nine frozen variants. No reference audio is reused.

The PCM mix has no clipped samples and peaks at −2.73 dBFS. The final decoded AAC
peaks at −3.8 dBFS. Active crunch RMS across the five trials ranges from −24.4
to −22.0 dBFS. These are measured checks, not a claim of human headphone listening.
Music remains deferred as requested.

## Limits and delivery

This is stylised rigid-body food animation. Thin fragments collide with the
fork, board and floor; dense debris does not solve mutual fragment collisions.
A bounded energy correction and support guard stabilise the piles. It is not
a scientific simulation of chocolate material.

HyperFrames preview was opened in Codex before rendering. The final MP4 is
delivered in the current conversation. No social-media upload was performed.
Source, sound receipts and the six-clip study index are committed separately
from ignored renders, review sheets and downloaded reference clips.
