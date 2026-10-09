# Two-minute pilot: Tony ruins Sunday dinner

**The Sopranos — S5E10, Cold Cuts.** Tony brings up Janice's son Harpo at the
dinner table, provokes her angry reaction, then claims he is only asking as an
uncle. English dialogue and original written analysis; **no voice-over**.
Primary reference: [ConversationAnalysisGuy](https://www.youtube.com/@ConversationAnalysisGuy).

The photographic Tony head on the short black pawn is approved. Preserve it.
The user wants a roughly two-minute test before extending this format.

## Current revision

The first real pilot was rejected after viewing: missing sound effects,
a wide bar on the right, approximate rating icons and a360p source.
The next test must use a **thin left evaluation bar**, actual Chess.com SVGs,
synchronized typing sound, brief move/rating accents and realHD footage.
After discussing the editing tools, the user also requires a real video editor.
Kdenlive 24.12.3 is installed in this cloud; the deliverable must include an
editable native project and its editor render. No access to the user's PC
or desktop CapCut/Premiere is established.

The ten official SVGs are byte-identical copies of the existing verified
`chess_studio/public/chesscom` assets. Miss is the official yellow minus;
Interesting is observed in the reference but has no established official asset.
The commentary text is original, and the numeric conversation score is an
editorial interpretation, **not a chess-engine calculation**.

## Actual HD source and timing

A normal documented Algrow download request for
[`biugRUTkh1c`](https://www.youtube.com/watch?v=biugRUTkh1c), range99.4–173.9 s,
maximum quality1080p, returned **1280×720**, 30frames/s with original stereo
audio; duration74.533 s. The provider does not list available formats. This
establishes an actual720p source, not native 1080p footage or the maximum quality
of every other upload. Final1080p graphics preserve SVG/text detail.

The media remains private outside Git. `pilot-tony-janice.json` binds its SHA256
and selects local0–74.5 s, trimming the last33ms of padding. Intro16 s plus74.5 s
of footage and five7 s inserts gives a125.5 s timeline. The outdoor walk and later
song are outside this cut; no complete human audio audit is claimed.

The source-relative anchors were reviewed again on the actual HD file:
local ASR, targeted short sections and15selected frames. Waveform correlation
against the previous reviewed source is1.000000 at zero sample lag at each
anchor (8kHz comparison), confirming the99.4 s offset. Do not apply these times
to a different source without review.

| Local anchor | Original upload | Rating | Conversation score, White-positive |
|---|---|---|---:|
|2.55s|101.95s|Book — Tony|−0.3|
|39.55s|138.95s|Great — Janice|−0.3|
|50.20s|149.60s|Brilliant — Tony|−1.8|
|66.20s|165.60s|Blunder — Janice|−4.8|
|71.55s|170.95s|Best — Tony|−4.8|

Tony is Black; Janice is White. The score starts at 0.0 and controls the actual
bar proportions consistently. Best/Great leave it unchanged. This is humorous
conversation control, not a moral rating or a claim of objective measurement.

## Montage and sound

Intro: symbols guide, bar explanation and fade over our own darkened source.
During an evaluation, the grade appears at upper left and the approved pawn at
lower left beside a white speech bubble. Text appears at50characters/s.
The preceding2–4 s replay slowly, blurred and without dialogue. Original
dialogue progression resumes at the saved source timestamp afterward.

Recorded keyboard clacks follow revealed non-space characters and stop when
typing ends. A brief click accompanies each evaluation; Brilliant/Blunder get
one short accent. Normal dialogue sections retain original audio. Added sounds
are CC0 with source pages, processing notes and hashes in `assets/sfx`.
No soundtrack or voice-over is added. Official Chess.com sounds were not
obtained; do not describe these original licensed UI cues as their audio.

Kdenlive should contain separate source, replay, graphics and audio tracks,
so these timings and sound levels remain editable. Preparation of transparent
graphics and WAVs can use scripts; the native project performs the montage
and final export. The independent live sports/TikTok tools remain untouched.

## Delivery status

**Corrected Kdenlive export rendered and inspected:125.504s**,1920×1080,
30fps/3765 frames,H264CRF17/AAC192k. The actual native GUI opened the project:
five tracks, 36media, no missing-resource dialog and correct alpha. A separate
GUI SaveAs roundtrip preserves all 35 actual clip ranges and five tracks; Kdenlive
normalizes wrapper/padding metadata without changing the reviewed clip timeline.

Fifteen final rendered images were examined, including both guide pages, all
five complete bubbles, progressive typing, clear dialogue and the ending.
Full A/V decoding passed. Actual exported PCM confirms rating/typing cues,
silent reading tails, original dialogue between analyses and no clipping.
These checks do not constitute human audio listening.

Private output: `output/conversation-chess/tony-janice-pilot-v2-hd.mp4`, plus
`output/conversation-chess/tony-janice-kdenlive/project.kdenlive` and its media.
After moving the full bundle, `export-kdenlive.py --bundle /new/path --relocate`
updates its media root. The relocated private bundle was checked for all 36 files.
Clips, pauses and sound levels remain editable in Kdenlive. Animated wording
is a separate alpha asset, regenerated from JSON, not a native editable title.

Keep the older rejected file separate. No upload, scheduling, source-rights
clearance or copyright outcome is established.
