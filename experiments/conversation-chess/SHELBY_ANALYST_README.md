# Pion analyste Shelby — cinq propositions rejetées

La vidéo Tommy / Alfie doit utiliser **Thomas Shelby comme analyste**. Le
pion doit d’abord être présenté seul puis **validé explicitement par
l’utilisateur avant toute intégration ou nouvel export**. Aucun brouillon
d’image, aucune validation technique et aucun avis interne ne remplace ce choix.

## Nouvelle direction acceptée, portrait encore à modifier

`branding/shelby-tony-style-candidate-2026-10-11.png` a été montré et
l’utilisateur apprécie enfin le rendu, mais demande **une autre photo avec
la tête plus droite**. Il ne valide pas encore cette image pour le montage.
Conserver proportions, base noire et badges ; soumettre le nouveau portrait
avant toute intégration. Le portrait de référence vient de TVmaze1000×1400.

La méthode du Tony approuvé est désormais retrouvée : planche, édition du
choix A avec corps noir, puis édition transparente. Les trois PNG du dépôt
sont identiques aux sorties conservées du générateur d’images. Le prompt
littéral ancien n’est pas conservé. Cette sixième proposition utilise le
Tony approuvé et une vraie photo Tommy comme références d’édition ; des
traits/détails de la photo sont reconstruits. Ne pas la décrire comme un
photomontage dont les pixels du visage resteraient inchangés.

## Images rejetées et correction d’identité

- `branding/shelby-pawn-candidate-2026-10-11.png` : rejetée ; visage artificiel
  et mauvaise jonction entre tête et pion. Ne jamais intégrer.
- `branding/shelby-photo-candidate-2026-10-11.png` : également rejetée ; elle
  représente Michael Gray, pas Thomas. Ne jamais intégrer.
- `branding/shelby-real-photo-candidate-2026-10-11.png` : vraie frame de Thomas,
  mais rejetée pour mauvais détourage et raccord tête/base. Ne jamais intégrer.
- Les frames S02E06 à **487 s et 601 s montrent Michael Gray**, pas Thomas.
  Leur recommandation initiale était erronée. Les exclure de tout portrait
  Shelby, même si un ancien nom de fichier ou manifeste dit « Tommy ».

Le cinquième essai, `branding/shelby-scene-photo-candidate-2026-10-11.png`,
utilise bien le vrai Thomas dans S03E06 à1165s, sans cou dépassant à droite,
mais **l’utilisateur le rejette aussi** : le rendu n’égale pas le pion Tony.
L’empreinte est `335120050bd0d220556c0cb01d805137682d178b1596d9b49df38ace05651ddf`.
La tête de255×341px a été agrandie2,3× ; la douceur et les contours irréguliers
restent visibles en grand format. Ne pas l’intégrer ni tenter de la faire
accepter en invoquant une revue interne.

La recherche a ensuite retrouvé la méthode du Tony ; le sixième essai ci-dessus
est apprécié, mais une meilleure orientation de portrait reste demandée.
Les cinq fichiers sont des archives **rejetées**, aucun asset n’est approuvé.
Conserver tête entière, proportions courtes, jonction harmonieuse et base noire.
Les frames S02E06 à747s et S03E06 à1165s ne sont plus recommandées pour le portrait.
Le poster BBC rayé et la petite photo Netflix aux yeux cachés ne sont pas des
sources convenables malgré leur origine officielle.

## Archive — poster BBC rejeté

`branding/shelby-bbc-photo-candidate-2026-10-11.png` : vrai portrait officiel
Tommy / Cillian, tête et casquette entières, luminance noir et blanc, masque
raffiné et raccord au pion noir. Root et revue indépendante ont comparé
la source, les fonds clair/sombre et l’aperçu à320px. Les rayures/grain sont
ceux du poster BBC, pas une génération du visage. Limite visible : bord de
casquette encore irrégulier en grand format. Empreinte du PNG :
`f8e2669967ec79e6e4c1698eb36691eaaca405e7d188618bbabb57259cb125b8`.

**Rejet utilisateur : poster trop retouché, débordement du cou à droite. Ne pas intégrer.**
Cette revue interne n’autorise ni intégration ni nouvel export. Les deux
badges existants et le bas du pion sont repris du PNG Tony approuvé, avec
les petits parasites des crops exclus. L’avatar Tony global reste intact.

## Portée de la correction

Seul l’analyste de cet épisode change. Conserver :

- l’avatar Tony approuvé pour la chaîne et les PNG Tony génériques ;
- les pions blanc et noir identiques de la barre gauche, dessinés par `pawn()` ;
- dialogues anglais, absence de voix off, sources et replays sélectionnés ;
- SFX, musiques, timing et les **32 annotations**, si la timeline reste identique.

Le renderer accepte déjà `mascot.file` et `mascot.overlay_file`, chemins PNG
relatifs au dossier du toolkit. Après validation seulement, une copie de la
timeline Peaky peut recevoir ces deux chemins et
`analysis_pawn_by_speaker: false`. Enregistrer l’empreinte du PNG réellement
validé dans le manifeste ; ne jamais remplacer un asset global Tony.

Le pion apparaît dans le guide (`scene.js`), les **32 analyses**, l’outro et
son fond déjà incrusté `project-background-outro.png`. Toutes ces couches doivent
être régénérées ou reconstruites avec le bon asset. Un rafraîchissement
d’intro est insuffisant : `--refresh-intro` et `--refresh-project-intro`
refusent volontairement une empreinte de mascotte différente.

## Reprise après validation utilisateur seulement

1. Sauvegarder le PNG transparent validé sous un nouveau nom propre à Peaky.
   Vérifier visage, masque, cadrage, jonction tête/base et aperçu réduit.
2. Copier la timeline active vers une nouvelle timeline corrigée ; remplacer
   les deux champs `mascot` et conserver les autres décisions éditoriales.
3. Utiliser le master source local déjà vérifié. Valider la nouvelle timeline,
   puis préparer les pistes dans un **nouveau dossier** avec
   `render-clip.mjs --validate-only` et `--prepare-project`.
4. Exporter un nouveau MP4 avec `export-kdenlive.py` et le projet Kdenlive/MLT.
   Le renderer prépare les pistes ; le moteur natif réalise le film final.
5. Exécuter `check-native-export.py` sur le nouveau MP4, son manifeste de pistes,
   son reçu natif et la nouvelle timeline. Examiner ses captures réelles,
   notamment guide, toutes les analyses et bilan. Voir les commandes complètes
   dans [la fiche de production](TOMMY_ALFIE_PRODUCTION.md).

Les caches source, pistes audio et décisions de montage restent réutilisables.
Le remplacement sélectif de toutes les couches de mascotte n’est pas encore
implémenté ni testé ; ne pas promettre une reprise instantanée. Le premier
export a demandé environ 15 minutes de préparation puis 31 minutes d’export
natif dans cet environnement CPU. Ce sont des mesures passées, pas une garantie
de délai pour la correction.

## Archive et état de livraison

Le premier MP4 terminé, 15 min 27,900 s, contient encore Tony comme analyste :
**archive privée, livraison interdite depuis la correction utilisateur**. Son
empreinte est
`24308206f0147649a22af173db41e3a3f50ecedfe8178ade89f1a328cbf73e55`.
Sa QA n’approuve pas un futur film corrigé. Aucun export Shelby n’est lancé.

Les originaux sont natifs 720p ; les graphismes et l’export sont en 1080p.
Conserver les crédits musicaux réels de la description. Les extraits Peaky
restent protégés : aucune absence de réclamation ou monétisation garantie,
aucune modification destinée à esquiver Content ID.
