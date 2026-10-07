# Pixel Cuts — crescendo approuvé

Direction : main du cuisto qui apporte la pastèque, pause avant les machettes,
scie circulaire plus imposante avec une vraie entrée, puis rafales de pistolet.
Pixel art sur toute l'image, titres anglais, musique reportée.

| Passage | Début–fin | Action et texte |
|---|---|---|
| Arrivée | 0–1,10 s | Paume ouverte sous le melon intact, manche blanche reliée au poignet. Main et fruit arrivent ensemble. 1 CUT affiché ; aucun lancer, aucun teaser. |
| MACHETE | 1,10–14,90 s | 1 / 4 / 8 / 16 / 32 CUTS. Lames lancées, puis chute. |
| CIRCULAR SAW | 14,90–29,90 s | 1 / 4 / 8 CUTS. Grand disque arrive du haut droit, tourne, traverse et repart en trajectoire continue. |
| PISTOL | 29,90–40,30 s | 1 / 4 / 8 SHOTS. Arme tenue, recul court, flash chaud discret, traceur d'une image, marques et éclats dirigés. |
| Fin | 40,30–41,80 s | Spatule dans la main avec léger saut et deux gerbes de particules pixel art, chute des débris qui continue. SERVED! / CHEF APPROVED. |

Machette : départs 1,10 / 3,10 / 5,40 / 8,10 / 11,20 s.
Scie : départs 14,90 / 18,30 / 23,00 s, durées 3,4 / 4,7 / 6,9 s.
Pistolet : départs 29,90 / 33,70 / 36,90 s. Premier tir à +0,85 s pour
le tir unique, +0,65 s pour les rafales. Intervalles de 120 ms puis 80 ms :
4 tirs sur 0,36 s et 8 tirs sur 0,56 s. Traceur de 16,7 ms avant l'impact,
flash pendant environ 52 ms, fissures plus ouvertes et projection renforcée.

Une seule scène 3D seekable est réutilisée pour tous les chapitres. Les poses
et les particules dépendent du temps absolu ; les chutes sont calculées hors ligne.

## Frame 1 — arrivée et machettes

status: implemented
src: index.html, scene.mjs, tools.mjs
rules: multi-phase-camera, particle-burst
beat: main porte le fruit, pause de lecture, puis 1 CUT et progression normale des lames. Aucun hook.

## Frame 2 — scie imposante

status: implemented
src: index.html, tools.mjs
rules: multi-phase-camera, particle-burst
beat: entrée du haut droit, grand disque tournant, retour en arc entre passes,
moteur qui monte puis accents au contact. Rayons des dents : 2,15 à 2,48 unités.

## Frame 3 — rafales et résultat

status: implemented
src: index.html, tools.mjs, impact-motion.mjs
rules: particle-burst, multi-phase-camera
registry: camera-shake, sampler et profil rig adaptés à la caméra 3D avant
conversion en palette. Les titres restent fixes sur la grille.
beat: tirs rapides, flash étouffé, recul, dégâts visibles, projection finale,
recul de caméra, main reprend la spatule. Bruitages locaux figés via Replicate.

Dernière révision approuvée : impacts avec fractures obliques inégales, 18 / 40 / 100 fragments ; petits éclats tétraédriques. Fin joyeuse avec deux gerbes de confettis et étincelles bitmap autour de la spatule, ancrées sur son mouvement et un léger saut. Célébration adaptée du sampler confetti du catalogue ; palette pixel art conservée.
