"""Upload the reviewed Quiet Little Worlds preview once, preserving uncertain outcomes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import sys

import requests

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "output/nature-sleep/night-train-preview"
VIDEO = HERE / "Quiet-Little-Worlds-Night-Train-24s.mp4"
QA = VIDEO.parent / "qa/technical-review.json"
REVIEW = HERE / "visual-review.json"
RECEIPT = HERE / "gofile-receipt.json"
PENDING = HERE / "gofile-pending.json"


def save(path, data, private=False):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if private:
        os.chmod(path, 0o600)


def digest():
    blob = VIDEO.read_bytes()
    return {"name": VIDEO.name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
            "md5": hashlib.md5(blob).hexdigest()}


def data(response, label):
    if response.status_code != 200:
        raise RuntimeError(f"{label}: HTTP {response.status_code}; no automatic retry.")
    body = response.json()
    if body.get("status") != "ok" or not isinstance(body.get("data"), dict):
        raise RuntimeError(label + ": no success confirmation; no automatic retry.")
    return body["data"]


def main():
    expected = digest()
    report = json.loads(QA.read_text())
    review = json.loads(REVIEW.read_text())
    if not report.get("technical_pass") or report.get("sha256") != expected["sha256"] \
            or not review.get("approved_for_preview_delivery") or review.get("sha256") != expected["sha256"]:
        raise RuntimeError("The actual file lacks a matching technical and visual review.")
    if RECEIPT.exists():
        old = json.loads(RECEIPT.read_text())
        if old.get("file") != expected:
            raise RuntimeError("An existing delivery refers to a different file.")
        print(json.dumps({"status": "already-uploaded", "url": old["url"]}))
        return
    if PENDING.exists():
        raise RuntimeError("An earlier upload is uncertain; inspect its private response before retrying.")
    with requests.Session() as session:
        response = session.get("https://api.gofile.io/servers", timeout=(15, 30), allow_redirects=False)
        servers = data(response, "GoFile server selection").get("servers", [])
        candidates = [s for s in servers if isinstance(s, dict) and re.fullmatch(r"store[a-z0-9-]+", str(s.get("name", "")))]
        if not candidates:
            raise RuntimeError("No supported GoFile upload server returned.")
        server = next((s for s in candidates if s.get("zone") == "eu"), candidates[0])
        save(PENDING, {"file": expected, "started_at": datetime.now(timezone.utc).isoformat()})
        with VIDEO.open("rb") as stream:
            response = session.post("https://" + server["name"] + ".gofile.io/uploadFile",
                                    files={"file": (VIDEO.name, stream, "video/mp4")},
                                    timeout=(20, 180), allow_redirects=False)
        # Keep owner credentials private before any schema assertions can fail.
        save(HERE / "gofile-response-private.json", {"status_code": response.status_code, "body": response.json()}, private=True)
        uploaded = data(response, "GoFile upload")
        if uploaded.get("md5") != expected["md5"] or int(uploaded.get("size", -1)) != expected["bytes"] or digest() != expected:
            raise RuntimeError("GoFile size or checksum confirmation failed; pending retained.")
        page = uploaded.get("downloadPage", "")
        if not re.fullmatch(r"https://gofile\.io/d/[A-Za-z0-9]+", page):
            raise RuntimeError("No valid download page confirmed; pending retained.")
        result = {"url": page, "file": expected, "uploaded_at": datetime.now(timezone.utc).isoformat(),
                  "kind": "Quiet Little Worlds — silent 24-second night train preview with forest parallax, rain and steam",
                  "md5_and_size_verified": True}
        save(RECEIPT, result)
        PENDING.unlink()
        print(json.dumps({"status": "upload-confirmed", "url": page, "bytes_verified": expected["bytes"]}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
        # Request exceptions can contain signed URLs: report only the failure type.
        if isinstance(exc, requests.RequestException):
            raise SystemExit("Network failure; outcome may be uncertain. No retry performed.") from None
        raise SystemExit("Upload stopped: " + str(exc)) from None
