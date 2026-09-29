"""Construit le dossier autonome « Oddly Specific Lives Studio » (double-clic sous Windows).

    python standalone/build_osl_package.py <dossier_de_sortie> [--no-env]

Copie uniquement ce qu'il faut au studio de la chaîne et à l'éditeur 2D Videos, plus les clés
utiles du .env (IA, Algrow) pour que tout marche sans rien remplir. Le Python et les modules
s'installent au premier lancement, dans le dossier (app\\runtime).
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "standalone", "osl")
ENV_KEYS = ("AI_BASE_URL", "AI_API_KEY", "AI_TEXT_MODEL", "AI_FAST_MODEL", "AI_IMAGE_MODEL", "AI_TEXT_FALLBACK",
            "AI_IMAGE_CONCURRENCY", "ALGROW_API_KEY", "FOS_MAX_ROUNDS", "ELEVENLABS_API_KEY", "OPENAI_API_KEY")
TREES = ("services", "tool_apps/osl-studio", "tool_apps/pov-studio", "static/fonts", "skills", "presets")
FILES = ("routes/__init__.py", "routes/pov.py", "requirements.txt")


def build(out, with_env=True):
    top = os.path.join(out, "Oddly Specific Lives Studio")
    app = os.path.join(top, "app")
    if os.path.isdir(top):
        shutil.rmtree(top)
    os.makedirs(app)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for t in TREES:
        shutil.copytree(os.path.join(ROOT, t), os.path.join(app, t), ignore=ignore)
    for f in FILES:
        os.makedirs(os.path.dirname(os.path.join(app, f)) or app, exist_ok=True)
        shutil.copy2(os.path.join(ROOT, f), os.path.join(app, f))
    for f in ("studio_app.py", "open_browser.py", "lancer.ps1"):
        shutil.copy2(os.path.join(HERE, f), os.path.join(app, f))
    for f in ("Lancer le studio.bat", "LISEZ-MOI.txt"):
        shutil.copy2(os.path.join(HERE, f), os.path.join(top, f))
    lines = ["# Clés du studio (reprises de ton .env). Ne partage pas ce fichier."]
    src = os.path.join(ROOT, ".env")
    if with_env and os.path.isfile(src):
        with open(src, encoding="utf-8") as fh:
            for ln in fh:
                k = ln.split("=", 1)[0].strip()
                if k in ENV_KEYS and "=" in ln:
                    lines.append(ln.rstrip("\n"))
    # images générées en parallèle : 12 (26 comptes derrière le proxy) → ~2 fois plus rapide qu'à 6
    lines = [ln for ln in lines if not ln.startswith("AI_IMAGE_CONCURRENCY=")] + ["AI_IMAGE_CONCURRENCY=12"]
    with open(os.path.join(app, ".env"), "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return top


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    print(build(args[0] if args else os.path.join(ROOT, "dist"), with_env="--no-env" not in sys.argv))
