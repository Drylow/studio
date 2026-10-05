"""Authenticated API and frontend entry point for the shared studio."""

from datetime import datetime, timedelta, timezone
import hmac
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
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv, set_key
from studio.store import ROOT, Store, Conflict, now, uid
from studio.domain import overview, utc_date, blockers, STATUSES
from studio.imports import seed, import_productions, digest


def create_app(config=None):
    load_dotenv(ROOT / ".env")
    config = config or {}
    app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="/static")
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
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
        PREVIEW=os.getenv("STUDIO_PREVIEW") == "1",
        WORKER_ENABLED=os.getenv("STUDIO_WORKER_ENABLED", "1") == "1",
    )
    app.config.update(config)
    path = config.get("DB_PATH") or (
        ROOT / "work/studio/preview.db"
        if app.config["PREVIEW"]
        else os.getenv("DB_PATH") or ROOT / "drylow_studio.db"
    )
    store = Store(path)
    store.migrate()
    seed(store)
    if config.get("IMPORT_PRODUCTIONS", True):
        import_productions(store)
    app.extensions["studio_store"] = store
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
        if app.config["PREVIEW"] or app.config.get("LOCAL_OWNER"):
            if request.remote_addr not in {"127.0.0.1", "::1"}:
                return jsonify(error="L’aperçu est réservé à cette machine."), 403
            session.setdefault("studio_user", "drylow")
        if session.get("studio_user"):
            g.user = next(
                (u for u in store.users() if u["id"] == session["studio_user"]), None
            )
        session.setdefault("csrf", secrets.token_urlsafe(32))
        if request.path.startswith("/api/") or request.path.startswith("/media/"):
            public = {"/api/studio/bootstrap", "/api/studio/login", "/api/studio/setup"}
            if not g.user and request.path not in public:
                return jsonify(error="Connecte-toi au studio.", code="locked"), 401
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                if not hmac.compare_digest(
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
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
        )
        if os.getenv("FLASK_ENV") == "production":
            resp.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.path.startswith(("/api/", "/media/")):
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

    @app.post("/api/studio/setup")
    def setup():
        b = body()
        token = os.getenv("STUDIO_BOOTSTRAP_TOKEN", "")
        if not token or not hmac.compare_digest(str(b.get("token", "")), token):
            raise PermissionError("Code d’activation invalide.")
        name = str(b.get("name", "")).strip()
        username = str(b.get("username", "")).strip().lower()
        password = str(b.get("password", ""))
        if (
            not name
            or not re.fullmatch(r"[a-z0-9_.-]{3,40}", username)
            or len(password) < 12
        ):
            raise ValueError(
                "Nom, identifiant (3–40 caractères) et mot de passe de 12 caractères minimum requis."
            )
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM studio_users").fetchone():
                raise Conflict("Le studio a déjà été activé.")
            user_id = uid()
            c.execute(
                "INSERT INTO studio_users VALUES(?,?,?,?,?,?)",
                (
                    user_id,
                    name,
                    username,
                    generate_password_hash(password),
                    "owner",
                    now(),
                ),
            )
        session.clear()
        session.update(studio_user=user_id, csrf=secrets.token_urlsafe(32))
        store.log(name, "setup", "Studio activé")
        return jsonify(ok=True)

    @app.post("/api/studio/login")
    def login():
        b = body()
        username = str(b.get("username", "")).strip().lower()
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with store.db() as c:
            c.execute("DELETE FROM studio_login_attempts WHERE created_at<?", (cutoff,))
            attempts = c.execute(
                "SELECT COUNT(*) FROM studio_login_attempts WHERE ip=? OR username=?",
                (request.remote_addr, username),
            ).fetchone()[0]
            if attempts >= 8:
                return jsonify(error="Trop d’essais. Réessaie dans 10 minutes."), 429
            u = c.execute(
                "SELECT * FROM studio_users WHERE username=?", (username,)
            ).fetchone()
            if not u or not check_password_hash(
                u["password_hash"], str(b.get("password", ""))
            ):
                c.execute(
                    "INSERT INTO studio_login_attempts VALUES(?,?,?)",
                    (request.remote_addr, username, now()),
                )
                return jsonify(error="Identifiant ou mot de passe incorrect."), 401
        session.clear()
        session.update(studio_user=u["id"], csrf=secrets.token_urlsafe(32))
        session.permanent = True
        store.log(u["name"], "login", "Connexion au studio")
        return jsonify(ok=True)

    @app.post("/api/studio/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/studio/workspace")
    def workspace():
        data = overview(store)
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
        password = str(b.get("password", ""))
        if (
            not re.fullmatch(r"[a-z0-9_.-]{3,40}", username)
            or len(password) < 12
            or not str(b.get("name", "")).strip()
        ):
            raise ValueError(
                "Nom, identifiant et mot de passe de 12 caractères minimum requis."
            )
        if store.one("SELECT id FROM studio_users WHERE username=?", (username,)):
            raise Conflict("Cet identifiant est déjà utilisé.")
        with store.db() as c:
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
        return jsonify(
            messages=store.rows("SELECT * FROM studio_chat ORDER BY id DESC LIMIT 40")[
                ::-1
            ]
        )

    @app.post("/api/studio/chat")
    def send_chat():
        b = body()
        message = str(b.get("message", "")).strip()
        if not message or len(message) > 6000:
            raise ValueError("Écris une demande de 1 à 6 000 caractères.")
        if app.config["PREVIEW"]:
            raise ValueError(
                "L’agent est branché au service IA ; les appels externes sont désactivés dans cet aperçu."
            )
        with store.db() as c:
            c.execute(
                "INSERT INTO studio_chat(role,content,actor,created_at) VALUES(?,?,?,?)",
                ("user", message, actor(), now()),
            )
        job = store.enqueue("agent", payload={"message": message, "actor": actor()})
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

    @app.get("/")
    @app.get("/channels")
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
