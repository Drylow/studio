# Conversation review — montage local

Le format a été préparé après visionnage réel de ConversationAnalysisGuy
(`InM2zft-iQs`, guide 0–25 s et annotations 25–100 s). Les corrections de
l’utilisateur priment : **barre fine à gauche, vrais glyphes Chess.com, source HD,
sons de frappe et projet Kdenlive éditable**. Aucun script de ce dossier ne touche
le site, les automatisations ou une plateforme de publication.

## Habillage et source

`ratings.json` est le schéma commun du guide et des commentaires : Brilliant,
Great, Best, Excellent, Good, Book, Blunder, Miss, Mistake et Inaccuracy.
Les dix SVG de `assets/chesscom/` sont réutilisés **sans changer leurs tracés ni
leurs couleurs** ; leurs empreintes sont contrôlées au chargement. `sources.json`
conserve leur provenance Chess.com. Ce sont des assets propriétaires : leur
présence dans le dépôt ne constitue pas une licence ouverte. Interesting n’est
pas revendiqué comme classification officielle.

Les deux pages du guide durent 16 s : symboles 0–6 s, explication du score 6–15 s,
puis fondu noir 15–16 s. Le premier frame de la scène reste sur une piste séparée
sous le guide. Les descriptions sont originales. Le Tony approuvé
`assets/tony-pawn.png` reste intact ; la copie transparente séparée
`assets/tony-pawn-overlay.png` sert à la composition, sans carré blanc.

La barre occupe x26, y112, 41×857 px, dans une marge gauche de 72 px. Le film
conserve ses proportions dans 1848×1080, sans recadrer les visages. Le chiffre
s’affiche du côté qui a l’avantage ; le passage de barre dure 0,5 s. Les valeurs
`score_text` sont des **jugements éditoriaux sur la conversation**, jamais des
évaluations Stockfish : signe positif pour le camp blanc, négatif pour le noir
(dans la timeline ; l’écran affiche la valeur absolue comme une barre d’échecs).
Best/Great laissent le score inchangé. La validation refuse un mouvement de score
contradictoire avec la catégorie et le locuteur.

La source réelle doit avoir une piste audio et une hauteur d’au moins 720 px.
Une source 360p est refusée. `--allow-low-res-preview` permet seulement un brouillon
explicitement marqué à l’écran ; un cadre1080p ne transforme pas une source basse
résolution en vidéo HD.

## Commentaires et sons

Après chaque réplique évaluée : grade en haut à gauche, Tony en bas à gauche,
grande bulle blanche et texte noir révélé à 50 caractères/s après 1 s. Le grade,
le pion et la bulle entrent discrètement ; les images d’habillage sont produites
à30 images/s. Les paragraphes peuvent atteindre 260 caractères. Chaque pause dure
3–9 s et réserve au moins 2,5 s de lecture après la frappe.

Le mode `analysis_background: "replay"` rejoue au ralenti les 2–4 s précédentes,
assombries et floutées, puis reprend **exactement** le dialogue au repère : aucun
passage du dialogue n’est supprimé. Cette méthode suit les mouvements et silences
mesurés dans la référence. Le replay ne contient pas de dialogue audible.
`"freeze"` permet une image figée explicite.

Le clavier provient de vraies frappes enregistrées sous CC0 ; les cues brefs
proviennent également d’assets CC0 documentés. **Ce ne sont pas les sons officiels
Chess.com.** `assets/sfx/manifest.json`, `LICENSES.md` et `provenance.json`
conservent sources, dérivations et gains. `sfx.mjs` choisit des frappes physiques
variées, ignore les espaces et limite la cadence à 16 frappes/s. La frappe s’arrête
avec le texte ; la fin de lecture est silencieuse. Un cue léger accompagne les
notes et un accent bref Brilliant/Blunder/erreur. Les SFX sont sur une piste
indépendante ; les dialogues gardent leur audio original et des fondus de 35 ms.
Aucune voix off ni musique ajoutée.

## Préparer les pistes Kdenlive

Dépendances présentes : Playwright dans `frontend/node_modules/`,
`/usr/bin/chromium`, FFmpeg, Kdenlive et MLT. Le rendu navigateur est hors réseau.
L’export natif exige un affichage X11 ou Wayland réel : `QT_QPA_PLATFORM=offscreen`
produit du noir dans les compositions alpha et n’est pas utilisé.
Depuis la racine du dépôt :

```bash
node experiments/conversation-chess/render-clip.mjs --prepare-project \
  --source /chemin/source-hd.mp4 \
  --timeline experiments/conversation-chess/pilot-tony-janice.json \
  --out /tmp/conversation-chess-hd-project
bash experiments/conversation-chess/with-editor-display.sh \
  python experiments/conversation-chess/export-kdenlive.py \
  --manifest /tmp/conversation-chess-hd-project/project-manifest.json \
  --bundle /tmp/conversation-chess-kdenlive \
  --render /tmp/conversation-chess-kdenlive/tony-janice.mp4
```

Le wrapper réutilise une session graphique existante. En cloud sans affichage,
il démarre un Xvfb authentifié, sans écoute TCP, avec cookie non affiché et dossiers
temporaires privés, puis ferme uniquement le processus qu’il a lancé. Il peut
extraire sans root un paquet Debian amd64 précis après contrôle SHA256, si Xvfb
manque ; il ne suppose pas que Xvfb soit installé sur chaque PC. `xauth`,
`xdpyinfo` et les bibliothèques X11/Qt restent nécessaires. Aucun changement de
`HOME` n’est effectué. Le bus de session D-Bus est créé si nécessaire.
Le wrapper a été testé sans affichage préexistant sur un export natif de 2 s :
60 frames à 30 fps, 1920×1080, AAC 48 kHz, composition alpha vue et décodage
intégral sans erreur. Une tentative X11 sans cookie a été refusée. Le processus
Xvfb et ses dossiers temporaires ont été nettoyés après la commande.

`--prepare-project` utilise FFmpeg seulement pour préparer les médias d’entrée.
Il ne fabrique pas de vidéo finale. Il produit `project-manifest.json`, les plans
sans texte, replays muets, habillageMOV qtrle alpha à 30fps, PNG alpha, audio des
dialogues WAV et SFX WAV. Le manifeste donne les frontières cumulées en frames
pour éviter les décalages par arrondis.

L’exporteur construit un **vrai projet Kdenlive**, avec médias relogés dans le
bundle et pistes vidéo/replay/habillage/dialogues/SFX séparées. Le fichier source
original reste disponible dans le bin pour les retouches. Le MP4 final est rendu
par Kdenlive/MLT. Ouvrir le `.kdenlive` pour modifier le montage dans le logiciel.
Les fichiers lourds, extraits protégés et captures restent dans `/tmp` ou
`output/conversation-chess/` ignoré par git ; ils ne sont pas ajoutés au dépôt public.

Pour corriger seulement le guide d’une préparation déjà faite, reprendre les
mêmes arguments avec `--refresh-project-intro`. Le script contrôle source,
repères, catégories et commentaires, régénère uniquement l’habillage d’intro et
préserve les plans, replays et SFX.

## Timeline revue et pilote

`timeline.empty.json` est un modèle sans repères inventés. Chaque annotation
réelle exige `source_at`, `hold_seconds`, `rating`, `comment`, `speaker`,
`control_after`, `score_text` et `reviewed:true`, après examen de la source.
`source_reviewed:true` et `source_sha256` figent la source exacte. Le score et la
proportion noire sont renseignés ensemble ; ils ne sont pas calculés par un moteur
d’échecs. `replay_seconds` précise la fenêtre de contexte (2–4 s, défaut 3).

Le pilote Tony/Janice utilise une vraie source **1280×720 à 30 fps** de 74,533 s,
recoupée visuellement et par ASR locale : aucune écoute humaine n’est prétendue.
La timeline retient 0–74,5 s de cette source HD, puis cinq commentaires de 7 s
(Book, Great, Brilliant, Blunder, Best), avec l’intro 16 s : **125,5 s /3765 frames**
à préparer. Les scores sont 0.0,−0.3,−0.3,−1.8,−4.8,−4.8, Tony noir/Janice blanc.
La demande de téléchargement maximal a fourni 720p ; l’export 1080p décrit la
résolution du montage et des graphiques, pas des images originales 1080p.

La préparation de ces pistes a été exécutée : 17 médias vidéo décodés entièrement
sans erreur, cinq WAV SFX de 7 s et six WAV de dialogues aux plages contiguës.
Le guide, la barre gauche, les vraies icônes et les bulles sont inspectés à partir des médias réels. Le helper audio a
été vérifié sur des cas synthétiques : variantes, espaces, accents, durées exactes,
48 kHz stéréo, limite −2dBFS et arrêt des frappes. Les WAV réels du pilote sont
mesurés séparément : frappes présentes puis lecture silencieuse, pic de clavier
−16,9 dBFS et accent Blunder −13,8 dBFS. Le projet/export natif et le MP4 final font l’objet de leur
propre rapport de contrôle ; ne pas présenter la préparation comme un export fini.

Le précédent pilote 360p à barre droite est historique et remplacé par cette
révision. Aucune publication automatique de série ni validation de droits n’est
activée. Le résultat reste un pilote privé.

## Aperçus graphiques et fixture

`render.mjs --intro-only --background /chemin/frame.png --out /tmp/intro` produit
un aperçu graphique silencieux 16 s. Il ne remplace pas le montage Kdenlive.
`timeline.demo.json` décrit seulement une mire 1280×720 avec audio synthétique,
avec Great/Good/Inaccuracy ; elle est marquée « Demo · synthetic source » et ne
constitue pas une scène des Sopranos. Les catégories inconnues, les contradictions
de score et les timelines réelles non relues sont refusées.

## Validation du second test

Export réellement effectué via Kdenlive24.12.3 : **125,504s,1920×1080,30fps,
3765frames,H264CRF17/AAC192k**. Les réglages sont confirmés dans son jobMLT
et le fluxH264. La vraie GUI ouvre les cinq pistes et36médias sans ressource
manquante. Le SaveAs séparé conserve les35clips et leurs bornes, avec les
normalisations usuelles des métadonnées, wrappers et plages vides.

Le MP4 final a été décodé intégralement. Quinze images ont été regardées : deux
pages du guide, cinq bulles complètes, frappe progressive, scènes nettes et fin.
Les mesures PCM confirment les cinq cues/sons de frappe, l'arrêt après le texte,
les six parties de dialogue et l'absence de clipping. Aucune écoute humaine
n'est revendiquée.

La vidéo et le bundle sont dans `output/conversation-chess/`, ignoré par Git.
Les plans et niveaux sont éditables dans Kdenlive ; modifier le texte animé
nécessite de régénérer son médiaalpha depuis la timeline JSON. Ce n'est pas
un titre natif à mots directement éditables. Après déplacement complet du
bundle, `export-kdenlive.py --bundle /nouveau/dossier --relocate` actualise sa
racine. Les36ressources relatives de la copie relogée ont été vérifiées.
