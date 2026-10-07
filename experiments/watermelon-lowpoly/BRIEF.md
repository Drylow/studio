---
workflow: general-video
flow: automation
storyboard: no
message: "Reproduire par le code les découpes de pastèque du tweet, avec un style pixel art sur toute la vidéo, des coupes rapides et des bruitages satisfaisants."
aspect: portrait
language: en
length: 14.65
---

## Intent
Demande du 7 octobre 2026 : regarder la vidéo du tweet ErnestoSOFTWARE/2107832530770829559 et produire un essai comparable, éventuellement low-poly et entièrement réalisé en code. La demande autorise la fabrication et le rendu de cet essai.

## Source
Vidéo consultée dans le navigateur : 26,517 s, montage promotionnel partagé en deux. À gauche : pastèque suspendue, compteur de coupes, lames horizontales, fragments qui tombent sur une planche. À droite : statistiques et galerie de simulations. Les chiffres de vues sont des affirmations de l'auteur et ne constituent aucune garantie.

## Decisions
Dernier retour du 7 octobre : limiter à 32 cuts et ralentir. Version de 14,65 s, 1080 × 1920, 60 images/s. Hook de 0,85 s : salve de 32 couteaux, fruit entaillé maintenu en place, cut avant libération des fragments. Cut direct vers 1 CUT, puis 4 / 8 / 16 / 32 CUTS. Chapitres de 2 / 2,3 / 2,7 / 3,1 / 3,7 s. Première frappe 0,12 s après chaque cut ; séries réparties sur 0,42 / 0,77 / 1,25 / 1,90 s. Lames projetées à vitesse constante, visibles 0,15 s, avec un écho plus discret. Chaque passe ajoute une vraie division géométrique. Preview web ouverte avant export pour permettre la revue du rythme.

Toute l'image, titres inclus, est dessinée sur une grille 216 × 384 et agrandie sans lissage. Palette limitée à 19 couleurs, tramage discret et alphabet bitmap original. Tous les mots visibles sont en anglais : WATERMELON, PREVIEW, CUT, CUTS. Même pastèque, planche et éclairage pour les cinq niveaux. Scène Three.js, découpes géométriques et corps rigides calculés hors ligne puis figés. Aucun changement au frontend du studio.

## Audio
Chaque coupe a un souffle bref, un claquement net synchronisé à la coupe géométrique et une résonance courte. Impacts synthétisés depuis les collisions, plus discrets que les coups de lame. Pas de voix ni musique. Limiteur doux à gain fixe pour conserver l'impact de la coupe unique malgré les salves denses.

## Limitations
Prototype de corps rigides : pas de simulation de chair molle ou de jus. Les coups sont scénarisés ; les collisions des fragments sont simulées. Géométrie low-poly, rendu final pixel art.

Les contacts entre fragments sont actifs pour 1 et 4 cuts. Les salves de 8 à 32 utilisent une dispersion initiale modérée avec collisions contre la planche et le sol ; les contacts entre lamelles sont désactivés pour stabiliser les morceaux fins et contenir le calcul. Le teaser amplifie légèrement les fissures, sans déclencher la physique de chute.
