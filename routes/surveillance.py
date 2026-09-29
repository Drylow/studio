"""
SURVEILLANCE // BLACK ICE — réservé au boss (mode root).

- Chaque tentative sur le gate (réussie, ratée, ou bloquée) est journalisée :
  IP, empreinte appareil (cookie), navigateur, OS, horodatage.
- Le boss peut blacklister un appareil ou une IP : l'appareil banni ne voit
  même plus la page de mot de passe (écran FLATLINED, enforce dans app.py).

L'empreinte appareil est un cookie aléatoire longue durée (nc_device) posé
sur tous les visiteurs du site — il identifie le navigateur, pas la personne.
"""

import re
import uuid
from flask import Blueprint, render_template, request, jsonify, session, g
from database import (
    list_access_events, access_stats,
    add_blacklist, remove_blacklist, list_blacklist,
    add_trusted, remove_trusted, list_trusted, purge_keep_only,
)

surveillance_bp = Blueprint("surveillance", __name__)

DEVICE_COOKIE = "nc_device"
DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 730  # 2 ans


def get_device_id() -> str:
    """Empreinte de l'appareil courant (générée si absente, posée en cookie
    par le after_request d'app.py)."""
    did = getattr(g, "_device_id", None)
    if did:
        return did
    did = (request.cookies.get(DEVICE_COOKIE) or "").strip()
    if not re.fullmatch(r"[0-9a-f]{32}", did):
        did = uuid.uuid4().hex
        g._device_new = True
    g._device_id = did
    return did


def parse_ua(ua: str):
    """Détection simple navigateur + OS depuis le User-Agent."""
    u = (ua or "").lower()
    if "edg/" in u or "edge/" in u:
        browser = "Edge"
    elif "opr/" in u or "opera" in u:
        browser = "Opera"
    elif "samsungbrowser" in u:
        browser = "Samsung Internet"
    elif "firefox" in u or "fxios" in u:
        browser = "Firefox"
    elif "chrome" in u or "crios" in u:
        browser = "Chrome"
    elif "safari" in u:
        browser = "Safari"
    elif not u:
        browser = "?"
    else:
        browser = "Autre"

    if "windows" in u:
        os_name = "Windows"
    elif "android" in u:
        os_name = "Android"
    elif "iphone" in u or "ipad" in u or "ios" in u:
        os_name = "iOS"
    elif "mac os" in u or "macintosh" in u:
        os_name = "macOS"
    elif "linux" in u:
        os_name = "Linux"
    elif not u:
        os_name = "?"
    else:
        os_name = "Autre"
    return browser, os_name


def client_ip() -> str:
    # ProxyFix (app.py) résout déjà X-Forwarded-For derrière o2switch
    return request.remote_addr or ""


# ── PAGE (boss-only via BOSS_ONLY_PREFIXES dans app.py) ─────────────────────
@surveillance_bp.route("/surveillance")
def surveillance_page():
    return render_template(
        "surveillance.html",
        active_page="surveillance",
        user_name=session.get("user_name"),
        role=session.get("role", "guest"),
        my_device=get_device_id(),
        my_ip=client_ip(),
    )


# ── API : flux + stats + blacklist (boss-only via le gate /api/) ────────────
@surveillance_bp.route("/api/surveillance/feed", methods=["GET"])
def api_feed():
    return jsonify({
        "events": list_access_events(limit=300),
        "blacklist": list_blacklist(),
        "trusted": list_trusted(),
        "stats": access_stats(),
        "me": {"device_id": get_device_id(), "ip": client_ip()},
    })


@surveillance_bp.route("/api/surveillance/blacklist", methods=["POST"])
def api_blacklist_add():
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip()
    value = (data.get("value") or "").strip()
    note = (data.get("note") or "").strip()[:200]
    # On ne bannit QUE des appareils (cookie secret). L'IP n'est plus utilisée
    # (proxies AdsPower → IP changeante, un ban IP serait inutile/dangereux).
    if kind != "device" or not value:
        return jsonify({"error": "Seul un appareil (kind='device') peut être banni. "
                                 "L'IP n'est plus utilisée."}), 400
    # Garde-fou : impossible de se bannir soi-même.
    if value == get_device_id():
        return jsonify({"error": "REFUSÉ // tu ne peux pas bannir ton propre appareil."}), 400
    add_blacklist(kind, value, note)
    return jsonify({"ok": True})


@surveillance_bp.route("/api/surveillance/blacklist", methods=["DELETE"])
def api_blacklist_remove():
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip()
    value = (data.get("value") or "").strip()
    if kind not in ("device", "ip") or not value:
        return jsonify({"error": "kind ('device'|'ip') et value requis"}), 400
    remove_blacklist(kind, value)
    return jsonify({"ok": True})


# ── Whitelist : appareils de confiance (ouverture boss auto, sans mot de passe) ─
@surveillance_bp.route("/api/surveillance/trust", methods=["POST"])
def api_trust_add():
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip()
    value = (data.get("value") or "").strip()
    note = (data.get("note") or "").strip()[:200]
    # SÉCURITÉ : seul un APPAREIL (cookie secret) peut être mis en confiance.
    # Mettre une IP en confiance accordait un accès boss à quiconque la partage
    # ou l'usurpe (X-Forwarded-For) → interdit (faille corrigée).
    if kind != "device" or not value:
        return jsonify({"error": "Seul un appareil (kind='device') peut être mis en confiance. "
                                 "Une IP n'accorde aucun accès (partageable et usurpable)."}), 400
    add_trusted(kind, value, note)
    return jsonify({"ok": True})


@surveillance_bp.route("/api/surveillance/trust", methods=["DELETE"])
def api_trust_remove():
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip()
    value = (data.get("value") or "").strip()
    if kind not in ("device", "ip") or not value:
        return jsonify({"error": "kind ('device'|'ip') et value requis"}), 400
    # Garde-fou : ne pas retirer la confiance de SON PROPRE appareil/IP → on se
    # retrouverait à devoir retaper le mot de passe (pas bloquant, mais évite la
    # mauvaise surprise). Le boss peut toujours le faire via la purge.
    if (kind == "device" and value == get_device_id()) or (kind == "ip" and value == client_ip()):
        return jsonify({"error": "REFUSÉ // c'est ton appareil/IP actuel, tu perdrais l'accès auto"}), 400
    remove_trusted(kind, value)
    return jsonify({"ok": True})


@surveillance_bp.route("/api/surveillance/purge", methods=["POST"])
def api_purge():
    """Mise en ligne : efface le journal + la whitelist de tous les appareils,
    ne garde QUE le tien (appareil + IP courants)."""
    device_id = get_device_id()
    ip = client_ip()
    purge_keep_only(device_id, ip)
    return jsonify({"ok": True, "kept": {"device_id": device_id, "ip": ip}})
