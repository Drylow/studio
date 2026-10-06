"""OAuth with expiring one-use state; uploads only through the checked job queue."""

from datetime import datetime, timedelta, timezone
import json
import os
import secrets
import urllib.parse
import urllib.request
from flask import request, session, jsonify, redirect, send_file
from studio.store import now, Conflict, ROOT


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
        active_channel(cid)
        state = secrets.token_urlsafe(32)
        with store.db() as c:
            c.execute(
                "INSERT INTO studio_oauth VALUES(?,?,?,?)",
                (
                    state,
                    session["studio_user"],
                    cid,
                    (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
                ),
            )
        query = urllib.parse.urlencode(
            {
                "client_id": cfg("GOOGLE_CLIENT_ID"),
                "redirect_uri": callback_url(),
                "response_type": "code",
                "scope": "https://www.googleapis.com/auth/youtube.force-ssl https://www.googleapis.com/auth/youtube.readonly",
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
                "SELECT * FROM studio_oauth WHERE state=?", (state,)
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
            return redirect(
                "/channels?"
                + urllib.parse.urlencode(
                    {
                        "youtube_error": "Connexion refusée : tu peux recommencer et accepter les autorisations Google.",
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
        from routes.youtube import _fetch_channel

        title, yt_id = _fetch_channel(token["access_token"])
        if not yt_id:
            raise ValueError("Aucune chaîne YouTube détectée sur ce compte.")
        normalize = lambda text: "".join(x.lower() for x in text if x.isalnum())
        if expected["yt_channel_id"] and expected["yt_channel_id"] != yt_id:
            raise ValueError(
                "Ce compte Google correspond à une autre chaîne. Reconnecte la chaîne attendue."
            )
        if not expected["yt_channel_id"] and normalize(title) not in {
            normalize(expected["name"]),
            normalize(expected["handle"]),
        }:
            raise ValueError(
                "La chaîne choisie ("
                + title
                + ") ne correspond pas à "
                + expected["name"]
                + ". Vérifie le compte sélectionné."
            )
        if store.one(
            "SELECT id FROM delamain_projects WHERE yt_channel_id=? AND id!=?",
            (yt_id, row["channel_id"]),
        ):
            raise ValueError(
                "Cette chaîne YouTube est déjà reliée à une autre fiche du studio."
            )
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
            if c.execute(
                "SELECT id FROM delamain_projects WHERE yt_channel_id=? AND id!=?",
                (yt_id, row["channel_id"]),
            ).fetchone():
                raise ValueError(
                    "Cette chaîne YouTube est déjà reliée à une autre fiche du studio."
                )
            c.execute(
                "UPDATE delamain_projects SET yt_refresh_token=?,yt_channel_title=?,yt_channel_id=? WHERE id=?",
                (token["refresh_token"], title, yt_id, row["channel_id"]),
            )
            from studio.channel_stats import clear

            if expected["yt_channel_id"] != yt_id:
                clear(c, row["channel_id"])
            else:
                c.execute("DELETE FROM studio_channel_sync WHERE channel_id=?", (row["channel_id"],))
            c.execute(
                "UPDATE studio_channels SET revision=revision+1,updated_at=? WHERE project_id=?",
                (now(), row["channel_id"]),
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
