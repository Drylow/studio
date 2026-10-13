#!/usr/bin/env python3
"""Dependency-free HTTPS client. All media work runs remotely on TubeForge."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

HOST = "https://tools.kanye.studio"
BASE = HOST + "/api/forge/v1"
SESSION = Path(os.getenv("FORGE_SESSION_FILE", str(Path.home() / ".tubeforge-session.json")))


def token():
    saved = os.environ.get("FORGE_SESSION_TOKEN")
    if not saved and SESSION.exists():
        saved = json.loads(SESSION.read_text(encoding="utf-8"))["token"]
    if not saved:
        raise ValueError("Run: python forge.py login")
    return saved


def request(method, url, data=None, content_type="application/json", login=False):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != urllib.parse.urlparse(HOST).netloc:
        raise ValueError("Refusing to send portal credentials outside the HTTPS portal")
    headers = {"Accept": "application/json"}
    if not login:
        headers["Authorization"] = "Bearer " + token()
    if data is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    # Refuse redirects rather than forwarding bearer credentials to another host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    return urllib.request.build_opener(NoRedirect()).open(req, timeout=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login")
    sub.add_parser("presets")
    sub.add_parser("endpoints")
    create = sub.add_parser("create")
    create.add_argument("--channel", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--script", type=Path)
    create.add_argument("--key", required=True, help="Stable idempotency key for this episode")
    create.add_argument("--minutes", type=float, default=15)
    create.add_argument("--brief", default="")
    for name in ("status", "project", "outputs", "transcript", "stop"):
        p = sub.add_parser(name); p.add_argument("id")
    action = sub.add_parser("action")
    action.add_argument("id"); action.add_argument("action")
    action.add_argument("--json", type=Path)
    generic = sub.add_parser("request")
    generic.add_argument("method"); generic.add_argument("path", help="Complete portal path from endpoint inventory")
    generic.add_argument("--json", type=Path)
    upload = sub.add_parser("upload")
    upload.add_argument("path", help="Complete upload endpoint path")
    upload.add_argument("file", type=Path)
    upload.add_argument("--field", action="append", default=[], help="name=value (repeatable)")
    download = sub.add_parser("download")
    download.add_argument("id"); download.add_argument("--kind", choices=("video", "voice", "subtitles"), default="video")
    download.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    method, data, url, content_type = "GET", None, BASE, "application/json"
    if args.command == "login":
        key = os.environ.get("FORGE_ACCESS_KEY") or getpass.getpass("Your portal access key: ")
        with request("POST", HOST + "/api/auth", json.dumps({"accessKey": key}).encode(), login=True) as res:
            from http.cookies import SimpleCookie
            cookies = SimpleCookie(); cookies.load(res.headers.get("Set-Cookie", ""))
            if "kt_session" not in cookies:
                raise ValueError("Login did not return a session cookie")
            payload = json.load(res)
            SESSION.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(SESSION), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump({"token": cookies["kt_session"].value, "user": payload["user"]}, out)
            os.chmod(SESSION, 0o600)
            print("Connected as", payload["user"]["name"], "— session stored privately at", SESSION)
            return
    if args.command in ("presets", "endpoints"):
        url += "/" + args.command
    elif args.command == "create":
        method, url = "POST", url + "/videos"
        data = json.dumps({"channel_id": args.channel, "title": args.title,
                           "script": args.script.read_text(encoding="utf-8-sig") if args.script else "",
                           "idempotency_key": args.key, "minutes": args.minutes, "brief": args.brief}).encode()
    elif args.command in ("request", "upload"):
        if not args.path.startswith("/") or args.path.startswith("//"):
            raise ValueError("Use a complete portal path beginning with one slash")
        url = HOST + args.path
        method = args.method.upper() if args.command == "request" else "POST"
        if args.command == "request" and args.json:
            data = args.json.read_bytes(); json.loads(data)
        elif args.command == "upload":
            if args.file.stat().st_size > 10 * 1024 * 1024:
                raise ValueError("Reference images must be at most 10 MB")
            boundary = "forge-" + uuid.uuid4().hex
            chunks = []
            for field in args.field:
                name, value = field.split("=", 1)
                if not name.isidentifier(): raise ValueError("Invalid form field")
                chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="reference.png"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
            chunks.extend([args.file.read_bytes(), f'\r\n--{boundary}--\r\n'.encode()])
            data, content_type = b"".join(chunks), "multipart/form-data; boundary=" + boundary
    else:
        url += "/videos/" + urllib.parse.quote(args.id, safe="")
        if args.command == "action":
            url += "/actions/" + urllib.parse.quote(args.action, safe="")
            method, data = "POST", args.json.read_bytes() if args.json else b"{}"
            json.loads(data)
        elif args.command != "project":
            url += "/" + args.command
            if args.command == "stop": method, data = "POST", b"{}"
            if args.command == "download": url += "?kind=" + args.kind
    with request(method, url, data, content_type) as res:
        if args.command == "download":
            import shutil
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("wb") as out: shutil.copyfileobj(res, out)
            print("Downloaded", args.out.resolve())
        else:
            payload = res.read().decode("utf-8")
            try: print(json.dumps(json.loads(payload), ensure_ascii=False, indent=2))
            except ValueError: print(payload)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: " + exc.read().decode("utf-8", errors="replace")[:2000], file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr); sys.exit(1)
