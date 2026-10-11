# Silent Little Worlds — jardin des lanternes

## État actif — 11 octobre 2026

L’utilisateur confirme avoir renommé sa chaîne **Silent Little Worlds**, après
l’indisponibilité de l’ancien identifiant Quiet Little Worlds. La mise à jour
de la chaîne et de son identifiant est rapportée par lui ; aucun contrôle
indépendant du compte ou de la disponibilité du nouvel @ n’est consigné ici.
La [bio anglaise renouvelée](channel-bio-en.txt) est prête. Ne pas renvoyer le
kit de branding déjà reçu sans nouvelle demande.

**Premier épisode : le jardin A est choisi.** Le train reste en réserve.
Le master est [A-lantern-garden.png](A-lantern-garden.png) : abri/pergola,
banc de bois, couverture crème, chat roux, tasse, lanterne, serre éclairée à
gauche et bassin à droite. B est une proposition non retenue. La source de
production [assets/garden-clean.png](assets/garden-clean.png) conserve cette
composition en retirant la pluie figée, afin de l’animer séparément.

**Production en cours, aucune vidéo jardin de deux heures terminée ou livrée.**
Aucun lien GoFile, message Discord ni publication YouTube du film final ne
doit être présenté comme acquis à cette étape. Le choix du décor et la
demande du long autorisent le travail ; ils ne constituent pas une revue du
rendu final encore en cours de fabrication.

## Récit et voix

L’accueil et les huit histoires anglaises sont terminés : **9 textes,
14 541 mots et 244 paragraphes**. Il s’agit de fiction originale dans un seul
petit jardin clos et ses dépendances, explicitement présentée comme une
promenade imaginaire depuis le banc. Le texte du train n’a pas été conservé
comme simple narration posée sur une autre image.

Les huit chapitres suivent Elias et les lanternes, June dans la serre, Ada
et sa couverture, Niall au salon de lecture, Ruth près du bassin, Tomas dans
la cuisine du jardin, Iona à la bibliothèque de graines, puis Mara et Pip
sous la pergola lorsque le jardin se repose.

- Textes : [episode-01/script/](episode-01/script/).
- Relecture : [CONTENT_REVIEW.md](episode-01/CONTENT_REVIEW.md).
- Approbation des **octets exacts**, liée aux SHA-256 :
  [script-review.json](episode-01/script-review.json).
- La voix est en production : **40 segments de chapitre et un accueil** dans
  le plan de narration. Ne pas confondre ce nombre avec des prises toutes
  déjà terminées et contrôlées. Les résultats privés font foi.
- Toute modification du texte invalide son ancienne approbation. Ne pas
  réutiliser une prise sur la seule ressemblance des noms de fichiers.

La durée finale doit être mesurée puis assemblée à **2:00:00** avec des pauses
naturelles. La seule quantité de mots ne prouve pas la durée. Les histoires
ne doivent pas être répétées pour remplir les deux heures.

## Animation et habillage

Une boucle **60 secondes, 1920 × 1080, 30 images/s** est en cours de rendu avec
[scene.html](scene.html) et [render.mjs](render.mjs). La dernière demande de
l’utilisateur insiste sur la pluie animée, les impacts et cercles dans le
bassin, ainsi que la vapeur du thé. Le travail comprend également reflets,
feuillage discret et respiration locale du chat. Les zones sous l’abri
doivent rester cohérentes ; la pluie ne doit pas traverser le toit.

Le code et la présence d’effets ne suffisent pas à valider leur rendu :
examiner les images effectivement exportées, la fluidité, les masques et le
raccord, puis vérifier le MP4 final. Ne pas déclarer la boucle ou les deux
heures validées avant leurs contrôles.

L’utilisateur demande aussi une **petite forme centrale organique liée à la
voix**. Un prototype original est en préparation, à relier à l’enveloppe de
notre narration et à laisser revenir doucement au repos pendant les pauses.
Son intégration et son contrôle dans le film final restent à faire. La forme
décrite chez Stephen Dalton n’a pas été vérifiée par lecture de sa vidéo :
voir [REFERENCE_VISUALIZER.md](REFERENCE_VISUALIZER.md). Aucun de ses médias
n’est repris dans notre production.

Sous-titres : fichier **SRT anglais activable**, sans transcription permanente
incrustée. Le SRT devra être ajouté dans YouTube Studio pour que le bouton CC
propose ces sous-titres. Cet habillage ne garantit pas la monétisation.

## Fond sonore et fabrication

Pluie douce sur le feuillage et l’abri, petite eau du bassin, nappe musicale
originale très discrète sous la voix : [AMBIENCE.md](episode-01/AMBIENCE.md).
L’ambiance du jardin est nouvelle ; elle ne contient pas le roulement du
train. La musique est la composition originale du projet, réutilisée avec
contrôle de son empreinte. Aucun audio de Stephen Dalton n’est employé.

Les contrôles numériques des stems ne remplacent pas l’écoute du mix final.
La voix, les raccords entre prises, les noms propres, les niveaux et le
timing des sous-titres demandent leur propre vérification.

Fichiers de travail privés : `output/nature-sleep/garden-production/`.
[narrate.py](episode-01/narrate.py) reprend les requêtes et contrôle les textes ;
[build.py](episode-01/build.py) assemble voix, pauses, SRT, mix et film.
Ne pas relancer aveuglément une génération payante lorsque son résultat
est incertain. Ni les sorties privées ni les réponses de services ne vont
dans le dépôt public.

## Livraison prévue

[deliver.py](episode-01/deliver.py) prépare trois titres, description, chapitres
issus de la vraie timeline, tags, commentaire, histoire intégrale et SRT.
Le kit ne doit pas être exécuté avant la présence de cette timeline.

Nom du film attendu :
`Silent-Little-Worlds-The-Lantern-Garden-2-Hours.mp4`.
Le JPG et le SRT portent également le préfixe `Silent-Little-Worlds`.
L’upload exige les revues technique et éditoriale liées au SHA du MP4 ; les
reçus, marqueurs d’envoi incertain et verrou Discord sont conservés.

Le salon Discord déjà autorisé conserve la variable privée
**DISCORD_WEBHOOK_QUIET_LITTLE_WORLDS**, malgré le nouveau nom public.
Ne pas renommer ce binding, choisir un autre salon ou diffuser sa valeur.
L’envoi prévu contient le lien GoFile et les quatre pièces du kit ; aucun
doublon du branding et aucune publication automatique YouTube ne sont prévus.

## Recherche de référence et autre chantier

[reference-stats.json](reference-stats.json) conserve **670 uploads récupérés**
de Stephen Dalton, dont 560 vidéos d’au moins trente minutes analysées, avec
comparaisons de cohortes. Les compteurs sont les vues cumulées publiques à
la date de collecte ; ce ne sont ni des Analytics privés, ni un taux de
réussite prévisible pour notre chaîne. Ils ne prouvent pas la cause d’une
performance ou le contenu sonore et visuel d’une vidéo non visionnée.

La recherche parallèle sur *Inglourious Basterds* est terminée :
[rapport de droits](../../conversation-chess/BASTERDS_RIGHTS_RESEARCH.md).
Le film est protégé ; une piste de licence existe chez Universal Clips,
fiche 13373. Aucune licence, absence de claim ou disponibilité monétisable
n’est acquise. Aucun téléchargement, montage ou test YouTube n’a été lancé.

Le [train](../night-train/README.md) est une archive en réserve sous `HOLD.json`.
Son prototype long a passé ses contrôles techniques mais n’a jamais été
envoyé. Son MP4 dérivé de deux heures a été supprimé pour libérer de la place ;
sources, boucle, voix, mix et éléments de reconstruction sont conservés.
