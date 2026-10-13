# Deux pistes — Eren VS Reiner

A : duel anime, chaleur de la cave, regard calme contre regard paniqué.
Recommandée pour la première publication. B : dessin manga plus contrasté,
fond clair, comme alternative à comparer.

Bases créées avec l'outil intégré de génération d'images depuis deux références
de visages adultes de la scène, puis vérifiées visuellement. Les bases ne
contiennent ni texte ni badges. Prompts archivés dans `prompts.json`.

Le compositeur existant ajoute ensuite les deux vrais SVG Chess.com : Brilliant
à gauche, Blunder à droite, inclinés de +10° et −10°. Les reçus `.jpg.json`
vérifient les empreintes originales et l'absence de changement hors badges.
Sorties 1280 × 720 JPEG, moins de 400 Ko chacune. Ne pas remplacer les SVG par
des badges redessinés par génération.

```powershell
node experiments/conversation-chess/compose-thumbnail.mjs `
  --base experiments/conversation-chess/thumbnails/eren-reiner/A-duel.base.png `
  --out CHEMIN_VERS_UN_NOUVEAU_FICHIER.jpg
```

Le choix A est une recommandation éditoriale ; aucun test CTR n'a été effectué.
