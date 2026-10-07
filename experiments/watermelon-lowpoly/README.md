# Pixel Cuts — chef et trois outils

Animation procédurale inspirée de la référence du tweet
https://x.com/ErnestoSOFTWARE/status/2107832530770829559, regardée avant réalisation.
Aucun extrait repris. Version actuelle : 41,80 s, portrait 1080 × 1920 à 60 images/s,
pixel art intégral et titres anglais.

Arrivée normale de 1,10 s, puis MACHETE (1/4/8/16/32 CUTS), CIRCULAR SAW (1/4/8 CUTS),
PISTOL (1/4/8 SHOTS) et spatule finale. La scie flotte et traverse le fruit.
Le pistolet noir reste tenu par une main avec manche blanche ; il recule,
émet un flash chaud discret et un traceur d'une image. Rafales de 4 tirs
sur 0,36 s puis 8 sur 0,56 s. Marques d'impact et éclats accompagnent
les fractures. La physique continue dans le plan final. Musique reportée.

## Reproduction

Node.js et Python, FFmpeg/FFprobe sur PATH, Pillow pour les planches de contrôle.

    npm install
    npm run build
    npm run verify
    npm run dev
    npm run check -- --strict
    npm run render -- --fps 60 --quality delivery --strict --no-browser-gpu --workers 2 --output watermelon-chef-three-levels.mp4
    python qa_frames.py watermelon-chef-three-levels.mp4

Le rendu doit être vérifié sur toutes les planches avant livraison. La preview
peut ralentir selon le navigateur ; cela ne change pas le rythme du MP4.

## Construction

build-simulation.mjs découpe un solide convexe et calcule sa chute hors ligne
avec un pas fixe de 120 Hz. Les poses sont figées ; aucune intégration physique
pendant le rendu. 2/12/28/60/124 fragments pour les machettes, 2/12/28 pour la scie,
18/40/100 pour les tirs. Volume conservé par les fractures. Petite dispersion
scénarisée ; contacts entre fragments désactivés pour les coupes denses et les tirs.

scene.mjs interpole les poses, éclaire la scène et cadre le fruit.
tools.mjs construit les outils, la main et la manche ; toutes leurs poses
sont des fonctions du temps absolu. pixel.mjs transforme chaque image
sur une grille 216 × 384 à palette de 23 couleurs et dessine les titres bitmap.
Les lots de sommets et les couleurs sont réutilisés pour alléger la preview.

sound.py assemble 74 accents de coupe, 13 tirs et des collisions regroupées
par fenêtres de 50 ms. Les bruitages du tir et de la scie sont générés via Replicate, puis figés. Le tir est dans
assets/sfx-pistol.wav ; provenance, prompt, découpe et empreinte dans
assets/sfx-pistol.json. Le moteur de scie est dans assets/sfx-saw.wav, avec sa provenance dans assets/sfx-saw.json. Les sources MP3 sont conservées. Aucun appel externe dans
le build ; régénération uniquement sur demande. Mix linéaire sans saturateur.

Logo de chaîne : brand/chef-spatula-avatar.png, chef pixel art tenant une spatule.

## Limites

Fragments rigides, pas de chair souple ni de jus simulé. Marques et petits éclats
scénarisés ; chute finale et collisions contre planche et sol simulées.
Code et petits fichiers du bruitage conservés dans Git. Simulation, bundle,
mix WAV, MP4, captures et dépendances générés exclus de Git.

Révision du crescendo : la paume ouverte du chef soutient le dessous de la pastèque et suit son arrivée en 0,72 s, puis se retire. La manche blanche reste reliée au poignet ; le dessus de la paume rejoint le point bas du fruit. Aucun lancer pendant l’arrivée ; première coupe à 1,22 s dans le niveau 1 CUT. Scie plus grande (rayon 2,48 contre 1,90 auparavant), entrée continue depuis le haut droit, trajectoire liée aux plans de coupe et retour en arc entre passes. 4 passes espacées de 0,75 s ; 8 de 0,65 s. Son de scie généré via Replicate, montée du moteur à l’entrée puis accent à chaque passe. Fissures plus ouvertes aux tirs, projection finale renforcée, léger mouvement de caméra issu du composant camera-shake du catalogue. Recul et recentrage finaux pour contenir les débris.

Ouverture : arrivée normale, puis progression 1 / 4 / 8 / 16 / 32 ; aucune salve initiale de 32, aucun texte PREVIEW.

Dernière révision approuvée : impacts avec fractures obliques inégales, 18 / 40 / 100 fragments ; petits éclats tétraédriques. Fin joyeuse avec deux gerbes de confettis et étincelles bitmap autour de la spatule, ancrées sur son mouvement et un léger saut. Célébration adaptée du sampler confetti du catalogue ; palette pixel art conservée.
