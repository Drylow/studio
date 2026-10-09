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
# render.mjs cherche playwright dans tiktok_engine/ ; le navigateur est celui de /opt/pw-browsers
# (session Claude) ou, ailleurs (Codex…), le Chromium que playwright télécharge ici une fois.
[ -d tiktok_engine/node_modules/playwright ] ||
  npm install -q --no-save --no-audit --no-fund --prefix tiktok_engine playwright@1.55.0 >/dev/null
ls -d "${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}"/chromium-* >/dev/null 2>&1 ||
  tiktok_engine/node_modules/.bin/playwright install --with-deps chromium >/dev/null 2>&1 ||
  tiktok_engine/node_modules/.bin/playwright install chromium >/dev/null
# Les clés Algrow et Zernio sont dans le .env du serveur : copiées ici si elles manquent.
need=""
for k in ALGROW_API_KEY ZERNIO_API_KEY; do
  grep -q "^$k=." .env 2>/dev/null || [ -n "${!k}" ] || need="$need $k"
done
[ -z "$need" ] || .venv/bin/python production/server_env.py $need
.venv/bin/python -c "import faster_whisper, scipy; print('Octave Histoire : prêt')"
