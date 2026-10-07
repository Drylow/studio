# Chocolate vs Crazy Tools

Original food adaptation of the falling-panel physics experiment, with the chef
and pixel art world from the approved Watermelon film. The revised progression
has two quantities per tool: fork 1 / 4 bars, spring boxing glove 4 / 8 bars,
upward jackhammer 8 / 16 bars, then the happy spatula gesture. Three quick
salvos per quantity use different fracture geometry. A compact bottom strip
shows every tool from the first frame, the current selection and completed tools.
It replaces round captions, with smaller sprites and centred action.

66.7 seconds, 1080×1920, 60fps. English bitmap labels. Entire scene and type on
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

The eighteen short SFX WAV variants are frozen local assets. Private generation
receipts describe each prompt, source hash and provider; credentials stay in the
ignored workspace environment. The six small source MP3s are frozen too.
`sound.py` can also reuse the trimmed variants if source files are absent.

## Reproduction

    npx hyperframes render --quality delivery --fps 60 --workers 2 --browser-gpu --gpu --strict-all --output chocolate-crazy-tools-final.mp4
    python qa_frames.py chocolate-crazy-tools-final.mp4

The film is a stylised rigid-body simulation. Intact bars fall until actual fork
contact. The glove strikes chocolate held in position; the other two mechanisms
meet falling bars. Seeded oblique planes produce uneven, closed convex pieces.
Mass and volume are conserved by the fracture geometry. The fork, board and
floor are collision objects; dense debris uses static-object collisions and a
support guard, with a bounded energy correction for thin wedges. It is not a
full material model or a claim of scientifically exact chocolate behaviour.

Physics is integrated offline at 240Hz and stored at 120Hz; preview and export
sample absolute poses. Contact events trigger all 123 major crunch accents.
`tools.mjs` shares mechanism positions between physics and visible props. New
spring creak, boxing thump and motor accents follow those actions.
Wooden landings share 40ms groups and a restrained crumb tail. Linear gain keeps
headroom; no saturator is used.

The existing Watermelon project is preserved. Channel name and posting remain
the user's decisions.
