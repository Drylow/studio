#!/usr/bin/env python3
"""Restore the personal bundle from an out-of-band key or the existing cPanel account."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile

from decrypt_access import (
    VaultError, check_output_path, decode_key, decrypt_payload, key_from_env_file,
    read_private_file, write_payload,
)


def key_via_cpanel() -> bytes:
    """The configured helper performs authenticated TLS GET; no shell or deployment."""
    helper_path = Path(__file__).resolve().parents[2] / "cpanel.py"
    spec = importlib.util.spec_from_file_location("handoff_cpanel", helper_path)
    if spec is None or spec.loader is None:
        raise VaultError("Existing cPanel helper is unavailable.")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.local_env()
    user = os.environ.get("CPANEL_USER", "")
    if not re.fullmatch(r"[a-zA-Z0-9_]+", user) or not os.environ.get("CPANEL_PASSWORD"):
        raise VaultError("Configure the existing CPANEL_USER and CPANEL_PASSWORD privately.")
    remote = f"/home/{user}/drylow_studio/work/private-access/tubeforge-vault-key.txt"
    with tempfile.TemporaryDirectory(prefix="tubeforge-unlock-") as temp_name:
        temp = check_output_path(Path(temp_name))
        os.chmod(temp, 0o700)
        key_path = temp / "vault-key.txt"
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        count = helper.fetch(remote, str(key_path))
        if count > 512:
            raise VaultError("Private unlock response has an unexpected size.")
        return decode_key(read_private_file(key_path, size_limit=512))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--via-cpanel", action="store_true", help="Fetch only the private vault unlock file using existing cPanel access.")
    source.add_argument("--key-file", type=Path)
    source.add_argument("--env-file", type=Path)
    parser.add_argument("--archive", type=Path, default=Path(__file__).with_name("tubeforge-personal-access.aesgcm"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        # Reject unsafe plaintext destinations before any external request.
        check_output_path(args.output)
        if args.via_cpanel:
            key = key_via_cpanel()
        elif args.key_file:
            key = decode_key(read_private_file(args.key_file, size_limit=512))
        elif args.env_file:
            key = key_from_env_file(args.env_file)
        else:
            value = os.environ.get("HANDOFF_VAULT_KEY")
            if not value:
                raise VaultError("No private unlock key is configured.")
            key = decode_key(value)
        files = decrypt_payload(args.archive, key)
        write_payload(files, args.output, overwrite=args.overwrite)
        print("Restored 5 original access files and their integrity manifest; private permissions applied.")
        return 0
    except (Exception, SystemExit):
        # cPanel exceptions can include session URLs; report no raw exception.
        print("Personal access restore failed. Check private access configuration and safe output location; no credentials were printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
