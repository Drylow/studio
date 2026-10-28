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
PUBLIC = ROOT / "chaines/sleep-theories/scripts-2026-10-22"
PLANS = ROOT / "work/sleep-shortened-2026-10-28"
OLD_FR = ROOT / "work/forgotten-voiceovers-2026-10-28/ledger.json"
engine.STATE = ROOT / "work/sleep-short-voiceovers-2026-10-28"
engine.SOURCE = engine.STATE / "sources"
engine.OUT = Path.home() / "Desktop/VIDEOS - TOUT REGROUPE"
VOICE = "IsEXLHzSvLH9UMB6SLHj"
engine.VOICE = VOICE
SPEED = 0.90
IDS = ("DV-08-bene-gesserit", "DV-09-jedi-order", "DV-10-fremen", "DV-11-old-republic", "DV-12-great-houses", "QP-07-silo-builders", "QP-08-from-rules", "QP-09-lumon-building", "QP-10-silo-outside", "QP-11-from-cycles", "FR-04-daedric-princes", "FR-05-brotherhood", "FR-06-elden-ring")
MAXIMUM_SECONDS = 9000
MAX_AUTHORIZED_CHARACTERS = 1350000
MAX_ACTIVE = 2
MINIMUM_SECONDS = 7200
FRENCH_LEDGER = ROOT / "work/recap-voiceovers-2026-10-28-recovery/ledger.json"
REMOTE_ACTIVE = {"submitted", "queued", "processing", "generating", "completed", "poll_error"}
ACTIVE = REMOTE_ACTIVE | {"downloaded"}
STOP = {"failed", "submitting", "submission_unknown", "audio_review_required", "audio_check_failed",
        "duration_below_minimum", "duration_above_maximum", "assembly_check_failed", "delivery_conflict"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def text_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def partition(eid, text):
    prefix = [0, 20584, 41534] if eid == "FR-04-daedric-princes" else [0]
    start = prefix[-1]
    count = math.ceil((len(text) - start) / 22000)
    boundaries = [m.end() for m in re.finditer(r"\n\s*\n", text) if m.end() > start]
    cuts = prefix + [min(boundaries, key=lambda x: abs(x - (start + (len(text) - start) * n / count)))
                     for n in range(1, count)] + [len(text)]
    if cuts != sorted(set(cuts)):
        raise RuntimeError("Invalid shortened partition: " + eid)
    return [{"id": eid + "-short-part" + str(n), "state": "ready", "start": a, "end": b,
             "characters": b-a, "words": len(text[a:b].split()), "sha256": text_digest(text[a:b]),
             "audio_file": eid + "-short-part" + str(n) + ".mp3"}
            for n, (a, b) in enumerate(zip(cuts, cuts[1:]), 1)]


def validate_settings(data):
    if (tuple(e["id"] for e in data["episodes"]) != IDS or data["voice_id"] != VOICE
            or data["speed"] != SPEED or data["generate_srt"] is not False
            or data["provider"] != "elevenlabs" or data["source_root"] != str(engine.SOURCE)
            or data["output_root"] != str(engine.OUT) or data["maximum_seconds"] != MAXIMUM_SECONDS):
        raise RuntimeError("Short batch selection or settings changed")


def load():
    path = engine.STATE / "ledger.json"
    if path.exists():
        data = read_json(path)
        validate_settings(data)
        return data
    rows = []
    old_fr = read_json(OLD_FR)
    for eid in IDS:
        channel = "Deep Void Theories" if eid.startswith("DV") else "Quiet Paradox" if eid.startswith("QP") else "Forgotten Realms of Sleep"
        plan = read_json(PLANS / "plans" / (eid + ".json"))
        original = (PUBLIC / channel / eid / "SCRIPT.txt").read_text("utf-8-sig")
        text = (PLANS / "scripts" / eid / "SCRIPT-COURT.txt").read_text("utf-8-sig")
        ranges = plan["kept_ranges"]
        if plan.get("review_status") != "reviewed":
            raise RuntimeError("Short script editorial review unfinished: " + eid)
        original_hash = plan.get("source_text_sha256") or plan.get("source_sha256")
        output_hash = plan.get("script_sha256", plan.get("output_sha256"))
        if text_digest(original) != original_hash or text_digest(text) != output_hash:
            raise RuntimeError("Reviewed text hash changed: " + eid)
        # The private plan records the exact extraction and editorial review.
        if any(not 0 <= r["start_character"] < r["end_character"] <= len(original) for r in ranges):
            raise RuntimeError("Short source range out of bounds")
        extracted = plan.get("join_separator", "\n\n").join(original[r["start_character"]:r["end_character"]] for r in ranges)
        if extracted.strip() != text.strip() or not plan.get("editorial_notes") or not plan.get("join_reviews"):
            raise RuntimeError("Short editorial evidence incomplete: " + eid)
        if any(a["end_character"] > b["start_character"] for a,b in zip(ranges,ranges[1:])):
            raise RuntimeError("Short source overlaps: " + eid)
        words = len(text.split())
        if not 14500 <= words <= 15500:
            raise RuntimeError("Short script outside calibrated bounds: " + eid)
        frozen = engine.SOURCE / eid
        frozen.mkdir(parents=True, exist_ok=True)
        target = frozen / "SCRIPT.txt"
        if target.exists() and target.read_text("utf-8-sig") != text:
            raise RuntimeError("Frozen short source conflict: " + eid)
        target.write_text(text, encoding="utf-8", newline="\n")
        shutil.copy2(PLANS / "plans" / (eid + ".json"), frozen / "editorial-plan.json")
        title = (PUBLIC / channel / eid / "TITRE.txt").read_text("utf-8-sig").strip()
        (frozen / "TITRE.txt").write_text(title + "\n", encoding="utf-8")
        delivery = Path(channel) / eid
        folder = engine.OUT / delivery
        folder.mkdir(parents=True, exist_ok=True)
        before = {}
        for name in ("SCRIPT.txt", "VOICEOVER.mp3"):
            dest = folder / name
            before[name] = digest(dest) if dest.exists() else None
        row = {"id": eid, "channel": channel, "state": "ready", "title": title,
               "script": eid + "/SCRIPT.txt", "sha256": text_digest(text), "characters": len(text),
               "words": words, "delivery_folder": str(delivery), "audio_file": str(delivery / "VOICEOVER.mp3"),
               "original_source_sha256": text_digest(original), "previous_delivery_hashes": before,
               "parts": partition(eid, text)}
        if eid == "FR-04-daedric-princes":
            old = next(e for e in old_fr["episodes"] if e["id"] == eid)
            for new, prior in zip(row["parts"][:2], old["parts"][:2]):
                if (prior["state"] != "verified" or prior["sha256"] != new["sha256"]
                        or prior["start"] != new["start"] or prior["end"] != new["end"]
                        or digest(prior["audio_path"]) != prior["audio_sha256"]):
                    raise RuntimeError("Paid prefix reuse could not be verified")
                new.update(state="downloaded", audio_path=prior["audio_path"], audio_sha256=prior["audio_sha256"],
                           audio_bytes=prior["audio_bytes"], duration_seconds=prior["duration_seconds"],
                           reused_from=str(OLD_FR), reused_part_id=prior["id"])
        rows.append(row)
    paid = sum(p["characters"] for e in rows for p in e["parts"] if p["state"] == "ready")
    if paid > MAX_AUTHORIZED_CHARACTERS:
        raise RuntimeError("Short batch exceeds character ceiling")
    data = {"created_at": engine.now(), "voice_id": VOICE, "voice_name": "Mellow Matt", "speed": SPEED,
            "provider": "elevenlabs", "generate_srt": False, "minimum_seconds": MINIMUM_SECONDS,
            "maximum_seconds": MAXIMUM_SECONDS, "source_root": str(engine.SOURCE), "output_root": str(engine.OUT),
            "authorized_new_characters": paid, "selection": "Ten shortened narrations and three first gaming episodes only",
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
    for e in data["episodes"]:
        text = (engine.SOURCE / e["script"]).read_text("utf-8-sig")
        expected = partition(e["id"], text)
        if len(expected) != len(e["parts"]):
            raise RuntimeError("Short source partition changed")
        for actual, original in zip(e["parts"], expected):
            if any(actual[k] != original[k] for k in ("id", "start", "end", "characters", "sha256", "audio_file")):
                raise RuntimeError("Short source slice changed")
        if any(not 10000 <= p["characters"] <= 25000 for p in e["parts"]):
            raise RuntimeError("Short block size outside expected bounds")
        folder = engine.OUT / e["delivery_folder"]
        (folder / "SCRIPT-COURT-EN-PRODUCTION.txt").write_text(text, encoding="utf-8", newline="\n")
        if e["state"] == "verified":
            for name, expected_hash in (("VOICEOVER.mp3", e["audio_sha256"]), ("SCRIPT.txt", e["sha256"])):
                actual = folder / name
                if not actual.exists() or digest(actual) != expected_hash:
                    raise RuntimeError("Delivered short package changed: " + e["id"])
    engine.save(data)
    return planned


def status_files(data):
    for e in data["episodes"]:
        counts = Counter(p["state"] for p in e["parts"])
        if e["state"] == "verified":
            label = "Version raccourcie livrée et contrôlée"
        elif submissions_paused():
            label = "Nouvelles soumissions en attente"
        elif e["state"] in STOP or any(p["state"] in STOP for p in e["parts"]):
            label = "Contrôle ou intervention requis avant livraison"
        else:
            label = "Nouvelle narration raccourcie en production"
        text = e["title"] + "\n\n" + label + ".\nMellow Matt, vitesse 0,90.\n"
        text += "Durée finale exigée : entre 2 heures et 2 h 30.\n"
        text += f"Blocs contrôlés : {counts.get('verified', 0)}/{len(e['parts'])}.\n"
        if e["state"] == "verified":
            text += f"VOICEOVER.mp3 : {e['duration_seconds']:.3f} secondes.\n"
            text += "Script raccourci, décodage, transcription automatique complète, assemblage et empreintes contrôlés.\n"
            text += "Les anciennes versions sont préservées dans les archives.\n"
        else:
            text += "Le MP3 existant, s'il est présent, reste la VERSION LONGUE en attendant le remplacement contrôlé.\n"
            text += "SCRIPT-COURT-EN-PRODUCTION.txt contient le nouveau texte.\n"
        folder = engine.OUT / e["delivery_folder"]
        (folder / "STATUT-VOICEOVER.txt").write_text(text, encoding="utf-8")
        (folder / "ETAT-DES-FICHIERS.txt").write_text(text + "\nMiniature et titre conservés.\n", encoding="utf-8")


def summary(data):
    return {"voice_id": VOICE, "speed": SPEED, "characters": sum(e["characters"] for e in data["episodes"]),
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
               if p["state"] in {"ready", "submitting", "submission_unknown", "failed"})


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
        fields["custom_title"] = "Sleep short 2026-10-28 - " + part["id"]
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
    passed = (qa.get("passed") is True and qa.get("scope") == "full_transcript"
              and qa.get("audio_sha256") == part["audio_sha256"]
              and qa.get("source_sha256") == part["sha256"]
              and digest(part["audio_path"]) == part["audio_sha256"])
    part.update(boundary_qa_passed=passed, boundary_qa_report=str(report),
                boundary_qa_scope="full_transcript", boundary_qa_at=engine.now())
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
    if not MINIMUM_SECONDS <= episode["duration_seconds"] <= MAXIMUM_SECONDS:
        raise RuntimeError("Duration cannot be delivered")
    folder = engine.OUT / episode["delivery_folder"]
    source_script = engine.SOURCE / episode["script"]
    desired = {"VOICEOVER.mp3": (source, episode["audio_sha256"]), "SCRIPT.txt": (source_script, episode["sha256"])}
    archive = engine.OUT / "_Archives des anciens dossiers/Versions longues avant correction - 28 octobre 2026" / episode["delivery_folder"]
    archive.mkdir(parents=True, exist_ok=True)
    # Archive both old assets before changing either. Never edit a shared hardlink in place.
    for name, (src, expected) in desired.items():
        dest = folder / name
        if not dest.exists():
            if episode["previous_delivery_hashes"][name] is not None:
                raise RuntimeError("Previous delivery unexpectedly missing")
            continue
        actual = digest(dest)
        if actual == expected:
            continue
        previous = episode["previous_delivery_hashes"][name]
        if actual != previous:
            episode["state"] = "delivery_conflict"
            engine.save(data)
            return
        backup = archive / name
        if backup.exists() and digest(backup) != previous:
            raise RuntimeError("Long original archive conflict")
        if not backup.exists():
            os.link(dest, backup)
        if digest(backup) != previous:
            raise RuntimeError("Archive failed verification")
    staged = []
    for name, (src, expected) in desired.items():
        dest = folder / name
        if dest.exists() and digest(dest) == expected:
            continue
        temporary = folder / (name + ".short-new")
        shutil.copy2(src, temporary)
        if digest(temporary) != expected:
            raise RuntimeError("Short delivery hash mismatch")
        staged.append((temporary, dest))
    marker = folder / "LIVRAISON-EN-COURS.txt"
    marker.write_text("Remplacement du MP3 et du script en cours. Attendre STATUT-VOICEOVER.txt : version raccourcie livrée.\n", encoding="utf-8")
    episode["state"] = "delivery_pending"
    engine.save(data)
    for temporary, dest in staged:
        temporary.replace(dest)
    evidence = {"id": episode["id"], "duration_seconds": episode["duration_seconds"],
                "script_sha256": episode["sha256"], "audio_sha256": episode["audio_sha256"],
                "audio_bytes": episode["audio_bytes"], "words": episode["words"],
                "duration_maximum_seconds": MAXIMUM_SECONDS, "full_decode_passed": True,
                "automatic_transcript_check_passed": True, "limits": "Automatic checks, not a full human listening."}
    (folder / "CONTROLES-VERSION-COURTE.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    episode.update(state="verified", audio_path=str(folder / "VOICEOVER.mp3"), delivered_at=engine.now())
    engine.save(data)
    marker.unlink(missing_ok=True)
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
    if episode["duration_seconds"] > MAXIMUM_SECONDS:
        episode["state"] = "duration_above_maximum"
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
        engine.emit("plan", episodes=len(data["episodes"]), parts=len(planned), characters=sum(e["characters"] for e in data["episodes"]),
                    largest_part=max(len(t) for _, _, t in planned), speed=SPEED, maximum_active=MAX_ACTIVE)
    elif args.action == "monitor":
        prepare(data)
        monitor(data)
    elif not run(data):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
