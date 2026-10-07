# Vérification de Pixel Cuts — 7 octobre 2026

Version actuelle : 1 / 4 / 8 / 16 / 32 cuts, cadence ralentie, 14,65 s. Le niveau 64 est retiré selon le dernier retour utilisateur.

## Contrôles réalisés

- Source : vidéo du tweet regardée en lecture et sur 53 captures, avec agrandissement des détails. Aucun extrait incorporé au livrable.
- Simulation : `node verify-simulation.mjs` vérifie les cinq niveaux, la continuité des chapitres, 93 événements de coupe (32 dans le hook et 61 ensuite), l'ordre des frappes, la conservation du volume, les surfaces fermées, les poses finies et les rotations unitaires. Résultat : réussite.
- Niveaux 1 / 4 / 8 / 16 / 32 : 2 / 12 / 28 / 60 / 124 fragments. Physique à 120 Hz, respectivement 216 / 202 / 208 / 198 / 192 poses. Aucun sommet sous le sol ; limites détaillées dans `simulation-report.json`.
- Hook : 0 à 0,85 s ; 32 frappes espacées de 20 ms. Fruit maintenu en place, fissures accentuées, aucune libération des fragments. Cut direct vers la pastèque intacte du niveau 1.
- Chapitres : départs 0,85 / 2,85 / 5,15 / 7,85 / 10,95 s. Première frappe à +0,12 s. Salves des niveaux multiples réparties sur 0,42 / 0,77 / 1,25 / 1,90 s. Dernière salve trois fois plus longue que celle de 32 cuts du brouillon précédent.
- Lames : vitesse constante réduite, fenêtres de visibilité de 0,15 s, écho à 12 ms et opacité de 12 %. Dispersion et rotation initiales des morceaux réduites. Un accent sonore synthétisé pour chaque division géométrique.
- Style : grille 216 × 384 agrandie ×5 sans lissage, palette de 19 couleurs, titres bitmap sur la même grille. WATERMELON, PREVIEW, CUT et CUTS ; texte exclusivement anglais.
- HyperFrames : contrôle strict à 13 instants, dont les limites du hook et des cinq chapitres. Aucune erreur ni avertissement de structure, d'exécution ou de mise en page. Le contraste DOM ne mesure pas les titres du canevas ; ils sont examinés visuellement.
- Huit captures du montage révisé regardées dans `snapshots/pixel-32-final/`. Preview ouverte dans le navigateur Codex sur le port 3019 ; lecture lancée et arrivée en fin de timeline constatée. Le titre 32 CUTS et la durée 14,65 s sont chargés dans l'éditeur.

## Export

Livrable : `watermelon-pixelcuts-32.mp4`, 14,65 s, 1080 × 1920, 60 images/s, 879 images, 11,3 Mo. SHA-256 : `4340da6fb14417b983a96bf50c51406254d6b4ece3e03a804b9b1a75035cdac4`.

- Rendu logiciel terminé en 4 min 18,3 s, dont 4 min 15,3 s de capture. H.264 High, YUV420p, BT.709 ; AAC LC stéréo à 48 kHz.
- Toutes les 879 images décodées sans erreur, puis regardées sur quinze planches numérotées couvrant les images 0 à 878. Hook coupé avant toute chute, cinq niveaux uniquement, lames espacées, morceaux dans le cadre, titres anglais et style pixel art conservés.
- Contrôle de présence des pixels des titres sur chaque image : couverture minimale de 100 %. Le tampon du canevas est publié après composition de la scène et de toutes les lettres.
- Audio décodé jusqu'à la fin : pic mesuré du MP4 à −1,7 dBFS, moyenne à −22,0 dBFS, sans saturation. Mixage réduit de 1,3 dB par HyperFrames pour respecter sa limite de −1 dBTP. Les 93 accents sont alignés sur les événements de découpe.

Planches et rapport local : `qa/pixelcuts-32/`. Huit captures de la composition : `snapshots/pixel-32-final/`. Contrôle strict : `pixel-check-report.json`. Fichiers générés exclus de Git. `python qa_frames.py watermelon-pixelcuts-32.mp4` reconstruit le contrôle et les quinze planches. La lecture de la composition dans Studio a été constatée ; aucune lecture complète du MP4 dans le navigateur n'est revendiquée.

## Limites

Fragments rigides et coupes planes : pas de chair souple, jus ni déformation du fruit. Lames et séparation initiale scénarisées ; chute et collisions contre la planche et le sol simulées. Contacts entre fragments actifs pour 1 et 4 cuts ; désactivés pour 8 à 32, avec une dispersion initiale modérée pour stabiliser les lamelles fines. Le teaser ne déclenche pas la chute.
