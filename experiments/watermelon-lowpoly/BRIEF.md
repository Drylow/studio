---
workflow: general-video
flow: automation
storyboard: no
message: "Reproduire par le code les découpes de pastèque du tweet, avec un style pixel art sur toute la vidéo, des coupes rapides et des bruitages satisfaisants."
aspect: portrait
language: en
length: 12
---

## Intent
Demande du 7 octobre 2026 : regarder la vidéo du tweet ErnestoSOFTWARE/2107832530770829559 et produire un essai comparable, éventuellement low-poly et entièrement réalisé en code. La demande autorise la fabrication et le rendu de cet essai.

## Source
Vidéo consultée dans le navigateur : 26,517 s, montage promotionnel partagé en deux. À gauche : pastèque suspendue, compteur de coupes, lames horizontales, fragments qui tombent sur une planche. À droite : statistiques et galerie de simulations. Les chiffres de vues sont des affirmations de l'auteur et ne constituent aucune garantie.

## Decisions
Version corrigée selon le retour du 7 octobre : 12 s, 1080 × 1920, 60 images/s. Toute l'image, titres inclus, est dessinée sur une grille 216 × 384 et agrandie sans lissage. Palette limitée à 19 couleurs, tramage discret et alphabet bitmap original. Tout le texte visible est en anglais : WATERMELON, 1 CUT, 3 CUTS, 7 CUTS. Même pastèque, planche et éclairage pour les trois passes. Coup de lame de 0,145 s et coups successifs espacés de 0,17 s. Scène Three.js, découpes géométriques et corps rigides calculés hors ligne puis figés. Aucun changement au frontend du studio.

## Audio
Chaque coupe a un souffle bref, un claquement net synchronisé à la coupe géométrique et une résonance courte. Impacts synthétisés depuis les collisions, plus discrets que les coups de lame. Pas de voix ni musique. Le volume est normalisé avec une marge avant saturation.

## Limitations
Prototype de corps rigides : pas de simulation de chair molle ou de jus. Les coups sont scénarisés ; les collisions des fragments sont simulées. Géométrie low-poly, rendu final pixel art.
