"""Pair a dedicated, visible Chrome profile with one YouTube Studio channel.

Runs only after an owner requests pairing, through the existing Windows agent.
No OAuth client, credentials export, upload, browser stealth or sandbox override.
The dedicated profile survives the agent's disposable work directory.
"""

import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit
import uuid

PLAYWRIGHT_VERSION = "1.63.0"
CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}")
NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class PairingError(Exception):
    pass


def validate_manifest(data, timestamp=None):
    timestamp = time.time() if timestamp is None else timestamp
    if not isinstance(data, dict) or data.get("action") != "connect":
        raise PairingError("invalid_request")
    if not CHANNEL_ID.fullmatch(str(data.get("channel_id", ""))):
        raise PairingError("invalid_request")
    if not re.fullmatch(r"pc-connect-[a-f0-9]{32}", str(data.get("request_id", ""))):
        raise PairingError("invalid_request")
    if not re.fullmatch(r"[a-f0-9]{64}", str(data.get("nonce", ""))):
        raise PairingError("invalid_request")
    deadline = data.get("deadline")
    if isinstance(deadline, bool) or not isinstance(deadline, (float, int)) or not timestamp < deadline <= timestamp + 1200:
        raise PairingError("expired_request")
    return data


def dashboard_channel(url):
    """A Google login URL or arbitrary /channel link is never identity proof."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "studio.youtube.com" or parsed.port or parsed.username:
            return ""
        match = re.fullmatch(r"/channel/(UC[A-Za-z0-9_-]{22})(?:/[^?#]*)?", parsed.path)
        return match.group(1) if match else ""
    except (ValueError, TypeError):
        return ""


def authenticated_dashboard(page, expected):
    """Confirm both Studio's location and its authenticated navigation context.

    Studio versions can use different dashboard tags. The visible app and its
    channel-scoped navigation links provide a second proof without reading any
    account configuration, cookie, login field, email or private video metadata.
    An arbitrary channel URL with another channel's sidebar must fail closed.
    """
    if dashboard_channel(page.url) != expected:
        return False
    try:
        if not page.locator("ytcp-app").is_visible():
            return False
        links = page.locator("ytcp-navigation-drawer a[href]").evaluate_all(
            "items => items.map(item => item.href)"
        )
        channels = [dashboard_channel(link) for link in links]
        channels = [channel for channel in channels if channel]
        return len(channels) >= 2 and set(channels) == {expected}
    except Exception:
        return False


def private_directory(path):
    if path.is_symlink():
        raise PairingError("unsafe_profile")
    path.mkdir(parents=True, exist_ok=True)
    return path


def agent_home():
    # The installed agent defines STUDIO_WORK=<agent>/work/build. Never guess a
    # default Chrome profile or inspect another user's browser directories.
    work = Path(os.environ.get("STUDIO_WORK", ""))
    if not work.is_absolute() or work.name != "build" or work.parent.name != "work":
        raise PairingError("agent_missing")
    home = work.parent.parent
    if home.is_symlink() or not (home / "pc_agent.py").is_file() or not (home / "config.json").is_file():
        raise PairingError("agent_missing")
    return home


def notify():
    """Visible Windows notice precedes installation and opening Chrome."""
    shell = Path(os.environ.get("SYSTEMROOT", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not shell.is_file():
        raise PairingError("notification_failed")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
        "$notice=New-Object System.Windows.Forms.NotifyIcon; "
        "$notice.Icon=[System.Drawing.SystemIcons]::Information; $notice.Visible=$true; "
        "$notice.BalloonTipTitle='Edgerunners Studio'; "
        "$notice.BalloonTipText='Connexion YouTube demandée : Chrome va ouvrir un profil dédié. Aucune vidéo ne sera publiée.'; "
        "$notice.ShowBalloonTip(10000); "
        "for($i=0;$i -lt 100;$i++){[System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 100}; "
        "$notice.Dispose()"
    )
    try:
        completed = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-Command", script],
                                   creationflags=NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        raise PairingError("notification_failed") from None
    if completed.returncode:
        raise PairingError("notification_failed")


def chrome_path():
    for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if os.environ.get(name):
            path = Path(os.environ[name]) / "Google/Chrome/Application/chrome.exe"
            if path.is_file():
                return path
    raise PairingError("chrome_missing")


def browser_library():
    try:
        installed = importlib.metadata.version("playwright")
    except importlib.metadata.PackageNotFoundError:
        installed = ""
    if installed != PLAYWRIGHT_VERSION or importlib.util.find_spec("playwright") is None:
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                                     "--no-warn-script-location", "playwright==" + PLAYWRIGHT_VERSION],
                                    creationflags=NO_WINDOW, capture_output=True, timeout=240)
        except (OSError, subprocess.TimeoutExpired):
            raise PairingError("dependency_failed") from None
        if result.returncode:
            raise PairingError("dependency_failed")
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        raise PairingError("dependency_failed") from None


def connect(data, job):
    if os.name != "nt":
        raise PairingError("windows_required")
    home = agent_home()
    chrome = chrome_path()
    notify()
    emit(job, data, "waiting", "preparing_browser")
    sync_playwright = browser_library()
    validate_manifest(data)  # An old queued command cannot open a Google login.
    root = private_directory(home / "youtube")
    profiles = private_directory(root / "profiles")
    profile = private_directory(profiles / data["channel_id"])
    device_file = root / "device_id"
    if device_file.is_symlink():
        raise PairingError("unsafe_profile")
    if not device_file.exists():
        device_file.write_text(uuid.uuid4().hex, encoding="ascii")
    device = device_file.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[a-f0-9]{32}", device):
        raise PairingError("unsafe_profile")
    # Never attach to an existing Chrome. Reusing a directory while Chrome is
    # open could send this command to a different existing browser process.
    active = profile / "DevToolsActivePort"
    if active.exists():
        try:
            import socket
            port = int(active.read_text(encoding="ascii").splitlines()[0])
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                raise PairingError("browser_busy")
        except (OSError, ValueError, IndexError):
            active.unlink(missing_ok=True)
    process = subprocess.Popen([str(chrome), "--user-data-dir=" + str(profile),
                                "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
                                "--no-first-run", "--no-default-browser-check", "https://studio.youtube.com/"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    browser = None
    try:
        until = min(data["deadline"], time.time() + 30)
        while not active.exists() and process.poll() is None and time.time() < until:
            time.sleep(.5)
        if not active.exists() or process.poll() is not None:
            raise PairingError("browser_failed")
        port = int(active.read_text(encoding="ascii").splitlines()[0])
        if not 1024 <= port <= 65535:
            raise PairingError("browser_failed")
        emit(job, data, "waiting", "sign_in")
        with sync_playwright() as automation:
            browser = automation.chromium.connect_over_cdp("http://127.0.0.1:" + str(port), timeout=20000)
            try:
                until = min(data["deadline"], time.time() + 300)
                other_channel = False
                while time.time() < until:
                    for context in browser.contexts:
                        for page in context.pages:
                            actual = dashboard_channel(page.url)
                            if not actual:
                                continue
                            if actual != data["channel_id"]:
                                other_channel = True
                                continue
                            if authenticated_dashboard(page, data["channel_id"]):
                                emit(job, data, "ready", "dashboard_confirmed", channel_id=actual,
                                     device_id=device, dashboard_seen=True)
                                return
                    time.sleep(1)
                raise PairingError("wrong_channel" if other_channel else "sign_in_timeout")
            finally:
                browser.close()
                browser = None
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        # Only terminate the process created here; never enumerate/kill Chrome.
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass


def emit(job, data, status, code, **details):
    result = dict(version=1, action="connect", request_id=data.get("request_id", ""),
                  nonce=data.get("nonce", ""), expected_channel_id=data.get("channel_id", ""),
                  status=status, code=code, **details)
    # Result contains only identifiers; no browser URLs, cookies, screenshots,
    # OAuth credentials, profile paths, user names or raw exception strings.
    target = job / "result.json"
    temporary = job / "result.tmp"
    temporary.write_text(json.dumps(result), encoding="utf-8")
    temporary.replace(target)


def main():
    job = Path(sys.argv[2])
    data = {}
    try:
        raw = (job / "pc_request.json").read_bytes()
        if len(raw) > 16384:
            raise PairingError("invalid_request")
        parsed = json.loads(raw)
        data = parsed if isinstance(parsed, dict) else {}
        validate_manifest(parsed)
        connect(data, job)
    except PairingError as error:
        emit(job, data, "failed", str(error))
    except Exception:
        emit(job, data if isinstance(data, dict) else {}, "failed", "browser_failed")


if __name__ == "__main__":
    main()
