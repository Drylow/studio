"""Authorized second French recap batch, with isolated state and no paid retries.

The monitor only retrieves existing jobs. Final MP3 files are published after
decoding, duration, transcript alignment and concatenation checks.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time

from recap_voiceovers_oct27 import transcript_metrics
import sleep_voiceovers as engine

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "chaines/la-boite-a-recap/lot-02-2026-10-27"
# Assign after importing the previous runner, which configures the shared engine.
engine.STATE = ROOT / "work/recap-voiceovers-2026-10-28"
engine.SOURCE = engine.STATE / "sources"
engine.OUT = Path.home() / "Desktop/La Boîte à Récap - Lot 2 - 27 octobre 2026"
FOLDERS = {
    "04-quatre-fantastiques": "04 - Les 4 Fantastiques",
    "05-one-piece": "05 - One Piece",
    "06-frieren": "06 - Frieren",
    "07-sakamoto-days": "07 - Sakamoto Days",
    "08-stranger-things": "08 - Stranger Things",
}
MINIMUM_SECONDS = 7200
POLL_SECONDS = 25
ACTIVE = {"submitted", "queued", "processing", "generating", "completed",
          "poll_error", "downloaded", "awaiting_transcript"}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load():
    ledger = engine.STATE / "ledger.json"
    if ledger.exists():
        data = json_read(ledger)
        assert tuple(row["id"] for row in data["episodes"]) == tuple(FOLDERS)
        assert data["source_root"] == str(engine.SOURCE)
        assert data["output_root"] == str(engine.OUT)
        assert data["speed"] == 1.0 and data["generate_srt"] is True
        assert data["provider"] == "elevenlabs"
        engine.VOICE = data["voice_id"]
        return data
    config = json_read(ROOT / "chaines/la-boite-a-recap/VOIX.json")
    assert config["service"] == "Algrow" and config["provider"] == "elevenlabs"
    assert config["language"] == "fr" and config["speed"] == 1.0
    assert config["generate_srt"] is True
    engine.VOICE = config["voice_id"]
    references = {v["dossier"]: v for v in json_read(PUBLIC / "CONTROLE-LOT.json")["videos"]}
    rows = []
    for eid, folder in FOLDERS.items():
        ref = references[eid]
        source = PUBLIC / eid / "SCRIPT.txt"
        text = source.read_text(encoding="utf-8")
        assert ref["statut"] == "controle_technique_ok" and not ref["erreurs"]
        assert ref["mots"] >= 24500 and digest(source) == ref["sha256"]
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == ref["sha256"]
        assert len(text) == ref["caracteres"]
        frozen = engine.SOURCE / eid
        frozen.mkdir(parents=True, exist_ok=True)
        for name in ("SCRIPT.txt", "TITRE.txt", "DESCRIPTION.txt"):
            src, dst = PUBLIC / eid / name, frozen / name
            if dst.exists() and dst.read_bytes() != src.read_bytes():
                raise RuntimeError("Frozen source conflict: " + eid + "/" + name)
            if not dst.exists():
                shutil.copy2(src, dst)
        rows.append({"id": eid, "channel": "la-boite-a-recap", "state": "ready",
                     "title": (frozen / "TITRE.txt").read_text(encoding="utf-8-sig").strip(),
                     "script": eid + "/SCRIPT.txt", "sha256": ref["sha256"],
                     "characters": len(text), "words": ref["mots"],
                     "delivery_folder": folder, "audio_file": folder + "/voiceover.mp3"})
    assert sum(row["characters"] for row in rows) == 779416
    data = {"created_at": engine.now(), "voice_id": engine.VOICE,
            "voice_name": "Voix française fournie par l'utilisateur",
            "provider": "elevenlabs", "speed": 1.0, "generate_srt": True,
            "source_root": str(engine.SOURCE), "output_root": str(engine.OUT),
            "source_manifest_sha256": digest(PUBLIC / "CONTROLE-LOT.json"),
            "selection": "Same standard multilingual settings as the preceding French batch",
            "episodes": rows}
    engine.save(data)
    return data


def prepare(data):
    planned = list(engine.parts(data))
    assert len(planned) == 10
    for episode in data["episodes"]:
        pieces = episode["parts"]
        assert pieces[0]["start"] == 0 and pieces[-1]["end"] == episode["characters"]
        assert all(a["end"] == b["start"] for a, b in zip(pieces, pieces[1:]))
        source = engine.SOURCE / episode["id"]
        target = engine.OUT / episode["delivery_folder"]
        target.mkdir(parents=True, exist_ok=True)
        script_target = target / "SCRIPT.txt"
        if script_target.exists() and digest(script_target) != episode["sha256"]:
            raise RuntimeError("Delivery script differs: " + episode["id"])
        if not script_target.exists():
            shutil.copy2(source / "SCRIPT.txt", script_target)
        combined = "TITRE\n" + (source / "TITRE.txt").read_text(encoding="utf-8-sig").strip()
        combined += "\n\nDESCRIPTION\n" + (source / "DESCRIPTION.txt").read_text(encoding="utf-8-sig").strip() + "\n"
        publication = target / "TITRE-ET-DESCRIPTION.txt"
        if publication.exists() and publication.read_text(encoding="utf-8-sig") != combined:
            raise RuntimeError("Delivery publication text differs: " + episode["id"])
        if not publication.exists():
            publication.write_text(combined, encoding="utf-8", newline="\n")
        final = engine.OUT / episode["audio_file"]
        if final.exists() and episode.get("audio_sha256") != digest(final):
            raise RuntimeError("Unregistered or changed final audio: " + episode["id"])
        if episode["state"] == "verified" and not final.exists():
            raise RuntimeError("Verified delivery audio missing: " + episode["id"])
    for _, part, text in planned:
        assert 200 <= len(text) <= 100000 and len(text) == part["characters"]
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == part["sha256"]
    engine.save(data)
    return planned


def status_files(data):
    labels = {"ready": "Préparée", "verified": "Terminée et contrôlée",
              "duration_below_minimum": "Durée inférieure à deux heures : à vérifier",
              "audio_check_failed": "Contrôle audio en échec : à vérifier",
              "assembly_check_failed": "Assemblage à vérifier",
              "delivery_conflict": "Fichier existant différent : à vérifier"}
    for episode in data["episodes"]:
        counts = Counter(part["state"] for part in episode.get("parts", []))
        failed = any(part["state"] in {"failed", "transcript_missing", "transcript_review_required",
                                      "audio_check_failed", "submission_unknown", "submitting"}
                     for part in episode.get("parts", []))
        label = labels.get(episode["state"], episode["state"])
        if episode["state"] == "ready" and any(s != "ready" for s in counts):
            label = "Action requise avant livraison" if failed else "Génération et récupération en cours"
        text = episode["title"] + "\n\n" + label + ".\n"
        text += "Voix française de La Boîte à Récap, vitesse 1,00.\n"
        text += f"Blocs contrôlés : {counts.get('verified', 0)}/2.\n"
        if episode["state"] == "verified":
            text += f"Durée mesurée : {episode['duration_seconds']:.3f} secondes.\nFichier : voiceover.mp3\n"
            text += "Décodage complet, texte de transcription et assemblage contrôlés ; pas d'écoute humaine intégrale.\n"
        else:
            text += "Le MP3 complet apparaîtra dans ce dossier après les contrôles.\n"
        (engine.OUT / episode["delivery_folder"] / "STATUT-VOICEOVER.txt").write_text(
            text, encoding="utf-8", newline="\n")


def summary(data):
    return {"voice_id": data["voice_id"], "speed": data["speed"],
            "characters": sum(e["characters"] for e in data["episodes"]),
            "remaining_characters": data.get("credits_latest", {}).get("tts_characters", {}).get("remaining"),
            "episodes": [{"id": e["id"], "state": e["state"],
                          "parts": dict(Counter(p["state"] for p in e.get("parts", []))),
                          "duration_seconds": e.get("duration_seconds"),
                          "audio_path": e.get("audio_path")} for e in data["episodes"]]}


def submit(data, limit):
    planned = prepare(data)
    if any(p["state"] in {"submitting", "submission_unknown"} for _, p, _ in planned):
        raise RuntimeError("Reconcile an ambiguous submission before any new paid request")
    waiting = [(e, p, t) for e, p, t in planned if p["state"] == "ready"][:limit]
    credits = engine.tts.algrow_credits()
    data.setdefault("credits_before", credits)
    data["credits_latest"] = credits
    required = sum(math.ceil(p["characters"] * 1.20) for _, p, _ in waiting)
    data["estimated_characters_with_transcript"] = required
    engine.save(data)
    if credits["tts_characters"]["remaining"] < required:
        raise RuntimeError("Insufficient balance including the transcript allowance")
    for _, part, text in waiting:
        fields = engine.tts.algrow_fields(text, engine.VOICE, speed=data["speed"], srt=True)
        fields["custom_title"] = "La Boite a Recap lot2 2026-10-28 - " + part["id"]
        part.update(state="submitting", attempted_at=engine.now(), custom_title=fields["custom_title"])
        part["settings"] = {k: v for k, v in fields.items() if k != "script"}
        engine.save(data)
        try:
            result = engine.tts._algrow_call("POST", "/api/generate-simple", fields, timeout=180)
        except Exception as exc:
            part.update(state="submission_unknown", error_type=type(exc).__name__, error_private=str(exc))
            engine.save(data)
            engine.emit("submission_unknown", id=part["id"], error_type=type(exc).__name__)
            status_files(data)
            return False
        part["submission_response"] = result
        if not result.get("job_id"):
            part["state"] = "submission_unknown"
            engine.save(data)
            status_files(data)
            engine.emit("submission_unknown", id=part["id"])
            return False
        part.update(job_id=result["job_id"], state="submitted", submitted_at=engine.now())
        engine.save(data)
        engine.emit("submitted", id=part["id"], characters=len(text))
    data["credits_latest"] = engine.tts.algrow_credits()
    engine.save(data)
    status_files(data)
    engine.emit("submitted_batch", parts=len(waiting), characters=sum(len(t) for _, _, t in waiting),
                remaining=data["credits_latest"]["tts_characters"]["remaining"])
    return True


def verify_part(part, text):
    engine.verify(part)
    if part["state"] != "verified":
        return
    import re
    words = engine.tts._srt_words(Path(part["transcript_path"]).read_text(encoding="utf-8-sig"))
    tokens = lambda value: re.findall(r"[^\W_]+", value.casefold())
    metrics = transcript_metrics(tokens(text), tokens(" ".join(w["w"] for w in words)))
    delta = abs(part["duration_seconds"] - (words[-1]["e"] if words else 0))
    passed = metrics["transcript_text_passed"] and delta <= 30
    part.update(**metrics, transcript_end_delta_seconds=round(delta, 3), transcript_integrity_passed=passed)
    if not passed:
        part["state"] = "transcript_review_required"
    engine.emit("transcript_checked", id=part["id"], passed=passed,
                source_coverage=metrics["transcript_source_coverage"],
                tail_coverage=metrics["transcript_tail_coverage"])


def assemble(episode):
    private = engine.STATE / "assembled"
    private.mkdir(exist_ok=True)
    target = private / (episode["id"] + ".mp3")
    if episode["state"] == "delivery_pending":
        if not target.exists() or digest(target) != episode["audio_sha256"]:
            raise RuntimeError("Pending delivery source changed: " + episode["id"])
        deliver(episode, target)
        return
    for part in episode["parts"]:
        source = Path(part["audio_path"])
        if (not source.exists() or source.stat().st_size != part["audio_bytes"]
                or digest(source) != part["audio_sha256"]):
            raise RuntimeError("Verified audio part changed: " + part["id"])
    listing = engine.STATE / (episode["id"] + "-concat.txt")
    listing.write_text("".join("file '" + Path(p["audio_path"]).as_posix().replace("'", "'\\''") + "'\n"
                               for p in episode["parts"]), encoding="utf-8", newline="\n")
    temporary = target.with_suffix(".partial.mp3")
    engine.media.run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c:a", "copy", str(temporary)], timeout=300)
    temporary.replace(target)
    episode.update(audio_path=str(target), audio_bytes=target.stat().st_size, audio_sha256=digest(target))
    engine.verify(episode, minimum=MINIMUM_SECONDS)
    if episode["state"] != "verified":
        return
    delta = episode["duration_seconds"] - sum(p["duration_seconds"] for p in episode["parts"])
    episode.update(duration_join_delta_seconds=round(delta, 3),
                   transcript_integrity_passed=all(p.get("transcript_integrity_passed") for p in episode["parts"]),
                   assembly="Exact contiguous source halves, MP3 packet concatenation; no padding")
    if abs(delta) > 1 or not episode["transcript_integrity_passed"]:
        episode["state"] = "assembly_check_failed"
        return
    deliver(episode, target)


def deliver(episode, target):
    final = engine.OUT / episode["audio_file"]
    if final.exists() and digest(final) != episode["audio_sha256"]:
        episode["state"] = "delivery_conflict"
        return
    # Record the expected final digest before placement for crash-safe recovery.
    episode["state"] = "delivery_pending"
    engine.save(_active_data)
    if not final.exists():
        temp_final = final.with_suffix(".partial.mp3")
        shutil.copy2(target, temp_final)
        assert digest(temp_final) == episode["audio_sha256"]
        temp_final.replace(final)
    episode.update(audio_path=str(final), state="verified", delivered_at=engine.now())
    engine.emit("delivered", id=episode["id"], seconds=episode["duration_seconds"])


def monitor(data):
    global _active_data
    _active_data = data
    while True:
        for episode, part, text in engine.parts(data):
            if part["state"] in ACTIVE - {"downloaded"}:
                try:
                    status = engine.tts._algrow_call("GET", "/api/job-status/" + part["job_id"], timeout=60)
                    part["last_response"] = status
                    current = status.get("status")
                    if current != part.get("remote_status"):
                        engine.emit("status", id=part["id"], status=current)
                    part.update(remote_status=current, last_poll=engine.now())
                    if current == "failed":
                        part.update(state="failed", failure_private=status.get("error_message") or status.get("error"))
                    elif current == "completed" and status.get("audio_url") and status.get("transcript_url"):
                        engine.download(part, status)
                    elif current == "completed" and status.get("audio_url"):
                        part.setdefault("audio_completed_at", engine.now())
                        elapsed = (datetime.fromisoformat(engine.now()) - datetime.fromisoformat(part["audio_completed_at"])).total_seconds()
                        part["state"] = "awaiting_transcript" if elapsed < 3600 else "transcript_missing"
                    else:
                        part["state"] = "submitted"
                    engine.save(data)
                except Exception as exc:
                    part.update(state="poll_error", last_error_type=type(exc).__name__, last_error_private=str(exc))
                    engine.save(data)
                    engine.emit("read_error", id=part["id"], error_type=type(exc).__name__)
            if part["state"] == "downloaded":
                verify_part(part, text)
                engine.save(data)
        for episode in data["episodes"]:
            if episode["state"] in {"ready", "delivery_pending"} and all(p["state"] == "verified" for p in episode["parts"]):
                assemble(episode)
                engine.save(data)
        status_files(data)
        if not any(part["state"] in ACTIVE for _, part, _ in engine.parts(data)):
            break
        time.sleep(POLL_SECONDS)
    try:
        data["credits_latest"] = engine.tts.algrow_credits()
    except Exception as exc:
        data["credits_refresh_error"] = type(exc).__name__
    engine.save(data)
    engine.emit("finished", states={e["id"]: e["state"] for e in data["episodes"]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["plan", "submit", "monitor", "status"])
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.limit < 1:
        raise ValueError("Positive submission limit required")
    engine.STATE.mkdir(parents=True, exist_ok=True)
    if args.action != "status":
        import msvcrt
        lock = (engine.STATE / "executor.lock").open("a+b")
        if lock.seek(0, 2) == 0:
            lock.write(b"0"); lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    if args.action == "status" and not (engine.STATE / "ledger.json").exists():
        engine.emit("status", state="not_prepared")
        return
    data = load()
    if args.action in {"submit", "monitor"}:
        from dotenv import dotenv_values
        config = dotenv_values(ROOT / ".env")
        if not config.get("ALGROW_API_KEY"):
            raise RuntimeError("Configured private key missing")
        os.environ["ALGROW_API_KEY"] = config["ALGROW_API_KEY"]
    if args.action == "plan":
        planned = prepare(data)
        status_files(data)
        engine.emit("plan", episodes=5, parts=len(planned),
                    characters=sum(len(text) for _, _, text in planned),
                    largest_part=max(len(text) for _, _, text in planned), voice_id=engine.VOICE, speed=data["speed"])
    elif args.action == "submit":
        if not submit(data, args.limit):
            raise SystemExit(2)
    elif args.action == "monitor":
        prepare(data)
        monitor(data)
    else:
        engine.emit("status", **summary(data))


if __name__ == "__main__":
    main()
