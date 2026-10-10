# Les profondeurs — prototype de visuels codés

Direction utilisateur du 10 octobre 2026 : nouvelle chaîne YouTube sur les
**vrais fonds marins, avec une ambiance inquiétante inspirée de DREDGE**.
Les visuels doivent être construits en HTML/JavaScript, sans Algrow ni autre
générateur d'images. Un aperçu de **30 secondes seulement** sert à choisir la
direction ; le script, la voix off et le montage du long viennent après le
retour utilisateur. Aucun long de 15–20 minutes n'est lancé.

## Aperçu livré — 10 octobre 2026

[Dossier GoFile de l'aperçu](https://gofile.io/d/VDW9Jtf8) :

- `Les-Profondeurs-Apercu-30s.mp4` : 30,000 s, 1920×1080 natif, 30 images/s,
  900 images, H.264/AAC, 7 558 921 octets.
- `Visuels-Codes-HTML.zip` : lecteur autonome ; extraire puis ouvrir
  `Les-Profondeurs/index.html`, sans installation ni ressource distante.

Empreinte SHA-256 du MP4 :
`7d8f67e750d2e835294f079bd61e56cb57233920883d90e872327d9fdc59bf75`.
Le dépôt conserve les sources ; les fichiers compilés et le MP4 restent hors git.
L'intégrité des deux envois a été confirmée par taille et MD5 auprès de GoFile.

Contrôles du MP4 terminé : décodage vidéo/audio intégral sans erreur, aucune
saturation audio, revue visuelle de 15 images réparties sur le film et de deux
images natives1080. Ce contrôle ne prétend pas à une lecture humaine intégrale.
Export mesuré : 500 s, soit environ 1,8 image calculée/s sur cette machine.
Le style reste en attente de l'avis utilisateur ; aucune vidéo longue n'est lancée.

## Ce que calcule le prototype

- Relief 3D triangulé, rochers facettés instanciés et véhicule original : Three.js.
- Éclairage, brume de profondeur, deux faisceaux et particules en suspension.
- Baudroie stylisée avec un seul leurre lumineux ; méduse fantôme avec quatre
  bras buccaux, sans émission lumineuse inventée ; petits poissons éloignés.
- Animaux et légendes : formes Canvas originales animées, pas des modèles 3D.
- Animations déterministes : la même seconde donne la même image.
- Ambiance sonore synthétisée localement, sans musique, enregistrement ou voix.

L'aperçu est une reconstitution illustrative. Les animaux apparaissent pour
évaluer le style : ce n'est pas la trace d'une expédition réelle. Aucun modèle,
image, interface, extrait ou son du jeu DREDGE n'est inclus. Les formes du
véhicule et les compositions sont originales.

## Installation et aperçu

Node.js, FFmpeg et Chromium sont nécessaires à l'export. Les dépendances sont
fixées dans `package-lock.json`. Dans ce dossier :

```bash
npm ci --ignore-scripts --no-audit --no-fund
npm run build
```

Dans cet environnement cloud, utiliser un cache inscriptible si le cache npm
personnel est absent : `npm ci --cache /workspace/.cache/npm --ignore-scripts`.

Ouvrir `dist/index.html` dans Chrome ou Firefox : lecture, pause et déplacement
dans les 30 secondes. Le dossier `dist/` compilé est autonome et utilise zéro
ressource distante. Il peut être partagé en ZIP, sans installation pour le lire.
La capture cloud charge ce même dossier par un serveur HTTP lié uniquement à
127.0.0.1 ; seules ses trois ressources publiques sont servies.

## Export de l'aperçu

Depuis la racine du dépôt, préparer l'ambiance sonore originale :

```bash
python experiments/deep-sea-procedural/make-ambience.py \
  --seconds 30 --out /tmp/deepsea-preview/ambience.wav
```

Puis, dans ce dossier :

```bash
node capture.mjs --out /tmp/deepsea-preview/apercu.mp4 \
  --audio /tmp/deepsea-preview/ambience.wav
```

Le navigateur dessine les images natives 1920×1080. FFmpeg les encode en
H.264, CRF17, 30 images/s ; ambiance AAC192 stereo48kHz. Le script refuse
d'écraser un film existant et verrouille chaque sortie avant de lancer un
export. Une interruption laisse le verrou : choisir une nouvelle sortie ou
retirer le verrou uniquement après avoir confirmé l'arrêt du processus.

`DEEPSEA_CHROMIUM` et `DEEPSEA_FFMPEG` permettent de choisir les exécutables.
Sur un système sans `/usr/bin/chromium`, fournir le chemin Chrome/Chromium réel
par `DEEPSEA_CHROMIUM`. Captures de contrôle sans export vidéo :

```bash
node capture.mjs --stills 3,12,23 --stills-dir /tmp/deepsea-review
```

Le rapport voisin du MP4 contient empreinte, durée, nombre d'images, temps
réel d'export et erreurs navigateur. Il laisse les indicateurs de revue finale
et de décodage à `false` : le rendu seul ne valide pas le film.

## Coût et limites mesurés

**Zéro appel de génération et zéro facturation à l'image.** Aucune clé ni API
Algrow n'est utilisée. Les logiciels employés sont disponibles dans
l'environnement ; Three.js est sous licence MIT, copiée dans le ZIP compilé.
Le temps de développement utilise la session de travail, et le calcul emploie
la machine : ce n'est pas une promesse de coût global nul.

Le navigateur cloud utilise le rendu logiciel SwiftShader, sans GPU matériel
vérifié. Le test du décor optimisé atteint environ 1–2 images natives1080/s,
28 appels de dessin et 3 624 triangles. L'export d'un long en 3D intégrale peut
donc être lent. Mise en cache par plan, dessin des animaux en Canvas et GPU
matériel sont des pistes ; leur gain n'est pas encore mesuré sur un long.
Ne pas extrapoler une cadence à partir des seuls mouvements 2D.

La caméra et le véhicule restent dans un même décor pour cet essai. Une vidéo
longue exige d'autres scènes, actions, échelles et schémas liés aux faits, pas
un allongement de cette boucle. La direction visuelle est **en attente de
validation utilisateur**. Aucune publication YouTube ou Discord n'est lancée.

## Références scientifiques et visuelles

- [DREDGE officiel](https://store.steampowered.com/app/1562430/DREDGE/) : référence
  de silhouettes, surfaces facettées, couleurs sourdes et visibilité limitée.
- [Baudroies — MBARI](https://www.mbari.org/animal/deep-sea-anglerfish/).
- [Méduse fantôme géante — MBARI](https://www.mbari.org/animal/giant-phantom-jelly/).
- [Exploration — NOAA](https://oceanexplorer.noaa.gov/ocean-fact/explored/) :
  cartographie et observation directe sont deux mesures distinctes.

Une future narration devra confirmer l'espèce, l'échelle, la profondeur et
le comportement de chaque scène. Aucun texte documentaire complet n'est
validé par cet aperçu d'ambiance.
