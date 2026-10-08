# Delivery verification — 8 October 2026

Export: `fries-hydraulic-press-final.mp4`, 188,111,600 bytes.
SHA-256: `AE1EB694B495429C39636DAEA080522A81B216E419FF0D971EBBC04AB8EDCFD8`.
1080 × 1920, 60 fps, 63.6 seconds, 3,816 decoded frames, audio present.

## Picture review

Codex visually inspected all 64 consecutive-frame contact sheets from the final
MP4, covering every frame (0–3815), with a complete portrait thumbnail and an
action crop beside each one. No frame sampling was used. Larger snapshots were
also inspected at tray placement, compression, oil release and the ending.

The supporting palm stays beneath the tray during arrival and withdraws before
the piston descends. Each load visibly settles under the platen; the food stays
crushed when the platen rises. The 48 → 96 → 192 transitions replace the tray
cleanly. Oil starts after contact, spreads around the tray and drips over the
board edge into persistent floor pools. The last shot retains the crushed food
and oil, with the white chef sleeve, happy spatula motion and confetti.

The English bitmap titles remain clear and complete through every frame.
`qa_frames.py` additionally checked their expected glyph masks and the current
load marker on every decoded image: minimum title coverage 100%, maximum marker
colour-channel error 5. No black frame or decode failure was found.

## Technical and sound checks

- HyperFrames check at 16 times, including both load boundaries and the ending:
  zero errors and zero warnings. Browser runtime and layout checks passed.
  Canvas lettering was assessed visually and by exported glyph masks; the DOM
  contrast checker did not evaluate it.
- `verify-simulation.mjs`: all 3,816 states passed contact, plate bounds, finite
  position, food-floor and sound-event timing checks; no oil before contact.
  Rendering uses absolute time and seeded data, including nonsequential seeks.
- Source sound mix: 157 placed events, zero clipped samples, peak −2.615 dBFS.
  Exported AAC: mean −26.1 dB, peak −3.7 dB. Motor, food compression and oil
  have independent filters and smooth level envelopes. No music or narration.
- Audio verification covers levels and event alignment; it is not a claim of
  subjective listening approval.

Evidence is reproducible using the commands in `README.md`; local reports,
snapshots, contact sheets and render logs are stored under ignored `qa/` and
`snapshots/`. The exaggerated oil volume is intentional cartoon staging.
The MP4 has not been uploaded to a social platform.
