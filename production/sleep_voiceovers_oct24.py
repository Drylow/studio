"""Authorized October 24 voice batch; exact sources and no automatic paid retries."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

import sleep_voiceovers as engine

ROOT = Path(__file__).resolve().parents[1]
engine.SOURCE = ROOT / "chaines/sleep-theories/scripts-2026-10-22"
engine.STATE = ROOT / "work/sleep-voiceovers-2026-10-24"
engine.OUT = Path.home() / "Desktop/Voix sleep - 24 octobre 2026"
IDS = (
    "DV-08-bene-gesserit", "DV-09-jedi-order", "DV-10-fremen",
    "DV-11-old-republic", "DV-12-great-houses", "QP-07-silo-builders",
    "QP-08-from-rules", "QP-09-lumon-building", "QP-10-silo-outside",
    "QP-11-from-cycles",
)


def load():
    ledger = engine.STATE / "ledger.json"
    if ledger.exists():
        data = json.loads(ledger.read_text(encoding="utf-8"))
        assert tuple(r["id"] for r in data["episodes"]) == IDS
        assert data["voice_id"] == engine.VOICE and data["speed"] == 0.90
        assert data["generate_srt"] is False
        return data
    measures = json.loads((engine.SOURCE / "MESURES-LOT.json").read_text(encoding="utf-8"))
    measured = {r["id"]: r for r in measures["episodes"]}
    rows = []
    for index, eid in enumerate(IDS, 1):
        found = list(engine.SOURCE.glob("*/" + eid + "/SCRIPT.txt"))
        assert len(found) == 1, eid
        path = found[0]
        text = path.read_text(encoding="utf-8-sig")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        ref = measured[eid]
        assert digest == ref["sha256"], eid
        assert len(text) == ref["characters_including_spaces"], eid
        assert ref["complete"] and ref["minimum_words_pass"], eid
        rows.append({"id": eid, "channel": path.parent.parent.name,
                     "title": (path.parent / "TITRE.txt").read_text(encoding="utf-8-sig").strip(),
                     "script": path.relative_to(engine.SOURCE).as_posix(),
                     "sha256": digest, "characters": len(text), "words": ref["words"],
                     "audio_file": f"{index:02d}-{eid}.mp3", "state": "ready"})
    assert sum(r["characters"] for r in rows) == 1726549
    return {"created_at": engine.now(), "voice_id": engine.VOICE,
            "voice_name": "Mellow Matt", "provider": "elevenlabs", "speed": 0.90,
            "generate_srt": False, "selection": "Existing standard provider default; expected 1x",
            "episodes": rows}


def summary(data):
    rows = [{"id": r["id"], "channel": r["channel"], "title": r["title"],
             "characters": r["characters"], "state": r["state"],
             "parts": dict(Counter(p["state"] for p in r.get("parts", []))),
             "duration_seconds": r.get("duration_seconds"),
             "audio_path": r.get("audio_path")} for r in data["episodes"]]
    return {"updated_at": engine.now(), "voice": data["voice_name"],
            "voice_id": data["voice_id"], "speed": data["speed"],
            "characters": sum(r["characters"] for r in rows), "episodes": rows,
            "remaining_characters": data.get("credits_latest", {}).get("tts_characters", {}).get("remaining")}


def submit(data, limit):
    # Persist the exact partition before the first chargeable request.
    all_parts = list(engine.parts(data))
    for episode in data["episodes"]:
        parts = episode["parts"]
        assert parts[0]["start"] == 0 and parts[-1]["end"] == episode["characters"]
        assert all(a["end"] == b["start"] for a, b in zip(parts, parts[1:]))
    waiting = [(e, p, t) for e, p, t in all_parts if p["state"] == "ready"][:limit]
    # An ambiguous previous response must be reconciled, never resubmitted.
    assert not any(p["state"] in {"submitting", "submission_unknown"} for _, p, _ in all_parts)
    credits = engine.tts.algrow_credits()
    data.setdefault("credits_before", credits)
    data["credits_latest"] = credits
    engine.save(data)
    required = sum(p["characters"] for _, p, _ in waiting)
    if credits["tts_characters"]["remaining"] < required:
        raise RuntimeError("Insufficient characters for the entire selected batch")
    for episode, part, text in waiting:
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == part["sha256"]
        fields = engine.tts.algrow_fields(text, engine.VOICE, speed=0.90, srt=False)
        fields["custom_title"] = "Sleep 2026-10-24 - " + part["id"]
        part.update(state="submitting", attempted_at=engine.now(), custom_title=fields["custom_title"])
        engine.save(data)
        try:
            result = engine.tts._algrow_call("POST", "/api/generate-simple", fields, timeout=180)
        except Exception as exc:
            part.update(state="submission_unknown", error_type=type(exc).__name__, error_private=str(exc))
            engine.save(data)
            engine.emit("submission_unknown", id=part["id"], error_type=type(exc).__name__)
            return
        part["submission_response"] = result
        if not result.get("job_id"):
            part["state"] = "submission_unknown"
            engine.save(data)
            engine.emit("submission_unknown", id=part["id"])
            return
        part.update(job_id=result["job_id"], state="submitted", submitted_at=engine.now())
        engine.save(data)
        engine.emit("submitted", id=part["id"], characters=len(text), job_id=part["job_id"])
    data["credits_latest"] = engine.tts.algrow_credits()
    engine.save(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["plan", "submit", "monitor", "status"])
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    engine.STATE.mkdir(parents=True, exist_ok=True)
    # Windows process lock prevents two submitters from using a stale ledger.
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
        cfg = dotenv_values(ROOT / ".env")
        if not cfg.get("ALGROW_API_KEY"):
            raise RuntimeError("Configured private account key missing")
        os.environ["ALGROW_API_KEY"] = cfg["ALGROW_API_KEY"]
    if args.action == "plan":
        planned = list(engine.parts(data))
        assert all(200 <= len(t) <= 100000 for _, _, t in planned)
        engine.save(data)
        engine.emit("plan", episodes=len(data["episodes"]), parts=len(planned),
                    characters=sum(len(t) for _, _, t in planned),
                    largest_part=max(len(t) for _, _, t in planned))
    elif args.action == "submit":
        submit(data, args.limit)
    elif args.action == "monitor":
        engine.monitor(data)  # reads/downloads only; cannot create a paid job
    else:
        engine.emit("status", **summary(data))


if __name__ == "__main__":
    main()
