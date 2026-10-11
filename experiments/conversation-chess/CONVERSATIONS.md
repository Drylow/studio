# Independent conversations in one native video

The optional `conversations` timeline array lets a film change opponents without
carrying the previous duel's advantage into the next one. Without this array,
the existing single-conversation behavior is unchanged.

```json
{
  "source_in": 0,
  "source_out": 600,
  "white_label": "LaPadite",
  "black_label": "Landa",
  "opening": {
    "speaker": "white", "label": "LaPadite", "reviewed": true,
    "evidence": "Review the actual first retained dialogue before filling this in."
  },
  "initial_score_text": "0.0",
  "initial_control": 0.5,
  "conversations": [
    {
      "source_at": 0,
      "white_label": "LaPadite", "black_label": "Landa",
      "opening": {
        "speaker": "white", "label": "LaPadite", "reviewed": true,
        "evidence": "Reviewed first retained dialogue for this duel."
      },
      "initial_score_text": "0.0", "initial_control": 0.5
    },
    {
      "source_at": 300,
      "white_label": "Landa", "black_label": "Shosanna",
      "opening": {
        "speaker": "white", "label": "Landa", "reviewed": true,
        "evidence": "Reviewed first retained dialogue for this second duel."
      },
      "initial_score_text": "0.0", "initial_control": 0.5
    }
  ]
}
```

These names/times are schema examples, not evidence about the film. Assign White
to the speaker who actually opens each selected conversation. Starts must be
strictly ordered on the 30 fps grid inside the source interval; the first start,
labels and initial state must match the global fields. An optional
`opening.source_at` must match its conversation start. Do not put an annotation
exactly at a conversation start.

For up to three source seconds after a new opening, the existing bandeau shows
the White/Black names; it ends earlier if the first grade occurs. The score and
bar reset to `0.0` / `0.5`. This is not a new move or an extra hold, and the recap
counts only real annotations. Analysis transitions start from the preceding
grade in the current duel, and replays cannot reach into the previous duel.
Label-only splits preserve continuous dialogue PCM; audio fades remain only at
real dialogue interval ends and new conversation boundaries.

Use `prepare-source-edit.py` before native preparation when applying source
cuts. It remaps chapter starts and opening timestamps into the edited source.
Later opening frames must survive a retained cut; omitted chapters, lost
openings or annotations reassigned to another duel are refused. The first
opening can be replaced by the explicitly reviewed opening in the edit file.

```sh
node experiments/conversation-chess/render-clip.mjs \
  --prepare-project --discard-frame-caches \
  --source /absolute/edited-source.mp4 \
  --timeline /absolute/edited-timeline.json \
  --out /absolute/fresh-prepared-directory
```

Independent conversations require complete native preparation (or
`--validate-only`); legacy flattened rendering and partial intro refreshes
refuse this option.

`--discard-frame-caches` is optional and defaults to false. It applies only to a
fresh native preparation. After each guide/analysis/outro frame sequence, the
renderer immediately encodes the lossless alpha MOV, counts decoded frames and
checks dimensions, fps, duration and codec before deleting the PNGs created by
that run. MOVs, source files and static review images remain. The project
manifest records the discarded cache paths and retained movie hashes under
`graphics_frame_cache_policy`. Graphics durations must align to 30 fps.

Validation:

```sh
node experiments/conversation-chess/conversations.test.mjs
.venv/bin/python -m unittest discover \
  -s experiments/conversation-chess -p 'test_prepare_source_edit.py'
```

The JS suite includes a real FFmpeg PCM comparison across a label-only split.
Native smoke evidence from this implementation is local and regenerable:
`/tmp/chess-conversations-smoke-uq0pe395/prepared/smoke-review.json`. This fixture
prepared a 30.2-second, two-duel project with four verified alpha MOVs and no
remaining intermediate frame caches; it did not export or upload a final film.
