"""Hosted access and revocation contracts without real credentials or API calls."""
import base64
import hashlib
import json
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

if Path(__file__).parent.name == "tests":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app import workspace_access as access
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "work/TubeForge"))
    from tubeforge_support import workspace_access as access


def record(role="worker"):
    salt = bytes.fromhex("0123456789abcdef0123456789abcdef")
    hashed = hashlib.pbkdf2_hmac("sha256", b"fixture-long-password", salt, 100000).hex()
    return {"role": role, "password_hash": f"pbkdf2_sha256$100000${salt.hex()}${hashed}"}


def header(username="worker", password="fixture-long-password"):
    return {"Authorization": "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()}


@pytest.fixture
def gate(tmp_path, monkeypatch):
    path = tmp_path / "users.json"
    path.write_text(json.dumps({"worker": record(), "owner": record("admin")}), encoding="utf-8")
    monkeypatch.setenv("TUBEFORGE_USERS_FILE", str(path))
    monkeypatch.setenv("TUBEFORGE_REQUIRE_AUTH", "1")
    app = FastAPI()
    @app.get("/api/project")
    async def project():
        return {"id": "fixture"}
    @app.put("/api/settings")
    async def settings():
        return {"ok": True}
    access.install(app)
    access.install(app)
    return TestClient(app), path


def test_missing_gate_fails_closed(monkeypatch):
    monkeypatch.delenv("TUBEFORGE_USERS_FILE", raising=False)
    monkeypatch.setenv("TUBEFORGE_REQUIRE_AUTH", "1")
    with pytest.raises(RuntimeError):
        access.install(FastAPI())


def test_desktop_gate_remains_optional(monkeypatch):
    monkeypatch.delenv("TUBEFORGE_USERS_FILE", raising=False)
    monkeypatch.delenv("TUBEFORGE_REQUIRE_AUTH", raising=False)
    app = FastAPI()
    access.install(app)
    assert not app.user_middleware


def test_anonymous_and_wrong_password_cannot_read_project(gate):
    client, _ = gate
    for headers in ({}, header(password="wrong"), {"Authorization": "Basic invalid%%"}):
        result = client.get("/api/project", headers=headers)
        assert result.status_code == 401
        assert "TubeForge" in result.headers["www-authenticate"]
    assert client.get("/healthz").json() == {"status": "ok"}


def test_worker_access_cannot_change_api_connections(gate):
    client, _ = gate
    assert client.get("/api/project", headers=header()).status_code == 200
    assert client.put("/api/settings", headers=header()).status_code == 403
    assert client.put("/api/settings", headers=header("owner")).status_code == 200
    assert client.get("/api/workspace/session", headers=header()).json() == {"username": "worker", "role": "worker"}


def test_cross_site_write_rejected(gate):
    client, _ = gate
    assert client.put("/api/settings", headers={**header("owner"), "Origin": "https://other.invalid"}).status_code == 403
    assert client.put("/api/settings", headers={**header("owner"), "Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.put("/api/settings", headers={**header("owner"), "Origin": "http://testserver"}).status_code == 200


def test_revocation_and_corrupt_registry_fail_closed(gate):
    client, path = gate
    assert client.get("/api/project", headers=header()).status_code == 200
    path.write_text(json.dumps({"owner": record("admin")}), encoding="utf-8")
    assert client.get("/api/project", headers=header()).status_code == 401
    path.write_text("broken registry", encoding="utf-8")
    assert client.get("/api/project", headers=header("owner")).status_code == 401
