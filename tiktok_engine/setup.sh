#!/bin/bash
# Prépare une session cloud neuve pour fabriquer une vidéo Octave Histoire (rien à faire si déjà prêt).
#   bash tiktok_engine/setup.sh
set -e
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -c "import numpy, PIL, scipy, imageio_ffmpeg, faster_whisper, dotenv" 2>/dev/null ||
  .venv/bin/pip install -q numpy Pillow scipy imageio-ffmpeg faster-whisper python-dotenv
# render.mjs cherche playwright dans tiktok_engine/ ; le navigateur est celui de /opt/pw-browsers.
[ -d tiktok_engine/node_modules/playwright ] ||
  npm install -q --no-save --no-audit --no-fund --prefix tiktok_engine playwright@1.55.0 >/dev/null
# La clé Algrow est celle du site : copiée depuis le .env du serveur si elle manque ici.
grep -q '^ALGROW_API_KEY=.' .env 2>/dev/null || [ -n "$ALGROW_API_KEY" ] ||
  .venv/bin/python production/server_env.py ALGROW_API_KEY
.venv/bin/python -c "import faster_whisper, scipy; print('Octave Histoire : prêt')"
