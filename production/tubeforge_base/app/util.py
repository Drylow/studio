import asyncio
import json
import os
import re
import subprocess
import time
import unicodedata
from pathlib import Path

from . import config


def now() -> float:
    return time.time()


def slugify(text: str, maxlen: int = 50) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:maxlen].strip("-") or "video"


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for attempt in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows : fichier ouvert ailleurs un court instant
            time.sleep(0.05 * (attempt + 1))
    os.replace(tmp, path)


def parse_json(text: str):
    """Extrait le premier objet/tableau JSON d'une réponse de LLM (tolère ```json ...```)."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text, strict=False)  # tolère les retours à la ligne dans les chaînes
    except json.JSONDecodeError:
        pass
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise ValueError("No JSON in the response")
    start = min(starts)
    closer = "}" if text[start] == "{" else "]"
    end = text.rfind(closer)
    return json.loads(text[start:end + 1], strict=False)


def ffprobe_duration(path: Path) -> float:
    if not config.get("FFPROBE"):
        import av
        with av.open(str(path)) as container:
            if container.duration is None:
                raise ValueError("Media duration is unavailable")
            return container.duration / av.time_base
    out = subprocess.run(
        [config.get("FFPROBE"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


async def run_cmd(args: list[str], cwd: Path | None = None) -> str:
    proc = await asyncio.create_subprocess_exec(
        *[str(a) for a in args], cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"{Path(str(args[0])).name} failed ({proc.returncode}): {err.decode(errors='ignore')[-1500:]}")
    return out.decode(errors="ignore")


def fmt_srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
