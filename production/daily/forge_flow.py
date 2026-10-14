"""Pilote une vidéo TubeForge (VPS) étape par étape, depuis le cloud, sans jamais afficher d'accès.

    python production/daily/forge_flow.py create <channel_id> "<titre>" <script.txt> <clé>
    python production/daily/forge_flow.py run <video_id> voice|prepare|preview|images|render [--json body.json]
    python production/daily/forge_flow.py status <video_id>
    python production/daily/forge_flow.py shots <video_id> <dossier> [--ids 1,2,3]   # images + planches à regarder
    python production/daily/forge_flow.py review <video_id> <scene_id|all> "<constat réel>"
    python production/daily/forge_flow.py regen <video_id> 12,40,77                 # refait ces images
    python production/daily/forge_flow.py thumbs <video_id> [--count 4] [--instruction "..."]
    python production/daily/forge_flow.py download <video_id> <fichier.mp4>

Session : FORGE_SESSION_FILE (fichier privé hors du dépôt, créé par `forge.py login`).
`run` lance l'étape puis attend la fin en relisant l'état toutes les 10 s ; il ne relance jamais
une étape payante tout seul. Après une coupure : `status`, puis décider.
"""
import argparse
import http.client
import json
import sys
import time
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tubeforge_support" / "forge_docs"))
import forge  # noqa: E402

V1 = forge.BASE
NATIVE = forge.HOST + "/api/2d"
TEXT_MODEL = "gpt-6-sol"   # découpage en plans ; doit figurer dans GET /api/workspace/models


def api(method, url, body=None):
    """Appel au portail. Les lectures et les revues sont réessayées si le VPS coupe ; jamais une étape payante."""
    data = json.dumps(body).encode() if body is not None else None
    retry = method == "GET" or url.endswith("/review")
    for attempt in range(6 if retry else 1):
        try:
            with forge.request(method, url, data) as res:
                raw = res.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if retry and e.code in (502, 503, 504) and attempt < 5:
                time.sleep(10 * (attempt + 1))
                continue
            raise SystemExit(f"{e.code} sur {url.replace(forge.HOST, '')} : {e.read().decode('utf-8', 'replace')[:600]}")
        except (OSError, http.client.HTTPException) as e:
            if retry and attempt < 5:
                time.sleep(10 * (attempt + 1))
                continue
            raise SystemExit(f"connexion coupée sur {url.replace(forge.HOST, '')} : {e}")


def vid(video_id):
    return V1 + "/videos/" + urllib.parse.quote(video_id, safe="")


def status(video_id):
    return api("GET", vid(video_id) + "/status")


def summary(s):
    steps = {k: f"{v.get('state')} {v.get('done')}/{v.get('total')}" for k, v in (s.get("steps") or {}).items()
             if v.get("state") not in (None, "idle")}
    img = s.get("images") or {}
    return (f"{s.get('state')} running={s.get('running')} images {img.get('done')}/{img.get('total')} "
            f"échecs {img.get('failed')} | {steps} | erreur={s.get('error')}")


def wait(video_id, every=10, limit=4 * 3600):
    start, last = time.time(), ""
    time.sleep(5)
    while time.time() - start < limit:
        try:
            s = status(video_id)
        except (SystemExit, OSError) as e:   # VPS momentanément indisponible (502/503, coupure) : on relit plus tard
            if not str(e)[:3] in ("502", "503", "504") and not isinstance(e, OSError):
                raise
            time.sleep(every * 3)
            continue
        line = summary(s)
        if line != last:
            print(time.strftime("%H:%M:%S"), line, flush=True)
            last = line
        if not s.get("running") and s.get("state") != "running":
            return s
        time.sleep(every)
    raise SystemExit("délai dépassé : relire `status` avant toute relance")


def run(video_id, action, body):
    current = status(video_id)
    if current.get("running"):
        print("une étape tourne déjà : on attend sa fin sans rien relancer", flush=True)
    elif action == "voice" and (current.get("steps") or {}).get("voiceover", {}).get("state") == "done":
        print("voix déjà faite : réutilisée", flush=True)
    else:
        api("POST", vid(video_id) + "/actions/" + action, body or {})
    s = wait(video_id)
    if s.get("error") or s.get("state") in ("failed", "interrupted"):
        raise SystemExit(f"étape {action} : {s.get('state')} {s.get('error')}")
    return s


def native(path):
    """Adresse complète d'un média ou d'une route : /api/2d/… et /api/forge/… tels quels, le reste sous /api/2d."""
    if path.startswith("http"):
        return path
    if path.startswith(("/api/2d/", "/api/forge/")):
        return forge.HOST + path
    return NATIVE + path


def fetch(url, out):
    with forge.request("GET", native(url)) as res:
        out.write_bytes(res.read())


def shots(video_id, folder, ids=None):
    """Télécharge les images des plans et fait des planches de 12, avec le texte dit, pour les regarder."""
    from PIL import Image, ImageDraw, ImageFont
    p = api("GET", vid(video_id))
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    got = []
    for s in p.get("scenes") or []:
        if ids and s["id"] not in ids:
            continue
        url = s.get("image_url")
        if not url or not s.get("image_available"):
            continue
        out = folder / f"s{s['id']:03d}.png"
        if not out.exists():
            fetch(url, out)
        got.append((s, out))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for n in range(0, len(got), 12):
        sheet = Image.new("RGB", (3 * 640, 4 * 400), "white")
        draw = ImageDraw.Draw(sheet)
        for i, (s, path) in enumerate(got[n:n + 12]):
            x, y = (i % 3) * 640, (i // 3) * 400
            im = Image.open(path).convert("RGB")
            im.thumbnail((640, 360))
            sheet.paste(im, (x, y))
            label = f"#{s['id']} {','.join(s.get('characters') or [])} | {(s.get('text') or '')[:70]}"
            draw.text((x + 4, y + 362), label, fill="black", font=font)
        sheet.save(folder / f"sheet_{n // 12 + 1:02d}.jpg", quality=85)
    print(f"{len(got)} images, {(len(got) + 11) // 12} planches dans {folder}")


def review(video_id, scene, notes):
    p = api("GET", vid(video_id))
    ids = [s["id"] for s in p.get("scenes") or []] if scene == "all" else [int(x) for x in scene.split(",")]
    for i in ids:
        api("POST", vid(video_id) + "/review", {"scope": "scene", "scene_id": i, "state": "verified",
                                                "reviewer": "Claude (cloud)", "source": "delegated_ai_inspection",
                                                "notes": notes})
    print(f"{len(ids)} revues enregistrées")


def regen(video_id, ids):
    """Refait les images ratées, une par une, avec leur prompt exact et le modèle figé du projet."""
    p = api("GET", vid(video_id))
    snap = p.get("model_snapshot") or {}
    scenes = {s["id"]: s for s in p.get("scenes") or []}
    url = NATIVE + f"/api/workspace/projects/{urllib.parse.quote(video_id, safe='')}/scenes/%d/generate"

    def one(i):
        body = {"confirm_prompt": scenes[i]["prompt"], "image_model": snap.get("image_model"),
                "image_provider": snap.get("image_provider", "cli_proxy")}
        try:
            api("POST", url % i, body)
            return i, "ok"
        except SystemExit as e:
            return i, str(e)[:120]

    # Le VPS n'accepte qu'une génération à la fois par projet : on les enchaîne, en réessayant si occupé.
    for i in ids:
        for attempt in range(30):
            _, r = one(i)
            if not r.startswith("409") or "in progress" not in r and "generation" not in r.lower():
                break
            time.sleep(10)
        print(f"#{i} {r}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--ids")
    ap.add_argument("--count", type=int, default=4)
    ap.add_argument("--instruction", default="")
    a = ap.parse_args()
    if a.cmd == "create":
        # Passe par un lot natif d'une vidéo : la création simple (v1) refuse tant que le modèle de texte par
        # défaut du serveur n'est plus au catalogue. Le lot permet de choisir un modèle qui y est.
        channel, title, script, key = a.args
        r = api("POST", NATIVE + "/api/workspace/batches", {
            "name": key, "text_model": TEXT_MODEL,
            "rows": [{"channel_id": channel, "title": title, "mode": "review",
                      "custom_script": Path(script).read_text(encoding="utf-8-sig")}]})
        print(r["projects"][0]["id"])
    elif a.cmd == "run":
        body = json.loads(a.json.read_text()) if a.json else {}
        s = run(a.args[0], a.args[1], body)
        print("terminé :", summary(s))
    elif a.cmd == "status":
        print(summary(status(a.args[0])))
    elif a.cmd == "shots":
        shots(a.args[0], a.args[1], [int(x) for x in a.ids.split(",")] if a.ids else None)
    elif a.cmd == "review":
        review(*a.args)
    elif a.cmd == "regen":
        regen(a.args[0], [int(x) for x in a.args[1].split(",")])
    elif a.cmd == "thumbs":
        api("POST", NATIVE + f"/api/projects/{urllib.parse.quote(a.args[0], safe='')}/thumbnails",
            {"count": a.count, "instruction": a.instruction})
        print("miniatures lancées")
    elif a.cmd == "download":
        with forge.request("GET", vid(a.args[0]) + "/download?kind=video") as res, open(a.args[1], "wb") as out:
            while chunk := res.read(1 << 20):
                out.write(chunk)
        print("téléchargé :", a.args[1])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
