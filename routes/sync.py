"""Sauvegarde serveur du travail dans les outils (sync multi-appareils).

Les outils de l'ami stockent tout dans le navigateur (localStorage + IndexedDB).
Comme la page-cadre (/tools/...) et l'outil (/toolfiles/...) sont SUR LE MÊME
DOMAINE, ils partagent ce stockage. `static/js/nc-sync.js` (injecté par
tool_frame.html, donc côté NOUS → incassable aux updates de l'ami) en fait un
instantané JSON et le pousse ici ; au chargement d'un outil il récupère le
dernier instantané et le restaure AVANT que l'outil ne lise le stockage.

Endpoints (boss-only : /api/ est dans la zone boss du gate d'app.py) :
  GET  /api/sync   → {version, data, updated_at}
  PUT  /api/sync   → body {data, base_version} → {ok, version} ou conflit 409
"""
from flask import Blueprint, jsonify, request, session

from database import get_tool_state, put_tool_state

sync_bp = Blueprint("sync", __name__)

SLUG = "__origin__"  # instantané global du stockage du domaine (tous les outils)


def _uid():
    # Identité boss partagée (cf. routes/access.py _open_session).
    return session.get("user_id") or "V_NIGHT_CITY"


@sync_bp.route("/api/sync", methods=["GET"])
def sync_get():
    # Ceinture + bretelles : le gate bloque déjà les non-boss, on revérifie.
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    state = get_tool_state(_uid(), SLUG)
    if not state:
        return jsonify({"version": 0, "data": "", "updated_at": None})
    return jsonify({
        "version": state["version"],
        "data": state["data"],
        "updated_at": state["updated_at"],
    })


@sync_bp.route("/api/sync", methods=["PUT"])
def sync_put():
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    payload = request.get_json(silent=True) or {}
    data = payload.get("data")
    if not isinstance(data, str):
        return jsonify({"error": "bad_request", "message": "champ 'data' (string) requis"}), 400
    base_version = payload.get("base_version", None)
    result = put_tool_state(_uid(), data, SLUG, expected_version=base_version)
    if not result.get("ok") and result.get("conflict"):
        # Une sauvegarde plus récente existe → le client doit refusionner.
        return jsonify(result), 409
    return jsonify(result)
