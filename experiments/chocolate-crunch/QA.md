# Delivery audit — 7 October 2026

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
