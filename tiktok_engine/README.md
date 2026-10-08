# Octave Histoire (@octave.histoire) : l'outil du compte TikTok (démarré le 7 oct. 2026)

Outil à part, propre à ce compte TikTok : tout est dans `tiktok_engine/`, indépendant des chaînes
YouTube. Pas encore automatisé : l'utilisateur veut en reparler (8 oct. : « on va regarder demain »).

Demande de l'utilisateur (7 oct., soir) : un compte TikTok français **dans le même style visuel
que @archibald.media**, codé de A à Z en HTML et JavaScript, sans vidéo IA. Vidéos de plus d'une
minute, voix ElevenLabs **v4** (via Algrow, crédits existants), zéro dépense. La piste des persos à
tête d'objet (`production/TIKTOK_PLAN.md`) est **en pause**.

## Ce que l'utilisateur a fixé

- **Copie du style d'Archibald**, pas de ses vidéos : fond **noir**, une seule couleur d'accent,
  un **bleu foncé vif** à la place de son rouge (pas de fond coloré : refusé le 7 oct.).
- **Thèmes** : des **personnages historiques** connus (Napoléon, Mozart, Beethoven…) avec un fait
  surprenant, chiffres à l'appui. Les idées « argent caché » et science pure ont été refusées
  (« à dormir debout »).
- **Les deux premières secondes doivent accrocher** (retour du 7 oct. sur la 1re vidéo : « pas assez
  accrocheur ») : le personnage en grand portrait pixel claque dès la première image (flash), avec la
  phrase choc. Le compteur seul ne suffit pas.
- **Pas d'outro** (« demain on fera… » : refusé) : la vidéo s'arrête sur sa chute.
- **Illustrations** : pixel art généré par Replicate (Retro Diffusion `rd-plus`, guidé par la palette,
  fond transparent) avec `art.py batch videos/<nom>/script.json` (bloc `"art"` du script ; ~11 images
  par vidéo, refaire une image : `--only nom`). Les petits dessins codés de `sprites.js` restent pour
  les icônes (soldats, crânes, thermomètre…). Clé : `REPLICATE_API_TOKEN` dans `.env`.

## Le compte (retenu par l'utilisateur le 8 oct.)

- **Nom et pseudo :** **Octave**, pseudo **@octave.histoire**. Octave est le premier nom de l'empereur
  Auguste, et c'est aussi un terme de musique (Mozart, Beethoven).
- **Bio :** « L'Histoire comme on ne te l'a jamais racontée. 1 vidéo par jour. 📜 » (sur le modèle
  d'Archibald, « 1 vidéo de qualité par jour. 🧠 »). Elle ne change pas d'une vidéo à l'autre.
- **Photo de profil :** la **couronne** bleue en pixel art, centrée sur fond noir pur :
  `brand/photo_profil_couronne.png`. Les 8 autres propositions sont dans `brand/noir_*.jpg`
  (les cercles bleus derrière ont été refusés le 7 oct.).
- **Description de vidéo**, simple comme la 1re d'Archibald : **une phrase + 4 hashtags**, sans
  sources ni émoji (ex. « La Joconde est devenue célèbre grâce à un voleur. #histoire #vulgarisation
  #joconde #louvre »). Champ `caption` du script ; les sources restent dans `sources`, pour nous.

## Règles de qualité ajoutées après la 1re vidéo

- **Vérifier chaque illustration** (mains, doigts, bras, visages) avant le montage. Sur la vidéo
  Napoléon, l'image de Napoléon écrivant avait des mains ratées (remarqué par l'utilisateur, publiée
  quand même). Une image ratée se refait avec `art.py batch … --only nom`.

## Le style d'Archibald (analysé image par image, 5 vidéos, 1 min 40 à 2 min)

- **Mise en page :**
  - Titre blanc en grotesque très gras, en haut (environ 16 % de la hauteur).
  - Gros chiffre en police pixel juste dessous.
  - Le dessin occupe le milieu ; le bas de l'écran reste vide (légende TikTok).
- **Animations :**
  - Le chiffre arrive en grand puis claque, avec un flash plein écran d'une image.
  - Les compteurs défilent (14 506 → 150 000) et s'éclaircissent en fin de course.
  - Tampons inclinés (« TCHERNOBYL », « 1 AN »).
  - Mots barrés.
  - Grilles de carrés ou d'icônes (une icône = N personnes).
  - Barres en segments.
- **Fond :**
  - Noir avec une grille très légère.
  - Poussières colorées qui montent.
  - Lueur ronde derrière le sujet.
  - Vignette.
- **Dessins :** pixel art tramé en damier, petites boucles (fumée, feu, « ? » qui clignote).
- **Son :** voix seule, sans musique ; quelques bruitages (impact sur les chiffres, grondement au début).
- **Récit :**
  - Accroche chiffrée.
  - « vous pensez sûrement à ça ».
  - « sauf que les chiffres… ».
  - « mais attendez ».
  - La leçon.
  - Une suite annoncée (carte de fin pleine couleur « LA SUITE DEMAIN ▶ »).
  - Sources dans la description.

## Le moteur (`tiktok_engine/`)

- **`engine.js` + `sprites.js` :**
  - Dessinent l'image du temps t sur un canevas 1080×1920, de façon déterministe.
  - Éléments : `text` (préréglages `title`, `big`, `num`, `label`, `sub` ; `*mot*` = bleu), `counter`, `stamp`,
    `img` (illustration, effets `in: slam|scan|pop|fade`, `fx: breathe|shiver|bob|zoom`), `sprite`, `icons`,
    `grid`, `bars`, `flow` (bande de Minard), `line`, `forest`, `dna`, `rect`, `endcard`.
  - Les gros chiffres utilisent Tiny5, avec des rayures façon écran LED.
- **`render.mjs` :**
  - Chromium dessine chaque image et ffmpeg l'encode, sur 3 pages en parallèle (environ 13 images/s ici).
  - `--stills` sort des images fixes pour la relecture.
  - `--serve` lance un lecteur local.
- **`build.py <dossier> --script videos/<nom>/script.json` :**
  - La voix vient d'Algrow (ou de `voice.mp3` déposé), puis les mots sont datés (SRT d'Algrow, sinon Whisper).
  - La `timeline.json` est calée sur les mots, puis viennent les planches `check/sheet_*.jpg`, le mix (bruitages synthétisés, -14 LUFS) et `video.mp4`.
- **Ancres de temps dans un script :**
  - `"at": "mot"` (début du mot dans ce temps fort), `"mot#2"`, `"mot+0.3"`, `"mot>"` (fin du mot).
  - Un nombre veut dire des secondes depuis le début du temps fort.
  - Avec `"keep": true`, la scène précédente continue.

Polices sous licence OFL (fichiers et licences dans `fonts/`).

## Livraison de chaque vidéo (demande du 7 oct.)

À chaque vidéo, l'utilisateur reçoit le **même paquet** :
- la vidéo en **qualité maximale** (lien Gofile + fichier) ;
- **3 miniatures** 1080×1920 (bloc `covers` du script, une recommandée) ;
- la **description** à coller, simple comme Archibald : une phrase + 4 hashtags (`caption`).

`build.py` fait tout à la fin du rendu (`deliver` : `covers/`, `description.txt`, `gofile_link.txt`,
`livraison.txt`). Les illustrations se relisent sur `videos/<nom>/art_review.jpg` (pixels ×3) avant le montage.

## Ce que coûte une vidéo (calculé le 8 oct.)

- **Illustrations Replicate** (clé de l'utilisateur) : environ **0,60 $ par vidéo** pour une douzaine
  d'images. Prix `rd-plus`, style `default`, à l'image : 0,044 $ jusqu'à 192×192, 0,058 $ jusqu'à
  256×256 (320×192 compris), 0,077 $ jusqu'à 320×320. Napoléon : 0,58 $ ; Joconde : 0,64 $. Chaque image
  refaite (mains ratées…) coûte le même prix. Les icônes de `sprites.js` sont gratuites.
- **Voix** : crédits Algrow, v4 compte 3 crédits par caractère. Napoléon ≈ 5 100, Joconde ≈ 3 600.
  Une voix refaite après correction se paie une 2e fois.
- **Gratuit** : rendu (machine cloud), datation des mots (Whisper local), bruitages (synthétisés),
  polices (OFL), hébergement Gofile.

## Vidéos livrées

| Date | Vidéo | Lien qualité max |
|---|---|---|
| 7 oct. 2026 | Napoléon en Russie (Minard, les poux, « La santé de Sa Majesté… ») | https://gofile.io/d/XfHd6IAK |
| 8 oct. 2026 | La Joconde, célèbre grâce à un voleur (vol de 1911) | https://gofile.io/d/DOWccY1j |
