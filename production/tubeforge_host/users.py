"""Manage hosted workspace users; passwords are read privately, never printed."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets


def hash_password(password):
    salt = secrets.token_bytes(16)
    rounds = 600000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds).hex()
    return f"pbkdf2_sha256${rounds}${salt.hex()}${digest}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("add", "remove", "list"))
    parser.add_argument("username", nargs="?")
    parser.add_argument("--role", choices=("admin", "worker"), default="worker")
    parser.add_argument("--file", type=Path, default=Path("/opt/tubeforge/config/users.json"))
    args = parser.parse_args()
    data = json.loads(args.file.read_text(encoding="utf-8")) if args.file.exists() else {}
    if args.action == "list":
        print(json.dumps({name: user["role"] for name, user in data.items()}, indent=2))
        return
    if not args.username or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.username):
        parser.error("Use a simple username of 1 to 64 letters, digits, underscores or hyphens")
    if args.action == "add":
        password = getpass.getpass("New password: ")
        if len(password) < 12:
            parser.error("Use a password of at least 12 characters")
        data[args.username] = {"role": args.role, "password_hash": hash_password(password)}
    else:
        data.pop(args.username, None)
    if not any(u["role"] == "admin" for u in data.values()):
        parser.error("Keep at least one owner/admin account")
    args.file.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.file.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o640)
    if os.name != "nt" and os.geteuid() == 0:
        os.chown(temporary, 10001, 10001)
    temporary.replace(args.file)
    print("Workspace access registry updated; no restart needed.")


if __name__ == "__main__":
    main()
