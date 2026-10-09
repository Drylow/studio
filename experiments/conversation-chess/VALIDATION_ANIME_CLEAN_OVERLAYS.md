# Lelouch vs Schneizel — contrôle des overlays V7

Le bandeau « SOURCE QUALITY PREVIEW · 720p source » provenait du montage,
pas du clip. Il est désactivé pour cet épisode, sans recadrage ni masque
sur la source. Les informations de résolution restent dans le manifeste.

Les analyses utilisent maintenant le pion du camp évalué : noir pour les
deux analyses de Schneizel, blanc pour les trois analyses de Lelouch.
Le récapitulatif conserve le commentateur neutre du montage natif.
Les autres épisodes conservent leur comportement par défaut.

## Export vérifié

- Fichier local : `work/conversation-chess/lelouch-full-v7/kdenlive/APERCU-LELOUCH-SCHNEIZEL.mp4`.
- Durée image : 255 secondes, 7 650 images à 30 fps, export 1920 × 1080.
- Taille : 122 831 308 octets.
- SHA256 : `a31200b5d1abf82c46e7dd3dcc9d4fe882210c6369dd6f0ee6979b6420a1f340`.
- Source native : 1280 × 720. Le passage à un export 1080p ne crée pas de détail source supplémentaire ; `accepted_for_final` reste faux.
- Export par le montage Kdenlive/MLT natif : H.264 CRF 17, AAC stéréo 192 kb/s.

## Contrôles effectués

- Décodage intégral image et audio sans erreur.
- Revue visuelle des 39 planches couvrant toutes les images sans saut,
  en vignettes 160 × 90 : absence du bandeau jaune, continuité des scènes,
  entrées et sorties des analyses, fondus du récapitulatif.
- Revue des 27 captures natives réunies en cinq planches ; contrôles
  supplémentaires en 1920 × 1080 aux secondes 18, 131,650, 174,700,
  207,700 et 244 : couleurs des pions, texte lisible et non coupé,
  absence du bandeau.
- Vérification des cinq overlays préparés : deux pions noirs et trois blancs.
- 23 fichiers source, replay et audio identiques à la V6 ; graphismes
  d'introduction et de récapitulatif identiques. Aucun changement des coupes,
  du dialogue, de la musique d'introduction ou des durées.
- Mesures audio : −23,05 LUFS intégrés, −2,31 dBTP, LRA 15,80 LU.
  Pas de normalisation supplémentaire. Silence vérifié sur la fin de lecture
  des analyses et le récapitulatif (243,3 à 254,9 secondes).
- Quatre tests du runtime réussis, dont couleur réelle des pixels des pions,
  affichage optionnel du bandeau et maintien du contrôle de résolution.

Les planches couvrent la temporalité complète à résolution réduite ; cette
revue n'est pas un contrôle pixel par pixel de chaque image native.
Les preuves locales sont dans le dossier `review` de l'export V7.
