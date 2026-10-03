"""Zip de l'agent du PC de l'utilisateur (montage automatique des vidéos d'actu), à lui envoyer.

  python production/make_pc_agent.py [sortie.zip]      (défaut : $STUDIO_WORK/Drylow_Montage_Auto.zip)

Contient standalone/pc_agent/ + config.json (adresse et jeton du relais : NEWS_WORKER_URL / NEWS_WORKER_TOKEN du
.env). Le zip contient donc un secret : il va à l'utilisateur, jamais dans git."""
import json
import os
import sys
import zipfile

from common import REPO, WORK

SRC = os.path.join(REPO, "standalone", "pc_agent")
FILES = ["Installer.bat", "Desinstaller.bat", "installer.ps1", "pc_agent.py", "LISEZ-MOI.txt"]


def main():
    url = (os.environ.get("NEWS_WORKER_URL") or "").rstrip("/")
    tok = os.environ.get("NEWS_WORKER_TOKEN") or ""
    if not url or not tok:
        raise SystemExit("NEWS_WORKER_URL / NEWS_WORKER_TOKEN absents du .env")
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORK, "Drylow_Montage_Auto.zip")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(os.path.join(SRC, f), "Drylow Montage Auto/" + f)
        z.writestr("Drylow Montage Auto/config.json", json.dumps({"url": url, "token": tok}, indent=1))
    print(out)


if __name__ == "__main__":
    main()
