# Bunker Survival — étude de style visuel

Référence : [Bunker Survival 1 Year](https://www.youtube.com/watch?v=RmyjNoz2pw4).
Étude du 16 octobre 2026. Essai indépendant des chaînes en production.

## Résultat

Le style est reproductible avec notre générateur Studio via le CLI Proxy déjà configuré. Six essais originaux ont été générés sur le VPS puis regardés individuellement par Codex. Ouvrir **00-planche.jpg** pour les comparer, ou les six JPG numérotés pour les voir séparément. Tous ces JPG sont en 1280 × 720, format 16:9 ; les fichiers natifs de génération sont conservés dans le dossier de travail privé.

La combinaison recherchée est obtenue : corps stickman en traits fins, visage blanc très simple, objets reconnaissables, couleurs mates, pièces peu chargées, objets et petits schémas sur blanc. La pièce jour/nuit conserve la même porte, le même établi, l'évent, l'étagère, la radio et le chiffon. Le personnage sourit quand la radio fonctionne, se montre surpris lors de la panne et enthousiaste quand sa lampe fonctionne.

Limites vues : contours encore un peu plus épais, certains objets légèrement plus ombrés et mains parfois plus dessinées que la référence. Ce test valide la direction artistique et une courte continuité jour/nuit ; il ne valide pas automatiquement une vidéo entière. Aucun preset existant n'a été remplacé.

## Ce qui a été étudié

97 captures réelles, de 0,50 s à 689,188 s, couvrant les 11 min 31 de la source. Échantillonnage régulier toutes les 12 s complété par des changements de scène, puis examen des 13 planches. Les captures source sont dans **References/Captures/** ; les 13 planches sont dans **References/Planches/** ; **References/timestamps.json** conserve temps exacts, dimensions et empreintes. Les médias de référence restent locaux et ne sont pas publiés dans Git.

| Repère dans la vidéo | Ce qu'il montre |
|---|---|
| 00:00,5 | Mobilier et personnage isolés sur champ blanc |
| 00:12,5 | Extérieur peu profond, ciel blanc, action en silhouette |
| 00:36,5 | Gros plan sur un objet isolé, dessin fonctionnel |
| 00:48,5 | Pièce complète : lignes de perspective fines, mobilier lisible |
| 01:00,5 | Petit schéma d'objets reliés par des flèches |
| 01:20,1 | Personnage et objet explicatif sur blanc |
| 01:54 | Vue en coupe, dessin technique simplifié |
| 03:00,5 | Graphique très dépouillé |
| 04:24,5 | Même univers sous une palette nocturne bleue |
| 05:48,5 | Réseau d'objets sur blanc, quelques traits de liaison |
| 08:21,6 | Personnage avec visualisation de pensée sur blanc |
| 10:48,5 | Objet au premier plan et personnage dans le décor |

Les sujets et textes de la source ne sont pas repris comme nouveau script. Cette analyse porte sur son langage graphique.

## Règles pour un futur preset

1. Choisir le type d'image depuis le beat du script : **scène dans un lieu**, **objet isolé**, **personnage sur blanc**, **schéma**, **coupe** ou **réaction**. Aucun quota arbitraire de fonds blancs ; choisir ce qui raconte ou explique le mieux.
2. Pour les scènes : préparer un maître de lieu vérifié et une référence de personnage distincte. Réutiliser le maître quand la scène revient. Un fond blanc n'implique pas d'abandonner la référence du personnage.
3. Une tête ronde simple avec quelques traits expressifs ; cou, corps et membres en traits noirs. Les vêtements humains détaillés et les corps pleins de nos autres chaînes ne font pas partie de cet essai. Les émotions restent propres à chaque situation.
4. Objet isolé = vrai champ blanc opaque, sans pièce, horizon ni ombre portée. Les formes de l'objet restent assez détaillées pour être comprises immédiatement.
5. Schéma = peu d'objets, une relation claire, flèches fines et beaucoup d'espace. En production, composer le texte et les chiffres séparément pour les contrôler ; pas de données inventées par le générateur.
6. La variété vient des actions et de l'alternance des modes, pas de rotations aléatoires de la même pièce. Une nouvelle lumière ou un nouvel angle se prépare comme variante explicite du maître.
7. Générer et contrôler sur le VPS avec le fournisseur existant ; regarder chaque sortie. Un prompt ou une empreinte ne prouve pas la qualité de l'image.

Finch, la casquette bleu-vert et les situations de ces essais sont des propositions de test, pas une identité de chaîne déjà validée par l'utilisateur.

## Corrections effectuées

- Premier intérieur : main posée sur le haut-parleur au lieu du bouton. Nouvelle version inspectée : main sur un bouton de la radio, positions de la pièce conservées.
- Premier personnage isolé : fond noir, incompatible avec le mode blanc demandé. Essai rejeté ; nouvelle génération à fond blanc inspectée. La cause technique exacte de ce premier fond noir n'est pas établie.
- Nuit : contrôle avec l'intérieur de jour à côté ; géométrie et accessoires reconnaissables, action et expression modifiées. Ne pas confondre cette vérification de deux images avec une certification de continuité sur un film complet.

## Prompts exacts et références envoyées

Prompts écrits manuellement par Codex. Les références source sont des captures de la vidéo ci-dessus, utilisées comme références de dessin. Les références de nos essais fixent le nouveau personnage et la géométrie de la pièce. L'ordre ci-dessous est l'ordre effectivement envoyé. Les reçus complets, avec fournisseur et transport, restent dans le dossier privé de travail `work/new-style-bunker-2026-10-16/`.

### 01-interieur-jour

Fichier : `01-interieur-jour.jpg` ; dimensions natives : 1672 × 941.

1. notre essai `tests/01-room-day-v1.png` — edit target, preserve camera, room geometry, character identity and objects. SHA-256 : `8bcf68abc6f04265a6677e1f419b807fcf4c432dbe4bee00a4ffa9e10f700c2f`.
2. capture source à 48.5 s — finer pen weight reference. SHA-256 : `596741f1517c118e75f254d7f28078951df4910311412c5317d3c31a4c3ec91b`.
3. notre essai `tests/02-radio-white-v1.png` — radio identity and knob placement. SHA-256 : `fc4f2a5a4af8fed4c54083a769d3d151c6719838403d27d529ebc7b23935d99a`.

```text
Use case: illustration-story. Asset: one original 16:9 video still, clean full-canvas raster illustration.
STYLE: match the supplied video-frame references in line weight, simplification, flat colors and generous negative space. Crisp black outlines roughly 2 pixels at 1280x720; thinner gray perspective/seam lines. Flat white or near-white surfaces, muted slate blue, olive and neutral gray objects, small color accents. Objects have enough construction lines to recognize their function, but not realistic textures. Only very restrained flat two-tone object shading. Clean digital drawing, no pencil grain, painterly brushwork, photorealism, 3D rendering, anime lighting, lens effects, drop shadows, rounded infographic cards or decorative borders. No title, subtitles, logos, watermark or unrequested writing. The references supply DRAWING LANGUAGE ONLY: invent the requested scene instead of tracing its architecture or repeating its props.
CHARACTER WHEN PRESENT: Finch is an original adult stick figure, round white face outlined in black, two small black dot eyes, small simple mouth, subtle situation-specific brows, short dark charcoal hair under a muted teal baseball cap. His neck, torso, arms and legs are SINGLE THIN BLACK LINES, not filled shapes or a clothed humanoid body; small line fingers, tiny oval feet. Slender stickman proportions similar to the reference, head about one fifth of standing height. Never duplicate him. Do not use the reference's orange-cap mascot. No bag attached to the body.


IMAGE 1 IS THE EDIT TARGET. Preserve the entire composition, camera, closed door on left, central workbench, centered wall vent, shelf on right, one ceiling lamp, cloth and exactly one smiling teal-cap stick figure. Image 2 only shows the slightly finer contour weight desired. Image 3 is the radio identity reference.
Make this targeted correction: Finch must be genuinely tuning the radio, pinching the LOWER RIGHT TUNING KNOB of the red radio between his small stick fingers; his hand must not rest on the speaker grille. Slightly angle his right forearm down to reach that knob without changing where he stands. Radio must have speaker on left, cream tuning window on upper right, two dark knobs on lower right, handle on top, same front/side construction as image 3. Maintain natural clear hand-to-knob contact. All other actions, objects and positions unchanged.
Use slightly finer black outlines matching image 2, roughly 2px at 1280x720 with thinner gray wall seams; flat matte color, no paper texture and no extra shadows. No text, no extra characters or furniture.
```

### 02-interieur-nuit

Fichier : `02-interieur-nuit.jpg` ; dimensions natives : 1672 × 941.

1. notre essai `tests/01-room-day-v2.png` — exact room geometry, camera, Finch identity, prop positions. SHA-256 : `60babc606893374bb6a0573511a26e1405f9c77fd67c57f3c0ff2b8963c8a328`.
2. capture source à 264.5 s — night palette and restrained flat dark-blue lighting only. SHA-256 : `69bb8a61453ba26e9ba37e252e2e0b7951bd9ebe51b378bfeb6a364b85dc2354`.

```text
Use case: illustration-story. Asset: one original 16:9 video still, clean full-canvas raster illustration.
STYLE: match the supplied video-frame references in line weight, simplification, flat colors and generous negative space. Crisp black outlines roughly 2 pixels at 1280x720; thinner gray perspective/seam lines. Flat white or near-white surfaces, muted slate blue, olive and neutral gray objects, small color accents. Objects have enough construction lines to recognize their function, but not realistic textures. Only very restrained flat two-tone object shading. Clean digital drawing, no pencil grain, painterly brushwork, photorealism, 3D rendering, anime lighting, lens effects, drop shadows, rounded infographic cards or decorative borders. No title, subtitles, logos, watermark or unrequested writing. The references supply DRAWING LANGUAGE ONLY: invent the requested scene instead of tracing its architecture or repeating its props.
CHARACTER WHEN PRESENT: Finch is an original adult stick figure, round white face outlined in black, two small black dot eyes, small simple mouth, subtle situation-specific brows, short dark charcoal hair under a muted teal baseball cap. His neck, torso, arms and legs are SINGLE THIN BLACK LINES, not filled shapes or a clothed humanoid body; small line fingers, tiny oval feet. Slender stickman proportions similar to the reference, head about one fifth of standing height. Never duplicate him. Do not use the reference's orange-cap mascot. No bag attached to the body.


IMAGE 1 IS THE ROOM/IDENTITY MASTER: keep exactly its camera, wall/floor seams, closed left door, wall vent, central workbench, shelf on right, one ceiling lamp, cloth and radio. No change of angle, no mirrored furniture, no bunk beds or ladder from image 2. Image 2 only supplies simple night coloring.
Make a new moment in this SAME room: the ceiling light has switched off, the room is filled with a uniform muted dark navy-blue night tone and all the silhouettes remain readable. Finch stays at the same floor position left of workbench, same teal cap, dark hair and simple stick anatomy. His right hand now holds a small gray flashlight pointing diagonally down and right onto the bare floor in front of the workbench. Show a short pale yellow cone ending in a small oval light patch on the floor, not a blinding glow. Other hand raised slightly toward his mouth in alert surprise; widened dot eyes, small open mouth. Clear flashlight grip, exactly two arms and two legs. The red radio and folded cloth remain on the workbench where image 1 puts them. Exactly one character. Flat clean drawing and fine black contours, no photo darkness, horror creature, mist, bloom or unrequested text.
```

### 03-exterieur-action

Fichier : `03-exterieur-action.jpg` ; dimensions natives : 1672 × 941.

1. capture source à 12.5 s — outdoor staging, flat grass and white sky. SHA-256 : `b4c505c61bb895a1f69ee4dd59806fc1b42b43f2b90998026f1b56d5e7decfb7`.
2. capture source à 80.1 s — thin stick anatomy and expressive simple face. SHA-256 : `d89da96682ff7943db4a5d0783a15b2a3da4c90309692ae3bf5c8cf09ce15559`.

```text
Use case: illustration-story. Asset: one original 16:9 video still, clean full-canvas raster illustration.
STYLE: match the supplied video-frame references in line weight, simplification, flat colors and generous negative space. Crisp black outlines roughly 2 pixels at 1280x720; thinner gray perspective/seam lines. Flat white or near-white surfaces, muted slate blue, olive and neutral gray objects, small color accents. Objects have enough construction lines to recognize their function, but not realistic textures. Only very restrained flat two-tone object shading. Clean digital drawing, no pencil grain, painterly brushwork, photorealism, 3D rendering, anime lighting, lens effects, drop shadows, rounded infographic cards or decorative borders. No title, subtitles, logos, watermark or unrequested writing. The references supply DRAWING LANGUAGE ONLY: invent the requested scene instead of tracing its architecture or repeating its props.
CHARACTER WHEN PRESENT: Finch is an original adult stick figure, round white face outlined in black, two small black dot eyes, small simple mouth, subtle situation-specific brows, short dark charcoal hair under a muted teal baseball cap. His neck, torso, arms and legs are SINGLE THIN BLACK LINES, not filled shapes or a clothed humanoid body; small line fingers, tiny oval feet. Slender stickman proportions similar to the reference, head about one fifth of standing height. Never duplicate him. Do not use the reference's orange-cap mascot. No bag attached to the body.

INPUT ROLES: image 1 supplies outdoor drawing treatment only; image 2 supplies stickman proportions only. Do not repeat orange cap, house, hatch or food.
SCENE: simple overcast outdoor yard, completely white sky occupying upper 55 percent, flat muted green grass across bottom, low horizon with only two small plain shrubs. A small gray corrugated utility shed stands on the right with its blue door half open; a yellow raincoat hangs from a hook just inside. Thin neat black construction lines, no forest, mountains, skyline or elaborate depth.
ACTION: Finch jogs from left toward the open shed door while holding a small red toolbox firmly in his right hand. A few simple motion strokes behind the legs, expression alert and purposeful, small determined mouth. Normal coherent stickman hands around handle, exactly two arms and two legs, thin line torso. A few large simple blue rain streaks in the otherwise white sky, no atmospheric or cinematic effects. No backpack, no mushroom cloud, no text.
```

### 04-objet-fond-blanc

Fichier : `04-objet-fond-blanc.jpg` ; dimensions natives : 1672 × 941.

1. capture source à 36.5 s — object illustration linework, limited shading and white negative space. SHA-256 : `967a4d7194a8cbd8c96e5d335da98eb733a6d812b3ee9025637cd35fbadb4cea`.
2. capture source à 660.5 s — radio structure, pictorial communication; not layout. SHA-256 : `974863b3218c5aa53ef4cb736798aca2061e19834a18f05700334c25610afb0e`.

```text
Use case: illustration-story. Asset: one original 16:9 video still, clean full-canvas raster illustration.
STYLE: match the supplied video-frame references in line weight, simplification, flat colors and generous negative space. Crisp black outlines roughly 2 pixels at 1280x720; thinner gray perspective/seam lines. Flat white or near-white surfaces, muted slate blue, olive and neutral gray objects, small color accents. Objects have enough construction lines to recognize their function, but not realistic textures. Only very restrained flat two-tone object shading. Clean digital drawing, no pencil grain, painterly brushwork, photorealism, 3D rendering, anime lighting, lens effects, drop shadows, rounded infographic cards or decorative borders. No title, subtitles, logos, watermark or unrequested writing. The references supply DRAWING LANGUAGE ONLY: invent the requested scene instead of tracing its architecture or repeating its props.
CHARACTER WHEN PRESENT: Finch is an original adult stick figure, round white face outlined in black, two small black dot eyes, small simple mouth, subtle situation-specific brows, short dark charcoal hair under a muted teal baseball cap. His neck, torso, arms and legs are SINGLE THIN BLACK LINES, not filled shapes or a clothed humanoid body; small line fingers, tiny oval feet. Slender stickman proportions similar to the reference, head about one fifth of standing height. Never duplicate him. Do not use the reference's orange-cap mascot. No bag attached to the body.

INPUT ROLES: images 1 and 2 are stylistic references for drawing objects on white only.
SCENE: pure opaque white #FFFFFF background all the way to every edge, no room, no wall, no floor line, no tabletop and no cast shadow.
SUBJECT: one portable red analog radio seen slightly from above, 3/4 front angle, in the left-center at generous scale; black speaker perforations on left front, simple cream frequency window on right front, two charcoal knobs, black carry handle and thin telescopic antenna. Flat muted red panels, a single darker side panel. To its right, three small hand-drawn black curved sound lines and one small floating musical note. No speech bubble and no text. Plenty of untouched white margin around the object. No character.
```

### 05-personnage-fond-blanc

Fichier : `05-personnage-fond-blanc.jpg` ; dimensions natives : 1672 × 941.

1. notre essai `tests/04-outdoor-v1.png` — Finch identity: teal cap, dark hair, dot eyes and line anatomy. SHA-256 : `701d4824e1e8eef976df81019b9c5dd806d216e0cb8a66497eb9bafc88324c48`.
2. capture source à 80.1 s — white-background character and object explanatory treatment. SHA-256 : `d89da96682ff7943db4a5d0783a15b2a3da4c90309692ae3bf5c8cf09ce15559`.

```text
Use case: illustration-story. Asset: one original 16:9 video still, clean full-canvas raster illustration.
STYLE: match the supplied video-frame references in line weight, simplification, flat colors and generous negative space. Crisp black outlines roughly 2 pixels at 1280x720; thinner gray perspective/seam lines. Flat white or near-white surfaces, muted slate blue, olive and neutral gray objects, small color accents. Objects have enough construction lines to recognize their function, but not realistic textures. Only very restrained flat two-tone object shading. Clean digital drawing, no pencil grain, painterly brushwork, photorealism, 3D rendering, anime lighting, lens effects, drop shadows, rounded infographic cards or decorative borders. No title, subtitles, logos, watermark or unrequested writing. The references supply DRAWING LANGUAGE ONLY: invent the requested scene instead of tracing its architecture or repeating its props.
CHARACTER WHEN PRESENT: Finch is an original adult stick figure, round white face outlined in black, two small black dot eyes, small simple mouth, subtle situation-specific brows, short dark charcoal hair under a muted teal baseball cap. His neck, torso, arms and legs are SINGLE THIN BLACK LINES, not filled shapes or a clothed humanoid body; small line fingers, tiny oval feet. Slender stickman proportions similar to the reference, head about one fifth of standing height. Never duplicate him. Do not use the reference's orange-cap mascot. No bag attached to the body.


INPUT ROLES: image 1 locks Finch's exact face/head, teal cap, dark hair and thin-line stick figure anatomy, NOT its outdoor scene. Image 2 supplies the white-background treatment, NOT its mascot, text or food.
Pure opaque white background from edge to edge, no floor, floor line, architecture, gradient or cast shadow. Finch stands in full body at left-center, about 70 percent canvas height; he holds a small gray flashlight in one stick hand, examining it with a pleased open-mouth smile as it finally turns on. A short simple pale-yellow light cone points to the right at empty white space. Other hand forms a simple raised thumbs-up. Exactly two arms, two legs and one Finch. Thin black line torso, thin black line limbs, tiny oval feet. At right-center float one small blue spare battery and one small yellow lightning icon, in the same outlined flat drawing treatment, clearly separated from the cone. Generous white margins. No bag, written text, speech bubble, anatomy fill, room or table. Fine black contour weight matching image 2.

BACKGROUND CORRECTION: The canvas itself is an OPAQUE SOLID WHITE painted rectangle (#FFFFFF). Render that white backing as visible pixels everywhere outside the colored outlined drawing, including between stick limbs and around the character. NOT a transparent sticker asset, NOT a black background, NOT a dark/night scene, NOT a cutout. The black stick body must be fully readable against the WHITE field. Keep the same cheerful flashlight action and teal-cap character specified above. White-background video illustration as in reference image 2.
```

### 06-schema-explicatif

Fichier : `06-schema-explicatif.jpg` ; dimensions natives : 1672 × 941.

1. capture source à 348.5 s — linework, isolated colored objects and simple connecting strokes. SHA-256 : `61e71c0b8867a0bff5fef1b2837e552f259c09c3d15a1827a57b93287b25dd74`.
2. capture source à 351.533 s — sparse pictorial diagram treatment. SHA-256 : `942487f0d247c58219ca2e96093bf9677f5d88581a28b92b42d428c08a26b0d4`.

```text
Use case: illustration-story. Asset: one original 16:9 video still, clean full-canvas raster illustration.
STYLE: match the supplied video-frame references in line weight, simplification, flat colors and generous negative space. Crisp black outlines roughly 2 pixels at 1280x720; thinner gray perspective/seam lines. Flat white or near-white surfaces, muted slate blue, olive and neutral gray objects, small color accents. Objects have enough construction lines to recognize their function, but not realistic textures. Only very restrained flat two-tone object shading. Clean digital drawing, no pencil grain, painterly brushwork, photorealism, 3D rendering, anime lighting, lens effects, drop shadows, rounded infographic cards or decorative borders. No title, subtitles, logos, watermark or unrequested writing. The references supply DRAWING LANGUAGE ONLY: invent the requested scene instead of tracing its architecture or repeating its props.
CHARACTER WHEN PRESENT: Finch is an original adult stick figure, round white face outlined in black, two small black dot eyes, small simple mouth, subtle situation-specific brows, short dark charcoal hair under a muted teal baseball cap. His neck, torso, arms and legs are SINGLE THIN BLACK LINES, not filled shapes or a clothed humanoid body; small line fingers, tiny oval feet. Slender stickman proportions similar to the reference, head about one fifth of standing height. Never duplicate him. Do not use the reference's orange-cap mascot. No bag attached to the body.

Use case: infographic-diagram. INPUT ROLES: both references supply sparse explanatory drawing style, not their arrangement or content.
SCENE: pure white #FFFFFF background. One large blue portable battery on the LEFT, simple flat rectangular casing with carry handle and tiny green charge indicator. Three thin black arrows travel from the right edge of that battery toward three separate objects stacked vertically on the RIGHT: a small gray work lamp with pale yellow face at top, a muted red radio in middle, a blue desk fan at bottom. Each object drawn as a clear small black-outline cartoon, comparable in size. Exactly one battery, one lamp, one radio and one fan. Generous white space between arrows and object outlines. Clean 2D object drawing, no boxes around groups, no decorative background, no gradients, no text or numeric readings, no central lightning bolt. This is a visual explanation of one source supplying three devices, not an engineering wiring diagram.
```
