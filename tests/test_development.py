"""Actual git, Python tests, Node build, HTTP reload, rollback and request boundaries."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch, create_autospec

from studio.development import (
    Config,
    apply_edits,
    check_setup,
    configuration,
    enqueue,
    execute,
    git,
    health,
    initialize,
    maintenance_path,
    recover,
    revision,
    run_once,
    safe_file,
    update,
)
from studio.store import Store, now, uid
from studio.web import create_app


@contextmanager
def host(root, *, fail_new=False):
    original = revision(root)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            commit = revision(root)
            # Executes the changed source on the simulated application host.
            namespace = {}
            exec((root / "services/feature.py").read_text(), namespace)
            if fail_new and commit != original:
                self.send_response(503)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"status": "ok", "revision": commit, "label": namespace["LABEL"]}
                ).encode()
            )

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/health/studio"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class DevelopmentPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        parent = Path(self.tmp.name)
        self.root = parent / "live"
        self.root.mkdir()
        self.remote = parent / "remote.git"
        git(parent, "init", "--bare", str(self.remote))
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Fixture")
        git(self.root, "config", "user.email", "fixture@example.invalid")
        (self.root / ".gitignore").write_text(
            "work/\n*.db*\n__pycache__/\nfrontend/node_modules/\n.env\n"
        )
        (self.root / "services").mkdir()
        (self.root / "services/feature.py").write_text(
            "LABEL = 'Original'\n\ndef add(a, b):\n    return a + b\n"
        )
        (self.root / "tests").mkdir()
        (self.root / "tests/test_feature.py").write_text(
            "import unittest\nfrom services.feature import add, LABEL\nclass TestFeature(unittest.TestCase):\n def test_existing_function(self): self.assertEqual(add(2, 3), 5)\n def test_label(self): self.assertTrue(LABEL)\n"
        )
        (self.root / "frontend").mkdir()
        (self.root / "frontend/package.json").write_text(
            json.dumps(
                {
                    "name": "release-fixture",
                    "version": "1.0.0",
                    "scripts": {"build": "node build.cjs"},
                }
            )
        )
        (self.root / "frontend/package-lock.json").write_text(
            json.dumps(
                {
                    "name": "release-fixture",
                    "version": "1.0.0",
                    "lockfileVersion": 3,
                    "packages": {"": {"name": "release-fixture", "version": "1.0.0"}},
                }
            )
        )
        (self.root / "frontend/build.cjs").write_text(
            "const fs = require('fs'); fs.mkdirSync('../static/studio', {recursive:true}); fs.writeFileSync('../static/studio/index.html', '<h1>Compiled application</h1>'); console.log('Frontend compiled');"
        )
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "Initial fixture")
        git(self.root, "remote", "add", "origin", str(self.remote))
        git(self.root, "push", "origin", "main")
        self.base = revision(self.root)
        self.store = Store(parent / "database.db")
        self.store.migrate()
        initialize(self.store)
        with self.store.db() as c:
            c.execute(
                "INSERT INTO studio_users VALUES('owner','Owner','owner','unused','owner',?)",
                (now(),),
            )
        self.owner = self.store.users()[0]
        self.npm = subprocess.check_output(["which", "npm"], text=True).strip()
        self.config = Config(root=self.root, enabled=True, npm=self.npm)
        self.env = patch.dict(
            os.environ,
            {
                "AI_API_KEY": "fixture-private-provider-secret",
                "AI_BASE_URL": "https://fixture.invalid",
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def job(self):
        job = uid()
        with self.store.db() as c:
            c.execute(
                "INSERT INTO studio_development(id,user_id,request,created_at,updated_at) VALUES(?,?,?,?,?)",
                (job, "owner", "Change the original label", now(), now()),
            )
        return self.store.one("SELECT * FROM studio_development WHERE id=?", (job,))

    def provider(self, broken=False, before_done=None):
        operations = iter(
            [
                {"reads": [{"path": "services/feature.py", "start": 1, "end": 10}]},
                {
                    "edits": [
                        {
                            "path": "services/feature.py",
                            "before": (
                                "return a + b" if broken else "LABEL = 'Original'"
                            ),
                            "after": "return 0" if broken else "LABEL = 'Updated'",
                        }
                    ]
                },
                {"done": True, "summary": "Libellé mis à jour"},
            ]
        )

        def call(*args, **kwargs):
            op = next(operations, None)
            if op is None:
                raise ValueError("L’agent n’a pas corrigé les tests échoués.")
            if op.get("done") and before_done:
                before_done()
            return op

        from studio.development import call_ai

        return create_autospec(call_ai, side_effect=call)

    def test_real_edit_test_build_git_deploy_and_terminal_replay(self):
        with host(self.root) as url:
            self.config.health_url = url
            job = self.job()
            run_once(self.store, self.config, provider=self.provider())
            result = self.store.one(
                "SELECT * FROM studio_development WHERE id=?", (job["id"],)
            )
            self.assertEqual(result["status"], "done", result["error"])
            self.assertIn("Libellé", result["summary"])
            self.assertIn("Ran 2 tests", result["checks"])
            self.assertIn("Frontend compiled", result["checks"])
            self.assertIn(
                "LABEL = 'Updated'", (self.root / "services/feature.py").read_text()
            )
            self.assertTrue((self.root / "static/studio/index.html").exists())
            self.assertEqual(revision(self.root), result["commit_id"])
            self.assertEqual(
                git(self.root, "ls-remote", "origin", "main").split()[0],
                result["commit_id"],
            )
            self.assertTrue((self.root / "tmp/restart.txt").exists())
            self.assertTrue(
                (
                    self.root
                    / "work/studio/backups"
                    / ("before-release-" + job["id"] + ".db")
                ).exists()
            )
            self.assertFalse(maintenance_path(self.root).exists())
            run_once(
                self.store,
                self.config,
                provider=lambda *a, **k: self.fail("Terminal jobs must not repeat"),
            )
            self.assertEqual(len(self.store.rows("SELECT * FROM studio_chat")), 1)

    def test_baseline_failure_never_deploys_or_pushes_main(self):
        with host(self.root) as url:
            self.config.health_url = url
            job = self.job()
            run_once(self.store, self.config, provider=self.provider(broken=True))
            result = self.store.one(
                "SELECT * FROM studio_development WHERE id=?", (job["id"],)
            )
            self.assertEqual(result["status"], "failed")
            self.assertIn("tests échoués", result["error"])
            self.assertIn("AssertionError", result["checks"])
            self.assertEqual(revision(self.root), self.base)
            self.assertEqual(
                git(self.root, "ls-remote", "origin", "main").split()[0], self.base
            )
            self.assertFalse((self.root / "tmp/restart.txt").exists())

    def test_failed_reload_restores_previous_code_and_preserves_private_data(self):
        (self.root / ".env").write_text("PRIVATE=keep-me\n")
        private = self.root / "work/video.txt"
        private.parent.mkdir()
        private.write_text("Existing video")
        with host(self.root, fail_new=True) as url, patch(
            "studio.development.time.sleep"
        ):
            self.config.health_url = url
            job = self.job()
            run_once(self.store, self.config, provider=self.provider())
            result = self.store.one(
                "SELECT * FROM studio_development WHERE id=?", (job["id"],)
            )
            self.assertEqual(result["status"], "failed", result["error"])
            self.assertEqual(revision(self.root), self.base)
            self.assertEqual((self.root / ".env").read_text(), "PRIVATE=keep-me\n")
            self.assertEqual(private.read_text(), "Existing video")
            self.assertFalse(maintenance_path(self.root).exists())
            self.assertEqual(
                git(self.root, "ls-remote", "origin", "main").split()[0], self.base
            )

    def test_remote_advance_does_not_overwrite_another_contributor(self):
        def advance():
            other = self.root.parent / "other"
            git(self.root.parent, "clone", str(self.remote), str(other))
            git(other, "checkout", "main")
            (other / "README.md").write_text("Concurrent colleague change")
            git(other, "add", ".")
            git(
                other,
                "-c",
                "user.name=Other",
                "-c",
                "user.email=other@example.invalid",
                "commit",
                "-m",
                "Concurrent update",
            )
            git(other, "push", "origin", "main")

        with host(self.root) as url:
            self.config.health_url = url
            job = self.job()
            run_once(
                self.store, self.config, provider=self.provider(before_done=advance)
            )
            result = self.store.one(
                "SELECT * FROM studio_development WHERE id=?", (job["id"],)
            )
            self.assertEqual(result["status"], "failed")
            self.assertIn("avancé", result["error"])
            self.assertEqual(revision(self.root), self.base)
            self.assertNotEqual(
                git(self.root, "ls-remote", "origin", "main").split()[0], self.base
            )
            self.assertFalse(maintenance_path(self.root).exists())

    def test_private_paths_symlinks_and_security_files_are_unavailable(self):
        for path in [
            ".env",
            "../other.py",
            "/tmp/other.py",
            "studio/web.py",
            "studio/security.py",
            "frontend/src/private-access.tsx",
            "studio/development.py",
            "tests/test_feature.py",
            "frontend/package.json",
        ]:
            with self.assertRaises(ValueError):
                safe_file(self.root, path)
        (self.root / "services/link.py").symlink_to(self.root / ".env")
        with self.assertRaises(ValueError):
            safe_file(self.root, "services/link.py")
        with self.assertRaises(ValueError):
            apply_edits(
                self.root,
                {
                    "edits": [
                        {
                            "path": "services/feature.py",
                            "before": "Original",
                            "after": os.environ["AI_API_KEY"],
                        }
                    ]
                },
                {"services/feature.py"},
            )

    def test_write_requires_read_and_unique_exact_passage(self):
        op = {
            "edits": [
                {
                    "path": "services/feature.py",
                    "before": "Original",
                    "after": "Changed",
                }
            ]
        }
        with self.assertRaises(ValueError):
            apply_edits(self.root, op, set())
        op["edits"][0]["before"] = "a"
        with self.assertRaises(ValueError):
            apply_edits(self.root, op, {"services/feature.py"})

    def test_interrupted_code_work_is_not_automatically_replayed(self):
        job = self.job()
        update(self.store, job["id"], status="coding")
        recover(self.store, self.config)
        result = self.store.one(
            "SELECT * FROM studio_development WHERE id=?", (job["id"],)
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(revision(self.root), self.base)

    def test_credentials_are_removed_from_tests_and_build(self):
        from studio.development import command

        output = command(
            [
                sys.executable,
                "-c",
                "import os; assert 'AI_API_KEY' not in os.environ; assert 'DB_PATH' not in os.environ; print('isolated')",
            ],
            self.root,
        )
        self.assertEqual(output, "isolated")

    def test_invalid_batch_never_partially_applies_edits(self):
        original = (self.root / "services/feature.py").read_text()
        with self.assertRaises(ValueError):
            apply_edits(
                self.root,
                {
                    "edits": [
                        {
                            "path": "services/feature.py",
                            "before": "Original",
                            "after": "Changed",
                        },
                        {
                            "path": "services/feature.py",
                            "before": "Missing unique passage",
                            "after": "replacement",
                        },
                    ]
                },
                {"services/feature.py"},
            )
        self.assertEqual((self.root / "services/feature.py").read_text(), original)

    def test_recovery_rolls_back_a_loaded_but_unpublished_release(self):
        job = self.job()
        (self.root / "services/feature.py").write_text("LABEL = 'Unpublished'\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "Interrupted fixture release")
        commit = revision(self.root)
        update(
            self.store,
            job["id"],
            status="deploying",
            base_commit=self.base,
            commit_id=commit,
        )
        marker = maintenance_path(self.root)
        marker.parent.mkdir(parents=True)
        marker.write_text(
            json.dumps({"id": job["id"], "previous": self.base, "commit": commit})
        )
        with host(self.root) as url:
            self.config.health_url = url
            recover(self.store, self.config)
        self.assertEqual(revision(self.root), self.base)
        self.assertFalse(marker.exists())
        self.assertEqual(
            self.store.one(
                "SELECT status FROM studio_development WHERE id=?", (job["id"],)
            )["status"],
            "failed",
        )

    def test_recovery_recognizes_an_already_published_healthy_release(self):
        job = self.job()
        (self.root / "services/feature.py").write_text("LABEL = 'Published'\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "Published fixture release")
        commit = revision(self.root)
        git(self.root, "push", "origin", "main")
        update(
            self.store,
            job["id"],
            status="deploying",
            base_commit=self.base,
            commit_id=commit,
        )
        marker = maintenance_path(self.root)
        marker.parent.mkdir(parents=True)
        marker.write_text(
            json.dumps({"id": job["id"], "previous": self.base, "commit": commit})
        )
        with host(self.root) as url:
            self.config.health_url = url
            recover(self.store, self.config)
        self.assertEqual(revision(self.root), commit)
        self.assertFalse(marker.exists())
        self.assertEqual(
            self.store.one(
                "SELECT status FROM studio_development WHERE id=?", (job["id"],)
            )["status"],
            "done",
        )
        self.assertEqual(
            (self.root / "work/studio/runtime-revision").read_text(), commit
        )

    def test_failure_after_successful_push_preserves_receipt_and_recovers_success(self):
        original_write = Path.write_text
        failed = False

        def write(path, *args, **kwargs):
            nonlocal failed
            if path == self.root / "work/studio/runtime-revision" and not failed:
                failed = True
                raise OSError("Simulated finalization interruption")
            return original_write(path, *args, **kwargs)

        with host(self.root) as url:
            self.config.health_url = url
            job = self.job()
            with patch.object(Path, "write_text", write):
                run_once(self.store, self.config, provider=self.provider())
            self.assertTrue(failed)
            commit = revision(self.root)
            self.assertNotEqual(commit, self.base)
            self.assertEqual(
                git(self.root, "ls-remote", "origin", "main").split()[0], commit
            )
            self.assertTrue(maintenance_path(self.root).exists())
            recover(self.store, self.config)
            self.assertFalse(maintenance_path(self.root).exists())
            self.assertEqual(
                self.store.one(
                    "SELECT status FROM studio_development WHERE id=?", (job["id"],)
                )["status"],
                "done",
            )

    def test_setup_proves_remote_and_running_revision_before_enabling(self):
        with host(self.root) as url:
            self.config.health_url = url
            check_setup(self.store, self.config)
            self.assertTrue(configuration(self.store, self.config)["verified"])
            self.assertFalse(configuration(self.store, self.config)["ready"])
            run_once(self.store, self.config)
            self.assertTrue(configuration(self.store, self.config)["ready"])
            with self.assertRaises(ValueError):
                health(url, "wrong-version")


class DeveloperResponseTests(unittest.TestCase):
    def test_identical_transport_duplicates_are_applied_only_once(self):
        from studio.development import call_ai

        operation = {"search": "tâches"}
        with patch(
            "services.ai.chat", return_value=json.dumps(operation) * 2
        ) as request:
            self.assertEqual(call_ai([]), operation)
        self.assertTrue(request.call_args.kwargs["json_mode"])
        self.assertEqual(request.call_args.kwargs["max_tokens"], 12000)

    def test_conflicting_or_malformed_responses_do_not_execute(self):
        from studio.development import call_ai

        for raw in ['{"search":"one"}{"search":"two"}', '{"done":tru', "[]garbage"]:
            with self.subTest(raw=raw), patch("services.ai.chat", return_value=raw):
                with self.assertRaises(ValueError):
                    call_ai([])


class DevelopmentApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(
            dict(
                TESTING=True,
                PREVIEW=True,
                MFA_REQUIRED=False,
                SECRET_KEY="fixture",
                DB_PATH=Path(self.tmp.name) / "studio.db",
                WORKER_ENABLED=False,
                IMPORT_PRODUCTIONS=False,
            )
        )
        self.store = self.app.extensions["studio_store"]
        self.client = self.app.test_client()
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.ready = patch(
            "studio.development.configuration", return_value={"ready": True}
        )

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, path="/chat", **data):
        return self.client.post(
            "/api/studio" + path,
            json={
                "message": "Ajoute un compteur au site",
                "mode": "development",
                **data,
            },
            headers={"X-CSRF-Token": self.csrf},
        )

    def test_explicit_chat_mode_queues_real_development_using_session_identity(self):
        self.app.config["PREVIEW"] = False
        with self.ready:
            response = self.post(user_id="collegue", actor="Kanye")
            self.assertEqual(response.status_code, 202)
            change = self.store.one("SELECT * FROM studio_development")
            self.assertEqual(change["user_id"], "drylow")
            self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])
            self.assertEqual(
                json.loads(
                    self.store.rows("SELECT * FROM studio_chat")[-1]["attachments"]
                )[0]["kind"],
                "development",
            )
            self.assertEqual(self.post().status_code, 409)

    def test_role_csrf_and_preview_are_real_guards(self):
        self.assertEqual(self.post().status_code, 400)
        self.assertEqual(
            self.client.post(
                "/api/studio/chat", json={"message": "change", "mode": "development"}
            ).status_code,
            403,
        )
        self.app.config["PREVIEW"] = False
        with self.client.session_transaction() as session:
            from studio.security import issue

            with self.app.app_context():
                issue(self.store, "collegue", container=session)
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        with self.ready:
            self.assertEqual(self.post().status_code, 403)
            self.assertEqual(
                self.client.post(
                    "/api/studio/development",
                    json={"request": "Change something"},
                    headers={"X-CSRF-Token": self.csrf},
                ).status_code,
                403,
            )
        self.assertEqual(self.store.rows("SELECT * FROM studio_development"), [])

    def test_health_reports_startup_version_and_no_secrets(self):
        self.app.config["CODE_REVISION"] = "loaded-version"
        data = self.client.get("/health/studio").json
        self.assertEqual(data, {"status": "ok", "revision": "loaded-version"})

    def test_only_queued_changes_can_be_cancelled(self):
        self.app.config["PREVIEW"] = False
        with self.ready:
            jid = self.post().json["development_id"]
        self.assertEqual(
            self.client.post(
                f"/api/studio/development/{jid}/cancel",
                json={},
                headers={"X-CSRF-Token": self.csrf},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                f"/api/studio/development/{jid}/cancel",
                json={},
                headers={"X-CSRF-Token": self.csrf},
            ).status_code,
            409,
        )

    def test_maintenance_blocks_mutations_and_new_production_claims(self):
        root = Path(self.tmp.name)
        marker = root / "work/studio/development-maintenance.json"
        marker.parent.mkdir(parents=True)
        marker.write_text("{}")
        self.app.config["DEVELOPMENT_MAINTENANCE_PATH"] = str(marker)
        self.assertEqual(self.post().status_code, 503)
        self.assertEqual(self.client.get("/api/studio/workspace").status_code, 200)
        self.store.enqueue("agent", payload={"message": "test"})
        with patch("studio.store.ROOT", root):
            self.assertIsNone(self.store.claim("fixture"))
        self.assertEqual(
            self.store.rows("SELECT * FROM studio_jobs")[0]["status"], "queued"
        )
