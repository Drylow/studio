# Vérification de Pixel Cuts — 7 octobre 2026

Version actuelle : chef et trois outils, 41,80 s. Arrivée normale du fruit, puis
machette 1 / 4 / 8 / 16 / 32, scie 1 / 4 / 8 et pistolet 1 / 4 / 8.
Aucun hook, teaser ni texte PREVIEW. Musique reportée.

## Composition et simulation

- Référence : vidéo du tweet regardée en lecture et sur 53 captures avant réalisation ; aucun extrait incorporé.
- `node verify-simulation.mjs` : réussite pour onze chapitres. Continuité, ordre des frappes, volumes conservés, solides fermés, poses finies, rotations unitaires et tolérance de sol vérifiés. L'intro garde un seul fruit intact et zéro événement de coupe.
- Machette : 2 / 12 / 28 / 60 / 124 fragments, 216 / 202 / 208 / 198 / 192 poses. Scie : 2 / 12 / 28 fragments, 280 / 166 / 154 poses. Pistolet : 18 / 40 / 100 fragments, 350 / 259 / 439 poses. Échantillonnage à 120 Hz ; intégration à 240 Hz pour les tirs. Chute finale poursuivie pendant la fin avec la spatule.
- Arrivée : fruit porté en 0,72 s, retrait de la main entre 0,76 et 1,05 s. Paume horizontale dédiée, centrée sous le fruit ; sa face supérieure et le point le plus bas du melon sont tous deux à y=1,00, sans écart. Main et fruit partagent le même déplacement jusqu'au retrait. Manche blanche reliée au poignet. Quatre captures à 0,30 / 0,55 / 0,72 / 0,82 s dans `snapshots/palm-support/`, dont les vues 0,55 et 0,72 s regardées en pleine taille.
- 1 CUT affiché dès l'arrivée ; première vraie coupe à 1,22 s. Chapitres machette à 1,10 / 3,10 / 5,40 / 8,10 / 11,20 s ; salves multiples sur 0,42 / 0,77 / 1,25 / 1,90 s. Lames lancées à vitesse constante, visibles 0,15 s. Les quatre captures de `snapshots/no-hook/` ont été regardées : arrivée intacte, 1 CUT, première lame, puis 4 CUTS.
- Scie : départs 14,90 / 18,30 / 23,00 s. Grand disque à 32 dents, rayon maximal 2,48. Entrée continue depuis le haut droit, alignement sur le plan de coupe, arc entre passes et sortie continue. Intervalles de 0,75 s pour quatre passes, 0,65 s pour huit.
- Pistolet : départs 29,90 / 33,70 / 36,90 s. Rafales de quatre tirs sur 0,36 s et huit sur 0,56 s, intervalles de 120 puis 80 ms. Recul de moins de 0,1 s, traceur d'une image, flash chaud discret d'environ 52 ms, blessures visibles et éclats dirigés. Fractures obliques à positions inégales, ouverture progressive, projection et rotation renforcées. Recul et recentrage de caméra pour contenir les débris.
- Mouvement : sampler et profil rig du composant camera-shake du catalogue adaptés à la caméra 3D avant la conversion en palette ; titres fixes. Carte d'animation sur 41,8 s dans `qa/animation-map/` : un seul pilote onUpdate, indicateur paced-slow. Cet indicateur décrit l'horloge et ne mesure pas les trajectoires 3D ; les cadences réelles figurent ci-dessus et dans les données simulées.
- Style : grille 216 × 384 agrandie ×5 sans lissage, palette de 23 couleurs, titres bitmap et icônes sur la même grille. Texte exclusivement anglais. Détails de palette et zones de sécurité dans `design.md`.

## Bruitages et contrôle technique

- 74 accents de coupe, 13 tirs, 1 160 collisions regroupées en 180 accents discrets. Bruitages du tir et de la scie générés via Replicate, puis figés en fichiers locaux avec prompt, identifiant de génération, empreinte et lien des conditions dans `assets/sfx-*.json`. Aucun appel externe dans le build.
- Tir : source réduite à 120 ms, mono 48 kHz, filtrage à 7,2 kHz, attaque de 1 ms et relâchement de 20 ms, puis gain de 0,62 dans le mix. Moteur de scie avec entrée progressive et accents au passage. Gain maître linéaire 1,314656 ; pic WAV 0,78, zéro échantillon écrêté. Sans saturateur, sans musique.
- HyperFrames 0.8.140 : contrôle strict final sur GPU matériel à 0,55 / 31,05 / 34,90 / 38,35 / 40,58 / 41,18 s, réussi avec zéro erreur et zéro avertissement. `three-levels-check-report.json`. Le contraste DOM ne mesure pas les titres du canevas ; ils sont examinés visuellement.
- Preview rechargée dans Codex sur le port 3019, durée 41,8 s et MACHETE — 1 CUT constatés. Les pages HTML de contrôle sont conservées sous extension .html.txt afin de ne pas être indexées comme compositions. FPS réel de Studio non mesuré ; aucune promesse de 60 FPS dans le navigateur.
- Logo existant : `brand/chef-spatula-avatar.png`, chef pixel art avec spatule, déjà regardé après modification.

## Dernière révision : éclats irréguliers et célébration

- Fractures déterministes obliques, divisions à positions inégales : 18 / 40 / 100 solides. Volume conservé ; rapports de volumes max/min de 17,73 / 6,56 / 12,16 ; surfaces internes non alignées sur une grille, vérifiés par `verify-simulation.mjs`. Petits débris de tir tétraédriques. Garde de contact par points de support pour prévenir la traversée du sol par les éclats rapides.
- Célébration : deux gerbes de quatorze particules à +0,06 et +0,72 s ; palette existante, petites étoiles et confettis bitmap. Ancre projetée depuis la main et la spatule, léger saut de 0,22 unité. Sampler adapté du composant confetti du catalogue, sans sa carte de démonstration.
- Captures finales 38,65 / 40,58 / 41,18 s regardées. Les morceaux ont des silhouettes anguleuses inégales ; les particules sont visibles autour de la spatule sans masquer les titres.

## Export

MP4 terminé : 41,800 s, 1080 × 1920, 60 images/s, 2 508 images ; H.264 High,
YUV420p / BT.709, AAC LC stéréo 48 kHz. Taille : 36 612 741 octets.
SHA-256 : `a822dd6c6db65e4b5209fe4ee3783579da670752de072c392809da263ffaba15`.

Rendu par captures avec GPU logiciel et deux workers : 7 min 4,4 s au total,
dont 5 min 44,5 s de capture, 1 min 14,1 s d'encodage et 1,9 s d'assemblage.
Les 2 508 images ont été décodées et regardées dans 42 planches ; la dernière
contient 48 images. Pas d'image noire ni de canevas incomplet constaté.
Les titres couvrent 100 % des images. Arrivée sur la paume, départ à 1 CUT,
entrée continue de la grande scie, fragments irréguliers et célébration finale
confirmés dans cet export. Rapport : `qa/watermelon-chef-three-levels/media-report.json`.

Audio AAC décodé : pic −3,4 dBFS, moyenne −31,3 dBFS, sans écrêtage mesuré.
Reproduction du contrôle : `python qa_frames.py watermelon-chef-three-levels.mp4`.

## Limites

Fragments rigides : pas de chair souple ni simulation de jus. Lames, flash,
marques et petits éclats scénarisés ; chute et collisions contre planche et sol
simulées. Contacts entre fragments désactivés pour les divisions denses et
les tirs. Les mesures audio vérifient l'absence d'écrêtage ; elles ne remplacent
pas une écoute humaine du caractère satisfaisant.
