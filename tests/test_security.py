"""Exercise the private gate, hostile direct requests."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from studio import security
from studio.web import create_app

PASSWORD = "a private password phrase for Drylow"
OTHER_PASSWORD = "a different private password for Kanye"


class PrivateGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ, {"STUDIO_BOOTSTRAP_TOKEN": "private-installation-fixture"}
        )
        self.env.start()
        self.clock = patch(
            "studio.security.time.time", return_value=int(time.time() // 30) * 30 + 5
        )
        self.time = self.clock.start()
        self.config = dict(
            TESTING=True,
            SECRET_KEY="private-session-fixture-" + "x" * 40,
            DB_PATH=Path(self.tmp.name) / "gate.db",
            PREVIEW=False,
            HOSTED=False,
            WORKER_ENABLED=False,
            IMPORT_PRODUCTIONS=False,
        )
        self.app = create_app(self.config)
        self.store = self.app.extensions["studio_store"]
        self.client = self.app.test_client()
        response = self.post(
            self.client,
            "/setup",
            {
                "token": "private-installation-fixture",
                "name": "Drylow",
                "username": "drylow",
                "password": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 200, response.json)
        self.user_id = self.store.users()[0]["id"]

    def tearDown(self):
        self.clock.stop()
        self.env.stop()
        self.tmp.cleanup()

    def post(self, client, path, body, **kwargs):
        boot = client.get("/api/studio/bootstrap").json
        return client.post(
            "/api/studio" + path,
            json=body,
            headers={"X-CSRF-Token": boot["csrf"]},
            **kwargs
        )

    def challenge(self, username="drylow", password=PASSWORD):
        client = self.app.test_client()
        self.assertEqual(
            self.post(
                client, "/login", {"username": username, "password": password}
            ).status_code,
            200,
        )
        return client

    def advance(self):
        self.time.return_value += 31

    def test_logout_revokes_a_stolen_copy_of_the_cookie(self):
        cookie = self.client.get_cookie("session").value
        self.assertEqual(self.post(self.client, "/logout", {}).status_code, 200)
        thief = self.app.test_client()
        thief.set_cookie("session", cookie)
        self.assertEqual(thief.get("/api/studio/workspace").status_code, 401)

    def test_cookie_identity_cannot_be_changed_to_another_user(self):
        self.post(
            self.client,
            "/users",
            {"name": "Kanye", "username": "kanye", "password": OTHER_PASSWORD},
        )
        other = next(u for u in self.store.users() if u["username"] == "kanye")
        with self.client.session_transaction() as container:
            container["studio_user"] = other["id"]
        self.assertEqual(self.client.get("/api/studio/workspace").status_code, 401)
        # Even a correctly signed cookie needs a real, bound server-side session.
        forged = self.app.session_interface.get_signing_serializer(self.app).dumps(
            {"studio_user": self.user_id, "studio_sid": "invented", "csrf": "invented"}
        )
        thief = self.app.test_client()
        thief.set_cookie("session", forged)
        self.assertEqual(thief.get("/api/studio/workspace").status_code, 401)

    def test_absolute_and_idle_session_expiry_are_enforced_on_server(self):
        with self.store.db() as c:
            c.execute(
                "UPDATE studio_sessions SET seen_at=?", (self.time.return_value - 3601,)
            )
        self.assertEqual(self.client.get("/api/studio/workspace").status_code, 401)
        self.advance()
        client = self.challenge()
        with self.store.db() as c:
            c.execute(
                "UPDATE studio_sessions SET expires_at=?", (self.time.return_value - 1,)
            )
        self.assertEqual(client.get("/api/studio/workspace").status_code, 401)

    def test_direct_static_files_never_expose_private_or_historical_media(self):
        anon = self.app.test_client()
        for path in [
            "/static/studio/index.html",
            "/static/projects/a/video.mp4",
            "/static/.env",
            "/static/../.env",
            "/static/fonts/../../.env",
            "/static/studio/assets/test.js.map",
            "/.git/config",
            "/drylow_studio.db",
            "/.env",
            "/production/REPRISE.md",
        ]:
            response = anon.get(path)
            self.assertEqual(response.status_code, 404, path)
            self.assertNotIn(PASSWORD, response.text)
        with anon.get("/static/fonts/DM-Sans.woff2") as response:
            self.assertEqual(response.status_code, 200)
        with anon.get("/login") as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(anon.get("/health/studio").json, {"status": "ok"})

    def test_csrf_origin_and_browser_headers_are_enforced(self):
        self.assertEqual(
            self.client.post("/api/studio/logout", json={}).status_code, 403
        )
        csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.assertEqual(
            self.client.post(
                "/api/studio/logout",
                json={},
                headers={"X-CSRF-Token": csrf, "Origin": "https://intruder.example"},
            ).status_code,
            403,
        )
        response = self.client.get("/agent")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn(
            "frame-ancestors 'self'", response.headers["Content-Security-Policy"]
        )
        self.assertIn("noindex", response.headers["X-Robots-Tag"])
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        response.close()

    def test_public_documents_do_not_open_the_private_workspace(self):
        anon = self.app.test_client()
        for path in ["/about", "/privacy", "/terms"]:
            response = anon.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn("Edgerunners Studio", response.text)
            self.assertIn('href="/privacy"', response.text)
            self.assertIn('href="/terms"', response.text)
            self.assertNotIn(PASSWORD, response.text)
            self.assertNotIn(self.user_id, response.text)
            self.assertNotIn("private-session-fixture", response.text)
            self.assertEqual(anon.head(path).status_code, 200)
            self.assertEqual(anon.post(path).status_code, 405)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        for path in ["/", "/channels", "/settings", "/agent"]:
            response = anon.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertTrue(response.location.startswith("/login?"))
        for path in ["/api/studio/workspace", "/media/private/thumb", "/api/youtube/callback"]:
            self.assertEqual(anon.get(path).status_code, 401, path)
        for path in ["/privacy/private", "/terms/.env", "/about/../.env"]:
            self.assertEqual(anon.get(path).status_code, 404, path)

    def test_public_documents_keep_host_and_https_protection(self):
        hosted = create_app(
            {**self.config, "HOSTED": True, "PUBLIC_URL": "https://studio.example.org"}
        )
        anon = hosted.test_client()
        for path in ["/about", "/privacy", "/terms"]:
            response = anon.get(path, base_url="https://studio.example.org")
            self.assertEqual(response.status_code, 200)
            self.assertIn("frame-ancestors 'self'", response.headers["Content-Security-Policy"])
            self.assertEqual(anon.get(path, base_url="http://studio.example.org").status_code, 308)
            self.assertEqual(anon.get(path, base_url="https://evil.example.org").status_code, 400)

    def test_parallel_password_guesses_cannot_bypass_throttle(self):
        def attempt(_):
            client = self.app.test_client()
            return self.post(
                client, "/login", {"username": "drylow", "password": "incorrect"}
            ).status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(attempt, range(12)))
        self.assertEqual(results.count(401), 8, results)
        self.assertEqual(results.count(429), 4, results)

    def test_internal_worker_uses_bound_short_session_and_removes_it(self):
        original = len(self.store.rows("SELECT * FROM studio_sessions"))
        with security.trusted_client(self.store, self.user_id) as (client, csrf, base):
            response = client.post(
                "/api/studio/tasks",
                json={"title": "Private worker action"},
                headers={"X-CSRF-Token": csrf},
                base_url=base,
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(
                len(self.store.rows("SELECT * FROM studio_sessions")), original + 1
            )
        self.assertEqual(
            len(self.store.rows("SELECT * FROM studio_sessions")), original
        )

    def test_hosted_mode_enforces_https_domain_and_secure_cookie(self):
        hosted = create_app(
            {**self.config, "HOSTED": True, "PUBLIC_URL": "https://studio.example.org"}
        )
        client = hosted.test_client()
        response = client.get("/login", base_url="https://studio.example.org")
        self.assertEqual(response.status_code, 200)
        cookie = response.headers["Set-Cookie"]
        for part in [
            "__Host-edgerunners=",
            "Secure",
            "HttpOnly",
            "SameSite=Lax",
            "Path=/",
        ]:
            self.assertIn(part, cookie)
        self.assertNotIn("Domain=", cookie)
        response.close()
        self.assertEqual(
            client.get("/agent", base_url="http://studio.example.org").status_code, 308
        )
        self.assertEqual(
            client.post(
                "/api/studio/login", base_url="http://studio.example.org", json={}
            ).status_code,
            426,
        )
        self.assertEqual(
            client.get("/login", base_url="https://evil.example.org").status_code, 400
        )
        with client.get(
            "/login",
            base_url="https://studio.example.org",
            headers={"X-Forwarded-Host": "evil.example.org"},
        ) as response:
            self.assertEqual(response.status_code, 200)
        self.assertIn("max-age=31536000", response.headers["Strict-Transport-Security"])
        hosted_store = hosted.extensions["studio_store"]
        with security.trusted_client(hosted_store, self.user_id) as (
            internal,
            csrf,
            base,
        ):
            result = internal.post(
                "/api/studio/tasks",
                base_url=base,
                json={"title": "Hosted worker action"},
                headers={"X-CSRF-Token": csrf},
            )
            self.assertEqual(result.status_code, 201)
        for changes in [
            {"PREVIEW": True},
            {"LOCAL_OWNER": True},
            {"SECRET_KEY": "weak"},
            {"PUBLIC_URL": "http://studio.example.org"},
        ]:
            with self.assertRaises(ValueError):
                create_app(
                    {
                        **self.config,
                        "HOSTED": True,
                        "PUBLIC_URL": "https://studio.example.org",
                        **changes,
                    }
                )

    def test_parallel_account_creation_preserves_the_two_member_limit(self):
        self.assertEqual(
            self.post(
                self.client,
                "/users",
                {"name": "Kanye", "username": "kanye", "password": "too short"},
            ).status_code,
            400,
        )
        cookie = self.client.get_cookie("session").value
        csrf = self.client.get("/api/studio/bootstrap").json["csrf"]

        def create(username):
            client = self.app.test_client()
            client.set_cookie("session", cookie)
            return client.post(
                "/api/studio/users",
                json={
                    "name": username,
                    "username": username,
                    "password": OTHER_PASSWORD,
                },
                headers={"X-CSRF-Token": csrf},
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, ["kanye", "stranger"]))
        self.assertEqual(sorted(results), [201, 403])
        self.assertEqual(len(self.store.users()), 2)
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)

    def test_revision_health_is_private_and_health_token_is_purpose_bound(self):
        client = self.app.test_client()
        self.assertEqual(
            client.get("/health/studio", headers={"X-Studio-Health": "forged"}).json,
            {"status": "ok"},
        )
        expected = security.health_token(self.app.config["SECRET_KEY"])
        self.assertIn(
            "revision",
            client.get("/health/studio", headers={"X-Studio-Health": expected}).json,
        )
        self.assertEqual(
            client.get(
                "/api/studio/workspace", headers={"X-Studio-Health": expected}
            ).status_code,
            401,
        )

    def test_login_opens_the_workspace_without_an_app_or_extra_code(self):
        owner = self.client.get("/api/studio/bootstrap").json
        self.assertEqual(owner["user"]["name"], "Drylow")
        self.assertNotIn("auth", owner)
        client = self.challenge()
        self.assertEqual(client.get("/api/studio/workspace").status_code, 200)
        with client.get("/agent") as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get("/api/studio/security").json["sessions"], 2)
        for route in ["/auth/enrol", "/auth/verify", "/auth/finish"]:
            self.assertEqual(self.post(client, route, {}).status_code, 404)

    def test_anonymous_users_cannot_open_pages_files_or_tools(self):
        client = self.app.test_client()
        boot = client.get("/api/studio/bootstrap").json
        self.assertIsNone(boot["user"])
        for path in [
            "/",
            "/agent",
            "/channels",
            "/settings",
            "/tools/osl-studio",
            "/calendar",
        ]:
            response = client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertTrue(response.location.startswith("/login?next="), path)
        for path in [
            "/api/studio/workspace",
            "/api/studio/chat",
            "/api/studio/security",
            "/api/studio/planning",
            "/media/anything/video",
            "/media/reference/private.png",
        ]:
            self.assertEqual(client.get(path).status_code, 401, path)
        self.assertEqual(self.post(client, "/users", {}).status_code, 401)

    def test_setup_token_cannot_create_another_owner(self):
        client = self.app.test_client()
        self.assertEqual(
            self.post(client, "/setup", {"token": "unknown"}).status_code, 403
        )
        response = self.post(
            client,
            "/setup",
            {
                "token": "private-installation-fixture",
                "name": "Intruder",
                "username": "intruder",
                "password": OTHER_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.store.users()), 1)

    def test_cookie_and_database_do_not_store_plaintext_credentials(self):
        cookie = self.client.get_cookie("session").value
        decoded = self.app.session_interface.get_signing_serializer(self.app).loads(
            cookie
        )
        self.assertNotIn(PASSWORD, json.dumps(decoded))
        self.assertNotIn(
            decoded["studio_sid"],
            json.dumps(self.store.rows("SELECT * FROM studio_sessions")),
        )
        self.assertNotIn(
            PASSWORD,
            self.store.one("SELECT password_hash FROM studio_users")["password_hash"],
        )
        self.assertNotIn(PASSWORD, self.client.get("/api/studio/workspace").text)

    def test_both_accounts_enter_directly_and_a_third_is_refused(self):
        self.assertEqual(
            self.post(
                self.client,
                "/users",
                {"name": "Kanye", "username": "kanye", "password": OTHER_PASSWORD},
            ).status_code,
            201,
        )
        self.assertEqual(
            self.post(
                self.client,
                "/users",
                {
                    "name": "Stranger",
                    "username": "stranger",
                    "password": OTHER_PASSWORD,
                },
            ).status_code,
            403,
        )
        colleague = self.challenge("kanye", OTHER_PASSWORD)
        self.assertEqual(colleague.get("/api/studio/workspace").status_code, 200)
        self.assertEqual(
            colleague.get("/api/studio/bootstrap").json["user"]["name"], "Kanye"
        )
        self.assertEqual(self.post(colleague, "/users", {}).status_code, 403)

    def test_invalid_tokens_and_unknown_accounts_never_produce_server_errors(self):
        self.assertEqual(
            self.post(self.app.test_client(), "/setup", {"token": "é"}).status_code, 403
        )
        client = self.app.test_client()
        client.get("/api/studio/bootstrap")
        self.assertEqual(
            client.post(
                "/api/studio/login", json={}, headers={"X-CSRF-Token": "é"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                client, "/login", {"username": "unknown", "password": OTHER_PASSWORD}
            ).status_code,
            401,
        )
        self.assertEqual(client.get("/api/studio/workspace").status_code, 401)

    def test_password_change_requires_current_password_and_revokes_old_devices(self):
        other = self.challenge()
        replacement = "a new private password phrase for Drylow"
        cookie = self.client.get_cookie("session").value
        self.assertEqual(
            self.post(
                self.client,
                "/security/password",
                {"current_password": "incorrect", "password": replacement},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.post(
                self.client,
                "/security/password",
                {"current_password": PASSWORD, "password": replacement},
            ).status_code,
            200,
        )
        self.assertNotEqual(self.client.get_cookie("session").value, cookie)
        self.assertEqual(other.get("/api/studio/workspace").status_code, 401)
        self.assertEqual(self.client.get("/api/studio/workspace").status_code, 200)
        self.assertEqual(
            self.post(
                self.app.test_client(),
                "/login",
                {"username": "drylow", "password": PASSWORD},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.challenge(password=replacement)
            .get("/api/studio/workspace")
            .status_code,
            200,
        )

    def test_password_change_cannot_be_raced_by_a_login_using_old_credentials(self):
        original = security.check_password_hash
        changed = False
        replacement = "a renewed private password phrase for Drylow"

        def verify(hashed, submitted):
            nonlocal changed
            valid = original(hashed, submitted)
            if valid and submitted == PASSWORD and not changed:
                changed = True
                result = self.post(
                    self.client,
                    "/security/password",
                    {"current_password": PASSWORD, "password": replacement},
                )
                self.assertEqual(result.status_code, 200)
            return valid

        anonymous = self.app.test_client()
        with patch("studio.security.check_password_hash", side_effect=verify):
            response = self.post(
                anonymous, "/login", {"username": "drylow", "password": PASSWORD}
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(anonymous.get("/api/studio/workspace").status_code, 401)
        self.assertEqual(
            self.challenge(password=replacement)
            .get("/api/studio/workspace")
            .status_code,
            200,
        )

    def test_closing_other_devices_keeps_this_device_and_the_colleague(self):
        other = self.challenge()
        self.post(
            self.client,
            "/users",
            {"name": "Kanye", "username": "kanye", "password": OTHER_PASSWORD},
        )
        colleague = self.challenge("kanye", OTHER_PASSWORD)
        self.assertEqual(
            self.post(self.client, "/security/sessions", {}).status_code, 200
        )
        self.assertEqual(other.get("/api/studio/workspace").status_code, 401)
        self.assertEqual(self.client.get("/api/studio/workspace").status_code, 200)
        self.assertEqual(colleague.get("/api/studio/workspace").status_code, 200)

    def test_old_incomplete_phone_sessions_do_not_grant_access(self):
        with self.store.db() as c:
            c.execute(
                "UPDATE studio_sessions SET scope='enrol',private_data='old encrypted fixture'"
            )
        self.assertEqual(self.client.get("/api/studio/workspace").status_code, 401)
        self.assertNotIn("auth", self.client.get("/api/studio/bootstrap").json)
        self.assertEqual(self.challenge().get("/api/studio/workspace").status_code, 200)


if __name__ == "__main__":
    unittest.main()
