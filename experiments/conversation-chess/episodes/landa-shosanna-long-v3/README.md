# Landa’s Mind Games — long editorial handoff

Latest outcome, 11 October 2026: the user reports publication with Content ID
claims, without a reported block or strike. No independent account check or
rights clearance is established. [Reported outcome](PUBLICATION.md#youtube-outcome-reported-after-delivery).

This edition contains two distinct verbal duels: Landa–LaPadite at the farm,
then Landa–Shosanna at the restaurant. The approved Landa pawn and native
Chess.com graphics apply to both chapters. Landa speaks first and plays White;
the Black label and evaluation reset when the restaurant starts.

The completed native export confirms **13:18.933**. The ten-minute user minimum is satisfied without
slowing, looping or repeating dialogue. No massacre or flight is included.

| Item | Farm | Restaurant |
| --- | --- | --- |
| Input | Raw compilation; apply `edit.candidate.json` | Raw compilation; apply `edit.candidate.json` |
| Source frames, 30 fps | 15 843 | 2 662 |
| Source duration | 528.1 s | 88.733333 s |
| Retained frames | 12 913 | 2 115 |
| Retained duration | 430.433333 s | 70.5 s |
| Written analyses | 21 × 9 s | 9 × 9 s |

The combined retained scene has 15 028 frames / 500.933333 seconds. Add 270
seconds of analysis holds, one 16-second guide and one 12-second recap. The
second duel’s three-second camp change is displayed within its footage rather
than as an extra card. Replay windows last three seconds inside each analysis
hold and do not increase this budget.

## Inputs and exact source bindings

Farm files: `farm/timeline.candidate.json`, `farm/edit.candidate.json`,
`farm/captions.edited.srt`, `farm/CAPTION_MAP.json`, `farm/SCENE_SPEC.json`.
The SHA bound source is:

`output/conversation-chess/landa-shosanna-long-v3/farm-source-compiled/farm-compilation-1080p.mkv`

SHA256: `4acdea1066ec9f14b1f92e66b5d701d3bfbcd821874fecde2799998b8290aad6`.
The actual 1920×1080 master fully decodes: 15 843 frames, 25 348 800 samples per
channel at 48 kHz stereo. All picture timestamps are unique and follow N/30
within Matroska’s 1 ms rounding; last picture PTS is 528.067 s. Root repaired
invalid staging timestamps by preserving all ordinal frames and independently
concatenating the original audio. The final decode log is empty.
The final remux also fixes PCM packet timestamp rounding with an explicit
48 kHz audio encoder clock; every decoded picture and audio packet is within
1.1 ms of its frame/sample clock. Encoded picture payloads are unchanged by
that last remux. Exact sample counts are verified for every retained cut.

Restaurant files: the same three candidate/edit/SRT names under `restaurant/`,
plus `restaurant/SCENE_SPEC.json`. Its existing source remains read-only:

`output/conversation-chess/landa-shosanna/source-compiled/source-compilation-1080p.mkv`

SHA256: `6f03353c9c4accf2298ca4e8e5974e37e4cceba1f24a24cac207484deb715d52`.
The dedicated long restaurant edit retains the complete forgotten-question
beat and differs from the archived short edition. Root already prepared its
70.5-second retained scene separately.

## Caption and review clocks

Both SRT files use the **retained scene clock before guides or analysis holds**.
Remap holds and offset the restaurant after the retained farm footage. Farm
contains 108 positive, non-overlapping cues bounded by its 430.433333-second
scene; the independent wording review corrected Miriam and the farmer’s
continuing enumeration “And the children,”. No absent reply is captioned.
French source speech has English reading text; this is not described as English
word-level ASR or a new dub.

Farm review evidence is saved under
`output/conversation-chess/landa-shosanna-long-v3/farm-exact-review/`:
53 actual pause/boundary stills viewed as six boards, a receipt and two real
corrected-clock samples near 241.267 and 526.133 seconds. Restaurant review is
in `restaurant-exact-review/`. ASR, official VTT and measured waveform envelopes
support the boundaries. No continuous human audio listening is claimed.

Technical QA and sampled final-frame review are complete, including the recap
counts. Continuous playback, human listening to the raccords and private
YouTube Checks have not been performed. Public-player source access is not a
commercial licence or a promise of no Content ID claim. No mirror, pitch,
colour disguise, watermark removal or rejected-source workaround was used.

`EDITORIAL.md` describes the argument, omitted fragments and rating rationale.
The earlier short candidates remain archived and unchanged.

## Assembly

From the repository root, apply `prepare-source-edit.py` separately to the two
bound raw sources and edits, using fresh output directories. Then run:

```bash
python experiments/conversation-chess/episodes/landa-shosanna-long-v3/assemble-two-duels.py \
  --farm /path/to/prepared-farm --restaurant /path/to/prepared-restaurant \
  --farm-captions experiments/conversation-chess/episodes/landa-shosanna-long-v3/farm/captions.edited.srt \
  --restaurant-captions experiments/conversation-chess/episodes/landa-shosanna-long-v3/restaurant/captions.edited.srt \
  --out /path/to/fresh-combined-source
```

The assembly requires the actual native layout preflight receipt under
`output/conversation-chess/landa-shosanna-long-v3-layout-review/`. It verifies
that its counts and summary still match; it does not approve a final film.
The resulting timeline requests a two-decibel dialogue reduction for peak
headroom. Each new export requires technical audio QA; the completed export
below has passed that check.
Pass its timeline and source to `render-clip.mjs --prepare-project
--discard-frame-caches`, then export the native Kdenlive bundle with the merged
source-clock SRT. `--hardlink-media` saves space when both directories share
one filesystem and the linked assets remain immutable.

## Completed native export and sampled final review

The closed native MP4 measures **23 968 frames / 798.933333 s / 13:18.933**,
1920×1080 at 30 fps; its SHA256 is
`42dcf2c2ced45ea1325b5986ec319923c682368ce9932ae90f3714d568225077`
and its size is 351 663 692 bytes. Full A/V decode, exact sample counts,
65 prepared-audio correlations, 30 grade onsets and 30 quiet reading tails
pass; measured mix true peak is −3.2 dBTP.

The final-file review inspected 172 distinct decoded captures on 24 contact
boards: 30 analyses, 130 native transitions, 5 guide states, 3 recap states and
4 longest-caption samples. The second duel resets labels and score to 0.0
at frame 19 063; the recap totals 30. Root reviewed transitions/captions, and
an independent reviewer checked analyses/guide/recap. This is sampled
visual inspection, not continuous playback or human audio listening.
Retained proof is under
`output/conversation-chess/landa-shosanna-long-v3-native/qa/`, especially
`native-qa-handoff.json`, `delivery-review.json` and the component reviews.

The five-file kit is uploaded to [GoFile](https://gofile.io/d/JEZfRO10).
The official public web listing confirms the film, thumbnail, titles, complete
description and music credits. The strict `--verify-existing-web` reconciliation
passed and bound all five files to the delivery manifest; the pending state is
archived. Discord delivery is confirmed by its own receipt: one message and
three attachments. These are delivery confirmations, not a YouTube publication
or commercial clearance.

The publication candidate remains `youtube-test`; no platform Checks,
commercial footage clearance or absence-of-claims guarantee is recorded.
[The method comparison](METHOD_REVIEW.md) records how the supplied TXT was
applied and the differences from its much shorter Death Note example.
