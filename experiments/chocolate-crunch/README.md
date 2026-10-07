# Chocolate vs Giant Fork

Original food adaptation of the falling-panel physics experiment, with the chef
and pixel art world from the approved Watermelon film. Five trials: 1, 2, 4, 8
and 16 edible chocolate bars, followed by the happy spatula gesture.

27.8 seconds, 1080×1920, 60fps. English bitmap labels. Entire scene and type on
one 216×384 pixel grid. No music or narration.

Reference: [NodeFan3D, horizontal glass panels on a pyramid](https://www.youtube.com/shorts/ub5r4awGvIc).
The reference is used to study anticipation, progression and debris timing.
Our geometry, animation, chef, sound and rendered frames are original.
The six downloaded study clips and analysis are indexed in
`../physics-references/2026-10-07/README.md`.

## Build and preview

Requires Node 22+, FFmpeg, FFprobe, Python, NumPy and Pillow.

    npm ci
    npm run build
    npm run verify
    npm run check -- --strict
    npx hyperframes preview --background

The nine short SFX WAV variants are frozen local assets. Private generation
receipts describe each prompt, source hash and provider; credentials stay in the
ignored workspace environment. The three small source MP3s are frozen too.
`sound.py` can also reuse the trimmed variants if source files are absent.

## Reproduction

    npx hyperframes render --quality delivery --fps 60 --workers 2 --browser-gpu --gpu --strict-all --output chocolate-giant-fork.mp4
    python qa_frames.py chocolate-giant-fork.mp4

The film is a stylised rigid-body simulation. Intact bars fall until actual fork
contact. Seeded oblique planes produce uneven, closed convex chocolate pieces.
Mass and volume are conserved by the fracture geometry. The fork, board and
floor are collision objects; dense debris uses static-object collisions and a
support guard, with a bounded energy correction for thin wedges. It is not a
full material model or a claim of scientifically exact chocolate behaviour.

Physics is integrated offline at 240Hz and stored at 120Hz; preview and export
sample absolute poses. Contact events trigger all 31 major crunch accents.
Wooden landings share 40ms groups and a restrained crumb tail. Linear gain keeps
headroom; no saturator is used.

The existing Watermelon project is preserved. Channel name and posting remain
the user's decisions.
