"""Une étape de production sur un dossier vidéo (le log du dossier garde la trace, marqueurs « … DONE »).

  python production/steps.py script <folder>   # script FacelessOS + audit → script.txt   (AUDIT DONE)
  python production/steps.py check  <folder> [--apply]  # vérif FacelessOS du script.txt relu (verdict + fixes)
  python production/steps.py save   <folder>   # renvoie script.txt (relu/corrigé) dans le projet
  python production/steps.py prod   <folder>   # voix, persos, montage, images            (PROD DONE)
  python production/steps.py qa     <folder>   # contrôle en vision des images, refait les ratées (QA DONE)
  python production/steps.py replan <folder>   # refait le plan d'animations              (REPLAN DONE)
  python production/steps.py render <folder>   # métadonnées (meta.json) + rendu           (RENDER DONE)"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from common import Job, folder, pid_of
from services import pov_engine as E, pov_store as store, pov_script as S

step, d = sys.argv[1], folder(sys.argv[2])
pid = pid_of(d)
t = time.time()

if step == "script":
    E.job_script(Job(), pid)
    print("SCRIPT DONE", round(time.time() - t), "s", flush=True)
    E.job_audit(Job(), pid)
    pr = store.get_project(pid)
    open(os.path.join(d, "script.txt"), "w").write(pr["script"])
    print("AUDIT DONE", S.word_count(S.narration(pr["script"])), "words", round(time.time() - t), "s", flush=True)

elif step == "check":
    # vérif FacelessOS (greenlight : groupes A-E + scanner) du script.txt relu/corrigé à la main ; --apply applique
    # les fixes trouvés (retouches chirurgicales) et réécrit script.txt — toujours avant script_ok
    from services import facelessos as FOS
    pr = store.get_project(pid)
    ch = E.project_channel(pr)
    s = open(os.path.join(d, "script.txt")).read()
    parts = [(h, FOS.mech_fix(x)) for h, x in S.parse(s)]
    res = S.greenlight(ch, pr["title"], parts, minutes=pr.get("minutes"))
    print("FOS VERDICT", res.get("verdict"), len(res.get("fixes") or []), "fixes", res.get("scan"), flush=True)
    for f in res.get("fixes") or []:
        print(f" #{f['n']} [{f.get('check', '')}] part {f['part']}: {f.get('problem', '')}\n    quote: {f.get('quote', '')[:160]}"
              f"\n    fix: {f.get('fix', '')[:200]}", flush=True)
    if res.get("fixes") and "--apply" in sys.argv:
        parts = S.apply_fixes(ch, pr["title"], parts, res["fixes"])
        open(os.path.join(d, "script.txt"), "w").write(S.compose(parts))
        print("FOS FIXES APPLIED → script.txt", S.word_count(S.narration(S.compose(parts))), "words", flush=True)

elif step == "save":
    s = open(os.path.join(d, "script.txt")).read()
    store.update_project(pid, lambda x: x.__setitem__("script", s))
    print("SAVED", S.word_count(S.narration(s)), "words")

elif step == "prod":
    E.job_autopilot(Job(), pid, render_video=False)
    pr = store.get_project(pid)
    print("PROD DONE", len(pr["scenes"]), "scenes", sum(1 for s in pr["scenes"] if s.get("fx")), "fx",
          (pr.get("voice") or {}).get("duration"), "s voice", round(time.time() - t), "s", flush=True)

elif step == "qa":
    store.update_project(pid, lambda x: x.__setitem__("montage", dict(x.get("montage") or {}, image_qa=True)))
    pr = store.get_project(pid)
    pd = store.project_dir(pid)
    todo = [s for s in pr["scenes"] if s.get("image") and (s.get("fx") or {}).get("type") != "sheet"]
    faceless = E.faceless_object(E.project_channel(pr), pr)

    def check(s):
        try:
            ok, pb = E.check_image(os.path.join(pd, s["image"]), s, True, faceless)
        except Exception as e:  # noqa: BLE001  (contrôle indisponible : on garde l'image)
            return s["i"], True, [f"check failed: {e}"]
        return s["i"], ok, pb
    bad = []
    with ThreadPoolExecutor(8) as ex:
        for i, ok, pb in ex.map(check, todo):
            if not ok:
                bad.append(i)
                print("BAD", i, "; ".join(pb)[:220], flush=True)
    print("QA", len(todo), "checked,", len(bad), "to redo", flush=True)
    if bad:
        E.job_images(Job(), pid, only=bad)
    print("QA DONE", round(time.time() - t), "s", flush=True)

elif step == "replan":
    before = sum(1 for s in store.get_project(pid)["scenes"] if s.get("fx"))
    E.job_montage(Job(), pid)
    pr = store.get_project(pid)
    print("REPLAN DONE", before, "->", sum(1 for s in pr["scenes"] if s.get("fx")), "fx", flush=True)

elif step == "render":
    if not (store.get_project(pid).get("metadata") or {}).get("titles"):
        E.job_metadata(Job(), pid)
        print("META DONE", flush=True)
    md = dict(store.get_project(pid)["metadata"])
    md["chapters"] = E.chapters(store.get_project(pid))
    json.dump(md, open(os.path.join(d, "meta.json"), "w"), indent=1, ensure_ascii=False)
    E.job_render(Job(), pid)
    print("RENDER DONE", store.get_project(pid)["render"], round(time.time() - t), "s", flush=True)

else:
    raise SystemExit(__doc__)
