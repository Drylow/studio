# Conversation review — montage local

Le guide a été repris **après visionnage réel de l'introduction de
ConversationAnalysisGuy, `InM2zft-iQs`, 0–25 s**. L'ancien panneau à quatre cartes
est abandonné. Le nouveau parcours comprend deux pages sur le premier frame de
la scène assombri : légende de 0 à 6 s, explication de la barre de 6 à 15 s,
puis fondu noir jusqu'à 16 s. La disposition, les catégories et les couleurs
suivent le guide observé ; les descriptions et les icônes vectorielles sont
originales. Cela ne prétend pas copier chaque pixel ni chaque phrase.

`ratings.json` est le schéma unique du guide et des annotations : **Brilliant
`!!`, Great `!`, Best `★`, Excellent (pouce), Good `✓`, Book (livre), Blunder
`??`, Miss `×`, Mistake `?`, Inaccuracy `?!`, Interesting `!?`**. Il ne contient
ni Forced, ni Checkmate, ni Draw : ces catégories n'apparaissent pas dans ce guide.
Les contrôles refusent un identifiant d'évaluation inconnu.

L'avatar Tony approuvé, `assets/tony-pawn.png`, est dessiné tel quel. Ses pixels,
sa tête, ses badges et son pion noir ne sont ni modifiés ni détourés. La composition utilise une copie transparente distincte dans le guide et les
bulles ; le PNG original reste le fichier de référence inchangé. Aucune génération
visuelle supplémentaire n'est lancée par les scripts. Le compositing du guide et des bulles
utilise séparément `assets/tony-pawn-overlay.png` (fond transparent, préparé et
regardé par l'agent principal) : `--tony-overlay /chemin/image.png` peut le
remplacer. L'original approuvé est toujours conservé intact.

## Intro autonome

Depuis la racine du dépôt, avec une image PNG extraite de **sa propre source** :

```bash
node experiments/conversation-chess/render.mjs --intro-only \
  --tony experiments/conversation-chess/assets/tony-pawn.png \
  --background /chemin/premier-frame.png \
  --out /tmp/conversation-chess-intro
```

Sans `--background`, le guide a un fond sombre neutre. C'est un aperçu graphique,
pas un épisode monté. Sorties : `preview.mp4` (1920×1080, 30 images/s, 16 s,
silencieux), `legend.png`, `example.png` (page barre), `contact-sheet.jpg`,
`render.json`, `frames/`. Les fichiers de référence visionnés et les exports
volumineux restent dans `/tmp`, jamais dans le dépôt public.

Dépendances existantes : Playwright dans `frontend/node_modules/`,
`/usr/bin/chromium`, `/usr/bin/ffmpeg`. Le navigateur de rendu interdit le réseau.
Le code n'accède ni au site ni aux automatisations et ne publie rien.

## Montage d'un fichier source local

`render-clip.mjs` utilise la première image sélectionnée de la source derrière
les deux pages du guide. Après ces 16 secondes silencieuses, la scène garde son
**audio original**, sans voix off ni musique ajoutée. Les blocs de lecture durent 3–9 s (5–9 s pour les paragraphes),
avec une courte observation en anglais dans une grande bulle blanche, l'icône
d'évaluation en haut à gauche et la mascotte en bas à gauche. La scène est floutée
et assombrie pendant cette lecture, comme dans les annotations réellement vues
(`InM2zft-iQs`, plage 25–100 s). La référence garde parfois du mouvement derrière
la bulle. Les mesures audio du fichier de référence montrent que les dialogues
s'arrêtent pendant cette lecture. Notre mode `analysis_background: "replay"`
rejoue au ralenti les 2–4 s précédant le repère, floutées et muettes, étirées
sur la durée de lecture, puis reprend exactement le dialogue au repère : aucune réplique n'est jetée. `"freeze"` reste possible
pour un fond figé explicite. Le texte anglais peut atteindre 260 caractères ; il apparaît
une seconde après l'icône/la mascotte, progressivement à 50 caractères/s,
puis reste lisible au moins 2,5 s.
Ces lectures sont silencieuses ; les reprises audio ont des fondus de 35 ms. Une vraie
source dépourvue de piste audio est refusée.

Le film est redimensionné proportionnellement dans **1800×1080**, sans recadrage,
à côté d'une barre **120 px à droite** : noir en haut, blanc en bas. Les bandes
nécessaires pour conserver tous les pixels restent noires. Il n'y a plus de
cadre de tableau de bord ni de cartouche Tony permanent. Le commentaire apparaît
uniquement lors d'une pause, après la réplique évaluée. Regarder chaque pause
pour vérifier la lisibilité et le choix du repère ; le film redevient net dès
la reprise.

`black_label` et `white_label` nomment les deux camps (par exemple Tony/Janice).
Un nombre de 0 à 1 donne la proportion noire : `0.5` signifie l'égalité,
`0.55` un petit avantage noir. Ces proportions ne sont jamais affichées en chiffres.
La transition de barre prend 0,5 s. Les alias `balanced`/`black`/`white` restent
acceptés. Les anciens alias `tony`/`ralph` restent acceptés pour compatibilité. Les états de
barre sont une lecture éditoriale, pas un score mesuré par un moteur. Le guide
explique que Best/Great ne déplacent pas la barre, Book peut donner un petit
avantage, Brilliant augmente l'avantage et les autres catégories indiquent
une perte de contrôle pour le locuteur. Les annotations réelles doivent être
relues pour respecter ce sens et l'identité du locuteur.

Copier `timeline.empty.json` dans un dossier de travail et renseigner les repères
**après avoir regardé le fichier** : `source_in`, `source_out`, et pour chaque
annotation `source_at` (secondes dans la SOURCE), `hold_seconds`, `rating`,
`comment`, `speaker` (`black` ou `white`), `control_after` (proportion noire de 0 à 1), `reviewed`. Le locuteur permet de refuser une direction de barre
contradictoire ; Best/Great doivent toujours laisser la barre inchangée.
Renseigner aussi `black_label` et `white_label` pour la scène réelle,
et `analysis_background: "replay"` pour le fond mobile muet.
`replay_seconds`, facultatif (2–4, défaut 3), ajuste le contexte rejoué. Mettre `source_reviewed` et chaque
`reviewed` à `true` uniquement après cette relecture. `source_sha256` peut figer
le fichier exact ; le rapport enregistre toujours son empreinte.

```bash
node experiments/conversation-chess/render-clip.mjs \
  --source /chemin/source.mp4 --timeline /chemin/timeline-revue.json \
  --tony experiments/conversation-chess/assets/tony-pawn.png \
  --out /tmp/conversation-chess-clip
```

Durée finale = 16 s + (`source_out` − `source_in`) + somme des pauses.
Choisir un extrait cohérent pour environ deux minutes ; aucun repère de Sopranos
n'est inventé dans le modèle vide. Le script exige un fichier local, ne télécharge
rien et ne rend pas un extrait de série automatiquement publiable.
Sorties : `clip.mp4`, `contact-sheet.jpg`, frames de pause, overlays, segments
intermédiaires et `render-report.json`. Regarder toutes les pauses et écouter le
résultat avant livraison. Aucune activation automatique de contenu protégé.

## Fixture technique

`timeline.demo.json` décrit uniquement une **mire FFmpeg avec un signal audio**,
pas une scène de série. Elle comporte Great, Good et Inaccuracy pour exercer les
nouvelles catégories. Les images de scène portent « Demo · synthetic source ».

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
  --out /tmp/conversation-chess-full-legend-internal/fixture
```

Fixture finale exécutée et décodée intégralement : 1920×1080, 30 images/s, **41,5 s**
(16 + 9 + 4 + 4,5 + 8), avec bulle et texte progressif. Ce test valide le
compositing, les catégories et les pauses ; ce n'est pas un épisode des Sopranos.

QA du guide : captures 1920×1080 et mobile paysage 844×475 regardées,
11 catégories présentes, aucun débordement. L'empreinte Git du PNG approuvé
est inchangée. Great/Good/Inaccuracy sont présentes dans le rapport de fixture ;
la catégorie non observée `forced` est explicitement refusée.

Intro autonome également exécutée sur le premier frame du vrai fichier
Tony/Janice acquis : 16,000 s, 1920×1080, 30 images/s, sans piste audio.
Captures des deux pages et planche regardées, décodage intégral réussi.
Ce fichier d'intro interne seul ne remplace pas le pilote de deux minutes.

## Pilote réel vérifié

Pilote exécuté avec la timeline revue de travail et le fichier source local
complet. `pilot-tony-janice.json` conserve ces repères pour le reproduire :

```bash
node experiments/conversation-chess/render-clip.mjs \
  --source /chemin/tony-janice-harpo-full-360p.mp4 \
  --timeline experiments/conversation-chess/pilot-tony-janice.json \
  --out /tmp/conversation-chess-tony-janice-pilot
```

Résultat réellement rendu : **125,564 s**, 1920×1080, 30 images/s. Intro16 s,
74,5 s de dialogue source (99,4–173,9) et cinq analyses de7 s : Book, Great,
Brilliant, Blunder, Best. Les deux pages du guide, les cinq bulles complètes,
les portions nettes et la fin ont été regardées ; aucun texte coupé. Le fichier
est décodé intégralement sans erreur. Le guide utilise également la copie
transparente de Tony, sans carré blanc ; l'original approuvé reste inchangé.

Audio mesuré sur PCM décodé : silence dans le guide et les cinq analyses ;
audio d'origine présent dans les six portions de dialogue (−24 à−35 dBFS RMS).
Les intervalles source sont contigus : aucune réplique n'est supprimée par
les analyses ajoutées. Aucun son ni voix off n'est ajouté. La synchronisation
éditoriale repose sur l'ASR local et la transcription recoupée, puis les captures ;
aucune écoute humaine n'est revendiquée.

La source acquise est **640×360**, agrandie pour le test : le cadre1080p ne la
transforme pas en source HD. Ce pilote est une prévisualisation privée, pas une
publication ni une validation de droits. MP4/source/captures restent dans des
emplacements ignorés ; aucune vidéo de référence n'est ajoutée à git.

Pour corriger uniquement le guide d'un montage déjà rendu : relancer la même
commande avec `--refresh-intro`. Le script exige les mêmes source, repères,
annotations et noms, réencode les deux segments du guide, puis réassemble les
segments de scène existants. Ce parcours a été exécuté et le résultat redécodé.
