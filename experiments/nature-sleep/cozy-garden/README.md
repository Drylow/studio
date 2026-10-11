# Silent Little Worlds — jardin des lanternes

## Pause demandée — validation de l’animation attendue

L’utilisateur a rappelé qu’il avait choisi l’image, mais pas validé cette
animation. Le rendu long est suspendu et ne doit pas reprendre sans son avis.
Un aperçu animé de 16 s en 1080p, avec voix, pluie, bassin, vapeur et forme
centrale, est préparé pour cette validation. Le MP4 long partiel ne doit pas
être livré. `cozy-garden/episode-01/HOLD.json` bloque nouvel export et livraison.
Les processus suspendus sont consignés dans le résultat privé
`garden-production/long-render-paused.json` ; ne pas les relancer automatiquement.


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
- Les **41 prises AI33 sont produites**, soit 40 segments de chapitre et
  l’accueil. Leur texte représente **80 245 caractères normalisés**. Les
  résultats et l’audit des transcriptions sont privés ; ils ne remplacent
  pas une écoute de la voix ni une validation de sa qualité sonore.
- Toute modification du texte invalide son ancienne approbation. Ne pas
  réutiliser une prise sur la seule ressemblance des noms de fichiers.

Les sources vocales totalisent **6 520,007 secondes**. La timeline vocale est
maintenant assemblée et mesurée à **7 200 secondes**, avec une pause de
paragraphe calculée à **2,6008 secondes** et les respirations de chapitre.
`timeline.json`, `timeline-words.json` et `voice-timeline.flac` sont présents
dans le dossier privé. Les histoires sont continues, sans répétition pour
remplir les deux heures. Le mix et le film encodé demandent encore leurs
contrôles propres ; une timeline de deux heures n’est pas le film livré.

## Animation et habillage

Le rendu source de **60 secondes, 1920 × 1080, 30 images/s** est complet.
[close_loop.py](close_loop.py) en a tiré une boucle de **59 secondes,
1 770 images**, encodée sans perte, avec un fondu de raccord d’une seconde.
Cette boucle corrigée est maintenant contrôlée : 1 770 images vérifiées,
raccord comparé aux images voisines et huit planches effectivement revues.
Le master et les mouvements viennent de [scene.html](scene.html) et
[render.mjs](render.mjs).

La pluie animée, les impacts et cercles dans le bassin et la vapeur du thé
répondent à la dernière demande utilisateur. Reflets, feuillage discret et
respiration locale du chat complètent le mouvement. Les zones sous l’abri
doivent rester cohérentes ; la pluie ne doit pas traverser le toit.

Le code et la présence d’effets ne suffisent pas à valider leur rendu :
examiner les images effectivement exportées, la fluidité, les masques et le
raccord, puis vérifier le MP4 final. Ne pas déclarer la boucle ou les deux
heures validées avant leurs contrôles.

L’utilisateur demande aussi une **petite forme centrale organique liée à la
voix**. Le moteur [visualizer.py](episode-01/visualizer.py) la pilote par notre
narration et la laisse revenir doucement au repos pendant les pauses.
Le mix et les contrôles du fond sont terminés. Le test court du mux final
est validé : 16 s, 480 images, neuf chapitres et copie audio identique.
L’export complet avec la forme centrale est lancé. **Le film final n’est pas encore achevé**.
La forme
décrite chez Stephen Dalton n’a pas été vérifiée par lecture de sa vidéo :
voir [REFERENCE_VISUALIZER.md](REFERENCE_VISUALIZER.md). Aucun de ses médias
n’est repris dans notre production.

Sous-titres : **SRT anglais activable, 1 322 cues**, sans transcription
permanente incrustée. Contrôle exhaustif contre les 14 541 mots du script et
les timings de la timeline : aucun mot perdu ni chevauchement. Les 26 cues
initialement trop brefs ont été prolongés à une seconde ; les six fins qui
rognaient légèrement le dernier mot ont été corrigées. Rapport privé :
`output/nature-sleep/garden-production/qa/captions-review.json`, lié au SHA
exact du SRT. Ce contrôle ne prétend pas à une nouvelle écoute acoustique.
Le SRT devra être ajouté dans YouTube Studio pour que CC le propose ; cet
import et l’alignement sur le film final restent à vérifier. Cet habillage
ne garantit pas la monétisation.

## Fond sonore et fabrication

Pluie douce sur le feuillage et l’abri, petite eau du bassin, nappe musicale
originale très discrète sous la voix : [AMBIENCE.md](episode-01/AMBIENCE.md).
L’ambiance du jardin est nouvelle ; elle ne contient pas le roulement du
train. La musique est la composition originale du projet, réutilisée avec
contrôle de son empreinte. Aucun audio de Stephen Dalton n’est employé.

Le mix final est terminé et mesuré à **−19,01 LUFS / −4,98 dBTP**. Ces
mesures ne remplacent pas l’écoute du mix. La voix, les raccords entre
prises et les noms propres demandent leur propre vérification. Le contrôle SRT porte sur les timings fournis et ne
prouve pas à lui seul la synchronisation perçue de chaque mot.

Fichiers de travail privés : `output/nature-sleep/garden-production/`.
[narrate.py](episode-01/narrate.py) reprend les requêtes et contrôle les textes ;
[build.py](episode-01/build.py) assemble voix, pauses, SRT, mix et film.
Ne pas relancer aveuglément une génération payante lorsque son résultat
est incertain. Ni les sorties privées ni les réponses de services ne vont
dans le dépôt public.

## Fournisseur vocal et ordre de grandeur

L’utilisateur confirme l’usage d’**AI33** et un budget annoncé de **3 millions
de caractères**. Avec **80 245 caractères normalisés** pour cet épisode,
l’ordre de grandeur est **37 films de taille comparable avant retouches**,
essais, régénérations et autres consommations. Ce calcul n’est pas un solde
vérifié du compte ni une garantie des règles de décompte du fournisseur.

**Kokoro reste une recherche d’alternative future**. Aucune installation,
conversion de la production active ou nouvelle voix locale n’a été lancée.
Ne pas changer de fournisseur pour terminer ce film.

## Assemblage final et livraison prévue

Après présence du mix terminé et des revues SHA de la boucle, la commande
courte est désormais :

```sh
.venv/bin/python experiments/nature-sleep/cozy-garden/episode-01/build.py package
.venv/bin/python experiments/nature-sleep/cozy-garden/episode-01/build.py verify
```

`package` appelle **le rendu complet du visualiseur lié à la voix**, avec
contrôles du fond, puis extrait la miniature du film final. Il ne produit
plus l’ancien export sans orbe. `verify` doit ensuite contrôler le fichier
réel, ses empreintes et son décodage complet. Ne pas lancer cette commande
en doublon pendant l’export déjà suivi par le root.


[deliver.py](episode-01/deliver.py) prépare trois titres, description, chapitres
issus de la vraie timeline, tags, commentaire, histoire intégrale et SRT.
La timeline existe désormais ; le kit peut être préparé à partir d’elle,
mais l’upload reste conditionné aux contrôles du film final exact.

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
