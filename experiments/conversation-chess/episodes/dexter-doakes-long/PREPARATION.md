# Dexter–Doakes — native long export, 15 October 2026

## Request and subject change

The user asked for a new Scene Analysis Guy long (« pour Scene Analysis Guy, il
faut une vidéo aussi »). The requested subject was **Jimmy McGill vs Chuck McGill**
(Better Call Saul), sourced from public Clip.cafe clips, with **Dexter vs Doakes**
as the first fallback if Clip.cafe lacked clean material for at least 10 minutes.

All 1,328 public Better Call Saul clips listed on Clip.cafe were indexed (title,
transcript, episode badge, size). The key Jimmy–Chuck conversations are missing:
no clip of the S01E09 HHM reveal ("You're not a real lawyer" appears only inside a
"Previously on" recap), only four S03E05 *Chicanery* clips (none of the
cross-examination) and no S03E10 final conversation. What remains is mostly
Season 1 caretaking small talk, which cannot carry the arc. **The fallback,
Dexter Morgan vs James Doakes, was therefore used.** About 6,900 public Dexter
clips were indexed the same way; the Dexter–Doakes material below is native 1080p.

## Current state

**Native export, technical QA and sampled visual review complete.** Kdenlive
24.12.3 / MLT exported **25,719 frames / 857.3 seconds of picture — 14:17.3** —
at 1920×1080, 30 fps, H264 CRF17 / medium, AAC 48 kHz stereo. Container duration
857.301 s, 426,063,023 bytes. Native export SHA256:
`81f8b70cfc15be9535d758b2a2196311820814d32849dc8290ae6b01bb67541e`.

The [authored timeline](timeline.json) holds **eleven conversations** and
**32 original analysis holds of eight seconds** (3-second muted replays), the
16-second guide and the 12-second recap: 573.3 s of source master (with eleven
3-second chapter cards) + 256 s of analysis + 28 s. The native project keeps
**235 editable English dialogue captions** (V4 titles), shown only during
dialogue. There is **no added voice-over**. The Ubuntu Kdenlive 23.08 package has
no command-line render, so the official Kdenlive 24.12.3 AppImage (extracted, no
FUSE) was used through the existing Xvfb wrapper.

## Eleven conversations and reviewed White openers

Each conversation resets to 0.0 / 50–50; White is the first retained speaker,
checked on native frames (mouth movement, shot) and two speech recognitions.

| # | Episode | Chapter | White / first retained line | Purpose |
|---|---|---|---|---|
| 1 | S01E07 | I'm Watching You | Dexter — "Excuse me?" | Doakes' praise turns into suspicion. |
| 2 | S01E12 | Surprise, Morgan | Doakes — "Surprise, motherfucker!" | Doakes catches Dexter at the port. |
| 3 | S02E01 | Caught in the Lab | Dexter — "Hey, Sergeant." | The fake alibi on the laptop. |
| 4 | S02E03 | The File | Dexter — "What exactly is it you think I've done?" | Doakes recites his dossier. |
| 5 | S02E07 | I Own You | Dexter — "You finally decided to fight back." | Open war in the lab. |
| 6 | S02E09 | The Everglades | Doakes — "All right, nice and slow." | Gun drawn, then the cage. |
| 7 | S02E10 | The Cage | Doakes — "If you want to bring me down, Morgan…" | First exchanges through the mesh. |
| 8 | S02E10 | Harry's Secret | Doakes — "You think you're a fucking hero, don't you?" | Doakes finds Dexter's weak point. |
| 9 | S02E10 | The Final Victim | Doakes — "Who the fuck is that?" | The frame-up is announced. |
| 10 | S02E11 | Turn Yourself In | Doakes — "No, no, Morgan, you're spinning." | Doakes argues for surrender. |
| 11 | S02E11 | Last Words | Dexter — "I've really enjoyed our conversations, James." | The farewell. |

Conversation 6 joins two consecutive public clips labelled S02E09 by Clip.cafe
(the dock, then Doakes caged). Within an episode, clip order follows the
narrative logic of the public clips; ellipses between clips are hard cuts, as in
the Hannibal long. Scores and grades are our editorial reading of the dialogue,
not chess-engine output. The 32 grades are Brilliant 6, Great 6, Best 7,
Excellent 2, Good 1, Book 7, Inaccuracy 2, Mistake 1, Blunder 0 — read back on
the exported recap.

## Sources (public Clip.cafe clips, native 1920×1080, 23.976 fps)

Nineteen clips, conformed to 30 fps without resizing by
`prepare-source-master.py`; the master's full A/V decode passed. Master SHA256:
`db25ed2eb1beaf7a8323045b47d3f67c114b858de28297f59bdac0be765f9cf4`
(17,199 frames, 573.3 s). Exact cuts are in [source-map.json](source-map.json).
Video bitrates are low (about 0.25–1.1 Mb/s), so facial detail is softer than a
disc master; native HD is accepted, maximum source quality is not claimed. No
broadcaster logo, Fandango mark or burned caption was seen in the reviewed frames.
No YouTube download was used.

| Chapter | Episode | Clip.cafe page | Cut (s) | Clip SHA256 |
|---|---|---|---|---|
| I'm Watching You | S01E07 | [excuse-me-s1199](https://clip.cafe/dexter-2006/excuse-me-s1199/) | 0.9–35.4 | `2c6199b2f2d5ffb094c107bef2f09c5b16baa24e796dc00e9ceb215cec7370e6` |
| Surprise, Morgan | S01E12 | [shit-surprise-motherfucker-are-you-follo](https://clip.cafe/dexter-2006/shit-surprise-motherfucker-are-you-following-me-now-you-better-have-a-reason-for-being-here/) | 4.4–32.4 | `84e6e5ea2d78e12b5ec2a5d9992c9ec39ac0a991c57aafbe93a32f130ec89d16` |
| Surprise, Morgan | S01E12 | [lab-geek-ass](https://clip.cafe/dexter-2006/lab-geek-ass/) | 0.6–19.4 | `d40346fa9c22fdea4d40dbe3d249c96ce48758a7f8bc1ae81988602ff69b2cf1` |
| Caught In The Lab | S02E01 | [hey-sergeant-s4](https://clip.cafe/dexter-2006/hey-sergeant-s4/) | 0.4–8.4 | `efc6f700cf227c5e8fc4770af5823e3aab15e86655d79c291418584f97c35a7f` |
| Caught In The Lab | S02E01 | [so-whats-that-a-titty-site](https://clip.cafe/dexter-2006/so-whats-that-a-titty-site/) | 0.5–37.8 | `a6d05235b8e09dd6e5ce48bd72c780766ca52e9000c4d8bc7cd1180aea701ee6` |
| The File | S02E03 | [what-exactly-is-it-you-think-lve-done](https://clip.cafe/dexter-2006/what-exactly-is-it-you-think-lve-done/) | 0.3–24.4 | `4d5079df76f7e124cd05d09ad95bcbd5df590252b8bd89ea1340cd5bf8f118cc` |
| I Own You | S02E07 | [you-finally-decided-to-fight-back](https://clip.cafe/dexter-2006/you-finally-decided-to-fight-back/) | 0.5–60.6 | `3e8f84b62a999effd89e397d6288db63d3662361dfa132324bc5acfa896cb216` |
| The Everglades | S02E09 | [all-right-s2709](https://clip.cafe/dexter-2006/all-right-s2709/) | 1.4–10.6 | `df3b60a7ea6a4e7da65978e95fbd9db58e0cd1d8b450da1cfcc0601fb2fca4a9` |
| The Everglades | S02E09 | [youre-gonna-have-to-kill-me-morgan](https://clip.cafe/dexter-2006/youre-gonna-have-to-kill-me-morgan/) | 0.5–9.0 | `9d2209ef9e2549daf6525861482274b71f7c4079d18bf72a29034d7feee6520f` |
| The Cage | S02E10 | [lf-you-want-to-bring-me-down-morgan-your](https://clip.cafe/dexter-2006/lf-you-want-to-bring-me-down-morgan-youre-gonna-have-to-open-this-goddamn-cage-first/) | 0.2–13.6 | `94bbf65f7c25b37d3c0d0e09ab42fb8f2aef8f439a301a956a41b6d52fc8bbdb` |
| The Cage | S02E10 | [lm-sure-special-ops-taught-you-to-rattle](https://clip.cafe/dexter-2006/lm-sure-special-ops-taught-you-to-rattle-your-captor/) | 0.6–17.2 | `89bf3f95d4a66fe120ddce444e257d3e0c8873c66a9bb4fa2c5131b216d141a9` |
| Harry's Secret | S02E10 | [you-think-youre-a-fucking-hero-dont-you](https://clip.cafe/dexter-2006/you-think-youre-a-fucking-hero-dont-you/) | 0.3–45.8 | `3ffa84b512a94de174a4f7d8a29c814a305d9a58c2e7384ecf9db9653274cc8e` |
| Harry's Secret | S02E10 | [what-was-that-shit-last-night](https://clip.cafe/dexter-2006/what-was-that-shit-last-night/) | 0.3–47.4 | `8bf2e0f43835e284160f153cd2085a604136febd0208589e107fb286f186bc3e` |
| Harry's Secret | S02E10 | [lts-a-small-conscience](https://clip.cafe/dexter-2006/lts-a-small-conscience/) | 1.0–51.4 | `a03bfc649f66a4cfde78895a7d7037db3ced773063eab54b568189a886820aa5` |
| The Final Victim | S02E10 | [who-the-fuck-is-that-s3](https://clip.cafe/dexter-2006/who-the-fuck-is-that-s3/) | 0.5–40.8 | `ce77e85eee67403b216c2acf6c8e3679e401bfb8c4070bc6bc0a1c197de65bb7` |
| Turn Yourself In | S02E11 | [lts-the-only-way-l-know-how-to-live](https://clip.cafe/dexter-2006/lts-the-only-way-l-know-how-to-live/) | 15.3–48.6 | `78469bf6f268b1c5280d97e765cc09c5f8ed00e29e02df900478e4ed8d75202d` |
| Turn Yourself In | S02E11 | [better-than-watching-me-dragged-in-like-](https://clip.cafe/dexter-2006/better-than-watching-me-dragged-in-like-an-animal/) | 0.7–41.4 | `3ae63407ad14c16f7af53217cb65b9147458eff3ac8c01fcb18061d6c9d89525` |
| Last Words | S02E11 | [ive-really-enjoyed-our-conversations-jam](https://clip.cafe/dexter-2006/ive-really-enjoyed-our-conversations-james/) | 3.0–17.6 | `cb8bb61a3627483b84dbc3c660bf05cbb60fd8bc02954f1eca2ca31c0f79790b` |
| Last Words | S02E11 | [sorry-about-the-cage](https://clip.cafe/dexter-2006/sorry-about-the-cage/) | 0.5–10.4 | `769d80129811f655cb919ea710bab52cf213542cd22326a42f8ee68da9bf38b6` |

Rejected candidates included clips with Dexter's inner voice-over only, clips with
other characters (Lila, Lundy, LaGuerta) and lines whose wording could not be
confirmed (for example the end of "Do you know what an easy credit is?", cut).

## Captions

Captions were built from word timings (faster-whisper medium.en) of each source
clip, mapped onto the master cuts and cross-checked against a second recognition pass per clip and the
Clip.cafe subtitles. Names and obvious mishearings were corrected (Masuka,
"Lab geek, my ass", "Security, I need to get somebody down here"). Two phrases
heard identically by both recognisers are kept as heard ("Call me an office
crazy, but your humbling interest…", "Is this why you're in a cage?"). No human
listening of the full film is claimed.

## Analyst pawn

New [Dexter pawn](../../assets/dexter/dexter-pawn-2026-10-15.png) with its
[receipt](../../assets/dexter/dexter-pawn-2026-10-15.json): a black-and-white
head cut from a real S01E07 frame, set on the unchanged black body of the approved
Hannibal pawn, with the renderer's original Chess.com companion badges. It was
built for this delegated request and has not been separately approved by the user.

## Actual QA results

Full A/V decode of the exact export returned zero with an empty error log.
Technical audio QA passed with no failures or warnings: 87 audio segments
correlated with the prepared tracks, 32 quiet reading tails and 32 single grade
cues verified. Sample peak −0.43 dBFS, true peak −0.3 dBTP, no decoded sample at
full scale (the source clips are mixed hot; there is no clipping, but little
headroom). See [qa-summary.json](qa-summary.json).

## Visual review and corrections before delivery

The final export was reviewed on 29 contact sheets (225 captures): the root
reviewer inspected all 32 analyses, the five guide captures, the eleven chapter
cards and three recap captures; two independent reviewers inspected the 174
boundary and caption captures. No defect remains.

Two earlier exports were rejected before delivery. A first transcription of the
whole master was decoded without its audio timestamps and drifted up to about
0.65 s late in the film (the master itself is in sync, checked by
cross-correlation with the original clips). As a result three captions touched
chapter cards and several analysis holds started on the last syllable of a line.
Captions and all 32 hold positions were re-derived from per-clip timings, every
hold was re-checked against the speech around it, and one hold (m04) was moved
after "In a cargo box?" because the next line starts immediately. Known source
limitations: compressed faces, and a warped Doakes close-up in the S02E07 clip
(about 4:36–4:57 in the film), present in the public clip itself.

Two-line captions keep the renderer's existing alignment. No continuous human
playback or listening review is claimed.

## Hosting and delivery

- Studio server (download for the publishing PC):
  `http://media.edgerunners.fr/scene-analysis-guy--dexter-vs-doakes-75bb3f0b7ccc5960.mp4`
  — uploaded in 400 MB parts by `production/daily/host_video.py --mp4`, re-joined on
  the server, downloaded back and SHA-256 verified.
- GoFile backup: <https://gofile.io/d/o25ulc0t> (MD5 confirmed by the upload response).
- Queue file: `production/publish/queue/scene-analysis-guy--dexter-vs-doakes.json`,
  scheduled for 16 October 2026 at 10:00 (Brussels), `copyright_check: private_first`.

## Rights

These are excerpts of a commercial series without an established licence. No
result of YouTube's copyright checks can be promised. The publishing PC uploads
privately first and waits for YouTube Checks (`copyright_check: private_first`).
