"""Recover three confirmed failed French narrations, at most two active jobs.

Only ``run`` submits paid requests. ``monitor`` retrieves existing jobs only.
Private state preserves every source slice and its original failed job reference.
"""
import argparse
from collections import Counter
import copy
import hashlib
import math
import os
from pathlib import Path
import re
import shutil

import recap_voiceovers_oct28 as base

engine = base.engine
ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "work/recap-voiceovers-2026-10-28"
engine.STATE = ROOT / "work/recap-voiceovers-2026-10-28-recovery"
engine.SOURCE = ORIGINAL / "sources"
engine.OUT = Path.home() / "Desktop/VIDEOS - TOUT REGROUPE/La Boîte à Récap"
FOLDERS = {
    "04-quatre-fantastiques": "04 - Les 4 Fantastiques",
    "06-frieren": "06 - Frieren",
    "07-sakamoto-days": "07 - Sakamoto Days",
}
VOICE = "IHngRooVccHyPqB4uQkG"
SPEED = 0.85
CHARACTERS = 473930
PARTS = 24
MAX_ACTIVE = 2
TARGET_REPAIR = "06-frieren-part2-recovery1"
STOP_STATES = {
    "failed", "submitting", "submission_unknown", "transcript_missing",
    "transcript_review_required", "audio_check_failed", "duration_below_minimum",
    "assembly_check_failed", "delivery_conflict",
}
base_assemble = base.assemble


def source_text(episode):
    path = engine.SOURCE / episode["script"]
    text = path.read_text(encoding="utf-8")
    if base.digest(path) != episode["sha256"] or hashlib.sha256(text.encode()).hexdigest() != episode["sha256"]:
        raise RuntimeError("Frozen source changed: " + episode["id"])
    if len(text) != episode["characters"]:
        raise RuntimeError("Frozen source length changed: " + episode["id"])
    return text


def subdivide(episode, old_part, text):
    start, end = old_part["start"], old_part["end"]
    piece = text[start:end]
    if hashlib.sha256(piece.encode()).hexdigest() != old_part["sha256"]:
        raise RuntimeError("Original failed slice changed")
    boundaries = [m.end() for m in re.finditer(r"\n\s*\n", piece)]
    if not boundaries:
        raise RuntimeError("No paragraph boundaries for recovery")
    cuts = [0] + [min(boundaries, key=lambda p: abs(p - len(piece) * i / 4)) for i in range(1, 4)] + [len(piece)]
    if cuts != sorted(set(cuts)):
        raise RuntimeError("Invalid recovery partition")
    rows = []
    for n, (a, b) in enumerate(zip(cuts, cuts[1:]), 1):
        part = piece[a:b]
        if not 200 <= len(part) < 30000:
            raise RuntimeError("Recovery slice is outside the allowed size")
        name = old_part["id"] + "-recovery" + str(n)
        rows.append({"id": name, "state": "ready", "start": start + a, "end": start + b,
                     "characters": len(part), "words": len(part.split()),
                     "sha256": hashlib.sha256(part.encode()).hexdigest(), "audio_file": name + ".mp3",
                     "replaces_failed_job_id": old_part["job_id"]})
    return rows


def load():
    ledger = engine.STATE / "ledger.json"
    if ledger.exists():
        data = base.json_read(ledger)
        if (tuple(e["id"] for e in data["episodes"]) != tuple(FOLDERS)
                or data["source_root"] != str(engine.SOURCE) or data["output_root"] != str(engine.OUT)
                or data["voice_id"] != VOICE or data["speed"] != SPEED
                or data["provider"] != "elevenlabs" or data["generate_srt"] is not True):
            raise RuntimeError("Recovery ledger settings changed")
        engine.VOICE = VOICE
        return data
    original = base.json_read(ORIGINAL / "ledger.json")
    if original["voice_id"] != VOICE:
        raise RuntimeError("Original voice does not match")
    selected = {e["id"]: e for e in original["episodes"]}
    episodes = []
    for eid, folder in FOLDERS.items():
        old = selected[eid]
        text = source_text(old)
        if len(old["parts"]) != 2:
            raise RuntimeError("Unexpected original partition")
        episode = {key: copy.deepcopy(old[key]) for key in ("id", "channel", "title", "script", "sha256", "characters", "words")}
        episode.update(state="ready", delivery_folder=folder, audio_file=folder + "/voiceover.mp3", parts=[], failed_attempts=[])
        for part in old["parts"]:
            response = part.get("last_response", {})
            if part["state"] != "failed" or response.get("status") != "failed" or response.get("audio_url"):
                raise RuntimeError("Original job is not a confirmed failure without audio")
            episode["failed_attempts"].append(copy.deepcopy(part))
            episode["parts"].extend(subdivide(episode, part, text))
        episodes.append(episode)
    data = {"created_at": engine.now(), "voice_id": VOICE,
            "voice_name": "Voix française fournie par l'utilisateur", "provider": "elevenlabs",
            "speed": SPEED, "generate_srt": True, "source_root": str(engine.SOURCE),
            "output_root": str(engine.OUT), "original_ledger_sha256": base.digest(ORIGINAL / "ledger.json"),
            "original_ledger_path": str(ORIGINAL / "ledger.json"), "episodes": episodes,
            "recovery_policy": "Confirmed failures only, exact contiguous text, two active jobs maximum, no automatic paid retries"}
    engine.VOICE = VOICE
    engine.save(data)
    return data


def expected_layout(data):
    """Allow only the explicitly audited subdivision of one confirmed failure."""
    counts = {eid: 8 for eid in FOLDERS}
    repairs = data.get("targeted_repairs", [])
    if not repairs:
        return PARTS, counts
    if len(repairs) != 1 or repairs[0].get("source_part_id") != TARGET_REPAIR:
        raise RuntimeError("Unrecognized targeted repair")
    repair = repairs[0]
    episode = next(e for e in data["episodes"] if e["id"] == "06-frieren")
    archived = [p for p in episode.get("failed_attempts", []) if p["id"] == TARGET_REPAIR]
    if len(archived) != 1 or archived[0]["state"] != "failed":
        raise RuntimeError("Targeted repair must preserve its confirmed failed attempt")
    old = archived[0]
    if old.get("last_response", {}).get("status") != "failed" or old["last_response"].get("audio_url"):
        raise RuntimeError("Targeted repair original is not a failure without audio")
    names = [TARGET_REPAIR + "-retry1", TARGET_REPAIR + "-retry2"]
    if repair.get("replacement_ids") != names or repair.get("source_sha256") != old["sha256"]:
        raise RuntimeError("Targeted repair identity changed")
    children = [p for p in episode["parts"] if p["id"] in names]
    if (len(children) != 2 or [p["id"] for p in children] != names
            or [p["characters"] for p in children] != [10474, 10264]
            or [children[0]["start"], children[0]["end"], children[1]["start"], children[1]["end"]]
               != [82028, 92502, 92502, 102766]
            or any(p.get("replaces_failed_job_id") != old["job_id"] for p in children)):
        raise RuntimeError("Targeted repair source ranges changed")
    counts[episode["id"]] = 9
    return PARTS + 1, counts


def prepare(data):
    if data.get("pending_targeted_approval"):
        raise RuntimeError("Targeted candidate is awaiting review; do not run it yet")
    planned = list(engine.parts(data))
    expected_parts, expected_counts = expected_layout(data)
    if len(planned) != expected_parts or sum(len(text) for _, _, text in planned) != CHARACTERS:
        raise RuntimeError("Recovery must contain all authorized source slices exactly once")
    for episode in data["episodes"]:
        text = source_text(episode)
        parts = episode["parts"]
        if len(parts) != expected_counts[episode["id"]] or parts[0]["start"] != 0 or parts[-1]["end"] != len(text):
            raise RuntimeError("Incomplete recovery source coverage")
        if any(a["end"] != b["start"] for a, b in zip(parts, parts[1:])):
            raise RuntimeError("Recovery source has a gap or overlap")
        source = engine.SOURCE / episode["id"]
        target = engine.OUT / episode["delivery_folder"]
        target.mkdir(parents=True, exist_ok=True)
        script = target / "SCRIPT.txt"
        if script.exists() and base.digest(script) != episode["sha256"]:
            raise RuntimeError("Delivery script differs: " + episode["id"])
        if not script.exists():
            shutil.copy2(source / "SCRIPT.txt", script)
        publication = target / "TITRE-ET-DESCRIPTION.txt"
        if not publication.exists():
            combined = "TITRE\n" + (source / "TITRE.txt").read_text(encoding="utf-8-sig").strip()
            combined += "\n\nDESCRIPTION\n" + (source / "DESCRIPTION.txt").read_text(encoding="utf-8-sig").strip() + "\n"
            publication.write_text(combined, encoding="utf-8", newline="\n")
        final = engine.OUT / episode["audio_file"]
        if final.exists() and base.digest(final) != episode.get("audio_sha256"):
            raise RuntimeError("Unregistered or conflicting final audio: " + episode["id"])
        if episode["state"] == "verified" and not final.exists():
            raise RuntimeError("Verified final audio is missing")
    for _, part, text in planned:
        if not 200 <= len(text) < 30000 or len(text) != part["characters"]:
            raise RuntimeError("Recovery slice size changed")
        if hashlib.sha256(text.encode()).hexdigest() != part["sha256"]:
            raise RuntimeError("Recovery slice hash changed")
    engine.save(data)
    return planned


def status_files(data):
    for episode in data["episodes"]:
        counts = Counter(p["state"] for p in episode["parts"])
        action = episode["state"] in STOP_STATES or any(s in STOP_STATES for s in counts)
        if episode["state"] == "verified":
            label = "Terminée et contrôlée"
        elif action:
            label = "Action requise avant livraison"
        elif all(p["state"] == "ready" for p in episode["parts"]):
            label = "Reprise préparée, génération non lancée"
        else:
            label = "Génération et récupération en cours"
        text = episode["title"] + "\n\n" + label + ".\n"
        text += "Voix française de La Boîte à Récap, vitesse 0,85.\n"
        text += f"Blocs contrôlés : {counts.get('verified', 0)}/{len(episode['parts'])}.\n"
        if episode.get("duration_seconds"):
            text += f"Durée mesurée : {episode['duration_seconds']:.3f} secondes.\n"
        if episode["state"] == "verified":
            text += "Fichier : voiceover.mp3\nDécodage complet, durée minimale de deux heures, texte de transcription et assemblage contrôlés.\n"
            text += "La transcription est un alignement fourni par le service ; pas d'écoute humaine intégrale.\n"
        else:
            text += "Le MP3 complet sera placé ici après les contrôles ; aucun fichier partiel n'est présenté comme terminé.\n"
        target = engine.OUT / episode["delivery_folder"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "STATUT-VOICEOVER.txt").write_text(text, encoding="utf-8", newline="\n")


def assemble(episode):
    base_assemble(episode)
    if episode.get("duration_seconds") is not None:
        episode["assembly"] = f"{len(episode['parts'])} exact contiguous source slices; MP3 packet concatenation, no padding or repeated content"


def blocked(data):
    return any(e["state"] in STOP_STATES or any(p["state"] in STOP_STATES for p in e["parts"])
               for e in data["episodes"])


def reconcile_original_failures(data):
    """Read-only confirmation before creating any replacement jobs."""
    for episode in data["episodes"]:
        for old in episode["failed_attempts"]:
            status = engine.tts._algrow_call("GET", "/api/job-status/" + old["job_id"], timeout=60)
            if status.get("status") != "failed" or status.get("audio_url"):
                raise RuntimeError("Original job status changed; recover or reconcile before replacement")
    data["original_failures_reconfirmed_at"] = engine.now()
    engine.save(data)


def run(data):
    """Explicit authorization to submit this finite queue; never resubmit any job."""
    prepare(data)
    reconciled = False
    while True:
        active = [p for e in data["episodes"] for p in e["parts"] if p["state"] in base.ACTIVE]
        if len(active) > MAX_ACTIVE:
            raise RuntimeError("More than two active jobs; reconcile before continuing")
        # Retrieve accepted jobs even if the other request in their pair was ambiguous.
        needs_assembly = any(e["state"] in {"ready", "delivery_pending"}
                             and all(p["state"] == "verified" for p in e["parts"])
                             for e in data["episodes"])
        if active or needs_assembly:
            base.monitor(data)
        if blocked(data):
            status_files(data)
            engine.emit("action_required", **base.summary(data))
            return False
        waiting = [p for e in data["episodes"] for p in e["parts"] if p["state"] == "ready"]
        if not waiting:
            return all(e["state"] == "verified" for e in data["episodes"])
        if not reconciled:
            reconcile_original_failures(data)
            reconciled = True
        credits = engine.tts.algrow_credits()
        required = sum(math.ceil(p["characters"] * 1.2) for p in waiting)
        if credits["tts_characters"]["remaining"] < required:
            raise RuntimeError("Insufficient balance for the remaining authorized recovery")
        if not base.submit(data, MAX_ACTIVE):
            # One request may have been accepted before the ambiguous response.
            base.monitor(data)
            return False


# The existing submit/monitor functions resolve these names in their own module.
base.prepare = prepare
base.status_files = status_files
base.assemble = assemble


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
            lock.write(b"0"); lock.flush()
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
        engine.emit("status", **base.summary(data))
    elif args.action == "plan":
        planned = prepare(data)
        status_files(data)
        engine.emit("plan", episodes=len(data["episodes"]), parts=len(planned), characters=CHARACTERS,
                    largest_part=max(len(t) for _, _, t in planned), speed=SPEED, maximum_active=MAX_ACTIVE)
    elif args.action == "monitor":
        prepare(data)
        base.monitor(data)
    elif not run(data):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
