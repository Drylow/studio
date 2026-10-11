# Approved Landa analyst pawn

On 11 October 2026 the user accepted the displayed Landa pawn with one condition:
add the same companion brilliant (!!) and blunder (??) badges as the other
analyst pawns. The approved PNG is kept byte-for-byte; its SHA256 is recorded
in `landa-pawn-approved-2026-10-11.json`.

Use this episode option relative to the conversation renderer:

```json
"mascot": {
  "file": "assets/landa/landa-pawn-approved-2026-10-11.png",
  "badges": true
}
```

`scene.js` draws the hash-verified original Chess.com SVGs beside the contained
portrait in the symbol guide, written analyses and recap. It does not alter
the photo or redraw the icons. Badges are disabled by default, preserving
existing pawns with their own embedded badges, including Shelby. Do not enable
this option on a PNG already containing badges.

Four actual 1920×1080 canvas frames were examined for placement, at the guide,
analysis entry, fully revealed analysis and recap. They showed no overlap with
the face, bubble or evaluation bar. Four equivalent default Shelby frames
were pixel-identical to the previous scene. Preview files and the detailed
receipt remain in `output/conversation-chess/landa-mascot-badge-review/`.
These checks approve the companion layout only; they do not review or clear
a final scene, movie, soundtrack or YouTube copyright result.
