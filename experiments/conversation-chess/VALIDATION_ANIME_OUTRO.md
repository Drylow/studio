# Lelouch / Schneizel — guide discret et sortie courte

Vérification du 9 octobre 2026. Cette version remplace le bilan final de douze secondes par un fondu de 0,5 seconde suivi de deux secondes de texte blanc « Subscribe » sur fond noir. Le projet et les anciens aperçus sont conservés.

## Résultat vérifié

- Fichier : `work/conversation-chess/lelouch-full-v4/kdenlive/APERCU-LELOUCH-SCHNEIZEL.mp4`.
- Durée image : 245 secondes, soit 4 min 05 ; 7 350 images à 30 i/s, export 1920 × 1080. Le conteneur dure 245,013 secondes à cause du remplissage AAC.
- Taille : 122 324 196 octets. SHA-256 : `60ec637d3ec42e0a8a675802c41cbb2ca46d57a0bec7557cd4474887c5edb1ae`.
- Export natif Kdenlive / MLT : H.264 CRF 17, preset medium, AAC 192 kbit/s, stéréo 48 kHz. Six pistes séparées et 39 ressources locales distinctes présentes.
- Source anglaise 1280 × 720 conservée : cet export reste un aperçu de qualité source, pas une validation de source native 1080p. Le marquage et le verrou de qualité restent actifs.

## Montage et son

Guide de 16 secondes, scène source continue de 0 à 192 secondes, cinq analyses de 7 secondes, sortie de 2 secondes. La correction du mot « opinion » et le pion neutre sont conservés. Les graphiques, dialogues et sons des analyses précédant la dernière portion source sont inchangés : 21 fichiers intermédiaires identiques à la version V2.

La dernière réponse « Understood » finit à 191,34 secondes dans l'alignement local. Le fondu commence à 191,5 et finit à 192,0, avant le « However » suivant à 192,06. Le dialogue préparé reste identique à V2 jusqu'à 191,48 secondes source. L'image, la barre, les mentions et le son original s'effacent ensemble.

La musique ajoutée est « Echoes » d'Andrew Ev, uniquement sous le guide, gain 0,12 avec fondus. Aucune musique ajoutée sous les scènes, les analyses ou le Subscribe. La musique et les dialogues intégrés au clip restent ensemble sur la piste originale. Niveau du lit musical préparé : moyenne −42,5 dB, pic −29,6 dB. Mesures du MP4 final : −23,31 LUFS intégrés, −2,31 dBTP, LRA 17,60.

La [licence Mixkit Stock Music Free](https://mixkit.co/license/#musicFree), vérifiée avec le [catalogue officiel](https://mixkit.co/free-stock-music/), permet cet usage sans attribution. Le fichier `MUSIC_LICENSES.json` conserve les preuves dans le dossier de travail ; aucun crédit n'est ajouté à l'écran ou imposé à la description. Le MP3 original reste ignoré par Git et se récupère avec `python fetch-music.py echoes`. Les obligations des anciens morceaux CC BY restent intactes.

## Contrôles réalisés

- Décodage complet image et audio du MP4 sans erreur.
- Toutes les 7 350 images représentées sans saut dans 37 planches, toutes regardées. C'est une revue temporelle à résolution réduite, pas une inspection de chaque pixel natif.
- 25 captures du MP4 à sa résolution native, regardées en cinq planches : guide, raccord de « opinion », cinq commentaires, fondu final et Subscribe. Textes complets lisibles et aucun portrait Tony.
- Début du carton à 243 secondes entièrement noir. Audio du Subscribe entre 243,3 et 244,9 secondes : pic PCM nul, donc silence effectif après le raccord AAC.
- Après la frappe du texte, chacune des cinq analyses offre plus de trois secondes de lecture sans son de frappe résiduel ; pics PCM nuls.
- Trois tests de runtime passent. Syntaxes JS et Python vérifiées. Régressions des licences vérifiées pour musique sans crédit, CC BY, mélange des deux et empreinte inconnue refusée.
- Empreinte et taille du MP4 final vérifiées contre le manifeste d'export.

Les preuves locales sont dans `work/conversation-chess/lelouch-full-v4/review/` et le projet éditable dans `kdenlive/project.kdenlive`. Cette livraison n'effectue aucune mise en ligne.
