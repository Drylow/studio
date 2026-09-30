"""Oddly Specific Lives Studio — version autonome (double-clic sur « Lancer le studio »).

Ne contient que le studio de la chaîne et l'éditeur 2D Videos. Pas de mot de passe :
le serveur n'écoute que ce PC (127.0.0.1), personne d'autre ne peut s'y connecter.
"""
import os
import secrets
import sys

APP = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP)
sys.path.insert(0, APP)  # le Python embarqué n'ajoute pas le dossier du script tout seul
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(APP, ".env"))

from flask import Flask, abort, redirect, send_from_directory, session  # noqa: E402

from routes.pov import pov_bp  # noqa: E402

TOOLS = os.path.join(APP, "tool_apps")

app = Flask(__name__, static_folder=os.path.join(APP, "static"), static_url_path="/static")
app.secret_key = secrets.token_hex(24)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
app.json.sort_keys = False


@app.before_request
def _local_owner():
    # usage local uniquement : la personne devant ce PC est la propriétaire du studio
    session["role"] = "boss"
    session["unlocked"] = True


app.register_blueprint(pov_bp)


@app.route("/")
def home():
    return redirect("/toolfiles/osl-studio/index.html")


@app.route("/toolfiles/<path:rel>")
def toolfiles(rel):
    return send_from_directory(TOOLS, rel, max_age=0)


@app.route("/tools/<slug>")
def tool(slug):
    if not os.path.isfile(os.path.join(TOOLS, slug, "index.html")):
        abort(404)
    return redirect(f"/toolfiles/{slug}/index.html")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5057
    print(f"  Studio : http://127.0.0.1:{port}", flush=True)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)
