---
workflow: general-video
flow: automation
storyboard: no
message: "Chef mignon, outils démesurés : machette, scie circulaire flottante, pistolet cartoon noir en rafales sur une pastèque."
aspect: portrait
language: en
length: 41.8
---

## Intent et autorisation

Essai demandé puis révisé le 7 octobre 2026. Référence consultée :
https://x.com/ErnestoSOFTWARE/status/2107832530770829559. Reproduire ce genre
d'animation par le code, puis rendre toute la vidéo en pixel art. Limite de
32 cuts approuvée pour les machettes ; cadence ralentie conservée.
L'utilisateur a approuvé trois outils, un pistolet noir reconnaissable et
la main avec l'avant-bras du chef en manche blanche. Dernier retour : flash
léger et étouffé, impact plus lisible, tirs qui spamment et bruitage généré
avec sa clé Replicate. Rendu autorisé dans la continuité des révisions.
Aucun changement au frontend du studio.

## Montage

41,80 s, 1080 × 1920, 60 images/s. Arrivée de la main pendant 1,10 s, fruit intact ; aucun hook ni teaser.
Le titre affiche 1 CUT dès le départ. Première coupe à 1,22 s.
MACHETE : 1 / 4 / 8 / 16 / 32 CUTS jusqu'à 14,90 s.
CIRCULAR SAW : 1 / 4 / 8 CUTS jusqu'à 29,90 s, scie flottante en rotation.
PISTOL : 1 / 4 / 8 SHOTS jusqu'à 40,30 s. Rafales sur 0,36 puis 0,56 s,
intervalles de 120 puis 80 ms. Pistolet tenu, recul de moins de 0,1 s,
traceur de 16,7 ms, flash chaud discret, marques d'impact et éclats dirigés.
Fin avec spatule jusqu'à 41,80 s ; la chute des fragments continue.
Voir STORYBOARD.md pour les départs exacts.

## Style

Grille 216 × 384 agrandie ×5 sans lissage ; palette de 23 couleurs,
alphabet bitmap original. Tous les mots visibles sont anglais. Icône pastèque
près de WATERMELON et icône de l'outil près de son nom. Éclairage doux,
bois miel, verts naturels ; chair corail, manche blanche et main pêche.
Même scène Three.js et physique déterministe calculée hors ligne.

## Audio

74 accents de coupe, 13 accents de tir et collisions regroupées par fenêtres
de 50 ms. Tir généré via Replicate, figé en fichier local, réduit à 120 ms,
filtré et normalisé avec réserve de niveau. Une occurrence alignée par tir,
petite variation déterministe de vitesse. Moteur de scie généré et figé, entrée progressive et accents aux passes.
Gain maître linéaire, aucun saturateur. Pas de voix ; musique reportée à la
demande de l'utilisateur. Clés seulement dans le .env ignoré.

## Limites

Fragments rigides ; pas de chair molle ni simulation de jus. Fractures planes
pour les coupes, fractures obliques de tailles inégales pour les tirs. Marques et petits éclats
scénarisés ; chute finale simulée. Contacts entre fragments désactivés pour
les coupes denses et les tirs, avec collisions contre planche et sol.

Révision du crescendo : la paume ouverte du chef soutient le dessous de la pastèque et suit son arrivée en 0,72 s, puis se retire. La manche blanche reste reliée au poignet ; le dessus de la paume rejoint le point bas du fruit. Aucun lancer pendant l’arrivée ; première coupe à 1,22 s dans le niveau 1 CUT. Scie plus grande (rayon 2,48 contre 1,90 auparavant), entrée continue depuis le haut droit, trajectoire liée aux plans de coupe et retour en arc entre passes. 4 passes espacées de 0,75 s ; 8 de 0,65 s. Son de scie généré via Replicate, montée du moteur à l’entrée puis accent à chaque passe. Fissures plus ouvertes aux tirs, projection finale renforcée, léger mouvement de caméra issu du composant camera-shake du catalogue. Recul et recentrage finaux pour contenir les débris.

Ouverture : arrivée normale, puis progression 1 / 4 / 8 / 16 / 32 ; aucune salve initiale de 32, aucun texte PREVIEW.

Dernière révision approuvée : impacts avec fractures obliques inégales, 18 / 40 / 100 fragments ; petits éclats tétraédriques. Fin joyeuse avec deux gerbes de confettis et étincelles bitmap autour de la spatule, ancrées sur son mouvement et un léger saut. Célébration adaptée du sampler confetti du catalogue ; palette pixel art conservée.
