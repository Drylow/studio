# Tony contre Richie — premier long livré, puis réclamé

**Archive : l'utilisateur a reçu une réclamation HBO sur l'épisode 8 après
l'import YouTube.** Il demande une version plus courte sans cet épisode.
Le nouveau montage de 9 min 27 est en préparation et devra être testé sur
YouTube ; les autres extraits HBO restent sans droits établis. Voir
[la réclamation et la décision de coupe](COPYRIGHT_REVIEW.md).

**Scene Analysis Guy : film et kit vérifiés sur [GoFile](https://gofile.io/d/mdNDwQQ4).**
L'envoi au salon Discord dédié est confirmé avec la miniature,
`Kit_publication.txt` et `MUSIC_CREDITS.txt`. Publication YouTube manuelle ;
le titre et la miniature sont des propositions, pas des choix déjà approuvés.

## Film terminé

- Neuf extraits de S2E3, S2E6 et S2E8, sept chapitres, 40 commentaires originaux,
  17 accents comiques. Anglais original et commentaires écrits, aucune voix off.
- **15 min 11 s** : 27 326 images à 30 fps, timeline de 910,866667 s.
  Export Kdenlive/MLT natif, 1920×1080, H264 `medium` CRF17, AAC192k stéréo 48k.
- Sources Naka natives **1280×720**, maximum proposé au compte pour ces épisodes.
  Aucun sous-titre ni filigrane ajouté visible sur les captures examinées.
  Le film et ses graphismes sont exportés en 1080p ; cela ne crée pas de détail 1080
  absent des sources. Les anciens clips compressés ne sont pas utilisés.
- Richie parle en premier : **Richie Blanc, Tony Noir**, camps fixes ; score
  positif Blanc. Barre fine à gauche, deux pions de même silhouette recolorés.
- Neuf catégories officielles actives ; Miss et Interesting exclus. Bilan final
  combiné : Brilliant 2, Great 3, Best 8, Excellent 2, Good 5, Inaccuracy 4,
  Mistake 8, Blunder 3, Book 5. Les scores sont éditoriaux, pas un calcul d'échecs.

Fichier : `Tony-vs-Richie-The-Jacket.mp4`, **600 210 017 octets**.
SHA256 : `c7e81eccb7061b719f9e6939237c6b24342d07db5f581e94b8abffd40c23d047`.
Titre recommandé : **Richie's Jacket Gambit Backfires | The Sopranos Analyzed Like Chess**.
Le kit contient aussi deux autres titres, la description avec dix chapitres,
les tags, un commentaire proposé et la miniature THE JACKET (PNG 1672×941).

## Contrôles réellement effectués

Décodage intégral A/V avec `-xerror` réussi, journal d'erreurs vide et nombre
d'images exact. Les 83 segments audio correspondent au mix préparé :
corrélation minimale 0,99906, décalage mesuré 0 ms. Les 40 débuts d'évaluation
correspondent chacun à un seul bruitage prévu ; les 40 fins de lecture sont
silencieuses. Pic échantillon −4,95 dBFS, pic estimé −4,9 dBFS, aucun écrêtage.

Images du **vrai MP4** examinées : les 40 analyses au commentaire complet,
les 164 captures avant/après les 82 frontières, trois images supplémentaires
du fondu d'outro, cinq d'intro, sept chapitres, trois d'outro et des gros plans
du premier locuteur et du bilan. Certaines captures se recoupent. Aucun défaut
bloquant observé. Il s'agit de contrôles d'images fixes, pas d'un visionnage
humain continu de toutes les images ni d'une écoute humaine complète.

Preuves privées : `output/conversation-chess/tony-richie-long-native/check/`
(`technical-qa.json`, contrôles audio, analyses, frontières et revue principale).
Reçus GoFile et Discord dans `publication/` du même dossier ; huit fichiers
uploadés, tailles/MD5/SHA vérifiés, aucun envoi incertain en attente.

## Musiques et limites

Intro : Sneaky Snitch ; outro : Scheming Weasel (faster version), Kevin MacLeod,
CC BY 4.0. Les crédits des deux morceaux sont dans la description et dans
`MUSIC_CREDITS.txt` : les conserver lors de la publication. Aucun crédit ajouté
en bas du tableau final. Les sons comiques/frappe gardent leurs provenances
documentées dans les assets ; les glyphes Chess.com restent propriétaires.

L'accès aux épisodes ne constitue pas une licence de republication.
Les contrôles de livraison n'incluaient pas Content ID. L'import ultérieur
par l'utilisateur a effectivement produit la réclamation S02E08 décrite en tête.
Ne pas garantir zéro réclamation à partir du seul contrôle technique ou du montage.
Le site et les automatisations Cage/Pitch/TikTok ne sont pas modifiés ici.

Pour reproduire le montage, utiliser [la source map](tony-richie-source-map.json),
[la timeline actuelle](tony-richie-long-timeline.json) et
[le contrat d'import](SOURCE_IMPORT.md). Les épisodes, fichiers de dialogue et
accès privés ne sont pas dans Git ; un autre ordinateur doit disposer des
sources autorisées. Chaque nouvel export exige ses propres contrôles et reçus.
