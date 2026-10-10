## Décision actuelle — repartir avec une illustration animée

L’utilisateur demande de tout oublier sur la 3D et autorise n’importe quel
style, pourvu que ce soit beau et différent du clip rejeté. Nouveau moteur
Canvas2D et récif nocturne illustré original, animaux et mouvement de caméra
codés. Deux assets originaux préparés une fois ; aucun Algrow ou générateur
vidéo, pas de génération à chaque image.

La nouvelle boucle complète de cinq minutes est livrée pour avis sur
https://gofile.io/d/95IFNFjM, avec fichier MP4 contrôlé et lecteur HTML
autonome. La validation du nom et de l’avatar ne vaut pas approbation de
ce fond ; avis visuel utilisateur attendu.

Les vidéos finales restent deux heures. Après validation du fond : voix off
sur histoires marines vraies et texte lisible, discret et élégant au milieu
de l’écran (pas de petits sous-titres bas d’écran). La première vidéo Sleep
sera publiée avant la prochaine Chess, Tommy/Alfie préparée en parallèle.
Depths After Dark et l’avatar méduse sont validés ; la bio anglaise est livrée.

Toutes les orientations 3D ci-dessous sont désormais historiques.

# Histoires vraies des profondeurs

Direction confirmée le 10 octobre 2026 : **récits vrais, ambiance inquiétante**.
Le format raconte une histoire pendant une exploration 3D en vue subjective.
L'utilisateur apprécie la V3, mais signale des poissons traversant des rochers.
Corriger cette cohérence physique avant de lancer un sujet ou un long.

## Relation entre narration et image

Partir d'un récit documenté : découverte d'une espèce, rencontre filmée,
expédition, épave ou événement réel. Donner une situation de départ, une
question, des découvertes et une conclusion fondée sur les sources.
La tension vient des faits et de la mise en scène, sans inventer un monstre
ou un événement pour les présenter comme une découverte réelle.

La caméra continue son exploration. Chaque moment du futur script précise
ce qui apparaît au même instant : l'animal dont il est question, l'objet
découvert, un détail de son comportement ou un changement de milieu.
L'exemple du « saumon vert » donné par l'utilisateur explique cette
synchronisation ; il ne décrit pas une espèce abyssale attestée.

Avant d'animer un sujet, vérifier son aspect, sa taille, sa profondeur, son
habitat et les comportements observés. Les espèces ne passent pas toutes
dans le même canyon par commodité. Une scène raconte une information nouvelle,
pas seulement un autre déplacement ou une répétition de modèles.

Le futur découpage associera des repères de voix aux actions, avec des entrées
et sorties naturelles. La voix définit les durées ; un changement de durée
doit décaler les actions concernées. Ce raccord narratif est une direction
de production, **pas une pipeline voix/scénario déjà implémentée**.

## Cohérence physique de la caméra et des animaux

- Les modèles animés occupent un volume, queue, nageoires et leurre compris.
- Réserver un corridor d'eau à partir de ce volume durant tout le passage.
- Placer les rochers hors de ce corridor ; une occultation visuelle ne prouve
  pas l'absence de traversée de matière.
- Garder de la distance au sol et réserver aussi le passage de la caméra.
- Les animaux déjà dans l'eau continuent leur nage hors champ ; éviter
  une apparition/disparition visible commandée par une simple heure.

Les volumes réservés et le déplacement des rochers sont réalisés dans
`swim-clearance.mjs` et `scene.mjs`. Il s'agit d'une composition préparée,
pas d'un système physique autonome permettant à tout nouvel animal d'éviter
n'importe quel obstacle. Chaque nouvelle scène doit refaire ses contrôles.

## Étape actuelle

**Correction explicite après la livraison de cinq minutes : repartir sur une
nouvelle direction artistique complète.** Le film GoFile `ixBAzbR6` est rejeté
comme vide et laid ; il n'est pas une référence validée. L'utilisateur abandonne
la reproduction du style DREDGE et demande un fond beau, vivant et inquiétant
supportant deux heures de narration. Nouveau décor organique, eau bleu-noir,
éclairage diffus, corps lisses, nombreux bancs visibles, requins et méduses
délicates ; aucune des anciennes créatures ou roches n'entre dans le nouvel
entrypoint `sleep-cinematic-scene.mjs`. Garder les archives sans les déclarer
validées. La construction reste entièrement codée, sans Algrow ni générateur
d'images. Vérifier un extrait avant un nouvel export complet de cinq minutes.

**Décision du 10 octobre : produire d'abord une boucle de cinq minutes**,
entièrement codée en HTML/JavaScript, détaillée et fluide. Les anciennes références
DREDGE et Subnautica restent documentées dans `STYLE_SLEEP.md` ; aucun
asset de jeu, Algrow ou générateur d'images payant. L'utilisateur vérifiera
cette boucle avant tout premier récit, script, voix ou épisode de deux heures.

## Format sleep choisi

L'utilisateur choisit une chaîne **sleep** avec récits marins réels : **tous
les épisodes feront deux heures**, avec la boucle de cinq minutes répétée
**24 fois**. Collaboration envisagée avec leur chaîne sleep existante.
Le premier sujet, la langue et la voix restent à choisir ; aucune production
de deux heures ni invitation de collaboration n'a été lancée.

Cette variante privilégie une lumière stable, des mouvements lents, des
passages espacés et une voix calme. La boucle doit raccorder réellement la
caméra, les animaux, les particules et l'ambiance sonore. **L'aperçu actuel
de 24 secondes reste une archive de cohérence. La première boucle de cinq
minutes a été livrée puis rejetée visuellement ; la refonte n'est pas validée.**
Une fois la boucle rendue, ses répétitions ne nécessiteront pas de recalculer
la géométrie durant deux heures ; l'assemblage et le son resteront à exporter.

Pour un programme de deux heures, proposer quatre à six récits de 20–30 minutes
reliés par un thème, ou une grande expédition suffisamment documentée.
La richesse du catalogue vient de familles variées : exploration, épaves,
créatures, adaptations à l'obscurité, paysages extrêmes, enquêtes résolues et
histoire des sciences. Recherche et narration originales doivent varier
entre les épisodes ; la répétition visuelle ne remplace pas ce travail.

Réservoirs documentaires effectivement consultés :

- [Smithsonian — calmar géant](https://ocean.si.edu/ocean-life/invertebrates/giant-squid).
- [WHOI — sources hydrothermales](https://www.whoi.edu/ocean-learning-hub/ocean-topics/how-the-ocean-works/seafloor-below/hydrothermal-vents/).
- [Endurance22 — expédition](https://endurance22.org/).
- [NOAA — Bloop](https://www.pmel.noaa.gov/acoustics/sounds/bloop.html) :
  son de fracturation de glace identifié, pas preuve d'un monstre.
- [MBARI — animaux des profondeurs](https://www.mbari.org/education/animals-of-the-deep/).
- [NOAA — archives de l'exploration](https://archive.oceanexplorer.noaa.gov/history/history.html).

La fonction YouTube invite des collaborateurs : leur nom et leur bouton
d'abonnement sont affichés après acceptation. YouTube indique vouloir
recommander la vidéo aux publics des deux chaînes, sans garantir un gain
immédiat dans les recommandations. Les revenus sont attribués à la chaîne
qui publie, sans partage automatique entre collaborateurs. Consulter les
[collaborations YouTube](https://support.google.com/youtube/answer/16554898?hl=en)
et les [règles de monétisation](https://support.google.com/youtube/answer/1311392?hl=en).
Conserver des récits substantiels, originaux et documentés pour chaque épisode,
plutôt que des contenus répétitifs produits en série avec peu de variation.
