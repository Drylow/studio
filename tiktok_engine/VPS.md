# Rendu TikTok sur le VPS existant

Ce chemin a été utilisé le 10 octobre 2026 pour Octave Histoire. Il réutilise le
worker HTTPS `production/news_worker.py`, sans installer quoi que ce soit sur le PC
et sans créer de serveur payant. Un lot de deux vidéos d’environ 90 secondes prend
environ deux minutes de rendu, puis vient le transfert. Ce délai varie selon la charge.

## Préparer les entrées

Depuis la racine du dépôt, utiliser la venv préparée par `tiktok_engine/setup.sh`.
Le `.env` ignoré ou l’environnement doit fournir `NEWS_WORKER_URL` et
`NEWS_WORKER_TOKEN`. Les variables héritées restent prioritaires ; ne jamais
afficher leurs valeurs, changer le jeton pour contourner un refus ou désactiver
le proxy et la vérification TLS. Si ces deux variables manquent, les récupérer sans
les afficher depuis le serveur avec les accès cPanel déjà configurés :

```bash
.venv/bin/python production/server_env.py NEWS_WORKER_URL NEWS_WORKER_TOKEN
```

Chaque vidéo doit déjà avoir :

- `tiktok_engine/videos/<nom>/script.json` et ses images `art/*.png` ;
- `work/tiktok/<nom>/timeline.json` à 30 images/s, d’au moins 61 secondes ;
- `work/tiktok/<nom>/mix.wav`, contenant la voix et les bruitages validés ;
- `work/tiktok/<nom>/QA.json` avec `"approved": true`, écrit après avoir réellement
  regardé toutes les images, toutes les planches et les trois covers.

Le rendu ne génère ni voix, ni illustration, ni nouvelle décision éditoriale.
Il transporte le mix en FLAC sans perte et reprend le moteur actuel du dépôt.

Préparation locale, une fois le script écrit, les faits vérifiés et les images
générées puis regardées selon [ROUTINE.md](ROUTINE.md) :

```bash
# Dans ce cloud, caches accessibles en écriture ; les garder aussi pour les covers.
export npm_config_cache=/workspace/.cache/npm
export PLAYWRIGHT_BROWSERS_PATH=/workspace/.cache/pw-browsers
bash tiktok_engine/setup.sh
.venv/bin/python -c "import requests, dotenv, imageio_ffmpeg"
.venv/bin/python tiktok_engine/build.py work/tiktok/premier_nom \
  --script tiktok_engine/videos/premier_nom/script.json --stills
.venv/bin/python tiktok_engine/build.py work/tiktok/premier_nom \
  --script tiktok_engine/videos/premier_nom/script.json --covers
```

`--stills` prépare la voix, la timeline et les planches ; il ne crée pas le mix.
Regarder toutes les planches et les trois covers, corriger les défauts et relancer
les deux commandes si nécessaire. Écrire `QA.json` seulement après cette relecture.
Puis préparer le mix, sans déclencher de rendu local :

```bash
.venv/bin/python - premier_nom <<'PY'
import json
from pathlib import Path
import sys
sys.path.insert(0, 'tiktok_engine')
import build
work = Path('work/tiktok') / sys.argv[1]
assert json.loads((work / 'QA.json').read_text())['approved'] is True
timeline = json.loads((work / 'timeline.json').read_text())
build.mix(str(work), timeline)
PY
```

`build.mix` réutilise `mix.wav` s’il existe déjà. Après un changement des timings
ou des bruitages, archiver cet ancien mix hors du dossier puis refaire le mix.
Si `requests` manque dans une session neuve, `.venv/bin/pip install requests`
complète cette dépendance du client ; les autres viennent de `setup.sh`.

## Lancer et récupérer

```bash
.venv/bin/python tiktok_engine/vps.py status
.venv/bin/python tiktok_engine/vps.py submit premier_nom second_nom
# Noter le nom tiktok-render-… affiché, puis attendre que le VPS soit libre.
.venv/bin/python tiktok_engine/vps.py status
.venv/bin/python tiktok_engine/vps.py collect tiktok-render-NOM_AFFICHE
```

Le client vérifie que le worker est libre avant le dépôt ; le worker refuse aussi
un dépôt concurrent. Deux vidéos maximum par lot, archive limitée à **9 Mio**.
Si le lot est trop lourd, déposer chaque vidéo séparément. Un refus HTTP 401
reste un refus : réduire le corps de la requête, sans contourner l’authentification.

Un reçu est conservé **avant** le dépôt dans `work/tiktok/vps/<job>.json`. Si le
réseau coupe pendant le dépôt, consulter `status` et tenter `collect` avec ce même
nom avant de relancer un nouveau rendu : le serveur a peut-être accepté le job.
La collecte vérifie taille, MD5 et SHA-256, ainsi que la correspondance avec les
entrées locales. Elle refuse de remplacer un MP4 différent ; archiver ce dernier
hors du dossier de travail si un nouveau rendu est volontairement demandé.

Les MP4 et les reçus privés restent dans `work/`, ignoré par Git. Le résultat
base64 passe uniquement par `/file` avec le jeton du worker ; il n’est jamais
imprimé ni ajouté au dépôt. La collecte ne supprime aucun job sur le VPS.

**Après récupération :** vérifier le décodage complet, la résolution 1080×1920,
le son et les images du MP4 lui-même. Ensuite seulement créer le paquet complet
(description, trois covers, Gofile et `livraison.txt`) :

```bash
.venv/bin/python - premier_nom <<'PY'
import json
from pathlib import Path
import sys
sys.path.insert(0, 'tiktok_engine')
import build
slug = sys.argv[1]
script_path = Path('tiktok_engine/videos') / slug / 'script.json'
script = json.loads(script_path.read_text())
script['_path'] = str(script_path.resolve())
build.deliver(str(Path('work/tiktok') / slug), script)
PY
# Vérifier le jour libre et les posts réels, y compris les pages suivantes.
.venv/bin/python tiktok_engine/zernio.py posts
# Remplacer la date/heure ci-dessous : heure de Bruxelles, 07:00 ou 19:00.
.venv/bin/python tiktok_engine/zernio.py schedule work/tiktok/premier_nom \
  --at AAAA-MM-JJTHH:MM --cover 1
```

Ne pas programmer un créneau déjà occupé. Conserver `zernio.json`, qui permet
de reprendre sans republier la même vidéo. Le client VPS lui-même ne publie rien.

## Dépendances présentes sur le VPS

Installées et testées dans le conteneur du worker le 10 octobre :

- Node : `/data/tiktok-tools/node-v22.20.0-linux-x64/bin/node` ;
- Playwright 1.55.0 : `/data/tiktok-tools/js/node_modules/playwright` ;
- Chromium : `/data/tiktok-tools/browsers` ;
- bibliothèques système Chromium installées par `playwright install-deps chromium` ;
- Python `imageio_ffmpeg`, déjà fourni par le worker.

Le rendu utilise deux vidéos en parallèle, quatre pages Chromium par vidéo,
1080×1920 à 30 images/s, x264 `medium`, CRF 10 et le même encodage audio que
`render.mjs`. `vps_render_job.py` est envoyé comme `code/production/news.py`
dans chaque archive ; il ne modifie pas le serveur ni ses autres productions.
Si ces dépendances disparaissent, refaire leur installation dans le conteneur
du worker existant avant de déposer des vidéos ; ne pas créer un VPS de remplacement.
