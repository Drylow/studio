# Episode 02 production checkpoint — 13 October 2026

Complete this same video; do not start a new script or regenerate its voice.
The user authorized the full video, corrections and delivery, with no extra
upscale. Do not publish to YouTube or send third-party messages.

- TubeForge project: `your-life-as-a-pokemon-trainer-df03b3`, owner Kanye.
- Voice COMPLETE: **950 seconds / 15:50**, 3,076 narrated words. Actual final
  audio was acoustically transcribed before the full scene images were made.
- 157 first-pass images COMPLETE; all current sources actually inspected.
- First correction batch: **64 new outputs**, 13 refused/interrupted requests.
- **117 current selections accepted**, **40 explicitly rejected selections**
  still need corrections. They are listed in `verification.json` and the
  public `generation-provenance.json`, not silently treated as approved.
- **26 distinct locations + one explicit night variant**, 39 cast identities.
- All three connected image accounts returned quota/rate-limit restrictions.
  Respect the saved delay: earliest retry **14 October 2026, 02:00 Paris**.
- NO final render, NO finished CapCut pack, NO publication. Do not claim otherwise.

Exact next-round prompts are already saved in TubeForge and in
`output/imagegen/oddly-fictional-pokemon-production/production-storyboard.json`.
They rebuild rejected frames using the existing approved location and identity
images, with the short compact character silhouette. They exclude the rejected
frame as an input; targeted edits were preserving bad proportions too strongly.
No automatic prompt writer or alternate provider/model is authorized here.

On this same PC, private resumable helpers, credentials and provider receipts
are under ignored `work/pokemon-episode-02/`. Keep that directory private.

1. Read `resume-not-before-private.json`. Do not reset its guard to evade the
   provider delay. Another account requires an actual user connection.
2. Inspect outstanding provider history for the timed-out requests. Preserve
   known completed results and unknown outcomes; do not blindly replay a marker.
   The provider documents that a `created` job cannot progress after its submitting
   connection closes, and marks it failed after 30 minutes:
   [job documentation](https://useapi.net/docs/api-google-flow-v1/get-google-flow-jobs-jobid).
3. Once the quota delay ends, run the **already-authored** 40 corrections with
   the TubeForge Python and a distinct phase marker:
   `work/TubeForge/.venv/Scripts/python.exe -u work/pokemon-episode-02/local_flow_execution.py corrections repairs2`.
   This is three simultaneous calls using the same frozen configuration,
   reference hashes and selected provider. No upscale or paid request replay.
4. Inspect every changed output using `inspect_scenes.py` with the repository
   Python, compare identities/locations/actions and record actual source hashes.
   Any rejected output still needs a concrete correction. Do not mark user approval.
5. When all 157 selections pass, run `install_visual_reviews.py`, then
   `production_api.py render`. TubeForge's render gate correctly refuses the
   current rejected frames; do not bypass it or fabricate reviews.
6. Run `export_episode.py download`, then `inspect`. View all generated rendered
   midpoint contact sheets and final frame. Record the actual montage inspection
   and only then run `export` for 157 ordered silent CapCut clips, voice, SRT,
   timeline CSV, full movie and ZIP. The rendered clock is 22,800 frames at 24 fps.
7. Run `finalize_metadata.py` only after a verified complete delivery exists.
   It deliberately refuses an unfinished production. Scoped Git push is handled
   by `publish_full_scoped.py`; preserve unrelated dirty files.

The transport fix now keeps generation POSTs open for several minutes during
captcha retries. It still sends ONE paid POST, and only recovers exact unique
completed history matches. Combined transport/generation checks: **74 passed**.
Provider job IDs, account data and literal configured model values remain private.

VPS deployment verified after this checkpoint: portal and authenticated project
return successfully, all 157 image selections remain, and downloaded final voice
and rebuilt shot 46 match their local byte hashes. The installed transport contains
the longer generation timeout. For a future host update, use the `update.sh`
inside the release directory recorded by `/opt/tubeforge/active-release.txt`.
The older bootstrap repository has unrelated local changes and was preserved;
do not reset it or overwrite its files. The release updater handles an empty
image batch and refuses active or queued jobs before restarting the application.
