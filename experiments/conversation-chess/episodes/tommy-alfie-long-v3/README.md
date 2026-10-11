# Tommy / Alfie — long V3

Ce film livré dure **13 min 34,067 s** avec le guide et les pauses, pour la
nouvelle demande de vidéos de dix à quinze minutes. Il garde trois rencontres
sur S02E02, S02E06 et S03E06. Landa–Shosanna reste prioritaire. Le master
intermédiaire est créé et contrôlé dans `output/`. Le montage natif et sa
finition audio sont exportés, avec QA technique finale passée et revue de
140 captures distinctes sur 22 planches. Le kit est livré via
[GoFile](https://gofile.io/d/uCNnoRLc) et Discord, avec reçus confirmés.
Il reste un candidat `youtube-test`, sans publication ni Checks YouTube attestés.

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
| Master source mesuré | 625,067 s | 18 752 |
| 23 analyses | 161 s | 4 830 |
| Guide / bilan | 16 s / 12 s | 840 |
| Film final mesuré | 814,067 s | 24 422 |

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
reste `null` dans la timeline candidate ; les timelines préparées dans
`output/` portent désormais son empreinte réelle. Aucun visionnage continu,
écoute humaine ou contrôle YouTube n'est déclaré fait. Il faut notamment écouter la pause
télégramme à 760,70 s, située très près de « Really? », et revoir en mouvement
le raccord sur la réaction d'Ollie au premier refus.

## Master intermédiaire préparé

`output/conversation-chess/tommy-alfie-long-v3-master/` contient maintenant
`source-master-1280x720-30fps.mkv`, `timeline.json` et
`source-master-manifest.json`. Le fichier de 261 218 773 octets mesure
1280×720 à 30 fps, 625,067 s : **18 752 images et 30 003 200 échantillons PCM
stéréo par canal**, avec timestamps continus et décodage intégral passé.
Son SHA256 est
`614beaf33498a54b198928fae48b3a33f5812d03990e8a2320a457ad9ca462b0`.
Les trois originaux et le pion approuvé conservent leurs empreintes.

Après ces contrôles, les seuls 29 MKV intermédiaires de cette exécution ont été
retirés, avec reçu privé conservant leurs SHA avant suppression. Le master et
les manifests restent intacts ; 261 287 936 octets alloués ont été récupérés.
Les 195 captions sont liées à l'empreinte réelle du master dans
`captions-review.json`. Cela ne remplace pas l'écoute ni la revue du vrai film.

La candidate contient désormais `ending_fade_seconds: 0.5`. La première
candidate et les rapports antérieurs sont conservés dans les fichiers
`*.before-ending-fade.json`. Le master et son ancienne timeline restent les
preuves de la préparation initiale ; leurs octets n'ont pas été modifiés.
Une timeline native dérivée et un nouveau manifeste sont dans
`output/conversation-chess/tommy-alfie-long-v3-native/prepared-ending-fade/`.
Seuls la vidéo, le WAV et l'overlay alpha des **18 dernières images** ont été
régénérés avec les filtres du renderer, avec reçu de leurs empreintes. Les
autres ressources restent inchangées. Les 28 800 échantillons du tail conservent
la durée de 0,6 s ; le fondu démarre à 0,1 s dans ce tail.

`ending-dialogue-evidence.json` décrit la marge après « I saw. » : fin du mot
reconnu à 1445,24 s, fin du cue anglais à 1446,165 s, début du fondu à 1446,5 s
dans S03E06. Le tail contient une ambiance faible mesurée à -43,15 dBFS RMS ;
ce n'est pas du silence numérique. Ces mesures et les mots reconnus ne sont
pas une écoute humaine. Les captions et toutes les notes restent identiques.

## Export et finition audio réels

Kdenlive a fermé l'export de **24 422 images / 814,067 s**, avec son projet,
ses médias liés et son reçu dans
`output/conversation-chess/tommy-alfie-long-v3-native/kdenlive/`.
Le parent conservé `/tmp/tommy-alfie-long-v3-native/Tommy-Alfie-V3-native.mp4`
mesure 386 409 333 octets, SHA256
`28bdc9fee0796d224bf2dffc6bf280d41cfa12994645b0ccc36373cebb7eeeb3`.

`finish-dialogue-audio.py` a ensuite ajouté **4 dB aux seuls intervalles source**.
Le guide, les SFX d'analyse et le bilan gardent leur niveau. L'enfant conservé
`/tmp/tommy-alfie-long-v3-native/Tommy-Alfie-V3-finished.mp4` mesure
386 450 550 octets, SHA256
`e421b73ec7cc0a421f336a2c170fd5ff5955c5e043976c5cd5849e5b654a6c8b`.
Son reçu `.audio.json` atteste le flux image inchangé, le décodage intégral,
un pic réel de **-2,1 dBTP** et une loudness de **-22,2 LUFS**. Cela ne constitue
pas une écoute humaine, une revue visuelle finale ou un contrôle YouTube.
Le checker final a comparé cet enfant aux ressources préparées : décodage
audio/vidéo intégral réussi, 48 fenêtres audio alignées, 23 queues de lecture
et 23 déclenchements de SFX contrôlés, aucun échec ni avertissement. Le PCM
décodé comporte 39 075 840 échantillons par canal, soit les 39 075 200 attendus
plus 640 échantillons de fin AAC ; la vidéo contient exactement 24 422 images.
Aucun échantillon ne dépasse la pleine échelle. Les reçus réels sont dans
`output/conversation-chess/tommy-alfie-long-v3-native/qa/`.

Le même enfant gelé a d’abord fourni **134 captures et 19 planches** :
23 analyses, 96 images de raccord, sept cartes, cinq vues du guide et trois vues du bilan.
`final-frame-extraction.json` les lie au SHA du fichier et du manifeste dérivé.
La revue finale comprend aussi six sous-titres longs : **140 captures distinctes
sur 22 planches** au total. Root a examiné les raccords, les cartes et ces captions
sur 13 planches ; un réviseur indépendant a examiné les analyses, le guide et
le bilan sur neuf planches, avec trois PNG pleine résolution supplémentaires.
`qa/delivery-review.json` lie cette revue au SHA final. Il s’agit d’un examen
échantillonné, sans lecture continue, écoute humaine ni contrôle YouTube.

## Livraison confirmée

Le kit [GoFile](https://gofile.io/d/uCNnoRLc) contient le film fini, la miniature
approuvée, quatre propositions de titre, la description complète et les crédits
musicaux. Les cinq fichiers sont confirmés par le site officiel puis réconciliés
avec les réponses d’upload et leurs empreintes locales. Le reçu conserve
`official_web_client_readback_complete: true`, sans revendiquer un succès du GET
Premium. L’état pending est archivé.

L’envoi Discord est confirmé séparément : un message et trois pièces jointes.
Les preuves sont `publication/gofile-receipt.json` et
`publication/discord_receipt.json` dans le dossier ignoré
`output/conversation-chess/tommy-alfie-long-v3-native/`.
Cette livraison ne constitue pas une publication YouTube ni une autorisation
commerciale des extraits. Les crédits exacts Sneaky Snitch accompagnent le kit
et sont inclus dans sa description complète.

## Reproduire la préparation et poursuivre après Landa

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
  --prepare --out output/conversation-chess/tommy-alfie-long-v3-master-reproduced
```

Le helper garde les dimensions natives, convertit seulement la cadence à 30 fps,
conserve les dialogues en PCM 48 kHz, ajoute des fondus de coupe de 20 ms et
des cartes silencieuses aux durées écrites. Il contrôle les images, les
échantillons audio, les timestamps et le décodage intégral avant d'écrire le
SHA réel du master et la timeline préparée. Aucun pitch, miroir, recadrage de
camouflage ou traitement pour tromper une détection n'est appliqué. Les parts
et le master occupent tous de l'espace : vérifier le stockage avant cette étape.

Après examen d'un nouveau master, préparer les graphismes dans un nouveau
dossier ; sa timeline candidate contient le fondu final :

```bash
node experiments/conversation-chess/render-clip.mjs --prepare-project \
  --source output/conversation-chess/tommy-alfie-long-v3-master-reproduced/source-master-1280x720-30fps.mkv \
  --timeline output/conversation-chess/tommy-alfie-long-v3-master-reproduced/timeline.json \
  --out output/conversation-chess/tommy-alfie-long-v3-native-reproduced/prepared
```

La correction ciblée déjà effectuée se reproduit dans un autre dossier neuf,
sans refaire les 23 animations et sans écraser les ressources initiales :

```bash
python experiments/conversation-chess/refresh-native-ending.py \
  --manifest output/conversation-chess/tommy-alfie-long-v3-native/prepared/project-manifest.json \
  --seconds 0.5 \
  --out output/conversation-chess/tommy-alfie-long-v3-native/prepared-ending-fade-reproduced
```

L’export terminé utilise son manifeste dérivé ; la commande conservée est :

```bash
bash experiments/conversation-chess/with-editor-display.sh \
  python experiments/conversation-chess/export-kdenlive.py \
  --manifest output/conversation-chess/tommy-alfie-long-v3-native/prepared-ending-fade/project-manifest.json \
  --bundle output/conversation-chess/tommy-alfie-long-v3-native/kdenlive \
  --subtitles experiments/conversation-chess/episodes/tommy-alfie-long-v3/captions.source.en.srt \
  --hardlink-media \
  --render /tmp/tommy-alfie-long-v3-native/Tommy-Alfie-V3-native.mp4
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
