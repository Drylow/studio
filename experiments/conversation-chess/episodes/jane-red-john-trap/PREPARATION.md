# Patrick Jane vs Red John's Trap — preparation

Short-clip test for **Scene Analysis Guy**, made under the explicit user exception recorded in
[COPYRIGHT_RELEASE.md](../../COPYRIGHT_RELEASE.md) (15 Oct.): very short real extracts, Death Note V3
model, private-first upload. If YouTube claims or blocks it, the channel switches to the no-clips format.

## Source

- Clip.cafe has little Red John material in usable quality (S06E08 church ≈ 40 s at 1916×1076,
  S03E24/S04E24 absent). Chosen instead: **S01E23 "Red John's Footsteps"**, Jane vs Sheriff Hardy
  (Red John's accomplice), framed by two Jane/Lisbon exchanges about Red John.
- Four public clips, 1920×1080 at 23.976 fps, no logo or watermark seen. Conformed to 30 fps without
  resize. No mirror, pitch change, crop or reframing.
- [source-map.json](source-map.json): 3 chapter cards (3 s each) + 7 cuts, master 98.833 s,
  **89.83 s of played scene**.

| Chapter | White | Black | Content |
|---|---|---|---|
| HE'S MINE | Jane | Lisbon | "Red John is mine… you will regret it." |
| THE TRAP | Hardy | Jane | Hardy caught, nicotine gum, "I'll try to persuade Red John…" |
| CHOOSE LIFE | Lisbon | Jane | "We saved a girl's life" → "some things you just can't fix." |

## Timeline and captions

- [timeline.json](timeline.json): Death Note V3 settings (neutral pawn, pawns follow the speaker's camp),
  16 s guide with Sneaky Snitch, 7 analyses of 7 s with 2 s muted replays, 12 s recap.
- Speakers checked on native frames. Word timings come from a speech-recognition pass on each clip
  (decoded with timestamp resync) mapped onto the cuts; misheard words fixed against the Clip.cafe
  transcripts. Analyses start after the last word of their line.
- Captions: 45 cues, all inside dialogue rows, none over chapter cards.

## Export and QA

`render-clip.mjs --validate-only` → `--prepare-project` → `export-kdenlive.py` (Kdenlive 24.12 AppImage
under the Xvfb wrapper) → `check-native-export.py`: full decode and audio QA pass (sample peak
−1.37 dBFS). All 10 contact sheets inspected one by one (intro, 3 chapters, 7 analyses, 42 boundary
frames, recap): no caption over cards, correct pawn colours and bar, nothing cut. Final 2:55.8.
Summary in [qa-summary.json](qa-summary.json).

## Thumbnail

[Jane-Hardy-trap-YouTube.jpg](Jane-Hardy-trap-YouTube.jpg): same style as the published covers (two
real frames, diagonal white separator, original Brilliant/Blunder icons via `compose-thumbnail-badges.mjs`).
New scene: Jane (left) and Hardy hands behind his head (right), from the trap clip, brightened only.
