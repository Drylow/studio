"""
Accès global au site via mot de passe — DEUX niveaux de clearance.

- GET  /unlock    → affiche le gate Edgerunners
- POST /unlock    → vérifie le password, ouvre la session
                    · clearance "guest" (défaut) → ACCESS_PASSWORD  → rôle "guest"
                    · clearance "root" (panneau caché) → BOSS_PASSWORD → rôle "boss"
- POST /lock      → ferme la session (retour au gate)
- GET  /lock      → idem (pour <a href>)

Le rôle est stocké dans session["role"] et exploité par le gate global
de app.py (certains tools sont réservés au boss).
"""

import os
import time
import hmac
from flask import Blueprint, render_template, request, redirect, session, url_for
from database import log_access_event, recent_failed_unlocks
from routes.surveillance import get_device_id, parse_ua, client_ip

access_bp = Blueprint("access", __name__)

# Anti-bruteforce : au-delà de LOCK_THRESHOLD échecs sur LOCK_WINDOW_MIN minutes
# (même appareil OU même IP), le gate se verrouille temporairement.
LOCK_THRESHOLD = 8
LOCK_WINDOW_MIN = 10


def _log_attempt(event: str, clearance: str):
    """Journalise une tentative sur le gate (panneau SURVEILLANCE du boss)."""
    try:
        ua = request.headers.get("User-Agent", "")
        browser, os_name = parse_ua(ua)
        log_access_event(
            event,
            clearance=clearance,
            ip=client_ip(),
            device_id=get_device_id(),
            browser=browser,
            os_name=os_name,
            user_agent=ua[:300],
            path="/unlock",
        )
    except Exception:
        # Le journal ne doit jamais empêcher la connexion
        pass

# Mots de passe : UNIQUEMENT via env vars (aucun fallback en dur dans le code).
# Lus à CHAQUE requête (et pas à l'import) : ce module est importé avant que
# load_dotenv() de app.py ne charge le .env.
# ACCESS_PASSWORD → accès "guest" (collaborateurs, tools limités)
# BOSS_PASSWORD   → accès "boss"  (tout l'arsenal)
def _guest_password() -> str:
    return os.getenv("ACCESS_PASSWORD", "")


def _boss_password() -> str:
    return os.getenv("BOSS_PASSWORD", "")


def _open_session(role: str):
    session.clear()
    session["unlocked"]  = True
    session["role"]      = role
    # Pool de projets PARTAGÉ : boss et guests travaillent sur le même espace
    # (identité "V_NIGHT_CITY", cf. migration dans database.init_db). C'est ce
    # qui garde les projets visibles après un restart serveur / un redéploiement.
    # Le rôle (boss/guest) reste distinct et gère les droits (tools, surveillance).
    session["user_id"]   = "V_NIGHT_CITY"
    session["user_name"] = "DRYLOW" if role == "boss" else "EDGERUNNER"
    # Boss : session persistante (30 j, cf. app.py) → reste connecté.
    # Guest : cookie de session → meurt à la fermeture du navigateur, doit
    # se reconnecter à chaque visite.
    session.permanent = (role == "boss")


def open_trusted_boss_session():
    """Ouvre une session boss SANS mot de passe — réservé aux appareils/IP
    whitelistés dans SURVEILLANCE (vérifié par le gate d'app.py)."""
    _open_session("boss")


@access_bp.route("/unlock", methods=["GET", "POST"])
def unlock():
    if session.get("unlocked"):
        return redirect(url_for("home"))

    error = None
    root_mode = False

    if request.method == "POST":
        pwd = (request.form.get("password") or "").strip()
        clearance = (request.form.get("clearance") or "guest").strip()
        root_mode = clearance == "root"

        # Anti-bruteforce : trop d'échecs récents → verrou temporaire, on ne
        # vérifie même pas le mot de passe (et on ralentit la réponse).
        if recent_failed_unlocks(get_device_id(), client_ip(), LOCK_WINDOW_MIN) >= LOCK_THRESHOLD:
            _log_attempt("unlock_locked", clearance)
            time.sleep(2.0)
            error = "ACCÈS VERROUILLÉ // TROP DE TENTATIVES — RÉESSAIE DANS QUELQUES MINUTES"
            return render_template("unlock.html", error=error, root_mode=root_mode), 429

        expected = _boss_password() if root_mode else _guest_password()

        # Si le password attendu n'est pas configuré côté serveur, on refuse
        # tout — évite qu'un déploiement sans .env laisse le site ouvert.
        if not expected:
            _log_attempt("unlock_fail", clearance)
            time.sleep(1.2)
            error = "ACCÈS REFUSÉ // TERMINAL NON CONFIGURÉ"
            return render_template("unlock.html", error=error, root_mode=root_mode)

        # hmac.compare_digest évite les timing-attacks
        if hmac.compare_digest(pwd, expected):
            _open_session("boss" if root_mode else "guest")
            _log_attempt("unlock_ok", clearance)
            return redirect(url_for("home"))

        # Mauvais password : on ralentit (anti-bruteforce basique)
        _log_attempt("unlock_fail", clearance)
        time.sleep(1.2)
        error = "ACCÈS REFUSÉ // SIGNATURE INVALIDE"

    return render_template("unlock.html", error=error, root_mode=root_mode)


@access_bp.route("/lock", methods=["GET", "POST"])
def lock():
    session.clear()
    return redirect(url_for("access.unlock"))


# Fallback pour tout code qui tenterait encore /login ou /logout
@access_bp.route("/login", methods=["GET", "POST"])
def legacy_login():
    return redirect(url_for("access.unlock"))


@access_bp.route("/logout", methods=["GET", "POST"])
def legacy_logout():
    session.clear()
    return redirect(url_for("access.unlock"))
