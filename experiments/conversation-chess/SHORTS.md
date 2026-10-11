# Deux Shorts anime — 11 octobre 2026

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
