# Utiliser l'outil du collègue sur Windows

Le moteur et l'habillage de `conversation-chess` sont conservés :
grande bulle blanche, vrais SVG Chess.com, frappe, barre gauche, replay muet et
montage Kdenlive avec pistes séparées. Aucun changement du site Flask.
Les archives conservent son pion Tony. Le duel anime complet utilise maintenant
un pion neutre provisoire, à la demande de l'utilisateur ; le futur personnage
reste à choisir. Le moteur graphique est identique.

Depuis la racine du dépôt, installation et diagnostic :

```powershell
powershell -ExecutionPolicy Bypass -File experiments/conversation-chess/setup-windows.ps1
```

Node, Python, FFmpeg et FFprobe doivent être accessibles dans le PATH.
L'installation ajoute Playwright dans ce dossier et son navigateur local.
Si Kdenlive manque, elle extrait la distribution officielle 26.08.1 dans
`work/conversation-chess/runtime/`, après contrôle SHA256. Aucun média lourd
ni exécutable n'est committé. Le lien 7zr peut évoluer : si son empreinte change,
l'installation s'arrête au lieu d'exécuter un binaire non vérifié.

## Premier test anime

Le premier extrait utilise les 19,95 premières secondes du duel anglais
Lelouch–Schneizel : 16 secondes de guide, une pause de 7 secondes, puis reprise
exacte du dialogue. Le premier locuteur observé est Lelouch, donc blanc.
La source existante est **720p** : seuls les graphiques et le montage sont1080p.
La scène reste un aperçu technique marqué, pas une livraison HD finale.

```powershell
powershell -ExecutionPolicy Bypass -File experiments/conversation-chess/chess.ps1 -Mode Render -Preview -Source work/chess-studio/schneizel/lelouch-vs-schneizel-english-720.mp4 -Timeline experiments/conversation-chess/episodes/code-geass-excerpt.json -Out work/conversation-chess/my-preview
```

Le bundle contient `project.kdenlive`, `media/`, la vidéo d'aperçu,
les rapports et `MUSIC_CREDITS.txt`. Garder le dossier `media/` avec le projet.
Les dialogues, ralentis muets, musique, bruitages et habillage sont sur six
pistes distinctes. Changer le commentaire demande de régénérer son calque
depuis le JSON ; il n'est pas un titre Kdenlive dont chaque mot est éditable.

`-Mode Validate` contrôle sans rendre et affiche séparément
`source_quality_accepted`. `-Mode Prepare` construit les médias et le projet
sans exporter de vidéo. `-Mode Render` effectue l'export natif Kdenlive/MLT.
Une nouvelle vidéo finale exige une vraie source au moins1080p, revue et
acceptée dans la timeline. Ne pas transformer une source720p en source acceptée
en l'agrandissant. Un nouveau fichier impose de revoir hash, dialogues et temps.

Le collegue documente une exception pour les originaux Naka720p dont la qualite
native et la disponibilite maximale ont ete verifiees, avec preuves dans la
timeline. Cette exception ne s'applique pas au clip anime YouTube actuel.

L'export ajoute son propre profil dans le dossier local Kdenlive, sans remplacer
`customprofiles.xml`. Le job natif est conservé et contrôlé : H264 CRF17,
1920×1080,30fps, AAC192k/48kHz. Un profil ignoré fait échouer le contrôle.
Un export existant est préservé ; le lanceur choisit alors un nouveau nom daté.
Relancer la préparation remplace la timeline générée : conserver à part un
projet Kdenlive retouché manuellement.

## Episodes

- `episodes/lelouch-vs-schneizel.json` : duel entier, cinq annotations adaptées
  au moteur, dont Great et Best à score inchangé, bilan12s et les deux musiques.
  Deux accents comiques choisis. Source720p refusée pour la version finale.
- `episodes/ayanokoji-vs-ryuen.empty.json` : titre retenu, repères à remplir
  après acquisition d'un clip anglais1080p sans texte incrusté.
- `episodes/game-of-thrones.empty.json` : même format, dialogue à sélectionner.

Les recherches précédentes n'ont pas trouvé de source Ayanokoji–Ryuen réunissant
ces exigences ; les modèles vides ne contiennent pas de temps inventés.
Le bilan conserve le dessin du collègue et compte une seule fois chaque
annotation. La recette complète est dans `ANIME_WORKFLOW.md`.

`dialogue_gain` est un gain linéaire optionnel dans la timeline, entre0 et1
(0 exclu), par défaut1. Il atténue uniquement les pistes de dialogue préparées,
sans normalisation dynamique et sans modifier le fichier source. L'épisode
Lelouch utilise0.65 après mesure de pics interéchantillons à+1.42dBTP dans
l'original. Un changement de gain demande une préparation complète.

`mascot.file` et `mascot.overlay_file` permettent de choisir deux PNG locaux
relatifs au dossier de l'outil. Si seul `file` est donné, il sert aux deux
emplacements. Sans configuration, les assets Tony historiques
restent utilisés. Le duel anime choisit `assets/neutral-pawn.png` pour les deux
emplacements. Les chemins et empreintes sont conservés dans le manifeste.

Options de chemins : `CHESS_KDENLIVE`, `CHESS_FFMPEG`, `CHESS_FFPROBE`,
`CHESS_CHROMIUM` ou `--chromium` pour les deux scripts Node.
Sous Linux, la dépendance Playwright historique dans `frontend/` reste utilisable
et le wrapper d'affichage du collègue est conservé.

Tests : `npm run check --prefix experiments/conversation-chess`.
