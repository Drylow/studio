# Vérification de Pixel Cuts — 7 octobre 2026

Livrable : `watermelon-pixelcuts.mp4`, 12 s, 1080 × 1920, 60 images/s, 720 images. SHA-256 : `ed9dfdd78d995cc006b2f409c2752570e2a1c252e07c038e318372dea0084777`.

## Contrôles réalisés

- Source : vidéo du tweet regardée en lecture et sur 53 captures, avec agrandissement des détails. Aucun extrait incorporé au livrable.
- Simulation : conservation du volume à chaque coupe, fragments fermés et non dégénérés, poses finies, rotations unitaires et pénétration du sol contrôlée. Les niveaux 1, 3 et 7 produisent 2, 8 et 32 fragments ; 387, 346 et 264 poses de physique ont été vérifiées.
- Exécution : contrôle HyperFrames avec navigateur à dix instants ; aucune erreur ni avertissement de structure, de mise en page ou d'exécution. Le texte est dessiné dans un canevas : le contrôle automatique de contraste DOM ne le mesure pas. La lisibilité des titres a été contrôlée visuellement.
- Style : scène entière sur une grille 216 × 384, agrandie ×5 sans lissage, palette de 19 couleurs, typographie bitmap sur la même grille. Tous les mots visibles sont en anglais : WATERMELON, 1 CUT, 3 CUTS, 7 CUTS.
- Mouvement et son : coups de lame de 0,145 s, espacés de 0,17 s, soit environ neuf images par coup à 60 images/s. Les onze accents sont centrés à 0,65 ; 4,65 / 4,82 / 4,99 ; 8,65 / 8,82 / 8,99 / 9,16 / 9,33 / 9,50 / 9,67 s. Pic audio du MP4 à −3,0 dBFS ; moyenne à −30,3 dBFS ; absence de saturation.
- Export final : capture par logiciel, 720 images, terminé en 1 min 57,8 s. Toutes les images ont été décodées sans erreur ; les douze planches ont été regardées, avec agrandissements des coupes, titres et fins de séquence. Les morceaux restent dans le cadre.
- Titres : un doute né des miniatures réduites a été levé par des images en pleine résolution et par un contrôle de présence des pixels des lettres sur les 720 images : couverture minimale de 100 %. La scène et le texte sont composés dans un tampon avant affichage. Le second export et les douze planches ont les mêmes empreintes que la version examinée.
- Lecture : MP4 lu jusqu'à la fin dans le navigateur, avec une piste AAC stéréo et sans erreur média.

Les captures et les rapports complets sont conservés localement dans `qa/pixelcuts/`, `snapshots/pixel-latest/` et `pixel-check-report.json`, exclus de Git. `python qa_frames.py watermelon-pixelcuts.mp4` reconstruit les douze planches et contrôle les titres.

## Limites

Fragments rigides et coupes planes : pas de chair souple, jus, déformation du fruit ni interaction physique avec la lame. Le fruit est maintenu en l'air pendant les passes ; la lame et la séparation initiale sont scénarisées, puis les collisions et la chute sont simulées. Les niveaux 13, 25 et 40 de la référence restent à concevoir et contrôler.
