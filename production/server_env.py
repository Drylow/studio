"""Copie des variables du .env du serveur o2switch vers le .env local, sans jamais les afficher.

    python production/server_env.py ALGROW_API_KEY [AUTRE_NOM ...]

Pour une session cloud neuve à qui il manque une clé déjà configurée sur le site (ex. la clé Algrow,
dont l'utilisateur n'a pas la valeur). Lit le fichier par l'API cPanel (Fileman) avec CPANEL_URL,
CPANEL_USER et CPANEL_PASSWORD de l'environnement ; la session cPanel reste en mémoire. Le .env local
est ignoré par git et reçoit les droits 600. Seuls les noms demandés sont copiés.
"""
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE, HOST = "edgerunners.fr", "cpanel.edgerunners.fr"   # cPanel joint par son sous-domaine, port 443
CA = "/root/.ccr/ca-bundle.crt"


def opener():
    ctx = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else ssl.create_default_context()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))


def login(op):
    data = urllib.parse.urlencode({"user": os.environ["CPANEL_USER"], "pass": os.environ["CPANEL_PASSWORD"]}).encode()
    with op.open(urllib.request.Request(f"https://{SITE}/login/?login_only=1", data=data,
                                        headers={"Host": HOST}), timeout=30) as r:
        body = json.loads(r.read())
        cookie = "; ".join(h.split(";", 1)[0] for h in r.headers.get_all("Set-Cookie") or [])
    if body.get("status") != 1:
        raise SystemExit("connexion cPanel refusée")
    return body["security_token"], cookie


def server_env():
    op = opener()
    token, cookie = login(op)
    query = urllib.parse.urlencode({"dir": f"/home/{os.environ['CPANEL_USER']}/drylow_studio", "file": ".env"})
    with op.open(urllib.request.Request(f"https://{SITE}{token}/execute/Fileman/get_file_content?{query}",
                                        headers={"Host": HOST, "Cookie": cookie}), timeout=60) as r:
        body = json.loads(r.read())
    if not body.get("status"):
        raise SystemExit("lecture du .env du serveur refusée : " + str(body.get("errors"))[:200])
    values = {}
    for line in body["data"]["content"].splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def main(names):
    if not names:
        raise SystemExit(__doc__)
    missing = [n for n in names if not os.environ.get(n)]
    if not missing:
        print("déjà présentes :", ", ".join(names))
        return
    if not all(os.environ.get(k) for k in ("CPANEL_USER", "CPANEL_PASSWORD")):
        raise SystemExit("CPANEL_USER / CPANEL_PASSWORD absents de l'environnement")
    remote = server_env()
    path = os.path.join(ROOT, ".env")
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    got = []
    for n in missing:
        if remote.get(n):
            lines = [l for l in lines if not l.startswith(n + "=")] + [f"{n}={remote[n]}"]
            got.append(n)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)
    print("copiées dans .env :", ", ".join(got) or "aucune", "| absentes du serveur :",
          ", ".join(n for n in missing if n not in got) or "aucune")


if __name__ == "__main__":
    main(sys.argv[1:])
