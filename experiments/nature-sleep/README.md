# Silent Little Worlds — production sleep

## Premier épisode actif : le jardin des lanternes

Le 11 octobre 2026, l’utilisateur confirme le nouveau nom **Silent Little Worlds**
et indique avoir mis sa chaîne à jour après l’indisponibilité de l’ancien @.
Cette confirmation vient de lui ; le compte et le nouvel identifiant n’ont pas
été vérifiés indépendamment ici. Quiet Little Worlds est désormais le nom historique.

**Le décor A du jardin est choisi** pour le premier film de deux heures :
pergola, chat Pip sur une couverture, lanterne, serre éclairée à gauche et bassin
à droite. Le [dossier actif](cozy-garden/README.md) remplace le train comme
premier épisode. Le [master A](cozy-garden/A-lantern-garden.png) est conservé ;
sa [version propre](cozy-garden/assets/garden-clean.png) retire la pluie figée
en gardant la composition, pour permettre les mouvements demandés.

Au point d’état actuel :

- **9 textes anglais, 14 541 mots**, accueil et huit histoires originales dans
  le même jardin clos ; [relecture et SHA figés](cozy-garden/episode-01/script-review.json).
- **41 prises AI33 complètes**, 80 245 caractères normalisés ; sources vocales
  de 6 520,007 s, assemblées en une timeline de **7 200 s** avec pauses naturelles.
- **Boucle 1080p30 terminée et contrôlée** : les 60 s sources sont raccordées
  en **59 s / 1 770 images**, fondu d’une seconde sans perte. Huit planches revues.
  Pluie, impacts et cercles sur le bassin, vapeur, reflets, feuillage et chat animés.
- **Petite forme centrale liée à la voix** prête pour le rendu long. Un test
  court du mux est validé, audio copié identique au mix ; export final lancé,
  contrôle du film complet et livraison restent à terminer.
- **Ambiance pluie/eau et musique originale discrète** :
  [provenance et contrôles des stems](cozy-garden/episode-01/AMBIENCE.md).
- **Mix terminé : −19,01 LUFS / −4,98 dBTP** ; aucune musique de la référence reprise.
- **SRT anglais activable, 1 322 cues contrôlés** contre l’intégralité du texte
  et des timings fournis, sans chevauchement. Les cues brefs ont été corrigés.
  Pas de transcription incrustée en permanence.

**Aucun long jardin terminé ni livré sur GoFile ou Discord à cette étape.**
La timeline vocale est bien de 2:00:00 ; le MP4 final avec visualiseur reste à
exporter et à contrôler. L’alignement SRT a été vérifié numériquement, sans
nouvelle écoute acoustique ni import YouTube revendiqués. Les mesures seules
ne constituent pas une validation artistique ou sonore du film complet.

**AI33 est confirmé par l’utilisateur**. Sur les 3 millions de caractères
annoncés, cet épisode représente environ **37 films de taille comparable
avant retouches**, essais et autres consommations ; ce n’est pas un solde
vérifié du compte. **Kokoro : recherche future seulement**, aucune installation
ni substitution de la voix en cours.

La [nouvelle bio](cozy-garden/channel-bio-en.txt) est prête, sans nouvel envoi.
Le kit nom/bio/avatar précédent a déjà été reçu sur Discord, confirmé par
l’utilisateur ; ne pas le renvoyer en doublon. Le salon conserve le binding
privé **DISCORD_WEBHOOK_QUIET_LITTLE_WORLDS** malgré le changement de nom.
Aucune valeur de webhook ou réponse privée de service ne doit entrer dans Git.

Le [helper de livraison](cozy-garden/episode-01/deliver.py) prépare trois titres,
miniature, description, histoire et SRT depuis la timeline maintenant présente.
`cozy-garden/episode-01/build.py package` appelle désormais le rendu complet
avec visualiseur, puis `verify` contrôle le fichier exact. Les gardes SHA,
reçus et verrous sont conservés. Aucun upload ou message ne doit être
présenté comme envoyé avant confirmation ; aucune publication YouTube n’a été
réalisée pour cet épisode.

## Référence étudiée et projet chess

[670 uploads publics de Stephen Dalton](cozy-garden/reference-stats.json) ont
été récupérés, dont 560 vidéos longues analysées. Les comparaisons portent
sur des compteurs cumulés et des cohortes ; ce ne sont ni des Analytics privés
ni une garantie de performance. Le détail de sa forme centrale animée n’a pas
été vérifié en vidéo : [limites de la recherche](cozy-garden/REFERENCE_VISUALIZER.md).
Notre voix, nos textes et notre musique ne reprennent pas ses médias.

La recherche parallèle [Inglourious Basterds](../conversation-chess/BASTERDS_RIGHTS_RESEARCH.md)
est terminée. Le film est protégé, avec une piste de licence Universal Clips
à obtenir et à préciser pour l’usage envisagé. **Aucun montage ni test YouTube
lancé ; aucune absence de claim garantie.** Les titres chess doivent garder
**Analyzed Like Chess**. Ne pas affirmer que Landa reconnaît Shosanna : le film
entretient cette incertitude.

Peaky Tommy/Alfie a été livré, publié puis supprimé par l’utilisateur après
une réclamation audiovisuelle avec blocage territorial. Voir le
[protocole de droits](../conversation-chess/COPYRIGHT_RELEASE.md) avant toute
nouvelle livraison finale ; la qualité technique n’établit pas une licence.

## Archive récente — train en réserve

Le [train A](night-train/README.md) avait été choisi et son aperçu de 24 secondes
livré. Un prototype de deux heures a ensuite été produit et contrôlé
techniquement, puis placé sous `night-train/episode-01/HOLD.json` lorsque
l’utilisateur a préféré le jardin pour la première vidéo. **Ce long n’a jamais
été envoyé sur GoFile ou Discord.** Son MP4 dérivé a été supprimé pour libérer
de la place ; sources, boucle, voix, mix et reconstruction sont conservés.
Ne pas le livrer ou le relancer à la place du jardin.

Les trois propositions du reset précédent — A train, B maison de thé dans
l’arbre, C refuge miniature — restent dans [cozy-reset-2026-10-11/](cozy-reset-2026-10-11/).
Le cottage pixel art, le saule, la grenouille et les anciennes scènes marines
sont des directions rejetées. Les sections suivantes relatent ces étapes
antérieures ; elles ne décrivent pas la production active ci-dessus.

## Anciennes propositions — archives

- **A — jardin nocturne cinématographique** : feuillage détaillé, mare,
  profondeur et lumière lunaire. Le prompt demandait de la peinture, mais
  le résultat paraît proche du réalisme ; ne pas le décrire comme une gouache.
- **B — macro réaliste** : mare vue au ras du sol, profondeur de champ,
  feuillages humides, grenouille et escargot. Image générée, pas une photo réelle.
- **C — illustration botanique douce** : contours fins, textures aquarellées,
  palette du crépuscule et vie discrète. Première proposition recommandée.

Les trois scènes sont originales et indépendantes des anciens décors marins
rejetés. C est choisi pour l’aperçu par délégation de l’utilisateur ; aucune
validation visuelle explicite de cette image n’est enregistrée. Le nombre de pixels
mesuré dans le manifeste est la résolution réelle ; aucun master natif 4K.
Les détails figurés ne servent pas de preuve biologique ou de prise de vue.

## Archive — avatar fougère et lune

[Avatar fougère, lune et luciole](branding/avatar-fern-moon.png), sans texte,
fond opaque, composition centrale destinée au recadrage circulaire YouTube.
Il ne reprend pas l’ancien avatar méduse. Son envoi a été demandé par
l’utilisateur, qui confirme le nom, la bio et l’image reçus dans Discord.

## Archive — premier nom choisi et autres pistes

1. **Quiet Little Worlds — @QuietLittleWorlds**, premier nom choisi explicitement, remplacé depuis par Silent Little Worlds.
2. **Glowfern Stories — @GlowfernStories**.
3. **Little Wilds Sleep — @LittleWildsSleep**.

Recherche de collisions dans les index publics : aucun homonyme exact repéré
dans les réponses exploitables, avec des contrôles limités pour les deux
derniers noms. **Aucun @ confirmé disponible ou réservé.** Certaines recherches
ont été élargies par le moteur ou limitées. Le choix ne vaut pas confirmation
de disponibilité ; celle-ci se vérifie dans YouTube lors de la création.
Voir [recherche de noms](NAME_RESEARCH.md) et [résumé](name-research.json).

## Archive — première bio proposée

> Slow stories. Small worlds. Deep rest.
>
> Gentle bedtime stories for adults, inspired by moss gardens, moonlit ponds,
> quiet greenhouses, and the hidden wonders of nature.
>
> Settle into peaceful little worlds with soothing narration, soft natural
> ambience, and calm visuals.
>
> Take a breath. Let the world grow quiet.

Dans chaque futur épisode, distinguer histoire naturelle documentée et
promenade imaginaire. Vérifier les faits annoncés comme réels. La bio définit
le thème de la chaîne sans prétendre que des épisodes sont déjà publiés.

## Ancien aperçu C — rejeté par l’utilisateur

Créer un aperçu court uniquement du style choisi : reflets légers, feuillage
discret, lucioles lentes et, éventuellement, une dérive de caméra imperceptible.
Éviter flashes, mouvements brusques et variations de volume. Utiliser le
décor choisi comme référence puis contrôler les images du film effectivement
exporté et le raccord avant de le montrer. Aucun appel Algrow ni génération
vidéo nécessaire ; la préparation des mouvements peut être codée.

[Aperçu C — 24 secondes, 1080p30, sans son](https://gofile.io/d/VOaYXcYo) :
eau, feuillage et petites lucioles très discrètement animés, cadrage fixe.
Les 720 images ont été décodées sans erreur ; captures du film revues par
l’auteur, un examinateur indépendant et le root. Le raccord du shader est
exact ; celui du MP4 conserve les différences de compression. Aucune lecture
continue revendiquée. L’utilisateur a depuis rejeté cet aperçu. Voir
[preuve de livraison](PREVIEW_DELIVERY.json) et [moteur](animation/README.md).
À cette étape ancienne, le premier nom était choisi et le kit de branding livré
dans Discord, confirmé par l’utilisateur. Aucun long ni voix n’avait alors été lancé.
Voir BRANDING_DELIVERY.json : le contrôle API des pièces jointes a échoué,
mais l’utilisateur confirme les trois éléments reçus ; aucun doublon envoyé.
Le webhook dédié est enregistré dans les .env privés local et serveur,
sans clé dans le dépôt. À cette étape ancienne, aucun compte YouTube n’avait
encore été créé ou renommé par l’agent ; l’état actuel figure en tête de ce document.
