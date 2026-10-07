# Vérification du prototype livré — 7 octobre 2026

Livrable local : `watermelon-lowpoly.mp4`, 1080 × 1920, 30 images/s, 540 images. La vidéo dure 18 s ; le conteneur avec l'audio AAC dure 18,005 s. SHA-256 : `5aea99c0c96c0f3e98a4eb09224fc9190f9b44550332c9b0f83ed8cedeb0018a`.

## Contrôles réalisés

- Source : vidéo du tweet regardée en lecture et sur 53 captures, avec agrandissement des détails. La source n'est pas incorporée au livrable.
- Simulation : conservation du volume à chaque coupe, fragments fermés et non dégénérés, poses finies, rotations unitaires et contrôle de pénétration du sol. Les trois passes produisent 2, 8 et 32 fragments.
- HyperFrames : contrôle de structure, d'exécution, de mise en page et de contraste, avec navigateur, à dix instants ; aucun avertissement ni erreur. Timeline GSAP de 18 s enregistrée et en pause pour le rendu.
- Export : capture WebGL par logiciel, 540 images, terminée en 8 min 30,8 s. Le premier essai avec GPU a dépassé le délai de capture ; aucun MP4 issu de cet essai n'est livré.
- Inspection visuelle : les neuf planches de 60 images ont toutes été regardées, ainsi que des agrandissements de la coupe et des fins de séquence. Cadrage, titre, bordure d'écorce, chair, pépins et surfaces coupées restent cohérents dans ce prototype. Les morceaux peuvent sortir de la planche, mais restent dans le cadre.
- MP4 final : décodage de toutes les images sans erreur, présence d'une piste AAC stéréo, lecture dans le navigateur jusqu'à la fin sans erreur média. Bruitages relevés de ×3,2 après le premier export, puis nouveau contrôle du MP4 ; pic mesuré à −7,3 dBFS, moyenne à −28,9 dBFS. La même amplification est conservée dans `sound.py` pour les prochaines constructions. L'image a été copiée sans réencodage pendant cette correction audio.

Les captures et les rapports complets sont conservés localement dans `qa/`, `snapshots/` et `check-report.json`, exclus de Git. `python qa_frames.py` reconstruit les neuf planches depuis le MP4.

## Limites observées

Il s'agit de fragments rigides et de coupes planes. Pas de chair souple, jus, déformation du fruit ni interaction physique avec la lame. Le fruit est maintenu en l'air pendant les passes ; la lame et la séparation initiale sont scénarisées, puis les collisions et la chute sont simulées. Le prototype reprend les niveaux 1, 3 et 7 ; les niveaux 13, 25 et 40 de la référence restent à concevoir et contrôler.
