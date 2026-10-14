#!/usr/bin/env python3
"""Restore the supplied personal access bundle; never print credential contents."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MAGIC = b"TFACCESS\x00\x01"
AAD = b"TubeForge personal access handoff; schema=1; AES-256-GCM"
MAX_CIPHER_BYTES = 32 * 1024 * 1024
MAX_CLEAR_BYTES = 30 * 1024 * 1024
EXPECTED_NAMES = {
    "ssh.zip", "TUBEFORGE_API_HANDOFF.md", "LLM.txt", "endpoints.json", "forge.py"
}
PRIVATE_MANIFEST_NAME = "PRIVATE_MANIFEST.json"


class VaultError(Exception):
    """An error whose message contains no credential contents."""


def decode_key(value: str) -> bytes:
    """Explicit formats prevent interpreting a password as an encryption key."""
    value = value.strip()
    try:
        if value.startswith("hex:") and re.fullmatch(r"[0-9a-fA-F]{64}", value[4:]):
            key = bytes.fromhex(value[4:])
        elif value.startswith("base64:"):
            key = base64.b64decode(value[7:], validate=True)
        else:
            raise ValueError
    except (ValueError, TypeError):
        raise VaultError("Key must use hex: or base64: followed by a 32-byte key.") from None
    if len(key) != 32:
        raise VaultError("Key must contain exactly 32 bytes.")
    return key


def refuse_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    for component in (absolute, *absolute.parents):
        try:
            mode = component.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise VaultError("Symlinked paths are not allowed for private access files.")


def read_private_file(path: Path, *, size_limit: int = 1024 * 1024) -> str:
    refuse_symlink_components(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > size_limit:
        raise VaultError("The private key input is not a regular bounded file.")
    if os.name == "posix" and info.st_mode & 0o077:
        raise VaultError("The private key input must have mode 600 or stricter.")
    return path.read_text(encoding="utf-8")


def key_from_env_file(path: Path) -> bytes:
    """Read only one dotenv name; never execute/source a shell file."""
    found = []
    for line in read_private_file(path).splitlines():
        match = re.match(r"^\s*(?:export\s+)?HANDOFF_VAULT_KEY\s*=\s*(.*?)\s*$", line)
        if match:
            value = match.group(1)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            found.append(value)
    if len(found) != 1:
        raise VaultError("The environment file must contain exactly one HANDOFF_VAULT_KEY.")
    return decode_key(found[0])


def decrypt_payload(cipher_path: Path, key: bytes) -> dict[str, bytes]:
    """Authenticate the entire envelope before inspecting or writing plaintext."""
    if cipher_path.stat().st_size > MAX_CIPHER_BYTES:
        raise VaultError("Invalid encrypted archive size.")
    with cipher_path.open("rb") as handle:
        envelope = handle.read(MAX_CIPHER_BYTES + 1)
    if len(envelope) > MAX_CIPHER_BYTES or len(envelope) < len(MAGIC) + 12 + 16:
        raise VaultError("Invalid encrypted archive size.")
    if not envelope.startswith(MAGIC):
        raise VaultError("Unsupported encrypted archive format.")
    nonce = envelope[len(MAGIC):len(MAGIC) + 12]
    try:
        clear = AESGCM(key).decrypt(nonce, envelope[len(MAGIC) + 12:], AAD + MAGIC)
    except InvalidTag:
        raise VaultError("Authentication failed: wrong key or changed archive. Nothing was written.") from None
    if len(clear) > MAX_CLEAR_BYTES:
        raise VaultError("Authenticated archive exceeds the supported size.")
    files: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(clear)) as archive:
            entries = archive.infolist()
            if len(entries) != len(EXPECTED_NAMES) + 1:
                raise VaultError("Unexpected number of archive entries.")
            if sum(item.file_size for item in entries) > MAX_CLEAR_BYTES:
                raise VaultError("Expanded archive exceeds the supported size.")
            for item in entries:
                name = item.filename
                if name in files or name not in EXPECTED_NAMES | {PRIVATE_MANIFEST_NAME}:
                    raise VaultError("Archive contains duplicate or unapproved paths.")
                if item.is_dir() or "/" in name or "\\" in name or Path(name).is_absolute():
                    raise VaultError("Archive paths must be flat regular filenames.")
                unix_mode = item.external_attr >> 16
                if stat.S_IFMT(unix_mode) not in (0, stat.S_IFREG):
                    raise VaultError("Archive contains a symlink or non-regular entry.")
                files[name] = archive.read(item)
    except (zipfile.BadZipFile, RuntimeError, ValueError):
        raise VaultError("Authenticated archive payload is invalid.") from None
    if set(files) != EXPECTED_NAMES | {PRIVATE_MANIFEST_NAME}:
        raise VaultError("Required access files are missing.")
    try:
        manifest = json.loads(files[PRIVATE_MANIFEST_NAME])
        records = manifest["files"]
        if manifest["schema"] != "tubeforge-private-access-files-v1":
            raise ValueError
        if len(records) != len(EXPECTED_NAMES) or {r["name"] for r in records} != EXPECTED_NAMES:
            raise ValueError
        for record in records:
            body = files[record["name"]]
            if len(body) != record["bytes"] or hashlib.sha256(body).hexdigest() != record["sha256"]:
                raise ValueError
    except (KeyError, TypeError, ValueError):
        raise VaultError("Authenticated file integrity manifest did not validate.") from None
    return files


def check_output_path(output: Path) -> Path:
    refuse_symlink_components(output)
    absolute = output.absolute()
    # Plaintext must never be restored into any repository, even an ignored folder.
    for ancestor in (absolute, *absolute.parents):
        marker = ancestor / ".git"
        # Managed sandboxes may reserve an empty, read-only .git directory at
        # /workspace and /tmp. It is not a checkout; real repositories have
        # HEAD/config metadata, or a .git file pointing to a worktree.
        if marker.is_file() or (marker / "HEAD").exists() or (marker / "config").exists():
            raise VaultError("Choose a private output directory outside every Git checkout.")
    if absolute.exists() and not absolute.is_dir():
        raise VaultError("Output must be a private directory.")
    return absolute


def write_payload(files: dict[str, bytes], output: Path, *, overwrite: bool = False) -> None:
    output = check_output_path(output)
    # Validate all existing targets before creating output or writing any file.
    for name in files:
        target = output / name
        if target.is_symlink():
            raise VaultError("Refusing to replace a symlinked private file.")
        if target.exists() and (not target.is_file() or not overwrite):
            raise VaultError("An output file already exists. Use --overwrite only if replacement is intended.")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    refuse_symlink_components(output)
    os.chmod(output, 0o700)
    # A directory descriptor protects publication from an output-directory swap.
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(output, flags)
    try:
        with tempfile.TemporaryDirectory(prefix=".tfaccess-", dir=output.parent) as temp_name:
            temp = Path(temp_name)
            os.chmod(temp, 0o700)
            for name, body in files.items():
                target = temp / name
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(body)
                    handle.flush()
                    os.fsync(handle.fileno())
            for name in files:
                if overwrite:
                    try:
                        info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                        if not stat.S_ISREG(info.st_mode):
                            raise VaultError("Refusing to replace a non-regular private file.")
                    except FileNotFoundError:
                        pass
                    os.replace(temp / name, name, dst_dir_fd=directory_fd)
                else:
                    # link is atomic and fails if another writer created the target.
                    os.link(temp / name, name, dst_dir_fd=directory_fd, follow_symlinks=False)
                    (temp / name).unlink()
    finally:
        os.close(directory_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path(__file__).with_name("tubeforge-personal-access.aesgcm"))
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--key-file", type=Path, help="Private file containing hex: or base64: plus the key.")
    inputs.add_argument("--env-file", type=Path, help="Private dotenv file containing only a selected HANDOFF_VAULT_KEY entry.")
    parser.add_argument("--output", type=Path, required=True, help="Private destination outside every Git checkout.")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly permit replacement of existing regular output files.")
    args = parser.parse_args()
    try:
        if args.key_file:
            key = decode_key(read_private_file(args.key_file, size_limit=512))
        elif args.env_file:
            key = key_from_env_file(args.env_file)
        else:
            value = os.environ.get("HANDOFF_VAULT_KEY")
            if not value:
                raise VaultError("Provide --key-file, --env-file, or the HANDOFF_VAULT_KEY environment variable.")
            key = decode_key(value)
        files = decrypt_payload(args.archive, key)
        write_payload(files, args.output, overwrite=args.overwrite)
        print("Restored 5 original access files and their integrity manifest; private permissions applied.")
        return 0
    except (VaultError, OSError, UnicodeError):
        # Do not include raw exception text from a parser or OS file contents.
        print("Access bundle not restored. Check private key format/permissions, archive integrity, and safe output location.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
