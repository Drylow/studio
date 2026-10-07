---
workflow: general-video
flow: automation
storyboard: no
message: "Reproduire par le code le plaisir visuel des découpes de pastèque du tweet, dans un style low-poly."
aspect: portrait
language: fr
length: 18
---

## Intent
Demande du 7 octobre 2026 : regarder la vidéo du tweet ErnestoSOFTWARE/2107832530770829559 et produire un essai comparable, éventuellement low-poly et entièrement réalisé en code. La demande autorise la fabrication et le rendu de cet essai.

## Source
Vidéo consultée dans le navigateur : 26,517 s, montage promotionnel partagé en deux. À gauche : pastèque suspendue, compteur de coupes, lames horizontales, fragments qui tombent sur une planche. À droite : statistiques et galerie de simulations. Les chiffres de vues sont des affirmations de l'auteur et ne constituent aucune garantie.

## Decisions
Essai original de 18 s, 1080 × 1920, 30 images/s. Même pastèque, même planche et même éclairage pour trois passes : 1, 3, 7 coupes. Studio crème, bois miel, vert feuille et chair corail. Scène Three.js, découpes géométriques véritables et trajectoires de corps rigides calculées hors ligne puis figées. Sans génération d'images ni fournisseur IA. Aucun changement au frontend du studio.

## Audio
Bruitage court de coupe et impacts synthétisés localement depuis les événements du moteur physique ; pas de voix ni musique.

## Limitations
Prototype de corps rigides : pas de simulation de chair molle ou de jus. Les coups sont scénarisés ; les collisions des fragments sont simulées. Le style low-poly est volontaire.
