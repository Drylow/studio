# Death Note — quatre pistes de miniature

Nouvelle exploration demandée le 11 octobre 2026 après le rejet de la miniature
initiale. La version précédente est conservée. Ces propositions constituent
des pistes visuelles à tester ; aucun résultat de clics n'est établi.

- A : le piège télévisé, avec une accroche courte.
- B : duel de regards, dessin anime net et cadrage très serré, sans texte.
- C : contraste manga noir et blanc sur fond clair, sans texte.
- D : métaphore des pions, L calme face à Light pris de court.

Les bases sont produites par l'outil intégré de génération d'images. Les SVG
Chess.com originaux sont assemblés ensuite avec le compositeur du dépôt,
sans génération ni redessin des signes. Chaque sortie conserve son reçu.
Les prompts exacts figurent dans `prompts.json`.

Les quatre JPEG sont en 1280×720, entre 207 et 342 ko. Le comparatif principal
montre les compositions ; `COMPARATIF-MOBILE.jpg` les compare à 312 pixels
de largeur. Images finales regardées : yeux et accroches dégagés, badges
entiers. Le reçu `verification.json` consigne les contrôles et les empreintes.
Suggestion de test fondée sur la lecture visuelle : A et C. La première raconte
le piège ; la seconde propose un contraste clair très différent du duel initial.

Recomposer A, depuis la racine, vers un nouveau fichier :

```powershell
node experiments/conversation-chess/compose-thumbnail.mjs --base experiments/conversation-chess/thumbnails/light-vs-l/styles-v2/A-piege-tv.base.png --layout experiments/conversation-chess/thumbnails/light-vs-l/styles-v2/A-piege-tv.layout.json --out work/conversation-chess/thumbnail-A-new.jpg
```

L'ordre des deux placements est Brilliant, puis Blunder. Les rotations et
dimensions sont contrôlées pour préserver les proportions et les badges complets.
Sans `--layout`, le compositeur garde son placement historique : le JPEG de la
première miniature est reproduit à l'identique par empreinte SHA256.

Paquet de choix local :
`work/conversation-chess/death-note-light-l-v3-edit/A-TESTER-V3/THUMBNAILS-4-STYLES/`.
Il contient les quatre JPEG, les deux comparatifs, les prompts et le titre.
L'ancienne `THUMBNAIL.jpg` n'est pas remplacée tant qu'aucune variante n'est choisie.

Titre conservé : **L Outsmarts Light Analysed like Chess | Death Note**.
Les illustrations racontent l'angle de la vidéo ; elles ne sont pas des captures
de l'épisode. Aucun changement au film ni publication automatique.
