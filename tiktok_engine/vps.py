"""Render reviewed TikToks through the existing authenticated VPS worker.

    python tiktok_engine/vps.py status
    python tiktok_engine/vps.py submit <slug> [<second_slug>]
    python tiktok_engine/vps.py collect <job_name>

This tool renders and retrieves files only. It never generates or publishes content.
"""
import argparse
import base64
import binascii
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
from urllib.parse import urlsplit
import uuid

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MAX_BUNDLE = 9 * 1024 * 1024
SLUG = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*\Z")
JOB = re.compile(r"tiktok-[a-z0-9][a-z0-9-]{0,70}\Z")
ENGINE_FILES = ("render.mjs", "engine.js", "sprites.js", "engine.html")


class RenderError(Exception):
    pass


def valid_slug(value):
    if not isinstance(value, str) or not SLUG.fullmatch(value) or len(value) > 100:
        raise RenderError("Nom de vidéo invalide")
    return value


def valid_job(value):
    if not isinstance(value, str) or not JOB.fullmatch(value):
        raise RenderError("Nom de job TikTok invalide")
    return value


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RenderError(f"Fichier JSON absent ou invalide : {path.name}") from None


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def file_bytes(path, root):
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise RenderError(f"Entrée absente ou hors du projet : {path.name}")
    data = path.read_bytes()
    if not data:
        raise RenderError(f"Entrée vide : {path.name}")
    return data


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Worker:
    def __init__(self):
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
        self.url = os.environ.get("NEWS_WORKER_URL", "").rstrip("/")
        token = os.environ.get("NEWS_WORKER_TOKEN", "")
        parsed = urlsplit(self.url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RenderError("NEWS_WORKER_URL doit être une adresse HTTPS sans identifiants ni paramètres")
        if not token:
            raise RenderError("NEWS_WORKER_TOKEN absent de l’environnement et du .env local")
        self.session = requests.Session()  # Keep the inherited proxy, CA and credentials.
        self.session.headers["X-Worker-Token"] = token

    def request(self, method, path, **kwargs):
        try:
            response = self.session.request(method, self.url + path, allow_redirects=False, **kwargs)
        except requests.RequestException as exc:
            raise RenderError(f"Requête VPS interrompue ({type(exc).__name__}) ; vérifier le statut avant de redéposer") from None
        if not 200 <= response.status_code < 300:
            suffix = "; réduire le lot à une vidéo, sans changer les identifiants" if response.status_code == 401 and method == "PUT" else ""
            raise RenderError(f"VPS : HTTP {response.status_code}{suffix}")
        return response

    def status(self):
        try:
            value = self.request("GET", "/status", timeout=25).json()
        except ValueError:
            raise RenderError("Statut VPS invalide") from None
        if not isinstance(value, dict) or not isinstance(value.get("busy"), bool):
            raise RenderError("Statut VPS invalide")
        return value


def ffmpeg_exe():
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def make_flac(work):
    path = work / "mix.flac"
    try:
        subprocess.run([ffmpeg_exe(), "-v", "error", "-y", "-i", str(work / "mix.wav"),
                        "-c:a", "flac", str(path)], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        raise RenderError(f"Conversion FLAC impossible : {work.name}") from None
    return path


def make_bundle(slugs, root=ROOT):
    if not 1 <= len(slugs) <= 2 or len(set(slugs)) != len(slugs):
        raise RenderError("Déposer une ou deux vidéos différentes par lot")
    entries, inputs = {}, {}
    engine = root / "tiktok_engine"
    entries["code/production/news.py"] = file_bytes(engine / "vps_render_job.py", root)
    render_inputs = [engine / "vps_render_job.py"]
    for name in ENGINE_FILES:
        entries["code/tiktok_engine/" + name] = file_bytes(engine / name, root)
        render_inputs.append(engine / name)
    fonts = sorted((engine / "fonts").glob("*.ttf"))
    if not fonts:
        raise RenderError("Polices du moteur absentes")
    for path in fonts + sorted((engine / "fonts").glob("OFL-*.txt")):
        entries["code/tiktok_engine/fonts/" + path.name] = file_bytes(path, root)
        render_inputs.append(path)
    for slug in slugs:
        valid_slug(slug)
        work, video = root / "work/tiktok" / slug, engine / "videos" / slug
        file_bytes(work / "QA.json", root)
        qa = read_json(work / "QA.json")
        if not isinstance(qa, dict) or qa.get("approved") is not True:
            raise RenderError(f"Relecture visuelle non approuvée : {slug}")
        spec = read_json(work / "timeline.json")
        if not isinstance(spec, dict):
            raise RenderError(f"Timeline invalide : {slug}")
        duration = spec.get("duration")
        if (not isinstance(duration, (float, int)) or isinstance(duration, bool)
                or not math.isfinite(duration) or duration < 61 or spec.get("fps") != 30):
            raise RenderError(f"Timeline attendue à 30 images/s et au moins 61 secondes : {slug}")
        images = spec.get("images")
        if not isinstance(images, dict) or not images or not isinstance(spec.get("scenes"), list):
            raise RenderError(f"Images ou scènes manquantes : {slug}")
        for scene in spec["scenes"]:
            if not isinstance(scene, dict) or not isinstance(scene.get("els"), list):
                raise RenderError(f"Scène invalide : {slug}")
            for element in scene["els"]:
                if not isinstance(element, dict) or (element.get("type") == "img" and element.get("src") not in images):
                    raise RenderError(f"Élément visuel ou image manquante : {slug}")
        checked = render_inputs + [video / "script.json", work / "timeline.json", work / "mix.wav"]
        for key in images:
            valid_slug(key)
            path = video / "art" / (key + ".png")
            data = file_bytes(path, root)
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RenderError(f"Image PNG invalide : {slug}/{key}")
            entries[f"job/videos/{slug}/art/{key}.png"] = data
            checked.append(path)
        inputs[slug] = {str(path.relative_to(root)): sha256(file_bytes(path, root)) for path in checked}
        # Only images bundled above are served by the remote renderer.
        spec["images"] = {key: key + ".png" for key in images}
        entries[f"job/videos/{slug}/timeline.json"] = json.dumps(spec, ensure_ascii=False).encode("utf-8")
        entries[f"job/videos/{slug}/mix.flac"] = file_bytes(make_flac(work), root)
    entries["job/plan.json"] = json.dumps({"slugs": slugs, "inputs_sha256": inputs}).encode("utf-8")
    body = io.BytesIO()
    with tarfile.open(fileobj=body, mode="w:gz") as archive:
        for name, data in entries.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o644
            archive.addfile(info, io.BytesIO(data))
    payload = body.getvalue()
    if len(payload) > MAX_BUNDLE:
        raise RenderError(f"Lot de {len(payload)} octets supérieur à 9 Mio ; déposer les vidéos séparément")
    return payload, inputs


def receipt_path(name, root=ROOT):
    return root / "work/tiktok/vps" / (valid_job(name) + ".json")


def submit(worker, slugs, root=ROOT):
    if worker.status()["busy"]:
        raise RenderError("VPS occupé ; aucun job remplacé")
    payload, inputs = make_bundle(slugs, root)
    if worker.status()["busy"]:
        raise RenderError("VPS occupé ; aucun job remplacé")
    name = "tiktok-render-" + uuid.uuid4().hex[:12]
    path = receipt_path(name, root)
    receipt = {"job": name, "slugs": slugs, "inputs_sha256": inputs,
               "bundle_bytes": len(payload), "bundle_sha256": sha256(payload), "state": "prepared"}
    write_json(path, receipt)
    print(f"Job : {name} — {len(slugs)} vidéo(s), {len(payload)} octets", flush=True)
    try:
        worker.request("PUT", "/job", params={"name": name, "upload": "0"}, data=payload, timeout=180)
    except RenderError:
        receipt["state"] = "unconfirmed"
        write_json(path, receipt)
        raise
    receipt["state"] = "submitted"
    write_json(path, receipt)
    return name


def collect(worker, name, root=ROOT):
    path = receipt_path(name, root)
    receipt = read_json(path)
    if not isinstance(receipt, dict) or receipt.get("job") != name or not isinstance(receipt.get("inputs_sha256"), dict):
        raise RenderError("Reçu de dépôt invalide")
    expected = receipt.get("slugs", [])
    if not isinstance(expected, list) or not 1 <= len(expected) <= 2 or any(not isinstance(slug, str) for slug in expected) or len(set(expected)) != len(expected):
        raise RenderError("Vidéos du reçu invalides")
    for slug in expected:
        valid_slug(slug)
    status = worker.status()
    if status["busy"] and status.get("job") == name:
        raise RenderError("Ce lot est encore en cours de rendu")
    try:
        result = worker.request("GET", "/file", params={"name": name, "path": "result.json"}, timeout=300).json()
    except ValueError:
        raise RenderError("Résultat VPS invalide") from None
    if not isinstance(result, dict) or result.get("complete") is not True:
        raise RenderError("Résultat VPS incomplet ; réessayer la collecte après le rendu")
    videos = result.get("videos")
    if not isinstance(videos, dict) or set(videos) - set(expected):
        raise RenderError("Le résultat contient des vidéos non demandées")
    artifacts = []
    for slug, value in videos.items():
        valid_slug(slug)
        if not isinstance(value, dict) or value.get("inputs_sha256") != receipt["inputs_sha256"].get(slug):
            raise RenderError(f"Le résultat ne correspond pas aux entrées déposées : {slug}")
        for relative, digest in receipt["inputs_sha256"][slug].items():
            local = root / relative
            if sha256(file_bytes(local, root)) != digest:
                raise RenderError(f"Entrées modifiées depuis le dépôt : {slug} ; rendu conservé sur le VPS")
        try:
            raw = base64.b64decode(value["video_base64"], validate=True)
        except (KeyError, ValueError, TypeError, binascii.Error):
            raise RenderError(f"Transport vidéo invalide : {slug}") from None
        if (len(raw) != value.get("size") or hashlib.md5(raw).hexdigest() != value.get("md5")
                or sha256(raw) != value.get("sha256") or raw[4:8] != b"ftyp"):
            raise RenderError(f"Taille ou empreinte de la vidéo incorrecte : {slug}")
        work = root / "work/tiktok" / slug
        out = work / "video.mp4"
        if out.exists() and sha256(out.read_bytes()) != sha256(raw):
            raise RenderError(f"Un autre rendu existe déjà : {slug} ; l’archiver avant la collecte")
        artifacts.append((work, raw, {k: v for k, v in value.items() if k != "video_base64"}))
    # Validate every artifact before writing any output.
    for work, raw, metadata in artifacts:
        temporary = work / "video.mp4.tmp"
        temporary.write_bytes(raw)
        temporary.replace(work / "video.mp4")
        write_json(work / "render_receipt.json", dict(metadata, job=name, transport="authenticated worker result"))
        print(f"Récupéré et vérifié : {work.name} — {len(raw)} octets", flush=True)
    receipt["state"] = "collected" if set(videos) == set(expected) else "partial"
    receipt["results"] = {work.name: metadata for work, _, metadata in artifacts}
    receipt["failed_slugs"] = [slug for slug in expected if slug not in videos]
    write_json(path, receipt)
    if receipt["failed_slugs"]:
        raise RenderError("Rendus manquants : " + ", ".join(receipt["failed_slugs"]) + " ; consulter build.log sur le VPS")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="voir si le VPS existant est disponible")
    submit_parser = commands.add_parser("submit", help="rendre une ou deux vidéos déjà relues")
    submit_parser.add_argument("slugs", nargs="+")
    collect_parser = commands.add_parser("collect", help="récupérer un lot et vérifier ses fichiers")
    collect_parser.add_argument("job")
    args = parser.parse_args()
    try:
        worker = Worker()
        if args.command == "status":
            status = worker.status()
            print(json.dumps({key: status.get(key) for key in ("busy", "job", "stage")}, ensure_ascii=False))
        elif args.command == "submit":
            submit(worker, args.slugs)
        else:
            collect(worker, args.job)
    except (RenderError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
