# OVNI On Windows

Installed and exercised on 9 October 2026. This is an isolated GPU renderer
evaluation, not a completed episode or a silent switch of the studio renderer.
The user explicitly requested OVNI after sharing Marc's post.

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

## Remaining Scope

OVNI is installed and the technical test works. Production integration still
needs the final motion, transitions, audio mix, colour metadata, exact frame
clock and full montage QA. No complete historical episode is claimed ready.
The old renderer remains unchanged as a comparison and recovery path.
