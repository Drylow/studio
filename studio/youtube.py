"""OAuth with expiring one-use state; uploads only through the checked job queue."""

from datetime import datetime, timedelta, timezone
import json
import os
import secrets
import urllib.parse
import urllib.request
from flask import request, session, jsonify, redirect
from studio.store import now


def register_youtube(app, store, owner):
    def cfg(k):
        return os.getenv(k, "").strip()

    def callback_url():
        return (
            cfg("OAUTH_REDIRECT_BASE").rstrip("/") or request.host_url.rstrip("/")
        ) + "/api/studio/youtube/callback"

    @app.get("/api/studio/youtube/<int:cid>/connect")
    def connect(cid):
        owner()
        if app.config["PREVIEW"]:
            raise ValueError("La connexion Google est désactivée dans l’aperçu.")
        if not cfg("GOOGLE_CLIENT_ID") or not cfg("GOOGLE_CLIENT_SECRET"):
            raise ValueError(
                "La connexion Google doit être configurée sur le serveur. Consulte Réglages → Connexions."
            )
        if not store.channel(cid):
            raise ValueError("Chaîne introuvable.")
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
            return redirect("/settings?youtube=refused")
        code = request.args.get("code")
        if not code:
            raise ValueError("Code de connexion absent.")
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
        with urllib.request.urlopen(req, timeout=30) as response:
            token = json.load(response)
        if not token.get("refresh_token"):
            raise ValueError(
                "Google n’a pas fourni un accès permanent. Recommence en acceptant les autorisations."
            )
        from routes.youtube import _fetch_channel

        title, yt_id = _fetch_channel(token["access_token"])
        if not yt_id:
            raise ValueError("Aucune chaîne YouTube détectée sur ce compte.")
        expected = store.channel(row["channel_id"])
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
            c.execute(
                "UPDATE delamain_projects SET yt_refresh_token=?,yt_channel_title=?,yt_channel_id=? WHERE id=?",
                (token["refresh_token"], title, yt_id, row["channel_id"]),
            )
        store.log("Studio", "youtube", "Chaîne connectée : " + title)
        return redirect("/channels?connected=" + str(row["channel_id"]))

    @app.post("/api/studio/youtube/<int:cid>/disconnect")
    def disconnect(cid):
        owner()
        if app.config["PREVIEW"]:
            raise ValueError("Les connexions réelles sont désactivées dans l’aperçu.")
        with store.db() as c:
            c.execute(
                "UPDATE delamain_projects SET yt_refresh_token='',yt_channel_id='',yt_channel_title='' WHERE id=?",
                (cid,),
            )
            c.execute(
                "UPDATE studio_channels SET enabled=0,paused=1,revision=revision+1 WHERE project_id=?",
                (cid,),
            )
        store.log("Studio", "youtube", "Chaîne déconnectée et automatisation suspendue")
        return jsonify(ok=True)
