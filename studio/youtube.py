"""OAuth with expiring one-use state; uploads only through the checked job queue."""

import base64
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


BUSY = """SELECT EXISTS(SELECT 1 FROM studio_jobs j JOIN studio_videos v ON v.id=j.video_id
    WHERE v.channel_id=? AND j.kind='publish' AND j.status IN ('queued','running'))"""
AVATAR_HOSTS = {"yt3.ggpht.com", "yt3.googleusercontent.com"}


def _profile(access, yt_id):
    """Best effort: handle, avatar and audience, so the owner recognises the channel."""
    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?"
            + urllib.parse.urlencode({"part": "snippet,statistics", "id": yt_id}),
            headers={"Authorization": "Bearer " + access},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            item = (json.load(r).get("items") or [{}])[0]
        snippet, stats = item.get("snippet") or {}, item.get("statistics") or {}
        profile = {
            "handle": str(snippet.get("customUrl") or "")[:100],
            "subscribers": None
            if stats.get("hiddenSubscriberCount")
            else stats.get("subscriberCount"),
        }
        url = ((snippet.get("thumbnails") or {}).get("default") or {}).get("url", "")
        # The page only loads its own images: carry the small avatar inline.
        if urllib.parse.urlparse(url).hostname in AVATAR_HOSTS:
            with urllib.request.urlopen(url, timeout=15) as r:
                kind = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
                body = r.read(200001)
            if kind.startswith("image/") and len(body) <= 200000:
                profile["thumbnail"] = (
                    f"data:{kind};base64," + base64.b64encode(body).decode()
                )
        return profile
    except Exception:
        return {}


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
    with store.db() as c:
        # Short-lived: one Google authorization waiting for the owner to pick its fiche.
        c.execute(
            "CREATE TABLE IF NOT EXISTS studio_youtube_pending(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, origin INTEGER NOT NULL, scope TEXT NOT NULL, refresh_token TEXT NOT NULL, yt_channel_id TEXT NOT NULL, title TEXT NOT NULL, profile TEXT NOT NULL DEFAULT '{}', expires_at TEXT NOT NULL)"
        )

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
        same = expected["yt_channel_id"] == yt_id or (
            not expected["yt_channel_id"]
            and _normal(title)
            in {_normal(expected["name"]), _normal(expected["handle"])}
        )
        if not same or not movable(
            store.rows(CLAIMS, (yt_id, row["channel_id"])), title
        ):
            # Google profiles may still carry a former channel name: show which
            # channel this is and let the owner choose its fiche explicitly.
            granted = str(token.get("scope") or row["requested_scope"])
            pending = secrets.token_urlsafe(18)
            profile = _profile(token["access_token"], yt_id)
            with store.db() as c:
                c.execute(
                    "DELETE FROM studio_youtube_pending WHERE expires_at<?", (now(),)
                )
                c.execute(
                    "INSERT INTO studio_youtube_pending VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        pending,
                        row["user_id"],
                        row["channel_id"],
                        granted,
                        token["refresh_token"],
                        yt_id,
                        title,
                        json.dumps(profile),
                        (
                            datetime.now(timezone.utc) + timedelta(minutes=15)
                        ).isoformat(),
                    ),
                )
            return redirect(
                "/channels?"
                + urllib.parse.urlencode(
                    {"youtube_pending": pending, "channel": row["channel_id"]}
                )
            )
        bind(
            row["channel_id"],
            expected["revision"],
            token["refresh_token"],
            title,
            yt_id,
        )
        return redirect("/channels?connected=" + str(row["channel_id"]))

    def bind(cid, revision, refresh, title, yt_id, *, explicit=False):
        """Link one fiche to one YouTube channel; never two fiches on one channel."""
        from studio.channel_stats import clear

        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            current = c.execute(
                "SELECT s.revision,s.retired,p.yt_channel_id FROM studio_channels s JOIN delamain_projects p ON p.id=s.project_id WHERE s.project_id=?",
                (cid,),
            ).fetchone()
            if not current or current["retired"] or current["revision"] != revision:
                raise Conflict(
                    "Cette chaîne a changé pendant la connexion. Recommence depuis sa fiche."
                )
            stale = [dict(r) for r in c.execute(CLAIMS, (yt_id, cid)).fetchall()]
            if explicit:
                # The owner chose this fiche after seeing the channel; only an
                # active or publishing fiche keeps its link.
                active = [old for old in stale if old["enabled"] or old["busy"]]
                if active:
                    raise ValueError(
                        f"Cette chaîne YouTube est reliée à la fiche active « {active[0]['name']} ». Désactive ou déconnecte d’abord cette fiche."
                    )
                if current["yt_channel_id"] != yt_id and c.execute(BUSY, (cid,)).fetchone()[0]:
                    raise ValueError(
                        "Une publication de cette fiche est en cours. Réessaie après sa fin."
                    )
            elif not movable(stale, title):
                raise ValueError(
                    "Cette chaîne YouTube est déjà reliée à une autre fiche du studio."
                )
            # The former fiche keeps its history and can no longer publish there.
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
                (refresh, title, yt_id, now(), cid),
            )
            if current["yt_channel_id"] != yt_id:
                clear(c, cid)
            else:
                c.execute("DELETE FROM studio_channel_sync WHERE channel_id=?", (cid,))
            c.execute(
                "UPDATE studio_channels SET revision=revision+1,updated_at=? WHERE project_id=?",
                (now(), cid),
            )
        for old in stale:
            store.log(
                "Studio",
                "youtube",
                f"Lien YouTube retiré de « {old['name']} » : chaîne « {title} » reliée ailleurs",
            )
        store.log("Studio", "youtube", "Chaîne connectée : " + title)

    def pending_choice(pid):
        row = store.one("SELECT * FROM studio_youtube_pending WHERE id=?", (pid,))
        if (
            not row
            or row["user_id"] != session["studio_user"]
            or row["expires_at"] < now()
        ):
            raise ValueError(
                "Ce choix de chaîne a expiré. Relance la connexion depuis la fiche."
            )
        return row

    @app.get("/api/studio/youtube/pending/<pid>")
    def pending_detail(pid):
        owner()
        row = pending_choice(pid)
        profile = json.loads(row["profile"] or "{}")
        channels = store.channels()
        handle = _normal(profile.get("handle", ""))
        suggested = next(
            (
                c["id"]
                for rule in (
                    lambda c: c["yt_channel_id"] == row["yt_channel_id"],
                    lambda c: handle and _normal(c["handle"] or "") == handle,
                    lambda c: _normal(c["name"]) == _normal(row["title"]),
                )
                for c in channels
                if rule(c)
            ),
            row["origin"],
        )
        return jsonify(
            title=row["title"],
            yt_channel_id=row["yt_channel_id"],
            handle=profile.get("handle", ""),
            subscribers=profile.get("subscribers"),
            thumbnail=profile.get("thumbnail", ""),
            expires_at=row["expires_at"],
            origin=row["origin"],
            suggested=suggested,
            fiches=[
                {
                    "id": c["id"],
                    "name": c["name"],
                    "revision": c["revision"],
                    "enabled": bool(c["enabled"]),
                    "holds": c["yt_channel_id"] == row["yt_channel_id"],
                    "linked_title": c["yt_channel_title"]
                    if c["yt_channel_id"] and c["yt_channel_id"] != row["yt_channel_id"]
                    else "",
                    "compatible": supports(row["scope"], requested_scope(c)),
                }
                for c in channels
            ],
        )

    @app.post("/api/studio/youtube/pending/<pid>/assign")
    def pending_assign(pid):
        owner()
        if app.config["PREVIEW"]:
            raise ValueError("Les connexions réelles sont désactivées dans l’aperçu.")
        row = pending_choice(pid)
        data = request.get_json(silent=True) or {}
        try:
            cid = int(data.get("channel_id"))
        except (TypeError, ValueError):
            raise ValueError("Choisis la fiche à relier.") from None
        ch = requested_channel(cid)
        if not supports(row["scope"], requested_scope(ch)):
            raise ValueError(
                f"L’autorisation donnée à Google ne suffit pas pour « {ch['name']} ». Lance la connexion depuis cette fiche."
            )
        bind(
            cid,
            ch["revision"],
            row["refresh_token"],
            row["title"],
            row["yt_channel_id"],
            explicit=True,
        )
        with store.db() as c:
            c.execute("DELETE FROM studio_youtube_pending WHERE id=?", (pid,))
        return jsonify(ok=True, channel_id=cid, title=row["title"])

    @app.post("/api/studio/youtube/pending/<pid>/cancel")
    def pending_cancel(pid):
        owner()
        with store.db() as c:
            c.execute(
                "DELETE FROM studio_youtube_pending WHERE id=? AND user_id=?",
                (pid, session["studio_user"]),
            )
        return jsonify(ok=True)

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
