"""Versioned, non-destructive workspace storage and atomic job reservations."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import uuid
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=30000")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def rows(self, sql, args=()):
        with self.db() as c:
            return [dict(x) for x in c.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        r = self.rows(sql, args)
        return r[0] if r else None

    def migrate(self):
        with self.db() as c:
            existing = c.execute(
                "SELECT name FROM sqlite_master WHERE name='studio_schema'"
            ).fetchone()
            if (
                not existing
                and c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchone()
            ):
                dest = (
                    ROOT
                    / "work/studio/backups"
                    / (self.path.stem + "-" + uid()[:8] + ".db")
                )
                dest.parent.mkdir(parents=True, exist_ok=True)
                backup = sqlite3.connect(dest)
                c.backup(backup)
                backup.close()
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
            CREATE TABLE IF NOT EXISTS studio_schema(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS delamain_projects(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                channel_id TEXT DEFAULT '', niche TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now')));
            CREATE TABLE IF NOT EXISTS studio_channels(project_id INTEGER PRIMARY KEY REFERENCES delamain_projects(id),
                key TEXT NOT NULL UNIQUE, format TEXT NOT NULL, accent TEXT NOT NULL DEFAULT '#00e5e5',
                initials TEXT DEFAULT '', target_stock INTEGER DEFAULT 3, freshness_hours INTEGER DEFAULT 48,
                enabled INTEGER DEFAULT 0, paused INTEGER DEFAULT 0, budget REAL DEFAULT 3,
                instructions TEXT DEFAULT '', revision INTEGER DEFAULT 1, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS studio_users(id TEXT PRIMARY KEY, name TEXT NOT NULL, username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS studio_settings(id INTEGER PRIMARY KEY CHECK(id=1), paused INTEGER DEFAULT 0,
                daily_budget REAL DEFAULT 15, timezone TEXT DEFAULT 'Europe/Paris', revision INTEGER DEFAULT 1);
            INSERT OR IGNORE INTO studio_settings(id) VALUES(1);
            CREATE TABLE IF NOT EXISTS studio_videos(id TEXT PRIMARY KEY, channel_id INTEGER NOT NULL REFERENCES studio_channels(project_id),
                title TEXT NOT NULL, status TEXT DEFAULT 'idea', minutes REAL DEFAULT 5, script TEXT DEFAULT '',
                description TEXT DEFAULT '', tags TEXT DEFAULT '[]', sources TEXT DEFAULT '[]', notes TEXT DEFAULT '',
                post_at TEXT DEFAULT '', event_at TEXT DEFAULT '', engine_ref TEXT DEFAULT '{}',
                asset_dir TEXT DEFAULT '', thumb_path TEXT DEFAULT '', video_path TEXT DEFAULT '',
                external_url TEXT DEFAULT '', youtube_id TEXT DEFAULT '', quality_status TEXT DEFAULT 'unknown',
                rights_status TEXT DEFAULT 'unknown', rights_manifest TEXT DEFAULT '{}',
                render_digest TEXT DEFAULT '', approved_digest TEXT DEFAULT '', cost REAL DEFAULT NULL,
                cost_cap REAL DEFAULT 3, error TEXT DEFAULT '', imported_key TEXT UNIQUE,
                revision INTEGER DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS studio_tasks(id TEXT PRIMARY KEY, title TEXT NOT NULL, channel_id INTEGER,
                video_id TEXT, assignee TEXT DEFAULT '', priority TEXT DEFAULT 'normal', due_at TEXT DEFAULT '',
                done INTEGER DEFAULT 0, revision INTEGER DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(channel_id) REFERENCES studio_channels(project_id),
                FOREIGN KEY(video_id) REFERENCES studio_videos(id));
            CREATE TABLE IF NOT EXISTS studio_activity(id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL,
                action TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS studio_jobs(id TEXT PRIMARY KEY, kind TEXT NOT NULL, video_id TEXT,
                status TEXT DEFAULT 'queued', progress REAL DEFAULT 0, message TEXT DEFAULT 'En attente',
                payload TEXT DEFAULT '{}', result TEXT DEFAULT '{}', error TEXT DEFAULT '', lease_until TEXT DEFAULT '',
                cancel_requested INTEGER DEFAULT 0, owner TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(video_id) REFERENCES studio_videos(id));
            CREATE UNIQUE INDEX IF NOT EXISTS studio_active_job ON studio_jobs(video_id)
                WHERE status IN ('queued','running') AND video_id IS NOT NULL;
            CREATE TABLE IF NOT EXISTS studio_chat(id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL,
                content TEXT NOT NULL, actor TEXT DEFAULT '', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS studio_login_attempts(ip TEXT NOT NULL, username TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS studio_oauth(state TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                channel_id INTEGER NOT NULL, expires_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS studio_channel_snapshots(channel_id INTEGER NOT NULL REFERENCES studio_channels(project_id),
                youtube_id TEXT NOT NULL, captured_at TEXT NOT NULL, views INTEGER,
                subscribers INTEGER, videos INTEGER, PRIMARY KEY(channel_id,captured_at));
            CREATE INDEX IF NOT EXISTS studio_channel_history ON studio_channel_snapshots(channel_id,youtube_id,captured_at);
            CREATE TABLE IF NOT EXISTS studio_channel_sync(channel_id INTEGER PRIMARY KEY REFERENCES studio_channels(project_id),
                checked_at TEXT NOT NULL DEFAULT '', lease_until TEXT NOT NULL DEFAULT '',
                lease_id TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '',
                videos_json TEXT NOT NULL DEFAULT '[]', videos_at TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS studio_worker(id INTEGER PRIMARY KEY CHECK(id=1), heartbeat TEXT DEFAULT '',
                message TEXT DEFAULT 'Hors ligne');
            INSERT OR IGNORE INTO studio_worker(id) VALUES(1);
            CREATE INDEX IF NOT EXISTS studio_schedule ON studio_videos(post_at,status);
            CREATE INDEX IF NOT EXISTS studio_task_due ON studio_tasks(done,due_at);
            CREATE TRIGGER IF NOT EXISTS studio_slot_insert BEFORE INSERT ON studio_videos
            WHEN NEW.post_at!='' AND NEW.status NOT IN ('published','reported')
            BEGIN SELECT RAISE(ABORT,'schedule_conflict') WHERE EXISTS(
                SELECT 1 FROM studio_videos WHERE channel_id=NEW.channel_id AND post_at=NEW.post_at
                AND status NOT IN ('published','reported')); END;
            CREATE TRIGGER IF NOT EXISTS studio_slot_update BEFORE UPDATE OF post_at,channel_id,status ON studio_videos
            WHEN NEW.post_at!='' AND NEW.status NOT IN ('published','reported')
            BEGIN SELECT RAISE(ABORT,'schedule_conflict') WHERE EXISTS(
                SELECT 1 FROM studio_videos WHERE channel_id=NEW.channel_id AND post_at=NEW.post_at
                AND id!=NEW.id AND status NOT IN ('published','reported')); END;
            """)
            c.execute("BEGIN IMMEDIATE")
            # Only additive changes to legacy projects; never run the destructive old message migration.
            columns = {
                r["name"] for r in c.execute("PRAGMA table_info(delamain_projects)")
            }
            for name, spec in {
                "description": "TEXT DEFAULT ''",
                "yt_refresh_token": "TEXT DEFAULT ''",
                "yt_channel_title": "TEXT DEFAULT ''",
                "yt_channel_id": "TEXT DEFAULT ''",
                "proxy": "TEXT DEFAULT ''",
                "cadence_days": "TEXT DEFAULT '1'",
                "post_time": "TEXT DEFAULT '18:00'",
                "video_tool": "TEXT DEFAULT ''",
                "autonomy": "TEXT DEFAULT 'manual'",
                "lang": "TEXT DEFAULT 'en'",
                "group_id": "INTEGER DEFAULT NULL",
            }.items():
                if name not in columns:
                    c.execute(f"ALTER TABLE delamain_projects ADD COLUMN {name} {spec}")
            channel_columns = {
                r["name"] for r in c.execute("PRAGMA table_info(studio_channels)")
            }
            if "template_key" not in channel_columns:
                c.execute(
                    "ALTER TABLE studio_channels ADD COLUMN template_key TEXT DEFAULT ''"
                )
                c.execute(
                    "UPDATE studio_channels SET template_key=key WHERE key IN ('mma_en','football_en','boxing_en','oddly_specific_en','oddly_expensive_en','oddly_things_en','survivors_account','frontier_blood')"
                )
            if "responsible_id" not in channel_columns:
                c.execute(
                    "ALTER TABLE studio_channels ADD COLUMN responsible_id TEXT REFERENCES studio_users(id)"
                )
            if "cadence_anchor" not in channel_columns:
                c.execute(
                    "ALTER TABLE studio_channels ADD COLUMN cadence_anchor TEXT DEFAULT ''"
                )
            if "publication_mode" not in channel_columns:
                c.execute(
                    "ALTER TABLE studio_channels ADD COLUMN publication_mode TEXT NOT NULL DEFAULT 'scheduled'"
                )
                # Existing sports channels follow the news, without inventing a daily slot.
                c.execute(
                    "UPDATE studio_channels SET publication_mode='news',revision=revision+1,updated_at=? WHERE key IN ('mma_en','football_en')",
                    (now(),),
                )
            if "retired" not in channel_columns:
                c.execute(
                    "ALTER TABLE studio_channels ADD COLUMN retired INTEGER NOT NULL DEFAULT 0"
                )
            chat_columns = {
                r["name"] for r in c.execute("PRAGMA table_info(studio_chat)")
            }
            if "attachments" not in chat_columns:
                c.execute(
                    "ALTER TABLE studio_chat ADD COLUMN attachments TEXT NOT NULL DEFAULT '[]'"
                )
            c.execute(
                "UPDATE studio_channels SET cadence_anchor=? WHERE cadence_anchor=''",
                (datetime.now(ZoneInfo("Europe/Paris")).date().isoformat(),),
            )
            c.execute("INSERT OR IGNORE INTO studio_schema VALUES(5,?)", (now(),))
            c.execute("INSERT OR IGNORE INTO studio_schema VALUES(1,?)", (now(),))
            c.execute("INSERT OR IGNORE INTO studio_schema VALUES(2,?)", (now(),))
            c.execute("INSERT OR IGNORE INTO studio_schema VALUES(6,?)", (now(),))
            c.execute("INSERT OR IGNORE INTO studio_schema VALUES(7,?)", (now(),))
            c.execute("INSERT OR IGNORE INTO studio_schema VALUES(8,?)", (now(),))
        self.retire_defaults()

    def retire_defaults(self):
        """Ring Dispatch was discontinued by the owner; never reimport it as active."""
        row = self.one(
            "SELECT project_id,revision FROM studio_channels WHERE key='boxing_en' AND retired=0"
        )
        if row:
            self.retire_channel(row["project_id"], row["revision"])

    def retire_channel(self, channel_id, revision):
        """Remove a channel from the active studio, retaining its historical records."""
        with self.db() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT revision,retired FROM studio_channels WHERE project_id=?",
                (channel_id,),
            ).fetchone()
            if not row:
                raise ValueError("Chaîne introuvable.")
            if row["retired"]:
                return
            if row["revision"] != revision:
                raise Conflict("Cette chaîne a changé. Actualise avant de la retirer.")
            c.execute(
                "UPDATE studio_channels SET retired=1,paused=1,enabled=0,responsible_id=NULL,revision=revision+1,updated_at=? WHERE project_id=?",
                (now(), channel_id),
            )
            from studio.channel_stats import clear

            clear(c, channel_id)
            c.execute(
                "UPDATE studio_jobs SET cancel_requested=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,message='Chaîne retirée du studio',updated_at=? WHERE status IN ('queued','running') AND (video_id IN (SELECT id FROM studio_videos WHERE channel_id=?) OR (kind='news_scan' AND json_extract(payload,'$.channel_id')=?))",
                (now(), channel_id, channel_id),
            )
            if c.execute(
                "SELECT 1 FROM sqlite_master WHERE name='studio_news_config'"
            ).fetchone():
                c.execute(
                    "UPDATE studio_news_config SET enabled=0,revision=revision+1 WHERE channel_id=?",
                    (channel_id,),
                )
                c.execute(
                    "UPDATE studio_jobs SET cancel_requested=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,message='Chaîne retirée du studio',updated_at=? WHERE status IN ('queued','running') AND kind='news_prepare' AND json_extract(payload,'$.item_id') IN (SELECT id FROM studio_news_items WHERE channel_id=?)",
                    (now(), channel_id),
                )

    def channels(self):
        # Deliberately enumerate safe columns: refresh tokens and proxies never leave the server.
        return self.rows(
            """SELECT p.id,p.name,p.channel_id AS handle,p.niche,p.lang,p.autonomy,
            p.cadence_days,p.post_time,p.yt_channel_title,p.yt_channel_id,
            CASE WHEN p.yt_refresh_token!='' THEN 1 ELSE 0 END AS connected,
            s.key,s.format,s.accent,s.initials,s.target_stock,s.freshness_hours,s.enabled,s.paused,
            s.budget,s.instructions,s.template_key,s.responsible_id,s.cadence_anchor,s.publication_mode,s.revision,s.updated_at
            FROM studio_channels s JOIN delamain_projects p ON p.id=s.project_id WHERE s.retired=0 ORDER BY p.id"""
        )

    def channel(self, channel_id):
        return next((c for c in self.channels() if c["id"] == channel_id), None)

    def add_channel(self, data):
        with self.db() as c:
            cur = c.execute(
                """INSERT INTO delamain_projects(name,channel_id,niche,lang,autonomy,cadence_days,post_time,video_tool)
                VALUES(?,?,?,?,?,?,?,?)""",
                (
                    data["name"],
                    data.get("handle", ""),
                    data.get("niche", ""),
                    data.get("lang", "en"),
                    data.get("autonomy", "manual"),
                    str(data.get("cadence_days", 1)),
                    data.get("post_time", "18:00"),
                    data["format"],
                ),
            )
            pid = cur.lastrowid
            c.execute(
                """INSERT INTO studio_channels(project_id,key,format,accent,initials,instructions,cadence_anchor,publication_mode,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    pid,
                    data.get("key") or uid(),
                    data["format"],
                    data.get("accent", "#00e5e5"),
                    data.get("initials")
                    or "".join(x[0] for x in data["name"].split())[:3].upper(),
                    data.get("instructions", ""),
                    datetime.now(ZoneInfo("Europe/Paris")).date().isoformat(),
                    "news" if data["format"] == "news" else "scheduled",
                    now(),
                ),
            )
            return pid

    def update_channel(self, channel_id, data, revision):
        with self.db() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT revision FROM studio_channels WHERE project_id=?", (channel_id,)
            ).fetchone()
            if not row or row["revision"] != revision:
                raise Conflict(
                    "Cette chaîne a été modifiée. Actualise avant de réessayer."
                )
            core = {
                k: v
                for k, v in data.items()
                if k
                in {
                    "name",
                    "handle",
                    "niche",
                    "lang",
                    "autonomy",
                    "cadence_days",
                    "post_time",
                }
            }
            core = {("channel_id" if k == "handle" else k): v for k, v in core.items()}
            if core:
                c.execute(
                    "UPDATE delamain_projects SET "
                    + ",".join(k + "=?" for k in core)
                    + " WHERE id=?",
                    [*core.values(), channel_id],
                )
            extra = {
                k: v
                for k, v in data.items()
                if k
                in {
                    "target_stock",
                    "freshness_hours",
                    "enabled",
                    "paused",
                    "budget",
                    "instructions",
                    "template_key",
                    "responsible_id",
                    "cadence_anchor",
                    "publication_mode",
                }
            }
            c.execute(
                "UPDATE studio_channels SET "
                + "".join(k + "=?," for k in extra)
                + "revision=revision+1,updated_at=? WHERE project_id=?",
                [*extra.values(), now(), channel_id],
            )

    def settings(self):
        return self.one("SELECT * FROM studio_settings WHERE id=1")

    def log(self, actor, action, message):
        with self.db() as c:
            c.execute(
                "INSERT INTO studio_activity(actor,action,message,created_at) VALUES(?,?,?,?)",
                (actor, action, message[:1500], now()),
            )

    def videos(self):
        out = self.rows(
            "SELECT v.* FROM studio_videos v JOIN studio_channels c ON c.project_id=v.channel_id WHERE c.retired=0 ORDER BY v.created_at DESC"
        )
        for v in out:
            for key in ("sources", "tags", "engine_ref", "rights_manifest"):
                v[key] = json.loads(v[key])
        return out

    def video(self, video_id):
        return next((v for v in self.videos() if v["id"] == video_id), None)

    def add_video(self, data):
        data = dict(
            data,
            id=data.get("id") or uid(),
            created_at=data.get("created_at") or now(),
            updated_at=now(),
        )
        allowed = {
            "id",
            "channel_id",
            "title",
            "status",
            "minutes",
            "script",
            "description",
            "tags",
            "sources",
            "notes",
            "post_at",
            "event_at",
            "engine_ref",
            "asset_dir",
            "thumb_path",
            "video_path",
            "external_url",
            "youtube_id",
            "quality_status",
            "rights_status",
            "rights_manifest",
            "render_digest",
            "approved_digest",
            "cost",
            "cost_cap",
            "error",
            "imported_key",
            "created_at",
            "updated_at",
        }
        data = {
            k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
            for k, v in data.items()
            if k in allowed
        }
        with self.db() as c:
            c.execute("BEGIN IMMEDIATE")
            if data.get("imported_key"):
                existing = c.execute(
                    "SELECT id FROM studio_videos WHERE imported_key=?",
                    (data["imported_key"],),
                ).fetchone()
                if existing:
                    return existing["id"]
            c.execute(
                "INSERT INTO studio_videos("
                + ",".join(data)
                + ") VALUES("
                + ",".join("?" for _ in data)
                + ")",
                list(data.values()),
            )
        return data["id"]

    def update(self, table, item_id, data, revision=None):
        if table not in {"studio_videos", "studio_tasks"}:
            raise ValueError("Table non autorisée")
        data = {
            k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
            for k, v in data.items()
        }
        with self.db() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                f"SELECT revision FROM {table} WHERE id=?", (item_id,)
            ).fetchone()
            if not row:
                raise ValueError("Élément introuvable")
            if revision is not None and row["revision"] != revision:
                raise Conflict(
                    "Cet élément a été modifié par quelqu’un. Actualise avant de réessayer."
                )
            c.execute(
                f"UPDATE {table} SET "
                + "".join(k + "=?," for k in data)
                + "revision=revision+1,updated_at=? WHERE id=?",
                [*data.values(), now(), item_id],
            )

    def enqueue(self, kind, video_id=None, payload=None):
        with self.db() as c:
            c.execute("BEGIN IMMEDIATE")
            if video_id:
                active = c.execute(
                    "SELECT id FROM studio_jobs WHERE video_id=? AND status IN ('queued','running')",
                    (video_id,),
                ).fetchone()
                if active:
                    return active["id"]
            job_id = uid()
            c.execute(
                "INSERT INTO studio_jobs(id,kind,video_id,payload,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (
                    job_id,
                    kind,
                    video_id,
                    json.dumps(payload or {}, ensure_ascii=False),
                    now(),
                    now(),
                ),
            )
            return job_id

    def claim(self, owner):
        with self.db() as c:
            c.execute("BEGIN IMMEDIATE")
            if (ROOT / "work/studio/development-maintenance.json").exists():
                return None
            # Recover only expired leases. Every running process renews its lease independently of progress.
            c.execute(
                "UPDATE studio_jobs SET status=CASE WHEN cancel_requested=1 THEN 'cancelled' ELSE 'queued' END,owner='' WHERE status='running' AND lease_until<?",
                (now(),),
            )
            if c.execute(
                "SELECT id FROM studio_jobs WHERE status='running'"
            ).fetchone():
                return None
            j = c.execute(
                "SELECT * FROM studio_jobs WHERE status='queued' AND cancel_requested=0 ORDER BY created_at LIMIT 1"
            ).fetchone()
            if not j:
                return None
            lease = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat()
            c.execute(
                "UPDATE studio_jobs SET status='running',owner=?,lease_until=?,updated_at=? WHERE id=?",
                (owner, lease, now(), j["id"]),
            )
            return dict(j)

    def users(self):
        return self.rows(
            "SELECT id,name,username,role,created_at FROM studio_users ORDER BY created_at"
        )
