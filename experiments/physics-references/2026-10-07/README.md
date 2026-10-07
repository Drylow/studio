# Références physiques et sonores — 7 octobre 2026

Six Shorts récupérés à la demande de l'utilisateur depuis Velvet Ji et NodeFan3D.
Les fichiers complets, avec leur son, sont dans `media/`. Cette étude sert aux
animations originales avec notre cuistot pixel art. La première adaptation est
réalisée dans `../../chocolate-crunch/`. Le nom de chaîne reste à confirmer.

## Sélection téléchargée

| Chaîne | Référence | Durée mesurée | Intérêt |
| --- | --- | --- | --- |
| [NodeFan3D](https://www.youtube.com/@NodeFan3D) | [Glass Panels Fall and Shatter on a Pyramid](https://www.youtube.com/shorts/ub5r4awGvIc) | 22,55 s | Plaques horizontales sur une pointe : correspond le mieux à l'exemple décrit. |
| NodeFan3D | [Glass Panels Fall on a Pyramid](https://www.youtube.com/shorts/tEsIu9R6-pQ) | 25,05 s | Variante : plaques verticales sur une arête métallique. |
| NodeFan3D | [Hammer Smashes a Tower of Cubes](https://www.youtube.com/shorts/lutYBNfxDkg) | 31,72 s | Marteau de plus en plus massif, choc lourd puis cascade de blocs. |
| NodeFan3D | [Ball Rolls Down Rails and Knocks Down Columns](https://www.youtube.com/shorts/FqGWEET6xcc) | 40,05 s | Roulement, collisions successives et effondrement. |
| [Velvet Ji](https://www.youtube.com/@VelvetJiPhysics3D/shorts) | [1 to 50 Blades vs a Mango](https://www.youtube.com/shorts/jmw6kx5rOVc) | 23,73 s | Coupes de fruit et passage des gros morceaux aux petits débris. |
| Velvet Ji | [Can Thicker Glass beat a Hydraulic Press?](https://www.youtube.com/shorts/K_lp3huE1_A) | 22,62 s | Progression d'épaisseur, résistance et sons de destruction. |

Les noms de fichiers sont les identifiants YouTube de ces liens, suivis de `.mp4`.
Exemple principal : `media/ub5r4awGvIc.mp4`.
Les métadonnées originales sont dans les `.info.json` voisins.
`manifest.json` conserve sources, tailles, empreintes, caractéristiques et mesures audio.
Les médias, planches et réponses brutes de l'outil sont exclus de Git ; l'index
et cette analyse sont conservés pour les prochaines sessions.

## Ce qui a réellement été examiné

- Catalogue des deux chaînes interrogé avec Nexlev et le téléchargeur : 45 Shorts
  chez Velvet Ji, 31 chez NodeFan3D au moment de la recherche.
- Six fichiers vérifiés avec FFprobe : image et son présents ; total 165,72 s.
  Copies d'étude 360 × 640 à 30 images/s, vidéo AV1 et audio AAC.
- Six planches regardées, avec 333 captures espacées de 0,5 s. Elles montrent
  l'arrivée, les changements de niveaux, les impacts et les débris.
- Chaque vidéo passée à l'outil d'analyse audiovisuelle de Nexlev pour les sons
  non verbaux. Réponses brutes dans `tool-analysis/`. Les observations visuelles
  ci-dessous ont été recoupées avec nos propres captures.
- Enveloppes audio décodées mesurées par fenêtres de 10 ms. Les pics aident à
  repérer les accents ; ils ne prouvent ni un matériau, ni une source de bruitage.
- L'outil de recherche d'outliers a renvoyé une liste vide pour les deux chaînes,
  malgré le catalogue de Shorts accessible. Aucun score d'outlier n'est inventé.
  Les références sont choisies pour leur scène et leur son, pas pour un score absent.
- Pas de mesure de rétention disponible : le rôle des SFX dans la rétention est
  une hypothèse créative à tester sur nos publications, pas un résultat établi.

## Verre sur une pointe : la référence recherchée

Dans `ub5r4awGvIc`, il s'agit de plaques de verre teinté translucide,
pas d'un miroir confirmé. Elles tombent à plat sur une petite pyramide métallique.
Progression visible : 1 / 2 / 3 / 4 / 5 plaques. Débuts de séquences approximatifs
à 0 / 3,5 / 7,5 / 12 / 16,5 s, relevés sur des captures espacées de 0,5 s.
Première cassure visible vers 1 s ; les éclats continuent à retomber après le choc.

Dans `tEsIu9R6-pQ`, les plaques restent verticales et rencontrent une arête
triangulaire. Débuts approximatifs à 0 / 4 / 8 / 13 / 18,5 s. Les silhouettes
des débris sont inégales et anguleuses. Le tas de chaque essai est remis à zéro
au changement de niveau ; il n'est pas conservé d'une séquence à l'autre.

L'analyse audiovisuelle relève un accent cristallin avant l'action, une cassure
sèche puis des tintements de débris qui s'éteignent. Elle ne signale ni narration
ni musique. Son point utile est l'articulation entre anticipation, rupture et
retombée ; ses suggestions de bruit d'air et de grave supplémentaire ne sont
pas des sons dont la présence est établie dans les originaux.

## Tours, roulement et fruits

**Marteau (`lutYBNfxDkg`).** Niveaux 1 / 10 / 25 / 50 / 100 kg,
approximativement à 0 / 3,5 / 10,5 / 17 / 23,5 s. Un marteau tenu au bout d'une
tige balaie une colonne de petits cubes. À 1 kg, presque rien ne tombe ; les
essais suivants passent d'un arrachement partiel à l'écroulement complet.
Les cubes réguliers sont cohérents ici : la tour est assemblée en cubes avant
le choc. L'analyse sonore relève un choc grave, un accent sec puis une texture
de petits impacts ; le crescendo doit faire entendre le poids.

**Boule sur rails (`FqGWEET6xcc`).** Niveaux 1 / 5 / 15 / 25 / 50 kg,
approximativement à 0 / 7 / 13,5 / 22,5 / 32 s. Le parcours reste lisible et la
boule abat de plus en plus de colonnes. Les unités brunes se séparent, puis les
boules colorées tombent et roulent. L'analyse sonore relève le roulement avant
le choc, les impacts successifs, puis les petites retombées. Garder une durée
après le premier choc permet de suivre ses conséquences.

**Mangue (`jmw6kx5rOVc`).** Teaser de 0 à environ 1,8 s, puis 1 / 5 / 10 / 25 /
50 CUTS. Débuts approximatifs des essais : 2 / 4,5 / 7,5 / 11,5 / 17 s. Le fruit
est au-dessus d'une assiette ; les lames passent, les divisions s'ouvrent puis
les morceaux tombent. Notre examen montre des morceaux anguleux : il ne
confirme pas l'affirmation de cubes uniformes pour 5–10 coupes dans la réponse
brute de l'outil. L'analyse audio relève des accents courts de coupe et une
retombée plus dense aux derniers niveaux. **Notre préférence approuvée reste
un départ normal, sans teaser, et un maximum de 32 coupes.**

**Verre épais (`K_lp3huE1_A`).** 0,5 / 2 / 4 / 7 / 35 cm, à environ
0 / 5 / 9 / 14 / 18,5 s. Des anneaux s'empilent sur un cône, puis deux presses
latérales les écrasent. Le dernier cylindre subit aussi une presse verticale.
L'analyse audio relève un mélange de rupture aiguë et de choc sourd, avec des
retombées plus légères. Augmenter l'épaisseur change la résistance et la forme
des débris, pas seulement leur quantité.

## Cahier sonore pour nos prochains essais

Les valeurs suivantes sont des choix proposés pour nos productions, pas des
réglages extraits des chaînes.

1. **Préparer le choc.** Laisser brièvement lire le fruit, son matériau et la
   machine. Employer un bruit de déplacement lié à l'objet, ou du calme.
2. **Synchroniser le choc.** Le premier accent fort commence à la même image
   que le contact réel, à une image près dans un export à 60 images/s.
3. **Distinguer poids et rupture.** Une couche courte et grave porte le choc ;
   une couche propre au matériau porte la cassure. Fruit : humide et mat.
   Verre/cristal : sec et cristallin. Blocs : petits claquements et frottements.
4. **Faire vivre la retombée.** Gros fragments : quelques impacts distincts.
   Petits fragments nombreux : texture granulaire plus douce, puis extinction.
   Prévoir 0,4–1,6 s selon l'essai, plutôt qu'une coupe immédiate.
5. **Éviter le son identique répété.** Plusieurs prises par matériau, sélection
   déterministe, petite variation de hauteur et de niveau. Aucun changement
   aléatoire pendant le rendu.
6. **Limiter la densité.** Priorité au choc principal. Regrouper les collisions
   secondaires d'un même matériau dans des fenêtres de 30–50 ms ; limiter
   initialement à quatre accents secondaires simultanés. Faire entendre un lit
   de débris pour les petits contacts au lieu de jouer un sample pour chacun.
7. **Lier le son à l'événement.** Déclencher depuis le contact et son énergie,
   pas depuis l'apparition d'un fragment ni depuis chaque pas de simulation.
   Calmer les retombées faibles et limiter le total d'un groupe dense.
8. **Garder de la réserve.** Tester le passage le plus chargé, le mix complet
   et l'AAC final. Vérifier les crêtes et faire écouter sur téléphone ; monter
   la force du dernier essai ne doit pas créer une saturation ni des aigus pénibles.
9. **Musique secondaire.** Priorité actuelle aux SFX. Tester d'abord sans
   musique ; si elle est ajoutée ensuite, garder les cassures et retombées lisibles.

Pour les prochains clips : créer ou sourcer nos propres SFX par matériau.
Les sons des références servent à l'étude, et ne sont pas branchés dans nos builds.
Les clés déjà configurées restent privées. Les bruitages du nouvel essai sont
générés séparément, puis figés dans le projet de chocolat.

## Adaptations alimentaires avec notre cuistot

L'utilisateur a précisé : toujours de vrais aliments (fruits, viande ou autre
nourriture), le même personnage et le même style que Watermelon. Il demande
maintenant de réaliser l'adaptation. Aucun fruit en verre ou en cristal.

| Piste de titre anglais | Expérience | Axe sonore | Difficulté |
| --- | --- | --- | --- |
| **Chocolate vs Giant Fork** | Réalisé : 1 / 2 / 4 / 8 / 16 tablettes comestibles tombent sur une fourchette géante. | Craquement sec de chocolat, miettes et retombées sur le bois. | Fracture au contact, corps rigides et trajectoires calculées hors ligne. |
| **Fruit Tower vs Giant Hammer** | Une tour de morceaux de fruits, frappée par un maillet de plus en plus gros. | Choc grave, impacts humides, cascade qui se calme. | Corps rigides ; cubes cohérents puisqu'ils sont découpés avant le choc. |
| **Steak vs Crusher** | Piste suivante : un steak comestible subit une presse ou un outil de plus en plus imposant. | Compression, frottement et relâchement humide. | Déformation souple à prototyper ; pas encore réalisée. |

Conserver les repères approuvés : anglais, pixel art partout, cuistot et manche
blanche reconnaissables, progression lisible, crescendo, courte joie finale.
Le nom de chaîne reste non confirmé. Le chocolat reprend l'expérience des
plaques horizontales sur la pointe, avec nos propres objets, images et sons.

## Refaire l'examen

Depuis la racine du dépôt, avec FFmpeg, FFprobe, Python, NumPy et Pillow :

    python experiments/physics-references/analyze_references.py experiments/physics-references/2026-10-07

La commande relit les fichiers présents, refait les planches et les mesures ;
elle ne télécharge rien et ne lance aucune génération.
