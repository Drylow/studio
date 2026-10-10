# Les profondeurs — exploration 3D codée

## Boucle sleep de cinq minutes — en cours

Direction actuelle : **histoires marines vraies, ambiance calme et inquiétante**.
Les futurs épisodes visent deux heures : ce fond de **300 secondes** pourra
être répété **24 fois** sous une narration originale. Ces cinq minutes sont
calculées comme un parcours continu, distinct des anciens aperçus courts.
**Rendu intégral repris avec la scène corrigée ; contrôle du fichier final
à terminer avant livraison.** Aucun épisode de deux heures, script, voix off
ou publication n'est produit à cette étape.

La scène conserve des volumes originaux entièrement codés : relief, rochers,
détails de surface procéduraux et vie sur le fond. Sept groupes animés
(`roots`) réunissent une baudroie, deux méduses, deux bancs et deux raies. Caméra,
animaux, particules et ambiance sonore suivent des cycles de 300 secondes,
sans fondu final ; le raccord et les passages libres doivent être contrôlés.
Les animaux sont des reconstitutions illustratives, pas des prises de vue
scientifiques ni des modèles repris du jeu.

Pour séparer son passage de ceux des autres animaux, la seconde raie (`ray2`)
passe désormais plus haut : son altitude de base est fixée à `y = 2.9`
unités de scène. Les volumes réservés aux animaux et à la caméra sont
recalculés avant de placer le décor. Le rendu repris utilise ce réglage ;
la cohérence de tout le cycle et le raccord du MP4 restent à vérifier avant
d'annoncer le fichier terminé.

Le lecteur se construit séparément dans `dist-sleep/`. Depuis la racine du dépôt,
créer l'ambiance originale avec la venv existante et NumPy :

```bash
.venv/bin/python experiments/deep-sea-procedural/make-sleep-ambience.py \
  --seconds 300 --out /tmp/deepsea-sleep-5m/ambience-master.wav
```

Puis, depuis `experiments/deep-sea-procedural/` :

```bash
npm run build:sleep
node verify-sleep-loop.mjs --out /tmp/deepsea-sleep-5m/loop-check.json
node capture-loop.mjs \
  --out /tmp/deepsea-sleep-5m/Les-Profondeurs-Boucle-Sleep-5min.mp4 \
  --audio /tmp/deepsea-sleep-5m/ambience-master.wav
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
en cours ; les livraisons qui suivent restent les anciens aperçus courts.

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
