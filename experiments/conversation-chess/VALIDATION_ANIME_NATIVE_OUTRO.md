# Lelouch / Schneizel — miniature B et bilan natif restauré

Vérification du 9 octobre 2026. La miniature B choisie par l'utilisateur reçoit les SVG originaux Chess.com. L'épisode rétablit Sneaky Snitch sous le guide et le bilan natif de douze secondes du collègue, sans carton Subscribe. La validation V4 reste conservée comme archive.

## Export vérifié

- Fichier local : `work/conversation-chess/lelouch-full-v6/kdenlive/APERCU-LELOUCH-SCHNEIZEL.mp4`.
- Durée image : 255 secondes, soit 4 min 15 ; 7 650 images à 30 i/s. Conteneur : 255,018 secondes, avec remplissage AAC.
- Taille : 124 726 567 octets. SHA-256 : `32f703b68b0670edba6f26f6d9b738448adf0d56c912ed3332359f6575383a57`.
- Pipeline complète `chess.ps1 -Mode Render -Preview`, projet natif Kdenlive/MLT, six pistes et 39 ressources locales présentes. Export 1920 × 1080, H.264 CRF 17 medium et AAC 192 kbit/s, stéréo 48 kHz.
- La source anglaise reste 1280 × 720. Cet export est un aperçu de qualité source ; le verrou `accepted_for_final: false` reste actif. La taille d'export ne restaure pas les détails manquants de la source.

## Montage et son

Guide de 16 secondes, source continue 0–192 secondes, cinq analyses de 7 secondes et bilan de 12 secondes. La pause après « opinion » reste à 15,45 secondes source, soit 0,61 seconde après la fin du mot alignée à 14,84. La réponse finale « Understood » se termine à 191,34 ; le fondu image et son commence à 191,5 et finit à 192,0, avant la phrase suivante.

Le bilan utilise le pion neutre, le résumé propre à la scène et les comptes des cinq moves : trois pour Lelouch, deux pour Schneizel. Aucun portrait Tony, Subscribe ou crédit à l'écran. Les captures montrent le résumé entier et les icônes originales, sans texte coupé.

Sneaky Snitch est rétabli à l'identique de V2, guide seul, gain 0,65 et départ à 66,104 secondes dans le morceau. Sa piste préparée est identique octet par octet à V2. La piste graphique du bilan est également identique à V2. Les 44 ressources image, dialogue et SFX du corps de vidéo sont inchangées par rapport à V4 : SHA-256 des fichiers, ou hash du flux H.264 pour les MKV dont le conteneur peut varier.

Aucune musique ajoutée aux scènes, aux analyses ou au bilan. La musique déjà intégrée au clip reste avec le dialogue original. Le fichier local `MUSIC_CREDITS.txt` conserve l'attribution CC BY 4.0 de Kevin MacLeod pour la description. Mesures du MP4 : −23,05 LUFS intégrés, −2,31 dBTP et LRA 15,80. Aucune normalisation supplémentaire appliquée.

## Revue réellement effectuée

- Décodage image et audio complet du MP4 sans erreur.
- Les 7 650 images sont représentées sans saut dans 39 planches, toutes regardées. Cette revue temporelle utilise des vignettes 160 × 90 ; elle n'est pas une inspection de chaque pixel natif.
- Les 27 captures à résolution native ont toutes été regardées en cinq planches, puis le bilan à 244 secondes a été regardé séparément en pleine taille : guide, raccord de « opinion », cinq commentaires complets, fondu final et bilan. Aucun trou noir inattendu ou calque cassé observé.
- Les cinq analyses offrent respectivement 3,04 / 3,20 / 3,34 / 3,08 / 3,18 secondes de lecture silencieuse après leurs SFX, avec pics PCM nuls.
- Audio du MP4 entre 243,3 et 254,9 secondes : pic PCM nul, donc bilan effectivement silencieux après le raccord AAC.
- Validation de la timeline en mode aperçu, syntaxe du nouveau renderer de miniature et empreinte/taille du MP4 vérifiées.

Les preuves locales sont dans `work/conversation-chess/lelouch-full-v6/review/` : couverture, planches, captures, mesures audio, comparaison des médias préparés et reçu de livraison. Le projet éditable est `kdenlive/project.kdenlive`. L'instruction de revue conservée dans le JSON de production est satisfaite par cette revue de l'export complet.

## Miniature B

Livraison : `thumbnails/lelouch-schneizel/B-chesscom.jpg`, 1 672 × 941, 390 238 octets. SHA-256 : `4f6c7c082691593ac76206c9421bc0ce6bda1cdc75188abe81839612d1189e39`.

Le renderer `render-thumbnail.mjs` pose directement les SVG Brilliant à gauche pour Lelouch et Blunder à droite pour Schneizel. Les empreintes correspondent à `ratings.json` et la provenance reste documentée dans `assets/chesscom/sources.json`. Le nettoyage des anciennes pastilles reprend uniquement les deux coins ; avant l'encodage JPEG, aucune différence de pixel n'existe ailleurs. Le PNG maître sans perte et les premières propositions sont conservés.

La B corrigée a été regardée en pleine taille et à 320 pixels de large : personnages et symboles lisibles, sans fragments des anciennes pastilles ni raccord visible. Aucune publication YouTube ou transmission externe de la vidéo n'est déclenchée.
