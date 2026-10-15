"""Finalize local voiceover evidence and the autonomous handoff; no paid calls."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services import tts

BASE = ROOT / "chaines/sleep-theories"
if not BASE.exists():
    BASE = ROOT  # autonomous handoff package
STATE = ROOT / "work/sleep-voiceovers-2026-10-15"
OUT = Path.home() / "Desktop/Voix sleep - 15 octobre 2026"
BACKUP = Path.home() / "Desktop/REPRISE - Deep Void et Quiet Paradox"
REPORT = BASE / "narrations-2026-10-15"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the Windows hidden-file attribute on existing handoff files.
    if path.exists():
        with path.open("r+", encoding="utf-8") as f:
            f.write(text)
            f.truncate()
    else:
        path.write_text(text, encoding="utf-8")


def dump(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def hms(seconds):
    total = round(seconds)
    return f"{total // 3600}:{total // 60 % 60:02d}:{total % 60:02d}"


def stamp(seconds):
    milliseconds = round(seconds * 1000)
    return f"{milliseconds // 3600000:02d}:{milliseconds // 60000 % 60:02d}:{milliseconds // 1000 % 60:02d},{milliseconds % 1000:03d}"


def srt_seconds(value):
    h, m, sec = value.strip().replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def caption_evidence(episode, source):
    offset, joined, evidence = 0.0, [], []
    for part in episode["parts"]:
        path = Path(part["transcript_path"])
        text = path.read_text(encoding="utf-8-sig")
        words = tts._srt_words(text)
        original = source[part["start"]:part["end"]]
        normalized = lambda value: re.findall(r"[a-z0-9]+", value.lower())
        a, b = normalized(original), normalized(" ".join(w["w"] for w in words))
        raw_ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
        # Reviewed spelling variants in the automatic transcript, not edits to
        # the script/audio/captions and not a claim about spoken pronunciation.
        aliases = ({"lumen": "lumon", "keir": "kier", "egan": "eagan", "egans": "eagans",
                    "coble": "cobel", "kobel": "cobel", "cobble": "cobel", "james": "jame"}
                   if episode["id"] == "QP-06-severance-eagan" else {})
        canonical_a = [aliases.get(w, w) for w in a]
        canonical_b = [aliases.get(w, w) for w in b]
        matcher = difflib.SequenceMatcher(None, canonical_a, canonical_b, autojunk=False)
        gaps = [j-i for op, i, j, k, l in matcher.get_opcodes() if op != "equal"]
        ratio = matcher.ratio()
        tail = part["duration_seconds"] - words[-1]["e"]
        check = {"id": part["id"], "alignment_ratio": round(ratio, 6),
                 "raw_alignment_ratio": round(raw_ratio, 6), "reviewed_spelling_aliases": aliases,
                 "longest_nonmatching_source_span_words": max(gaps, default=0),
                 "first_50_words_identical": a[:50] == b[:50],
                 "last_50_words_identical": a[-50:] == b[-50:],
                 "audio_tail_after_srt_seconds": round(tail, 3),
                 "passed": ratio >= 0.98 and max(gaps, default=0) < 30 and -1 <= tail <= 5}
        evidence.append(check)
        for block in re.split(r"\n\s*\n", text.replace("\r", "").strip()):
            lines = block.splitlines()
            index = next((i for i, line in enumerate(lines) if "-->" in line), None)
            if index is None:
                continue
            begin, end = lines[index].split("-->")
            start, stop = srt_seconds(begin) + offset, srt_seconds(end.split()[0]) + offset
            joined.append(f"{len(joined)+1}\n{stamp(start)} --> {stamp(stop)}\n" + "\n".join(lines[index+1:]))
        offset += part["duration_seconds"]
    if not all(c["passed"] for c in evidence):
        dump(STATE / (episode["id"] + "-caption-review.json"), evidence)
        raise RuntimeError("Transcript coverage needs review: " + episode["id"])
    write(OUT / Path(episode["audio_file"]).with_suffix(".srt"), "\n\n".join(joined) + "\n")
    return evidence


def main():
    ledger = json.loads((STATE / "ledger.json").read_text(encoding="utf-8"))
    if len(ledger["episodes"]) != 6 or not all(e["state"] == "verified" for e in ledger["episodes"]):
        raise RuntimeError("All six assembled audios must be verified before delivery")
    episodes = []
    successful_parts = sum(len(e["parts"]) for e in ledger["episodes"])
    failed_attempts = [{"episode": e["id"], "job_id": p["job_id"], "failure": p.get("failure")}
                       for e in ledger["episodes"] for p in e.get("failed_attempts", [])]
    for e in ledger["episodes"]:
        source = (BASE / "scripts-2026-10-15" / e["script"]).read_text(encoding="utf-8")
        assert hashlib.sha256(source.encode()).hexdigest() == e["sha256"]
        assert "".join(source[p["start"]:p["end"]] for p in e["parts"]) == source
        assert e["duration_seconds"] >= 7200 and e["full_decode_passed"]
        assert digest(Path(e["audio_path"])) == e["audio_sha256"]
        checks = caption_evidence(e, source)
        episodes.append({"id": e["id"], "title": e["title"], "state": "audio_verified",
            "script_sha256": e["sha256"], "source_characters": e["characters"],
            "audio_file": e["audio_file"], "audio_bytes": e["audio_bytes"],
            "audio_sha256": e["audio_sha256"], "duration_seconds": e["duration_seconds"],
            "duration": hms(e["duration_seconds"]), "over_two_hours": True,
            "full_decode_passed": True, "join_delta_seconds": e["duration_join_delta_seconds"],
            "caption_checks": checks, "parts": [{"id": p["id"], "job_id": p["job_id"],
                 "duration_seconds": p["duration_seconds"], "audio_sha256": p["audio_sha256"]} for p in e["parts"]]})
    before = ledger["credits_before"]["tts_characters"]["remaining"]
    after = ledger["credits_latest"]["tts_characters"]["remaining"]
    public = {"date": "2026-10-15", "state": "six_audios_downloaded_verified",
              "user_authorized": True, "voice_id": ledger["voice_id"], "voice_name": ledger["voice_name"],
              "speed": ledger["speed"], "source_characters": sum(e["source_characters"] for e in episodes),
              "audio_measured": True, "all_over_two_hours": True,
              "successful_source_parts": successful_parts, "failed_attempts": failed_attempts,
              "accepted_jobs_including_failed": successful_parts + len(failed_attempts),
              "recovery_audit": json.loads((STATE / "recovery-audit.json").read_text(encoding="utf-8")),
              "recovery_note": "One definitive unbilled failure replaced by four shorter contiguous slices; source unchanged",
              "balance_before": before, "balance_after": after, "observed_character_debit": before-after,
              "debit_note": "Observed account balance change, including requested captions; other account activity may affect it",
              "desktop_folder": OUT.name, "episodes": episodes,
              "limitations": ["Full MP3 decoding and transcript comparison performed; no claim of complete human listening",
                              "Automatic captions retain transcription errors, especially names; review before publication",
                              "No music, video montage or publication performed"]}
    dump(REPORT / "suivi.json", public)
    dump(OUT / "CONTROLES.json", public)
    table = "\n".join(f"| {e['id']} | {e['duration']} |" for e in episodes)
    readme = f"""# Six narrations terminées — 15 octobre 2026

Les six MP3 complets sont récupérés et contrôlés, voix **Mellow Matt**, ID `{ledger['voice_id']}`, vitesse **0,90**. Chaque fichier dépasse deux heures de narration. Les textes finaux sont inchangés.

| Épisode | Durée décodée |
|---|---:|
{table}

Fichiers sur le Bureau : **{OUT.name}**. Les {successful_parts} parties sources terminées sont conservées dans `work/sleep-voiceovers-2026-10-15/parts`. Les scripts sont découpés en parties contiguës sous la limite de 100 000 caractères du compte. L'assemblage conserve les paquets MP3, sans réencodage, silence ou répétition ajoutés.

Contrôles : empreinte du texte, source complète, décodage intégral sans erreur, durée réelle et comparaison des sous-titres au texte. Détails dans `suivi.json`. Les SRT automatiques sont fournis pour chaque MP3 ; leurs noms propres et autres erreurs de transcription restent à corriger avant publication. Ces vérifications ne constituent pas une écoute humaine intégrale.

Solde observé : **{before:,} → {after:,} caractères**, soit **{before-after:,} débités**, sous-titres demandés compris. Ce relevé est celui du compte, pas une facture ventilée par job.

Reprise : `production/sleep_voiceovers.py monitor` relit les jobs existants sans soumettre de génération. `production/sleep_voiceover_delivery.py` reconstruit le relevé et la sauvegarde sans appel payant. Le registre privé `work/sleep-voiceovers-2026-10-15/ledger.json` contient les réponses et URL des médias ; ne pas le publier. La clé valide reste exclusivement dans le `.env` privé. Une ancienne variable Windows est refusée, sans avoir été modifiée.

Le premier essai intégral a été refusé pour taille, sans job ni débit. La seconde moitié de Severance a ensuite échoué définitivement sans être facturée : le solde correspondait exactement aux onze jobs réussis. Son texte a été réparti en quatre blocs plus courts, sans réécriture, avec la même voix. Les {successful_parts} parties réussies sont terminées. Aucun nouveau montage ou upload n'est lancé. Préserver les originaux et ne pas repayer ces voix.
"""
    write(REPORT / "README.md", readme)
    write(OUT / "LIRE-MOI.txt", readme)
    write(OUT / "TITRES.txt", "\n\n".join(e["audio_file"] + "\n" + e["title"] + "\n" + e["duration"] for e in episodes) + "\n")
    status_path = BASE / "etat-videos.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    batch = status["next_script_batch"]
    batch.update(state="six_final_scripts_and_voiceovers_verified", audio_generated=True)
    batch["narration_batch"].update(completed_audio_verified=6, all_over_two_hours=True,
        state="six_audios_downloaded_verified", report="narrations-2026-10-15/suivi.json",
        successful_parts=successful_parts, parts_accepted=successful_parts + len(failed_attempts),
        recovery_state="completed", failed_unbilled_jobs=len(failed_attempts))
    dump(status_path, status)
    p = BASE / "PROCHAINES-ACTIONS.md"
    text = p.read_text(encoding="utf-8")
    start, end = text.index("3. "), text.index("4. ")
    text = text[:start] + "3. Les six voix Algrow Mellow Matt sont récupérées et contrôlées, toutes au-delà\n   de deux heures. Voir `narrations-2026-10-15/README.md` et le dossier Bureau\n   **Voix sleep - 15 octobre 2026**. Ne pas les régénérer. Le montage reste à faire.\n" + text[end:]
    write(p, text)
    tools_path = BASE / "OUTILS-ET-REPRISE.md"
    tools_text = tools_path.read_text(encoding="utf-8")
    if "## Voix Algrow du 15 octobre" not in tools_text:
        tools_text += "\n## Voix Algrow du 15 octobre\n\nLes six narrations ont été produites avec l'API Algrow, voix Mellow Matt\n`IsEXLHzSvLH9UMB6SLHj`, vitesse 0,90. Les parties sources sont terminées ;\nne pas les relancer. Voir `narrations-2026-10-15/README.md` et le registre privé\n`work/sleep-voiceovers-2026-10-15/ledger.json`. MP3 complets sur le Bureau dans\n**Voix sleep - 15 octobre 2026**, et dans **VOIX-FINALES** de la sauvegarde.\n\nCet accès API utilise `ALGROW_API_KEY` dans le `.env` privé du dépôt ; il peut\nfonctionner après un changement de compte ChatGPT sur le même PC. La connexion\nMCP de recherche reste propre au compte de l'application. Une ancienne variable\nWindows du même nom est refusée : l'exécuteur choisit la clé du `.env` uniquement\npour son processus. Ne pas modifier Windows ni afficher la clé.\n\nCompte professionnel : 100 000 caractères maximum par génération, et sous-titres\navec supplément. Les fichiers sont découpés sans réécriture puis réunis en MP3\nsans silence ou répétition ajoutés. Les SRT sont automatiques, noms à relire.\nL'exécuteur de reprise ne soumet pas de nouveau job en mode `monitor`.\n"
        write(tools_path, tools_text)
    p = BASE / "README.md"
    text = p.read_text(encoding="utf-8")
    a, b = text.index("## Narrations du nouveau lot"), text.index("## Miniatures du nouveau lot")
    text = text[:a] + "## Narrations du nouveau lot\n\nLes six voix Algrow sont terminées, téléchargées et contrôlées, voix Mellow Matt\n`IsEXLHzSvLH9UMB6SLHj`. Toutes dépassent deux heures. Lire [le relevé des voix](narrations-2026-10-15/README.md).\nCopie sur le Bureau : **Voix sleep - 15 octobre 2026**. Ne pas régénérer les jobs terminés.\n\n" + text[b:]
    write(p, text)
    p = ROOT / "REPRISE-SLEEP.md"
    text = p.read_text(encoding="utf-8")
    a, b = text.index("Ils font chacun"), text.index("Le README du lot", text.index("Ils font chacun"))
    text = text[:a] + "Ils font chacun plus de 20 500 mots. Les six voix Algrow Mellow Matt sont téléchargées\net contrôlées, toutes au-delà de deux heures. Relevé :\n`chaines/sleep-theories/narrations-2026-10-15/README.md`.\nMP3 complets sur le Bureau : **Voix sleep - 15 octobre 2026**. Ne pas les régénérer.\nAucun nouveau montage ou upload lancé. " + text[b:]
    write(p, text)
    measurements_path = BASE / "scripts-2026-10-15/livraison-mesures.json"
    measurements = json.loads(measurements_path.read_text(encoding="utf-8"))
    measurements["measured_audio"] = True
    for row, e in zip(measurements["episodes"], episodes):
        assert row["id"] == e["id"]
        row.update(audio_duration_seconds=e["duration_seconds"], audio_file=e["audio_file"])
    dump(measurements_path, measurements)
    p = BASE / "scripts-2026-10-15/README.md"
    text = p.read_text(encoding="utf-8")
    text = text.replace("La voix finale doit être générée puis chronométrée dans Ultravid. Aucun audio ou upload n'a été réalisé pour ce lot.",
        "Les six voix ont ensuite été générées dans Algrow avec Mellow Matt et mesurées : toutes dépassent deux heures. Voir `../narrations-2026-10-15/README.md`. Aucun montage ou upload lancé.")
    write(p, text)
    for name in ["README.md", "PROCHAINES-ACTIONS.md", "etat-videos.json", "OUTILS-ET-REPRISE.md"]:
        shutil.copy2(BASE / name, BACKUP / name)
    for folder in ["narrations-2026-10-15", "scripts-2026-10-15"]:
        shutil.copytree(BASE / folder, BACKUP / folder, dirs_exist_ok=True)
    write(BACKUP / "REPRISE-SLEEP.md", (ROOT / "REPRISE-SLEEP.md").read_text(encoding="utf-8"))
    for name in ["production/sleep_voiceovers.py", "production/sleep_voiceover_delivery.py"]:
        shutil.copy2(ROOT / name, BACKUP / name)
    shutil.copytree(STATE, BACKUP / "work/sleep-voiceovers-2026-10-15", dirs_exist_ok=True)
    shutil.copytree(OUT, BACKUP / "VOIX-FINALES", dirs_exist_ok=True)
    for e in ledger["episodes"]:
        assert digest(BACKUP / "VOIX-FINALES" / e["audio_file"]) == e["audio_sha256"]
        for part in e["parts"]:
            assert digest(BACKUP / "work/sleep-voiceovers-2026-10-15/parts" / part["audio_file"]) == part["audio_sha256"]
    write(BACKUP / "NARRATIONS-REPRISE.txt", "Six voix terminees et verifiees. Lire narrations-2026-10-15/README.md.\nMP3 complets : VOIX-FINALES/. Parties sources et registre prive : work/sleep-voiceovers-2026-10-15/.\nNe pas regenerer ou repayer. Aucun secret copie. La cle reste dans le .env prive du depot original.\nLa passation fonctionne sans l historique du chat. Aucun montage ni upload lance.\n")
    entries = [{"path": p.relative_to(BACKUP).as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)}
               for p in sorted(BACKUP.rglob("*")) if p.is_file() and p.name not in {"INVENTAIRE.json", "VERIFICATIONS.json"}]
    dump(BACKUP / "INVENTAIRE.json", {"date": "2026-10-15", "files": entries,
         "note": "No keys or browser sessions. Private narration media URLs in work ledger: do not publish."})
    check_path = BACKUP / "VERIFICATIONS.json"
    checks = json.loads(check_path.read_text(encoding="utf-8"))
    checks["narrations_2026_10_15"] = {"parts_complete": successful_parts, "failed_attempts": len(failed_attempts), "final_audios_verified": 6,
        "all_over_two_hours": True, "source_and_backup_audio_hashes_match": True,
        "manifest_files": len(entries), "no_credentials_copied": True}
    dump(check_path, checks)
    print(json.dumps({"delivered": 6, "durations": {e["id"]: e["duration"] for e in episodes},
                      "character_debit": before-after, "remaining": after, "backup_verified": True}))


if __name__ == "__main__":
    main()
