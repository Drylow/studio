# History finishing and verified delivery

These helpers preserve the completed Viking/Pirate workflow and support a new
episode through explicit paths, its actual project ID and its measured clock.
They do not write a script, choose references, generate images, approve an image,
start a render or publish to YouTube.

For generation/rendering use the maintained [TubeForge client and guide](../tubeforge_support/forge_docs/README.md),
[endpoint inventory](../tubeforge_support/forge_docs/endpoints.json) and native
[API implementation](../tubeforge_support/forge_api.py). The full application is
already in `production/tubeforge_base` and `production/tubeforge_support`.
There is no ZIP installer prerequisite. The publication handoff is separate:
[POSTING_HANDOFF.md](../handoff/POSTING_HANDOFF.md).

## Install and private workspace

Run evidence helpers with normal Python, without `-O` or `PYTHONOPTIMIZE`, which
would disable assertions. Those helpers reject optimized execution.

Python **3.11+** is required by these helpers (`hashlib.file_digest`). The canonical
remote client supports Python 3.10+. Install FFmpeg and FFprobe using the host's
normal package manager, then from the repository root:

```bash
python -m venv .venv-history
.venv-history/bin/python -m pip install -r production/history_delivery/requirements.txt
.venv-history/bin/python -m playwright install chromium
```

The requirements declare compatible ranges; they are not an exact environment
lock. `HISTORY_FFMPEG` and `HISTORY_FFPROBE` can select binaries. The normal-site
GoFile reader uses Playwright's installed Chromium by default;
`HISTORY_CHROMIUM_PATH` can select an existing system Chromium and
`HISTORY_BROWSER_PYTHON` can select a separately provisioned browser interpreter.
The uploader uses Unix `fcntl` locking and private modes: run it on Linux/macOS
or the existing VPS, not directly in Windows Python.

Store working episodes, recordings, API sessions and browser profiles **outside
the public checkout**. The canonical client uses `FORGE_SESSION_FILE` or
`FORGE_SESSION_TOKEN`; login reads a personal member access key without echoing it.
Never copy the colleague's member session, SSH key, shared worker trust token or
provider credentials into Git. Use the member's normal portal authorization.
The supplemental HTTP/2 transport keeps normal TLS verification, refuses redirects
and sends authorization only to the canonical portal. It is not an access bypass.

## Supported tools and evidence

| Helper | Real operation and limits |
|---|---|
| `selected_source_provenance.py` | Creates a new selected plan from genuinely reviewed images; hashes actual files. Keeps declared prompts and actual generation receipts separate; recovered missing receipts remain explicitly unknown. |
| `download_native_base.py` | GET-only download of an already completed own native render; retains response range/size, hash and FFprobe receipt. Can continue validated GET ranges. Does not repeat paid POSTs. |
| `normalize_voice.py` | Actual two-pass −17 LUFS, −1.5 dBTP target; measures output and proves identical decoded sample count/rate/layout. Changes amplitude, not sample values identically. Requires 44100 Hz mono voice. |
| `master_vps_movie.py` | Audio-only AAC remux using `-c:v copy`. Preserves base, refuses an unproved existing final, compares every encoded video packet/hash/timing and stream properties. |
| `check_vps_film.py` | Full fatal A/V decode, measured levels, seven source/final audio correlation windows, every scene midpoint, every before/after cut and first/last frame. Writes **visual review pending**. Requires H264 1080p24, AAC mono44100 and normally 15–20 minutes. |
| `prepare_captions.py` | Exact canonical English words into a separate SRT using the supplied actual adopted word clock. No new transcript; no phoneme-perfect timing claim. |
| `build_delivery_proof.py` | Binds current API snapshots, source/import pixels, saved authoring, genuine reviews, voice clock, native base and derived film. GET refresh is explicit; missing inputs remain pending. Supports the documented import record layout, not arbitrary server schemas. |
| `build_native_export.py` | Offline binding of a completed provider/import proof and audio-only master; does not manufacture those proofs. |
| `release_history.py` | Binds already existing complete technical and genuine visual reports. Explicit `--root-release` records the operator's release; the program does not look at images or create a visual PASS. |
| `gofile_delivery.py` | Offline gate by default. Upload requires exact manifest SHA; one new folder, seven files, no retry after ambiguous POST. Requires real normal-site readback. |
| `gofile_site_readback.py` | Read-only observation of the unmodified authenticated website: actual listing, exact visible filenames and fresh screenshot. Rejects mutation and foreign Authorization. |

Use `python production/history_delivery/HELPER.py --help` for every explicit
argument. No helper contains an episode's old ephemeral machine root.

## Episode contract

Copy [episode-profile.example.json](episode-profile.example.json) **outside Git**
and update every value from the current episode. Counts, duration and frame count
must come from the actual voice and native render. The project ID is a TubeForge
project ID, not a YouTube UC ID, handle or desktop browser profile.
`reviewer` must exactly match the actual thumbnail review ledger, not its example.

The default private episode layout is:

```text
episode/
  script.txt
  combined-actual-source-review.json
  vps-adoption/
    native-aligned-words.json
    actual-paragraph-timings.json
    exact-authored-scenes-new-vps-clock.json
    selected-generation-provenance-plan.json
    voice-adoption.json
    narration-normalized.flac
    level-only-normalization-proof.json
  thumbnails/
    Thumbnail-A.jpg ... Thumbnail-D.jpg
    export-and-actual-review.json
  delivery/
    Film.mp4
    UPLOAD.txt
    English-Captions.srt
    caption-proof.json
    audio-only-mastering.json
    final-visual-qa.json
    native-export-binding.json
    gofile-final-manifest.json
```

`native_plan_path` and `voice_adoption_path` are optional absolute profile
overrides for those two conventional evidence paths in the uploader. The
specialized export/release builders use the default layout.

`voice-adoption.json` binds the current project, actual duration/frame/sample
counts and original voice SHA. After normalization, save
`comparison_voice_path`, `derived_voice_sha256` and `normalization_proof` from the
measured proof, retaining `official_voice_path` and `original_voice_sha256`.
Regenerating a voice changes the clock: retime every authored scene and chapters,
then generate captions against that actual clock. Never reuse the old timings.

For a preserved existing-media import, `build_delivery_proof.py` additionally
expects an explicitly supplied staging root with:

```text
staging-root/
  private/history-migration-state.json       # episodes[slug].remote_project_id
  private/<slug>-delivery-project.json       # current authenticated GET snapshot
  private/<slug>-delivery-outputs.json
  staging/<slug>-remote-clock/voice.mp3       # complete official voice download
  staging/<slug>-native-import/
    import-manifest.json
    scenes.json
    locations.json
    media-import-state.json
```

Those are **actual saved receipts**, not templates to fill with “verified”.
The importer must preserve original reference order, record source and uploaded
hashes separately and prove decoded RGB equality if the server normalizes PNG
metadata. Location/registry annotations added at import are explicitly later
documentation, not a claim that they were sent during historical generation.
The tool rejects/pends absent current snapshots and cannot infer lost receipts.

## Finishing one completed native film

The variables below point to private working files, not repository paths:

```bash
python production/history_delivery/download_native_base.py \
  --project-id "$HISTORY_PROJECT_ID" --output-dir "$HISTORY_BASE_DIR" \
  --expected-frames "$HISTORY_FRAMES"
python production/history_delivery/normalize_voice.py \
  --source "$HISTORY_OFFICIAL_VOICE" \
  --output "$HISTORY_EPISODE/vps-adoption/narration-normalized.flac" \
  --proof "$HISTORY_EPISODE/vps-adoption/level-only-normalization-proof.json"
# Bind the actual normalization result in voice-adoption.json before remux/QA.
python production/history_delivery/master_vps_movie.py \
  --episode-dir "$HISTORY_EPISODE" --project-id "$HISTORY_PROJECT_ID" \
  --base "$HISTORY_BASE_DIR/native-base.mp4" \
  --download-receipt "$HISTORY_BASE_DIR/native-base-download-receipt.json" \
  --output "$HISTORY_EPISODE/delivery/Film.mp4"
python production/history_delivery/check_vps_film.py \
  --episode "$HISTORY_EPISODE" --scene-count "$HISTORY_SCENES" \
  --movie "$HISTORY_EPISODE/delivery/Film.mp4" --sha256 "$HISTORY_FINAL_SHA" \
  --plan "$HISTORY_EPISODE/vps-adoption/exact-authored-scenes-new-vps-clock.json" \
  --voice-proof "$HISTORY_EPISODE/vps-adoption/voice-adoption.json"
```

The normalized FLAC and final AAC are separate artifacts. The delivered film's
SHA is the audio-mastered derivative's SHA, not the raw VPS MP4's SHA. The visual
render remains the VPS render; normalization and remux do not reencode video.
Do not describe this historical finishing as an entirely unmodified API download.

**Actually inspect every generated QA sheet** and the relevant audio before
recording visual review. Each `capture_sheets` record needs actual path/SHA,
`state:pass`, reviewer and concrete notes. The final visual ledger binds
`movie_sha256`, `finished_render_visual_reviewed:true`,
`reviewed_encoded_scene_count`, `reviewed_cut_count` and `state:pass` only after
that inspection. Source image approvals alone never approve the encoded film.
The automated QA covers the complete decode but its visual sample scope is the
listed midpoints/cut pairs/first/last frames, not every movie frame viewed by a person.

After real review, `release_history.py --stage evidence` creates the bound
technical/audio/quality/release records. Then `build_delivery_proof.py` binds the
native base and derivative using those records; pass all actual files through
`--native-base`, `--movie`, `--download-receipt`, `--mastering-provenance`,
`--audio-analysis`, `--final-qa` and `--root-release`. Run
`build_native_export.py --profile ... --provider-proof ... --download-receipt ...`
and finally `release_history.py --stage manifest --profile ... --movie ...
--movie-sha256 ... --root-release`. Each helper validates its inputs and preserves
different existing releases for inspection.

Four thumbnails must be genuinely reviewed distinct JPEGs at 3840×2160, each
under 2 MB. Historical originals were generated around 1672×941 then exported to
3840×2160; this is a 4K export, not native 4K generated detail. Author `UPLOAD.txt`
and its sources/chapters from the final approved script and actual new clock.

## Seven-file GoFile delivery

This preserved delivery validator supports the explicitly bound audio-mastered
branch; a raw API-only export needs its own complete semantic binding validator
before it is supported here. It does not silently accept an unbound raw export.

The root release binds exactly: `video`, `thumbnail_a`, `thumbnail_b`,
`thumbnail_c`, `thumbnail_d`, `upload_text`, `captions`. The last two names are
`UPLOAD.txt` and `English-Captions.srt`. Validate without uploading:

```bash
python production/history_delivery/gofile_delivery.py \
  --profile "$HISTORY_PROFILE" \
  --manifest "$HISTORY_EPISODE/delivery/gofile-final-manifest.json" \
  --state-dir "$HISTORY_GOFILE_PRIVATE_STATE"
```

GoFile private state requires a legitimately existing authenticated browser
profile in `browser-profile/`, an `owner-private.json` mode0600 with the same
account's `owner_token`, and a real `normal-site-preflight.json` obtained by
`gofile_site_readback.py`. Initialize this privately from an account/profile the
operator controls. The tools do not create guest accounts or invent website
headers/tokens. Preflight observes an existing owned share page and sends no
mutation. The first new file POST creates a **new** folder; no old folder ID is
used for upload.

Add `--upload --manifest-sha256 "$HISTORY_MANIFEST_SHA"` only for an actually
released kit within the user's authorized delivery scope. Readback uses the
website's real listing response and visible DOM; it correctly accepts a share
code URL when the response's actual canonical folder UUID matches the upload
receipt. It does not call or bypass the Premium-only direct listing API.
Upload response MD5/size and final listing MD5/size are checked; no remote SHA256
availability is claimed. Inspect the fresh screenshot before reporting delivery.

On ambiguous POST, preserve `pending-private.json`, inspect actual account
contents and reconcile rather than blindly rerun. Once `receipt.json` confirms
the exact kit, rerunning checks the existing receipt with **zero new POSTs**.
These tools deliver files; YouTube/Fury publication is a separate integration.

## Validation scope

```bash
python -m unittest discover -s production/history_delivery/tests -p 'test_*.py' -v
python production/history_delivery/tests/check_offline_transport.py
```

Tests use synthetic media, mocked transports and no network. They check actual
normalization/sample clock, complete video packet identity after remux, foreign
portal auth rejection, share-code/canonical-ID binding and website mutation guards.
Ten transport fixtures cover successful seven-file sequencing, ambiguous POST,
MD5 mismatch, private/wrong listings, file changes and the exact release SHA gate.
Those fixture results are not production receipts.

The portable proof builder additionally passed 1341 actual saved Viking
source/import/render/derivation checks offline, without refreshing remote snapshots
or changing the original release files.

During this handoff both existing finished real Viking/Pirate kits additionally
passed the portable uploader's complete **offline** SHA/evidence gate. No new
upload, review, voice, image generation or remote render was requested during
packaging. The original final media QA and real GoFile delivery records remain
the evidence of the films already delivered.
