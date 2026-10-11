# Depths After Dark — fonds marins animés

## Boucle corrigée livrée — caméra en avancée et davantage de vie

Retour utilisateur après le film `95IFNFjM` : ambiance appréciée, mais pas
assez de vie et mouvement caméra en avant demandé explicitement. Cette boucle
illustrée est une archive de test, pas le fond final validé.

`npm run build:forward` prépare maintenant `dist-forward/` depuis
`sleep-forward-scene.mjs`, `sleep-forward-reef.mjs` et `forward-index.html`.
La caméra avance dans un parcours de 600 unités, bouclé en 300 secondes ;
les éléments proches sont projetés par profondeur, sans simple zoom global.
C’est une illustration **2.5D**, pas une géométrie 3D solide. Les deux images
originales existantes sont réutilisées ; pas de nouvel appel de génération.
480 poissons au total, huit requins et douze méduses : totaux du monde,
pas nombres simultanément visibles. La présence dans le cadre est mesurée.

**[Aperçu corrigé de 24 secondes sur GoFile](https://gofile.io/d/qsIDnkvK).**
Fichier `Depths-After-Dark-Camera-Forward-24s.mp4` : **24 s, 1920×1080,
30 images/s, 720 images, 34 172 536 octets**. SHA-256 :
`38fc4e4e2f62514d00d91cf143eb10b6d25682e7230a7a8fff56535f44e7fa84`.
Le bundle contrôlé et utilisé par le rendu porte l’empreinte
`d3460e0da70312fcfb26134c92ca09c696750ea02a62e11ffba77731c0c8ce5f`.

Les orientations évoluent progressivement ; les animaux proches quittent
le cadre avant le plan de coupe de la caméra. Les éléments du récif ont été
redistribués. Décodage A/V complet sans erreur, horodatages et 720 images
vérifiés ; revue de 24 captures générales, 48 rapprochées natives, neuf
planches et six vues natives supplémentaires. Le requin sort par le haut
vers 6–7 s, la méduse par la gauche vers 7–7,5 s. Aucun saut miroir ni fondu
central identifié dans ces échantillons. Audio fini, aucune saturation.
Pas de lecture continue ni d’écoute humaine complète prétendue.

Contrôle de la scène source sur 601 poses : pixels 0/300 s identiques,
retour arrière déterministe, perspective cohérente et **112–128 poissons
visibles**. La marge latérale indépendante des poissons vaut au minimum
0,368 unité. Ce contrôle discret ne prouve pas des collisions 3D continues
ni l’absence d’occultation ; le sol peint n’est pas contrôlé géométriquement.
Preuves publiques : [FORWARD_SCENE_CHECK.json](FORWARD_SCENE_CHECK.json),
[FORWARD_PREVIEW_CHECK.json](FORWARD_PREVIEW_CHECK.json),
[FORWARD_VISUAL_REVIEW.md](FORWARD_VISUAL_REVIEW.md) et
[FORWARD_DELIVERY.json](FORWARD_DELIVERY.json).

**Avis visuel utilisateur attendu.** Les motifs de récif réutilisés et
certains contours de calques restent reconnaissables ; les animaux sont
en 2.5D et le fond lointain reste fixe. Le contrôle technique ne valide pas
la direction artistique. Deux assets historiques sont réutilisés : **zéro
nouvelle génération pour cet aperçu, zéro Algrow et zéro génération vidéo**.

**La boucle corrigée complète de cinq minutes est livrée dans le même dossier
GoFile.** Choisir `Depths-After-Dark-Camera-Forward-5min.mp4` :300s,
1920×1080/30i/s,9000images,462311725octets, SHA-256
`37699678ea847830c6992e160064adc8592d4760b2508fa4153b39ae42a8c459`.
Rendu en24,10min sur cette machine, upload confirmé par taille et MD5.
Un seul décodage A/V complet a contrôlé les9000PTS ; revue réelle de249
trames sélectionnées dans17planches et13PNG natifs, avec revue indépendante.
Audio PCM fini, sans saturation, raccord encodé dans les variations voisines
mesurées. Source0/300 identique ; dernier/premier frame encodé différent,
continuité comparable à celle des frames voisines. Aucun visionnage ou écoute
humain continu prétendu. **Validation artistique utilisateur toujours attendue.**
Preuves : [FORWARD_LOOP_CHECK.json](FORWARD_LOOP_CHECK.json),
[FORWARD_LOOP_REVIEW.md](FORWARD_LOOP_REVIEW.md),
[FORWARD_DELIVERY.json](FORWARD_DELIVERY.json).
Aucun script, voix off ou épisode de deux heures n’est produit à cette étape.

Pour reproduire dans un nouveau dossier de sortie, depuis ce dossier :

```bash
npm run build:forward
node verify-forward-loop.mjs --dist dist-forward --min-visible-fish 80 \
  --out /tmp/deepsea-forward/check.json
node capture.mjs --dist dist-forward --canvas-cpu --duration 24 --fps 30 \
  --out /tmp/deepsea-forward/preview.mp4 \
  --audio /tmp/deepsea-sleep-5m/ambience-master.wav
```

Le mode CPU est requis ici pour ce Canvas2D ; SwiftShader entraînait un
blocage lors du premier essai. Le contrôle source vérifie vrais pixels au
raccord, retour arrière, perspective des repères et marges latérales des
animaux. Il ne certifie ni collisions 3D continues ni qualité artistique.
La QA d’un aperçu de 24 s ne certifie pas le raccord d’un MP4 de 300 s.

Pour contrôler à nouveau un futur export de **cette même version figée**,
utiliser `verify-current-forward-render.py --video /chemin/boucle.mp4
--scene-check /chemin/check.json --out-dir /chemin/nouveau-dossier-qa`.
Le checker a été exécuté sur le vrai film terminé ci-dessus ; il est épinglé
au bundle `d3460e…`, exige le reçu final et30checkpoints complets, puis fait
un seul décodage A/V avec captures et PCM. Il laisse la revue visuelle et
l’analyse audio en attente : elles ne sont pas automatiquement approuvées.
Une autre version de la scène demande une nouvelle épingle et sa propre QA.

## Archive récente — récif nocturne illustré et animé

La boucle 3D livrée précédemment est **rejetée**. L’utilisateur abandonne
ensuite toutes les contraintes de 3D et de style de jeu : il veut un beau
fond marin vivant, immersif, très différent du rendu précédent.

Cette archive utilise `npm run build:sleep` et **sleep-illustrated-scene.mjs**,
un moteur Canvas2D. Un récif nocturne original et une méduse détourée
sont animés par du code : panoramique/zoom lents, huit bancs (144 poissons
au total), deux silhouettes de requins, trois méduses aux tissus ondulants,
neige marine et frondes. Les anciennes scènes et modèles 3D ne sont pas
importés ; ils restent des études abandonnées.

Deux illustrations ont été préparées une fois, puis sont réutilisées pour
chaque image de la boucle. Aucun appel à Algrow, aucune génération vidéo,
aucune API lors de la lecture. Le décor source est **1672×941** ; le canevas
et l’export sont **1920×1080**. Ne pas prétendre que le décor est une source
native 4K/1080p, ni que tout a été fabriqué sans générateur d’images.
Le sprite provient de l’avatar original validé. Voir [ASSETS.md](ASSETS.md).

**[Archive de cinq minutes remplacée par la correction ci-dessus](https://gofile.io/d/95IFNFjM).**
Choisir `Depths-After-Dark-Boucle-5min.mp4` : **300 s, 1920×1080, 30 images/s,
9 000 images, 393 133 259 octets**. SHA-256 :
`bec3996016d93c4e994b72a15ef88b4d1ce531cfd7a5e12b79216e703c4389fa`.
Export en 1 819,46 s sur cette machine sans GPU. Upload confirmé par taille
et MD5. Le même dossier contient l’extrait de 24 s et le lecteur autonome
`Depths-After-Dark-Boucle-5min-HTML.zip` (4 645 976 octets) : extraire et ouvrir
`index.html` dans Chrome/Firefox sur PC, sans installation. Le lecteur HTML
est silencieux ; le MP4 contient une ambiance aquatique originale.

Le film terminé passe le décodage A/V intégral, le comptage des images,
les contrôles de raccord et de saturation audio. Revue des captures :
60 générales, 208 de mouvements/raccord et 11 natives, dont une revue
indépendante. Pas de lecture/écoute humaine continue prétendue. Les pixels
0/300 s de la scène source sont identiques ; ceux du raccord encodé ne le
sont pas. Aucun saut de composition évident dans les captures examinées.
Voir [ILLUSTRATED_RENDER_CHECK.json](ILLUSTRATED_RENDER_CHECK.json),
[ILLUSTRATED_VISUAL_REVIEW.md](ILLUSTRATED_VISUAL_REVIEW.md) et
[ILLUSTRATED_DELIVERY.json](ILLUSTRATED_DELIVERY.json).

**Ce fond est une archive : vie et mouvement caméra jugés insuffisants.** Les futurs épisodes
feront deux heures, soit 24 répétitions, avec voix off et texte élégant et
discret au milieu de l’écran après validation du fond. Aucun texte/voix de
long ni publication lancés à cette étape. Pour le futur mix, utiliser le
master PCM périodique ; ne pas répéter les paquets AAC comme fond sonore.

Chaîne : **Depths After Dark**, nom confirmé ; avatar méduse validé et bio
anglaise dans [CHANNEL_BRAND.md](CHANNEL_BRAND.md). Sleep passe avant Chess,
mais le montage Tommy–Alfie a repris en parallèle dans son propre dossier.

Depuis ce dossier :

```bash
npm run build:sleep
../../.venv/bin/python make-sleep-ambience.py --seconds 300 \
  --out /tmp/deepsea-sleep-5m/ambience-master.wav
node verify-illustrated-loop.mjs --out /tmp/deepsea-illustrated/check.json
node capture.mjs --dist dist-sleep --duration 24 --fps 30 \
  --out /tmp/deepsea-illustrated/preview.mp4 \
  --audio /tmp/deepsea-sleep-5m/ambience-master.wav
node capture-loop.mjs --out /tmp/deepsea-illustrated/loop-5min.mp4 \
  --audio /tmp/deepsea-sleep-5m/ambience-master.wav
../../.venv/bin/python verify-sleep-render.py \
  --video /tmp/deepsea-illustrated/loop-5min.mp4 \
  --scene-check /tmp/deepsea-illustrated/check.json \
  --ambience-check /tmp/deepsea-sleep-5m/ambience-master.json \
  --out-dir /tmp/deepsea-illustrated/review
```

Le master sonore se recrée avec `make-sleep-ambience.py`, comme indiqué plus
bas. Le vérificateur illustré contrôle les **vrais pixels**, le raccord,
le retour arrière, la finitude et la lecture hors ligne. Il ne prétend pas
faire des collisions 3D. Le MP4 terminé a été décodé et inspecté avec `verify-sleep-render.py`,
qui distingue les schémas illustré et 3D ; refaire ces contrôles pour tout
nouvel export.
Les rapports publics `SLEEP_*CHECK.json` concernent seulement le film
**rejeté** ci-dessous, pas la nouvelle direction. Le nouveau moteur est
contrôlé dans [ILLUSTRATED_SCENE_CHECK.json](ILLUSTRATED_SCENE_CHECK.json) ;
l’extrait terminé dans [ILLUSTRATED_PREVIEW_CHECK.json](ILLUSTRATED_PREVIEW_CHECK.json).

### Étude intermédiaire 3D abandonnée, jamais livrée

`sleep-cinematic-scene.mjs`, `sleep-cinematic-environment.mjs`, les nouveaux
bancs/requins/méduses, shaders et vérificateurs 3D restent des archives de
travail. Ils n’ont pas reçu de validation artistique et ne sont pas le
fond actif. Ne pas réutiliser les rapports privés d’anciennes trajectoires
pour présenter les dernières trajectoires de cette étude comme contrôlées.

## Archive — première boucle de cinq minutes, rejetée visuellement

Direction à cette étape historique : **histoires marines vraies, ambiance calme et inquiétante**.
Les futurs épisodes visent deux heures : ce fond de **300 secondes** pourra
être répété **24 fois** sous une narration originale. Ces cinq minutes sont
calculées comme un parcours continu, distinct des anciens aperçus courts.
**[Télécharger le MP4 et le lecteur HTML sur GoFile](https://gofile.io/d/ixBAzbR6).**
Les contrôles techniques étaient passés ; l’utilisateur a ensuite rejeté
le rendu visuel. Ne pas reprendre cette version comme référence approuvée.
Aucun épisode de deux heures, script, voix off ou publication n'est produit
à cette étape.

- MP4 : **300 s, 1920×1080 natif, 30 images/s, 9 000 images**, 155 052 684 octets.
  SHA-256 : `203de8a6a72be4ff9817d97e4ce2be0a6db7d043d4ce40cbbaf30d27ff8ab9d0`.
- ZIP : `Les-Profondeurs-Boucle-5min-HTML.zip`, 206 228 octets. Extraire puis
  ouvrir `index.html` dans Chrome ou Firefox, sans installation. Lecteur silencieux ;
  le MP4 contient une ambiance aquatique originale, sans narration.
- Taille et MD5 des deux uploads vérifiés. Export complet : **3 080,867 secondes**
  (51 min 21 s environ), sur cette machine sans GPU, avec rendu logiciel.

La scène conserve des volumes originaux entièrement codés : relief, rochers,
détails de surface procéduraux et vie sur le fond. Sept groupes animés
(`roots`) réunissent une baudroie, deux méduses, deux bancs et deux raies. Caméra,
animaux, particules et ambiance sonore suivent des cycles de 300 secondes,
sans fondu final ; le raccord et les passages ont été contrôlés.
Les animaux sont des reconstitutions illustratives, pas des prises de vue
scientifiques ni des modèles repris du jeu.

Pour séparer son passage de ceux des autres animaux, la seconde raie (`ray2`)
passe désormais plus haut : son altitude de base est fixée à `y = 2.9`
unités de scène. Les volumes réservés aux animaux et à la caméra sont
recalculés avant de placer le décor. Le MP4 livré utilise ce réglage.

Contrôles consignés dans [SLEEP_SCENE_CHECK.json](SLEEP_SCENE_CHECK.json) et
[SLEEP_RENDER_CHECK.json](SLEEP_RENDER_CHECK.json) : décodage A/V intégral sans
erreur, format et nombre d'images conformes, raccord visuel comparable aux
pas ordinaires du film, aucune saturation audio. Revue des captures du MP4
terminé : 60 images générales, 208 images de mouvements/raccord et 11 vues
natives, avec revue indépendante supplémentaire. Aucune lecture continue ni
écoute humaine complète prétendue. Les passages sont vérifiés sur des poses
échantillonnées, pas par une preuve de collision continue. Pour les futurs
épisodes de deux heures, utiliser le master PCM périodique dans le mix audio,
plutôt que de répéter les paquets AAC encodés.

Le lecteur se construit séparément dans `dist-sleep/`. Depuis la racine du dépôt,
créer l'ambiance originale avec la venv existante et NumPy :

```bash
.venv/bin/python experiments/deep-sea-procedural/make-sleep-ambience.py \
  --seconds 300 --out /tmp/deepsea-sleep-5m/ambience-master.wav
```

Les anciennes commandes qui associaient `build:sleep` à
`verify-sleep-loop.mjs` concernaient le build 3D historique. L’entrée active
de la correction est `build:forward` avec `verify-forward-loop.mjs`, décrite
en tête de ce README. Les vérificateurs 3D exigent des diagnostics absents
de la scène 2.5D ; ne pas les exécuter sur `dist-forward/`.
Pour reproduire le contrôle du MP4 illustré historique :

```bash
../../.venv/bin/python verify-sleep-render.py \
  --video /tmp/deepsea-illustrated/loop-5min.mp4 \
  --scene-check /tmp/deepsea-illustrated/check.json \
  --ambience-check /tmp/deepsea-sleep-5m/ambience-master.json \
  --out-dir /tmp/deepsea-illustrated/review
```

La capture vise **1920×1080 natif, 30 images/s, 9 000 images**, H.264 CRF17,
avec anticrénelage et ambiance AAC stéréo. Elle enregistre des blocs de
10 secondes vérifiés par nombre d'images et SHA-256. Pour reprendre après
une interruption, relancer la même commande en ajoutant `--resume` : les
empreintes du lecteur, de la scène, du script de capture et de l'audio doivent
être identiques. Un verrou restant ne se retire qu'après confirmation de
l'arrêt du processus ; un MP4 terminé n'est jamais écrasé.

Le contrôle `verify-sleep-loop.mjs` inspecte le raccord visuel, le retour
arrière déterministe, les mouvements et les passages à partir des modèles
entiers animés. Il ne remplace pas le **QA du MP4 terminé** : décodage A/V
intégral, durée et nombre d'images, raccord audio, saturation et revue des
images restent requis avant livraison. Les rapports de capture gardent les
indicateurs de contrôle final à `false` jusqu'à ce travail effectif.

L'[évaluation de fframes](FFRAMES_REVIEW.md) rassemble la recherche sur son
dépôt officiel, sa documentation et la démonstration proposée. L'outil local
est sous licence MIT : Rust/SVG, rendu Skia, Metal/Vulkan et options CPU. Il
peut servir aux habillages et animations de texte ; porter nos volumes et
animations Three.js demanderait une intégration ou une réécriture. Three.js
reste utilisé pour cette boucle. fframes n'a pas été installé ici et aucun
gain de vitesse sur notre scène 3D n'a été mesuré.

## Historique — aperçus d'exploration de 24 secondes

Nouvelle chaîne YouTube envisagée : **vrais fonds marins, ambiance inquiétante
inspirée de DREDGE**, entièrement construite en HTML/JavaScript, sans Algrow
ni générateur d'images. Le 10 octobre 2026, le premier essai est rejeté comme
trop statique et trop peu immersif. La V2 améliore l'exploration en vue subjective,
mais l'utilisateur trouve les créatures trop « goofy » et la baudroie trop rigide,
comme morte. Il demande des formes plus belles et une animation plus vivante,
en étudiant réellement le style du jeu.

**Archive V4 : 24 secondes seulement, exportée et livrée.** La direction
associe des silhouettes plus sobres, des mouvements du corps et des nageoires,
un banc qui change de forme et une caméra qui suit brièvement la rencontre.
La [recherche DREDGE](STYLE_DREDGE.md) distingue les grandes créatures 3D des
illustrations de poissons en 2D et décrit les sources effectivement regardées.

Retour V3 : « pas trop mal », mais les poissons traversent des rochers. La V4
réserve leurs passages à partir des modèles entiers animés, puis déplace les
rochers qui les obstruent. Les faits et visuels devront suivre la narration.

Direction confirmée : **histoires vraies, ambiance inquiétante**. L'utilisateur
envisage ensuite une variante sleep : récits de deux heures, boucle calme
d'environ cinq minutes et collaboration avec une chaîne existante. Voir
[DIRECTION.md](DIRECTION.md). La section ci-dessus décrit la boucle désormais
livrée pour validation ; les livraisons qui suivent restent les anciens aperçus courts.

### Aperçu V4 livré — archive du 10 octobre 2026

[Voir les passages corrigés sur GoFile](https://gofile.io/d/nrriY6iM).

- `Les-Profondeurs-V4-Passages-Libres-24s.mp4` : 24 s, 1920×1080 natif,
  30 images/s, 720 images, 9 438 720 octets, sans voix.
- `Exploration-3D-V4-HTML.zip` : lecteur autonome sans son, 199 550 octets ;
  extraire puis ouvrir `Les-Profondeurs-3D/index.html`, sans installation.

SHA-256 du MP4 :
`713d498db228157c46c5eb53b29ff707350ad8d23602c55ab016075b4ba7000d`.
Les deux uploads sont vérifiés par taille/MD5. Décodage A/V intégral sans erreur,
pic audio −18,51 dBFS, aucune saturation. Revue du MP4 terminé : 12 captures
réparties, 40 images du passage de la baudroie, 16 de la méduse et quatre vues
natives 1080. Pas de lecture continue ni d'écoute complète humaine prétendue.

**Cohérence physique vérifiée indépendamment sur 1 441 poses à 60 poses/s** :
aucun recouvrement entre les volumes entiers animés et les rochers retenus,
ni avec le passage de la caméra. La réserve de construction prend 721 poses
à 30 poses/s, élargies de 0,40 unité, et une marge caméra de 0,55 unité.
Les 122 rochers sont conservés, dont 26 déplacés latéralement hors des passages.
Le contrôle indépendant mesure au minimum 0,433 unité aux rochers et 0,832
au sol réel, interpolé dans les triangles sous chaque sommet du modèle.
Un second contrôle Chromium confirme positions finies, retour arrière
reproductible, absence d'erreur et anticrénelage actif. Il s'agit de poses
échantillonnées, pas d'une preuve de simulation physique continue.

Le banc continue hors champ au lieu d'être masqué à une heure donnée.
La mise en scène reste préparée : un nouvel animal ou trajet nécessite de
réserver ses passages et de refaire les contrôles, pas une collision dynamique
universelle. La V4 corrige ce test ; elle ne constitue pas encore la boucle sleep.

## Ce qui est réellement calculé dans les aperçus V1–V4

- Caméra en vue subjective : environ 43 mètres de parcours virtuel, légère
  dérive, tangage et roulis ; rochers proches et silhouettes lointaines.
- Sol irrégulier, parois facettées, bancs rocheux et particules en suspension.
- Un banc de 17 poissons qui change de forme, avec profondeur, phases de nage
  individuelles et déformation du corps et de la queue.
- Une baudroie volumétrique avec silhouette continue, petits yeux sombres,
  bouche creusée et pigmentation plus sobre.
- Une onde de nage qui entraîne le corps et la queue ; nageoires et leurre
  bougent avec des phases décalées, et la bouche respire discrètement.
- Une trajectoire courbe avec orientation et roulis ; la caméra et sa torche
  suivent brièvement le poisson pendant son passage.
- Une méduse volumétrique avec cloche et quatre bras buccaux larges animés.
- Chaque animal possède une vraie géométrie dans la même scène : projection,
  lumière et occultation par les rochers, aucun animal Canvas superposé.
- Roches aux masses et couleurs cohérentes, lumière de plongée liée à la caméra,
  couleurs mates, brume et calcul de l'éclairage aux sommets pour réduire le
  coût du rendu logiciel.
- Anticrénelage WebGL natif (MSAA) activé par défaut, pour améliorer les contours
  des nageoires, des dents et des autres formes fines.
- Animation déterministe : `render(seconds)` donne toujours la même scène.
- Ambiance sonore synthétisée localement ; pas de musique, sample ni voix.

C'est une **reconstitution illustrative**, pas une expédition réelle. Le
rapprochement des espèces sert seulement à montrer le rendu. DREDGE inspire
les surfaces facettées, les couleurs sourdes et la visibilité ; aucun modèle,
image, interface, son ou extrait du jeu n'est repris. Les volumes sont originaux.
Les seules formes Canvas actuelles sont une minuscule texture de particule
créée par le code ; le film est capturé directement depuis le canvas WebGL.

## Installation et lecteur autonome de l'aperçu V4

Node.js, Chromium et FFmpeg sont nécessaires à l'export. Les versions sont
fixées dans `package-lock.json`. Dans ce dossier :

```bash
npm ci --ignore-scripts --no-audit --no-fund
npm run build
```

Dans le cloud, un cache inscriptible peut être nécessaire :
`npm ci --cache /workspace/.cache/npm --ignore-scripts`.

Ouvrir `dist/index.html` dans Chrome ou Firefox : lecture, pause et recherche
dans les 24 secondes. Le dossier `dist/` est autonome, sans ressource distante
ni clé. Le ZIP livré peut être extrait puis ouvert, sans installation.
La capture sert uniquement les fichiers publics prévus sur 127.0.0.1 et
interdit les requêtes du navigateur vers une autre origine.

## Export de la V4

Depuis la racine du dépôt :

```bash
python experiments/deep-sea-procedural/make-ambience.py \
  --seconds 24 --out /tmp/deepsea-v4/ambience.wav
```

Puis, depuis ce dossier :

```bash
node capture.mjs --out /tmp/deepsea-v4/apercu-3d-v4.mp4 \
  --duration 24 --audio /tmp/deepsea-v4/ambience.wav
```

Images **natives 1920×1080**, H.264 CRF17, 30 images/s, 720 images ; ambiance
AAC192 stéréo48kHz. Le script préserve les sorties existantes et verrouille
chaque nom de fichier. Après une interruption, choisir une nouvelle sortie
ou retirer son verrou seulement après avoir confirmé l'arrêt du processus.
`DEEPSEA_CHROMIUM` et `DEEPSEA_FFMPEG` choisissent les exécutables.

Contrôles avant export :

```bash
node capture.mjs --stills 2,5,12,13,20,22 --stills-dir /tmp/deepsea-v4/review
```

Contrôle reproductible de l'espace libre, depuis ce dossier :

```bash
node verify-clearance.mjs --out /tmp/deepsea-v4/clearance.json
```

Il inspecte dans Chromium les vrais volumes déformés à 60 poses/s et toutes
les boîtes des rochers, puis vérifie retour arrière, visibilité et coordonnées
finies. Il échoue si un chevauchement est trouvé. Le contrôle géométrique
indépendant du sol effectué pour la V4 n'est pas inclus dans ce CLI.

Le rapport voisin du MP4 indique taille, SHA-256, durée, cadence, nombre
réel d'images, temps d'export et erreurs du navigateur. Le rendu laisse les
indicateurs de contrôle final à `false` : seul le QA du fichier terminé les valide.

## Coût et vitesse des aperçus courts

**Zéro appel de génération et zéro facturation à l'image.** Aucune API Algrow
ni autre fournisseur n'est utilisée. Three.js est sous licence MIT, incluse
dans le ZIP. Le développement utilise la session, et le calcul la machine :
ce n'est pas une promesse de coût global nul.

Le navigateur disponible utilise **SwiftShader sur processeur**, sans GPU local.
La V4 a pris **218,418 s pour 720 images** sur la machine actuelle, capture
et encodage inclus. Ce résultat ne mesure pas le futur fond sleep ni deux
heures de narration ; la charge et le cadrage peuvent influencer la durée.

La V3 complète avait pris **257,221 s pour 720 images**, soit environ 2,80 images
calculées/s, capture et encodage inclus. Elle prend davantage de temps que la
V2 (180,586 s) : géométrie enrichie, déformations et anticrénelage actif donnent
la priorité au rendu demandé. Ces chiffres n'isolent pas le coût de chaque
changement. Les mesures suivantes sur les V1/V2 sont historiques.

Une mesure sur la V2 native1080 au même instant donne 428 ms/image avec
l'éclairage Lambert contre **199 ms/image** avec l'éclairage aux sommets,
après six images de chauffe et six images mesurées. Cela mesure un plan,
pas tout le film. L'éclairage de certaines surfaces est plus doux ; les
volumes, couleurs, lumière mobile et brume sont conservés.

La capture WebGL directe évite la copie complète vers un deuxième Canvas2D.
JPEG direct était plus rapide que capture écran, lecture brute et encodage
vidéo expérimental testés sur cette machine. Le film reste encodé en H.264.
La V1 avait pris 500 s pour 30 s de vidéo : comparer les exports complets
par image, plutôt que les seules durées de vidéos différentes.
La V2 complète a pris **180,586 s pour 720 images**, soit environ 3,99 images
calculées/s, contre 1,80 pour la V1 : gain mesuré d'environ **2,2 fois**.
Ces deux exports incluent la capture et l'encodage, sur cette machine ; ce
n'est pas une promesse de performance sur une autre machine ou un long.

Le style attend toujours **la validation utilisateur**. Aucun téléchargement
n'autorise une publication automatique. Aucune publication YouTube ou Discord.
Un long exigerait d'autres scènes/actions/échelles liées aux faits, pas
l'allongement de ce trajet. Les gains d'un GPU ou d'un montage long restent
à mesurer ; ne pas annoncer une cadence de production finale sur ce seul essai.

## Archives et références

### Aperçu V3 livré — archive du 10 octobre 2026

[Voir le nouvel aperçu V3 sur GoFile](https://gofile.io/d/6pQee3FV).

- `Les-Profondeurs-V3-Nage-24s.mp4` : 24 s, 1920×1080 natif, 30 images/s,
  720 images, 9 840 323 octets ; ambiance originale, sans voix off.
- `Exploration-3D-V3-HTML.zip` : lecteur autonome sans son, 198 898 octets ;
  extraire puis ouvrir `Les-Profondeurs-3D/index.html`, sans installation.

SHA-256 du MP4 :
`7b746b1e093f6173767ee1d57ac54c5abdc278f68fddf5ff4938fefa111ec438`.
Les deux uploads sont vérifiés auprès de GoFile par taille et MD5.
Décodage vidéo/audio intégral sans erreur ; pic audio −18,51 dBFS, aucun
échantillon saturé. Revue du fichier final : 12 images réparties, 40 images
du passage du poisson à 8 images/s, 16 de la méduse à 4 images/s et quatre
images natives 1080. Seconde revue indépendante des planches et deux images
natives. Aucune lecture continue ni écoute intégrale humaine n'est prétendue.

Les coordonnées locales vérifiées dans le navigateur changent réellement :
le corps se déforme de jusqu'à 0,250 unité sur une demi-seconde, indépendamment
du déplacement de l'animal dans le décor. Queue, membranes, leurre, banc,
cloche et bras de la méduse évoluent aussi. Les contrôles confirment des
coordonnées finies, une recherche temporelle reproductible et des racines
de modèles inchangées par la bibliothèque d'animation. Le contexte WebGL
confirme l'anticrénelage actif ; aucune erreur navigateur pendant l'export.
La qualité artistique reste soumise à l'avis de l'utilisateur.

Retour reçu : modèles appréciés davantage, mais traversées de rochers signalées.
La revue d'images V3 ne constituait pas un contrôle de collision ; voir V4.


### Aperçu V2 livré — archive du 10 octobre 2026

[Aperçu V2 archivé sur GoFile](https://gofile.io/d/hiTXjUn2).

- `Les-Profondeurs-Immersion-3D-24s.mp4` : 24 s, 1920×1080 natif,
  30 images/s, 720 images, 11 410 969 octets.
- `Exploration-3D-HTML.zip` : lecteur V2 autonome sans son ; extraire puis ouvrir
  `Les-Profondeurs-3D/index.html`, sans installation.

SHA-256 du MP4 :
`c37209f5cfcf1d261fb4ea41052b3a844ff4b32f7ec6feeeb9298a6edaedd76d`.
L'intégrité des deux envois est confirmée par MD5 et taille auprès de GoFile.
Décodage vidéo/audio complet sans erreur, aucune saturation audio ; 12 captures
du MP4 terminé et trois images natives ont été vues. Aucune lecture humaine
intégrale n'est prétendue. L'utilisateur préfère son immersion à la V1 mais
demande de refaire les modèles et leurs mouvements : **le style V2 n'est pas
validé pour une production longue**. Ces résultats ne constituent pas les
contrôles de la V3.

Les sources sont sur GitHub ; films, fichiers compilés et reçus privés restent
hors git. Aucun fichier du jeu n'est utilisé dans les rendus.

### Aperçu V1 archivé

V1 livrée avant le retour négatif : 30 s, 1920×1080/30fps, 900 images,
7 558 921 octets, SHA-256
`7d8f67e750d2e835294f079bd61e56cb57233920883d90e872327d9fdc59bf75`.
Décor Three.js mais animaux Canvas : **ce rendu n'est pas la direction validée**.
`scene-v1.mjs` et `creatures.js` sont des sources archivées, jamais utilisées
par le lecteur actuel. Le montage long reste suspendu.

### Sources

- [DREDGE officiel](https://store.steampowered.com/app/1562430/DREDGE/).
- [Étude des visuels et mouvements DREDGE](STYLE_DREDGE.md) : sources regardées,
  corrections retenues et limites de la comparaison.
- [Baudroies — MBARI](https://www.mbari.org/animal/deep-sea-anglerfish/).
- [Méduse fantôme géante — MBARI](https://www.mbari.org/animal/giant-phantom-jelly/).
- [Exploration — NOAA](https://oceanexplorer.noaa.gov/ocean-fact/explored/) :
  cartographie et observation directe sont des mesures distinctes.

Une future narration doit confirmer espèces, échelles, profondeurs et
comportements. Cet essai ne valide pas un texte documentaire.
