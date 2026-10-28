"""Run the authorized French recap narration batch with a resumable ledger.

Submission is separate from monitoring. A monitor cannot create paid jobs.
"""
import argparse
from collections import Counter
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

import sleep_voiceovers as engine

ROOT = Path(__file__).resolve().parents[1]
engine.SOURCE = ROOT / "chaines/la-boite-a-recap/scripts-2026-10-27"
engine.STATE = ROOT / "work/recap-voiceovers-2026-10-27"
engine.OUT = Path.home() / "Desktop/Voix La Boîte à Récap - 27 octobre 2026"
engine.VOICE = "IHngRooVccHyPqB4uQkG"
IDS = ("01-galactus", "02-freezer", "03-sukuna")
SPEED = 1.0
BASE_VERIFY = engine.verify


def transcript_metrics(expected, actual):
    matcher = difflib.SequenceMatcher(None, expected, actual, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    coverage = matched / max(1, len(expected))
    precision = matched / max(1, len(actual))
    gaps = [(b - a, d - c) for tag, a, b, c, d in matcher.get_opcodes() if tag != "equal"]
    source_gap = max((a for a, _ in gaps), default=0)
    extra_gap = max((b for _, b in gaps), default=0)
    tail = expected[-60:]
    tail_matched = sum(block.size for block in difflib.SequenceMatcher(None, tail, actual[-120:], autojunk=False).get_matching_blocks())
    tail_coverage = tail_matched / max(1, len(tail))
    passed = (bool(expected) and bool(actual) and coverage >= .98 and precision >= .98
              and tail_coverage >= .90 and source_gap < 24 and extra_gap < 24)
    return {"transcript_source_coverage": round(coverage, 5),
            "transcript_output_precision": round(precision, 5),
            "transcript_tail_coverage": round(tail_coverage, 5),
            "transcript_largest_source_gap_tokens": source_gap,
            "transcript_largest_extra_gap_tokens": extra_gap,
            "transcript_text_passed": passed}


def verify_with_transcript(row, minimum=0):
    BASE_VERIFY(row, minimum)
    if row["state"] != "verified":
        return
    if "parts" in row:
        row["transcript_integrity_passed"] = all(
            part.get("transcript_integrity_passed") for part in row["parts"])
        if not row["transcript_integrity_passed"]:
            row["state"] = "transcript_review_required"
        return
    if not row.get("transcript_path"):
        row.update(state="transcript_review_required", transcript_integrity_passed=False)
        return
    episode_id = row["id"].split("-part", 1)[0]
    source = (engine.SOURCE / episode_id / "SCRIPT.txt").read_text(encoding="utf-8")
    text = source[row["start"]:row["end"]]
    words = engine.tts._srt_words(Path(row["transcript_path"]).read_text(encoding="utf-8-sig"))
    tokens = lambda value: re.findall(r"[^\W_]+", value.casefold())
    expected = tokens(text)
    actual = tokens(" ".join(word["w"] for word in words))
    metrics = transcript_metrics(expected, actual)
    end_delta = abs(row["duration_seconds"] - (words[-1]["e"] if words else 0))
    passed = metrics["transcript_text_passed"] and end_delta <= 30
    row.update(**metrics, transcript_end_delta_seconds=round(end_delta, 3),
               transcript_integrity_passed=passed)
    if not passed:
        row["state"] = "transcript_review_required"
    engine.emit("transcript_checked", id=row["id"], passed=passed,
                source_coverage=metrics["transcript_source_coverage"],
                tail_coverage=metrics["transcript_tail_coverage"])


def load():
    ledger = engine.STATE / "ledger.json"
    if ledger.exists():
        data = json.loads(ledger.read_text(encoding="utf-8"))
        assert tuple(row["id"] for row in data["episodes"]) == IDS
        assert data["voice_id"] == engine.VOICE
        assert data["speed"] == SPEED and data["generate_srt"] is True
        return data
    verification = json.loads((engine.SOURCE / "VERIFICATION.json").read_text(encoding="utf-8"))
    measured = {row["id"]: row for row in verification["scripts"]}
    rows = []
    for eid in IDS:
        path = engine.SOURCE / eid / "SCRIPT.txt"
        text = path.read_text(encoding="utf-8-sig")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        ref = measured[eid]
        assert digest == ref["sha256"]
        assert len(text) == ref["characters_with_spaces"]
        assert ref["metadata_and_chapter_boundaries_verified"]
        rows.append({"id": eid, "channel": "la-boite-a-recap",
                     "title": (path.parent / "TITRE.txt").read_text(encoding="utf-8-sig").strip(),
                     "script": eid + "/SCRIPT.txt", "sha256": digest,
                     "characters": len(text), "words": ref["words"],
                     "audio_file": eid + "/voiceover.mp3", "state": "ready"})
    assert sum(row["characters"] for row in rows) == 467273
    return {"created_at": engine.now(), "voice_id": engine.VOICE,
            "voice_name": "Voix française fournie par l'utilisateur",
            "provider": "elevenlabs", "speed": SPEED, "generate_srt": True,
            "selection": "Existing standard multilingual provider default; expected 1x",
            "episodes": rows}


def prepare(data):
    planned = list(engine.parts(data))
    for episode in data["episodes"]:
        pieces = episode["parts"]
        assert pieces[0]["start"] == 0 and pieces[-1]["end"] == episode["characters"]
        assert all(a["end"] == b["start"] for a, b in zip(pieces, pieces[1:]))
        target = engine.OUT / episode["id"]
        target.mkdir(parents=True, exist_ok=True)
        for name in ("SCRIPT.txt", "TITRE.txt"):
            source = engine.SOURCE / episode["id"] / name
            dest = target / name
            if dest.exists() and dest.read_bytes() != source.read_bytes():
                raise RuntimeError("Delivery text differs; preserve and reconcile: " + str(dest))
            if not dest.exists():
                shutil.copy2(source, dest)
    assert len(planned) == 6 and all(200 <= len(text) <= 100000 for _, _, text in planned)
    engine.save(data)
    return planned


def summary(data):
    return {"voice_id": data["voice_id"], "speed": data["speed"],
            "characters": sum(row["characters"] for row in data["episodes"]),
            "episodes": [{"id": row["id"], "state": row["state"],
                          "parts": dict(Counter(p["state"] for p in row.get("parts", []))),
                          "duration_seconds": row.get("duration_seconds"),
                          "audio_path": row.get("audio_path")}
                         for row in data["episodes"]]}


def submit(data, limit):
    planned = prepare(data)
    assert not any(part["state"] in {"submitting", "submission_unknown"}
                   for _, part, _ in planned), "Reconcile ambiguous submission before retrying"
    waiting = [(episode, part, text) for episode, part, text in planned if part["state"] == "ready"][:limit]
    credits = engine.tts.algrow_credits()
    data.setdefault("credits_before", credits)
    data["credits_latest"] = credits
    engine.save(data)
    required = sum(part["characters"] for _, part, _ in waiting)
    if credits["tts_characters"]["remaining"] < required:
        raise RuntimeError("Insufficient standard narration balance for the selected batch")
    for episode, part, text in waiting:
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == part["sha256"]
        fields = engine.tts.algrow_fields(text, engine.VOICE, speed=SPEED, srt=True)
        fields["custom_title"] = "La Boite a Recap 2026-10-27 - " + part["id"]
        part.update(state="submitting", attempted_at=engine.now(), custom_title=fields["custom_title"])
        engine.save(data)
        try:
            result = engine.tts._algrow_call("POST", "/api/generate-simple", fields, timeout=180)
        except Exception as exc:
            part.update(state="submission_unknown", error_type=type(exc).__name__, error_private=str(exc))
            engine.save(data)
            engine.emit("submission_unknown", id=part["id"], error_type=type(exc).__name__)
            return False
        part["submission_response"] = result
        if not result.get("job_id"):
            part["state"] = "submission_unknown"
            engine.save(data)
            engine.emit("submission_unknown", id=part["id"])
            return False
        part.update(job_id=result["job_id"], state="submitted", submitted_at=engine.now())
        engine.save(data)
        engine.emit("submitted", id=part["id"], characters=len(text))
    data["credits_latest"] = engine.tts.algrow_credits()
    engine.save(data)
    engine.emit("submitted_batch", parts=len(waiting), characters=required)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["plan", "submit", "monitor", "status"])
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    engine.STATE.mkdir(parents=True, exist_ok=True)
    if args.action != "status":
        import msvcrt
        lock = (engine.STATE / "executor.lock").open("a+b")
        if lock.seek(0, 2) == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    data = load()
    if args.action in {"submit", "monitor"}:
        from dotenv import dotenv_values
        config = dotenv_values(ROOT / ".env")
        if not config.get("ALGROW_API_KEY"):
            raise RuntimeError("Configured private account key missing")
        os.environ["ALGROW_API_KEY"] = config["ALGROW_API_KEY"]
    if args.action == "plan":
        planned = prepare(data)
        engine.emit("plan", episodes=3, parts=len(planned),
                    characters=sum(len(text) for _, _, text in planned),
                    largest_part=max(len(text) for _, _, text in planned))
    elif args.action == "submit":
        if not submit(data, args.limit):
            raise SystemExit(2)
    elif args.action == "monitor":
        prepare(data)
        engine.verify = verify_with_transcript
        engine.monitor(data)
    else:
        engine.emit("status", **summary(data))


if __name__ == "__main__":
    main()
