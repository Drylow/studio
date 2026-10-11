# Deuxième vidéo anime — L contre Light

Titre choisi par l'utilisateur : **L Outsmarts Light Analysed like Chess | Death Note**.
Scène : première confrontation télévisée, épisode 2. Le passage garde la
provocation, la mort du faux L, la révélation du piège, la localisation au Kanto
et la conclusion « I am justice ». Aucun voiceover.

L ouvre par son dispositif de télévision et son représentant Lind L. Tailor :
camp blanc. Light : camp noir. Lind n'est pas présenté comme le vrai L dans nos
commentaires. Les pions des analyses suivent ces camps ; guide et bilan utilisent
le pion neutre. Les évaluations sont éditoriales, pas celles d'un moteur d'échecs.
Ce piège donne l'avantage à L ; il ne révèle pas encore l'identité de Light.

## Acquisition et limites

Recherche avec Nexlev et Algrow le 11 octobre 2026. La copie longue
`uuVufrmNc2A` est refusée : image 640×480, seules variantes HD proposées
explicitement agrandies. La copie `NIJG2S9jj5w` plafonne à 720p. La version
`HmiYGLStrWg` comporte un dialogue différent et ne sert pas de raccord.

Quatre extraits publics de la chaîne Anime Remastered sont acquis en 1920×1080,
23,976 images/s, avec doublage anglais original. Le premier passe par le MCP
Algrow ; les trois suivants par le téléchargement YouTube normal de flux publics.
Les pistes anglaises sont vérifiées dans les métadonnées, notamment sur les
deux vidéos qui proposent plusieurs langues.

| Ordre | Extrait source | Codec acquis |
|---|---|---|
| 1 | [Lind L. Tailor challenges Kira](https://www.youtube.com/watch?v=Owdxb3BmmIo) | H264 |
| 2 | [Light gets outsmarted by L](https://www.youtube.com/watch?v=aFmEy9tf49c) | H264 |
| 3 | [L humiliates Kira](https://www.youtube.com/watch?v=SnfgTzuUABk) | AV1 |
| 4 | [I am justice](https://www.youtube.com/watch?v=9VpIsZ9TCIg) | AV1 |

Les dix planches des sources à une image par seconde et des captures natives
ont été examinées : aucun watermark de distributeur, sous-titre incrusté ou
texte promotionnel ajouté observé. Les inscriptions de la télévision et du
carnet appartiennent à la scène. Ces copies sont déjà remasterisées par leur
éditeur : la résolution du master de production et la méthode de remasterisation
ne sont pas établies. Ne pas les appeler « master studio brut » ou « 4K natif ».
Notre assemblage ne reconstruit aucun détail et ne masque aucune inscription.

## Montage et description

Outil du collègue conservé : moteur `scene.js`, neuf SVG Chess.com d'origine,
guide de 16 secondes, replay muet derrière chaque analyse, texte anglais tapé,
barre à gauche et montage natif Kdenlive/MLT. Great et Best gardent score et
barre inchangés. Pas de musique ajoutée pendant les scènes ou analyses.
Sneaky Snitch au guide uniquement, comme la V2 choisie par l'utilisateur.
Fin de scène par fondu image et son de 0,5 seconde, puis bilan natif de 12 secondes.
Pas de Subscribe, portrait de Tony ni étiquette de qualité dans l'image.

Description courte :

> Light thinks he has eliminated L. Instead, one televised trap exposes the
> limits of his power and narrows the hunt to Kanto. L plays White. Light plays
> Black. Every move analysed like chess.
>
> #DeathNote #ChessAnalysis #LightYagami #L

Ajouter à la description les crédits de musique présents dans le bundle
`MUSIC_CREDITS.txt`. Aucun crédit n'est affiché à l'écran.

Les sources, transcriptions intégrales, médias de montage et vidéos sont dans
`work/`, ignoré par Git. Les conserver sur ce PC avec le projet et son dossier
`media/`. Ni publication YouTube ni envoi Discord ne sont déclenchés.


## Reproduire l'export local

Depuis la racine du dépôt :

```powershell
powershell -ExecutionPolicy Bypass -File experiments/conversation-chess/chess.ps1 -Mode Render -Source work/chess-studio/death-note/sources/light-vs-l-broadcast-1080.mp4 -Timeline experiments/conversation-chess/episodes/light-vs-l.json -Out work/conversation-chess/death-note-light-l-new
python experiments/conversation-chess/finish-dialogue-audio.py --bundle work/conversation-chess/death-note-light-l-new/kdenlive --out work/conversation-chess/death-note-light-l-new/L-Outsmarts-Light-Death-Note.mp4 --gain-db 6
```

La finition augmente de 6 dB le son des huit passages de scène uniquement.
Guide, clavier, accents de notation et bilan gardent leur niveau. Les dialogues
et la musique intégrée au clip restent dans le même rapport. Le MP4 natif est
préservé ; le flux vidéo de la livraison est copié sans réencodage et son hash
est comparé. Une mesure des crêtes et un décodage intégral sont obligatoires.
Cette étape produit un reçu `.audio.json`. Le projet natif conserve le niveau
initial des sources ; appliquer la même finition après tout nouvel export.

## Livraison vérifiée — 11 octobre 2026

Fichier courant : `work/conversation-chess/death-note-light-l-v1/L-Outsmarts-Light-Death-Note.mp4`.
Durée 7 min 29,1 s ; 1920×1080, 30 images/s, 13 473 images ; H264 et AAC
stéréo 192 kb/s, 48 kHz. Taille 197 943 752 octets. Le reçu public
`episodes/light-vs-l.qa.json` conserve le SHA256 et les résultats.

Les 68 planches représentant toutes les images ont été regardées. Les 38 captures
sélectionnées ont été examinées en montages de plus grande taille, puis les pions
blanc/noir et le bilan en captures pleine résolution : textes lisibles, camps
cohérents, comptage des sept coups correct. Le décodage intégral passe.
Son final : -19,2 LUFS intégrés, crête vraie -3,2 dBFS. Les points de pause sont
placés après les mots alignés ; la dernière réplique complète est conservée.
Les effets de clavier cessent avant les queues de lecture, toutes silencieuses.
Ces contrôles ne sont pas une écoute humaine continue de tout le film.

Projet éditable : `work/conversation-chess/death-note-light-l-v1/kdenlive/project.kdenlive`,
à conserver avec `media/`. Le titre, la description et l'attribution musicale
sont dans `episodes/light-vs-l.publish.txt` et dans `PUBLISH.txt` près du MP4.
Les textes, paramètres et contrôles sont sauvegardés dans Git ; les vidéos,
sources et le bundle lourd restent locaux dans `work/`.

## Paquet et miniature — 11 octobre 2026

Le dossier `work/conversation-chess/death-note-light-l-v1/A-PUBLIER/` rassemble
le MP4 final vérifié, une miniature JPEG 1280×720, le titre et la description
avec l'attribution musicale. La copie vidéo est contrôlée par SHA256.
La miniature dessine L calme face à Light surpris ; les SVG Chess.com originaux
Brilliant et Blunder sont ajoutés avec des inclinaisons opposées de 10°.
Base, prompt, reçu et JPEG sont conservés dans `thumbnails/light-vs-l/`.
Image finale regardée : personnages identifiables, yeux dégagés, badges entiers,
aucun texte ni watermark ajouté. Aucune nouvelle modification du film.

## Retour Content ID et variante graphique — 11 octobre 2026

L'utilisateur signale un blocage mondial Nippon Television sur six plages,
totalisant 358 secondes de la livraison initiale. VAP revendique également
deux musiques intégrées à l'épisode, avec une limitation potentielle des revenus.
Les plages et les titulaires lus dans ses captures sont conservés dans
`episodes/light-vs-l.claims.json`. La livraison initiale reste archivée ; ne pas
la présenter comme un fichier dont YouTube a accepté la diffusion.

Une simple suppression des six plages laisserait 91,1 secondes, mais casserait
la continuité et garderait des fonds de replay de l'épisode sous les analyses.
La nouvelle variante est donc un aperçu graphique distinct de 91 secondes :
guide de 16 secondes, sept analyses de 9 secondes, bilan natif de 12 secondes.
Elle conserve les commentaires originaux, les pions par camp, les SVG vérifiés
et les effets existants. Tous les plans, replays, voix et musiques de l'épisode
sont retirés. Guide et bilan sont régénérés sur un fond graphique original.
Ce n'est plus la scène doublée avec pauses ; c'est une explication graphique.

Préparation puis rendu natif :

```powershell
node experiments/conversation-chess/prepare-graphics-overview.mjs --manifest work/conversation-chess/death-note-light-l-v1/kdenlive/project-manifest.json --out work/conversation-chess/death-note-light-l-v2-graphics/prepared
$env:CHESS_KDENLIVE = 'work/conversation-chess/runtime/kdenlive-26.08.1_standalone/bin/kdenlive.exe'
python experiments/conversation-chess/export-kdenlive.py --manifest work/conversation-chess/death-note-light-l-v2-graphics/prepared/project-manifest.json --bundle work/conversation-chess/death-note-light-l-v2-graphics/kdenlive --render work/conversation-chess/death-note-light-l-v2-graphics/L-Outsmarts-Light-GRAPHICS-V2.mp4
```

Choisir un nouveau répertoire pour chaque autre préparation. La description
adaptée est dans `episodes/light-vs-l.graphics.publish.txt`.
Le contrôle Content ID de cette variante n'a pas été exécuté : seul le retour
de YouTube peut confirmer son statut de diffusion. Aucune contestation envoyée.

Rendu natif livré : `work/conversation-chess/death-note-light-l-v2-graphics/A-REGARDER-V2-GRAPHICS/`.
1920×1080, 30 fps, 2 730 images, 12 073 867 octets. Toutes les images sont
représentées dans 14 planches regardées, avec 11 captures pleine résolution.
Décodage complet réussi. Les médias du bundle sont vérifiés par empreinte :
zéro segment de scène, uniquement fonds graphiques, surimpressions natives,
Sneaky Snitch au guide et effets d'analyse existants. Aucun son d'épisode.
Le reçu `episodes/light-vs-l.graphics.qa.json` conserve ces contrôles et le hash
du MP4. Le dossier contient aussi la miniature, le titre et la description adaptée.
