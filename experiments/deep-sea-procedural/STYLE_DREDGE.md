# Référence visuelle — DREDGE

Étude du 10 octobre 2026 pour corriger l'aperçu immersif V2. Il s'agit
d'adapter une direction artistique à des fonds marins originaux, pas d'utiliser
les modèles, textures ou séquences du jeu dans nos vidéos.

## Sources effectivement regardées

- [Page Steam officielle](https://store.steampowered.com/app/1562430/DREDGE/) :
  les 13 captures disponibles, notamment le canyon avec créature immergée
  (capture 7), la navigation nocturne (8) et la crique sombre (11).
- **Launch Trailer**, vidéo officielle de la page Steam, 105 secondes :
  planches de toute la vidéo, une image toutes les 3 secondes.
- **DREDGE: Complete Edition Trailer**, vidéo officielle de la page Steam,
  93 secondes : planche entière, puis séquences à 4 images/seconde pour le
  serpent (26,5–30 s), la créature de glace (50,1–53,9 s) et la créature
  aquatique passant devant le bateau (69–72 s).
- [Site officiel](https://www.dredge.game/) et
  [kit presse officiel](https://www.dredge.game/press-kit).

Les téléchargements et planches de recherche restent dans le dossier temporaire
`/tmp/deepsea-v3-reference/`, hors des ressources du film. Les observations de
mouvement reposent sur des séquences échantillonnées, pas sur une étude de toutes
les animations de tous les ennemis du jeu.

**Distinction importante pour les futures productions :** la navigation et les
grandes créatures dans l'eau sont en 3D ; les poissons dans l'inventaire,
l'encyclopédie et certaines scènes de dialogue sont des illustrations 2D.
Les monstres fantastiques donnent une référence de mise en scène, pas une
référence scientifique d'anatomie pour notre chaîne documentaire.

## Six corrections pour les modèles et la scène

1. **Dessiner la silhouette avant les facettes.** Les objets du jeu ont une
   forme cohérente : courbes de corps, masses de roche, profils de navires.
   Leur aspect polygonal sert cette forme. Remplacer notre baudroie presque
   sphérique par un corps irrégulier dont le dos, le ventre et le pédoncule
   caudal forment une ligne continue. Ajouter du relief de crâne et des
   membranes de nageoires, sans empiler des primitives reconnaissables.

2. **Retirer les yeux de jouet et la bouche figée.** Notre V2 présente un
   gros anneau blanc autour de l'œil et une énorme bouche ouverte constamment.
   Les créatures 3D regardées ont des yeux petits, sombres, intégrés au crâne,
   ou un accent lumineux localisé. Réduire l'œil, supprimer son anneau blanc,
   creuser la cavité buccale, espacer les dents fines et animer une respiration
   discrète. La bouche ne doit pas devenir un sourire à dents.

3. **Peindre des volumes plutôt que du bruit de triangles.** La créature de
   glace et les falaises ont de grandes plages mates cohérentes, avec quelques
   valeurs sombres et claires. Les variations suivent les volumes. Utiliser
   un dos plus sombre, un ventre légèrement plus clair, des plis et quelques
   marques irrégulières ; limiter la variation arbitraire par face. Palette
   de travail : brun-violet et gris-olive pour l'animal, vert-gris et bleu
   sombre pour le milieu, lumière chaude ou vert pâle seulement au point focal.

4. **La nage doit entraîner le corps.** La séquence de la créature aquatique
   montre une orientation qui évolue pendant le passage, un corps courbé et
   un effet local dans l'eau. Notre baudroie ne doit pas être un objet rigide
   translaté. Faire partir une onde faible du thorax, augmenter son amplitude
   vers la queue, donner aux nageoires pectorales un cycle indépendant et
   retarder le mouvement du leurre. Les virages ont un léger roulis et une
   accélération douce. Ce sont des choix d'animation pour notre poisson,
   pas une prétendue copie exacte du cycle de nage du jeu.

5. **Montrer une rencontre, pas un défilé de modèles.** Le jeu révèle souvent
   une masse dans l'eau, puis un détail, avec une partie du corps cachée.
   Commencer par le leurre dans la brume ; la tête rejoint la lumière puis
   passe à proximité, une nageoire masque brièvement le décor, la queue
   retourne dans l'obscurité. Utiliser des profondeurs différentes pour le
   banc, le poisson principal, les particules et les rochers.

6. **Donner du poids au milieu.** Les captures nocturnes ont des zones de
   lumière limitées, des silhouettes lointaines et de la vie autour du bateau.
   Pour notre POV sous-marin : éclairer une zone précise au lieu d'illuminer
   uniformément tout le canyon ; conserver du contraste sur le premier plan
   et absorber les couleurs au loin ; faire dériver les particules à plusieurs
   vitesses ; varier les phases du banc et donner aux petites formes benthiques
   un mouvement discret. Ne pas multiplier des sources néon ou des silhouettes
   impossibles pour remplacer une vraie composition.

## Validation avant une nouvelle livraison

- Comparer une vue de profil et une vue trois-quarts de la baudroie aux
  références de style ; aucun globe oculaire blanc ni aspect de boule rigide.
- Comparer plusieurs instants du passage : queue, nageoires, leurre et thorax
  doivent changer de forme ou d'orientation, pas seulement de position.
- Examiner les personnages proches en définition native : les facettes doivent
  dessiner le relief, les dents et membranes ne doivent pas clignoter.
- Garder l'aperçu court, sans voix ni script documentaire. Le style reste soumis
  à la validation de l'utilisateur ; ce dossier ne prétend pas que le résultat
  a déjà la finition du jeu.
