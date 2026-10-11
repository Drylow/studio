# Pion analyste Shelby — portrait frontal validé

La vidéo Tommy / Alfie utilise **Thomas Shelby comme analyste**. L’utilisateur
a explicitement validé la septième proposition frontale : « Voilà là nickel »,
puis demandé de l’utiliser dans tout le montage et de préparer la vidéo.
Cette validation lève la gate du portrait ; aucun des anciens essais rejetés
n’est intégré.

## Asset exact approuvé et correction exportée

Le PNG final est [assets/peaky/shelby-pawn-approved-2026-10-11.png](assets/peaky/shelby-pawn-approved-2026-10-11.png),
1254×1254 RGBA, empreinte
`de053ed15db958a0444d3327571c5223a2d53471cb876d49f11bb1011e7b3c04`.
Il est copié sans retouche depuis la sortie présentée puis validée. La
[fiche d’asset](assets/peaky/shelby-pawn-approved-2026-10-11.json) conserve
la source BBC du portrait de référence et l’empreinte réelle. Cette édition
photographique par générateur reconstruit des détails ; ne pas la décrire
comme un photomontage conservant exactement les pixels du visage.

La [timeline Shelby](tommy-alfie-shelby-timeline.json) remplace seulement
`mascot.file`/`mascot.overlay_file` et fixe `analysis_pawn_by_speaker: false`.
Les 32 analyses, timings, sources, audio, musiques, catégories et ouvertures
restent identiques. Le guide, chaque carte, l’outro et son fond incrusté
sont régénérés. Le nouvel export Kdenlive/MLT est terminé dans
`output/conversation-chess/tommy-alfie-shelby-native/` :
`Tommy-Alfie-Shelby-15m28.mp4`, 27 837 images, 927,900 s, 444 369 182 octets,
SHA256 `97725d9abe363e8c421adaab5367464275a0700efb27cd8eb2ad88743c59a694`.
Son propre décodage A/V et contrôle technique/audio passent sans erreur,
sans clipping, avec true peak −4,9 dBFS. Les 181 captures réelles sont extraites ;
les raccords, le guide et le bilan ont été regardés, sans ancien pion observé.
La revue indépendante est terminée : 32 analyses et tous les groupes hors
raccords examinés, empreinte du MP4 recalculée conforme, aucun défaut trouvé
dans ces captures. Les deux revues couvrent les 181 images sur 25 planches.
Elles ne constituent pas une lecture continue du film ni une écoute humaine
complète. Le root a aussi examiné 85 captures distinctes, dont trois en
1920×1080 natif ; son reçu autorise la livraison de ce MP4 précis.

La sixième proposition `branding/shelby-tony-style-candidate-2026-10-11.png`
a fait accepter la direction, mais l’utilisateur demandait encore une tête
plus droite. Elle n’est jamais utilisée dans le montage.

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

La recherche a ensuite retrouvé la méthode du Tony. Le sixième essai a fait
accepter le style ; le septième, frontal, est maintenant validé pour la vidéo.
Les cinq anciens fichiers sont des archives **rejetées**.
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
relatifs au dossier du toolkit. La copie de la
timeline Peaky validée reçoit ces deux chemins et
`analysis_pawn_by_speaker: false`. Enregistrer l’empreinte du PNG réellement
validé dans le manifeste ; ne jamais remplacer un asset global Tony.

Le pion apparaît dans le guide (`scene.js`), les **32 analyses**, l’outro et
son fond déjà incrusté `project-background-outro.png`. Toutes ces couches doivent
être régénérées ou reconstruites avec le bon asset. Un rafraîchissement
d’intro est insuffisant : `--refresh-intro` et `--refresh-project-intro`
refusent volontairement une empreinte de mascotte différente.

## Reprise après la validation reçue

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

La préparation privée a réutilisé les caches source, pistes audio et décisions
de montage après contrôle d’empreintes, et régénéré toutes les couches de
mascotte. Elle n’a pas modifié le MP4 existant : le nouveau film est un export
natif complet. Cet export a pris environ 26 minutes après préparation ; le
premier export avait demandé environ 15 minutes de préparation puis 31 minutes
d’export natif. Ces mesures passées ne garantissent pas les délais suivants.

## Archive et état de livraison

Le premier MP4 terminé, 15 min 27,900 s, contient encore Tony comme analyste :
**archive privée, livraison interdite depuis la correction utilisateur**. Son
empreinte est
`24308206f0147649a22af173db41e3a3f50ecedfe8178ade89f1a328cbf73e55`.
Sa QA n’approuve pas le film corrigé. Le film Shelby et sa QA technique propre
sont terminés dans le nouveau dossier. Le bilan montre 32 annotations,
dont 7 Brilliant, 7 Great, 8 Best, 0 Excellent, 2 Good, 2 Inaccuracy, 4 Mistake,
1 Blunder et 1 Book ; les images examinées montrent le seul pion frontal approuvé.
Le root a confirmé la livraison du nouveau MP4 et de son kit sur
[GoFile](https://gofile.io/d/cCuEdqOv), puis le message Discord et ses trois
pièces jointes : kit, crédits et JPG. Aucune publication YouTube réalisée.
Voir [le reçu public de livraison](PEAKY_SHELBY_DELIVERY.json) ; il ne contient
ni clé de webhook ni jeton propriétaire GoFile.

Les originaux sont natifs 720p ; les graphismes et l’export sont en 1080p.
Conserver les crédits musicaux réels de la description. Les extraits Peaky
restent protégés : aucune absence de réclamation ou monétisation garantie,
aucune modification destinée à esquiver Content ID.
