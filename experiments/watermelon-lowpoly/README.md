# Pixel Cuts — prototype du 7 octobre 2026

Étude inspirée de la vidéo partagée dans [le tweet d'Ernesto Lopez](https://x.com/ErnestoSOFTWARE/status/2107832530770829559). La référence montre une pastèque suspendue découpée en 1, 3, 7, 13, 25 puis 40 passes, avant de laisser les morceaux tomber sur une planche. Le filigrane visible est Velvet Physics. L'auteur du tweet est celui qui partage la vidéo ; son texte ne suffit pas à identifier le logiciel qui a produit l'animation originale.

La version actuelle commence par une preview de 0,85 s : une salve de 32 couteaux entaille la pastèque, puis le montage coupe avant la chute des morceaux. Les niveaux 1, 4, 8, 16 et 32 suivent par cuts directs, en 14,65 secondes et 60 images/s. Chaque niveau compte les passes réellement effectuées, avec 2, 12, 28, 60 et 124 fragments fermés. Le dernier retour utilisateur demande un maximum de 32 et un rythme plus lent ; le niveau 64 est retiré.

Le fruit, la planche, les ombres et la typographie partagent un rendu pixel art : grille 216 × 384 agrandie ×5 sans lissage, palette de 19 couleurs. Tout le texte visible est en anglais. Les lames sont projetées à vitesse constante ; leurs fenêtres de visibilité de 0,15 s peuvent se superposer. Première frappe à 0,12 s dans chaque chapitre, salves de 0,42 / 0,77 / 1,25 / 1,90 s. La vitesse de traversée et la dispersion des morceaux sont réduites pour améliorer la lecture. Un accent sonore accompagne chaque coupe. Aucun extrait de la référence n'est utilisé dans le rendu. Aucun fichier du frontend du studio n'est modifié.

## Reproduire

Node récent, Python 3, Pillow et FFmpeg ; aucune clé API.

```sh
npm ci
npm run build
npm run verify
npm run check
npx hyperframes preview --background
npm run render -- --fps 60 --quality looks --strict --no-browser-gpu --workers 1 --output watermelon-pixelcuts-32-polished.mp4
python qa_frames.py watermelon-pixelcuts-32-polished.mp4
```

Les versions de Three.js, Cannon et GSAP sont figées dans `package-lock.json`. La composition et le moteur ne font aucun appel réseau lors de l'évaluation d'une image. Les titres bitmap n'utilisent aucune police téléchargée.

Le rendu logiciel est utilisé ici : la capture du contexte WebGL avec la carte graphique a dépassé le délai sur cette machine lors du premier essai. Les planches `qa/watermelon-pixelcuts-32-polished/all-frames-*.jpg` permettent de vérifier les 879 images du MP4. Les résultats du contrôle sont consignés dans `QA.md` après export. La preview HyperFrames reste ouverte pendant les révisions et précède le rendu.

## Comment ça fonctionne

- `build-simulation.mjs` construit la pastèque facettée, coupe les polygones avec 31 plans radiaux imbriqués et un plan équatorial, ferme les surfaces intérieures et prépare les enveloppes convexes des morceaux. Les géométries sont dédupliquées par identifiant, puis chaque chapitre réutilise les mêmes étapes.
- La physique est calculée à pas fixe de 1/120 s : gravité et collisions contre la planche et le sol. Les niveaux 1 et 4 incluent les contacts entre morceaux ; les salves de 8 à 32 utilisent une dispersion initiale modérée et désactivent ces contacts pour éviter les vibrations des lamelles très fines et borner le coût de calcul. Les poses sont enregistrées. `simulation-report.json` conserve les limites mesurées.
- `scene.mjs` interpole les poses selon le temps demandé : rendu identique en lecture, en retour arrière et à l'export. Les sommets des fragments sont regroupés en trois maillages pour conserver les matériaux et les pépins sans multiplier les appels de dessin. Un pool de couteaux suit des trajectoires scénarisées à vitesse constante, synchronisées aux divisions géométriques. Un écho à 12 ms souligne la vitesse. La preview utilise uniquement les étapes de coupe, sans libération physique.
- La chair, la bordure de l'écorce et les pépins sont modélisés. L'éclairage, les ombres et la caméra sont de vraies données 3D.
- `pixel.mjs` réduit le rendu à une palette fixe avec tramage discret et dessine les lettres et une petite icône pastèque sur le même canevas que la scène. Un cache conserve le résultat exact de chaque couleur et position de tramage ; les pixels restent identiques. Les sommets du fruit maintenu ne sont recalculés qu'au changement d'étape de coupe. Ces deux optimisations allègent la preview sans modifier le rythme du rendu.
- `sound.py` synthétise 93 accents de coupe courts, avec un bruit filtré et une résonance grave. Les frappes proches adaptent leur gain. Les 584 collisions sont regroupées en 67 accents discrets par fenêtres de 50 ms et par chapitre. Le mixage utilise un gain linéaire avec réserve de niveau, sans le saturateur précédent. Le générateur est fixe.

Le logo de chaîne est conservé dans `brand/chef-spatula-avatar.png` : cuisto pixel art avec spatule, sans texte, sur badge vert et fond crème. Le prompt est dans `brand/README.md`.

## Limites et suite

Les fragments sont rigides : pas de jus ni de chair qui se déforme. La pastèque est maintenue dans les airs pendant les coups, comme dans la référence. La géométrie low-poly sert de base au rendu pixel art demandé par l'utilisateur après le premier prototype. La peau, les couleurs et la caméra sont des décisions artistiques.

Pour élargir le format : garder ce moteur, remplacer la géométrie et les matériaux, écrire les plans et les trajectoires de lame, puis refaire les contrôles. Les prochaines difficultés seraient les objets creux, la souplesse et les liquides. Blender pourrait servir à ces rendus plus lourds ; il n'est pas requis pour cet essai.

Les fichiers générés (`assets/scene.js`, simulation, WAV, MP4, captures et dépendances) sont exclus de Git et reconstruits par `npm run build`.
