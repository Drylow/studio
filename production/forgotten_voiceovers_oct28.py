"""Finite authorized narration queue with isolated state and no paid retries.

Only ``run`` submits requests. ``monitor`` retrieves existing jobs and performs
local checks. Source text and media remain private; every publication is atomic.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import sleep_voiceovers as engine

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "chaines/sleep-theories/scripts-2026-10-22/Forgotten Realms of Sleep"
engine.STATE = ROOT / "work/forgotten-voiceovers-2026-10-28"
engine.SOURCE = engine.STATE / "sources"
engine.OUT = Path.home() / "Desktop/VIDEOS - TOUT REGROUPE/Forgotten Realms of Sleep"
VOICE = "IsEXLHzSvLH9UMB6SLHj"
engine.VOICE = VOICE
SPEED = 0.90
IDS = ("FR-04-daedric-princes", "FR-05-brotherhood", "FR-06-elden-ring")
CHARACTERS = 524530
MAX_ACTIVE = 2
MINIMUM_SECONDS = 7200
FRENCH_LEDGER = ROOT / "work/recap-voiceovers-2026-10-28-recovery/ledger.json"
REMOTE_ACTIVE = {"submitted", "queued", "processing", "generating", "completed", "poll_error"}
ACTIVE = REMOTE_ACTIVE | {"downloaded"}
STOP = {"failed", "submitting", "submission_unknown", "audio_review_required", "audio_check_failed",
        "duration_below_minimum", "assembly_check_failed", "delivery_conflict"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def text_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def partition(eid, text):
    boundaries = [m.end() for m in re.finditer(r"\n\s*\n", text)]
    if not boundaries:
        raise RuntimeError("No paragraph boundaries: " + eid)
    cuts = [0] + [min(boundaries, key=lambda x: abs(x - len(text) * n / 8)) for n in range(1, 8)] + [len(text)]
    if cuts != sorted(set(cuts)):
        raise RuntimeError("Invalid partition: " + eid)
    result = []
    for n, (a, b) in enumerate(zip(cuts, cuts[1:]), 1):
        piece = text[a:b]
        if not 15000 <= len(piece) <= 30000:
            raise RuntimeError("Unexpected source slice length: " + eid)
        name = eid + "-part" + str(n)
        result.append({"id": name, "state": "ready", "start": a, "end": b,
                       "characters": len(piece), "words": len(piece.split()),
                       "sha256": text_digest(piece), "audio_file": name + ".mp3"})
    return result


def validate_settings(data):
    if (tuple(e["id"] for e in data["episodes"]) != IDS
            or data["voice_id"] != VOICE or data["speed"] != SPEED
            or data["generate_srt"] is not False or data["provider"] != "elevenlabs"
            or data["source_root"] != str(engine.SOURCE) or data["output_root"] != str(engine.OUT)):
        raise RuntimeError("Narration selection or settings changed")


def load():
    path = engine.STATE / "ledger.json"
    if path.exists():
        data = read_json(path)
        validate_settings(data)
        return data
    rows = []
    for eid in IDS:
        folder = PUBLIC / eid
        measures = read_json(folder / "MESURES.json")
        text = (folder / "SCRIPT.txt").read_text(encoding="utf-8-sig")
        if (not measures["complete"] or not measures["minimum_words_pass"]
                or measures.get("missing") or text_digest(text) != measures["sha256"]
                or len(text) != measures["characters_including_spaces"]):
            raise RuntimeError("Validated source differs: " + eid)
        frozen = engine.SOURCE / eid
        frozen.mkdir(parents=True, exist_ok=True)
        for name in ("SCRIPT.txt", "TITRE.txt", "MESURES.json"):
            src, dst = folder / name, frozen / name
            if dst.exists() and dst.read_bytes() != src.read_bytes():
                raise RuntimeError("Frozen source conflict: " + eid + "/" + name)
            if not dst.exists():
                shutil.copy2(src, dst)
        rows.append({"id": eid, "channel": "Forgotten Realms of Sleep", "state": "ready",
                     "title": (frozen / "TITRE.txt").read_text(encoding="utf-8-sig").strip(),
                     "script": eid + "/SCRIPT.txt", "sha256": text_digest(text),
                     "characters": len(text), "words": measures["words"],
                     "delivery_folder": eid, "audio_file": eid + "/VOICEOVER.mp3",
                     "parts": partition(eid, text)})
    if sum(e["characters"] for e in rows) != CHARACTERS:
        raise RuntimeError("Authorized character total differs")
    data = {"created_at": engine.now(), "voice_id": VOICE, "voice_name": "Mellow Matt",
            "provider": "elevenlabs", "speed": SPEED, "generate_srt": False,
            "source_root": str(engine.SOURCE), "output_root": str(engine.OUT),
            "selection": "Three explicitly authorized episodes only; standard provider settings",
            "episodes": rows}
    engine.save(data)
    return data


def parts(data):
    for episode in data["episodes"]:
        text = (engine.SOURCE / episode["script"]).read_text(encoding="utf-8-sig")
        if text_digest(text) != episode["sha256"] or len(text) != episode["characters"]:
            raise RuntimeError("Frozen source changed: " + episode["id"])
        for part in episode["parts"]:
            piece = text[part["start"]:part["end"]]
            if len(piece) != part["characters"] or text_digest(piece) != part["sha256"]:
                raise RuntimeError("Frozen slice changed: " + part["id"])
            yield episode, part, piece


def prepare(data):
    validate_settings(data)
    planned = list(parts(data))
    if len(planned) != 24 or sum(len(text) for _, _, text in planned) != CHARACTERS:
        raise RuntimeError("Incomplete authorized partition")
    for episode in data["episodes"]:
        slices = episode["parts"]
        if (len(slices) != 8 or slices[0]["start"] != 0 or slices[-1]["end"] != episode["characters"]
                or any(a["end"] != b["start"] for a, b in zip(slices, slices[1:]))):
            raise RuntimeError("Source gap or overlap: " + episode["id"])
        expected = partition(episode["id"], (engine.SOURCE / episode["script"]).read_text("utf-8-sig"))
        for actual, original in zip(slices, expected):
            if any(actual[k] != original[k] for k in ("id", "start", "end", "characters", "sha256", "audio_file")):
                raise RuntimeError("Partition changed: " + actual["id"])
        folder = engine.OUT / episode["delivery_folder"]
        folder.mkdir(parents=True, exist_ok=True)
        source = engine.SOURCE / episode["script"]
        target = folder / "SCRIPT.txt"
        if target.exists() and text_digest(target.read_text("utf-8-sig")) != episode["sha256"]:
            raise RuntimeError("Delivery script differs: " + episode["id"])
        if not target.exists():
            shutil.copy2(source, target)
        if not (folder / "TITRE.txt").exists():
            shutil.copy2(source.parent / "TITRE.txt", folder / "TITRE.txt")
        final = engine.OUT / episode["audio_file"]
        if final.exists() and digest(final) != episode.get("audio_sha256"):
            raise RuntimeError("Unregistered or changed final audio: " + episode["id"])
        if episode["state"] == "verified" and not final.exists():
            raise RuntimeError("Verified final audio missing: " + episode["id"])
    engine.save(data)
    return planned


def status_files(data):
    for episode in data["episodes"]:
        counts = Counter(p["state"] for p in episode["parts"])
        failed = episode["state"] in STOP or any(p["state"] in STOP for p in episode["parts"])
        if episode["state"] == "verified":
            label = "Terminée et contrôlée"
        elif failed:
            label = "Contrôle ou intervention requis avant livraison"
        elif data.get("budget_blocked"):
            label = "En attente de crédits, réserve des voix françaises protégée"
        elif all(p["state"] == "ready" for p in episode["parts"]):
            label = "Préparée, en attente dans la file autorisée"
        else:
            label = "Génération, récupération et contrôles en cours"
        text = episode["title"] + "\n\n" + label + ".\n"
        text += "Mellow Matt, vitesse 0,90, sans sous-titres payants.\n"
        text += f"Blocs contrôlés : {counts.get('verified', 0)}/8.\n"
        if episode["state"] == "verified":
            text += f"Fichier : VOICEOVER.mp3\nDurée mesurée : {episode['duration_seconds']:.3f} secondes.\n"
            text += "Décodage complet, empreinte, assemblage et extraits de début/fin contrôlés.\n"
            text += "Contrôles ciblés : aucune écoute humaine ni transcription intégrale revendiquée.\n"
        else:
            text += "Le MP3 complet apparaîtra ici après assemblage et contrôles.\n"
        folder = engine.OUT / episode["delivery_folder"]
        (folder / "STATUT-VOICEOVER.txt").write_text(text, encoding="utf-8", newline="\n")
        state_file = folder / "ETAT-DES-FICHIERS.txt"
        inventory = episode["title"] + "\n\nETAT DES FICHIERS - 28 OCTOBRE 2026\n"
        for name, label_name in (("SCRIPT.txt", "Script"), ("TITRE.txt", "Titre"), ("MINIATURE.jpg", "Miniature")):
            inventory += label_name + " : " + ("présent" if (folder / name).is_file() else "absent") + " (" + name + ").\n"
        inventory += "Narration : " + label + ".\n"
        inventory += "Détails actualisés : STATUT-VOICEOVER.txt.\nFichier final après validation : VOICEOVER.mp3.\n"
        state_file.write_text(inventory, encoding="utf-8", newline="\n")


def summary(data):
    return {"voice_id": VOICE, "speed": SPEED, "characters": CHARACTERS,
            "budget_blocked": data.get("budget_blocked", False),
            "episodes": [{"id": e["id"], "state": e["state"],
                          "parts": dict(Counter(p["state"] for p in e["parts"])),
                          "duration_seconds": e.get("duration_seconds")} for e in data["episodes"]]}


def french_reserve(path=None):
    """Fail closed if the independently running French queue cannot be read."""
    data = read_json(path or FRENCH_LEDGER)
    if data.get("generate_srt") is not True:
        raise RuntimeError("Unexpected French reserve settings")
    return sum(math.ceil(p["characters"] * 1.2) for e in data["episodes"] for p in e["parts"]
               if p["state"] in {"ready", "submitting", "submission_unknown"})


def budget_snapshot(data):
    # Reserve before reading balance. If the French process submits meanwhile,
    # this over-reserves safely instead of pairing an old balance with new state.
    reserve_before = french_reserve()
    credits = engine.tts.algrow_credits()
    reserve_after = french_reserve()
    reserve = max(reserve_before, reserve_after)
    available = credits["tts_characters"]["remaining"]
    remaining = sum(p["characters"] for _, p, _ in parts(data) if p["state"] == "ready")
    data.setdefault("credits_before", credits)
    data.update(credits_latest=credits, french_reserve=reserve,
                remaining_authorized_characters=remaining, budget_checked_at=engine.now())
    data["budget_blocked"] = available < reserve + remaining
    engine.save(data)
    return not data["budget_blocked"]


def blocked(data):
    return any(e["state"] in STOP or any(p["state"] in STOP for p in e["parts"])
               for e in data["episodes"])


def submissions_paused():
    # Presence alone is authoritative, including an incomplete or malformed file.
    return (engine.STATE / "pause-submissions.json").exists()


def submit_pair(data):
    if submissions_paused():
        engine.emit("submissions_paused")
        return False
    planned = list(parts(data))
    if blocked(data):
        raise RuntimeError("Reconcile blocked jobs before any new paid request")
    active = sum(p["state"] in ACTIVE for _, p, _ in planned)
    if active:
        raise RuntimeError("Finish the accepted pair before submitting the next pair")
    if not budget_snapshot(data):
        status_files(data)
        engine.emit("budget_blocked", reserve=data["french_reserve"], remaining=data["remaining_authorized_characters"])
        return False
    waiting = [(e, p, text) for e, p, text in planned if p["state"] == "ready"][:MAX_ACTIVE]
    for _, part, text in waiting:
        if submissions_paused():
            engine.emit("submissions_paused")
            return False
        fields = engine.tts.algrow_fields(text, VOICE, speed=SPEED, srt=False)
        fields["custom_title"] = "Forgotten Realms 2026-10-28 - " + part["id"]
        part.update(state="submitting", attempted_at=engine.now(), custom_title=fields["custom_title"])
        part["settings"] = {k: v for k, v in fields.items() if k != "script"}
        engine.save(data)
        # Recheck after persistence, immediately before the chargeable request.
        # No POST happened for this part, so restoring ready is unambiguous.
        if submissions_paused():
            part.update(state="ready", paused_before_request_at=engine.now())
            engine.save(data)
            engine.emit("submissions_paused")
            return False
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
        engine.emit("submitted", id=part["id"], characters=part["characters"])
    status_files(data)
    return True


def quality_check(part, text):
    """Run the configured offline callback; missing evidence never passes."""
    config = read_json(engine.STATE / "qa-config.json")
    callback = Path(config["callback"])
    cache = Path(config["cache_dir"])
    if not callback.is_file() or not cache.is_dir():
        raise RuntimeError("Local boundary QA configuration unavailable")
    private = engine.STATE / "qa"
    private.mkdir(exist_ok=True)
    request, report = private / (part["id"] + "-request.json"), private / (part["id"] + "-report.json")
    payload = {"id": part["id"], "audio_path": part["audio_path"], "audio_sha256": part["audio_sha256"],
               "source_text": text, "source_sha256": part["sha256"], "cache_dir": str(cache),
               "duration_seconds": part["duration_seconds"]}
    request.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    result = subprocess.run([config.get("python_executable", sys.executable), str(callback),
                             "--input", str(request), "--output", str(report)],
                            capture_output=True, timeout=1200,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError("Local boundary QA callback failed")
    qa = read_json(report)
    passed = (qa.get("passed") is True and qa.get("scope") == "sampled_boundaries"
              and qa.get("audio_sha256") == part["audio_sha256"]
              and qa.get("source_sha256") == part["sha256"]
              and digest(part["audio_path"]) == part["audio_sha256"])
    part.update(boundary_qa_passed=passed, boundary_qa_report=str(report),
                boundary_qa_scope="sampled_boundaries", boundary_qa_at=engine.now())
    return passed


def verify_part(part, text):
    engine.verify(part)
    if part["state"] != "verified":
        return
    try:
        passed = quality_check(part, text)
    except Exception as exc:
        part.update(qa_error_type=type(exc).__name__, qa_error_private=str(exc))
        passed = False
    part["state"] = "verified" if passed else "audio_review_required"
    engine.emit("boundary_qa", id=part["id"], passed=passed)


def deliver(data, episode, source):
    final = engine.OUT / episode["audio_file"]
    if final.exists() and digest(final) != episode["audio_sha256"]:
        episode["state"] = "delivery_conflict"
        return
    episode["state"] = "delivery_pending"
    engine.save(data)
    if not final.exists():
        temporary = final.with_suffix(".partial.mp3")
        shutil.copy2(source, temporary)
        if digest(temporary) != episode["audio_sha256"]:
            raise RuntimeError("Final copy digest differs")
        temporary.replace(final)
    episode.update(state="verified", audio_path=str(final), delivered_at=engine.now())
    engine.save(data)
    engine.emit("delivered", id=episode["id"], seconds=episode["duration_seconds"])


def assemble(data, episode):
    folder = engine.STATE / "assembled"
    folder.mkdir(exist_ok=True)
    target = folder / (episode["id"] + ".mp3")
    if episode["state"] == "delivery_pending":
        if not target.exists() or digest(target) != episode["audio_sha256"]:
            raise RuntimeError("Pending delivery source changed")
        deliver(data, episode, target)
        return
    for part in episode["parts"]:
        if (part["state"] != "verified" or not part.get("boundary_qa_passed")
                or digest(part["audio_path"]) != part["audio_sha256"]
                or Path(part["audio_path"]).stat().st_size != part["audio_bytes"]):
            raise RuntimeError("Audio part changed or lacks QA: " + part["id"])
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
    episode.update(duration_join_delta_seconds=round(delta, 3), boundary_qa_passed=True,
                   assembly="Exact contiguous source slices, MP3 packet concatenation, no added silence or repeats")
    if abs(delta) > 1:
        episode["state"] = "assembly_check_failed"
        return
    deliver(data, episode, target)


def monitor(data):
    """Retrieve accepted jobs only; this function contains no submission path."""
    while True:
        for _, part, text in parts(data):
            if part["state"] in REMOTE_ACTIVE:
                try:
                    status = engine.tts._algrow_call("GET", "/api/job-status/" + part["job_id"], timeout=60)
                    part["last_response"] = status
                    current = status.get("status")
                    if current != part.get("remote_status"):
                        engine.emit("status", id=part["id"], status=current)
                    part.update(remote_status=current, last_poll=engine.now())
                    if current == "failed":
                        part.update(state="failed", failure_private=status.get("error_message") or status.get("error"))
                    elif current == "completed" and status.get("audio_url"):
                        engine.download(part, status)
                    else:
                        part["state"] = "submitted"
                    engine.save(data)
                except Exception as exc:
                    part.update(state="poll_error", error_type=type(exc).__name__, error_private=str(exc))
                    engine.save(data)
                    engine.emit("read_error", id=part["id"], error_type=type(exc).__name__)
            if part["state"] == "downloaded":
                verify_part(part, text)
                engine.save(data)
        for episode in data["episodes"]:
            if episode["state"] in {"ready", "delivery_pending"} and all(p["state"] == "verified" for p in episode["parts"]):
                assemble(data, episode)
                engine.save(data)
        status_files(data)
        if not any(p["state"] in ACTIVE for _, p, _ in parts(data)):
            return
        time.sleep(25)


def run(data):
    if submissions_paused():
        engine.emit("submissions_paused")
        return False
    prepare(data)
    while True:
        active = [p for _, p, _ in parts(data) if p["state"] in ACTIVE]
        if len(active) > MAX_ACTIVE:
            raise RuntimeError("Too many active jobs; reconcile first")
        # Preserve accepted jobs even if the second request had an ambiguous response.
        if active or any(e["state"] == "delivery_pending" for e in data["episodes"]):
            monitor(data)
        if blocked(data):
            status_files(data)
            engine.emit("action_required", **summary(data))
            return False
        if all(p["state"] == "verified" for _, p, _ in parts(data)):
            monitor(data)
            return all(e["state"] == "verified" for e in data["episodes"])
        if not submit_pair(data):
            monitor(data)
            return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["plan", "status", "run", "monitor"])
    args = parser.parse_args()
    if args.action == "status" and not (engine.STATE / "ledger.json").exists():
        engine.emit("status", state="not_prepared")
        return
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
    if args.action in {"run", "monitor"}:
        from dotenv import dotenv_values
        key = dotenv_values(ROOT / ".env").get("ALGROW_API_KEY")
        if not key:
            raise RuntimeError("Configured private key missing")
        os.environ["ALGROW_API_KEY"] = key
    if args.action == "status":
        engine.emit("status", **summary(data))
    elif args.action == "plan":
        planned = prepare(data)
        status_files(data)
        engine.emit("plan", episodes=3, parts=len(planned), characters=CHARACTERS,
                    largest_part=max(len(t) for _, _, t in planned), speed=SPEED, maximum_active=MAX_ACTIVE)
    elif args.action == "monitor":
        prepare(data)
        monitor(data)
    elif not run(data):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
