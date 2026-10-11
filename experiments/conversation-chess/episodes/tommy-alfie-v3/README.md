# Tommy–Alfie V3 — editorial draft, not a cleared export

**Short candidate retained as an archive.** The user now requires at least ten
minutes, targeting ten to fifteen. This 5:20 native test is not the requested
long and must not be delivered as its replacement. Long recut work is separate
in `../tommy-alfie-long-v3/`. The native export and sample-accurate audio finish
have passed full decoding and technical QA locally; that establishes no
YouTube acceptance. No GoFile or Discord delivery of this short was made.

The user requested a new Tommy–Alfie edit after the original 15m28 export was
claimed and blocked in some territories. Landa–Shosanna is the first production;
this folder prepares the next edit without rendering or replacing the archive.

## A complete negotiation instead of three extended encounters

Keep the S02E06 negotiation: Tommy provides a valuable export document; Alfie
changes the agreed 20% to 100%; Tommy refuses to sign, presents mutual risk,
covers Alfie's attempted exit, supports his credibility and settles at 35%.
This is a complete change of bargaining power. The initial bakery meeting and
the later moral confrontation are omitted entirely rather than compressed into
unexplained highlights. The original three-episode master and approved Shelby
pawn remain untouched.

The proposed retained dialogue lasts **229.13 s**, in 14 explicitly authored
cuts. Nine original analyses of 7 s, the 16 s native guide and the 12 s native
outro would make **320.13 s (5m20.1)**, before any corrections made in review.
These durations follow this story; they are not copyright thresholds.

`edit.draft.json` uses the source-edit schema but deliberately keeps
`source_visually_reviewed: false`, so the preparation helper must reject it
until the selected source cuts have actually been reviewed. `timeline.draft.json`
preserves the initial source-coordinate draft, without changing its pending
review flags. The newer `edit.candidate.json` and `timeline.candidate.json` are
ready for native source preparation on the precise visual/timing evidence below.
They do not approve a final export, moving/audio raccords or a YouTube result.

## What has been checked now

- The local S02E06 episode exists, matches its recorded SHA256, and ffprobe
  reports H264 1280×720 at 25 fps with AAC audio, duration 3527.04 s.
- The local English soft subtitle reference was read across the full
  negotiation. It establishes the progression and supplies dialogue anchors.
- The cuts are ordered, inside the episode, and quantized to 30 fps. Each
  proposed annotation belongs to exactly one cut. Counts are computed from
  these nine annotations, not copied from the old 32-move export.
- The existing word-timed ASR was checked in absolute episode coordinates:
  its original script had already added the 300 s extraction offset. The current
  episode matches the contemporaneous source inventory. The old ASR header
  stores a filename but no input SHA; `word-boundary-review.json` records that
  limitation, not a cryptographic binding absent from the original artifact.
- Seven boundaries crossed recognised words and were moved. Four short ASR
  windows were then transcribed from the current SHA-verified source, without
  VAD or a prompt supplying dialogue. They recovered the initial “If” at the
  shared-risk condition and exposed an eighth boundary to fix. There are now
  zero crossings of recognised words at the 28 cut boundaries and nine pauses.
- The targeted ending recognises 35% in Tommy's offer and Alfie's acceptance;
  the older long ASR had misheard 45%. The short Why window locates the utterance
  but still mishears its text as “What?” with low confidence. Speech recognition
  remains an estimate, not a complete alignment or listening review.
- **37 native source stills** were examined in cut order on four contact boards:
  both ends of all 14 cuts and each of the nine annotation points. No burned
  subtitle or watermark was visible in these samples. `visual-sample-review.json`
  records board hashes and observations. The first-concession final sample
  contains source motion blur on Ollie; the moving cut still needs review.
- No boundary listening, continuous moving-scene review, final render or
  YouTube check has been performed. Only the specified source quality,
  source-timing and still-review evidence supports the preparation candidate.

The stored entitlement manifest was inspected without exposing URLs or IDs:
its single S02E06 item lists quality720p and maxHeight720. The current source
measures 1280×720/25 fps and matches its separate contemporaneous inventory SHA.
The earlier safe acquisition receipt has downloaded:false, so it is not used
as proof of a completed download. `quality-evidence.json` records the exact
manifest hash and safe fields. This is stored evidence, not a fresh network
response. Keep the
footage at its real resolution; final 1080p graphics do not make it native1080.
Access to an episode is not a reuse licence.

## Opening, camps and native elements

The first retained line is Tommy presenting the signed export document, anchored
by the local cue at **406.38–408.499 s**. Tommy therefore remains White and Alfie
Black. The candidate records the new opening's actual document-handoff stills,
subtitle reference and recognised speech evidence; it claims no listening.
The old S02E02 payroll evidence is not copied into this cut.

Reuse `assets/peaky/shelby-pawn-approved-2026-10-11.png` without alteration for
the guide, analysis mascot and native outro. The approved image is separate from
the white/black pawns in the evaluation bar. Keep the left bar and checksum
verified Chess.com icons. No Miss or purple Interesting badge. English dialogue
and written analysis, no voice-over. Typewriter/grade SFX remain in the native
tool. Intro music only; no added music under scenes or analyses. Required music
attribution accompanies the eventual publication description.

## Before using this draft

1. Review all 14 source cuts in motion and the omitted material needed for context.
2. Align the actual episode audio at word level. Refine every boundary to avoid
   clipped syllables, incomplete lines or misleading reaction continuity.
   The known recognised-word intersections have been corrected, but the ASR
   has omissions and errors. The current numbers are candidates, not a
   clean-audio claim. Check the short transitions and original source music too.
3. Rewrite the original analyses if a source boundary or dialogue changes.
   Remap source-coordinate times to the prepared scene at 30 fps, then insert
   the analysis pauses. Update the source hash and new opening evidence.
4. Use the updated `prepare-source-edit.py`, which accepts explicitly reviewed
   native dimensions and episode-specific opening/camps. Its `plan_edit`
   preflight has passed for this candidate without encoding media; the result
   is recorded in `preparation-preflight.json`. Preserve native720 dimensions.
5. Render a new Kdenlive/MLT bundle, measure dialogue loudness before choosing a
   gain, decode the full output, review images and listen to each new raccord.
6. Verify the generated native outro reports Brilliant1, Great2, Best3, Book2,
   Good1, and zero in the other four categories. These are editorial judgments,
   not engine calculations or accuracy percentages.
7. Record a YouTube check for the exact final MP4 separately. The previous
   blocked export and a colleague's Death Note result establish no clearance
   for this cut. Do not describe this draft as bypassing Content ID or guarantee
   that it can earn revenue.

No mirror, pitch change, concealment crop, watermark or quality degradation is
proposed. Each omission has a narrative reason in the edit file. Final words
must finish before the ending fade; use tiny boundary fades only to avoid clicks.

## Grades after editorial review

The initial four Brilliant candidates were reduced to **one**. Tommy's shared
downside condition changes the balance of the whole negotiation. Covering the
exit develops that plan and is Great, rather than a second independent brilliant
reversal. Settling at 35% converts existing leverage and is Best. Alfie's 100%
demand is Book: a coercive squeeze backed by control of the room, without proof
of an unusually brilliant strategic choice. The grades follow the decisions
shown; they are not chosen to make the final counts look spectacular.

## Preparation paths

From the repository root, choose a fresh output directory:

```bash
python experiments/conversation-chess/prepare-source-edit.py \
  --source output/conversation-chess/peaky-resume-source/peaky-blinders-s02e06-english-acquired.mp4 \
  --edit experiments/conversation-chess/episodes/tommy-alfie-v3/edit.candidate.json \
  --out output/conversation-chess/tommy-alfie-v3-source-edit
```

The helper reads `timeline.candidate.json` from the edit's folder and prepares
`scene-edit-1280x720.mkv` plus a remapped `timeline.json` in the output directory.
The expected source contains 6,874 frames. The final native project should
contain 9,604 frames after the guide, nine analysis pauses and the outro.
The preparation command has **not** been executed here: the parent production
task owns encoding and the actual Kdenlive/MLT export, preventing parallel work
on the same media. No previous source, render or approved pawn was replaced.
