"""Generate only the user-authorized missing ending, with a separate durable ledger."""
import argparse
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import re
import shutil
import time

import sleep_voiceovers as engine

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "work/sleep-voiceovers-2026-10-24"
SOURCE = ROOT / "chaines/sleep-theories/scripts-2026-10-22"
engine.STATE = BATCH / "silo-ending-repair"
START = 137874


def load():
    original = json.loads((BATCH / "ledger.json").read_text(encoding="utf-8"))
    episode = next(x for x in original["episodes"] if x["id"] == "QP-10-silo-outside")
    text = (SOURCE / episode["script"]).read_text(encoding="utf-8-sig")
    assert hashlib.sha256(text.encode()).hexdigest() == episode["sha256"]
    assert text[START:].startswith("The interval between those circumstances remains unfilled,")
    assert len(text[START:]) == 29377
    ledger = engine.STATE / "ledger.json"
    if ledger.exists():
        d = json.loads(ledger.read_text(encoding="utf-8"))
        assert d["source_sha256"] == episode["sha256"] and d["source_start"] == START
    else:
        boundaries = [m.end() for m in re.finditer(r"\n\s*\n", text) if m.end() > START]
        cut = min(boundaries, key=lambda p:abs(p-(START+len(text))/2))
        d = {"created_at":engine.now(), "episode_id":episode["id"],
             "source_script":episode["script"], "source_sha256":episode["sha256"],
             "source_start":START, "source_end":len(text), "characters":len(text)-START,
             "voice_id":engine.VOICE, "voice_name":"Mellow Matt", "speed":0.90,
             "generate_srt":False, "original_final_sha256":episode["audio_sha256"], "parts":[]}
        for n,(a,b) in enumerate([(START,cut),(cut,len(text))],1):
            piece=text[a:b]
            name=f"QP-10-silo-outside-ending-{n}"
            d["parts"].append({"id":name,"state":"ready","start":a,"end":b,
                               "characters":len(piece),"words":len(piece.split()),
                               "sha256":hashlib.sha256(piece.encode()).hexdigest(),
                               "audio_file":name+".mp3"})
    assert d["parts"][0]["start"] == START and d["parts"][-1]["end"] == len(text)
    assert all(a["end"]==b["start"] for a,b in zip(d["parts"],d["parts"][1:]))
    for p in d["parts"]:
        assert hashlib.sha256(text[p["start"]:p["end"]].encode()).hexdigest()==p["sha256"]
    return d,text


def submit(d,text):
    assert not any(p["state"] in {"submitting","submission_unknown"} for p in d["parts"])
    credits=engine.tts.algrow_credits()
    d.setdefault("credits_before",credits)
    pending=[p for p in d["parts"] if p["state"]=="ready"]
    assert credits["tts_characters"]["remaining"]>=sum(p["characters"] for p in pending)
    engine.save(d)
    for p in pending:
        fields=engine.tts.algrow_fields(text[p["start"]:p["end"]],engine.VOICE,speed=.90,srt=False)
        fields["custom_title"]="Sleep 2026-10-25 - "+p["id"]
        p.update(state="submitting",attempted_at=engine.now())
        engine.save(d)
        try:
            response=engine.tts._algrow_call("POST","/api/generate-simple",fields,timeout=180)
        except Exception as exc:
            p.update(state="submission_unknown",error_private=str(exc))
            engine.save(d)
            raise
        p["submission_response"]=response
        if not response.get("job_id"):
            p["state"]="submission_unknown"
            engine.save(d)
            raise RuntimeError("Submission returned no job id; reconcile before any retry")
        p.update(state="submitted",job_id=response["job_id"],submitted_at=engine.now())
        engine.save(d)
        engine.emit("submitted",id=p["id"],characters=p["characters"],job_id=p["job_id"])
    d["credits_latest"]=engine.tts.algrow_credits()
    engine.save(d)


def monitor(d):
    while True:
        for p in d["parts"]:
            if p["state"] in {"submitted","poll_error","completed"}:
                try:
                    result=engine.tts._algrow_call("GET","/api/job-status/"+p["job_id"],timeout=60)
                    if result.get("status")!=p.get("remote_status"):
                        engine.emit("status",id=p["id"],status=result.get("status"))
                    p.update(last_response=result,last_poll=engine.now(),remote_status=result.get("status"))
                    if result.get("status")=="failed":
                        p.update(state="failed",failure=result.get("error"))
                    elif result.get("status")=="completed" and result.get("audio_url"):
                        engine.download(p,result)
                    else:
                        p["state"]="submitted"
                    engine.save(d)
                except Exception as exc:
                    p.update(state="poll_error",error_type=type(exc).__name__)
                    engine.save(d)
            if p["state"]=="downloaded":
                engine.verify(p)
                engine.save(d)
        if not any(p["state"] in {"submitted","poll_error","completed","downloaded"} for p in d["parts"]):
            break
        time.sleep(25)
    engine.emit("finished",states={p["id"]:p["state"] for p in d["parts"]})


def assemble(d,text):
    """Create a private candidate; publication into the delivery folder is separate."""
    assert all(p["state"]=="verified" for p in d["parts"])
    batch=json.loads((BATCH/"ledger.json").read_text(encoding="utf-8"))
    episode=next(x for x in batch["episodes"] if x["id"]==d["episode_id"])
    plan=json.loads((BATCH/"splice-plan.json").read_text(encoding="utf-8"))
    assert plan["source"]["replacement_start_char"]==START
    assert plan["source"]["sha256_LF"]==d["source_sha256"]
    assert len(episode["parts"])==2, "Reconcile an already repaired episode before assembling"
    first,old=episode["parts"]
    assert hashlib.file_digest(Path(old["audio_path"]).open("rb"),"sha256").hexdigest()==plan["audio"]["sha256"]
    assert hashlib.file_digest(Path(first["audio_path"]).open("rb"),"sha256").hexdigest()==first["audio_sha256"]
    original=Path(episode["audio_path"])
    assert hashlib.file_digest(original.open("rb"),"sha256").hexdigest()==d["original_final_sha256"]
    archive=engine.STATE/"archive"
    archive.mkdir(exist_ok=True)
    backup=archive/"09-QP-10-silo-outside-TRUNCATED-original.mp3"
    if not backup.exists():shutil.copy2(original,backup)
    assert hashlib.file_digest(backup.open("rb"),"sha256").hexdigest()==d["original_final_sha256"]
    cut=plan["splice"]["cut_seconds_in_part2"]
    trimmed=engine.STATE/"parts/QP-10-silo-outside-part2-preserved.mp3"
    if not trimmed.exists():
        engine.media.run(["-i",old["audio_path"],"-to",str(cut),"-map","0:a:0","-c:a","copy",str(trimmed)],timeout=300)
    kept={"id":"QP-10-silo-outside-part2-preserved","start":old["start"],"end":START,
          "characters":START-old["start"],"words":len(text[old["start"]:START].split()),
          "sha256":hashlib.sha256(text[old["start"]:START].encode()).hexdigest(),
          "audio_file":trimmed.name,"audio_path":str(trimmed),"audio_bytes":trimmed.stat().st_size,
          "audio_sha256":hashlib.file_digest(trimmed.open("rb"),"sha256").hexdigest(),
          "derived_from_job_id":old["job_id"],"retained_seconds":cut}
    engine.verify(kept)
    assert kept["state"]=="verified" and abs(kept["duration_seconds"]-cut)<.15
    newparts=[first,kept]+d["parts"]
    assert newparts[0]["start"]==0 and newparts[-1]["end"]==len(text)
    assert all(a["end"]==b["start"] for a,b in zip(newparts,newparts[1:]))
    listing=engine.STATE/"corrected-concat.txt"
    listing.write_text("".join("file '"+Path(p["audio_path"]).as_posix().replace("'","'\\''")+"'\n" for p in newparts),encoding="utf-8")
    candidate=engine.STATE/"QP-10-silo-outside-complete-candidate.mp3"
    engine.media.run(["-f","concat","-safe","0","-i",str(listing),"-c:a","copy","-y",str(candidate)],timeout=300)
    info={"id":episode["id"],"audio_path":str(candidate),"audio_bytes":candidate.stat().st_size,
          "audio_sha256":hashlib.file_digest(candidate.open("rb"),"sha256").hexdigest(),
          "source_sha256":d["source_sha256"],"parts":newparts,"original_backup":str(backup),
          "repair_join_seconds":first["duration_seconds"]+kept["duration_seconds"],
          "ending_part_join_seconds":first["duration_seconds"]+kept["duration_seconds"]+d["parts"][0]["duration_seconds"],
          "delivery_state":"awaiting_boundary_QA"}
    engine.verify(info,minimum=7200)
    info["duration_join_delta_seconds"]=round(info["duration_seconds"]-sum(p["duration_seconds"] for p in newparts),3)
    assert info["state"]=="verified" and abs(info["duration_join_delta_seconds"])<.2
    (engine.STATE/"candidate.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")
    engine.emit("candidate_ready",seconds=info["duration_seconds"],repair_join_seconds=info["repair_join_seconds"],audio_path=str(candidate))


def finalize(d):
    """Replace the delivered truncated file only after independent speech boundary QA."""
    info=json.loads((engine.STATE/"candidate.json").read_text(encoding="utf-8"))
    qa=json.loads((engine.STATE/"repair-qa.json").read_text(encoding="utf-8"))
    assert qa.get("passed") is True, "Independent boundary and join verification must pass"
    assert qa.get("candidate_audio_sha256")==info["audio_sha256"]
    candidate=Path(info["audio_path"])
    assert hashlib.file_digest(candidate.open("rb"),"sha256").hexdigest()==info["audio_sha256"]
    assert info["full_decode_passed"] and info["state"]=="verified"
    batch_lock=(BATCH/"executor.lock").open("r+b")
    msvcrt.locking(batch_lock.fileno(),msvcrt.LK_NBLCK,1)
    batch=json.loads((BATCH/"ledger.json").read_text(encoding="utf-8"))
    episode=next(x for x in batch["episodes"] if x["id"]==d["episode_id"])
    dest=Path(episode["audio_path"])
    present_hash=hashlib.file_digest(dest.open("rb"),"sha256").hexdigest()
    assert present_hash in {d["original_final_sha256"],info["audio_sha256"]}
    backup=BATCH/"ledger-before-silo-ending-repair.json"
    if not backup.exists():backup.write_text(json.dumps(batch,ensure_ascii=False,indent=2),encoding="utf-8")
    if present_hash!=info["audio_sha256"]:
        temp=dest.with_suffix(".corrected.partial.mp3")
        shutil.copy2(candidate,temp)
        assert hashlib.file_digest(temp.open("rb"),"sha256").hexdigest()==info["audio_sha256"]
        temp.replace(dest)
    if not episode.get("silo_ending_repaired"):
        episode.setdefault("repair_history",[]).append({
            "reason":"Original remote completed job was audibly truncated; missing suffix generated with user authorization.",
            "previous_audio_sha256":episode["audio_sha256"],"previous_duration_seconds":episode["duration_seconds"],
            "original_backup":info["original_backup"],"previous_parts":episode["parts"]})
    for key in ["audio_bytes","audio_sha256","duration_seconds","full_decode_passed","over_two_hours","duration_join_delta_seconds","parts"]:
        episode[key]=info[key]
    episode.update(state="verified",silo_ending_repaired=True,verified_at=engine.now(),
                   assembly="Preserved original first part and trimmed second part, followed by exact authorized suffix; no added silence or repeated source text.",
                   boundary_qa_path=str(engine.STATE/"repair-qa.json"))
    repair_state=engine.STATE
    try:
        engine.STATE=BATCH
        engine.save(batch)
    finally:
        engine.STATE=repair_state
    d.update(delivered_at=engine.now(),delivered_audio_sha256=info["audio_sha256"],delivered_audio_path=str(dest))
    engine.save(d)
    engine.emit("delivered",audio_path=str(dest),seconds=info["duration_seconds"],sha256=info["audio_sha256"])


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("action",choices=["plan","submit","monitor","status","assemble","finalize"])
    args=ap.parse_args()
    engine.STATE.mkdir(parents=True,exist_ok=True)
    if args.action!="status":
        lock=(engine.STATE/"executor.lock").open("a+b")
        if lock.seek(0,2)==0:
            lock.write(b"0");lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    d,text=load()
    if args.action in {"submit","monitor"}:
        from dotenv import dotenv_values
        os.environ["ALGROW_API_KEY"]=dotenv_values(ROOT/".env")["ALGROW_API_KEY"]
    if args.action=="submit":submit(d,text)
    elif args.action=="monitor":monitor(d)
    elif args.action=="assemble":assemble(d,text)
    elif args.action=="finalize":finalize(d)
    else:
        if args.action=="plan":engine.save(d)
        engine.emit(args.action,characters=d["characters"],parts=[{k:p[k] for k in ["id","state","characters","start","end"]} for p in d["parts"]])


if __name__=="__main__":main()
