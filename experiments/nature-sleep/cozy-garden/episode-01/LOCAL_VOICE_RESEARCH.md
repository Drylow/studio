# Local narration option — research, not current production

Checked on 11 October 2026. The user's latest decision is to continue this episode with the existing AI33 narration. **This document keeps Kokoro as an option for future tests; it does not replace the current voice, delay the film, or authorize another paid submission.**

This was a read-only review of public source code, package metadata, model cards and licences. No package or model was installed in this research pass, no inference was run, and no audio sample was listened to. Root's separate runtime experiments, if any, need their own results.

## Result

Kokoro can synthesize narration locally without a per-character API bill. The official code and published weights use Apache-2.0; the separate community `kokoro-onnx` wrapper uses MIT. Commercial use is permitted by these licences subject to their terms. A two-hour production is technically a sequence of short inference chunks, not one two-hour model request.

For a future low-risk comparison, use the same short original garden passage with British male `bm_george` or `bm_fable`, British female `bf_emma`, and American female `af_heart`. These are **candidates to hear**, not voices approved as soothing by this review. Do not replace the completed narration until a real listening comparison is satisfactory.

## Licensing checked at the source

| Component | Evidence read | Finding |
|---|---|---|
| Official inference code | [hexgrad/kokoro LICENSE](https://github.com/hexgrad/kokoro/blob/main/LICENSE) and [README](https://github.com/hexgrad/kokoro) | Apache License 2.0. Section 2 grants no-charge, royalty-free rights to reproduce, make derivatives, publicly perform and distribute the work. Section 4 sets redistribution and notice conditions. |
| Official weights and voice repository | [Kokoro-82M model card](https://huggingface.co/hexgrad/Kokoro-82M), its [raw metadata](https://huggingface.co/hexgrad/Kokoro-82M/raw/main/README.md), and [repository API metadata](https://huggingface.co/api/models/hexgrad/Kokoro-82M) | `license: apache-2.0`; the owner explicitly describes Apache-licensed weights and welcomes production/commercial deployments. The repository is public and not gated. |
| Stock English voices | [Official VOICES.md](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) within that weight repository | No separate noncommercial restriction is listed for the recommended English voices. The voice files are part of the Apache-labelled model repository. This does not mean every independently uploaded voice file elsewhere has that licence. |
| Community ONNX Python wrapper | [thewh1teagle/kokoro-onnx LICENSE](https://github.com/thewh1teagle/kokoro-onnx/blob/main/LICENSE) and [README licence section](https://github.com/thewh1teagle/kokoro-onnx#license) | Wrapper code is MIT; its README separately identifies the underlying model as Apache-2.0. MIT requires retaining its copyright/permission notice with copies or substantial software portions. |
| Separate community ONNX weight export | [onnx-community/Kokoro-82M-v1.0-ONNX](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX) | This converted-weight repository also declares Apache-2.0. It is a conversion route, not the author's Python inference package. |

The model repository's `/LICENSE` file returned 404 when checked. The weight licence finding is based on the owner's explicit model-card declaration and repository licence metadata, not an invented separate file. The official code licence file was available and read.

The owner describes the training sources and separately credits some CC BY datasets in the model card. The voice table identifies specific Japanese and French dataset attributions; the English candidates listed here have no additional per-voice licence row. Preserve the selected release's licensing and attribution material when storing or redistributing model assets, and check dependency licences separately if distributing a bundled application. An Apache/MIT wrapper licence is not a blanket licence for every dependency or an unrelated input script.

No requirement to put a permanent on-screen voice credit in each English narration video was found in the reviewed sources. Redistribution obligations for code/weights should not be confused with a mandatory graphic over a video. These licences support commercial use; they do **not** guarantee YouTube monetization, absence of all copyright disputes, rights in unrelated visuals/music, or approval of repetitive channel content. The channel's original writing and finished content still matter.

## Versions: three different numbers

| Item checked | Version / identifier | Practical meaning |
|---|---|---|
| Official Python package, PyPI | `kokoro 0.9.4` | The library version; it is not “model v0.9”. |
| Official pretrained model | `Kokoro-82M v1.0` | Weight release listed by its owner, with 82 million parameters. |
| Community Python ONNX wrapper, PyPI | `kokoro-onnx 0.6.1` | Independent runtime version, not the official package or a new official weight generation. |
| Community download tag in its README | `model-files-v1.1` | That tag still supplies files named `kokoro-v1.0.onnx` and `voices-v1.0.bin`; do not infer a different official model version from the asset-pack tag. |

The published [official PyPI metadata](https://pypi.org/pypi/kokoro/json) for 0.9.4 requires **Python >=3.10,<3.13**. The current [GitHub pyproject](https://github.com/hexgrad/kokoro/blob/main/pyproject.toml) says `<3.14`; those are not identical. Python 3.11 or 3.12 is the conservative common choice for a future installation. The published [community wrapper metadata](https://pypi.org/pypi/kokoro-onnx/json) requires Python >=3.10,<3.14.

The official model card declares checkpoint SHA-256 `496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4`. The repository API returned revision `f3ff3571791e39611d31c381e3a41a3af07b4987`. No weight binary was downloaded or independently hashed in this research pass. A future production should pin the exact chosen assets and record their verified hashes.

## Official PyTorch route versus community ONNX

| Point | Official `hexgrad/kokoro` | Community `thewh1teagle/kokoro-onnx` |
|---|---|---|
| Main runtime | PyTorch, with `misaki[en]`, Transformers, NumPy and Hugging Face Hub listed as dependencies. | ONNX Runtime >=1.20.1, NumPy, `phonemizer` and `espeakng-loader`; the wrapper does not list PyTorch as a required dependency. |
| CPU | Supported in the actual `KPipeline` source with `device='cpu'`; default selection falls back to CPU. | CPU support is advertised by the project. Suitable to test when avoiding the larger PyTorch installation matters. |
| GPU | CUDA supported when available; Apple MPS has an explicit fallback setting described by the author. No GPU is mandatory for using the model. | GPU support is offered through ONNX execution providers; optional `onnxruntime-gpu` dependency targets supported x86-64 Windows/Linux systems. Hardware, provider and export compatibility still need a real test. |
| Pronunciation front end | Official English pipeline uses Misaki. The README installs `espeak-ng` for unknown-word fallback. Source warns that out-of-dictionary words can be skipped when that fallback is absent. | Default phonemization and asset packaging differ. The README recommends the Misaki route for v1.0 examples. Matching only the voice name does not establish identical output to the official pipeline. |
| Model files | Official checkpoint plus matching voice tensors, fetched/cached from the owner's repository. | Matching ONNX model and voice bank. README estimates roughly 300 MB, or roughly 80 MB for a quantized model; this is its advertised model footprint, not total process RAM. |
| Long text | Official English pipeline divides phoneme sequences; its generator yields individual pieces. | Current source divides phonemes into batches and offers a streaming method. Calling an API that returns one concatenated array can still accumulate the whole output in memory. |
| Timing data | Current official pipeline contains token-duration/timestamp support. It still needs verification against the generated audio for subtitle use. | Current source can report timings only when the selected graph exposes duration output. Its continuous-window mode also requires such an export. Do not assume a generic older `.onnx` download has that output. |
| Quality/performance | Reference implementation is the easier baseline for comparing behaviour. | Quantization, phonemizer and graph conversion may change output. A smaller model or a claimed speed advantage is not proof of equal voice quality. |

The community README claims near-real-time performance on a Mac M1. That is not a benchmark of this VPS/cloud machine and does not establish an ETA for two hours here. No CPU-versus-GPU benchmark or RAM measurement was performed in this research.

Sources for these implementation details: [official pipeline](https://github.com/hexgrad/kokoro/blob/main/kokoro/pipeline.py), [official model](https://github.com/hexgrad/kokoro/blob/main/kokoro/model.py), [community implementation](https://github.com/thewh1teagle/kokoro-onnx/blob/main/src/kokoro_onnx/__init__.py), and [community package metadata](https://pypi.org/pypi/kokoro-onnx/json). The source trees can evolve ahead of an installed release, so production must verify the pinned package rather than assume every `main` feature is present.

## Voice shortlist to test, without pretending to have heard it

The official voice table grades its training/reference coverage, not suitability for sleep. Its own text says preferences are subjective. Recommendations below use those published grades to prioritize tests; “soothing” remains a listening decision.

| Candidate | Locale | Official overall grade | Why include it in a short trial |
|---|---|---|---|
| `bm_george` | British male, `lang_code='b'` | C | Candidate for the requested calm British male storytelling direction; compare against Fable rather than assuming one is softer. |
| `bm_fable` | British male, `lang_code='b'` | C | Alternative British male candidate with the same published overall grade. |
| `bf_emma` | British female, `lang_code='b'` | B- | Strongest published overall grade among the British female entries; the table lists tens of hours of training audio. |
| `af_heart` | American female, `lang_code='a'` | A | First American candidate: author's example/default and highest listed overall grade. |
| `af_bella` | American female, `lang_code='a'` | A- | Alternative with substantial training coverage. |
| `af_nicole` | American female, `lang_code='a'` | B- | Additional candidate if the first trials are too bright; softness/breathiness must be heard, not inferred from the name or emoji. |

Use the matching British/American language setting, rather than placing a British voice over an American phonemizer unintentionally. In the ONNX interface, check the corresponding `en-gb` or `en-us` parameter; those codes are not interchangeable with the official `a`/`b` API convention. Stock voices do not require cloning Stephen Dalton or any other narrator.

## How two hours would be produced

The raw model context is 512 tokens, with two positions reserved, leaving up to roughly **510 input phoneme tokens**. These are not 510 English words. The [official voice notes](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) say many voices behave best around 100–200 tokens, can be weak on very short utterances, and can rush above about 400 tokens.

A future renderer should:

1. Keep the reviewed story text, then split at complete sentence boundaries into small groups whose **actual phoneme length** is checked. Do not directly reuse the AI33 six-paragraph request blocks as raw model inputs.
2. Load one model and the chosen voice once, synthesize chunks progressively, and save each completed waveform with text, voice, version and audio hashes. Resume only exact completed chunks.
3. Verify that all source text was covered. The official pipeline contains truncation fallback paths for oversize phoneme strings; merely getting an audio file does not prove no ending was dropped.
4. Keep one voice and stable settings throughout. Test a modest speed change on a short excerpt first; stretching too far or making chunks too long can hurt diction and rhythm.
5. Retain natural sentence endings and insert intentional quiet gaps between paragraphs. Do not blindly trim all quiet audio at a join or crossfade over spoken consonants.
6. Compare an independent transcription with the script and listen to names, joins, sibilants and the beginning/end of each type of chunk before extending the trial.
7. Measure the actual speech duration before setting a two-hour timeline. The current story has 14,541 words; voice choice, speed and pauses determine the final length.

The native output demonstrated by both routes is **24 kHz**. Upsampling later for the video's mixer does not turn it into genuinely higher-bandwidth source audio. Two hours of mono 16-bit PCM at 24 kHz is about **345.6 MB** before file headers; a float32 buffer alone is about **691.2 MB**. Writing and joining chunks avoids retaining an entire two-hour waveform plus model memory at once.

There is no paid per-character quota when running the downloaded model locally. Compute time, disk space, electricity and any rented server still exist. “Free local voice” means no hosted TTS charge, not that all production resources have zero cost.

## What remains unverified

- No local voice was selected or approved by listening in this research.
- No installation, benchmark, full-length inference, memory measurement or generated-file QA was performed here.
- No claim is made that a local voice matches or surpasses the already completed narration.
- This alternative stays separate from the current AI33 production. Test a small excerpt later, then decide whether its sound and operational cost justify a future switch.

Source snapshots for this research were saved as plain text in `/tmp/garden-kokoro-research/`, with HTTP statuses and SHA-256 receipts. The principal model card, code licence and voice table all returned HTTP 200. Source links above remain the durable references; temporary snapshots are not a deployment dependency.
