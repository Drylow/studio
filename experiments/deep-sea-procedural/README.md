# Les profondeurs — exploration 3D codée

Nouvelle chaîne YouTube envisagée : **vrais fonds marins, ambiance inquiétante
inspirée de DREDGE**, entièrement construite en HTML/JavaScript, sans Algrow
ni générateur d'images. Le 10 octobre 2026, le premier essai est rejeté comme
trop statique et trop peu immersif. La nouvelle direction est une caméra qui
explore les profondeurs, avec des créatures réellement en 3D près de l'objectif.

**V2 : 24 secondes seulement.** Aucun long de 15–20 minutes n'est lancé.
Attendre le retour utilisateur avant script, voix off et montage du documentaire.

## Aperçu V2 livré — 10 octobre 2026

[Voir le nouvel aperçu 3D sur GoFile](https://gofile.io/d/hiTXjUn2).

- `Les-Profondeurs-Immersion-3D-24s.mp4` : 24 s, 1920×1080 natif,
  30 images/s, 720 images, 11 410 969 octets.
- `Exploration-3D-HTML.zip` : lecteur autonome sans son ; extraire puis ouvrir
  `Les-Profondeurs-3D/index.html`, sans installation.

SHA-256 du MP4 :
`c37209f5cfcf1d261fb4ea41052b3a844ff4b32f7ec6feeeb9298a6edaedd76d`.
L'intégrité des deux envois est confirmée par MD5 et taille auprès de GoFile.
Décodage vidéo/audio complet sans erreur, aucune saturation audio ; 12 captures
du MP4 terminé et trois images natives ont été vues. Aucune lecture humaine
intégrale ni validation du style par l'utilisateur n'est prétendue.
Les sources sont sur GitHub ; films, fichiers compilés et reçus privés restent
hors git. Les droits de réutilisation du jeu ne sont pas nécessaires : aucun
de ses fichiers n'est utilisé.

## Ce qui est réellement calculé

- Caméra en vue subjective : environ 43 mètres de parcours virtuel, légère
  dérive, tangage et roulis ; rochers proches et silhouettes lointaines.
- Sol irrégulier, parois facettées, bancs rocheux et particules en suspension.
- Un banc de 17 poissons avec profondeur et mouvements individuels.
- Une baudroie volumétrique : gueule, dents, yeux, leurre, queue et nageoires.
- Une méduse volumétrique avec cloche et quatre bras buccaux larges animés.
- Chaque animal possède une vraie géométrie dans la même scène : projection,
  lumière et occultation par les rochers, aucun animal Canvas superposé.
- Lumière de plongée liée à la caméra, couleurs mates, brume et calcul de
  l'éclairage aux sommets pour réduire le coût du rendu logiciel.
- Animation déterministe : `render(seconds)` donne toujours la même scène.
- Ambiance sonore synthétisée localement ; pas de musique, sample ni voix.

C'est une **reconstitution illustrative**, pas une expédition réelle. Le
rapprochement des espèces sert seulement à montrer le rendu. DREDGE inspire
les surfaces facettées, les couleurs sourdes et la visibilité ; aucun modèle,
image, interface, son ou extrait du jeu n'est repris. Les volumes sont originaux.
Les seules formes Canvas actuelles sont une minuscule texture de particule
créée par le code ; le film est capturé directement depuis le canvas WebGL.

## Installation et lecteur autonome

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

## Export de la V2

Depuis la racine du dépôt :

```bash
python experiments/deep-sea-procedural/make-ambience.py \
  --seconds 24 --out /tmp/deepsea-v2/ambience.wav
```

Puis, depuis ce dossier :

```bash
node capture.mjs --out /tmp/deepsea-v2/apercu-3d.mp4 \
  --duration 24 --audio /tmp/deepsea-v2/ambience.wav
```

Images **natives 1920×1080**, H.264 CRF17, 30 images/s, 720 images ; ambiance
AAC192 stéréo48kHz. Le script préserve les sorties existantes et verrouille
chaque nom de fichier. Après une interruption, choisir une nouvelle sortie
ou retirer son verrou seulement après avoir confirmé l'arrêt du processus.
`DEEPSEA_CHROMIUM` et `DEEPSEA_FFMPEG` choisissent les exécutables.

Contrôles avant export :

```bash
node capture.mjs --stills 2,5,12,13,20,22 --stills-dir /tmp/deepsea-review
```

Le rapport voisin du MP4 indique taille, SHA-256, durée, cadence, nombre
réel d'images, temps d'export et erreurs du navigateur. Le rendu laisse les
indicateurs de contrôle final à `false` : seul le QA du fichier terminé les valide.

## Coût et vitesse

**Zéro appel de génération et zéro facturation à l'image.** Aucune API Algrow
ni autre fournisseur n'est utilisée. Three.js est sous licence MIT, incluse
dans le ZIP. Le développement utilise la session, et le calcul la machine :
ce n'est pas une promesse de coût global nul.

Le navigateur disponible utilise **SwiftShader sur processeur**, sans GPU local.
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

V1 livrée avant le retour négatif : 30 s, 1920×1080/30fps, 900 images,
7 558 921 octets, SHA-256
`7d8f67e750d2e835294f079bd61e56cb57233920883d90e872327d9fdc59bf75`.
Décor Three.js mais animaux Canvas : **ce rendu n'est pas la direction validée**.
`scene-v1.mjs` et `creatures.js` sont des sources archivées, jamais utilisées
par le lecteur V2. Le montage long reste suspendu.

- [DREDGE officiel](https://store.steampowered.com/app/1562430/DREDGE/).
- [Baudroies — MBARI](https://www.mbari.org/animal/deep-sea-anglerfish/).
- [Méduse fantôme géante — MBARI](https://www.mbari.org/animal/giant-phantom-jelly/).
- [Exploration — NOAA](https://oceanexplorer.noaa.gov/ocean-fact/explored/) :
  cartographie et observation directe sont des mesures distinctes.

Une future narration doit confirmer espèces, échelles, profondeurs et
comportements. Cet essai ne valide pas un texte documentaire.
