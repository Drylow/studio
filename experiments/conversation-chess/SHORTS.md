# Deux Shorts anime — 11 octobre 2026

## Versions corrigées : passages continus et fond noir

Retour utilisateur : trop de coupes soudaines, fond noir permanent, meilleure
source si possible. Il valide la qualité de la source Death Note : elle reste
strictement identique. Les premières versions ci-dessous sont des archives.

- Death Note V2 : `episodes/short-death-note-v2.json`, 2886 images / 96,20 s.
  Les réponses de Light et l'explication de L sont complètes. Une seule ellipse
  sépare l'écriture du compte à rebours ; fondu de six images, sans écran noir
  intercalé ni suppression de mots. Après la première pause, la scène reprend
  au temps source exact où elle s'était arrêtée.
- Classroom V3 : `episodes/short-ayanokoji-v3.json`, 1720 images / 57,33 s.
  Le passage source 44,20–90,733 s est intégral, avec une pause d'analyse.
  Le combat initial reste entier avant les trois phrases d'Ayanokoji.
  Aucune ellipse ni retour artificiel vers un ancien plan pour les pauses.

Le cadre extérieur est noir pur `#000000`, y compris pendant les évaluations.
Le cadrage central large reste constant : pas de bascule portrait / paysage
ni de déplacement brusque du recadrage. Les pauses tiennent la dernière image
source à 1/30 s de la fin ; pas de filtre de luminosité sur le fond. L'audio
entre sur 60 ms et sort sur 120 ms, dans les marges vérifiées autour des mots.
Le seul fondu visuel Death Note dure 200 ms. Les coupes natives de l'anime
restent celles de la scène originale.

La recherche Classroom a comparé les candidats publics aux sources archivées.
`YyV1KEn7o4U` est anglais mais 480p ; `3toHDky3Ub0` est japonais en 720p ;
`hbzKj5uC31g` est japonais. Les versions Crunchyroll portent un logo et des
mentions incrustées ; d'autres versions ont des sous-titres. Pas de nouveau
master anglais brut plus propre confirmé. Le même clip Slash Kyubi est repris
dans son flux H264 natif 1920 × 1080 / 60 fps, environ 1,02 Mb/s ; ancien flux
AV1 environ 0,49 Mb/s. Comparaison visuelle côte à côte : gain modeste, le débit
seul ne prouve pas la qualité. Aucun agrandissement 4K n'est revendiqué.
Source privée : `work/chess-studio/ayanokoji/slash-kyubi-avc.mp4`.

Reproduire avec les mêmes commandes ci-dessous, en remplaçant les timelines
et dossiers par `death-note-v2` et `ayanokoji-v3`. Les gains de dialogue restent
respectivement +8 et +2 dB. Les nouveaux reçus sont dans
`episodes/shorts-2026-10-11-smooth.qa.json`. Les médias et projets restent dans
`work/conversation-chess/shorts/` ; livraison corrigée distincte des anciens
exports, dans `A-POSTER-CORRIGE-2026-10-11/`.

Les exports finaux sont décodés entièrement et leurs 2886 / 1720 images
contrôlées sur 21 / 12 planches, avec les évaluations à taille native.
Le coin extérieur est testé noir pur dans chaque image. Death Note mesure
−16,2 LUFS et −1,2 dBFS de crête vraie ; Classroom −17,0 LUFS et −1,1 dBFS.
Le gain audio conserve le flux vidéo natif à l'identique.

## Première livraison conservée en archive

Demandés séparément : Death Note et Classroom of the Elite. Montage anglais,
1080 × 1920, 30 fps, deux évaluations courtes, répliques complètes, aucun guide
d'ouverture. Le moteur conserve les SVG Chess.com originaux et vérifie leurs
SHA-256. Les pions suivent les camps. Les scores sont éditoriaux.

- `episodes/short-death-note.json` : le leurre télévisé de L ; 1339 images,
  44,63 s ; L blanc, Light noir. Le présentateur est le proxy de L.
- `episodes/short-ayanokoji.json` : Ryuen croit contrôler la confrontation,
  Ayanokoji révèle qu'il voulait précisément cette situation ; 1448 images,
  48,27 s ; Ayanokoji blanc, Ryuen noir.

Le découpage, les évaluations, les commentaires originaux et les cadrages sont
écrits à la main. Les changements de cadrage contigus passent entre les mots.
Les pauses de 4,8 s laissent au moins 2,5 s de lecture après la frappe du texte.
Le bilan de 1,2 s utilise les deux vrais symboles et se ferme en fondu de 0,4 s.
Pas de texte Subscribe, pas de musique ajoutée, pas de voix off.

## Sources et limites de qualité

Death Note réutilise le montage source anglais déjà contrôlé, 1920 × 1080,
remasterisé en amont. Aucun master studio n'est revendiqué.

Classroom utilise le clip public anglais de Slash Kyubi, `ZMamsKeRgew`,
1920 × 1080. Le fichier d'origine comporte un petit logo rouge en bas à droite :
ce n'est donc pas un original 100 % raw. Les gros plans ont un cadrage portrait
écrit plan par plan. Les deux plans larges utilisent le rectangle source
1728 × 972 à x96,y0 pour garder les deux acteurs. Le montage final ne présente
pas ce logo ; aucun masque, flou ou peinture de suppression n'est appliqué.
La définition du conteneur ne certifie pas la qualité d'un master d'origine.
Les autres candidats examinés avaient des sous-titres, des logos ou une
définition insuffisante. Le fichier Algrow annoncé 1080p pour `hdqMd9CnOtA`
était réellement 640 × 360 ; il n'est pas utilisé.

Les vidéos, sources, captures et alignements privés restent dans `work/`,
hors Git. Les données de production ne valent pas une autorisation de
réutilisation ni un résultat de vérification YouTube pour ces nouveaux Shorts.

## Reproduire en local

Depuis la racine du dépôt, Node prépare des fonds portrait, les graphiques
transparents et l'audio séparé. L'export final est natif Kdenlive / MLT.
Exemple Death Note :

```powershell
node experiments/conversation-chess/render-short.mjs --source work/chess-studio/death-note/sources/light-vs-l-broadcast-1080.mp4 --timeline experiments/conversation-chess/episodes/short-death-note.json --out work/conversation-chess/shorts/death-note-v1/prepared
$env:CHESS_KDENLIVE = (Resolve-Path 'work/conversation-chess/runtime/kdenlive-26.08.1_standalone/bin/kdenlive.exe').Path
python experiments/conversation-chess/export-kdenlive.py --manifest work/conversation-chess/shorts/death-note-v1/prepared/project-manifest.json --bundle work/conversation-chess/shorts/death-note-v1/editable --render work/conversation-chess/shorts/death-note-v1/native-portrait.mp4
```

Classroom : source `work/chess-studio/ayanokoji/slash-kyubi.mp4`, timeline
`episodes/short-ayanokoji.json`, dossier final `shorts/ayanokoji-v2`.
Le premier export est conservé comme essai : son image fixe finale montrait
surtout les spectateurs. La V2 a deux `frame_source` explicites, vérifiés
depuis la vidéo : Ryuen à19 s et Ayanokoji à86 s, cadrages propres à chacun.

Le profil documentaire natif doit être `vertical_hd_30`, fourni par la version
portable vérifiée. Une propriété de profil vide fait basculer cette application
sur PAL ; le premier essai rejeté a permis de corriger ce défaut. Le garde-fou
vérifie les dimensions, le nombre d'images et le framerate après l'export.
Le profil paysage reste `atsc_1080p_30`. Voir également le comportement du
[répertoire de profils Kdenlive](https://github.com/KDE/kdenlive/blob/master/src/profiles/profilerepository.cpp).

Les pistes source, graphiques, dialogues et SFX restent éditables dans chaque
`editable/project.kdenlive`. Les analyses utilisent un arrêt sur image.
Les libellés génériques des pistes héritées mentionnent les replays, mais les
fonds de ces deux pauses sont des images fixes.

```powershell
npm run check --prefix experiments/conversation-chess
python experiments/conversation-chess/export-kdenlive.test.py
```

Les reçus audio et QA accompagnent les livraisons. Une finition audio conserve
bit à bit le flux vidéo natif. Les planches de contrôle conservent chaque image
du fichier final, avec des vérifications supplémentaires en taille native.
Le dialogue Death Note reçoit +8 dB ; celui de Classroom +2 dB. Les SFX gardent
leur niveau. Mesures finales : respectivement -18,3 / -18,4 LUFS et -2,3 /
-2,5 dBTP. Reprendre les mesures après toute modification de source ou de coupe.

```powershell
python experiments/conversation-chess/finish-dialogue-audio.py --bundle work/conversation-chess/shorts/death-note-v1/editable --input work/conversation-chess/shorts/death-note-v1/native-portrait.mp4 --out work/conversation-chess/shorts/death-note-v1/Death-Note-Chess-Short.mp4 --gain-db 8
python experiments/conversation-chess/finish-dialogue-audio.py --bundle work/conversation-chess/shorts/ayanokoji-v2/editable --input work/conversation-chess/shorts/ayanokoji-v2/native-portrait.mp4 --out work/conversation-chess/shorts/ayanokoji-v2/Ayanokoji-Chess-Short.mp4 --gain-db 2
```
