# Outils pour reprendre la production

Lire [CHANNELS.md](CHANNELS.md) pour les identités, formats et vidéos terminées,
puis [POSTING_HANDOFF.md](POSTING_HANDOFF.md) pour le travail de publication à
automatiser. Ne pas confondre cette automatisation future avec la livraison
GoFile déjà terminée.

## Application et API maintenues

- Application complète : `production/tubeforge_base/`.
- Ajouts et contrôles : `production/tubeforge_support/`.
- Client personnel, guide et routes :
  [forge_docs/README.md](../tubeforge_support/forge_docs/README.md),
  [forge.py](../tubeforge_support/forge_docs/forge.py),
  [LLM.txt](../tubeforge_support/forge_docs/LLM.txt),
  [endpoints.json](../tubeforge_support/forge_docs/endpoints.json).
- API, files de travaux et contrats de lieux : `forge_api.py`, `forge_queue.py`,
  `workspace_locations.py` dans `production/tubeforge_support/`.
- Déploiement et accès hôte : les guides existants de `production/tubeforge_host/`
  et `production/tubeforge_workspace.py`. Ne pas redéployer ou redémarrer un
  serveur occupé simplement pour fabriquer un contenu.

Le service normal est `https://tools.kanye.studio/api/forge/v1` ; les projets
et références détaillés passent aussi par `/api/2d/api/workspace`. On utilise
une connexion **personnelle de membre**. Les clés, sessions, webhooks, mots de
passe et le ZIP SSH sont privés et ne font pas partie du dépôt public. Il n'y a
pas d'archive de l'application à réclamer : elle est déjà versionnée.

## Ordre de travail pour les chaînes historiques

1. Recherche sourcée puis narration anglaise originale de 15–20 minutes, validée
   avant voix/images. Le titre, les détails historiques et les choix de chaîne
   restent ceux de la fiche concernée.
2. Références réellement vues : personnages et costumes stables, maître par lieu,
   variantes explicites de lumière/angle/état. Chaque plan ajoute une action ou
   une information pertinente, pas seulement un zoom d'une même image.
3. Voix sur le VPS avec la configuration sauvegardée de la chaîne ; télécharger
   la voix complète et son horloge. Les paroles effectives définissent les durées
   des plans, chapitres et sous-titres.
4. Prompts et références ordonnées écrits explicitement. Le code exécute sans les
   réécrire. Générations réparties selon la limite existante du fournisseur et du
   serveur ; contrôler chaque image puis corriger uniquement les plans concernés.
5. Enregistrer les vrais résultats et vraies inspections dans les registres ;
   garder les tentatives rejetées et les reçus. Une référence seule ne prouve pas
   que l'image finale est cohérente.
6. Rendu visuel natif sur le VPS, contrôle complet technique et inspection réelle
   du film échantillonné aux scènes/coupes, puis quatre miniatures distinctes,
   texte de publication, chapitres et SRT dans chaque GoFile.

Le client ne démarre pas toutes les étapes tout seul. Un HTTP202 accepte une
tâche ; il ne prouve pas que le film existe. Une file peut attendre de vraies
inspections. Après un délai ou une coupure, vérifier l'état réel avant de rejouer
une requête payante. Un changement de voix exige une nouvelle horloge de montage.

## Finition et livraison réutilisables

[production/history_delivery/README.md](../history_delivery/README.md) donne
les dépendances, profils d'épisode, commandes et schémas attendus. Les outils
portables couvrent le téléchargement authentifié du rendu terminé, la
normalisation mesurée de la voix, le remux sans réencodage vidéo, la QA complète,
les sous-titres exacts, la conservation des preuves et la livraison réelle de
sept fichiers. Les chemins de travail et identifiants sont des arguments/profils,
pas les anciens chemins de cette machine.

Pour Viking/Pirate, le VPS a produit les visuels et le montage natif. Le son natif
était faible : une finition locale a normalisé le volume puis recopié les paquets
vidéo sans réencoder. On conserve séparément le MP4 natif, la voix native, le FLAC
normalisé et le MP4 livré, leurs SHA et la preuve de paquets/timings identiques.
Ne pas présenter le SHA du dérivé comme celui du téléchargement natif.

Le contrôle automatique **n'invente jamais les PASS visuels**. Il produit les
planches des vrais frames encodés et laisse la revue en attente. Le prochain
opérateur les regarde réellement et note qui a inspecté quoi. Le niveau audio,
le nombre de frames et les sept contrôles de synchronisation sont mesurés, pas
affirmés depuis le seul script.

Les anciennes migrations de cette session étaient ciblées : création des deux
projets, import des maîtres/personnages/frames déjà générés, annotations natives
et nouvelle horloge officielle. Leurs boucles de génération/import spécifiques,
les chemins éphémères et l'état privé ne sont pas copiés comme une fausse
pipeline universelle. Pour une prochaine vidéo, utiliser les **routes actuelles
documentées** et les contrats du code natif. Le constructeur portable des preuves
accepte le même registre d'import seulement si ses reçus réels existent ; il ne
reconstruit pas une preuve manquante à partir du nom d'un fichier.

Les deux sources vikings récupérées sans reçu associé sont conservées comme
visuellement inspectées mais avec association des arguments incertaine. Les
annotations de lieu ajoutées ensuite ne sont pas attribuées rétroactivement aux
requêtes du générateur. Les quatre exports miniatures de chaque film sont en
3840×2160 ; leurs originaux sont plus petits, sans promesse de détail natif4K.

GoFile : même compte légitime, même profil navigateur privé ; aucun nouveau
compte invité et aucune simulation d'authentification. Les fichiers créent un
nouveau dossier, les MD5/taille retournés sont comparés, puis la page normale est
observée avec ses sept noms et une capture fraîche. Ne pas contourner l'API de
listing réservée au Premium. Un résultat POST incertain se réconcilie ; il ne se
relance pas à l'aveugle.

## Vérification de cette passation

Les sept tests locaux couvrent le son et le remux réels sur une courte vidéo
synthétique, la protection d'accès du client et les garde-fous du lecteur
GoFile. Dix cas de transport sont des mocks explicitement nommés. Le constructeur portable des preuves a également vérifié 1341 points du vrai
registre Viking déjà sauvegardé, hors réseau. Les deux véritables kits terminés ont également passé le validateur portable hors réseau,
avec leurs sept fichiers et toutes leurs preuves existantes. La passation n'a
déclenché ni génération payante, ni nouveau rendu, ni envoi GoFile.

La disponibilité de l'application ne prouve pas l'automatisation YouTube. Les
droits des comptes, OAuth/profils, association chaîne/destination, anti-doublon,
vraie publication et statut réel doivent être vérifiés dans le travail séparé
décrit par la fiche de publication.
