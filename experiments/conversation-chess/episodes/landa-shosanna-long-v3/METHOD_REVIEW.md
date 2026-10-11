# Relecture indépendante du procédé V3

Audit documentaire du 11 octobre 2026 : [TXT transmis](../../PROCEDE-V3-A-TRANSMETTRE.txt), décisions de coupe, timelines, manifests préparés et reçus. Aucun montage ni média modifié par cet audit. **Les sections jusqu’aux preuves décrivent l’état historique avant les exports finaux.** Le suivi en fin de document distingue les contrôles terminés depuis et ceux encore absents.

Le TXT expose **un résultat Death Note rapporté**, non vérifié directement dans le compte YouTube. Il ne démontre ni sa cause ni une efficacité générale.

## Appliqué

- Coupes justifiées par écrit, chronologie et omissions explicites, commentaires adaptés aux passages retenus ; aucune reconnaissance de Shosanna inventée.
- Timelines et coupes séparées, remapping à 30 fps, captions recalées après les pauses. Masters intermédiaires liés à leurs SHA, décodage complet et horloges image/PCM vérifiés : 15 028 images pour Landa, 18 752 pour Peaky.
- Blancs documentés en ouverture. Landa reste Blanc et son adversaire Noir change au restaurant ; Tommy/Alfie conservent leurs camps dans les trois actes.
- Outil conversation-chess/scene.js, puis Kdenlive/MLT : graphismes natifs, barre gauche, bulles, SFX et bilan. Replays muets, dialogues originaux conservés, aucune voix off ni Subscribe.
- Sneaky Snitch uniquement dans le guide ; crédits CC BY 4.0 générés. Pas de musique ajoutée sur les dialogues/analyses, ni de miroir, pitch ou camouflage documenté. Fondus courts et horloges servent la synchronisation.

## Adapté, avec différences mesurables

Les plages ci-dessous précèdent les interruptions d’analyse ; elles ne désignent pas les petits segments supplémentaires créés par les pauses.

| Mesure | Death Note du TXT | Landa long | Peaky long |
| --- | ---: | ---: | ---: |
| Plages retenues | 13 | 27 : 16 ferme + 11 restaurant | 22, trois épisodes |
| Durée d’une plage | 2,27–13,8 s | 3,6–173,467 s | 3,6–95,9 s |
| Scène avec son | 105,6 s | 500,933 s | 603,667 s |
| Analyses | 7 × 7 s | 30 × 9 s | 23 × 7 s |
| Film final | 182,6 s rapportées | 798,933 s attendues | 814,067 s attendues |

**La réduction très forte de Death Note n’est pas reproduite quantitativement.** Le TXT impose une sélection éditoriale, sans quota d’extraits ni seuil autorisant leur usage. Les adaptations répondent aux dix à quinze minutes demandées ; elles ne présument pas le même résultat YouTube. Les replays prolongent encore l’affichage d’images protégées.

Guide/bilan restent 16/12 secondes. Landa utilise des sources 1080p ou 4K ramenée en 1080p ; Peaky conserve ses originaux 720p, graphismes 1080p. Les dialogues deviennent multilingues pour Landa, anglais pour Peaky, sous-titres anglais. Les pions photographiques approuvés remplacent le pion neutre de l’exemple. Le preset final demandé reste H264 CRF17 medium/AAC192/48 kHz ; il devra être confirmé sur les exports. L’intermédiaire Peaky emploie `veryfast`, plutôt que `superfast`.

Le +6 dB de Death Note n’est pas copié : Landa prépare −2 dB de dialogue. Peaky mesure −26 LUFS/−5,9 dBFS de crête vraie sur le master et propose +4 dB, **encore non appliqués**. Le mix final reste à mesurer.

## Facteurs non repris ou non démontrés

- **Scène entière et raccords à l’écoute** : progression écrite, ASR, VTT, signaux et captures existent ; aucune lecture audiovisuelle intégrale ni écoute humaine n’est attestée. Ces mesures ne prouvent pas la fluidité audible. Peaky signale notamment « Really? » près d’une pause et une réaction d’Ollie à revoir en mouvement.
- **Fondu final de 0,5 s** : présent dans la timeline Landa et son dernier segment préparé ; absent de la timeline Peaky préparée, dont le dernier segment indique `fade_out_seconds: 0`. À régler ou justifier avant export, après vérification du dernier mot utile. Ce rapport ne le modifie pas.
- **Droits** : provenance tracée, mais aucun droit commercial aux extraits établi. Accès public, commentaires et durée ne constituent pas une autorisation.

## Contrôles encore en cours ou non effectués

Le bundle Kdenlive Landa existe avec `export_completed: false` ; Peaky dispose de pistes préparées sans export final approuvé. Restent la QA du MP4 fermé — décodage, durée/images, mix, captions, textes, camps, bilan — et l’examen des raccords. Les préflights sources/graphiques ne remplacent pas ces contrôles.

La couverture de toutes les images décrite pour Death Note, la lecture intégrale, l’écoute humaine des raccords ou intégrale, les Checks YouTube et la livraison des projets éditables avec médias ne sont pas déclarés faits. Conserver un reçu lié au MP4 final, puis un résultat YouTube séparé, exact, daté et sourcé. Statut **`youtube-test`**, sans garantie d’absence de claim, de disponibilité territoriale ou de monétisation.

Preuves : edits ferme/restaurant et README des deux épisodes ; `output/conversation-chess/landa-shosanna-long-v3-combined/{timeline.json,assembly-receipt.json}` ; `/tmp/landa-shosanna-long-v3-native/prepared/project-manifest.json` et bundle Kdenlive ; manifests master/préparé et mesure audio sous `output/conversation-chess/tommy-alfie-long-v3-*`.

## Suivi après cet audit

L’export natif Landa s’est terminé : 23 968 images à 30 fps, soit
798,933333 s ; SHA256
`42dcf2c2ced45ea1325b5986ec319923c682368ce9932ae90f3714d568225077`.
La QA technique du fichier fermé passe : décodage audiovisuel intégral sans
erreur, nombre exact d’échantillons et crête vraie du mix à −3,2 dBTP.
La revue visuelle finale porte sur 172 captures distinctes réparties sur
24 planches : 130 raccords, 30 analyses, 5 états du guide, 3 états du bilan et
4 sous-titres longs. Les camps, le retour du score à 0,0 au restaurant et le
total de 30 notes au bilan sont confirmés sur ces captures. Les reçus sont dans
`output/conversation-chess/landa-shosanna-long-v3-native/qa/`, notamment
`delivery-review.json` et les deux revues composantes. Il s’agit d’un examen
échantillonné, sans lecture continue ni écoute humaine.

Le film et quatre fichiers de publication ont été envoyés sur
[GoFile](https://gofile.io/d/JEZfRO10) ; leur présence est confirmée par la page
publique officielle et leur réconciliation stricte est passée. Les cinq
fichiers sont liés au manifeste, le pending archivé et l’envoi Discord confirmé
par un reçu distinct : un message et trois pièces jointes. Aucun Checks YouTube,
publication YouTube ni droit commercial aux extraits n’est attesté.

Le fondu Peaky absent lors de l’audit a été corrigé avant son export.
`refresh-native-ending.py` crée une timeline et un manifest dérivés, sans
écraser les préparations précédentes, puis régénère les trois ressources
affectées. Les 146 médias précédents gardent leur SHA ; les nouveaux fichiers
comptent 18 images et 28 800 échantillons par canal. Le fondu de 0,5 s commence
après le dernier mot reconnu et le dernier cue. Le PCM mesuré est une ambiance
faible (−43,15 dBFS RMS), pas du silence numérique ; aucune écoute humaine
n’est revendiquée. Les frames composites 3, 10 et 17 ont été vues : scène et
barre s’assombrissent ensemble. Le rapport public
`../tommy-alfie-long-v3/ending-dialogue-evidence.json` et le reçu local
`prepared-ending-fade/ending-refresh-receipt.json` conservent cette portée.
L’export natif Peaky utilise ce nouveau manifest et s’est terminé à
814,066667 s, soit 13:34,067. Sa finition applique ensuite +4 dB uniquement
aux dialogues source, avec flux image inchangé et décodage intégral réussi.
Le reçu `Tommy-Alfie-V3-finished.audio.json` lie cet enfant au parent natif :
SHA256 final `e421b73ec7cc0a421f336a2c170fd5ff5955c5e043976c5cd5849e5b654a6c8b`,
crête vraie −2,1 dBTP, loudness intégrée −22,2 LUFS. La QA technique finale
de cet enfant passe également, avec décodage audiovisuel complet et sans
échec ni avertissement. La revue finale porte désormais sur 140 captures
distinctes réparties sur 22 planches : 96 raccords, 7 cartes de chapitre,
6 sous-titres longs, 23 analyses, 5 états du guide et 3 états du bilan. Le reçu
`qa/delivery-review.json` atteste cette revue échantillonnée liée au SHA final,
sans lecture continue ni écoute humaine. Le film Peaky est contrôlé pour sa
livraison. Son kit [GoFile](https://gofile.io/d/uCNnoRLc) est maintenant confirmé
sur le site officiel et réconcilié : cinq fichiers, avec reçu lié au manifeste.
L’envoi Discord est également confirmé, un message et trois pièces jointes,
par un reçu distinct. Les deux films restent des candidats livrés
`youtube-test`, sans contrôle privé YouTube effectué ni garantie de droits.
