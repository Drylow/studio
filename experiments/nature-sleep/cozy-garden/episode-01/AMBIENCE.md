# Jardin des lanternes — fond sonore original

Le décor approuvé est `../A-lantern-garden.png` : abri en bois au premier plan,
feuillage sous la pluie, serre éclairée et petit bassin à droite. Le nouveau
fond sonore suit ce décor. **Le roulement de train est entièrement retiré.**

## Stems prêts

Dossier privé : `output/nature-sleep/garden-production/ambience/`.

Chaque fichier dure **240 secondes exactement**, stéréo **24 kHz / 16 bits**,
FLAC sans perte. Il contient **5 760 000 échantillons par canal** ; trente
répétitions donnent exactement deux heures. Aucun WAV de deux heures créé.

| Fichier | Contenu | Sonie intégrée | Crête vraie | Étendue de sonie | Taille |
| --- | --- | ---: | ---: | ---: | ---: |
| `ambience.flac` | Nouvelle pluie sur feuilles et pergola, petite eau à droite | −24,00 LUFS | −12,50 dBTP | 0,7 LU | 10 162 935 octets |
| `music.flac` | Copie exacte de notre nappe harmonique originale | −24,00 LUFS | −13,26 dBTP | 3,6 LU | 4 889 246 octets |

L’ensemble, reçu et trois extraits de contrôle inclus, pèse
**20 691 246 octets** : sous le budget de 50 Mo.

Empreintes SHA-256 :

- Ambiance : `eea24287764da820589c6b7ce832f3031f9b9d306651d73ef33ee92d8478f7a8`
- Musique : `64e87d3af1d0bde0257a7d8e73e09e2ed46268d26dffb0f983c9aa755593df87`

## Provenance et fabrication

L’ambiance est **nouvellement synthétisée** dans `make_ambience.py`, avec une
graine fixe, des champs de bruit coloré et de lentes variations continues :

- pluie diffuse sur feuillage, largeur stéréo modérée et aigus adoucis ;
- bruit plus mat de pluie sur le bois de l’abri ;
- petite eau en mouvement, légèrement à droite comme le bassin de l’image ;
- quelques variations diffuses de texture, sans goutte claquante isolée.

Aucun roulement mécanique, claquement de rails, tonnerre, chant d’oiseau,
alarme ou effet soudain. Le fond ne prétend pas être une captation réelle.
Il ne contient ni enregistrement externe ni échantillon téléchargé.

La musique a été **copiée octet pour octet**, sans régénération, depuis
`output/nature-sleep/night-train-production/ambience/music.flac`. Il s’agit
de notre composition originale de nappes lentes, sans percussion ni piano.
Son empreinte est vérifiée avant et après copie. Aucun audio de Stephen
Dalton, achat, fournisseur musical ou appel payant n’a été utilisé.

Le script réutilise seulement les fonctions techniques d’encodage, mesure et
contrôle de l’ancien moteur `night-train/episode-01/make_ambience.py`. Il
n’appelle pas le compositeur d’ambiance de train, ni le compositeur musical.

## Contrôles réalisés

- Format et durée exacts lus avec `ffprobe`.
- Décodage intégral des deux FLAC avec arrêt sur erreur ; nombres
  d’échantillons vérifiés, empreintes consignées dans `receipt.json`.
- Mesures de sonie et de crête avec FFmpeg. La normalisation de l’ambiance
  est un **gain constant**, sans compression ou pompage dans les pauses.
- Signal conçu périodique sur 240 secondes : champs Fourier et toutes les
  enveloppes ferment la même période. La dernière valeur enregistrée est
  celle de `240 − 1/24000 s` ; elle n’est pas artificiellement dupliquée.
- Au raccord du jardin, l’écart entre derniers/premiers échantillons vaut
  **0,010 / 0,172 fois** le 99e centile des variations ordinaires gauche/droite.
  Il n’y a pas de rupture de niveau ou de silence ajouté à chaque boucle.
- Le stem jardin comporte seulement **2,67 %** de son énergie entre 30 et
  200 Hz et une énergie négligeable sous 30 Hz ; il ne conserve pas la couche
  grave du train. Le reste évoque davantage la pluie et l’eau proche.

Extraits privés de **40 secondes**, vingt avant et vingt après le raccord :
`ambience-seam-preview.flac`, `music-seam-preview.flac` et
`quiet-bed-seam-preview.flac` (mix d’essai).

**Pas d’écoute humaine ou par modèle réalisée ici.** Ces contrôles numériques
ne remplacent pas l’écoute du mix final avec sa narration ; ne pas présenter
ce reçu comme une validation auditive subjective.

## Réglages de départ du mix

Les fichiers à −24 LUFS sont des références à atténuer sous la voix :

- ambiance : **−15 dB**, soit environ −39 LUFS ;
- musique : **−20 dB**, soit environ −44 LUFS.

Ces valeurs accompagnent une voix autour de −20 à −18 LUFS. Utiliser des gains
explicites et `amix=normalize=0`, puis mesurer et écouter le résultat, notamment
à faible volume. Les LUFS ne s’additionnent pas arithmétiquement.
Appliquer le fondu d’ouverture et celui de fermeture seulement au début et
à la fin des deux heures, pas à chaque répétition des stems.

## Reproduction

```sh
.venv/bin/python experiments/nature-sleep/cozy-garden/episode-01/make_ambience.py \
  --out output/nature-sleep/garden-production/ambience-new
```

NumPy, SciPy et FFmpeg existants suffisent. Le dossier de sortie doit être
vide. Le générateur exige la musique existante avec son empreinte attendue ;
`--music` permet d’indiquer une autre copie du **même fichier**. Il refuse une
source différente ou absente et ne lance aucune génération payante en secours.
