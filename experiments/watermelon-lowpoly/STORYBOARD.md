# Pixel Cuts — proposition v2, à valider

## Locked

Montage actuellement livré : 14,65 s, pixel art intégral, titres anglais,
progression 1 / 4 / 8 / 16 / 32 cuts, hook coupé avant la chute.
Logo approuvé dans son principe : chef mignon tenant une spatule.
Aucun des nouveaux niveaux ci-dessous n'est encore implémenté.

## Changes from v1

Retour utilisateur du 7 octobre 2026 : « au moins 3 levels avec des trucs de plus
en plus forts » ; « après la machette […] une scie circulaire » ; « une arme à feu
qui tire sur des fruits pour les casser, et qu'il y ait plein d'éclats partout ».
La scie « flotte et […] va couper le truc, mais pas […] à toute vitesse comme les
machettes ». « Tu peux me proposer des idées, avant de faire ».

Direction : contraste entre le chef pixel art mignon et ses outils démesurés.

## Proposition recommandée — environ 40 à 45 secondes

| Passage | Durée indicative | Texte visible et action |
|---|---:|---|
| Hook et MACHETE | 15 s | Hook existant conservé. Icône machette près de MACHETE, icône fruit près de WATERMELON. Lames projetées ; 1 / 4 / 8 / 16 / 32 CUTS. |
| CIRCULAR SAW | 12–14 s | Pastèque intacte au changement de niveau. Icône scie, disque flottant en rotation continue, traversée contrôlée du fruit. 1 / 4 / 8 CUTS, passes nettes et chute finale. |
| SHOTGUN | 12–14 s | Pastèque intacte, arme cartoon visible sur le côté. 1 / 4 / 8 SHOTS ; recul bref, impact sur le fruit, éclats rouges et verts progressivement plus nombreux. Outil maintenu, seuls les projectiles se déplacent. |
| Fin | 1–2 s | Chef avec sa spatule, satisfait devant le résultat. |

Les titres restent intégralement anglais. On peut comprendre chaque outil par sa
silhouette, son icône et son mouvement avant de lire le texte. Les éclats restent
ceux du fruit. Le niveau 32 ne réapparaît pas en rafale de tirs.

## Still open

- Validation des trois outils et du choix SHOTGUN plutôt qu'une autre arme cartoon.
- Alternative moins violente : MACHETE → CIRCULAR SAW → LASER, avec une ligne
  lumineuse qui découpe le fruit et un effet final de cubes.
- Musique chill originale de jeu 2D, sans voix, sous les sons de découpe. Requête et
  générateur préparés ; aucune piste générée. ElevenLabs répond HTTP 401,
  invalid_api_key, avec la clé trouvée puis la clé communiquée. Nouvelle clé valide
  nécessaire avant génération. Aucun secret dans ce document ou dans Git.
- La durée exacte sera fixée après validation ; génération musicale prévue à
  48 secondes pour garder une marge de montage.

## Construction après validation

Conserver le mouvement approuvé des machettes ; créer une rotation et une traversée
continues pour la scie ; créer les impacts et la fragmentation du troisième niveau.
Mixer la musique comme piste séparée, avec fondus et gain faible. Vérifier le son,
les icônes et chaque image du rendu avant livraison.
