"""Actionable local diagnostics, personal alert receipts and shared task routines."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
from flask import g, jsonify, request, Response
from studio.domain import TZ, blockers, date, fresh, overview, utc_date
from studio.store import Conflict, now, uid

ROUTINES = [
    {
        "id": "research",
        "name": "Préparer un sujet",
        "description": "De la piste d’actualité au script sourcé.",
        "steps": [
            "Ouvrir les sources originales et vérifier leurs dates",
            "Recouper les faits et distinguer les rumeurs des confirmations",
            "Renseigner les faits vérifiés et les liens dans la fiche vidéo",
            "Préparer le titre, l’angle et le script",
        ],
    },
    {
        "id": "release",
        "name": "Vérifier une publication",
        "description": "Une liste commune avant de publier ou livrer.",
        "steps": [
            "Regarder le rendu et vérifier son, images et sous-titres",
            "Documenter les droits des médias, de la musique et de la voix",
            "Vérifier la miniature et le titre avec les références approuvées",
            "Relire la description, les sources et la fraîcheur au créneau prévu",
            "Compléter les contrôles de la fiche et confirmer la publication réelle",
        ],
    },
    {
        "id": "weekly",
        "name": "Organiser la semaine",
        "description": "Stock, calendrier et priorités de la chaîne.",
        "steps": [
            "Vérifier le stock réellement prêt et les sujets encore frais",
            "Choisir les prochains sujets sans reprendre une vidéo déjà traitée",
            "Réserver les créneaux et répartir le travail avec l’équipe",
            "Traiter les blocages dans le centre de contrôle",
        ],
    },
]


def initialize(store):
    with store.db() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS studio_alert_reads(
                user_id TEXT NOT NULL,alert_key TEXT NOT NULL,fingerprint TEXT NOT NULL,
                read_at TEXT NOT NULL,PRIMARY KEY(user_id,alert_key),
                FOREIGN KEY(user_id) REFERENCES studio_users(id));
            CREATE TABLE IF NOT EXISTS studio_routine_runs(
                request_key TEXT PRIMARY KEY,request_hash TEXT NOT NULL,template TEXT NOT NULL,
                channel_id INTEGER NOT NULL,video_id TEXT NOT NULL DEFAULT '',
                task_ids TEXT NOT NULL,created_at TEXT NOT NULL,
                FOREIGN KEY(channel_id) REFERENCES studio_channels(project_id));
            CREATE INDEX IF NOT EXISTS studio_routine_scope ON
                studio_routine_runs(template,channel_id,video_id);
        """)
        c.execute("INSERT OR IGNORE INTO studio_schema VALUES(4,?)", (now(),))


def diagnostics(store, user_id, *, preview=False, data=None, at=None):
    at = at or datetime.now(timezone.utc)
    data = data or overview(store)
    channels = {c["id"]: c for c in data["channels"]}
    alerts = []

    def add(key, level, category, title, message, help_text, action, version=""):
        fingerprint = hashlib.sha256(
            json.dumps(
                [key, level, title, message, version], ensure_ascii=False
            ).encode()
        ).hexdigest()
        alerts.append(
            dict(
                key=key,
                level=level,
                category=category,
                title=title,
                message=message,
                help=help_text,
                action=action,
                fingerprint=fingerprint,
            )
        )

    worker = data["worker"]
    heartbeat = date(worker["heartbeat"])
    online = bool(
        heartbeat
        and heartbeat.tzinfo
        and timedelta(0) <= at - heartbeat < timedelta(minutes=2)
    )
    active_jobs = store.rows(
        "SELECT id FROM studio_jobs WHERE status IN ('queued','running')"
    )
    collecting = store.one(
        "SELECT count(*) AS n FROM studio_news_config n JOIN studio_channels c ON c.project_id=n.channel_id WHERE n.enabled=1 AND c.paused=0"
    )["n"]
    scheduled = [
        v for v in data["videos"] if v["status"] == "scheduled" and v["post_at"]
    ]
    needs_worker = bool(
        active_jobs
        or collecting
        or any(
            channels[v["channel_id"]]["enabled"]
            and not channels[v["channel_id"]]["paused"]
            for v in scheduled
        )
    )
    if not preview and not online and needs_worker and not data["settings"]["paused"]:
        add(
            "system:worker",
            "critical",
            "system",
            "Le moteur ne répond plus",
            "Des travaux ou une cadence sont actifs, mais aucun signal récent du moteur n’est reçu.",
            "Ouvre Studio vidéo pour voir les travaux. Si le serveur a redémarré, relance son moteur : .venv/bin/python -m studio.worker, depuis le dossier du site.",
            {"page": "studio", "label": "Voir les travaux"},
            worker["heartbeat"],
        )
    if data["settings"]["paused"]:
        add(
            "system:pause",
            "info",
            "system",
            "Le studio est en pause",
            "Les collectes régulières et les publications programmées attendent.",
            "Clique sur Reprendre dans la barre du haut lorsque l’équipe veut reprendre.",
            {"page": "settings", "label": "Voir les réglages"},
            data["settings"]["revision"],
        )
    for c in channels.values():
        if not c["connected"]:
            add(
                f"channel:{c['id']}:connection",
                "critical" if c["enabled"] else "warning",
                "connections",
                c["name"],
                "Cette chaîne n’est pas connectée à YouTube.",
                "Chaînes → bouton avec l’icône de lien de la chaîne. Si la configuration Google manque, ses étapes sont dans Réglages.",
                {
                    "page": "channels",
                    "label": "Ouvrir les chaînes",
                    "channel_id": c["id"],
                },
                c["revision"],
            )
        if c["ready"] < c["target_stock"] and (
            c["connected"] or c["total"] or c["enabled"]
        ):
            add(
                f"channel:{c['id']}:stock",
                "warning",
                "stock",
                c["name"],
                f"{c['ready']} vidéo(s) prête(s) pour un objectif de {c['target_stock']}.",
                "Prépare un sujet et termine ses contrôles. Une fiche en recherche ne compte pas comme une vidéo prête.",
                {
                    "page": "studio",
                    "kind": "new_video",
                    "channel_id": c["id"],
                    "label": "Préparer une vidéo",
                },
                [c["ready"], c["target_stock"]],
            )
    for v in data["videos"]:
        c = channels[v["channel_id"]]
        action = {"page": "production", "video_id": v["id"], "label": "Ouvrir la fiche"}
        if v["status"] == "blocked":
            add(
                f"video:{v['id']}:blocked",
                "critical",
                "production",
                v["title"],
                "Cette production est bloquée.",
                "Ouvre la fiche : l’erreur et les étapes avant publication indiquent quoi reprendre.",
                action,
                v["revision"],
            )
        if v["status"] == "scheduled" and date(v["post_at"]):
            slot = date(v["post_at"])
            issues = blockers(v, c, data["settings"], automatic=True, at=max(at, slot))
            overdue = slot < at
            if issues or overdue:
                add(
                    f"video:{v['id']}:schedule",
                    "critical" if slot <= at + timedelta(hours=1) else "warning",
                    "calendar",
                    v["title"],
                    (
                        "Créneau dépassé. "
                        if overdue
                        else "À corriger avant le créneau. "
                    )
                    + "; ".join(issues),
                    "Ouvre Publication dans la fiche et suis les étapes. Si l’heure est passée, choisis un nouveau créneau dans le calendrier.",
                    action,
                    v["revision"],
                )
        elif (
            c["format"] == "news"
            and v["event_at"]
            and v["status"] in {"research", "script", "creating", "review", "ready"}
            and not fresh(v, c, at)
        ):
            add(
                f"video:{v['id']}:freshness",
                "warning",
                "production",
                v["title"],
                "Cette actualité dépasse la fraîcheur de la chaîne.",
                "Vérifie s’il existe une mise à jour sourcée, ou choisis un autre sujet dans le radar. Ne change pas simplement la date pour rendre un vieux sujet récent.",
                action,
                v["revision"],
            )
        if v["status"] == "delivered":
            add(
                f"video:{v['id']}:delivery",
                "info",
                "calendar",
                v["title"],
                "Livraison enregistrée ; publication YouTube à renseigner.",
                "Après l’envoi manuel, ouvre Publication → Déjà postée manuellement ? Colle le lien YouTube, puis clique sur Enregistrer le lien.",
                action,
                v["revision"],
            )
    for t in data["tasks"]:
        due = date(t["due_at"])
        if not t["done"] and due and due.tzinfo and due < at:
            add(
                f"task:{t['id']}:due",
                "warning",
                "tasks",
                t["title"],
                "L’échéance de cette tâche est dépassée.",
                "Ouvre la tâche pour la terminer, attribuer un responsable ou changer son échéance.",
                {"page": "tasks", "task_id": t["id"], "label": "Ouvrir la tâche"},
                t["revision"],
            )
    for f in store.rows(
        "SELECT id,channel_id,name,error,revision,last_checked FROM studio_news_feeds WHERE enabled=1 AND error!=''"
    ):
        add(
            f"feed:{f['id']}",
            "warning",
            "news",
            f["name"],
            "Cette source du radar ne répond pas correctement.",
            "Radar d’actus → choisir la chaîne → Actualiser les infos. Si l’erreur persiste, Configurer le radar pour remplacer ou désactiver le flux.",
            {"page": "news", "label": "Ouvrir le radar", "channel_id": f["channel_id"]},
            [f["revision"], f["last_checked"]],
        )
    latest = set()
    for j in store.rows(
        "SELECT id,kind,video_id,status,payload FROM studio_jobs ORDER BY created_at DESC,rowid DESC"
    ):
        payload = json.loads(j["payload"])
        scope = (
            j["kind"],
            j["video_id"],
            payload.get("channel_id"),
            payload.get("item_id"),
        )
        if scope in latest:
            continue
        latest.add(scope)
        if j["status"] == "failed":
            add(
                f"job:{j['id']}",
                "warning",
                "production",
                "Un travail s’est arrêté",
                "Le dernier essai a échoué. Un nouveau lancement n’a pas encore pris le relais.",
                "Studio vidéo → Travaux : lis l’erreur. Reprends ensuite l’étape depuis la fiche concernée ; aucun relancement payant n’est automatique ici.",
                {
                    "page": "studio",
                    "video_id": j["video_id"],
                    "label": "Voir le travail",
                },
                j["id"],
            )
    reads = {
        r["alert_key"]: r
        for r in store.rows(
            "SELECT * FROM studio_alert_reads WHERE user_id=?", (user_id,)
        )
    }
    for alert in alerts:
        receipt = reads.get(alert["key"])
        alert["read"] = bool(receipt and receipt["fingerprint"] == alert["fingerprint"])
        alert["read_at"] = receipt["read_at"] if alert["read"] else ""
    levels = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: (levels[a["level"]], a["read"], a["title"].casefold()))

    def configured(*names):
        return all(bool(os.getenv(name)) for name in names)

    services = [
        {
            "id": "worker",
            "name": "Moteur de production",
            "state": (
                "preview"
                if preview
                else (
                    "online" if online else "waiting" if not needs_worker else "offline"
                )
            ),
            "detail": (
                "Désactivé dans l’aperçu"
                if preview
                else (
                    "Signal reçu il y a moins de deux minutes"
                    if online
                    else (
                        "Pas de signal récent ; aucun travail attendu"
                        if not needs_worker
                        else "Pas de signal récent"
                    )
                )
            ),
            "page": "studio",
        },
    ]
    for key, name, names in [
        ("ai", "Agent texte", ["AI_BASE_URL", "AI_API_KEY"]),
        ("voice", "Voix sport / Oddly", ["ALGROW_API_KEY"]),
        ("voice_history", "Voix documentaire", ["AI33_API_KEY"]),
        ("render", "Relais de montage", ["NEWS_WORKER_URL", "NEWS_WORKER_TOKEN"]),
        (
            "youtube",
            "Client Google / YouTube",
            ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
        ),
    ]:
        ok = configured(*names)
        services.append(
            {
                "id": key,
                "name": name,
                "state": "configured" if ok else "missing",
                "detail": "Configuration présente" if ok else "Configuration absente",
                "page": "settings",
            }
        )
    return dict(
        alerts=alerts,
        services=services,
        server_time=at.isoformat(),
        preview=preview,
        summary=dict(
            total=len(alerts),
            unread=sum(not a["read"] for a in alerts),
            critical=sum(a["level"] == "critical" for a in alerts),
        ),
    )


def create_routine(store, b, actor):
    template = next((r for r in ROUTINES if r["id"] == b.get("template")), None)
    key = b.get("request_key", "")
    if (
        not template
        or not isinstance(key, str)
        or not re.fullmatch(r"[a-zA-Z0-9_-]{16,80}", key)
    ):
        raise ValueError("Choisis une routine et réessaie depuis le formulaire.")
    try:
        cid = int(b.get("channel_id", 0))
    except (ValueError, TypeError):
        raise ValueError("Choisis une chaîne.")
    ch = store.channel(cid)
    if not ch:
        raise ValueError("Choisis une chaîne existante.")
    vid = b.get("video_id") or ""
    video = store.video(vid) if isinstance(vid, str) and vid else None
    if vid and (not video or video["channel_id"] != cid):
        raise ValueError("La vidéo doit appartenir à la chaîne choisie.")
    assignee = b.get("assignee") or ""
    if not isinstance(assignee, str) or (
        assignee and assignee not in {u["id"] for u in store.users()}
    ):
        raise ValueError("Choisis un membre de l’équipe.")
    due = utc_date(b.get("due_at", ""))
    signature = hashlib.sha256(
        json.dumps([template["id"], cid, vid, assignee, due]).encode()
    ).hexdigest()
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        previous = c.execute(
            "SELECT * FROM studio_routine_runs WHERE request_key=?", (key,)
        ).fetchone()
        if previous:
            if previous["request_hash"] != signature:
                raise Conflict(
                    "Cette demande a déjà servi à une autre routine. Rouvre le formulaire."
                )
            return dict(task_ids=json.loads(previous["task_ids"]), created=False)
        ids = []
        for row in c.execute(
            "SELECT task_ids FROM studio_routine_runs WHERE template=? AND channel_id=? AND video_id=? ORDER BY created_at DESC",
            (template["id"], cid, vid),
        ).fetchall():
            candidates = json.loads(row["task_ids"])
            if any(
                c.execute(
                    "SELECT id FROM studio_tasks WHERE id=? AND done=0", (tid,)
                ).fetchone()
                for tid in candidates
            ):
                ids = candidates
                break
        created = not ids
        if created:
            suffix = video["title"] if video else ch["name"]
            for i, step in enumerate(template["steps"], 1):
                tid = uid()
                ids.append(tid)
                c.execute(
                    "INSERT INTO studio_tasks(id,title,channel_id,video_id,assignee,priority,due_at,created_at,updated_at) VALUES(?,?,?,?,?,'normal',?,?,?)",
                    (
                        tid,
                        f"{i}. {step} · {suffix}"[:300],
                        cid,
                        vid or None,
                        assignee,
                        due,
                        now(),
                        now(),
                    ),
                )
            c.execute(
                "INSERT INTO studio_activity(actor,action,message,created_at) VALUES(?,'routine',?,?)",
                (
                    actor,
                    "Routine ajoutée : " + template["name"] + " · " + ch["name"],
                    now(),
                ),
            )
        c.execute(
            "INSERT INTO studio_routine_runs VALUES(?,?,?,?,?,?,?)",
            (key, signature, template["id"], cid, vid, json.dumps(ids), now()),
        )
    return dict(task_ids=ids, created=created)


def ical_text(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold_line(line):
    chunks, current, size = [], "", 0
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > 75:
            chunks.append(current)
            current, size = " ", 1
        current += char
        size += width
    chunks.append(current)
    return "\r\n".join(chunks)


def calendar_export(store, month, channel_id=None):
    if not re.fullmatch(r"\d{4}-\d{2}", month or ""):
        raise ValueError("Choisis le mois à exporter.")
    try:
        start = datetime.strptime(month, "%Y-%m").replace(tzinfo=TZ)
    except ValueError:
        raise ValueError("Ce mois n’existe pas.")
    channels = {c["id"]: c for c in store.channels()}
    if channel_id is not None and channel_id not in channels:
        raise ValueError("Cette chaîne n’existe pas.")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Edgerunners Studio//Planning//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Edgerunners Studio",
    ]
    stamp = lambda d: d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for v in store.videos():
        slot = date(v["post_at"])
        if (
            not slot
            or not slot.tzinfo
            or slot.astimezone(TZ).strftime("%Y-%m") != start.strftime("%Y-%m")
            or v["status"] in {"published", "reported"}
        ):
            continue
        if channel_id is not None and v["channel_id"] != channel_id:
            continue
        c = channels[v["channel_id"]]
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:video-{v['id']}@edgerunners.studio",
                f"DTSTAMP:{stamp(date(v['updated_at']))}",
                f"SEQUENCE:{v['revision']}",
                f"DTSTART:{stamp(slot)}",
                f"DTEND:{stamp(slot + timedelta(minutes=15))}",
                "SUMMARY:" + ical_text(f"{c['name']} · {v['title']}"),
                "DESCRIPTION:"
                + ical_text(
                    "Créneau prévu dans Edgerunners Studio. Les contrôles et la connexion YouTube restent nécessaires. Cet export est une copie du planning, sans synchronisation automatique."
                ),
                "STATUS:TENTATIVE",
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_line(line) for line in lines) + "\r\n"


def register(app, store, body):
    initialize(store)

    @app.get("/api/studio/control")
    def control():
        return jsonify(diagnostics(store, g.user["id"], preview=app.config["PREVIEW"]))

    @app.post("/api/studio/control/alerts/<key>/read")
    def read_alert(key):
        b = body()
        item = next(
            (
                a
                for a in diagnostics(
                    store, g.user["id"], preview=app.config["PREVIEW"]
                )["alerts"]
                if a["key"] == key
            ),
            None,
        )
        if not item or item["fingerprint"] != b.get("fingerprint"):
            raise Conflict(
                "Cette alerte a changé ou s’est résolue. Actualise le centre de contrôle."
            )
        with store.db() as c:
            c.execute(
                "INSERT INTO studio_alert_reads VALUES(?,?,?,?) ON CONFLICT(user_id,alert_key) DO UPDATE SET fingerprint=excluded.fingerprint,read_at=excluded.read_at",
                (g.user["id"], key, item["fingerprint"], now()),
            )
        return jsonify(ok=True)

    @app.get("/api/studio/routines")
    def routines():
        return jsonify(templates=ROUTINES)

    @app.post("/api/studio/routines")
    def add_routine():
        result = create_routine(store, body(), g.user["name"])
        return jsonify(result), 201 if result["created"] else 200

    @app.get("/api/studio/calendar.ics")
    def export_calendar():
        cid = request.args.get("channel_id")
        if cid is not None:
            try:
                cid = int(cid)
            except ValueError:
                raise ValueError("Choisis une chaîne existante.")
        content = calendar_export(store, request.args.get("month", ""), cid)
        response = Response(content, content_type="text/calendar; charset=utf-8")
        response.headers["Content-Disposition"] = (
            f'attachment; filename="edgerunners-{request.args["month"]}.ics"'
        )
        return response
