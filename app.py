from flask import Flask, render_template, request, session, redirect, url_for, g
from werkzeug.middleware.proxy_fix import ProxyFix
from routes.access import access_bp, open_trusted_boss_session
from routes.surveillance import (
    surveillance_bp, get_device_id, parse_ua, client_ip,
    DEVICE_COOKIE, DEVICE_COOKIE_MAX_AGE,
)
from routes.tools import tools_bp
from routes.sync import sync_bp
from routes.fal import fal_bp
from routes.llm import llm_bp
from routes.delamain import delamain_bp
from routes.youtube import youtube_bp
from routes.lore import lore_bp
from routes.worker import worker_bp
from routes.pov import pov_bp
from routes.history import history_bp
from database import init_db, is_blacklisted, is_trusted_device, touch_trusted, log_access_event
import logging
import os
import sys
from dotenv import load_dotenv

# Sous Windows la console est en cp1252 : un print() contenant un emoji (✅, ❌…)
# lève UnicodeEncodeError et fait planter la requête en cours (500). On force
# stdout/stderr en UTF-8 pour que les logs ne cassent jamais une requête.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

app = Flask(__name__)

# --- Secret key ----------------------------------------------------------
_secret = os.getenv("FLASK_SECRET_KEY")
if not _secret:
    if os.getenv("FLASK_ENV") == "production":
        raise RuntimeError(
            "FLASK_SECRET_KEY is required in production. "
            "Set it in your hosting environment variables."
        )
    _secret = "dev-change-me"
app.secret_key = _secret

app.json.sort_keys = False

# --- Cookies session -----------------------------------------------------
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"]   = os.getenv("COOKIE_SECURE", "0") == "1"
# Durée de la session une fois déverrouillée (jours)
from datetime import timedelta
app.permanent_session_lifetime = timedelta(days=30)

# --- Upload size limit ---------------------------------------------------
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024

# --- Reverse proxy (o2switch, Cloudflare, nginx...) ---------------------
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# --- Logs ----------------------------------------------------------------
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- DB ------------------------------------------------------------------
init_db()

# --- Blueprints ----------------------------------------------------------
app.register_blueprint(access_bp)
app.register_blueprint(surveillance_bp)
app.register_blueprint(tools_bp)   # tools VPS (registre dans routes/tools.py)
app.register_blueprint(sync_bp)    # sauvegarde serveur du travail (sync multi-appareils)
app.register_blueprint(fal_bp)     # proxy Fal (Nano Banana 2) pour le Thumbnail Creator
app.register_blueprint(llm_bp)     # proxy LLM (cliwebproxy/Claude) pour Script + Title/Desc
app.register_blueprint(delamain_bp)  # mémoire permanente de Delamain (tableau de production)
app.register_blueprint(youtube_bp)   # connexion YouTube OAuth par projet (publication)
app.register_blueprint(lore_bp)      # pont vers le tool vidéo « Lore » (worker de rendu distant)
app.register_blueprint(worker_bp)    # worker autonome (produit + poste aux dates du calendrier)
app.register_blueprint(pov_bp)       # 2D Videos : script → voix → images → montage, 100 % local
app.register_blueprint(history_bp)   # Format Histoire : documentaire + animations Remotion (history_engine/)


# --- Gate global ---------------------------------------------------------
# Toute requête qui n'est pas sur une route publique est redirigée vers
# /unlock si la session n'est pas déverrouillée.
# /api/delamain/worker/tick : public au niveau de la grille (pour le CRON sans
# session) MAIS protégé à l'intérieur par WORKER_CRON_SECRET (cf. routes/worker.py).
PUBLIC_PREFIXES = ("/unlock", "/lock", "/static/", "/favicon.ico", "/api/delamain/worker/tick")
PUBLIC_EXACT    = {"/favicon.ico"}

# --- Clearance par rôle ---------------------------------------------------
# Les guests (collaborateurs) n'ont accès qu'à une partie de l'arsenal.
# /tools     = pages-cadres Night City des outils
# /toolfiles = fichiers statiques des outils (config.js avec les CLÉS API !)
# Les deux sont boss-only — c'est ce qui protège tes clés derrière le mdp.
BOSS_ONLY_PREFIXES = ("/surveillance", "/tools", "/toolfiles", "/category")
# Aucune API ouverte aux guests pour l'instant (le module projets a été retiré).
# → toute route /api/ est boss-only (cf. _is_boss_only).
GUEST_API_PREFIXES = ()

# --- Écran renvoyé aux appareils/IP blacklistés (aucun asset chargé) ------
_FLATLINE_HTML = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>CONNECTION TERMINATED</title>
<style>
  body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
       background:#050507;color:#FF3860;font-family:'Courier New',monospace;}
  .box{text-align:center;border:1px solid rgba(255,56,96,.4);padding:40px 56px;}
  h1{font-size:20px;letter-spacing:6px;margin:0 0 12px;text-shadow:0 0 12px rgba(255,56,96,.7);}
  p{font-size:11px;letter-spacing:3px;color:#6B7A99;margin:4px 0;}
</style></head><body><div class="box">
<h1>⚠ FLATLINED</h1>
<p>CONNECTION TERMINATED BY NETWATCH</p>
<p>// BLACK ICE ENGAGED — ACCESS PERMANENTLY DENIED //</p>
</div></body></html>"""


def _is_boss_only(path: str) -> bool:
    for prefix in BOSS_ONLY_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    if path.startswith("/api/"):
        return not any(path.startswith(p) for p in GUEST_API_PREFIXES)
    return False


_IS_PROD = os.getenv("FLASK_ENV") == "production"

# Note : la redirection HTTP→HTTPS est gérée par o2switch (cPanel → Domaines →
# « Forcer la redirection HTTPS »), PAS par l'app — car derrière le proxy
# o2switch, Flask ne voit pas toujours le bon protocole, ce qui provoquerait
# une boucle de redirection infinie. L'app se contente d'envoyer HSTS (plus bas).


@app.before_request
def _gate():
    path = request.path or "/"
    # Assets statiques + favicon : servis sans toucher la DB. Un appareil banni
    # n'en récupère que des fichiers inertes (aucune donnée), et ça évite une
    # requête SQLite blacklist sur CHAQUE asset d'une page.
    if path == "/favicon.ico" or path.startswith("/static/"):
        return None
    # Mur blacklist : un appareil/IP banni ne voit RIEN, même pas /unlock.
    device_id = get_device_id()
    ip = client_ip()  # gardé pour le journal uniquement (jamais pour décider l'accès)
    if is_blacklisted(device_id):
        try:
            ua = request.headers.get("User-Agent", "")
            browser, os_name = parse_ua(ua)
            log_access_event("blocked", ip=ip, device_id=device_id,
                             browser=browser, os_name=os_name,
                             user_agent=ua[:300], path=path)
        except Exception:
            pass
        session.clear()
        return _FLATLINE_HTML, 403
    # Routes publiques restantes : /unlock, /lock
    if path in PUBLIC_EXACT:
        return None
    # Matching avec FRONTIÈRE : "/lock" ne doit PAS rendre "/lockdown" public.
    # On accepte le chemin exact, ou un vrai sous-chemin (préfixe + "/").
    for prefix in PUBLIC_PREFIXES:
        p = prefix.rstrip("/")
        if path == p or path.startswith(p + "/"):
            return None
    wants_json = (
        path.startswith("/api/")
        or "application/json" in (request.headers.get("Accept") or "")
    )
    # Tout le reste nécessite d'être déverrouillé
    if not session.get("unlocked"):
        # Appareil/IP de confiance (whitelist SURVEILLANCE) → ouverture boss
        # automatique, sans mot de passe. C'est ce qui évite au boss de se
        # reconnecter. Les guests ne sont jamais whitelistés.
        if is_trusted_device(device_id):
            open_trusted_boss_session()
            touch_trusted(device_id)
            try:
                ua = request.headers.get("User-Agent", "")
                browser, os_name = parse_ua(ua)
                log_access_event("unlock_trusted", clearance="root", ip=ip,
                                 device_id=device_id, browser=browser, os_name=os_name,
                                 user_agent=ua[:300], path=path)
            except Exception:
                pass
        elif wants_json:
            from flask import jsonify
            return jsonify({"error": "locked", "redirect": url_for("access.unlock")}), 401
        else:
            return redirect(url_for("access.unlock"))
    # Clearance insuffisante : guest sur une zone boss-only
    if session.get("role") != "boss" and _is_boss_only(path):
        if wants_json:
            from flask import jsonify
            return jsonify({"error": "clearance", "message": "ROOT ACCESS REQUIRED"}), 403
        return redirect(url_for("home"))
    return None


@app.context_processor
def _inject_clearance():
    # Tous les templates (y compris les futurs tools) connaissent le rôle
    # sans que chaque route ait à le passer à render_template.
    role = session.get("role", "guest")
    return {"role": role, "is_boss": role == "boss"}


@app.after_request
def _device_cookie(resp):
    # Pose l'empreinte appareil (cookie longue durée) si elle vient d'être créée
    if getattr(g, "_device_new", False):
        resp.set_cookie(
            DEVICE_COOKIE, g._device_id,
            max_age=DEVICE_COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
            secure=app.config["SESSION_COOKIE_SECURE"],
        )
    return resp


@app.after_request
def _security_headers(resp):
    # En-têtes de sécurité de base. X-Frame-Options = SAMEORIGIN (PAS DENY) :
    # le site s'iframe lui-même (/toolfiles dans tool_frame), il faut donc
    # autoriser le cadrage interne tout en bloquant les sites tiers.
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # HSTS : en prod uniquement (sinon on forcerait HTTPS sur le localhost de dev).
    # Force les navigateurs à n'utiliser QUE le HTTPS pour edgerunners.fr pendant 1 an.
    if _IS_PROD:
        resp.headers.setdefault("Strict-Transport-Security",
                                "max-age=31536000; includeSubDomains")
    return resp


@app.route("/")
def home():
    # Le gate global a déjà vérifié que la session est unlocked
    return render_template(
        "index.html",
        active_page="home",
        user_name=session.get("user_name"),
        role=session.get("role", "guest"),
    )


@app.route('/favicon.ico')
def favicon():
    return '', 204


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_ENV") != "production")
