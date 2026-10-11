# Final encoded preview QA — V3

Technical checks passed for `Depths-After-Dark-Camera-Forward-24s.mp4`:24.000s,1920×1080,H264/AAC,30fps,720 decoded video frames. File SHA-256 `38fc4e4e2f62514d00d91cf143eb10b6d25682e7230a7a8fff56535f44e7fa84`;34,172,536bytes. Final current bundle SHA matches both the expected freeze and the scene-check report: `d3460e0da70312fcfb26134c92ca09c696750ea02a62e11ffba77731c0c8ce5f`.

One complete FFmpeg A/V decode produced the720frame MD5 profile,24 general images,48 native close images and float32 stereo PCM together. It exited0 with no error. Actual video timestamps are exactly0–719 in a1/30s timebase; all frame durations are one tick. All720 decoded frame MD5 values differ. The original encoded file was unchanged and its SHA matches the original render sidecar.

## Actual decoded-image review

All nine contact sheets were inspected: general integer-second frames0–23 and close frames6–13.833333 at6Hz. General captures are960×540; all48 close captures are native1920×1080. Additional native decoded images were inspected at6,6.5,7.3333,8,9.8333 and12.5 seconds.

No sampled blank frame or conspicuous opaque rectangular texture background was identified. No unexplained position teleport, near-camera animal dissolving in the middle of the frame, or instant mirrored fish turn was identified in these samples. The shark crosses the upper viewport edge around6–7s. The jelly crosses the left edge around7–7.5s. The nearest school moves toward and across the right edge. Partial body clipping at the actual viewport edges during those exits is expected; this differs from the previous fade/disappearance within the frame.

This is sampled image inspection, not a claim of watching the complete clip continuously or reviewing every native video frame.

## PCM audio

Stéréo48kHz,exactly24.000s,all samples finite,zero full-scale samples. Peak left/right0.06619/0.06134;RMS approximately−36.27dBFS. Largest adjacent step0.002826/0.001807 occurs at AAC startup. PCM inspection reused the single decode output; no second FFmpeg or MP4 decode was performed. It does not constitute human listening or a guarantee about audible clicks, tonal quality, perceived loudness or a300s audio loop.

## Remaining artistic limits

Recognizable reef cutouts and reused shapes remain, with some thin foreground silhouettes and comparatively regular side placement. These may still look like layers of a painting. The yaw effect is projected2.5D rather than articulated3D anatomy. The far background remains stationary while nearer layers advance. The preview now addresses the identified abrupt mirror/fade defects; it still needs the user's judgement on the visual style, naturalness and sense of immersion. Technical PASS does not approve the artwork or a future full-length export.

Evidence: `preview-qa.json`, `qa/video-profile.json`, `qa/decoded-frames.md5`, `qa/audio-qa.json`, and the three `qa/general-sheet-*.jpg` plus six `qa/close-sheet-*.jpg`. Only private QA outputs were written. Sources, bundle, original MP4 and original render metadata were not edited. No rerender or generation call was made.
