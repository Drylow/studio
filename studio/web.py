"""Authenticated API and frontend entry point for the shared studio."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import urlparse
from flask import (
    Flask,
    jsonify,
    request,
    session,
    send_file,
    send_from_directory,
    redirect,
    g,
)
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv, set_key
from studio.store import ROOT, Store, Conflict, now, uid
from studio.domain import overview, utc_date, blockers, STATUSES
from studio.imports import seed, import_productions, digest
from studio import security


def create_app(config=None):
    load_dotenv(ROOT / ".env")
    config = config or {}
    app = Flask(__name__, static_folder=None)
    hosted = config.get(
        "HOSTED",
        os.getenv("STUDIO_HOSTED") == "1" or os.getenv("FLASK_ENV") == "production",
    )
    secret = config.get("SECRET_KEY") or os.getenv("FLASK_SECRET_KEY")
    if not secret:
        secret = secrets.token_urlsafe(48)
        set_key(str(ROOT / ".env"), "FLASK_SECRET_KEY", secret)
        os.chmod(ROOT / ".env", 0o600)
    app.config.update(
        SECRET_KEY=secret,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
        MAX_CONTENT_LENGTH=12 * 1024 * 1024,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        HOSTED=hosted,
        PUBLIC_URL=os.getenv("STUDIO_PUBLIC_URL")
        or os.getenv("OAUTH_REDIRECT_BASE", ""),
        PREVIEW=os.getenv("STUDIO_PREVIEW") == "1",
        WORKER_ENABLED=os.getenv("STUDIO_WORKER_ENABLED", "1") == "1",
    )
    app.config.update(config)
    if app.config["HOSTED"]:
        if app.config["PREVIEW"] or app.config.get("LOCAL_OWNER"):
            raise ValueError(
                "L’aperçu et l’accès local sont interdits sur un site hébergé."
            )
        if len(app.config["SECRET_KEY"]) < 32:
            raise ValueError("L’hébergement exige une clé de session forte.")
        public = urlparse(app.config["PUBLIC_URL"])
        if (
            public.scheme != "https"
            or not public.hostname
            or public.username
            or public.password
            or public.path not in {"", "/"}
            or public.query
            or public.fragment
        ):
            raise ValueError("STUDIO_PUBLIC_URL doit être l’adresse HTTPS du studio.")
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_NAME="__Host-edgerunners",
            SESSION_COOKIE_PATH="/",
            SESSION_COOKIE_DOMAIN=None,
            TRUSTED_HOSTS=[public.hostname],
        )
        app.config["PUBLIC_URL"] = app.config["PUBLIC_URL"].rstrip("/")
    path = config.get("DB_PATH") or (
        ROOT / "work/studio/preview.db"
        if app.config["PREVIEW"]
        else os.getenv("DB_PATH") or ROOT / "drylow_studio.db"
    )
    store = Store(path)
    store.migrate()
    security.initialize(store)
    for private_file in [
        store.path,
        Path(str(store.path) + "-wal"),
        Path(str(store.path) + "-shm"),
    ]:
        if private_file.exists():
            os.chmod(private_file, 0o600)
    if app.config["HOSTED"] and len(store.users()) > 2:
        raise ValueError(
            "Le studio hébergé est réservé à deux comptes. Vérifie les accès existants avant son ouverture."
        )
    seed(store)
    if config.get("IMPORT_PRODUCTIONS", True):
        import_productions(store)
    app.extensions["studio_store"] = store
    store.web_app = app
    from studio.development import revision as code_revision, maintenance_path

    app.config["CODE_REVISION"] = code_revision()
    app.config.setdefault("DEVELOPMENT_MAINTENANCE_PATH", str(maintenance_path()))
    if (
        not app.config["PREVIEW"]
        and not store.users()
        and not os.getenv("STUDIO_BOOTSTRAP_TOKEN")
    ):
        token = secrets.token_urlsafe(32)
        set_key(str(ROOT / ".env"), "STUDIO_BOOTSTRAP_TOKEN", token)
        os.environ["STUDIO_BOOTSTRAP_TOKEN"] = token
        os.chmod(ROOT / ".env", 0o600)
    if app.config["PREVIEW"] or app.config.get("LOCAL_OWNER"):
        with store.db() as c:
            for name, username in [("Drylow", "drylow"), ("Kanye", "collegue")]:
                c.execute(
                    "INSERT OR IGNORE INTO studio_users VALUES(?,?,?,?,?,?)",
                    (
                        username,
                        name,
                        username,
                        generate_password_hash(secrets.token_urlsafe(32)),
                        "owner" if username == "drylow" else "editor",
                        now(),
                    ),
                )

            c.execute(
                "UPDATE studio_users SET name='Kanye' WHERE id='collegue' AND name='Collègue'"
            )

    def actor():
        return g.user["name"] if g.user else "Studio"

    def owner():
        if not g.user or g.user["role"] != "owner":
            raise PermissionError("Ce réglage est réservé au propriétaire du studio.")

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise ValueError("Requête JSON attendue.")
        return value

    def channel(cid):
        c = store.channel(cid)
        if not c:
            raise ValueError("Chaîne introuvable.")
        return c

    def video(vid):
        v = store.video(vid)
        if not v:
            raise ValueError("Vidéo introuvable.")
        return v

    def revision(b):
        if not isinstance(b.get("revision"), int):
            raise Conflict("Version absente : actualise la page.")
        return b["revision"]

    @app.before_request
    def guard():
        g.user = None
        if app.config["HOSTED"]:
            public = urlparse(app.config["PUBLIC_URL"])
            if request.host.lower() != public.netloc.lower():
                return jsonify(error="Adresse du studio invalide."), 400
            if not request.is_secure:
                if request.method in {"GET", "HEAD"}:
                    return redirect(
                        app.config["PUBLIC_URL"] + request.full_path.rstrip("?"),
                        code=308,
                    )
                return jsonify(error="La connexion HTTPS est obligatoire."), 426
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and Path(app.config["DEVELOPMENT_MAINTENANCE_PATH"]).exists()
        ):
            return (
                jsonify(
                    error="Le site se met à jour. Réessaie dans quelques instants."
                ),
                503,
            )
        if app.config["PREVIEW"] or app.config.get("LOCAL_OWNER"):
            if request.remote_addr not in {"127.0.0.1", "::1"}:
                return jsonify(error="L’aperçu est réservé à cette machine."), 403
        g.user = security.identity(store)
        if (
            (app.config["PREVIEW"] or app.config.get("LOCAL_OWNER"))
            and not g.user
            and not g.auth_session
        ):
            security.issue(store, "drylow")
            g.user = security.identity(store)
        session.setdefault("csrf", secrets.token_urlsafe(32))
        public_endpoint = request.endpoint in {
            "bootstrap",
            "auth_setup",
            "auth_login",
            "auth_logout",
            "login_page",
            "static_asset",
            "favicon",
            "studio_health",
            "robots",
            "public_about",
            "public_privacy",
            "public_terms",
        }
        if request.endpoint and not public_endpoint and not g.user:
            if request.endpoint in {"frontend", "legacy"}:
                from urllib.parse import urlencode

                return redirect("/login?" + urlencode({"next": request.path}), code=302)
            return jsonify(error="Connecte-toi au studio.", code="locked"), 401
        if request.path.startswith("/api/") or request.path.startswith("/media/"):
            if not g.user and request.path not in security.PUBLIC_APIS:
                return jsonify(error="Connecte-toi au studio.", code="locked"), 401
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                origin = request.headers.get("Origin")
                if origin and origin != request.host_url.rstrip("/"):
                    return jsonify(error="Origine de la requête refusée."), 403
                if not security.equal(
                    request.headers.get("X-CSRF-Token", ""), session["csrf"]
                ):
                    return (
                        jsonify(
                            error="Session expirée. Actualise la page.", code="csrf"
                        ),
                        403,
                    )

    @app.after_request
    def headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
        )
        if app.config["HOSTED"]:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000"
        if not request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(Conflict)
    def conflict(e):
        return jsonify(error=str(e)), 409

    @app.errorhandler(sqlite3.IntegrityError)
    def duplicate(e):
        return (
            jsonify(
                error=(
                    "Ce créneau est déjà occupé."
                    if "schedule_conflict" in str(e)
                    else "Cet élément existe déjà ou a changé. Actualise la page."
                )
            ),
            409,
        )

    @app.errorhandler(ValueError)
    def bad(e):
        return jsonify(error=str(e)), 400

    @app.errorhandler(PermissionError)
    def forbidden(e):
        return jsonify(error=str(e)), 403

    @app.errorhandler(404)
    def missing(e):
        return jsonify(error="Ce contenu est introuvable."), 404

    @app.get("/api/studio/bootstrap")
    def bootstrap():
        return jsonify(
            user=g.user,
            csrf=session["csrf"],
            setup_required=not bool(store.users()),
            preview=app.config["PREVIEW"],
        )

    security.register(app, store)

    @app.get("/api/studio/workspace")
    def workspace():
        data = overview(store)
        from studio.development import overview as development_overview

        data["development"] = development_overview(store, preview=app.config["PREVIEW"])
        data["connections"] = {
            "ai": bool(os.getenv("AI_BASE_URL") and os.getenv("AI_API_KEY")),
            "voice": bool(os.getenv("ALGROW_API_KEY")),
            "voice_history": bool(os.getenv("AI33_API_KEY")),
            "youtube": bool(
                os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET")
            ),
            "render": bool(os.getenv("NEWS_WORKER_URL")),
            "discord_mma": bool(os.getenv("DISCORD_WEBHOOK_MMA_EN")),
            "discord_football": bool(os.getenv("DISCORD_WEBHOOK_FOOTBALL_EN")),
        }
        from studio.control import diagnostics

        data["control"] = diagnostics(
            store, g.user["id"], preview=app.config["PREVIEW"], data=data
        )["summary"]
        return jsonify(data)

    @app.post("/api/studio/channels")
    def add_channel():
        b = body()
        name = str(b.get("name", "")).strip()
        fmt = b.get("format")
        if len(name) < 3 or fmt not in {"news", "pov", "history"}:
            raise ValueError("Indique un nom et un format de chaîne.")
        cid = store.add_channel(dict(b, name=name, autonomy="manual"))
        if fmt == "news":
            from studio.newsroom import initialize

            initialize(store)
        store.log(actor(), "channel", "Chaîne créée : " + name)
        return jsonify(id=cid), 201

    @app.delete("/api/studio/channels/<int:cid>")
    def remove_channel(cid):
        old = channel(cid)
        store.retire_channel(cid, revision(body()))
        store.log(actor(), "channel", "Chaîne retirée : " + old["name"])
        return jsonify(ok=True)

    @app.patch("/api/studio/channels/<int:cid>")
    def edit_channel(cid):
        old = channel(cid)
        b = body()
        data = {
            k: v
            for k, v in b.items()
            if k
            in {
                "name",
                "handle",
                "niche",
                "lang",
                "autonomy",
                "cadence_days",
                "post_time",
                "target_stock",
                "freshness_hours",
                "enabled",
                "paused",
                "budget",
                "instructions",
                "cadence_anchor",
                "publication_mode",
            }
        }
        if "template_key" in b:
            presets = {
                "news": {"mma_en", "football_en", "boxing_en"},
                "pov": {"oddly_specific_en", "oddly_expensive_en", "oddly_things_en"},
                "history": {"survivors_account", "frontier_blood"},
            }
            if b["template_key"] not in presets.get(old["format"], set()):
                raise ValueError("Ce modèle ne correspond pas au format de la chaîne.")
            data["template_key"] = b["template_key"]
        if "autonomy" in data and data["autonomy"] not in {"manual", "auto"}:
            raise ValueError("Mode invalide.")
        if "publication_mode" in data:
            if not isinstance(data["publication_mode"], str) or data["publication_mode"] not in {
                "scheduled", "news"
            }:
                raise ValueError(
                    "Choisis un rythme fixe ou une publication selon l’actualité."
                )
            if data["publication_mode"] == "news" and old["format"] != "news":
                raise ValueError(
                    "La publication selon l’actualité est réservée aux chaînes d’actualité."
                )
        if "lang" in data and data["lang"] not in {"fr", "en"}:
            raise ValueError("Langue invalide.")
        for key, lo, hi in [
            ("cadence_days", 0.25, 30),
            ("budget", 0, 1000),
            ("target_stock", 0, 100),
            ("freshness_hours", 1, 168),
        ]:
            if key in data:
                data[key] = float(data[key])
                if not lo <= data[key] <= hi:
                    raise ValueError("Valeur hors limites : " + key)
                if key in {"target_stock", "freshness_hours"}:
                    data[key] = int(data[key])
        if "post_time" in data and not re.fullmatch(
            r"([01]\d|2[0-3]):[0-5]\d", str(data["post_time"])
        ):
            raise ValueError("Heure invalide.")
        if "cadence_anchor" in data:
            from datetime import date as calendar_date

            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["cadence_anchor"]):
                    raise ValueError()
                calendar_date.fromisoformat(data["cadence_anchor"])
            except (ValueError, TypeError):
                raise ValueError(
                    "Choisis un premier jour valide pour le rythme de publication."
                )
        if data.get("enabled"):
            owner()
            if old["autonomy"] != "auto" and data.get("autonomy") != "auto":
                raise ValueError("Choisis le mode automatique avant de l’activer.")
            if not old["connected"]:
                raise ValueError("Connecte d’abord cette chaîne à YouTube.")
        store.update_channel(cid, data, revision(b))
        store.log(actor(), "channel", "Réglages mis à jour : " + old["name"])
        return jsonify(ok=True)

    @app.patch("/api/studio/channels/<int:cid>/responsibility")
    def assign_channel(cid):
        old = channel(cid)
        b = body()
        if "responsible_id" not in b:
            raise ValueError("Choisis un responsable ou À répartir.")
        member = b["responsible_id"]
        if member is not None and (
            not isinstance(member, str)
            or member not in {u["id"] for u in store.users()}
        ):
            raise ValueError("Choisis un membre de l’équipe ou la section À répartir.")
        store.update_channel(cid, {"responsible_id": member}, revision(b))
        name = next(
            (u["name"] for u in store.users() if u["id"] == member), "À répartir"
        )
        store.log(actor(), "assignment", old["name"] + " → " + name)
        return jsonify(ok=True)

    @app.post("/api/studio/videos")
    def add_video():
        b = body()
        ch = channel(int(b.get("channel_id", 0)))
        title = str(b.get("title", "")).strip()
        if len(title) < 4 or len(title) > 200:
            raise ValueError("Écris un sujet ou titre de 4 à 200 caractères.")
        sources = b.get("sources", [])
        if (
            not isinstance(sources, list)
            or len(sources) > 30
            or any(
                not isinstance(s, dict)
                or not s.get("name")
                or not str(s.get("url", "")).startswith("https://")
                or not s.get("id")
                for s in sources
            )
        ):
            raise ValueError(
                "Chaque source doit avoir un nom, un identifiant et une adresse HTTPS."
            )
        minutes = float(b.get("minutes") or (5 if ch["format"] == "news" else 14))
        if not 1 <= minutes <= 60:
            raise ValueError("Durée : de 1 à 60 minutes.")
        vid = store.add_video(
            {
                "channel_id": ch["id"],
                "title": title,
                "minutes": minutes,
                "notes": str(b.get("notes", ""))[:30000],
                "script": str(b.get("script", ""))[:100000],
                "sources": sources,
                "cost_cap": ch["budget"],
                "event_at": utc_date(b.get("event_at", "")),
            }
        )
        store.log(actor(), "video", "Vidéo créée : " + title)
        return jsonify(id=vid), 201

    @app.patch("/api/studio/videos/<vid>")
    def edit_video(vid):
        v = video(vid)
        b = body()
        if v["status"] in {"published", "reported"}:
            raise ValueError(
                "Cette publication est archivée. Crée une nouvelle vidéo pour la modifier."
            )
        if v["youtube_id"] and any(k in b for k in {"script", "sources"}):
            raise ValueError(
                "Ce rendu est déjà chargé sur YouTube. Crée une nouvelle version pour changer son contenu."
            )
        if store.one(
            "SELECT id FROM studio_jobs WHERE video_id=? AND status IN ('queued','running')",
            (vid,),
        ):
            raise Conflict("Une opération est en cours sur cette vidéo.")
        data = {
            k: value
            for k, value in b.items()
            if k
            in {
                "title",
                "description",
                "tags",
                "script",
                "notes",
                "sources",
                "event_at",
            }
        }
        if "event_at" in data:
            data["event_at"] = utc_date(data["event_at"])
        if "title" in data and not 4 <= len(str(data["title"]).strip()) <= 200:
            raise ValueError("Titre : de 4 à 200 caractères.")
        if "tags" in data and (
            not isinstance(data["tags"], list)
            or any(not isinstance(x, str) for x in data["tags"])
        ):
            raise ValueError("Les tags doivent être une liste de textes.")
        if "sources" in data and (
            not isinstance(data["sources"], list)
            or any(
                not isinstance(s, dict)
                or not s.get("name")
                or not s.get("id")
                or not str(s.get("url", "")).startswith("https://")
                for s in data["sources"]
            )
        ):
            raise ValueError(
                "Chaque source nécessite un nom, un identifiant et une adresse HTTPS."
            )
        if "post_at" in b:
            post = utc_date(b["post_at"])
            if post and datetime.fromisoformat(post) <= datetime.now(timezone.utc):
                raise ValueError("Choisis un créneau futur.")
            if post and store.one(
                "SELECT id FROM studio_videos WHERE channel_id=? AND post_at=? AND id!=? AND status!='published'",
                (v["channel_id"], post, vid),
            ):
                raise Conflict(
                    "Une vidéo est déjà prévue à ce créneau sur cette chaîne."
                )
            data["post_at"] = post
            if v["status"] in {"ready", "scheduled"}:
                data["status"] = "scheduled" if post else "ready"
        if "status" in b:
            if b["status"] not in {"idea", "research", "script", "review"}:
                raise ValueError(
                    "Utilise les contrôles de validation et publication pour changer cet état."
                )
            data["status"] = b["status"]
        if any(k in data and data[k] != v[k] for k in {"script", "sources"}):
            data.update(
                approved_digest="",
                quality_status="unknown",
                rights_status="unknown",
                render_digest="",
                status="script",
            )
        store.update("studio_videos", vid, data, revision(b))
        store.log(actor(), "video", "Vidéo mise à jour : " + v["title"])
        return jsonify(ok=True)

    @app.post("/api/studio/videos/<vid>/action")
    def video_action(vid):
        v = video(vid)
        b = body()
        ch = channel(v["channel_id"])
        action = b.get("action")
        if action == "approve":
            if (
                v["quality_status"] != "verified"
                or not v["render_digest"]
                or v["rights_status"] != "verified"
            ):
                raise ValueError(
                    "Les contrôles du rendu et des droits doivent être terminés avant validation."
                )
            store.update(
                "studio_videos",
                vid,
                {
                    "approved_digest": v["render_digest"],
                    "status": "scheduled" if v["post_at"] else "ready",
                },
                revision(b),
            )
            store.log(actor(), "approve", "Vidéo validée : " + v["title"])
            return jsonify(ok=True)
        if action == "report":
            url = str(b.get("url", "")).strip()
            match = re.fullmatch(
                r"https://(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]{11})|https://youtu\.be/([A-Za-z0-9_-]{11})",
                url,
            )
            if not match:
                raise ValueError("Colle le lien YouTube de cette vidéo.")
            store.update(
                "studio_videos",
                vid,
                {"youtube_id": match.group(1) or match.group(2), "status": "reported"},
                revision(b),
            )
            store.log(
                actor(), "report", "Publication manuelle rapportée : " + v["title"]
            )
            return jsonify(ok=True)
        if action not in {"render", "script", "publish", "discord", "verify"}:
            raise ValueError("Action inconnue.")
        if app.config["PREVIEW"]:
            raise ValueError(
                "L’aperçu permet d’organiser le studio ; les générations payantes et envois sont désactivés."
            )
        if action == "publish":
            reasons = blockers(v, ch, store.settings())
            if reasons:
                raise ValueError(" · ".join(reasons))
        if action in {"render", "script"} and (
            ch["budget"] <= 0 or store.settings()["daily_budget"] <= 0
        ):
            raise ValueError("Définis un budget de production dans les réglages.")
        job = store.enqueue(action, vid, {"actor": actor()})
        store.log(actor(), "job", action + " : " + v["title"])
        return jsonify(job_id=job), 202

    @app.post("/api/studio/tasks")
    def add_task():
        b = body()
        title = str(b.get("title", "")).strip()
        if not title or len(title) > 300:
            raise ValueError("Écris une tâche (300 caractères maximum).")
        cid = int(b["channel_id"]) if b.get("channel_id") else None
        if cid:
            channel(cid)
        if b.get("video_id"):
            video(b["video_id"])
        task_id = uid()
        with store.db() as c:
            c.execute(
                """INSERT INTO studio_tasks(id,title,channel_id,video_id,assignee,priority,due_at,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    task_id,
                    title,
                    cid,
                    b.get("video_id"),
                    str(b.get("assignee", "")),
                    (
                        b.get("priority", "normal")
                        if b.get("priority", "normal") in {"normal", "high", "low"}
                        else "normal"
                    ),
                    utc_date(b.get("due_at", "")),
                    now(),
                    now(),
                ),
            )
        store.log(actor(), "task", "Tâche ajoutée : " + title)
        return jsonify(id=task_id), 201

    @app.patch("/api/studio/tasks/<tid>")
    def edit_task(tid):
        b = body()
        data = {
            k: v
            for k, v in b.items()
            if k in {"title", "assignee", "done", "priority", "due_at", "channel_id"}
        }
        if "priority" in data and data["priority"] not in {"low", "normal", "high"}:
            raise ValueError("Priorité invalide.")
        if "title" in data and not 1 <= len(str(data["title"]).strip()) <= 300:
            raise ValueError("Écris un titre de tâche valide.")
        if data.get("channel_id"):
            channel(int(data["channel_id"]))
        if "due_at" in data:
            data["due_at"] = utc_date(data["due_at"])
        if "done" in data:
            data["done"] = int(bool(data["done"]))
        store.update("studio_tasks", tid, data, revision(b))
        store.log(actor(), "task", "Tâche mise à jour")
        return jsonify(ok=True)

    @app.delete("/api/studio/tasks/<tid>")
    def delete_task(tid):
        b = body()
        with store.db() as c:
            cur = c.execute(
                "DELETE FROM studio_tasks WHERE id=? AND revision=?", (tid, revision(b))
            )
            if not cur.rowcount:
                raise Conflict("La tâche a changé ou a déjà été supprimée.")
        return jsonify(ok=True)

    @app.patch("/api/studio/settings")
    def settings():
        owner()
        b = body()
        budget = float(b.get("daily_budget", store.settings()["daily_budget"]))
        if not 0 <= budget <= 1000:
            raise ValueError("Budget hors limites.")
        with store.db() as c:
            cur = c.execute(
                "UPDATE studio_settings SET paused=?,daily_budget=?,revision=revision+1 WHERE id=1 AND revision=?",
                (
                    int(bool(b.get("paused", store.settings()["paused"]))),
                    budget,
                    revision(b),
                ),
            )
            if not cur.rowcount:
                raise Conflict("Les réglages ont changé. Actualise la page.")
        store.log(actor(), "settings", "Réglages du studio mis à jour")
        return jsonify(ok=True)

    @app.post("/api/studio/users")
    def add_user():
        owner()
        if app.config["PREVIEW"]:
            raise ValueError("Les deux comptes de l’aperçu sont déjà disponibles.")
        b = body()
        username = str(b.get("username", "")).strip().lower()
        password = security.valid_password(b.get("password"))
        if (
            not re.fullmatch(r"[a-z0-9_.-]{3,40}", username)
            or not 1 <= len(str(b.get("name", "")).strip()) <= 80
        ):
            raise ValueError("Renseigne le nom et un identifiant de 3 à 40 caractères.")
        if store.one("SELECT id FROM studio_users WHERE username=?", (username,)):
            raise Conflict("Cet identifiant est déjà utilisé.")
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT COUNT(*) FROM studio_users").fetchone()[0] >= 2:
                raise PermissionError("Le studio est réservé à vos deux comptes.")
            c.execute(
                "INSERT INTO studio_users VALUES(?,?,?,?,?,?)",
                (
                    uid(),
                    str(b["name"]).strip(),
                    username,
                    generate_password_hash(password),
                    "editor",
                    now(),
                ),
            )
        store.log(actor(), "user", "Compte du collègue créé")
        return jsonify(ok=True), 201

    @app.post("/api/studio/import")
    def import_existing():
        count = import_productions(store)
        store.log(actor(), "import", f"{count} productions importées")
        return jsonify(count=count)

    @app.get("/api/studio/chat")
    def chat():
        messages = store.rows("SELECT * FROM studio_chat ORDER BY id DESC LIMIT 40")[
            ::-1
        ]
        for m in messages:
            m["attachments"] = json.loads(m["attachments"])
        return jsonify(messages=messages)

    @app.post("/api/studio/agent/news-work")
    def agent_news_work():
        b = body()
        if b.get("kind") == "news_scan":
            ch = channel(b.get("channel_id"))
            if ch["format"] != "news":
                raise ValueError("Choisis une chaîne d’actualité.")
            if app.config["PREVIEW"]:
                raise ValueError(
                    "Utilise Actualiser dans le radar de l’aperçu ; la collecte en file nécessite le moteur permanent."
                )
            payload = {"channel_id": ch["id"]}
        elif b.get("kind") == "news_prepare":
            item = store.one(
                "SELECT * FROM studio_news_items WHERE id=?", (b.get("item_id"),)
            )
            if not item or item["revision"] != revision(b):
                raise Conflict("Cette information a changé. Actualise le radar.")
            channel(item["channel_id"])
            payload = {"item_id": item["id"], "revision": item["revision"]}
        else:
            raise ValueError("Action de recherche inconnue.")
        payload["actor"] = actor()
        return jsonify(job_id=store.enqueue(b["kind"], payload=payload)), 202

    @app.post("/api/studio/chat")
    def send_chat():
        b = body()
        message = str(b.get("message", "")).strip()
        if not message or len(message) > 6000:
            raise ValueError("Écris une demande de 1 à 6 000 caractères.")
        if b.get("mode") == "development":
            owner()
            from studio.development import enqueue as enqueue_development

            job = enqueue_development(
                store, g.user, message, preview=app.config["PREVIEW"]
            )
            return jsonify(development_id=job), 202
        if b.get("mode", "studio") != "studio":
            raise ValueError("Mode Delamain inconnu.")
        if app.config["PREVIEW"]:
            raise ValueError(
                "L’agent est branché au service IA ; les appels externes sont désactivés dans cet aperçu."
            )
        with store.db() as c:
            c.execute(
                "INSERT INTO studio_chat(role,content,actor,created_at) VALUES(?,?,?,?)",
                ("user", message, actor(), now()),
            )
        job = store.enqueue(
            "agent",
            payload={"message": message, "actor": actor(), "user_id": g.user["id"]},
        )
        return jsonify(job_id=job), 202

    @app.post("/api/studio/jobs/<jid>/cancel")
    def cancel(jid):
        with store.db() as c:
            c.execute(
                "UPDATE studio_jobs SET cancel_requested=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END WHERE id=?",
                (jid,),
            )
        return jsonify(ok=True)

    @app.get("/media/<vid>/<kind>")
    def media(vid, kind):
        v = video(vid)
        key = {"thumbnail": "thumb_path", "video": "video_path"}.get(kind)
        if not key or not v.get(key):
            return jsonify(error="Fichier indisponible."), 404
        path = (ROOT / v[key]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            return jsonify(error="Fichier indisponible."), 404
        return send_file(
            path, conditional=True, as_attachment=request.args.get("download") == "1"
        )

    @app.get("/api/studio/library")
    def library():
        refs = []
        for folder in [
            ROOT / "presets/news_thumbnails/approved_2026-10-05",
            ROOT / "presets/oddly_things_en",
            ROOT / "presets/oddly_specific_en",
            ROOT / "presets/oddly_expensive_en",
        ]:
            for f in folder.glob("*"):
                if f.suffix.lower() in {".png", ".jpg", ".jpeg"} and f.name in {
                    "reference_01.png",
                    "reference_02.png",
                    "thumb.jpg",
                    "style.jpg",
                }:
                    refs.append(
                        {
                            "name": folder.name + " / " + f.stem,
                            "path": str(f.relative_to(ROOT / "presets")),
                        }
                    )
        return jsonify(references=refs)

    @app.get("/media/reference/<path:path>")
    def reference(path):
        p = (ROOT / "presets" / path).resolve()
        if not p.is_relative_to(ROOT / "presets") or p.suffix.lower() not in {
            ".png",
            ".jpg",
            ".jpeg",
        }:
            return jsonify(error="Référence introuvable."), 404
        return send_file(p, conditional=True)

    from studio.youtube import register_youtube

    register_youtube(app, store, owner)
    from studio.channel_stats import register as register_channel_stats

    register_channel_stats(app, store)
    from studio.public_statistics import register as register_public_statistics

    register_public_statistics(app, store, owner)
    from studio.development import register as register_development

    register_development(app, store, owner)

    @app.get("/health/studio")
    def studio_health():
        # Revision captured on application startup, not the possibly newer files on disk.
        store.one("SELECT id FROM studio_settings WHERE id=1")
        token = request.headers.get("X-Studio-Health", "")
        expected = security.health_token(app.config["SECRET_KEY"])
        private = bool(g.user) or bool(token and security.equal(token, expected))
        response = jsonify(
            status="ok",
            **({"revision": app.config["CODE_REVISION"]} if private else {}),
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    from studio.review import register_reviews

    register_reviews(app, store, owner)
    from studio.newsroom import register as register_newsroom

    register_newsroom(app, store, owner, body)
    from studio.control import register as register_control

    register_control(app, store, body)
    from studio.planning import register as register_planning

    register_planning(app, store)

    @app.get("/tools/<path:slug>")
    @app.get("/category/<path:slug>")
    @app.get("/surveillance")
    @app.get("/unlock")
    def legacy(slug=""):
        return redirect("/studio" if slug != "delamain" else "/agent", code=302)

    @app.get("/login")
    def login_page():
        if g.user:
            return redirect("/", code=302)
        return send_from_directory(ROOT / "static/studio", "index.html")

    from studio.public_pages import register as register_public_pages

    register_public_pages(app)

    @app.get("/robots.txt")
    def robots():
        return (
            "User-agent: *\nAllow: /about$\nAllow: /privacy$\nAllow: /terms$\nDisallow: /\n",
            200,
            {"Content-Type": "text/plain"},
        )

    @app.get("/static/<path:path>")
    def static_asset(path):
        # Never expose old generated media or arbitrary files from the static tree.
        allowed = (
            re.fullmatch(r"studio/assets/[A-Za-z0-9_-]+\.(?:js|css)", path)
            or re.fullmatch(r"fonts/[A-Za-z0-9_-]+\.(?:woff2?|ttf)", path)
            or path == "studio-icon.svg"
        )
        file = (ROOT / "static" / path).resolve()
        if not allowed or not file.is_relative_to((ROOT / "static").resolve()):
            return jsonify(error="Fichier introuvable."), 404
        return send_from_directory(ROOT / "static", path)

    @app.get("/")
    @app.get("/channels")
    @app.get("/statistics")
    @app.get("/production")
    @app.get("/calendar")
    @app.get("/tasks")
    @app.get("/studio")
    @app.get("/library")
    @app.get("/settings")
    @app.get("/agent")
    @app.get("/news")
    @app.get("/control")
    def frontend():
        return send_from_directory(ROOT / "static/studio", "index.html")

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(
            ROOT / "static", "studio-icon.svg", mimetype="image/svg+xml"
        )

    if (
        app.config["WORKER_ENABLED"]
        and not app.config["PREVIEW"]
        and not app.config.get("TESTING")
    ):
        from studio.worker import start

        start(store)
    return app
