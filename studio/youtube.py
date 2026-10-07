"""OAuth with expiring one-use state; uploads only through the checked job queue."""

from datetime import datetime, timedelta, timezone
import json
import os
import secrets
import urllib.parse
import urllib.request
from flask import request, session, jsonify, redirect, send_file
from studio.store import now, Conflict, ROOT
from studio.youtube_permissions import MANAGED_SCOPE, requested_scope, supports

# Other fiches already bound to a YouTube channel, with what decides if they may let go.
CLAIMS = """SELECT p.id,p.name,p.yt_channel_title,coalesce(s.enabled,0) AS enabled,
    EXISTS(SELECT 1 FROM studio_jobs j JOIN studio_videos v ON v.id=j.video_id
      WHERE v.channel_id=p.id AND j.kind='publish' AND j.status IN ('queued','running')) AS busy
    FROM delamain_projects p LEFT JOIN studio_channels s ON s.project_id=p.id
    WHERE p.yt_channel_id=? AND p.id!=?"""


def _normal(text):
    return "".join(x.lower() for x in text if x.isalnum())


def movable(claims, title):
    """A channel renamed on YouTube may leave an inactive fiche that kept its former name."""
    return all(
        c["yt_channel_title"]
        and _normal(c["yt_channel_title"]) != _normal(title)
        and not c["enabled"]
        and not c["busy"]
        for c in claims
    )


def register_youtube(app, store, owner):
    @app.get("/api/studio/youtube/setup-guide")
    def setup_guide():
        return send_file(
            ROOT / "DEPLOY_O2SWITCH.md", mimetype="text/plain; charset=utf-8"
        )

    def cfg(k):
        return os.getenv(k, "").strip()

    def callback_url():
        path = cfg("OAUTH_CALLBACK_PATH") or "/api/studio/youtube/callback"
        if path not in {"/api/studio/youtube/callback", "/api/youtube/callback"}:
            raise ValueError("Adresse de retour Google non prise en charge.")
        return (
            cfg("OAUTH_REDIRECT_BASE").rstrip("/") or request.host_url.rstrip("/")
        ) + path

    def active_channel(cid):
        ch = store.channel(cid)
        if not ch:
            raise ValueError("Cette chaîne a été retirée ou n’existe pas.")
        return ch

    def requested_channel(cid):
        ch = active_channel(cid)
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or data.get("revision") != ch["revision"]:
            raise Conflict(
                "Cette chaîne a changé. Actualise avant de modifier sa connexion."
            )
        return ch

    @app.get("/api/studio/youtube/<int:cid>/connect")
    def connect(cid):
        owner()
        if app.config["PREVIEW"]:
            raise ValueError("La connexion Google est désactivée dans l’aperçu.")
        if not cfg("GOOGLE_CLIENT_ID") or not cfg("GOOGLE_CLIENT_SECRET"):
            raise ValueError(
                "La connexion Google doit être configurée sur le serveur. Consulte Réglages → Connexions."
            )
        scope = requested_scope(active_channel(cid))
        state = secrets.token_urlsafe(32)
        with store.db() as c:
            c.execute(
                "INSERT INTO studio_oauth(state,user_id,channel_id,expires_at) VALUES(?,?,?,?)",
                (
                    state,
                    session["studio_user"],
                    cid,
                    (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
                ),
            )
            c.execute("INSERT INTO studio_oauth_requests VALUES(?,?)", (state, scope))
        query = urllib.parse.urlencode(
            {
                "client_id": cfg("GOOGLE_CLIENT_ID"),
                "redirect_uri": callback_url(),
                "response_type": "code",
                "scope": scope,
                "access_type": "offline",
                "prompt": "select_account consent",
                "state": state,
            }
        )
        resp = redirect("https://accounts.google.com/o/oauth2/v2/auth?" + query)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/api/studio/youtube/callback")
    @app.get("/api/youtube/callback")
    def callback():
        owner()
        state = request.args.get("state", "")
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT o.*,coalesce(r.requested_scope,?) AS requested_scope FROM studio_oauth o LEFT JOIN studio_oauth_requests r ON r.state=o.state WHERE o.state=?",
                (MANAGED_SCOPE, state),
            ).fetchone()
            if (
                not row
                or row["user_id"] != session["studio_user"]
                or row["expires_at"] < now()
            ):
                raise ValueError(
                    "Connexion expirée ou état invalide. Relance la connexion depuis la chaîne."
                )
            c.execute("DELETE FROM studio_oauth WHERE state=?", (state,))
        if request.args.get("error"):
            explanations = {
                "access_denied": "Google a refusé l’autorisation. Si l’application est en test, le compte doit être ajouté aux utilisateurs de test du projet.",
                "invalid_scope": "Google refuse une permission demandée. Vérifie les autorisations YouTube du projet Google existant.",
                "admin_policy_enforced": "L’administrateur du compte Google bloque cette autorisation. Il doit autoriser Edgerunners Studio.",
                "org_internal": "Le projet Google est réservé à une organisation. Son audience doit être externe pour ces comptes.",
                "disallowed_useragent": "Ouvre edgerunners.fr directement dans Chrome ou Safari, puis recommence la connexion Google.",
            }
            return redirect(
                "/channels?"
                + urllib.parse.urlencode(
                    {
                        "youtube_error": explanations.get(
                            request.args["error"],
                            "Google a refusé cette autorisation. Vérifie l’état du projet dans Google Auth Platform.",
                        ),
                        "channel": row["channel_id"],
                    }
                )
            )
        code = request.args.get("code")
        if not code:
            raise ValueError("Code de connexion absent.")
        try:
            return complete_connection(row, code)
        except ValueError as e:
            return redirect(
                "/channels?"
                + urllib.parse.urlencode(
                    {"youtube_error": str(e), "channel": row["channel_id"]}
                )
            )

    def complete_connection(row, code):
        expected = active_channel(row["channel_id"])
        data = urllib.parse.urlencode(
            {
                "client_id": cfg("GOOGLE_CLIENT_ID"),
                "client_secret": cfg("GOOGLE_CLIENT_SECRET"),
                "redirect_uri": callback_url(),
                "code": code,
                "grant_type": "authorization_code",
            }
        ).encode()
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                token = json.load(response)
        except (OSError, ValueError):
            raise ValueError(
                "Google est injoignable ou a refusé la connexion. Recommence depuis la chaîne."
            ) from None
        if not token.get("refresh_token") or not token.get("access_token"):
            raise ValueError(
                "Google n’a pas fourni un accès permanent. Recommence en acceptant les autorisations."
            )
        if token.get("scope") is not None and not supports(
            str(token["scope"]), row["requested_scope"]
        ):
            raise ValueError(
                "L’autorisation d’envoi et de mise en ligne est absente. Reconnecte la chaîne et accepte cette autorisation Google."
            )
        from routes.youtube import _fetch_channel

        title, yt_id = _fetch_channel(token["access_token"])
        if not yt_id:
            raise ValueError("Aucune chaîne YouTube détectée sur ce compte.")
        if expected["yt_channel_id"] and expected["yt_channel_id"] != yt_id:
            raise ValueError(
                "Ce compte Google correspond à une autre chaîne. Reconnecte la chaîne attendue."
            )
        if not expected["yt_channel_id"] and _normal(title) not in {
            _normal(expected["name"]),
            _normal(expected["handle"]),
        }:
            raise ValueError(
                "La chaîne choisie ("
                + title
                + ") ne correspond pas à "
                + expected["name"]
                + ". Vérifie le compte sélectionné."
            )
        if not movable(store.rows(CLAIMS, (yt_id, row["channel_id"])), title):
            raise ValueError(
                "Cette chaîne YouTube est déjà reliée à une autre fiche du studio."
            )
        from studio.channel_stats import clear

        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            current = c.execute(
                "SELECT revision,retired FROM studio_channels WHERE project_id=?",
                (row["channel_id"],),
            ).fetchone()
            if (
                not current
                or current["retired"]
                or current["revision"] != expected["revision"]
            ):
                raise Conflict(
                    "Cette chaîne a changé pendant la connexion. Recommence depuis sa fiche."
                )
            stale = [
                dict(r) for r in c.execute(CLAIMS, (yt_id, row["channel_id"])).fetchall()
            ]
            if not movable(stale, title):
                raise ValueError(
                    "Cette chaîne YouTube est déjà reliée à une autre fiche du studio."
                )
            # The channel was renamed on YouTube: its former fiche loses the link,
            # keeps its history, and can no longer publish to this channel.
            for old in stale:
                c.execute(
                    "UPDATE delamain_projects SET yt_refresh_token='',yt_channel_title='',yt_channel_id='' WHERE id=?",
                    (old["id"],),
                )
                clear(c, old["id"])
                c.execute(
                    "UPDATE studio_channels SET revision=revision+1,updated_at=? WHERE project_id=?",
                    (now(), old["id"]),
                )
            c.execute(
                "UPDATE delamain_projects SET yt_refresh_token=?,yt_channel_title=?,yt_channel_id=?,yt_connected_at=? WHERE id=?",
                (token["refresh_token"], title, yt_id, now(), row["channel_id"]),
            )
            if expected["yt_channel_id"] != yt_id:
                clear(c, row["channel_id"])
            else:
                c.execute(
                    "DELETE FROM studio_channel_sync WHERE channel_id=?",
                    (row["channel_id"],),
                )
            c.execute(
                "UPDATE studio_channels SET revision=revision+1,updated_at=? WHERE project_id=?",
                (now(), row["channel_id"]),
            )
        for old in stale:
            store.log(
                "Studio",
                "youtube",
                f"Lien YouTube retiré de « {old['name']} » : chaîne renommée « {title} »",
            )
        store.log("Studio", "youtube", "Chaîne connectée : " + title)
        return redirect("/channels?connected=" + str(row["channel_id"]))

    @app.post("/api/studio/youtube/<int:cid>/verify")
    def verify(cid):
        owner()
        if app.config["PREVIEW"]:
            raise ValueError("Les connexions réelles sont désactivées dans l’aperçu.")
        ch = requested_channel(cid)
        if not cfg("GOOGLE_CLIENT_ID") or not cfg("GOOGLE_CLIENT_SECRET"):
            raise ValueError("Configure l’accès Google dans Réglages → Connexions.")
        project = store.one(
            "SELECT yt_refresh_token,proxy FROM delamain_projects WHERE id=?", (cid,)
        )
        if not project["yt_refresh_token"] or not ch["yt_channel_id"]:
            raise ValueError("Connecte d’abord cette chaîne avec Google.")
        from routes.youtube import _access_token, _fetch_channel

        try:
            access = _access_token(project["yt_refresh_token"], project["proxy"])
            title, yt_id = _fetch_channel(access) if access else ("", "")
        except (OSError, ValueError):
            raise ValueError(
                "Impossible de vérifier l’accès auprès de Google. Réessaie ou reconnecte cette chaîne."
            ) from None
        if not yt_id:
            raise ValueError(
                "YouTube n’a confirmé aucune chaîne. Réessaie ou reconnecte avec Google."
            )
        if yt_id != ch["yt_channel_id"]:
            raise ValueError(
                "L’accès Google correspond à une autre chaîne. Reconnecte la chaîne attendue."
            )
        current = active_channel(cid)
        if current["revision"] != ch["revision"]:
            raise Conflict(
                "La connexion a changé pendant la vérification. Actualise la chaîne."
            )
        store.log("Studio", "youtube", "Connexion YouTube vérifiée : " + title)
        return jsonify(channel_title=title, channel_id=yt_id, checked_at=now())

    @app.post("/api/studio/youtube/<int:cid>/disconnect")
    def disconnect(cid):
        owner()
        if app.config["PREVIEW"]:
            raise ValueError("Les connexions réelles sont désactivées dans l’aperçu.")
        ch = requested_channel(cid)
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            current = c.execute(
                "SELECT revision,retired FROM studio_channels WHERE project_id=?",
                (cid,),
            ).fetchone()
            if (
                not current
                or current["retired"]
                or current["revision"] != ch["revision"]
            ):
                raise Conflict(
                    "Cette connexion a changé. Actualise avant de la retirer."
                )
            c.execute(
                "UPDATE delamain_projects SET yt_refresh_token='' WHERE id=?",
                (cid,),
            )
            from studio.channel_stats import clear

            clear(c, cid)
            c.execute(
                "UPDATE studio_channels SET enabled=0,paused=1,revision=revision+1,updated_at=? WHERE project_id=?",
                (now(), cid),
            )
        store.log("Studio", "youtube", "Chaîne déconnectée et automatisation suspendue")
        return jsonify(ok=True)
