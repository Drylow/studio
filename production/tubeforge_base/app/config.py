"""Configuration : lit le fichier .env à la racine (modifiable depuis l'onglet Réglages)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROJECTS_DIR = DATA / "projects"
STYLES_DIR = DATA / "styles"
WEB_DIR = Path(__file__).resolve().parent / "web"
ENV_FILE = ROOT / ".env"

DEFAULTS = {
    "PROXY_BASE_URL": "",
    "PROXY_API_KEY": "",
    "ELEVENLABS_API_KEY": "",
    "SCRIPT_MODEL": "",
    "IMAGE_MODEL": "",
    "TTS_MODEL": "",
    "FAST_MODEL": "",
    "IMAGE_CONCURRENCY": "36",
    "LLM_CONCURRENCY": "36",
    "WORKSPACE_PLAN_CONCURRENCY": "6",
    "TTS_CONCURRENCY": "3",
    "RENDER_CONCURRENCY": "1",
    "PROJECT_PARALLEL": "6",
    "STUDIO_ROOT": "",
    "RENDER_BACKEND": "native",
    "RENDER_WORKERS": str(max(2, min(8, (os.cpu_count() or 4) // 2))),
    "PORT": "8765",
    "HOST": "127.0.0.1",
    "LOCAL_TTS_URL": "http://127.0.0.1:8790",
    "LOCAL_TTS_VRAM_GB": "10",
    "LOCAL_TTS_WORKERS": "2",
    "LOCAL_TTS_MTL_PARALLEL": "4",
    "FFMPEG": "ffmpeg",
    "FFPROBE": "ffprobe",
}

DEFAULTS.update({"IMAGE_PROVIDER": "cli_proxy", "USEAPI_API_KEY": "",
                 "USEAPI_IMAGE_MODEL": "", "USEAPI_IMAGE_CONCURRENCY": "3"})

SECRET_KEYS = {"PROXY_API_KEY", "ELEVENLABS_API_KEY", "USEAPI_API_KEY"}

_values: dict[str, str] = {}


def _read_env_file() -> dict[str, str]:
    out = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def reload() -> None:
    _values.clear()
    _values.update(DEFAULTS)
    _values.update(_read_env_file())
    for k in DEFAULTS:
        if os.environ.get(k):
            _values[k] = os.environ[k]


def get(key: str) -> str:
    if not _values:
        reload()
    return _values.get(key, DEFAULTS.get(key, ""))


def get_int(key: str) -> int:
    try:
        return int(get(key))
    except ValueError:
        return int(DEFAULTS[key])


def update(changes: dict[str, str]) -> None:
    """Met à jour le .env en conservant les commentaires et l'ordre des lignes."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    remaining = dict(changes)
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k in remaining:
                lines[i] = f"{k}={remaining.pop(k)}"
    for k, v in remaining.items():
        lines.append(f"{k}={v}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for k in changes:
        os.environ.pop(k, None)
    reload()


def public_settings() -> dict:
    if not _values:
        reload()
    out = {}
    for k in DEFAULTS:
        v = get(k)
        if k in SECRET_KEYS:
            out[k] = (v[:4] + "…" + v[-4:]) if len(v) > 10 else ("•••" if v else "")
        else:
            out[k] = v
    return out


DATA.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)
STYLES_DIR.mkdir(exist_ok=True)
