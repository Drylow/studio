# Fond sonore original — train de nuit

Deux stems indépendants sont prêts pour le mix du premier épisode de Quiet
Little Worlds. **Aucun enregistrement, morceau existant, fichier téléchargé,
API de musique ou appel payant n’entre dans leur fabrication.**

Ils sont synthétisés dans `make_ambience.py` avec des champs de bruit coloré,
des oscillateurs et des enveloppes périodiques. Il s’agit d’une création sonore
originale évoquant le train et la pluie, pas d’un enregistrement de terrain.
La musique ne reprend ni mélodie ni audio de Stephen Dalton.

## Fichiers et mesures

Résultats privés : `output/nature-sleep/night-train-production/ambience/`.

Les deux fichiers FLAC ont chacun **240 secondes exactement**, **5 760 000
échantillons par canal**, **24 kHz, stéréo, PCM 16 bits**. Trente répétitions
produisent exactement 120 minutes ; aucun intermédiaire WAV de deux heures
n’a été produit.

| Fichier | Rôle | LUFS intégrés | Crête vraie | Étendue de sonie | Taille |
| --- | --- | ---: | ---: | ---: | ---: |
| `ambience.flac` | Pluie étouffée par une vitre, roulement grave continu, air du wagon | −24,00 | −12,81 dBTP | 1,2 LU | 8 912 814 octets |
| `music.flac` | Nappes harmoniques lentes et chaudes, sans mélodie ni percussion | −24,00 | −13,26 dBTP | 3,6 LU | 4 889 246 octets |

SHA-256 :

- Ambiance : `852157742aefcab32af5be1e2db60b6d4a6197d62accd783610c7d5eba40fb12`
- Musique : `64e87d3af1d0bde0257a7d8e73e09e2ed46268d26dffb0f983c9aa755593df87`

Le reçu exact, avec spectres, RMS et raccords, est dans `receipt.json`.
FFmpeg `loudnorm` sert **uniquement à mesurer**. La correction appliquée est
un gain constant ; aucun limiteur ni compresseur ne pompe dans les pauses.

## Construction et douceur

- Pluie : bruit filtré, large mais assourdi, filtrage fort dans les aigus,
  légères variations lentes et diffusées dans l’espace stéréo. Les couches
  d’eau sont un peu plus présentes côté fenêtre, sans goutte claquante isolée.
- Train : roulement large autour des graves, sans sifflet, claquement de rail,
  voix de gare, accélération ni tonnerre. Énergie infrabasse limitée : la part
  d’énergie sous 30 Hz du stem complet reste environ 0,04 %.
- Musique : quatre nuages harmoniques suspendus qui se recouvrent lentement
  sur quatre minutes, sons assourdis, très peu d’harmoniques aigus, pas de
  piano, de tempo saillant ou de montée dramatique. 40 % de l’énergie est
  entre 30 et 200 Hz, presque tout le reste entre 200 et 2 000 Hz.
- Image sonore stable : largeur modérée du bruit, placement doux des notes,
  pas de balayage stéréo distrayant.

Ces propriétés décrivent la synthèse et les mesures. **Aucune écoute humaine
ou par modèle n’a été effectuée ici** : elles ne remplacent pas une appréciation
auditive réelle du mix final avec la voix. Ne pas affirmer « écouté et parfait ».

## Raccord de boucle vérifié

Le bruit est créé directement par transformée de Fourier inverse sur la
période entière. Les fréquences, phases de modulation et enveloppes musicales
effectuent un nombre entier de cycles dans 240 secondes. Le signal possède
ainsi un état continu à `t = 240 s`, identique à celui de `t = 0`.

Le dernier échantillon ne doit **pas** être dupliqué : il représente
`240 s − 1/24000 s`, et non `240 s`. Son écart avec le premier est donc une
variation ordinaire d’un échantillon, pas obligatoirement zéro.

Après encodage et décodage complet des FLAC :

- forme exacte vérifiée : 5 760 000 × 2 échantillons par stem ;
- raccord ambiance : saut d’un échantillon = 0,45 / 0,30 fois le 99e centile
  des variations ordinaires gauche/droite ;
- raccord musique : 1,18 / 0,84 fois ce même centile ;
- aucun dépassement de −3 dBTP ; marges réelles supérieures à 12 dB ;
- pas de silence ajouté entre répétitions, pas de fade-out puis fade-in à
  chaque raccord, ce qui ferait respirer artificiellement la boucle.

Trois extraits privés de contrôle montrent **20 secondes avant et 20 secondes
après le raccord réel** :

- `ambience-seam-preview.flac`
- `music-seam-preview.flac`
- `quiet-bed-seam-preview.flac` — mix d’essai à −15 dB / −18 dB respectivement.

L’ensemble des stems, reçus et extraits reste inférieur à 20 Mo, largement
sous le budget de 100 Mo.

## Dose de départ pour le montage

Les stems sont livrés à −24 LUFS pour garder une référence simple ; **ne pas
les additionner à plein niveau sous la narration**.

Pour une voix autour de −20 à −18 LUFS, point de départ :

- ambiance : **−15 dB**, soit un gain linéaire de 0,17783 et environ −39 LUFS ;
- musique : **−18 dB**, soit 0,12589 et environ −42 LUFS.

Écouter ensuite la parole à faible volume et ajuster. L’ambiance doit évoquer
un refuge, la musique rester à peine perceptible. Mesurer le mix final plutôt
que sommer les LUFS arithmétiquement. Utiliser `amix=normalize=0` avec des
gains explicites pour ne pas atténuer involontairement la voix.

Les fondus de début et fin s’appliquent une seule fois sur la durée de la
vidéo entière, pas à chaque boucle. Éviter un remontage automatique très
audible du fond pendant les respirations. Un fichier final à exactement
7 200 secondes peut utiliser `-stream_loop -1` pour chaque stem puis `-t 7200`.

## Reproduction

Depuis la racine du dépôt :

```sh
.venv/bin/python experiments/nature-sleep/night-train/episode-01/make_ambience.py \
  --out output/nature-sleep/night-train-production/ambience-new
```

Le générateur refuse d’écraser une livraison existante. Il nécessite NumPy,
SciPy et FFmpeg déjà présents ; sa graine est fixée. Les mêmes dépendances et
versions donnent les mêmes fichiers. Le reçu contient les empreintes réellement
produites ; aucun résultat n’est déclaré reçu depuis un autre ordinateur.
