"""Mémoire permanente de Delamain — projets, conversations, messages, tableau.

  Projets (chaînes YouTube) :
    GET    /api/delamain/projects
    POST   /api/delamain/projects           {name, channel_id?, niche?}
    PATCH  /api/delamain/projects/<id>
    DELETE /api/delamain/projects/<id>

  Conversations (N par projet) :
    GET    /api/delamain/conversations?project_id=X
    POST   /api/delamain/conversations      {project_id, title?}
    PATCH  /api/delamain/conversations/<id> {title}
    DELETE /api/delamain/conversations/<id>

  Messages (par conversation) :
    GET    /api/delamain/messages/<conv_id>
    POST   /api/delamain/messages/<conv_id> {role, content}
    DELETE /api/delamain/messages/<conv_id>

  Tableau de production :
    GET    /api/delamain/plan               [?project_id=X]
    POST   /api/delamain/plan               {topic, project_id?, ...}
    PATCH  /api/delamain/plan/<id>
    DELETE /api/delamain/plan/<id>

Boss-only.
"""
from flask import Blueprint, jsonify, request, session

from database import (
    plan_list, plan_get, plan_create, plan_update, plan_delete, plan_clear,
    project_list, project_get, project_create, project_update, project_delete,
    group_list, group_get, group_create, group_update, group_delete,
    conv_list, conv_get, conv_create, conv_update, conv_delete,
    msg_list, msg_add, msg_clear,
)

delamain_bp = Blueprint("delamain", __name__)


def _guard():
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    return None


# ── Projets ──────────────────────────────────────────────────────────────────

def _safe_project(p):
    """Ne JAMAIS exposer au navigateur le refresh token ni le proxy (peut contenir
    un user:pass). On les remplace par des booléens."""
    if not p:
        return p
    p = dict(p)
    p["yt_connected"] = bool(p.pop("yt_refresh_token", ""))
    p["has_proxy"] = bool((p.pop("proxy", "") or "").strip())
    return p


@delamain_bp.route("/api/delamain/projects", methods=["GET"])
def projects_index():
    g = _guard()
    if g: return g
    return jsonify({"projects": [_safe_project(p) for p in project_list()]})


@delamain_bp.route("/api/delamain/projects", methods=["POST"])
def projects_add():
    g = _guard()
    if g: return g
    p = request.get_json(silent=True) or {}
    if not (p.get("name") or "").strip():
        return jsonify({"error": "name requis"}), 400
    new_id = project_create(p)
    return jsonify({"id": new_id, "project": _safe_project(project_get(new_id))})


@delamain_bp.route("/api/delamain/projects/<int:pid>", methods=["PATCH"])
def projects_edit(pid):
    g = _guard()
    if g: return g
    if not project_get(pid): return jsonify({"error": "not_found"}), 404
    project_update(pid, request.get_json(silent=True) or {})
    return jsonify({"project": _safe_project(project_get(pid))})


@delamain_bp.route("/api/delamain/projects/<int:pid>", methods=["DELETE"])
def projects_remove(pid):
    g = _guard()
    if g: return g
    project_delete(pid)
    return jsonify({"ok": True})


# ── Projets (GROUPES de chaînes) ───────────────────────────────────────────

@delamain_bp.route("/api/delamain/groups", methods=["GET"])
def groups_index():
    g = _guard()
    if g: return g
    return jsonify({"groups": group_list()})


@delamain_bp.route("/api/delamain/groups", methods=["POST"])
def groups_add():
    g = _guard()
    if g: return g
    p = request.get_json(silent=True) or {}
    if not (p.get("name") or "").strip():
        return jsonify({"error": "name requis"}), 400
    new_id = group_create(p)
    return jsonify({"id": new_id, "group": group_get(new_id)})


@delamain_bp.route("/api/delamain/groups/<int:gid>", methods=["PATCH"])
def groups_edit(gid):
    g = _guard()
    if g: return g
    if not group_get(gid): return jsonify({"error": "not_found"}), 404
    group_update(gid, request.get_json(silent=True) or {})
    return jsonify({"group": group_get(gid)})


@delamain_bp.route("/api/delamain/groups/<int:gid>", methods=["DELETE"])
def groups_remove(gid):
    g = _guard()
    if g: return g
    group_delete(gid)
    return jsonify({"ok": True})


# ── Conversations ─────────────────────────────────────────────────────────────

@delamain_bp.route("/api/delamain/conversations", methods=["GET"])
def convs_index():
    g = _guard()
    if g: return g
    pid = request.args.get("project_id", type=int)
    if not pid: return jsonify({"error": "project_id requis"}), 400
    return jsonify({"conversations": conv_list(pid)})


@delamain_bp.route("/api/delamain/conversations", methods=["POST"])
def convs_add():
    g = _guard()
    if g: return g
    p = request.get_json(silent=True) or {}
    pid = p.get("project_id")
    if not pid: return jsonify({"error": "project_id requis"}), 400
    new_id = conv_create(int(pid), p.get("title", "Nouvelle conversation"))
    return jsonify({"id": new_id, "conversation": conv_get(new_id)})


@delamain_bp.route("/api/delamain/conversations/<int:cid>", methods=["PATCH"])
def convs_edit(cid):
    g = _guard()
    if g: return g
    if not conv_get(cid): return jsonify({"error": "not_found"}), 404
    p = request.get_json(silent=True) or {}
    if "title" in p: conv_update(cid, p["title"])
    return jsonify({"conversation": conv_get(cid)})


@delamain_bp.route("/api/delamain/conversations/<int:cid>", methods=["DELETE"])
def convs_remove(cid):
    g = _guard()
    if g: return g
    conv_delete(cid)
    return jsonify({"ok": True})


# ── Messages ─────────────────────────────────────────────────────────────────

@delamain_bp.route("/api/delamain/messages/<int:cid>", methods=["GET"])
def messages_index(cid):
    g = _guard(); return g if g else jsonify({"messages": msg_list(cid)})


@delamain_bp.route("/api/delamain/messages/<int:cid>", methods=["POST"])
def messages_add(cid):
    g = _guard()
    if g: return g
    p = request.get_json(silent=True) or {}
    content = (p.get("content") or "").strip()
    if not content: return jsonify({"error": "content requis"}), 400
    msg_add(cid, p.get("role", "user"), content)
    return jsonify({"ok": True})


@delamain_bp.route("/api/delamain/messages/<int:cid>", methods=["DELETE"])
def messages_clear(cid):
    g = _guard()
    if g: return g
    msg_clear(cid)
    return jsonify({"ok": True})


# ── Tableau de production ─────────────────────────────────────────────────────

@delamain_bp.route("/api/delamain/plan", methods=["GET"])
def plan_index():
    g = _guard()
    if g: return g
    pid = request.args.get("project_id", type=int)
    return jsonify({"items": plan_list(project_id=pid)})


@delamain_bp.route("/api/delamain/plan", methods=["POST"])
def plan_add():
    g = _guard()
    if g: return g
    p = request.get_json(silent=True) or {}
    if not (p.get("topic") or "").strip():
        return jsonify({"error": "topic requis"}), 400
    new_id = plan_create(p)
    return jsonify({"id": new_id, "item": plan_get(new_id)})


@delamain_bp.route("/api/delamain/plan/bulk", methods=["POST"])
def plan_bulk():
    """Crée plusieurs fiches d'un coup (remplissage du calendrier).
    Body : {project_id, items:[{topic, post_at?, status?}, ...]}"""
    g = _guard()
    if g: return g
    p = request.get_json(silent=True) or {}
    pid = p.get("project_id")
    items = p.get("items") or []
    created = []
    for it in items:
        topic = (it.get("topic") or "").strip()
        if not topic:
            continue
        data = {"topic": topic, "post_at": it.get("post_at") or "",
                "status": it.get("status") or "scheduled"}
        fr = (it.get("franchise") or "").strip().lower()
        if fr:
            data["franchise"] = fr
        if pid:
            data["project_id"] = pid
        nid = plan_create(data)
        if nid:
            created.append(nid)
    return jsonify({"created": created, "count": len(created)})


@delamain_bp.route("/api/delamain/plan/clear", methods=["POST"])
def plan_clear_route():
    """Vide tout le calendrier d'une chaîne : {project_id}."""
    g = _guard()
    if g: return g
    p = request.get_json(silent=True) or {}
    pid = p.get("project_id")
    if not pid:
        return jsonify({"error": "project_id requis"}), 400
    n = plan_clear(int(pid))
    return jsonify({"ok": True, "deleted": n})


@delamain_bp.route("/api/delamain/plan/<int:item_id>", methods=["PATCH"])
def plan_edit(item_id):
    g = _guard()
    if g: return g
    if not plan_get(item_id): return jsonify({"error": "not_found"}), 404
    plan_update(item_id, request.get_json(silent=True) or {})
    return jsonify({"item": plan_get(item_id)})


@delamain_bp.route("/api/delamain/plan/<int:item_id>", methods=["DELETE"])
def plan_remove(item_id):
    g = _guard()
    if g: return g
    plan_delete(item_id)
    return jsonify({"ok": True})
