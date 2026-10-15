"""Execute the approved six-script voiceover batch, with a resumable private ledger.

No writing, rewriting, provider switching or automatic paid retries. The ledger
and audio belong outside Git. A lost submission response requires reconciliation.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import dotenv_values
from services import tts, media

VOICE = "IsEXLHzSvLH9UMB6SLHj"
SOURCE = ROOT / "chaines/sleep-theories/scripts-2026-10-15"
if not SOURCE.exists():
    SOURCE = ROOT / "scripts-2026-10-15"  # autonomous handoff folder
STATE = ROOT / "work/sleep-voiceovers-2026-10-15"
OUT = Path.home() / "Desktop/Voix sleep - 15 octobre 2026"


def now():
    return datetime.now(timezone.utc).isoformat()


def save(data):
    STATE.mkdir(parents=True, exist_ok=True)
    temp = STATE / "ledger.tmp"
    content = json.dumps(data, ensure_ascii=False, indent=2)
    for attempt in range(10):
        try:
            temp.write_text(content, encoding="utf-8")
            temp.replace(STATE / "ledger.json")
            return
        except PermissionError:
            # A Windows reader/backup can briefly lock replacement. This only
            # retries local persistence, never a chargeable network request.
            if attempt == 9:
                raise
            time.sleep(0.05 * (attempt + 1))


def emit(kind, **values):
    print(json.dumps({"event": kind, **values}, ensure_ascii=True), flush=True)


def load():
    ledger = STATE / "ledger.json"
    if ledger.exists():
        return json.loads(ledger.read_text(encoding="utf-8"))
    episodes = json.loads((SOURCE / "livraison-mesures.json").read_text(encoding="utf-8"))["episodes"]
    rows = []
    for index, episode in enumerate(episodes, 1):
        text = (SOURCE / episode["script"]).read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest != episode["sha256"] or not 200 <= len(text) <= 200000:
            raise RuntimeError("Source validation failed: " + episode["id"])
        rows.append({"id": episode["id"], "title": episode["title"],
                     "script": episode["script"], "sha256": digest,
                     "characters": len(text), "words": episode["words"],
                     "audio_file": f"{index:02d}-{episode['id']}.mp3", "state": "ready"})
    return {"created_at": now(), "voice_id": VOICE, "voice_name": "Mellow Matt",
            "provider": "elevenlabs", "speed": 0.90,
            "selection": "Existing standard provider default; expected 1x character rate",
            "episodes": rows}


def parts(data):
    """Two contiguous paragraph-aligned slices, exact concatenation to source."""
    for row in data["episodes"]:
        text = (SOURCE / row["script"]).read_text(encoding="utf-8")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != row["sha256"]:
            raise RuntimeError("Source changed")
        if "parts" not in row:
            if row.get("job_id") or row["state"] != "ready":
                raise RuntimeError("Reconcile existing episode-level submission first")
            cuts = [m.end() for m in re.finditer(r"\n\s*\n", text)]
            cut = min(cuts, key=lambda position: abs(position - len(text) / 2))
            slices = [text[:cut], text[cut:]]
            assert "".join(slices) == text
            row["parts"] = []
            for n, piece in enumerate(slices, 1):
                assert len(piece) <= 100000
                row["parts"].append({"id": row["id"] + f"-part{n}", "state": "ready",
                    "start": 0 if n == 1 else cut, "end": cut if n == 1 else len(text),
                    "characters": len(piece), "words": len(piece.split()),
                    "sha256": hashlib.sha256(piece.encode("utf-8")).hexdigest(),
                    "audio_file": row["id"] + f"-part{n}.mp3"})
        for part in row["parts"]:
            yield row, part, text[part["start"]:part["end"]]


def submit(data, limit):
    credits = tts.algrow_credits()
    data.setdefault("credits_before", credits)
    data["credits_latest"] = credits
    save(data)
    waiting = [(episode, row, text) for episode, row, text in parts(data)
               if row["state"] == "ready"][:limit]
    save(data)
    required = sum(row["characters"] for _, row, _ in waiting)
    available = credits["tts_characters"]["remaining"]
    if available < required:
        raise RuntimeError("Insufficient standard voiceover balance")
    for episode, row, text in waiting:
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != row["sha256"]:
            raise RuntimeError("Script changed after validation")
        fields = tts.algrow_fields(text, VOICE, speed=data["speed"], srt=True)
        fields["custom_title"] = "Sleep 2026-10-15 - " + row["id"]
        row.update(state="submitting", submitted_at=now())
        save(data)
        # Never retry a POST automatically: even a timeout can mean it was charged.
        try:
            result = tts._algrow_call("POST", "/api/generate-simple", fields, timeout=180)
        except Exception as exc:
            row.update(state="submission_unknown", error_type=type(exc).__name__)
            row["private_error"] = str(exc)
            save(data)
            raise
        row["submission_response"] = result
        if not result.get("job_id"):
            row["state"] = "submission_unknown"
            save(data)
            raise RuntimeError("No job ID; reconcile private response before retrying")
        row.update(state="submitted", job_id=result["job_id"])
        save(data)
        emit("submitted", id=row["id"], job_id=row["job_id"], characters=row["characters"])
    data["credits_latest"] = tts.algrow_credits()
    save(data)
    emit("balance", remaining=data["credits_latest"]["tts_characters"]["remaining"])


def download(row, status):
    folder = STATE / "parts"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / row["audio_file"]
    if not target.exists():
        temporary = target.with_suffix(".partial")
        tts._download(quote(status["audio_url"], safe=":/?&=#%+;,~@!$'()*[]"), str(temporary), timeout=300)
        temporary.replace(target)
    row["audio_path"] = str(target)
    row["audio_bytes"] = target.stat().st_size
    row["audio_sha256"] = hashlib.file_digest(target.open("rb"), "sha256").hexdigest()
    if status.get("transcript_url"):
        transcript = target.with_suffix(".srt")
        if not transcript.exists():
            temporary = transcript.with_suffix(".partial")
            tts._download(quote(status["transcript_url"], safe=":/?&=#%+;,~@!$'()*[]"), str(temporary), timeout=180)
            temporary.replace(transcript)
        row["transcript_path"] = str(transcript)
    row.update(state="downloaded", downloaded_at=now())
    emit("downloaded", id=row["id"], bytes=row["audio_bytes"])


def verify(row, minimum=0):
    result = subprocess.run([media.ffmpeg_bin(), "-hide_banner", "-nostdin", "-v", "error",
                             "-xerror", "-i", row["audio_path"], "-progress", "pipe:1",
                             "-f", "null", "-"], capture_output=True, timeout=1200,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        row.update(state="audio_check_failed", decode_errors=result.stderr.decode("utf-8", "replace")[-2000:])
        return
    values = re.findall(r"out_time_us=(\d+)", result.stdout.decode("utf-8", "replace"))
    if not values:
        raise RuntimeError("No decoded duration: " + row["id"])
    seconds = int(values[-1]) / 1000000
    row.update(duration_seconds=round(seconds, 3), full_decode_passed=True,
               over_two_hours=seconds >= 7200)
    if row.get("transcript_path"):
        words = tts._srt_words(Path(row["transcript_path"]).read_text(encoding="utf-8-sig"))
        row["srt_words"] = len(words)
        row["srt_end_seconds"] = words[-1]["e"] if words else None
        row["srt_word_ratio"] = round(len(words) / row["words"], 4)
    row.update(state="verified" if seconds >= minimum else "duration_below_minimum", verified_at=now())
    emit("verified", id=row["id"], seconds=seconds, over_two_hours=row["over_two_hours"],
         srt_word_ratio=row.get("srt_word_ratio"))


def assemble(row):
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / row["audio_file"]
    listing = STATE / (row["id"] + "-concat.txt")
    listing.write_text("".join("file '" + Path(p["audio_path"]).as_posix().replace("'", "'\\''") + "'\n"
                               for p in row["parts"]), encoding="utf-8")
    temporary = dest.with_suffix(".partial.mp3")
    media.run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c:a", "copy", str(temporary)], timeout=300)
    temporary.replace(dest)
    row.update(audio_path=str(dest), audio_bytes=dest.stat().st_size,
               audio_sha256=hashlib.file_digest(dest.open("rb"), "sha256").hexdigest())
    verify(row, minimum=7200)
    row["assembly"] = "Contiguous source halves; MP3 packet concatenation, no added silence or repeated content"
    expected = sum(p["duration_seconds"] for p in row["parts"])
    row["duration_join_delta_seconds"] = round(row["duration_seconds"] - expected, 3)


def monitor(data):
    while True:
        for episode, row, text in parts(data):
            if row["state"] in {"submitted", "queued", "processing", "generating", "completed", "poll_error"}:
                try:
                    status = tts._algrow_call("GET", "/api/job-status/" + row["job_id"], timeout=60)
                    row["last_response"] = status
                    current = status.get("status")
                    if current != row.get("remote_status"):
                        emit("status", id=row["id"], status=current)
                    row.update(remote_status=current, last_poll=now())
                    if current == "failed":
                        row.update(state="failed", failure=status.get("error_message") or status.get("error"))
                    elif current == "completed" and status.get("audio_url"):
                        download(row, status)
                    else:
                        row["state"] = "submitted"
                    save(data)
                except Exception as exc:
                    row.update(state="poll_error", last_error_type=type(exc).__name__)
                    save(data)
                    emit("read_error", id=row["id"], error_type=type(exc).__name__)
            if row["state"] == "downloaded":
                verify(row)
                save(data)
        for episode in data["episodes"]:
            if episode["state"] == "ready" and all(p["state"] == "verified" for p in episode["parts"]):
                assemble(episode)
                save(data)
        active = [r for _, r, _ in parts(data) if r["state"] in
                  {"submitted", "queued", "processing", "generating", "completed", "poll_error", "downloaded"}]
        if not active:
            break
        time.sleep(25)
    data["credits_latest"] = tts.algrow_credits()
    save(data)
    emit("finished", states={r["id"]: r["state"] for r in data["episodes"]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["plan", "submit", "monitor"])
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    # Explicit task-local choice: a stale inherited Windows value must not win.
    config = dotenv_values(ROOT / ".env")
    if not config.get("ALGROW_API_KEY"):
        raise RuntimeError("Repository .env lacks the configured account key")
    os.environ["ALGROW_API_KEY"] = config["ALGROW_API_KEY"]
    data = load()
    if args.action == "plan":
        emit("plan", characters=sum(r["characters"] for r in data["episodes"]),
             voice_id=VOICE, speed=data["speed"], episodes=len(data["episodes"]))
    elif args.action == "submit":
        submit(data, args.limit)
    else:
        monitor(data)


if __name__ == "__main__":
    main()
