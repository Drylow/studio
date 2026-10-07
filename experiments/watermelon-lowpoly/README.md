# Pixel Cuts — prototype du 7 octobre 2026

Étude inspirée de la vidéo partagée dans [le tweet d'Ernesto Lopez](https://x.com/ErnestoSOFTWARE/status/2107832530770829559). La référence montre une pastèque suspendue découpée en 1, 3, 7, 13, 25 puis 40 passes, avant de laisser les morceaux tomber sur une planche. Le filigrane visible est Velvet Physics. L'auteur du tweet est celui qui partage la vidéo ; son texte ne suffit pas à identifier le logiciel qui a produit l'animation originale.

Ce prototype reprend les trois premiers niveaux, en 12 secondes et 60 images/s. Le fruit, la planche, les ombres et la typographie partagent un rendu pixel art : grille 216 × 384 agrandie ×5 sans lissage, palette de 19 couleurs. Tout le texte visible est en anglais. Les coups de lame durent 0,145 s et sont espacés de 0,17 s dans les séries, avec un accent sonore à chaque coupe. Aucun extrait de la référence n'est utilisé dans le rendu. Aucun fichier du frontend du studio n'est modifié.

## Reproduire

Node récent, Python 3, Pillow et FFmpeg ; aucune clé API.

```sh
npm ci
npm run build
npm run verify
npm run check
npx hyperframes preview --background
npm run render -- --fps 60 --quality looks --strict --no-browser-gpu --workers 1 --output watermelon-pixelcuts.mp4
python qa_frames.py watermelon-pixelcuts.mp4
```

Les versions de Three.js, Cannon et GSAP sont figées dans `package-lock.json`. La composition et le moteur ne font aucun appel réseau lors de l'évaluation d'une image. HyperFrames embarque les polices lors de la compilation.

Le rendu logiciel est utilisé ici : la capture du contexte WebGL avec la carte graphique a dépassé le délai sur cette machine lors du premier essai. Les douze planches `qa/pixelcuts/all-frames-*.jpg` permettent de vérifier les 720 images du MP4.

## Comment ça fonctionne

- `build-simulation.mjs` construit la pastèque facettée, coupe les polygones avec des plans, ferme les surfaces intérieures et prépare les enveloppes convexes des morceaux.
- La physique est calculée à pas fixe de 1/120 s : gravité, collisions contre la planche, le sol et les autres morceaux. Les poses sont enregistrées. `simulation-report.json` conserve les limites mesurées.
- `scene.mjs` interpole les poses selon le temps demandé : rendu identique en lecture, en retour arrière et à l'export. La lame suit une trajectoire scénarisée, synchronisée aux divisions géométriques.
- La chair, la bordure de l'écorce et les pépins sont modélisés. L'éclairage, les ombres et la caméra sont de vraies données 3D.
- `pixel.mjs` réduit le rendu à une palette fixe avec tramage discret et dessine les lettres en pixels sur le même canevas que la scène. Aucun texte lissé n'est superposé à la vidéo.
- `sound.py` synthétise un souffle, un claquement central et une résonance courte pour chaque coupe, ainsi que les impacts physiques plus doux. Le générateur et la normalisation sont fixes, avec une marge avant saturation.

## Limites et suite

Les fragments sont rigides : pas de jus ni de chair qui se déforme. La pastèque est maintenue dans les airs pendant les coups, comme dans la référence. La géométrie low-poly sert de base au rendu pixel art demandé par l'utilisateur après le premier prototype. La peau, les couleurs et la caméra sont des décisions artistiques.

Pour élargir le format : garder ce moteur, remplacer la géométrie et les matériaux, écrire les plans et les trajectoires de lame, puis refaire les contrôles. Les prochaines difficultés seraient les objets creux, la souplesse et les liquides. Blender pourrait servir à ces rendus plus lourds ; il n'est pas requis pour cet essai.

Les fichiers générés (`assets/scene.js`, simulation, WAV, MP4, captures et dépendances) sont exclus de Git et reconstruits par `npm run build`.
