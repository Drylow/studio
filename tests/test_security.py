"""Exercise the private gate, its second factor and hostile direct requests."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import pyotp

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

    def complete(self, client=None):
        client = client or self.client
        self.assertEqual(
            client.get("/api/studio/bootstrap").json["auth"]["stage"], "enrol"
        )
        enrol = self.post(client, "/auth/enrol", {}).json
        self.assertTrue(enrol["qr"].startswith("data:image/png;base64,"))
        self.assertIn("otpauth://totp/", enrol["uri"])
        secret = enrol["secret"]
        response = self.post(
            client,
            "/auth/verify",
            {"code": pyotp.TOTP(secret).at(self.time.return_value)},
        )
        self.assertEqual(response.status_code, 200, response.json)
        codes = client.get("/api/studio/bootstrap").json["auth"]["codes"]
        self.assertEqual(
            self.post(client, "/auth/finish", {"saved": True}).status_code, 200
        )
        self.assertEqual(client.get("/api/studio/workspace").status_code, 200)
        return secret, codes

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

    def test_password_proof_alone_never_opens_pages_or_tools(self):
        boot = self.client.get("/api/studio/bootstrap").json
        self.assertIsNone(boot["user"])
        self.assertEqual(boot["auth"], {"stage": "enrol"})
        for path in [
            "/",
            "/agent",
            "/channels",
            "/settings",
            "/tools/osl-studio",
            "/calendar",
        ]:
            response = self.client.get(path)
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
            self.assertEqual(self.client.get(path).status_code, 401, path)
        self.assertEqual(
            self.post(self.client, "/auth/finish", {"saved": True}).status_code, 403
        )

    def test_no_registration_or_enrolment_without_password_proof(self):
        client = self.app.test_client()
        for path in ["/auth/enrol", "/auth/verify", "/auth/finish", "/users"]:
            self.assertIn(
                self.post(client, path, {"saved": True}).status_code, {401, 403}, path
            )
        self.assertEqual(
            self.post(client, "/setup", {"token": "unknown"}).status_code, 403
        )

    def test_full_enrolment_keeps_secrets_off_cookie_and_database_plaintext(self):
        enrol = self.post(self.client, "/auth/enrol", {}).json
        raw_cookie = self.client.get_cookie("session").value
        signed = self.app.session_interface.get_signing_serializer(self.app).loads(
            raw_cookie
        )
        self.assertNotIn(enrol["secret"], json.dumps(signed))
        secret, codes = self.complete()
        record = self.store.one("SELECT * FROM studio_mfa")
        self.assertNotIn(secret, record["secret"])
        hashes = json.dumps(self.store.rows("SELECT * FROM studio_recovery_codes"))
        for code in codes:
            self.assertNotIn(code, hashes)
        boot = self.client.get("/api/studio/bootstrap").json
        self.assertIsNone(boot["auth"])
        self.assertNotIn(secret, json.dumps(boot))
        self.assertEqual(
            self.client.get("/api/studio/security").json["recovery_remaining"], 8
        )

    def test_recovery_codes_must_be_saved_before_entering(self):
        secret = self.post(self.client, "/auth/enrol", {}).json["secret"]
        self.post(
            self.client,
            "/auth/verify",
            {"code": pyotp.TOTP(secret).at(self.time.return_value)},
        )
        self.assertEqual(self.client.get("/api/studio/workspace").status_code, 401)
        self.assertEqual(
            self.post(self.client, "/auth/finish", {"saved": False}).status_code, 400
        )
        self.assertEqual(
            self.post(self.client, "/auth/finish", {"saved": True}).status_code, 200
        )

    def test_code_replay_is_rejected_even_after_a_new_password_login(self):
        secret, _ = self.complete()
        self.advance()
        code = pyotp.TOTP(secret).at(self.time.return_value)
        first = self.challenge()
        self.assertEqual(
            self.post(first, "/auth/verify", {"code": code}).status_code, 200
        )
        second = self.challenge()
        self.assertEqual(
            self.post(second, "/auth/verify", {"code": code}).status_code, 401
        )
        self.assertEqual(second.get("/api/studio/workspace").status_code, 401)
        self.advance()
        self.assertEqual(
            self.post(
                second,
                "/auth/verify",
                {"code": pyotp.TOTP(secret).at(self.time.return_value)},
            ).status_code,
            200,
        )

    def test_concurrent_confirmation_of_one_cookie_only_succeeds_once(self):
        secret, _ = self.complete()
        self.advance()
        first = self.challenge()
        cookie = first.get_cookie("session").value
        csrf = first.get("/api/studio/bootstrap").json["csrf"]

        def attempt(_):
            client = self.app.test_client()
            client.set_cookie("session", cookie)
            return client.post(
                "/api/studio/auth/verify",
                json={"code": pyotp.TOTP(secret).at(self.time.return_value)},
                headers={"X-CSRF-Token": csrf},
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(results.count(200), 1, results)
        self.assertIn(next(code for code in results if code != 200), {401, 403})

    def test_logout_revokes_a_stolen_copy_of_the_cookie(self):
        self.complete()
        cookie = self.client.get_cookie("session").value
        self.assertEqual(self.post(self.client, "/logout", {}).status_code, 200)
        thief = self.app.test_client()
        thief.set_cookie("session", cookie)
        self.assertEqual(thief.get("/api/studio/workspace").status_code, 401)

    def test_cookie_identity_cannot_be_changed_to_another_user(self):
        self.complete()
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
        self.complete()
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
        self.assertEqual(self.post(client, "/auth/enrol", {}).status_code, 403)

    def test_only_two_accounts_can_be_created_and_both_need_mfa(self):
        self.complete()
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
        other = self.challenge("kanye", OTHER_PASSWORD)
        self.assertEqual(other.get("/api/studio/workspace").status_code, 401)
        self.complete(other)
        self.assertEqual(
            other.get("/api/studio/bootstrap").json["user"]["name"], "Kanye"
        )
        self.assertEqual(
            self.post(other, "/users", {"name": "Intruder"}).status_code, 403
        )

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
        self.complete()
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

    def test_malformed_unicode_codes_are_rejected_without_server_errors(self):
        self.assertEqual(
            self.post(self.client, "/auth/verify", {"code": "١٢٣٤٥٦"}).status_code, 401
        )
        self.assertEqual(
            self.post(self.app.test_client(), "/setup", {"token": "é"}).status_code, 403
        )
        client = self.app.test_client()
        client.get("/api/studio/bootstrap")
        response = client.post(
            "/api/studio/login", json={}, headers={"X-CSRF-Token": "é"}
        )
        self.assertEqual(response.status_code, 403)

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

    def test_second_factor_guesses_are_throttled(self):
        for _ in range(8):
            self.assertEqual(
                self.post(self.client, "/auth/verify", {"code": "invalid"}).status_code,
                401,
            )
        response = self.post(self.client, "/auth/verify", {"code": "invalid"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "600")

    def test_recovery_is_one_use_and_requires_replacement_phone(self):
        old_secret, codes = self.complete()
        client = self.challenge()
        self.assertEqual(
            self.post(
                client, "/auth/verify", {"code": codes[0], "recovery": True}
            ).status_code,
            200,
        )
        self.assertEqual(
            client.get("/api/studio/bootstrap").json["auth"]["stage"], "enrol"
        )
        self.assertEqual(client.get("/api/studio/workspace").status_code, 401)
        replay = self.challenge()
        self.assertEqual(
            self.post(
                replay, "/auth/verify", {"code": codes[0], "recovery": True}
            ).status_code,
            401,
        )
        self.advance()
        new_secret, new_codes = self.complete(client)
        self.assertNotEqual(old_secret, new_secret)
        self.assertTrue(set(codes).isdisjoint(new_codes))
        self.assertEqual(self.client.get("/api/studio/workspace").status_code, 401)

    def test_password_change_needs_fresh_second_factor_and_revokes_old_sessions(self):
        secret, _ = self.complete()
        self.advance()
        other = self.challenge()
        self.post(
            other,
            "/auth/verify",
            {"code": pyotp.TOTP(secret).at(self.time.return_value)},
        )
        self.assertEqual(other.get("/api/studio/workspace").status_code, 200)
        replacement = "a new private password phrase for Drylow"
        self.assertEqual(
            self.post(
                self.client,
                "/security/password",
                {
                    "current_password": PASSWORD,
                    "password": replacement,
                    "code": "invalid",
                },
            ).status_code,
            401,
        )
        self.advance()
        self.assertEqual(
            self.post(
                self.client,
                "/security/password",
                {
                    "current_password": PASSWORD,
                    "password": replacement,
                    "code": pyotp.TOTP(secret).at(self.time.return_value),
                },
            ).status_code,
            200,
        )
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

    def test_close_other_devices_keeps_current_account_and_cookie(self):
        secret, _ = self.complete()
        self.advance()
        other = self.challenge()
        self.post(
            other,
            "/auth/verify",
            {"code": pyotp.TOTP(secret).at(self.time.return_value)},
        )
        self.assertEqual(
            self.post(self.client, "/security/sessions", {}).status_code, 200
        )
        self.assertEqual(other.get("/api/studio/workspace").status_code, 401)
        self.assertEqual(self.client.get("/api/studio/workspace").status_code, 200)

    def test_internal_worker_uses_bound_short_session_and_removes_it(self):
        self.complete()
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

    def test_hosted_mode_enforces_https_domain_mfa_and_secure_cookie(self):
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
            {"MFA_REQUIRED": False},
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
        self.complete()
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


if __name__ == "__main__":
    unittest.main()
