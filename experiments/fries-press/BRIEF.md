---
workflow: general-video
flow: automation
storyboard: no
message: "A cute chef squeezes increasingly absurd piles of fries under a hydraulic press until oil pours everywhere."
destination: tiktok-youtube-shorts
aspect: 1080x1920
language: en
length: 63.6s
---

## Intent

Adapt the supplied hydraulic-press reference to the approved Watermelon / Chocolate world: chunky pixel art, warm cream background, a white chef's sleeve and supporting palm, satisfying food destruction, and a happy spatula celebration. The user explicitly asks to make the video. Earlier confirmed preferences: videos over one minute, fewer steps, English labels, clear cause and effect, synchronized SFX, a small progression strip at the bottom, normal introduction rather than a destructive teaser.

## Assets

- https://x.com/adventure_bloom/status/2107842852231561384 — movement reference only; 15.073 seconds, studied every 0.25 seconds. The ram descends slowly, the fries compress, then oil drains out near the end. No source footage or source audio appears in this composition.
- ../chocolate-crunch/chef.mjs — approved white sleeve, supporting palm, and happy spatula hand; adapt the carry motion to support the fry tray.
- ../chocolate-crunch/celebration.mjs — approved pixel confetti.
- ../chocolate-crunch/pixel.mjs — approved bitmap lettering and palette system.

## Customizations

- Model a large hydraulic press and individual golden fries in code.
- Three increasing loads: 48, 96, and 192 fries. Compression breaks fries unevenly; oil appears only after contact, spreads around the pressed pile, then runs down the tray and board edges.
- Layer hydraulic motor, dry crunches, wet squeezing, continuous runoff, individual drops and tray foley. No music or narration, consistent with the earlier music deferral.
- Keep the existing videos and application frontend untouched.

## Notes

Original code animation, not an engineering or nutritional claim. Oil volume is deliberately exaggerated for the cartoon payoff. Planned timing: small load 0–18s; medium 18–38s; large 38–60.8s; happy chef 60.8–63.6s. All geometry, particles, deformation and camera poses are functions of absolute time, including backwards seeking.
