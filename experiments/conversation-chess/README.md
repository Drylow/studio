# Conversation review — étude d'habillage

Aperçu autonome **1920 × 1080, 14 secondes, 30 images/s, sans audio**.
Six secondes de légende lisible (Brilliant `!!`, Best `!`, Mistake `?`, Blunder `??`),
puis une démonstration de barre Tony/Ralph et du commentaire « Returned to sender. ».
La barre exprime une lecture éditoriale de l'échange, sans note chiffrée.
Le panneau du montage indique explicitement qu'il ne contient pas encore de scène.

Depuis la racine du dépôt :

```bash
node experiments/conversation-chess/render.mjs \
  --tony experiments/conversation-chess/assets/tony-pawn.png \
  --out /tmp/edgerunners-conversation-chess
```

Pour composer une mascotte Tony fournie en PNG :

```bash
node experiments/conversation-chess/render.mjs \
  --tony /chemin/tony.png --out /tmp/edgerunners-conversation-chess-tony
```

Le panneau de démonstration est blanc pur pour accueillir l'avatar fourni sur fond
blanc, sans carré discordant. L'image est composée telle quelle, sans détourage,
recoloration ou modification de ses pixels. Une image transparente convient aussi.

Dépendances existantes : Playwright dans `frontend/node_modules/`, `/usr/bin/chromium`,
`/usr/bin/ffmpeg`. Les requêtes réseau sont interdites pendant le rendu.
Sorties : `preview.mp4`, `legend.png`, `example.png`, `contact-sheet.jpg`, `render.json`, `frames/`.
Les exports volumineux vont dans `/tmp`, jamais dans le dépôt public.
Sans `--tony`, un pion neutre dessiné par le code remplace la mascotte.
Commande ci-dessus exécutée : lecture des captures et de la planche, contrôle des
dimensions/durée/absence d'audio avec ffprobe et décodage intégral avec ffmpeg.

Cette étude ne contient ni extrait des Sopranos, ni dialogues inventés de la série,
ni voix off, ni logos/sons d'une plateforme d'échecs. Elle ne publie rien et ne
modifie ni le site ni ses automatisations.

## Montage d'un fichier source local

`render-clip.mjs` prépare le vrai parcours : **intro silencieuse de 12 secondes**,
scène avec son audio original, pauses sur images de 3–4 secondes avec une observation
éditoriale en anglais et une évaluation. Le son est silencieux pendant les pauses,
avec fondus de 35 ms aux reprises ; aucune voix ni musique ajoutée. La source est
redimensionnée proportionnellement sans recadrage, dans une zone distincte de
la mascotte : l'avatar ne masque aucun visage de la scène. Pendant les dialogues,
la source occupe **1600×900** avec une barre étroite et une petite mascotte à côté ;
pendant les pauses, **1280×720** avec le commentaire et un cartouche blanc pour Tony.
Une vraie source sans piste audio est refusée.

Copier `timeline.empty.json` dans le dossier de travail et renseigner les repères
**après avoir regardé le fichier** : `source_in`, `source_out` et, pour chaque
annotation, `source_at` (secondes dans la SOURCE, pas le montage final), `hold_seconds`,
`rating`, `comment`, `control_after`, `reviewed`.
Les évaluations sont `brilliant`, `best`, `mistake`, `blunder` ; le contrôle est
`balanced`, `tony`, `ralph`. Mettre `source_reviewed` et chaque `reviewed` à `true`
seulement après cette relecture. `source_sha256`, facultatif, peut figer le fichier
exact ; le rapport enregistre toujours son empreinte.

```bash
node experiments/conversation-chess/render-clip.mjs \
  --source /chemin/source.mp4 --timeline /chemin/timeline-revue.json \
  --tony experiments/conversation-chess/assets/tony-pawn.png \
  --out /tmp/edgerunners-conversation-chess-clip
```

Durée finale = 12 s + (`source_out` − `source_in`) + somme des pauses.
Choisir un extrait cohérent pour viser environ deux minutes ; aucun repère de
Sopranos n'est inventé dans le modèle vide. Ce parcours exige le fichier source
local, ne télécharge rien et ne rend pas une source automatiquement publiable.
Sorties : `clip.mp4`, `contact-sheet.jpg`, `source-freeze-*.png`, overlays,
segments intermédiaires et `render-report.json`. Lire toutes les pauses et écouter
le résultat avant livraison. Les extraits de série ne sont pas ajoutés aux
automatisations existantes.

## Fixture technique vérifiée

`timeline.demo.json` décrit seulement une **mire synthétique FFmpeg**, jamais
un épisode ou une scène de série. Les images du parcours portent « Demo ».

```bash
mkdir -p /tmp/edgerunners-conversation-chess-fixture
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i testsrc2=size=1280x720:rate=30:duration=10 \
  -f lavfi -i sine=frequency=440:sample_rate=48000:duration=10 \
  -c:v libx264 -preset fast -crf 18 -threads 4 -pix_fmt yuv420p \
  -c:a aac -shortest /tmp/edgerunners-conversation-chess-fixture/source.mp4
node experiments/conversation-chess/render-clip.mjs \
  --source /tmp/edgerunners-conversation-chess-fixture/source.mp4 \
  --timeline experiments/conversation-chess/timeline.demo.json \
  --out /tmp/edgerunners-conversation-chess-fixture/render
```

Exécuté et inspecté : 1920×1080, 30 images/s, **27,5 secondes** (12 + 9 + 3 + 3,5),
décodage intégral réussi. Mesure audio : silence réel sur l'intro et les deux
pauses, signal d'origine présent sur les trois portions en mouvement. Les pauses
montrent les frames SOURCE 3 s et 6 s. Ce test prouve le compositing et les pauses,
pas un montage terminé des Sopranos de deux minutes.
