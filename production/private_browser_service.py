"""Owner-controlled first-party Firefox session on the existing private VPS.

No OAuth client impersonation, cookie export, stealth flags or disabled browser
security. Normal Google challenges must be completed by the account owner.
This service provides login/inspection only; it does not claim to upload videos.
"""

import base64
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

RUNTIME = Path("/data/edgerunners-browser-runtime")
HOME_PATH = Path("/data/edgerunners-browser-service")
BRIDGE_PATH = "/api/studio/youtube-browser/bridge"
CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}")
SESSION_ID = re.compile(r"[0-9a-f]{32}")
KEYS = {"Return", "Tab", "BackSpace", "Escape", "Left", "Right", "Up", "Down", "Delete"}


def launch(args, env=None):
    return subprocess.Popen(["runuser", "-u", "edg_browser", "--", *args],
                            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)


def terminate(process):
    if process and process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def bootstrap(jobdir):
    job = Path(jobdir)
    result = {"private_browser_service_started": False, "account_connected": False,
              "video_uploaded": False, "no_pc_installation": True}
    try:
        config = json.loads((job / "start.json").read_text())
        from urllib.parse import urlsplit
        parsed = urlsplit(config["site"])
        assert parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password
        assert parsed.path in ("", "/") and not parsed.query and not parsed.fragment
        assert os.geteuid() == 0 and len(os.getenv("WORKER_TOKEN", "")) >= 24
        RUNTIME.mkdir(mode=0o700, exist_ok=True)
        RUNTIME.chmod(0o700)
        # Do not restart an existing login or another process with a reused PID.
        pid_file = RUNTIME / "service.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text())
                args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                if str(RUNTIME / "service.py").encode() in args:
                    if (RUNTIME / "service.py").read_bytes() == Path(__file__).read_bytes():
                        result["private_browser_service_started"] = True
                        result["already_running"] = True
                        return
                    os.kill(pid, signal.SIGTERM)
                    for _ in range(150):
                        if not Path(f"/proc/{pid}").exists(): break
                        time.sleep(.2)
                    else: raise OSError("previous_private_browser_service_did_not_stop")
            except (OSError, ValueError):
                pass
        packages = [p for p, executable in (("firefox-esr", "firefox-esr"), ("xvfb", "Xvfb"), ("xauth", "xauth"), ("xdotool", "xdotool")) if not shutil.which(executable)]
        if packages:
            # Debian's default signature/TLS verification is preserved.
            subprocess.run(["apt-get", "update", "-qq"], check=True, timeout=180)
            dry_run = subprocess.run(["apt-get", "install", "--no-install-recommends", "--no-upgrade", "--simulate", *packages], check=True, capture_output=True, text=True, timeout=60)
            assert not re.search(r"^Remv ", dry_run.stdout, re.M), "package_removal_refused"
            subprocess.run(["apt-get", "install", "-y", "-qq", "--no-install-recommends", "--no-upgrade", *packages], check=True, timeout=180, stdout=subprocess.DEVNULL)
        deps = RUNTIME / "deps"
        if not (deps / "cryptography").is_dir():
            subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--only-binary=:all:", "--target", str(deps), "cryptography==46.0.3"], check=True, timeout=180, stdout=subprocess.DEVNULL)
        try:
            person = pwd.getpwnam("edg_browser")
        except KeyError:
            subprocess.run(["useradd", "--system", "--create-home", "--home-dir", str(HOME_PATH), "--shell", "/usr/sbin/nologin", "edg_browser"], check=True)
            person = pwd.getpwnam("edg_browser")
        assert Path(person.pw_dir) == HOME_PATH
        HOME_PATH.chmod(0o700)
        service = RUNTIME / "service.py"
        shutil.copyfile(__file__, service)
        service.chmod(0o600)
        start = RUNTIME / "start.json"
        start.write_text(json.dumps(config)); start.chmod(0o600)
        subprocess.Popen([sys.executable, str(service), "serve"], cwd=RUNTIME, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        result["private_browser_service_started"] = True
    except Exception as error:
        result["failure_class"] = type(error).__name__
    finally:
        (job / "result.json").write_text(json.dumps(result))
        print(json.dumps(result), flush=True)


class Marionette:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=2)
        self.sock.settimeout(25)
        self.buffer = b""
        self.seq = 0
        self.receive()
        self.command("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {}}})

    def receive(self):
        while b":" not in self.buffer:
            part = self.sock.recv(65536)
            if not part: raise OSError("browser_connection_closed")
            self.buffer += part
        size, self.buffer = self.buffer.split(b":", 1)
        length = int(size)
        assert 0 < length < 2_000_000
        while len(self.buffer) < length:
            part = self.sock.recv(65536)
            if not part: raise OSError("browser_connection_closed")
            self.buffer += part
        raw, self.buffer = self.buffer[:length], self.buffer[length:]
        return json.loads(raw)

    def command(self, command, args=None):
        self.seq += 1
        raw = json.dumps([0, self.seq, command, args or {}]).encode()
        self.sock.sendall(str(len(raw)).encode()+b":"+raw)
        result = self.receive()
        if result[2]: raise OSError("browser_command_refused")
        answer = result[3]
        return answer.get("value", answer) if isinstance(answer, dict) else answer


class Browser:
    """One private display. Normal login first; standard debugging only for inspection."""
    def __init__(self, cid, expected):
        assert isinstance(cid, int) and cid > 0 and CHANNEL_ID.fullmatch(expected)
        self.cid, self.expected = cid, expected
        self.person = pwd.getpwnam("edg_browser")
        self.process, self.xvfb, self.remote = None, None, None
        self.auth = RUNTIME / "display.xauth"
        try:
            self.start()
        except BaseException:
            self.close()
            raise

    def start(self):
        cid = self.cid
        profiles = HOME_PATH / "profiles"
        profiles.mkdir(mode=0o700, exist_ok=True)
        os.chown(profiles, self.person.pw_uid, self.person.pw_gid)
        self.profile = profiles / ("channel-"+str(cid))
        self.profile.mkdir(mode=0o700, exist_ok=True)
        self.profile.chmod(0o700)
        os.chown(self.profile, self.person.pw_uid, self.person.pw_gid)
        self.display = next(n for n in range(230, 280) if not Path(f"/tmp/.X11-unix/X{n}").exists() and not Path(f"/tmp/.X{n}-lock").exists())
        self.auth.unlink(missing_ok=True)
        subprocess.run(["xauth", "-f", str(self.auth), "source", "-"], input=f"add :{self.display} . {secrets.token_hex(16)}\n", text=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Browser may read this dedicated file, not the service's keys/config.
        visible_auth = HOME_PATH / "display.xauth"
        shutil.copyfile(self.auth, visible_auth)
        visible_auth.chmod(0o600)
        os.chown(visible_auth, self.person.pw_uid, self.person.pw_gid)
        # Never pass WORKER_TOKEN/provider credentials to the browser user.
        self.env = {"PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                    "DISPLAY": f":{self.display}", "XAUTHORITY": str(visible_auth)}
        self.xvfb = launch(["Xvfb", f":{self.display}", "-screen", "0", "480x820x24", "-nolisten", "tcp", "-auth", str(visible_auth)], self.env)
        for _ in range(50):
            if self.xvfb.poll() is not None: raise OSError("private_display_unavailable")
            if Path(f"/tmp/.X11-unix/X{self.display}").exists(): break
            time.sleep(.1)
        # The default Firefox content sandbox remains on. No home override, anti-bot
        # override, browser password/cookie export, or inbound debugging listener.
        prefs = self.profile / "user.js"
        prefs.write_text('user_pref("browser.shell.checkDefaultBrowser", false);\nuser_pref("browser.startup.homepage_override.mstone", "ignore");\n')
        prefs.chmod(0o600); os.chown(prefs, self.person.pw_uid, self.person.pw_gid)
        # Keep the address bar visible so the owner can check Google's real origin.
        self.process = launch(["firefox-esr", "--no-remote", "--profile", str(self.profile), "--width", "480", "--height", "820", "https://studio.youtube.com/"], self.env)
        time.sleep(4)
        if self.process.poll() is not None: raise OSError("browser_unavailable")

    def screenshot(self):
        from PIL import ImageGrab
        prior = os.environ.get("XAUTHORITY")
        os.environ["XAUTHORITY"] = self.env["XAUTHORITY"]
        try:
            image = ImageGrab.grab(xdisplay=self.env["DISPLAY"])
        finally:
            if prior is None: os.environ.pop("XAUTHORITY", None)
            else: os.environ["XAUTHORITY"] = prior
        output = io.BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=85)
        return {"image": base64.b64encode(output.getvalue()).decode(), "width": 480, "height": 820}

    def input(self, data):
        action = data.get("action")
        args, text = None, None
        if action == "click" and type(data.get("x")) is int and type(data.get("y")) is int and 0 <= data["x"] < 480 and 0 <= data["y"] < 820:
            args = ["mousemove", str(data["x"]), str(data["y"]), "click", "1"]
        elif action == "key" and data.get("key") in KEYS:
            args = ["key", "--clearmodifiers", data["key"]]
        elif action == "text" and isinstance(data.get("text"), str) and 0 < len(data["text"]) <= 2000 and "\x00" not in data["text"]:
            args, text = ["type", "--clearmodifiers", "--file", "/dev/stdin"], data["text"]
        if not args: raise ValueError("input_refused")
        # No user input in a shell, argv, environment, file or log.
        subprocess.run(["runuser", "-u", "edg_browser", "--", "xdotool", *args], env=self.env, input=text,
                       text=True, check=True, timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"input_delivered": True}

    def inspect(self):
        if self.remote:
            self.remote.sock.close(); self.remote = None
        terminate(self.process)
        sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port=sock.getsockname()[1]; sock.close()
        prefs = self.profile / "user.js"
        prefs.write_text('user_pref("marionette.port", '+str(port)+');\n')
        prefs.chmod(0o600); os.chown(prefs, self.person.pw_uid, self.person.pw_gid)
        self.process = launch(["firefox-esr", "--no-remote", "--profile", str(self.profile), "--width", "480", "--height", "820", "--marionette", "https://studio.youtube.com/channel/"+self.expected], self.env)
        for _ in range(80):
            try:
                self.remote = Marionette(port)
                break
            except OSError:
                time.sleep(.25)
        if not self.remote: raise OSError("browser_inspection_unavailable")
        time.sleep(3)
        result = self.remote.command("WebDriver:ExecuteScript", {"script": """
            const url = new URL(location.href);
            const cfg = window.ytcfg;
            const id = cfg && typeof cfg.get === 'function' ? cfg.get('CHANNEL_ID') : '';
            const text = document.body.innerText;
            return {host:url.hostname,path:url.pathname, configuredChannelId:id || '',
              studioApp:!!document.querySelector('ytcp-app'),
              navigation:!!document.querySelector('ytcp-navigation-drawer'),
              accessRefused:/you do not have access|don't have permission|access denied/i.test(text),
              googleLogin:url.hostname==='accounts.google.com',
              browserBlocked:/This browser or app may not be secure/i.test(text)};
            """, "args": [], "newSandbox": True})
        # A URL alone does not establish ownership: require the actual authenticated
        # Studio app/navigation and its own channel identity, never a guessed title.
        verified = (result.get("host") == "studio.youtube.com" and result.get("studioApp") and result.get("navigation")
                    and result.get("configuredChannelId") == self.expected and not result.get("accessRefused"))
        return {"channel_access_observed": bool(verified), "channel_id": self.expected if verified else "",
                "login_required": bool(result.get("googleLogin")), "browser_blocked": bool(result.get("browserBlocked")),
                "publication_validated": False}

    def close(self):
        if self.remote: self.remote.sock.close(); self.remote = None
        terminate(self.process)
        terminate(self.xvfb)
        self.auth.unlink(missing_ok=True)
        (HOME_PATH / "display.xauth").unlink(missing_ok=True)


def serve():
    sys.path.insert(0, str(RUNTIME / "deps"))
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    instance = secrets.token_hex(16)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    public_key = base64.b64encode(private_key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
    source_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    token = os.environ["WORKER_TOKEN"]
    auth_key = hmac.new(token.encode(), b"edgerunners-private-browser-v1", hashlib.sha256).digest()
    site = json.loads((RUNTIME / "start.json").read_text())["site"].rstrip("/")
    pid = RUNTIME / "service.pid"
    pid.write_text(str(os.getpid())); pid.chmod(0o600)
    browser, sid, pending = None, None, None
    alive = True
    def stop(*_):
        nonlocal alive
        alive = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while alive:
            data = {"instance": instance, "public_key": public_key, "source_digest": source_digest}
            if pending: data["result"] = pending
            body = json.dumps(data, separators=(",", ":")).encode()
            stamp, nonce = str(int(time.time())), secrets.token_hex(16)
            proof = hmac.new(auth_key, (stamp+"\n"+nonce+"\n"+BRIDGE_PATH+"\n").encode()+body, hashlib.sha256).hexdigest()
            req = urllib.request.Request(site+BRIDGE_PATH, data=body, headers={"Content-Type":"application/json", "X-Browser-Time":stamp, "X-Browser-Nonce":nonce, "X-Browser-Proof":proof})
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    answer = json.load(response)
                pending = None
                live = {s["id"] for s in answer["sessions"] if s["expires_at"] > time.time()}
                if sid not in live and browser:
                    browser.close(); browser, sid = None, None
                command = answer.get("command")
                if not command:
                    time.sleep(.7 if live else 8)
                    continue
                if command["expires_at"] <= time.time() or command["session_id"] not in live:
                    continue
                try:
                    kind = command["kind"]
                    if kind == "open":
                        if browser: browser.close(); browser = None
                        sid = command["session_id"]
                        browser = Browser(command["channel_id"], command["expected_id"])
                        value = browser.screenshot()
                    elif not browser or sid != command["session_id"]:
                        raise ValueError("browser_session_unavailable")
                    elif kind == "frame":
                        value = browser.screenshot()
                    elif kind == "input":
                        envelope = command["payload"]
                        decode = lambda key: base64.b64decode(envelope[key], validate=True)
                        key = private_key.decrypt(decode("key"), padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
                        raw = AESGCM(key).decrypt(decode("iv"), decode("ciphertext"), sid.encode())
                        value = browser.input(json.loads(raw))
                    elif kind == "inspect":
                        value = browser.inspect()
                    else:
                        raise ValueError("command_refused")
                except Exception:
                    # Never report a password, provider response, sensitive URL or raw traceback.
                    value = {"error": "Le navigateur n’a pas exécuté cette action. Elle ne sera pas renvoyée automatiquement."}
                pending = {"id": command["id"], "value": value}
            except Exception:
                # Losing the signed viewer lease closes the interactive browser.
                if browser:
                    browser.close(); browser, sid = None, None
                pending = None
                time.sleep(5)
    finally:
        if browser: browser.close()
        pid.unlink(missing_ok=True)


if __name__ == "__main__" and sys.argv[1:] == ["serve"]:
    serve()
