import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "drylow_studio.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS access_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT DEFAULT (datetime('now')),
            event       TEXT NOT NULL,
            clearance   TEXT DEFAULT '',
            ip          TEXT DEFAULT '',
            device_id   TEXT DEFAULT '',
            browser     TEXT DEFAULT '',
            os          TEXT DEFAULT '',
            user_agent  TEXT DEFAULT '',
            path        TEXT DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_access_events_id ON access_events(id DESC)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blacklist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kind        TEXT NOT NULL,
            value       TEXT NOT NULL,
            note        TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(kind, value)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trusted_devices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kind        TEXT NOT NULL,
            value       TEXT NOT NULL,
            note        TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now')),
            last_seen   TEXT DEFAULT (datetime('now')),
            UNIQUE(kind, value)
        )
    """)
    # Sauvegarde serveur du travail dans les outils (sync multi-appareils).
    # Un instantané (localStorage + IndexedDB sérialisés) par identité + slug.
    # slug = '__origin__' → instantané global de tout le stockage du domaine.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tool_state (
            user_id     TEXT NOT NULL,
            slug        TEXT NOT NULL,
            version     INTEGER NOT NULL DEFAULT 0,
            data        TEXT NOT NULL DEFAULT '',
            updated_at  TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, slug)
        )
    """)
    # Mémoire permanente de Delamain : le tableau de production. Chaque ligne =
    # une vidéo en cours de fabrication, avec son état, ses assets et sa date de
    # publication prévue. C'est le cerveau qui permet à Delamain (et plus tard à
    # un worker autonome) de savoir quoi produire, quoi poster et quand.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delamain_plan (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            topic         TEXT NOT NULL,
            status        TEXT DEFAULT 'idea',
            niche         TEXT DEFAULT '',
            script        TEXT DEFAULT '',
            title         TEXT DEFAULT '',
            description   TEXT DEFAULT '',
            tags          TEXT DEFAULT '',
            thumbnail_url TEXT DEFAULT '',
            video_url     TEXT DEFAULT '',
            post_at       TEXT DEFAULT '',
            notes         TEXT DEFAULT '',
            created_at    TEXT DEFAULT (datetime('now')),
            updated_at    TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_status ON delamain_plan(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_postat ON delamain_plan(post_at)")
    # Projets = REGROUPEMENTS de chaînes (ex. « Chess » = 2-3 chaînes). Un projet porte des
    # INSTRUCTIONS communes, héritées par toutes ses chaînes (en plus des instructions propres
    # à chaque chaîne).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delamain_groups (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            instructions TEXT DEFAULT '',
            created_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    # Chaînes YouTube (rattachées à un projet via group_id). Chaque chaîne a sa propre
    # conversation, son tableau filtré et ses propres instructions (champ description).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delamain_projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            channel_id  TEXT DEFAULT '',
            niche       TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    # Conversations : chaque projet peut avoir N conversations (threads distincts).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delamain_conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            title      TEXT DEFAULT 'Nouvelle conversation',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_proj ON delamain_conversations(project_id, id DESC)")
    # Messages liés à une conversation. Migration safe : si la table existe avec l'ancien
    # schéma (project_id NOT NULL, sans conversation_id), on la recrée proprement.
    try:
        conn.execute("SELECT conversation_id FROM delamain_messages LIMIT 1")
    except Exception:
        conn.execute("DROP TABLE IF EXISTS delamain_messages")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delamain_messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            ts              TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON delamain_messages(conversation_id, id)")
    # Lier les fiches du tableau à leur projet (migration safe).
    try:
        conn.execute("ALTER TABLE delamain_plan ADD COLUMN project_id INTEGER DEFAULT NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_project ON delamain_plan(project_id)")
    except Exception:
        pass
    # Worker autonome : franchise (univers du tool vidéo) + id du job de rendu en cours.
    for ddl in (
        "ALTER TABLE delamain_plan ADD COLUMN franchise TEXT DEFAULT ''",
        "ALTER TABLE delamain_plan ADD COLUMN render_job TEXT DEFAULT ''",
        # Durée demandée en minutes (0/'' = mode 'liste de 100 faits' par défaut).
        "ALTER TABLE delamain_plan ADD COLUMN duration TEXT DEFAULT ''",
        # Avancement de la miniature en cours de génération. Valeurs :
        #   ''          = rien en cours (l'existence d'une miniature se lit sur thumbnail_url)
        #   '1'..'100'  = génération en cours, ce pourcentage (affiché en live, polling)
        #   'error'     = le dernier re-roll a échoué
        #   'pushfail'  = miniature refaite mais la mise à jour YouTube a échoué
        #   'pubfail:N' = N échecs de génération AU MOMENT DE PUBLIER (filet anti-blocage)
        "ALTER TABLE delamain_plan ADD COLUMN thumb_progress TEXT DEFAULT ''",
    ):
        try:
            conn.execute(ddl)
        except Exception:
            pass
    # Champs supplémentaires des projets (migration safe, colonne par colonne).
    for col, ddl in (
        ("description",      "ALTER TABLE delamain_projects ADD COLUMN description TEXT DEFAULT ''"),
        ("yt_refresh_token", "ALTER TABLE delamain_projects ADD COLUMN yt_refresh_token TEXT DEFAULT ''"),
        ("yt_channel_title", "ALTER TABLE delamain_projects ADD COLUMN yt_channel_title TEXT DEFAULT ''"),
        ("yt_channel_id",    "ALTER TABLE delamain_projects ADD COLUMN yt_channel_id TEXT DEFAULT ''"),
        ("proxy",            "ALTER TABLE delamain_projects ADD COLUMN proxy TEXT DEFAULT ''"),
        # Calendrier : cadence de publication (jours entre 2 uploads ; 0.5 = 2/jour)
        # et heure de publication par défaut. Réglables par chaîne.
        ("cadence_days",     "ALTER TABLE delamain_projects ADD COLUMN cadence_days TEXT DEFAULT '1'"),
        ("post_time",        "ALTER TABLE delamain_projects ADD COLUMN post_time TEXT DEFAULT '18:00'"),
        # Tool de création vidéo branché sur cette chaîne (slug ; un seul par chaîne).
        ("video_tool",       "ALTER TABLE delamain_projects ADD COLUMN video_tool TEXT DEFAULT ''"),
        # Mode d'automatisation : 'auto' (produit+poste seul) ou 'manual' (tu valides).
        ("autonomy",         "ALTER TABLE delamain_projects ADD COLUMN autonomy TEXT DEFAULT 'auto'"),
        # Langue de la chaîne (voix + script de l'atelier vidéo) : 'fr' ou 'en'. Défaut FR.
        ("lang",             "ALTER TABLE delamain_projects ADD COLUMN lang TEXT DEFAULT 'fr'"),
        # Projet (groupe) auquel la chaîne est rattachée (NULL = « Sans projet »).
        ("group_id",         "ALTER TABLE delamain_projects ADD COLUMN group_id INTEGER DEFAULT NULL"),
    ):
        try:
            conn.execute(ddl)
        except Exception:
            pass
    # Verrou GLOBAL du worker autonome (cross-process). o2switch/Passenger peut
    # lancer plusieurs process : un simple lock mémoire ne suffit pas. Cette table
    # à 1 ligne sert de mutex : un seul tick produit/publie à la fois, partout.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS worker_lock (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            held_until  TEXT DEFAULT ''
        )
    """)
    conn.execute("INSERT OR IGNORE INTO worker_lock (id, held_until) VALUES (1, '')")
    # NOTRE base d'assets (logos de licence, et + tard persos, etc.) : on stocke
    # l'IMAGE elle-même (BLOB) une fois récupérée via SerpAPI → réutilisable pour
    # toutes les chaînes, plus jamais de crédit de recherche. Clé = (kind, key),
    # ex. ('logo','one piece'). Extensible (kind='character'…).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS asset_cache (
            kind         TEXT,
            key          TEXT,
            source_url   TEXT,
            image        BLOB,
            content_type TEXT,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (kind, key)
        )
    """)
    # Journal du worker autonome : 1 ligne par événement marquant (rendu lancé, retry,
    # publication, blocage…). Sert la « console live » de Delamain + le diagnostic après
    # coup (« qu'est-ce qui a bloqué pendant que j'étais absent ? »). Borné (~600 lignes).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS worker_events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT DEFAULT (datetime('now')),
            level      TEXT DEFAULT 'info',     -- info | ok | warn | error
            action     TEXT DEFAULT '',
            message    TEXT DEFAULT '',
            plan_id    INTEGER DEFAULT NULL,
            project_id INTEGER DEFAULT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wevents_id ON worker_events(id DESC)")
    # Battement de cœur du worker (1 ligne) : quand a-t-il tourné pour la dernière fois,
    # et quoi. Permet le « dead-man's switch » : si pas de tick depuis trop longtemps
    # alors qu'il y a des vidéos dues → c'est mort, on le voit (et on alertera).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS worker_state (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            last_tick   TEXT DEFAULT '',
            last_action TEXT DEFAULT '',
            last_detail TEXT DEFAULT ''
        )
    """)
    conn.execute("INSERT OR IGNORE INTO worker_state (id) VALUES (1)")
    conn.commit()
    conn.close()


def event_log(level, action, message, plan_id=None, project_id=None):
    """Ajoute une ligne au journal du worker (et borne à ~600 lignes). Best-effort :
    si l'écriture échoue, on n'interrompt JAMAIS la production pour un log."""
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO worker_events (level, action, message, plan_id, project_id) "
            "VALUES (?,?,?,?,?)",
            (level, action, (message or "")[:500], plan_id, project_id))
        conn.execute(
            "DELETE FROM worker_events WHERE id <= (SELECT MAX(id) - 600 FROM worker_events)")
        conn.commit()
        conn.close()
    except Exception:
        pass


def event_list(since_id=0, limit=200):
    """Événements d'id > since_id (ordre chronologique), pour le polling de la console."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, ts, level, action, message, plan_id, project_id "
            "FROM worker_events WHERE id > ? ORDER BY id ASC LIMIT ?",
            (since_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def worker_heartbeat(action="", detail=""):
    """Marque que le worker vient de tourner (à chaque tick). UPDATE court, pas un event."""
    try:
        conn = get_db()
        conn.execute(
            "UPDATE worker_state SET last_tick = datetime('now'), last_action = ?, "
            "last_detail = ? WHERE id = 1",
            ((action or "")[:60], (detail or "")[:200]))
        conn.commit()
        conn.close()
    except Exception:
        pass


def worker_state_get():
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT last_tick, last_action, last_detail FROM worker_state WHERE id = 1"
        ).fetchone()
        return dict(row) if row else {"last_tick": "", "last_action": "", "last_detail": ""}
    finally:
        conn.close()


def asset_get(kind, key):
    """Renvoie (bytes, content_type) de l'asset stocké, ou (None, None)."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT image, content_type FROM asset_cache WHERE kind = ? AND key = ?",
            (kind, key)).fetchone()
        if row and row[0]:
            return row[0], (row[1] or "image/png")
        return None, None
    finally:
        conn.close()


def asset_set(kind, key, source_url, image, content_type):
    """Stocke (ou remplace) l'image d'un asset dans notre base."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO asset_cache (kind, key, source_url, image, content_type) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(kind, key) DO UPDATE SET source_url = excluded.source_url, "
            "image = excluded.image, content_type = excluded.content_type, "
            "updated_at = CURRENT_TIMESTAMP",
            (kind, key, source_url, sqlite3.Binary(image), content_type))
        conn.commit()
    finally:
        conn.close()


# ── Verrou global du worker (mutex cross-process via SQLite) ─────────────────

def worker_lock_acquire(ttl_seconds=600):
    """Tente de prendre le verrou global du worker. Renvoie True si on l'obtient.

    Atomique : l'UPDATE ne réussit (rowcount=1) que si le verrou est libre ou
    expiré. SQLite sérialise les écritures → un seul process passe à la fois.
    `ttl_seconds` = filet si un process meurt en tenant le verrou : au-delà il
    expire seul. 10 min suffisent pour le tick le plus long (upload YouTube /
    miniature Fal) ; au-delà on préfère débloquer la file plutôt que rester figé
    une demi-heure (avant : 1800 s → production gelée 30 min après un crash)."""
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE worker_lock SET held_until = datetime('now', ?) "
            "WHERE id = 1 AND (held_until = '' OR held_until < datetime('now'))",
            ("+%d seconds" % int(ttl_seconds),),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def worker_lock_release():
    """Libère le verrou global (marque expiré → réutilisable tout de suite)."""
    conn = get_db()
    try:
        conn.execute("UPDATE worker_lock SET held_until = '' WHERE id = 1")
        conn.commit()
    finally:
        conn.close()


# ── Surveillance : journal d'accès + blacklist ──────────────────────────────

def log_access_event(event, clearance="", ip="", device_id="",
                     browser="", os_name="", user_agent="", path=""):
    conn = get_db()
    conn.execute(
        """INSERT INTO access_events
           (event, clearance, ip, device_id, browser, os, user_agent, path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (event, clearance, ip, device_id, browser, os_name, user_agent, path),
    )
    # On garde les 3000 derniers événements pour ne pas faire gonfler la DB
    conn.execute(
        "DELETE FROM access_events WHERE id NOT IN "
        "(SELECT id FROM access_events ORDER BY id DESC LIMIT 3000)"
    )
    conn.commit()
    conn.close()


def list_access_events(limit=300):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM access_events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def access_stats():
    conn = get_db()
    stats = {
        "total":   conn.execute("SELECT COUNT(*) c FROM access_events WHERE event = 'unlock_ok'").fetchone()["c"],
        "fails":   conn.execute("SELECT COUNT(*) c FROM access_events WHERE event = 'unlock_fail'").fetchone()["c"],
        "blocked": conn.execute("SELECT COUNT(*) c FROM access_events WHERE event = 'blocked'").fetchone()["c"],
        "devices": conn.execute("SELECT COUNT(DISTINCT device_id) c FROM access_events WHERE device_id != ''").fetchone()["c"],
        "banned":  conn.execute("SELECT COUNT(*) c FROM blacklist").fetchone()["c"],
    }
    conn.close()
    return stats


def add_blacklist(kind, value, note=""):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO blacklist (kind, value, note) VALUES (?, ?, ?)",
        (kind, value, note),
    )
    conn.commit()
    conn.close()


def remove_blacklist(kind, value):
    conn = get_db()
    conn.execute("DELETE FROM blacklist WHERE kind = ? AND value = ?", (kind, value))
    conn.commit()
    conn.close()


def list_blacklist():
    conn = get_db()
    rows = conn.execute("SELECT * FROM blacklist ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_blacklisted(device_id):
    """Cet APPAREIL est-il banni ? On ne bannit que par appareil (cookie secret),
    JAMAIS par IP : avec des proxies (AdsPower) l'IP change tout le temps → un ban
    IP serait inutile et bloquerait des accès légitimes."""
    if not device_id:
        return False
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM blacklist WHERE kind = 'device' AND value = ? LIMIT 1",
        (device_id,),
    ).fetchone()
    conn.close()
    return bool(row)


# ── Appareils de confiance (whitelist boss : ouverture auto sans mot de passe) ─

def add_trusted(kind, value, note=""):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO trusted_devices (kind, value, note) VALUES (?, ?, ?)",
        (kind, value, note),
    )
    conn.commit()
    conn.close()


def remove_trusted(kind, value):
    conn = get_db()
    conn.execute("DELETE FROM trusted_devices WHERE kind = ? AND value = ?", (kind, value))
    conn.commit()
    conn.close()


def list_trusted():
    conn = get_db()
    rows = conn.execute("SELECT * FROM trusted_devices ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_trusted_device(device_id):
    """Cet APPAREIL est-il whitelisté → ouverture boss automatique sans mot de passe ?

    SÉCURITÉ : on ne fait confiance QU'À l'appareil, identifié par son cookie
    `nc_device` = jeton aléatoire 128 bits (httponly, non lisible par JS, non
    devinable). On NE fait JAMAIS confiance à une IP : une IP est partagée
    (même box/4G/VPN/proxy) et surtout USURPABLE via l'en-tête X-Forwarded-For,
    ce qui permettait à n'importe qui d'obtenir un accès boss (faille corrigée)."""
    if not device_id:
        return False
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM trusted_devices WHERE kind = 'device' AND value = ? LIMIT 1",
        (device_id,),
    ).fetchone()
    conn.close()
    return bool(row)


def touch_trusted(device_id):
    """Met à jour la dernière vue d'un appareil de confiance (cosmétique)."""
    if not device_id:
        return
    conn = get_db()
    conn.execute(
        "UPDATE trusted_devices SET last_seen = datetime('now') "
        "WHERE kind = 'device' AND value = ?",
        (device_id,),
    )
    conn.commit()
    conn.close()


def purge_keep_only(device_id, ip=None):
    """Repart sur une BASE FRAÎCHE : vide entièrement le journal d'accès ET la
    liste des bannis, supprime tous les appareils de confiance SAUF le tien, et
    (ré)inscrit le tien. Les projets/chaînes/calendrier ne sont PAS touchés.

    SÉCURITÉ : tout est géré par APPAREIL (cookie secret), jamais par IP. Le
    paramètre `ip` est ignoré (gardé pour compat des appels existants)."""
    conn = get_db()
    # Journal entièrement vidé (base fraîche).
    conn.execute("DELETE FROM access_events")
    # Bannis : on efface tout (aucun banni au départ).
    conn.execute("DELETE FROM blacklist")
    # Confiance : on supprime TOUT sauf mon appareil (et donc toute entrée IP héritée).
    conn.execute(
        "DELETE FROM trusted_devices WHERE NOT (kind = 'device' AND value = ?)",
        (device_id or "\x00",),
    )
    # On (ré)inscrit uniquement MON appareil comme de confiance.
    if device_id:
        conn.execute(
            "INSERT OR IGNORE INTO trusted_devices (kind, value, note) VALUES ('device', ?, ?)",
            (device_id, "Appareil du boss — épinglé"),
        )
    conn.commit()
    conn.close()


# ── Sauvegarde serveur du travail dans les outils (sync multi-appareils) ──────

def get_tool_state(user_id, slug="__origin__"):
    """Récupère l'instantané sauvegardé (ou None s'il n'y en a pas encore)."""
    conn = get_db()
    row = conn.execute(
        "SELECT version, data, updated_at FROM tool_state WHERE user_id = ? AND slug = ?",
        (user_id, slug),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def put_tool_state(user_id, data, slug="__origin__", expected_version=None):
    """Enregistre un instantané avec contrôle de version optimiste.

    - expected_version = None   → écrasement forcé (dernier qui écrit gagne).
    - expected_version = entier → n'écrit QUE si la version serveur correspond
      (évite qu'un onglet/appareil écrase une sauvegarde plus récente).

    Retourne {"ok": True, "version": n} en cas de succès, ou
    {"ok": False, "conflict": True, "version": n, "data": ...} si la version
    attendue ne correspond pas (le client doit refusionner puis réessayer).
    """
    conn = get_db()
    row = conn.execute(
        "SELECT version, data FROM tool_state WHERE user_id = ? AND slug = ?",
        (user_id, slug),
    ).fetchone()
    current = row["version"] if row else 0

    if expected_version is not None and int(expected_version) != current:
        result = {"ok": False, "conflict": True, "version": current,
                  "data": row["data"] if row else ""}
        conn.close()
        return result

    new_version = current + 1
    conn.execute(
        """INSERT INTO tool_state (user_id, slug, version, data, updated_at)
           VALUES (?, ?, ?, ?, datetime('now'))
           ON CONFLICT(user_id, slug) DO UPDATE SET
             version = excluded.version,
             data = excluded.data,
             updated_at = excluded.updated_at""",
        (user_id, slug, new_version, data),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "version": new_version}


# ── Mémoire de Delamain : tableau de production ─────────────────────────────

_PLAN_FIELDS = ("project_id", "topic", "status", "niche", "script", "title", "description",
                "tags", "thumbnail_url", "video_url", "post_at", "notes",
                "franchise", "render_job", "duration", "thumb_progress")


def plan_list(project_id=None):
    conn = get_db()
    if project_id is not None:
        rows = conn.execute(
            "SELECT * FROM delamain_plan WHERE project_id = ? ORDER BY "
            "CASE WHEN post_at = '' THEN 1 ELSE 0 END, post_at ASC, id DESC",
            (project_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM delamain_plan ORDER BY "
            "CASE WHEN post_at = '' THEN 1 ELSE 0 END, post_at ASC, id DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def plan_get(item_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM delamain_plan WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def plan_create(data):
    topic = (data.get("topic") or "").strip()
    if not topic:
        return None
    cols = [f for f in _PLAN_FIELDS if f in data]
    if "topic" not in cols:
        cols.append("topic")
    vals = [data.get(c, "") for c in cols]
    conn = get_db()
    cur = conn.execute(
        f"INSERT INTO delamain_plan ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
        vals,
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def plan_update(item_id, data):
    cols = [f for f in _PLAN_FIELDS if f in data]
    if not cols:
        return False
    sets = ", ".join(f"{c} = ?" for c in cols) + ", updated_at = datetime('now')"
    vals = [data[c] for c in cols] + [item_id]
    conn = get_db()
    cur = conn.execute(f"UPDATE delamain_plan SET {sets} WHERE id = ?", vals)
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n > 0


def plan_delete(item_id):
    conn = get_db()
    conn.execute("DELETE FROM delamain_plan WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def plan_clear(project_id):
    """Vide tout le calendrier/tableau d'une chaîne."""
    conn = get_db()
    cur = conn.execute("DELETE FROM delamain_plan WHERE project_id = ?", (project_id,))
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n


# ── Conversations Delamain ──────────────────────────────────────────────────

def conv_list(project_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM delamain_conversations WHERE project_id = ? ORDER BY updated_at DESC, id DESC",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def conv_get(conv_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM delamain_conversations WHERE id = ?", (conv_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def conv_create(project_id, title="Nouvelle conversation"):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO delamain_conversations (project_id, title) VALUES (?, ?)",
        (project_id, title or "Nouvelle conversation"),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def conv_update(conv_id, title):
    conn = get_db()
    conn.execute(
        "UPDATE delamain_conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
        ((title or "Nouvelle conversation"), conv_id),
    )
    conn.commit()
    conn.close()


def conv_touch(conv_id):
    conn = get_db()
    conn.execute(
        "UPDATE delamain_conversations SET updated_at = datetime('now') WHERE id = ?",
        (conv_id,),
    )
    conn.commit()
    conn.close()


def conv_delete(conv_id):
    conn = get_db()
    conn.execute("DELETE FROM delamain_conversations WHERE id = ?", (conv_id,))
    conn.execute("DELETE FROM delamain_messages WHERE conversation_id = ?", (conv_id,))
    conn.commit()
    conn.close()


# ── Projets Delamain (chaînes YouTube) ──────────────────────────────────────

_PROJECT_FIELDS = ("name", "channel_id", "niche", "description", "proxy",
                   "cadence_days", "post_time", "video_tool", "autonomy", "lang")


def project_list():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM delamain_projects ORDER BY created_at ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def project_get(project_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM delamain_projects WHERE id = ?", (project_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def project_create(data):
    name = (data.get("name") or "").strip()
    if not name:
        return None
    cols = [f for f in _PROJECT_FIELDS if (data.get(f) or "").strip()]
    if "name" not in cols:
        cols.append("name")
    vals = [(data.get(c) or "").strip() for c in cols]
    # group_id (entier, ou rien) — hors _PROJECT_FIELDS car non-texte.
    if data.get("group_id") not in (None, "", 0, "0"):
        cols.append("group_id"); vals.append(int(data["group_id"]))
    conn = get_db()
    cur = conn.execute(
        f"INSERT INTO delamain_projects ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
        vals,
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def project_update(project_id, data):
    cols = [f for f in _PROJECT_FIELDS if f in data]
    # Ne pas écraser le proxy avec une valeur vide : une édition qui ne touche pas
    # au champ proxy (laissé vide) ne doit PAS effacer le proxy déjà enregistré.
    if "proxy" in cols and not (data.get("proxy") or "").strip():
        cols.remove("proxy")
    set_parts = [f"{c} = ?" for c in cols]
    vals = [(data.get(c) or "") for c in cols]
    # group_id : entier (rattacher à un projet) ou NULL ('' / 0 = détacher).
    if "group_id" in data:
        gid = data.get("group_id")
        set_parts.append("group_id = ?")
        vals.append(int(gid) if gid not in (None, "", 0, "0") else None)
    if not set_parts:
        return False
    conn = get_db()
    conn.execute(f"UPDATE delamain_projects SET {', '.join(set_parts)} WHERE id = ?", vals + [project_id])
    conn.commit()
    conn.close()
    return True


def project_delete(project_id):
    conn = get_db()
    # Récupère les conversations du projet pour effacer aussi leurs messages.
    rows = conn.execute(
        "SELECT id FROM delamain_conversations WHERE project_id = ?", (project_id,)
    ).fetchall()
    conv_ids = [r["id"] for r in rows]
    conn.execute("DELETE FROM delamain_projects WHERE id = ?", (project_id,))
    conn.execute("DELETE FROM delamain_conversations WHERE project_id = ?", (project_id,))
    for cid in conv_ids:
        conn.execute("DELETE FROM delamain_messages WHERE conversation_id = ?", (cid,))
    conn.execute("DELETE FROM delamain_plan WHERE project_id = ?", (project_id,))
    conn.commit()
    conn.close()


# ── Projets (GROUPES de chaînes) ────────────────────────────────────────────

def group_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM delamain_groups ORDER BY created_at ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def group_get(group_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM delamain_groups WHERE id = ?", (group_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def group_create(data):
    name = (data.get("name") or "").strip()
    if not name:
        return None
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO delamain_groups (name, instructions) VALUES (?, ?)",
        (name, (data.get("instructions") or "").strip()),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def group_update(group_id, data):
    cols, vals = [], []
    if "name" in data and (data.get("name") or "").strip():
        cols.append("name = ?"); vals.append(data["name"].strip())
    if "instructions" in data:
        cols.append("instructions = ?"); vals.append((data.get("instructions") or "").strip())
    if not cols:
        return False
    conn = get_db()
    conn.execute(f"UPDATE delamain_groups SET {', '.join(cols)} WHERE id = ?", vals + [group_id])
    conn.commit()
    conn.close()
    return True


def group_delete(group_id):
    """Supprime un PROJET (groupe). Ses chaînes sont DÉTACHÉES (group_id=NULL), jamais supprimées."""
    conn = get_db()
    conn.execute("UPDATE delamain_projects SET group_id = NULL WHERE group_id = ?", (group_id,))
    conn.execute("DELETE FROM delamain_groups WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()


def project_set_youtube(project_id, refresh_token, channel_title="", channel_id=""):
    """Enregistre la connexion YouTube OAuth d'un projet (refresh token + infos chaîne)."""
    conn = get_db()
    conn.execute(
        "UPDATE delamain_projects SET yt_refresh_token = ?, yt_channel_title = ?, yt_channel_id = ? WHERE id = ?",
        (refresh_token or "", channel_title or "", channel_id or "", project_id),
    )
    conn.commit()
    conn.close()


def project_disconnect_youtube(project_id):
    conn = get_db()
    conn.execute(
        "UPDATE delamain_projects SET yt_refresh_token = '', yt_channel_title = '', yt_channel_id = '' WHERE id = ?",
        (project_id,),
    )
    conn.commit()
    conn.close()


# ── Messages (conversation par projet) ──────────────────────────────────────

def msg_list(conv_id, limit=200):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, role, content, ts FROM delamain_messages "
        "WHERE conversation_id = ? ORDER BY id ASC LIMIT ?",
        (conv_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def msg_add(conv_id, role, content):
    conn = get_db()
    conn.execute(
        "INSERT INTO delamain_messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conv_id, role, content),
    )
    conn.commit()
    conn.close()
    conv_touch(conv_id)


def msg_clear(conv_id):
    conn = get_db()
    conn.execute("DELETE FROM delamain_messages WHERE conversation_id = ?", (conv_id,))
    conn.commit()
    conn.close()


def recent_failed_unlocks(device_id, ip, minutes=10):
    """Nombre de tentatives de connexion ratées récentes pour cet appareil OU
    cette IP (anti-bruteforce du gate). S'appuie sur le journal access_events."""
    conn = get_db()
    row = conn.execute(
        """SELECT COUNT(*) AS c FROM access_events
           WHERE event = 'unlock_fail'
             AND ts >= datetime('now', ?)
             AND (device_id = ? OR ip = ?)""",
        (f"-{int(minutes)} minutes", device_id or "\x00", ip or "\x00"),
    ).fetchone()
    conn.close()
    return row["c"] if row else 0
