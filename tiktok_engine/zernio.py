"""Publication TikTok d'Octave Histoire par Zernio (appli validée par TikTok : posts publics, programmés).

    python tiktok_engine/zernio.py accounts                    # comptes connectés (vérifie la clé)
    python tiktok_engine/zernio.py creator-info                # réglages permis par le compte TikTok
    python tiktok_engine/zernio.py schedule <dossier> --at 2026-10-10T07:00 [--cover 1]
    python tiktok_engine/zernio.py posts                       # posts programmés ou publiés

<dossier> = dossier de rendu de build.py (video.mp4, description.txt, covers/). L'heure est en
heure de Bruxelles. Clé : ZERNIO_API_KEY (variable d'environnement ou .env), jamais dans le code.
Chaque envoi est noté dans <dossier>/zernio.json : relancer ne programme jamais deux fois.
Testé le 9 oct. 2026 : clé, compte octave.histoire (seul niveau permis : PUBLIC_TO_EVERYONE), envoi du
fichier et création du post programmé. --draft n'est PAS fiable : le post d'essai est resté
« scheduled / public » (supprimé avant l'heure). Ne pas s'en servir pour un test.
"""
import argparse
import glob
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASE = "https://zernio.com/api/v1"
TZ = "Europe/Brussels"


def key():
    value = os.environ.get("ZERNIO_API_KEY")
    if not value and os.path.exists(os.path.join(ROOT, ".env")):
        for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
            if line.startswith("ZERNIO_API_KEY="):
                value = line.split("=", 1)[1].strip()
    if not value:
        raise SystemExit("ZERNIO_API_KEY absente (variables d'environnement ou .env)")
    return value


def api(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + key(), "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Zernio {e.code} sur {path} : {e.read().decode('utf-8', 'replace')[:500]}")


def tiktok_account():
    accounts = [a for a in api("GET", "/accounts").get("accounts", []) if a.get("platform") == "tiktok"]
    if len(accounts) != 1:
        raise SystemExit(f"{len(accounts)} compte(s) TikTok connecté(s) dans Zernio : il en faut exactement un")
    return accounts[0]


def upload(path, content_type):
    """Envoie un fichier local chez Zernio et rend son adresse publique (valable 7 jours pour un post)."""
    size = os.path.getsize(path)
    pre = api("POST", "/media/presign", {"filename": os.path.basename(path), "contentType": content_type,
                                          "size": size})
    with open(path, "rb") as f:
        req = urllib.request.Request(pre["uploadUrl"], data=f.read(), method="PUT",
                                     headers={"Content-Type": content_type})
    urllib.request.urlopen(req, timeout=900).read()
    return pre["publicUrl"]


def settings(account_id, draft=False):
    info = api("GET", f"/accounts/{account_id}/tiktok/creator-info?mediaType=video")
    if not (info.get("creator") or {}).get("canPostMore", True):
        raise SystemExit("TikTok refuse un post de plus pour l'instant (limite atteinte) : réessayer plus tard")
    levels = [p["value"] for p in info.get("privacyLevels", [])]
    if "PUBLIC_TO_EVERYONE" not in levels and not draft:
        raise SystemExit(f"Le compte ne permet pas un post public : {levels}")
    inter = (info.get("postingLimits") or {}).get("interactionSettings") or {}
    allowed = lambda k: (inter.get(k) or {}).get("enabled", True) is not False
    return {
        "privacy_level": "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in levels else levels[0],
        "allow_comment": allowed("allow_comment"),
        "allow_duet": allowed("allow_duet"),
        "allow_stitch": allowed("allow_stitch"),
        "content_preview_confirmed": True,
        "express_consent_given": True,
        # Images et voix faites par IA : TikTok demande de le signaler.
        "video_made_with_ai": True,
        "draft": draft,
    }


def schedule(folder, at, cover=1, draft=False):
    folder = os.path.abspath(folder)
    record = os.path.join(folder, "zernio.json")
    if os.path.exists(record):
        done = json.load(open(record, encoding="utf-8"))
        print(f"déjà programmée : {done['post_id']} pour {done['at']} ({done['status']})")
        return done
    video = os.path.join(folder, "video.mp4")
    caption = open(os.path.join(folder, "description.txt"), encoding="utf-8").read().strip()
    covers = sorted(glob.glob(os.path.join(folder, "covers", "*.png")))
    account = tiktok_account()
    tiktok = settings(account["_id"], draft)
    if covers:
        tiktok["video_cover_image_url"] = upload(covers[min(cover, len(covers)) - 1], "image/png")
    url = upload(video, "video/mp4")
    body = {
        "content": caption,
        "mediaItems": [{"type": "video", "url": url}],
        "platforms": [{"platform": "tiktok", "accountId": account["_id"]}],
        "tiktokSettings": tiktok,
        "scheduledFor": at,
        "timezone": TZ,
    }
    post = api("POST", "/posts", body).get("post") or {}
    done = {"post_id": post.get("_id"), "status": post.get("status"), "at": at, "timezone": TZ,
            "account": account.get("username"), "draft": draft}
    json.dump(done, open(record, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"programmée : {done['post_id']} pour {at} ({TZ}), statut {done['status']}")
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["accounts", "creator-info", "schedule", "posts"])
    ap.add_argument("folder", nargs="?")
    ap.add_argument("--at", help="heure de Bruxelles, ex. 2026-10-10T07:00")
    ap.add_argument("--cover", type=int, default=1, help="numéro de la miniature (covers/, 1 = la 1re)")
    ap.add_argument("--draft", action="store_true", help="dans la boîte de réception TikTok, sans publier")
    a = ap.parse_args()
    if a.cmd == "accounts":
        for acc in api("GET", "/accounts").get("accounts", []):
            print(acc.get("platform"), acc.get("username"), acc.get("_id"), "actif" if acc.get("isActive") else "inactif")
    elif a.cmd == "creator-info":
        print(json.dumps(api("GET", f"/accounts/{tiktok_account()['_id']}/tiktok/creator-info?mediaType=video"),
                         ensure_ascii=False, indent=2))
    elif a.cmd == "posts":
        print(json.dumps(api("GET", "/posts"), ensure_ascii=False, indent=2)[:6000])
    else:
        if not (a.folder and a.at):
            raise SystemExit("schedule <dossier> --at AAAA-MM-JJTHH:MM")
        schedule(a.folder, a.at, a.cover, a.draft)


if __name__ == "__main__":
    sys.exit(main())
