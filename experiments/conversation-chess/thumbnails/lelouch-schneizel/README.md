# Lelouch vs Schneizel — deux propositions de miniature

Créées le 9 octobre 2026 avec l'outil intégré de génération d'images, depuis des références visuelles réellement regardées. Le titre associé reste **Lelouch vs Schneizel Analysed like Chess | Code Geass**. Aucun nom de chaîne n'est incrusté tant que son choix reste ouvert.

- **A-duel.png** : partage symétrique, Lelouch calme et Schneizel surpris.
- **B-calcul.png** : geste de Lelouch près de son visage, cadrage plus tendu et séparateur incliné. Première proposition B, conservée comme archive.

**Choix utilisateur : B.** Sa version corrigée est **B-chesscom.jpg**, avec les SVG originaux Brilliant et Blunder du kit `assets/chesscom/`, vérifiés contre les empreintes de `ratings.json`. Le PNG maître `B-chesscom.png` est conservé. Les pastilles générées de la première proposition sont remplacées. Le nettoyage a été effectué avec l'outil de génération d'images puis seuls les deux coins nettoyés ont été repris : le reste du dessin conserve exactement les pixels de B avant encodage JPEG. Le renderer natif `render-thumbnail.mjs` pose les fichiers SVG originaux, sans les redessiner. Son reçu JSON vérifie cette conservation et les sources des icônes.

Les images font 1 672 × 941 pixels. La livraison corrigée `B-chesscom.jpg` pèse 390 238 octets ; le PNG maître pèse 2 448 558 octets et sert d'archive sans perte. Les premières propositions et la B corrigée ont été regardées à leur taille native puis à 320 pixels de large : personnages reconnaissables, yeux et bouches visibles, deux pastilles lisibles, aucun mot ajouté ou watermark. Ce sont des illustrations générées adaptées à l'anime, pas des captures prétendument extraites de la série.

## Références étudiées

Les miniatures de [Chicanery](https://www.youtube.com/watch?v=mA4t3Ph9DI4), [Walt Outplays Mike](https://www.youtube.com/watch?v=Ef3MhXWWaWA), [Dexter vs Doakes](https://www.youtube.com/watch?v=WUNJZQyuaY4) et [Pretending to be Teacher](https://www.youtube.com/watch?v=4PZXqt0zWkI) de la [chaîne Analysed Like Chess](https://www.youtube.com/@analysedlikechess/videos) ont été regardées. Les planches des vidéos Chicanery et Walt ont également été relues pour la relation entre scène, notation et commentaire. Algrow a fourni le catalogue populaire, Nexlev les vidéos dépassant la moyenne de la chaîne ; leurs résultats ne prouvent pas à eux seuls un effet causal des miniatures sur les vues.

Code visuel retenu : visages dominants, séparation blanche, couleurs de notation teal/rouge, seulement les symboles « !! » et « ?? ». Pas de gros titre, d'échiquier décoratif ou de collage chargé. Les identités et costumes ont été guidés par les images de la source anglaise Lelouch/Schneizel aux secondes 2, 11 et 111, réellement inspectées. Les badges expriment ici la lecture éditoriale de la scène.

Les prompts complets sont conservés dans `prompt-a.txt`, `prompt-b.txt` et `prompt-clean-corners.txt`. Les références téléchargées et la planche de contrôle restent dans `work/chess-studio/thumbnail-reference/`, hors dépôt. Les premières propositions sont conservées ; B est sélectionnée, sans publication.
