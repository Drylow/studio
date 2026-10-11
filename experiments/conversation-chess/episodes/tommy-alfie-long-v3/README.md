# Tommy / Alfie — long V3

Ce candidat prépare **13 min 34,067 s** après le guide et les pauses, pour la
nouvelle demande de vidéos de dix à quinze minutes. Il garde trois rencontres
sur S02E02, S02E06 et S03E06. Landa–Shosanna reste prioritaire ; ce dossier ne
contient aucun nouveau master, export final ou envoi.

`source-map.candidate.json` décrit les coordonnées des trois épisodes et les
images du futur master. `timeline.candidate.json` contient 23 analyses originales
de sept secondes, l'habillage approuvé et les coordonnées de ce master. Les
`*.draft.json` et `editorial-preflight.json` préservent le premier brouillon de
12:59 ; la version retenue et les chiffres actuels sont dans
`editorial-preflight.candidate.json`. Les sources et le court V3 de 5:20 restent
intacts.

| Élément | Durée | Images à 30 fps |
| --- | ---: | ---: |
| 22 extraits | 603,667 s | 18 110 |
| 7 cartes de transition | 21,4 s | 642 |
| Master source prévu | 625,067 s | 18 752 |
| 23 analyses | 161 s | 4 830 |
| Guide / bilan | 16 s / 12 s | 840 |
| Film final prévu | 814,067 s | 24 422 |

## Découpage et décisions

La première rencontre garde l'invitation par télégramme, le diagnostic financier,
la préparation face à l'arme et l'accusation concernant Billy Kimber. Ce dernier
échange explique la méfiance d'Alfie ; l'ancien montage l'avait retiré. La menace
de l'armoire s'arrête après sa phrase complète, avant « So, what I would do is
this ». Une carte indique la discussion omise. Le dernier commentaire décrit
l'invitation à exposer le plan, sans évoquer une démonstration absente du montage.

La deuxième rencontre reprend les quatorze coupes déjà vérifiées du court V3 :
l'accord à vingt pour cent devient une exigence de cent pour cent, puis finit à
trente-cinq. Les conditions de la menace, sa crédibilité, le refus à soixante-cinq
et le contrôle du récit de guerre restent compréhensibles. Les neuf analyses
de cet acte sont conservées ; elles ne multiplient pas les Brilliant pour une
même idée.

Le troisième acte commence par la demande complète de Tommy et les trois listes
d'acheteurs fournies par Alfie. On peut ainsi comprendre ce que Tommy a vérifié
et ce que signifie le nom omis. L'accusation, l'enjeu de l'enfant, le contre-argument
moral, l'acceptation de Tommy et la clarification finale restent présents.
Les interventions omises sont signalées par des cartes. Des armes pointées et
du sang sur le visage de Tommy restent visibles ; aucun tir n'est conservé.

Tommy ouvre la **vidéo** avec sa phrase sur les policiers à son service, à
S02E02 692,4 s. Tommy reste Blanc, Alfie Noir pour toute cette rivalité ; aucune
remise à zéro artificielle par acte n'est ajoutée. Le pion Shelby approuvé reste
le même PNG, avec ses badges déjà intégrés : ne pas ajouter `mascot.badges:true`.

Le bilan totalise Brilliant 2, Great 5, Best 8, Good 2, Book 5 et Inaccuracy 1.
Excellent, Mistake et Blunder sont à zéro. Les deux Brilliant correspondent au
risque partagé préparé par Tommy puis au renversement du standard moral par
Alfie. Ces évaluations et les chiffres de la barre sont des lectures éditoriales,
pas des mesures Stockfish. Aucune catégorie Miss ou Interesting n'est ajoutée.

## Contrôles réellement faits

- `source-preflight.json` : les trois SHA originaux correspondent aux anciens
  fichiers locaux ; leur profil mesuré est 1280×720, 25 fps, audio anglais.
  Les reçus d'accès stockés indiquent 720p / maximum 720. Aucun nouveau contrôle
  réseau n'est revendiqué.
- `word-boundary-review.json` : 44 limites d'extraits et 23 pauses ne traversent
  aucun mot **reconnu** par les ASR examinés. Leurs temps sont déjà absolus,
  sans ajout de l'offset source_start. Deux fenêtres S03 supplémentaires sont
  liées au SHA actuel et au PCM décodé. L'ASR comporte des erreurs de texte et
  n'est pas un alignement forcé complet.
- `visual-sample-review.json` : huit planches et 67 cadres natifs réellement
  examinés couvrent chaque début, fin et point d'analyse. Aucun sous-titre
  incrusté ni watermark visible dans ces échantillons. La couleur sombre et
  le grain sont ceux des sources. Quelques plans montrent la réaction de
  l'interlocuteur : les locuteurs suivent les dialogues, pas seulement le visage.
- `native-ui-review.json` : deux vrais cadres graphiques 1920×1080 ont été
  examinés. Le bilan raccourci est lisible et totalise 23 annotations ; le
  commentaire le plus long rentre dans la bulle et son budget de sept secondes.
  Ce contrôle de mise en page n'est pas un export du film.
- `rating-review.json` : les Best / Great conservent la valeur et la barre,
  les autres changements suivent leur catégorie et leur locuteur.

Les flags positifs `source_reviewed`, `source_visually_reviewed`,
`annotation.reviewed` et l'exception nativeHD couvrent ce stade précis. Le SHA
du futur master reste `null`. Aucun visionnage continu, écoute, export final ou
contrôle YouTube n'est déclaré fait. Il faut notamment écouter la pause
télégramme à 760,70 s, située très près de « Really? », et revoir en mouvement
le raccord sur la réaction d'Ollie au premier refus.

## Préparation à lancer après Landa

Depuis la racine du dépôt, le helper vérifie seulement le plan par défaut,
sans écrire ni encoder de média :

```bash
python experiments/conversation-chess/episodes/tommy-alfie-long-v3/prepare-master.py \
  --plan experiments/conversation-chess/episodes/tommy-alfie-long-v3/source-map.candidate.json \
  --timeline experiments/conversation-chess/episodes/tommy-alfie-long-v3/timeline.candidate.json
```

Pour créer l'intermédiaire dans un **nouveau** dossier :

```bash
python experiments/conversation-chess/episodes/tommy-alfie-long-v3/prepare-master.py \
  --plan experiments/conversation-chess/episodes/tommy-alfie-long-v3/source-map.candidate.json \
  --timeline experiments/conversation-chess/episodes/tommy-alfie-long-v3/timeline.candidate.json \
  --prepare --out output/conversation-chess/tommy-alfie-long-v3-master
```

Le helper garde les dimensions natives, convertit seulement la cadence à 30 fps,
conserve les dialogues en PCM 48 kHz, ajoute des fondus de coupe de 20 ms et
des cartes silencieuses aux durées écrites. Il contrôle les images, les
échantillons audio, les timestamps et le décodage intégral avant d'écrire le
SHA réel du master et la timeline préparée. Aucun pitch, miroir, recadrage de
camouflage ou traitement pour tromper une détection n'est appliqué. Les parts
et le master occupent tous de l'espace : vérifier le stockage avant cette étape.

Après examen du master préparé, reprendre la préparation graphique native :

```bash
node experiments/conversation-chess/render-clip.mjs --prepare-project \
  --source output/conversation-chess/tommy-alfie-long-v3-master/source-master-1280x720-30fps.mkv \
  --timeline output/conversation-chess/tommy-alfie-long-v3-master/timeline.json \
  --out output/conversation-chess/tommy-alfie-long-v3-native/prepared
bash experiments/conversation-chess/with-editor-display.sh \
  python experiments/conversation-chess/export-kdenlive.py \
  --manifest output/conversation-chess/tommy-alfie-long-v3-native/prepared/project-manifest.json \
  --bundle output/conversation-chess/tommy-alfie-long-v3-native/kdenlive \
  --subtitles experiments/conversation-chess/episodes/tommy-alfie-long-v3/captions.source.en.srt \
  --render output/conversation-chess/tommy-alfie-long-v3-native/kdenlive/Tommy-Alfie-long-V3-native.mp4
```

`captions.source.en.srt` contient 195 cues provenant des trois VTT anglais locaux,
sur l'horloge du master de 625,067 s avant le guide et les analyses. Les cartes
restent sans texte ; l'exporteur réserve les titres aux segments de dialogues.
`captions-review.json` conserve les empreintes, les sept ajustements de limites
et l'omission prudente d'un court cue mixte ambigu. Aucune écoute humaine ou
certification de provenance officielle des VTT n'est revendiquée.

Les plans source sont 720p natifs ; la composition graphique est 1080p. Ne pas
présenter le résultat comme des épisodes natifs 1080p ou 4K. La musique est
Sneaky Snitch dans le guide uniquement ; reprendre les crédits réellement
générés dans `MUSIC_CREDITS.txt` pour la description de la livraison.

Le montage reste composé d'extraits protégés. Le procédé transmis et le test
Death Note d'un autre fichier n'établissent aucune garantie pour celui-ci.
Après les contrôles techniques, visuels et sonores du vrai export, effectuer
un contrôle privé YouTube et examiner ses claims avant publication. La durée,
les commentaires et l'habillage ne constituent pas une autorisation des ayants droit.
