# L vs Light — miniature de livraison

Fichier à utiliser : `thumbnail-v1.jpg`, 1280×720, 294 194 octets.
L à gauche avec Brilliant ; Light à droite avec Blunder. Les deux badges
Chess.com sont les SVG originaux du dépôt, inclinés à +10° et -10°.
Leurs empreintes sont vérifiées contre `ratings.json`, sans redessiner les signes.

`base-v1.png` est une illustration produite avec l'outil intégré de génération
d'images, pas une capture de l'épisode. `prompt.txt` conserve la demande complète.
`thumbnail-v1.jpg.json` conserve les empreintes, le cadrage et les placements.
Contrôle visuel de l'image finale : visages et yeux visibles, doigt de L lisible,
badges entiers, aucun texte ajouté. Les pixels hors des coins des badges restent
inchangés avant encodage JPEG.

Reproduction depuis la racine, en choisissant un nouveau fichier de sortie :

```powershell
node experiments/conversation-chess/compose-thumbnail.mjs --base experiments/conversation-chess/thumbnails/light-vs-l/base-v1.png --out experiments/conversation-chess/thumbnails/light-vs-l/thumbnail-v2.jpg
```

Paquet local : `work/conversation-chess/death-note-light-l-v1/A-PUBLIER/`.
Il réunit le MP4 courant, la miniature, `TITLE.txt`, `DESCRIPTION.txt`,
`PUBLISH.txt` et le prompt. Le MP4 copié garde la même empreinte que la livraison
vérifiée ; le montage et le son ne sont pas modifiés.
