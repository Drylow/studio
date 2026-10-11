# Quiet Little Worlds — cottage pastel en pixel art

Nouvelle direction demandée le 11 octobre 2026 après le rejet de l’animation
botanique C. L’utilisateur aime et conserve le nouveau décor montré, puis
demande davantage d’animation visible et de détails. L’animation reste à juger
par lui. Nom, bio et avatar de la chaîne sont conservés à ce stade.

## Décor et mouvements

`assets/cottage-pastel-source.png` est une création originale : cottage et
serre, fenêtre éclairée, mare fleurie, saule, ciel mauve et lumière pêche.
L’original généré est conservé intact. Le prompt exact est dans `art-prompt.json`.
Au rendu, l’illustration est placée sur une grille de 480×270 puis agrandie
exactement quatre fois, sans lissage, pour un fichier de présentation 1080p.
La grille est un choix de pixel art, pas une prétention de source native 4K.

L’animation est codée dans `scene.html` :

- Pluie douce à deux distances, avec des gouttes dédiées qui atteignent la mare
  et déclenchent leurs rides d’eau.
- Ondulation des bandes de reflets dans l’eau dégagée et petits scintillements.
- Brise locale dans le saule, attachée au sommet et au tronc ; la maison reste fixe.
- Petites volutes de cheminée, six lucioles et un papillon de nuit à quatre poses
  près de la lanterne extérieure.

Les rives, fleurs et principaux nénuphars sont exclus du mouvement de l’eau.
La caméra reste fixe. Pas de texte, musique, narration ou flash global. Les
trajectoires sont déterministes et reviennent à leur état initial en 24 secondes.
Le raccord exact du dessin ne certifie pas une absence de différence entre les
images compressées du MP4.

## Reproduire le prototype

Depuis la racine, avec les dépendances déjà présentes (Node, Playwright dans
`frontend/`, Chromium système, FFmpeg et Python/Pillow) :

```sh
node experiments/nature-sleep/pixel-cozy/render.mjs output/nature-sleep/pixel-cozy-new
.venv/bin/python experiments/nature-sleep/pixel-cozy/verify.py output/nature-sleep/pixel-cozy-new
```

Le dossier de sortie doit être neuf ; aucun MP4 existant n’est écrasé. Le
navigateur transmet des PNG 480×270 sans perte directement à FFmpeg, qui
agrandit en 1920×1080 et encode en H.264. Pas d’appel Algrow ni de génération
vidéo facturée. Le test dure 24 secondes à 30 images/s, sans audio.

Le vérificateur décode les 720 images, vérifie la durée et extrait 73 captures
du MP4 final sur cinq planches, dont le raccord. La revue des captures doit être
consignée séparément ; elle ne vaut pas visionnage humain continu. Reçus,
vidéos et éventuels identifiants de livraison restent dans `output/nature-sleep/`,
ignoré par Git. Aucun épisode de deux heures ou nouvelle voix commencé.

## Aperçu livré

[Aperçu actuel — 24 secondes, sans son](https://gofile.io/d/fzRYLiGv). Décodage complet
passé, 73 captures sur cinq planches et trois vues natives revues, upload
confirmé par taille/MD5. Avis utilisateur sur l’animation encore attendu.
Reçu public : [DELIVERY.json](DELIVERY.json). Le prochain format est une
[proposition de récit de deux heures](CHANNEL_FORMAT_PROPOSAL.md), pas une
production intégrale déjà lancée.
