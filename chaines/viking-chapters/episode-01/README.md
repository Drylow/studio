# Viking Chapters — épisode 01 livré

**Why Being a Viking Was Worse Than You Think** · anglais · 19 min 26 s · 88 plans.
Le film final est dans le [GoFile livré](https://gofile.io/d/Zd5AhFJi). L’utilisateur poste
manuellement ; aucune publication de cette chaîne n’a été automatisée pendant cette production.

Eirik est un agriculteur norrois fictif vers 950, avec sa partenaire Aslaug. Son parcours
va de la ferme au voyage saisonnier vers l’Angleterre, au commerce, au retour, à l’hiver
et au règlement d’un différend. Les sources et leurs nuances sont dans `research/` ;
ce scénario illustre une époque, pas une biographie réelle ni la vie identique de tous les Scandinaves.

## Reprendre le montage et les prochaines vidéos

1. Lire `script-en.txt`, `editorial/storyboard.json` et les faits sourcés.
2. Pour le film livré, utiliser **`editorial/authored-scene-prompts-vps-clock.json`**,
   `official-vps-aligned-words.json` et `official-vps-paragraph-clock.json`.
   Le fichier `authored-scene-prompts-original-clock.json` est un historique : son ancienne
   voix n’est pas celle du rendu final et ses timings ne doivent pas être mélangés aux nouveaux.
   Le projet natif livré est `why-being-a-viking-was-worse-than-you-th-cca49f`.
   `original_editorial_project_id` identifie l’ancien projet local et ne doit pas être
   utilisé pour lancer ou modifier le projet distant ; utiliser `native_vps_project_id`.
3. `provenance/selected-generation-plan.json` distingue la direction déclarée, les arguments
   réellement associés au PNG choisi et les annotations de l’import sur le VPS.
   Les références sont ordonnées ; un ancien plan utilisé comme ancre de correction
   n’est pas un nouveau décor maître. Ne jamais les remplacer ou changer leur ordre automatiquement.
4. Réutiliser les personnages, décors et variantes réellement relus dans `assets/masters/registry.json`.
   `editorial/visual-bible-v1.md` conserve la bible initiale ; les groupes et variantes
   ajoutés et relus ensuite sont dans le registre actuel. Les définitions de prompts maîtres
   et les arguments réellement sauvegardés sont séparés dans `provenance/master-generation/`.
   Eirik : barbe rousse, tunique teal, cape brune, chaussures de cuir, mains noires.
   Aslaug : robe mauve et coiffe claire. Les scènes ordinaires restent sans armes et sans casque.
   Aucun casque à cornes, château fantaisie, accessoire moderne ou texte généré dans les scènes.
5. Les 88 PNG choisis dans `assets/scenes/` sont les vrais originaux, copiés sans recompression.
   Le rendu visuel natif a été réalisé sur le VPS. La finition audio a ensuite normalisé le
   niveau avec le même nombre de samples, puis remuxé en `-c:v copy`. Le hash du film final
   est différent du rendu natif ; les paquets vidéo et leurs timings sont identiques.
6. Les quatre miniatures sont dans `thumbnails/` : gros texte jaune bord noir, visages
   expressifs et décor d’époque, comme le kit Samurai. Leurs JPG 3840×2160 sont des exports
   agrandis des PNG natifs d’environ 1672×941, pas une génération de détail natif 4K.
7. Les contrôles réels et planches du film encodé sont dans `evidence/`. La revue visuelle
   couvre tous les milieux de plans, toutes les coupes, la première et dernière image ;
   la lecture technique complète des deux flux est prouvée séparément. Cela ne prétend pas
   qu’un humain a regardé chacune des 27 980 images du film à vitesse réelle.
8. `delivery/UPLOAD.txt`, `upload-metadata.json` et `English-Captions.srt` sont ceux réellement livrés.
   Faire valider le choix de miniature et le créneau avant une nouvelle publication.

## Limites de provenance conservées

Les plans **41 et 71** ont été récupérés parmi les PNG originaux après l’interruption de
leurs workers. Les images ont réellement été relues et acceptées, mais le reçu de sortie
est absent et leur association exacte au prompt reste **non confirmée**. La direction
candidate ne doit jamais être présentée comme un argument effectivement envoyé.

`asset-provenance-manifest.json` donne le SHA256 de chaque fichier copié et de chaque
dérivé volontaire, ainsi que celui de sa source. Les JSON portables sont des dérivés
documentaires, pas de faux reçus historiques. Un champ `historical-artifact:` est un
identifiant de preuve exclue, pas un chemin à ouvrir. Quand une preuve originale pointait
vers un JSON maintenant assaini, `original_recorded_sha256` conserve le hash historique ;
le hash réel du dérivé est dans le manifeste. Les sources originales hors du dépôt restent intactes.

Les MP4, voix intermédiaires/FLAC, caches, reçus bruts, réponses encodées, clés, SSH et sessions de
navigateur ne sont pas dans ce dépôt public. La voix officielle actuelle peut être ajoutée
séparément sous `audio/narration-api.mp3` par la passation générale, avec son SHA vérifié.
Récupérer le MP4 final dans le GoFile ;
l’accès privé au projet natif et les outils TubeForge sont documentés dans la passation générale.
