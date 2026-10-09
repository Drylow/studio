# Conversation review — montage local

**Sur Windows : [installation, lancement et premiers épisodes anime](WINDOWS.md).**

Déclinaison anime : [recette de production](ANIME_WORKFLOW.md) et
[duel Lelouch–Schneizel](episodes/lelouch-vs-schneizel.json), cinq analyses,
guide16s et bilan12s. La pause après « opinion » laisse une respiration ; Tony
est remplacé par un pion neutre provisoire. La source720p reste un aperçu.

## État actuel et premier long

**Tony contre Richie autour de The Jacket** est choisi par l'utilisateur.
Voir [le découpage](PLAN_TONY_RICHIE.md) et [la comparaison des scènes](FIRST_LONG_OPTIONS.md).
Les trois épisodes S2E3, S2E6 et S2E8 sont maintenant acquis et contrôlés :
originaux anglais natifs 1280×720, sans sous-titres intégrés. C'est le maximum
proposé à ce compte Naka ; les anciens clips compressés sont remplacés.
Le [découpage actuel](tony-richie-source-map.json) comporte neuf extraits,
sept cartes de chapitre et [40 analyses originales](tony-richie-long-timeline.json).
Durée réelle : **15 min 11 s**, 27 326 images. Richie ouvre réellement : Richie
est Blanc, Tony est Noir pendant tout le film. Le master et l'export Kdenlive
natif sont terminés ; décodage complet, contrôles audio et images du vrai film
vérifiés. **Le MP4 et le kit sont livrés via GoFile et Discord** ; voir
[la livraison et ses preuves](TONY_RICHIE_DELIVERY.md). Publication YouTube
manuelle, titre et miniature proposés. Le précédent
[draft de 37 coups](tony-richie-long-editorial-draft.json) reste une archive,
pas le découpage utilisé. Les épisodes, repères de dialogue et accès restent privés.
Le titre et la miniature sont dans le kit après le montage. Tony/Janice reste un test.
Nom de chaîne choisi : **Scene Analysis Guy**. [Avatar et bio](channel-profile/README.md)
reprennent le pion approuvé et présentent un format ouvert aux séries/animés.
La [livraison Discord](DISCORD_DELIVERY.md) envoie les aperçus et paquets finaux
avecGoFile, titre, description, miniature et crédits dans le salon dédié.
Son style v3 est validé ; les anciennes sources et l'ancien tableau sont rejetés.
`pilot-tony-janice-v4.json` corrige les camps et prépare les règles, sans export
du pilote complet. La capture du vrai tableau final Tuco fournie par l'utilisateur
a été examinée ; **une nouvelle outro séparée de12s est exportée et contrôlée**.
La scène où Richie offre la veste est désormais téléchargée en720p réel et
le court passage où il la découvre sur quelqu'un d'autre en **1920×1080 réel**.
Ces courts imports historiques ne servent pas au nouveau long Naka.
La [méthode d'import vérifiée](SOURCE_IMPORT.md) conserve le contrat API et
les contrôles réels, sans clés ni fichiers vidéo dans Git.

**Premier personnage qui parle = blanc**, pour toutes les vidéos. La première
réplique peut être sans annotation. Renseigner `opening:{speaker:"white",
label:<white_label>,reviewed:true}` après examen du vrai début. Les camps restent
fixes, score positif blanc / négatif noir. Ne pas déduire les blancs de la
première note ni imposer Tony blanc si l'autre personnage ouvre réellement.

La validation des repères ne lance pas de rendu et indique séparément les
prérequis manquants :

```bash
node experiments/conversation-chess/render-clip.mjs --validate-only \
  --source /chemin/source.mp4 \
  --timeline experiments/conversation-chess/pilot-tony-janice-v4.json
```

`valid:true` valide les repères/camps ; **source_quality_accepted:false** ou
**outro_layout_reviewed:false** signifie que la livraison finale reste bloquée.
Le moteur refuse l'export d'un original non accepté ou d'un tableau rejeté.
`--allow-legacy-opening` est réservé aux anciennes archives et ne valide pas
un nouveau premier locuteur. Ne pas l'utiliser pour une nouvelle vidéo.

Le format a été préparé après visionnage réel de ConversationAnalysisGuy
(`InM2zft-iQs`, guide 0–25 s et annotations 25–100 s). Les corrections de
l’utilisateur priment : **barre fine à gauche, vrais glyphes Chess.com, source HD,
sons de frappe et projet Kdenlive éditable**. Aucun script de ce dossier ne touche
le site, les automatisations ou une plateforme de publication.

## Habillage et source

`ratings.json` est le schéma commun du guide et des commentaires : Brilliant,
Great, Best, Excellent, Good, Book, Blunder, Mistake et Inaccuracy.
Miss est retiré à la demande de l'utilisateur, Interesting violet exclu.
Les neuf SVG actifs de `assets/chesscom/` sont réutilisés **sans changer leurs tracés ni
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

La nouvelle source réelle doit avoir son audio et viser au moins1080p par défaut,
avec `source_quality.accepted_for_final:true` après examen visuel. Une exception
native720 explicite est disponible pour les originaux Naka réellement proposés
à cette résolution maximale : `source_quality.native_hd_review` exige fournisseur,
maximum disponible, revue visuelle, absence de sous-titres incrustés/watermark,
absence d'agrandissement de l'original et justification. Les preuves sont
conservées jusqu'au bundle natif. Une simple cible720 ne valide pas la qualité.
Le fichier du test
est1280×720 mais très compressé (~0,687Mb/s vidéo) ; il est refusé pour la suite.
La résolution seule ne prouve pas le détail. `--allow-low-res-preview` permet
seulement un brouillon technique marqué ; un cadre1080p ne restaure pas les détails
d'une mauvaise source. Cette option ne permet pas de réutiliser l'outro rejetée.

## Nouveau tableau final : capture fournie, aperçu exporté

La disposition suit la capture réellement regardée : Tony au-dessus d'une
grande bulle de bilan dans le panneau gauche (~38,6% de l'écran), puis neuf
grandes icônes à droite. Brilliant/Great/Best/Excellent sur la première ligne,
Good/Inaccuracy/Mistake/Blunder sur la deuxième, Book centré sur la troisième.
Les nombres colorés sont les **totaux des deux personnages**, calculés à partir
de la timeline. Pas de colonnes par joueur ni de catégorie violet/croix.

`outro_summary` est obligatoire pour chaque nouvelle timeline réelle avec bilan :
un résumé anglais original, non vide, au plus700 caractères, adapté à ses
propres échanges. Le moteur refuse aussi un texte qui dépasse la bulle.
Le manifest conserve `recap_summary` et les comptes par camp pour vérification.

Le dernier aperçu privé `output/conversation-chess/outro-v5-clean.mp4` dure
12,01s :360frames,1920×1080 à30fps, export final **Kdenlive/MLT**.
Il reprend seulement les cinq notes du test Janice (Brilliant1, Great1, Best1,
Blunder1, Book1). Le fond720p refusé est volontairement flouté : cet aperçu
valide l'habillage, pas une amélioration des clips ni le film Tony/Richie.
Décodage intégral, quatre captures finales et musique sans écrêtage vérifiés.
Le bandeau de crédits est retiré, à la demande de l'utilisateur et conformément
à la FAQ de l'auteur. La musique exportée reste identique au précédent aperçu.
Les crédits complets accompagnent le MP4 dans `MUSIC_CREDITS.txt` et doivent
être copiés dans sa description lors de la publication surYouTube.
La disposition n'est pas encore approuvée par l'utilisateur.

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
Aucune voix off. La révision musicale du guide et du bilan est décrite ci-dessous.

## Historique v3 : intro musicale et bilan

L'utilisateur trouve le second test bien meilleur et demande maintenant une intro
musicale, un bilan des coups, deux pions de même forme et davantage de petits SFX.
`pilot-tony-janice-v3.json` conserve les cinq repères et dialogues déjà relus ;
il ajoutait12s de bilan, soit137,5s au total. L'utilisateur a ensuite validé le
style, refusé la qualité des clips/tableau final et choisi Tony/Richie pour le long.

Les crédits du créateur identifient **Sneaky Snitch** pour l'intro et
**Scheming Weasel (faster version)** pour l'outro. Les deux enregistrements viennent
directement d'Incompetech sous **CC BY4.0**, avec empreintes, pages originales et
crédits dans `assets/music/`. La corrélation PCM de l'intro identifie le passage
66,104s de Sneaky Snitch. La musique est découpée et fondue sur une pisteA3
indépendante ; elle s'arrête avant les dialogues. Les crédits sont affichés dans
le bilan historiquev3. Le nouveau bilan retire ce bandeau : l'auteur autorise
explicitement les crédits dans la description YouTube. `MUSIC_CREDITS.txt`
accompagne désormais la livraison et le projetKdenlive, avec les seules musiques
réellement utilisées. Copier son texte dans la description lors de l'envoi.

Les pions du haut et du bas utilisent **un seul tracé vectoriel recoloré**.
Le bilan dénombre les annotations par locuteur et par catégorie officielle :
Tony3 (Book, Brilliant, Best), Janice2 (Great, Blunder). Il n'ajoute ni catégorie
violette Interesting, ni pourcentage de précision inventé.

Un seul cue accompagne chaque note : le clic générique ne se superpose plus aux
accents Brilliant/Blunder. Des fondus de4–8ms adoucissent les bords. Deux accents
comiques originauxCC0 sont placés à l'entrée des bulles Book et Blunder. Le passage
de référence à9:12 montre une explosion ; son enregistrement n'est pas réutilisé.
`annotation.comedy_sfx` permet d'autres accents explicitement placés, à partir des
assets locaux documentés. Ils finissent avant la lecture silencieuse.

```bash
node experiments/conversation-chess/render-clip.mjs --prepare-project --allow-legacy-opening \
  --source /chemin/source-hd.mp4 \
  --timeline experiments/conversation-chess/pilot-tony-janice-v3.json \
  --out /tmp/conversation-chess-v3-project
bash experiments/conversation-chess/with-editor-display.sh \
  python experiments/conversation-chess/export-kdenlive.py \
  --manifest /tmp/conversation-chess-v3-project/project-manifest.json \
  --bundle /tmp/conversation-chess-v3-kdenlive \
  --render /tmp/conversation-chess-v3-kdenlive/pilot.mp4
```

Les fichiersMP3 vérifiés rendent ce projet reproductible sans télécharger les
musiques à chaque export. La timeline accepte `outro_seconds` (0 ou6–20s) et
`music.intro`/`music.outro` avec chemin local relatif, SHA256, gain et début.
Ces ajouts exigent `--prepare-project` : le rendu final passe par Kdenlive.
L'ancien manifeste sans musique garde ses cinq pistes ; la version musicale
en possède six, avec indices et cibles calculés automatiquement.

## Préparer les pistes Kdenlive

Pour un long composé de plusieurs scènes, le préparateur local conserve les
dimensions natives, vérifie les SHA des originaux et les durées en images,
insère les chapitres et ne réencode l'audio AAC qu'une fois. Il ne télécharge
aucun média et ne remplace pas les contrôles de l'export final.

```bash
python experiments/conversation-chess/prepare-source-master.py \
  --source-map experiments/conversation-chess/tony-richie-source-map.json \
  --source-root output/conversation-chess/source-cache \
  --out output/conversation-chess/tony-richie-master
```

Le reçu contient le SHA du master réellement écrit. S'il diffère du SHA
enregistré dans la timeline, vérifier le nouveau master et mettre à jour
`source_sha256` avant le préflight ; ne pas supprimer le contrôle d'empreinte.
`--verify-only` recontrôle un master existant sans réencodage. Pour un autre
duel, fournir son propre découpage et `--heading`, vérifier l'audio sélectionné
et conserver ses camps. Les originaux ne sont pas inclus dans Git.

Les commandes historiques ci-dessous reproduisent une préparation technique,
pas une version finale acceptée. Pour les nouveaux projets, partir de
`timeline.empty.json`, vérifier le premier locuteur et remplacer les repères
à partir du vrai fichierHD. Ne pas réutiliser les temps Janice sur une autre source.

Dépendances présentes : Playwright dans `frontend/node_modules/`,
`/usr/bin/chromium`, FFmpeg, Kdenlive et MLT. Le rendu navigateur est hors réseau.
L’export natif exige un affichage X11 ou Wayland réel : `QT_QPA_PLATFORM=offscreen`
produit du noir dans les compositions alpha et n’est pas utilisé.
Depuis la racine du dépôt :

```bash
node experiments/conversation-chess/render-clip.mjs --prepare-project --allow-legacy-opening \
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

## Timeline et historique du pilote v2

`timeline.empty.json` est un modèle sans repères inventés. Chaque annotation
réelle exige `source_at`, `hold_seconds`, `rating`, `comment`, `speaker`,
`control_after`, `score_text` et `reviewed:true`, après examen de la source.
`source_reviewed:true` et `source_sha256` figent la source exacte. Le score et la
proportion noire sont renseignés ensemble ; ils ne sont pas calculés par un moteur
d’échecs. `replay_seconds` précise la fenêtre de contexte (2–4 s, défaut 3).

Le pilote Tony/Janice utilise une vraie source **1280×720 à 30 fps** de 74,533 s,
recoupée visuellement et par ASR locale : aucune écoute humaine n’est prétendue.
La timeline historique v2 retient 0–74,5 s de cette source, puis cinq commentaires de 7 s
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
