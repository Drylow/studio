# OVNI On Windows

Installed, exercised and integrated on 9 October 2026 at the user's request.
OVNI is the default picture renderer for the five Codex-authored historical
channels only. This integration does not complete the unfinished episodes or
change the frontend, automatic prompting or other studio workflows.

## Sources

- Upstream: https://github.com/billythegoat356/OVNI
- Pinned source commit: `6d82e678667d438162fe52f76de4666991d4c424`
- Windows packages: conda-forge and NVIDIA's PyNvVideoCodec package on PyPI.
- Micromamba installation: https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html

## Installation

Run from the repository with Windows PowerShell:

```powershell
./production/ovni.ps1 -Action Install
```

Runtime: `$HOME/.codex/runtimes/ovni-20261009`. Source and technical tests are
under `work/ovni-evaluation-2026-10-09` and `work/ovni-runtime-2026-10-09`.
No studio Python, NVIDIA driver, system PATH, frontend, scheduled task or
publication setting is changed. Initial downloads are approximately 2 GB.

Validated installation: Python 3.11, CUDA 12.9, CuPy 13.6.0, PyCUDA 2025.1.1,
PyNvVideoCodec 2.0.1, NumPy 2.2.6, Pillow 11.2.1 and OpenCV 4.11.0.86.
`pip check` passes. The device is a GeForce RTX 4060 Laptop GPU, 8 GB.

Upstream kernels are compiled with NVIDIA NVRTC for compute capability 8.9,
avoiding a system Visual Studio installation. The only supplied virtual header
defines the upstream kernel's `uint32_t` as `unsigned int`. Upstream source is
not rewritten. PTX and source hashes are recorded alongside the compiled module.
The pinned CuPy internal compiler API is deliberately limited to the build step.

## Reproduce The Test

Requires the already prepared and manually approved Edo review-excerpt timeline,
normalized images, format-review ledger and excerpt narration. It checks image
hashes and approval, timeline coverage and the six-second cadence. The test
does not generate content, choose new references or approve creative material.
Each output directory must be fresh.

```powershell
./production/ovni.ps1 -Action Benchmark -Seconds 30 -Output work/ovni-runtime-2026-10-09/my-gpu-test
./production/ovni.ps1 -Action Baseline -Seconds 30 -Output work/ovni-runtime-2026-10-09/my-studio-test
./venv/Scripts/python.exe -m unittest production.test_ovni_smoke
```

Each OVNI invocation is a separate process, following the upstream warning about
codec memory leaks in long-running processes. Image processing and encoding run
on the GPU. FFmpeg still muxes the encoded H.264 with AAC audio and performs the
decode check; it is not eliminated by OVNI.

## Measured Result

First run: 30 seconds, 900 frames, eight approved Edo images, 1920x1080 at 30 fps,
centred 2.5 percent zoom, hard cuts, no fade transitions:

- GPU image loading: 0.611 seconds.
- OVNI processing and encoding: 2.419 seconds, 372 frames/second.
- Audio encoding and MP4 muxing: 2.840 seconds.
- Total measured OVNI work: 5.870 seconds, excluding Python startup and QA.
- Existing studio renderer, fresh clip cache: 10.970 seconds, plus 0.193 seconds
  for preparing its audio input.

This is roughly 1.9x on this short workload, NOT a universal 10x claim. Inputs,
resolution, cadence and zoom strength match, but interpolation/easing differ.
OVNI uses 8 Mbps/P3, while the studio uses CRF 18. Equal bitrate or preset names
would not prove equal visual quality. A longer equal-quality comparison remains.

Second OVNI run through `ovni.ps1`: 4.106 seconds total (0.515 loading, 2.327
processing/encoding, 1.264 muxing), about 2.7x versus that same studio baseline.
Its eight capture files are byte-identical to the individually viewed first-run
captures. The range on these two short runs is therefore roughly 2-3x, with the
same quality caveats. All 43 focused production/runtime tests pass.

The failed first installation's temporary cache remains under the test directory;
the working environment uses the shorter runtime path listed above.

The output has exactly 900 frames and decodes without errors. Eight start-of-shot
captures were individually viewed by Codex: framing and colours are readable,
with no visible rendering corruption. The pre-existing headband-knot continuity
caution is unchanged. RGB mean absolute errors near shot starts are 3.64-4.63.
These numerical checks do not substitute for creative review or a listening pass.

## Historical Production Integration

`production/historical_renderer.py` routes Edo Daily, Aztec Daily, Babylon Daily,
Imperial China Daily and Ottoman Daily to `services/render_ovni.py`. The five
narration manifests carry their channel and `render_backend: ovni`; their
narration-only phase still prevents premature full-episode rendering. Final
authored episode manifests must retain those fields. Other channels stay on
the existing renderer. An explicit `render_backend: studio` is available for
comparison, never an automatic fallback after a GPU failure.

The wrapper preserves the voice-derived integer frame clock, centre/corner
zooms, four pans, cuts and short fades. Fades consume frames at the start of the
next shot, not narration time. The existing final audio pass still handles
voice normalization, music ducking, effects and the audio tail; it copies the
GPU-encoded picture rather than encoding it again. H.264 VUI declares the
upstream converter's limited-range BT.709 colour matrix explicitly.

Each render starts one GPU child process, retaining at most two scene images.
Cancellation kills and waits for that child. Cache keys include actual image
hashes, camera/frame settings, wrapper/worker sources and compiled kernel hash.
Picture reuse requires the completed worker receipt, frame count and file hash.
Progress-file replacement retries brief Windows locks; a locked progress file
cannot abort the encode. A missing runtime/kernel or worker failure is visible.
`OVNI_PYTHON` can override the isolated runtime executable.

Nonopaque images require normalization and review before this path. Existing
full-sized RGB frames are passed through unchanged. Board layouts, graphic
overlays, effects layers and burned-in captions are explicitly rejected rather
than silently discarded. The backend never writes prompts, swaps references,
approves an image or declares a movie publication-ready.

## Full Excerpt Comparison

Same 36 manually reviewed Edo shots, 180.62 seconds of actual narration plus
0.4-second tail, 1920x1080 at 30 fps, 2.5 percent zoom, 0.15-second fades and
identical voice normalization. Neither picture cache was reused:

- Existing studio renderer: 69.138 seconds.
- Integrated OVNI renderer: 32.263 seconds, including worker startup, image
  checks, GPU encoding, muxing and final audio mix; GPU worker 21.215 seconds.
- About 2.14x faster on this measured workload. Voice extraction and final QA
  are outside both render timers. Inputs were already reviewed RGB frames.
- Studio uses CRF 18; OVNI uses NVENC P5 at 12 Mbps. Camera interpolation and
  encoders differ, so this is not an identical-quality or universal speed claim.

The original reviewed excerpt is preserved. The separate GPU excerpt is:
`output/historical-01-2026-10-08/edo-daily/Edo-Daily-01-EXTRAIT-3min-OVNI.mp4`.
Its manifest is `chaines/edo-daily/01-production-2026-10-08/review-excerpt-ovni.json`.
Full-episode assets and creative checks remain unfinished.

```powershell
$env:PYTHONPATH = (Get-Location).Path
./venv/Scripts/python.exe production/review_excerpt.py chaines/edo-daily/01-production-2026-10-08/review-excerpt-ovni.json --stage prepare
# Keep the existing manual format review only when every frame hash matches.
./venv/Scripts/python.exe production/review_excerpt.py chaines/edo-daily/01-production-2026-10-08/review-excerpt-ovni.json --stage render
./venv/Scripts/python.exe production/review_excerpt.py chaines/edo-daily/01-production-2026-10-08/review-excerpt-ovni.json --stage qa
$env:OVNI_GPU_TESTS = '1'
./venv/Scripts/python.exe -m unittest discover -s production -p 'test_*.py'
```

The opt-in actual GPU test verifies a 90-frame fixture, red-to-blue blend at
start/middle/end, colour metadata and decoded pixels, audio presence, completed
cache reuse and cancellation. This technical fixture is not content for upload.

Final GPU excerpt QA: full decode without errors, 5,431 video frames, constant
30 fps, 1920x1080, BT.709 limited range, picture 181.033333 seconds and audio
181.020000 seconds. Codex viewed all 108 scene captures on six contact sheets;
no renderer-added black areas or visible corruption. The original headband-knot
continuity caution remains; no perfect creative continuity or listening review
is claimed. Review ledger: `work/historical-01-2026-10-08/edo-daily/review-excerpt-ovni/montage-review.json`.
Export SHA256: `192be7aab782624de7e860aaedfcd8349fec4a150f3124487cffdf2ecd7854ef`.
All 56 focused tests pass, including the actual GPU/mux/cache/cancellation test.
