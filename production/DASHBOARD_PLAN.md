# Nouveau dashboard — Edgerunners Studio

Cadrage du 5 octobre 2026. La première version du site est construite ; voir
`DASHBOARD_STATUS.md` pour les fonctions disponibles, les essais et les étapes restantes.
Ce document conserve le périmètre complet, y compris l'automatisation encore à terminer.

## Décisions confirmées par l'utilisateur

- Nom du site : **Edgerunners Studio**, en un mot avec un S. Le dépôt et les noms
  techniques des bases restent compatibles avec les données existantes.
- Refaire **toute l'interface de A à Z**, y compris les anciens studios de création.
  Garder les outils de production développés récemment et les contenus existants.
- Un seul site pour gérer toutes les chaînes, produire, organiser et publier.
- Deux utilisateurs au départ : l'utilisateur et son collègue, dans un espace partagé.
- Autonomie **par chaîne** : validation humaine sur certaines, publication entièrement
  automatique sur d'autres. Cage Dispatch et Pitch Dispatch sont destinées au mode automatique.
- Direction visuelle très travaillée, inspirée de Cyberpunk 2077 et Edgerunners.
- Hébergement sur un domaine personnel possible ensuite ; ne pas déployer maintenant.
- Conserver le thème des miniatures vidéo déjà approuvées, indépendamment du thème du site.
  Références : `presets/news_thumbnails/approved_2026-10-05/`.

Le choix du mode automatique autorise l'agent à choisir sujets, titres, miniatures et
créneaux dans les règles de la chaîne, sans redemander une validation pour chaque vidéo.
Il ne dispense jamais des contrôles de faits, droits et qualité avant publication.

## Ce qu'on doit voir immédiatement

L'accueil répond à quatre questions : **qu'est-ce qui sort aujourd'hui, combien de
vidéos sont prêtes, quelles chaînes manquent de contenu, qu'est-ce qui est bloqué ?**

Chaque chaîne affiche son mode, sa prochaine publication, ses vidéos prêtes et sa
couverture du calendrier. Pour un format intemporel, afficher les jours d'avance
réellement couverts par les créneaux et les vidéos éligibles. Pour l'actualité,
afficher la fraîcheur des sujets et le prochain créneau : une vieille actualité ne
constitue pas un stock utile. Les seuils de fraîcheur et les cadences sont configurables.

Les trois analyses sportives livrées le 5 octobre sont des livraisons Discord avec
publication manuelle rapportée par l'utilisateur. Ne pas les marquer « publiées sur
YouTube » sans confirmation ou import du lien. Une livraison Discord est un état distinct.

## Les pages du site

| Page | Fonction principale |
| --- | --- |
| Vue d'ensemble | Publications du jour, stock par chaîne, travaux en cours, actions et alertes. |
| Chaînes | Fiche, connexion YouTube, format, langue, voix, style, cadence, stock cible et autonomie. |
| Radar d'actus | Flux datés, fraîcheur, sujets déjà traités, sources configurables et fiche de recherche. |
| Production | Tableau des vidéos : idée, recherche, script, création, contrôle, prête, programmée, publiée ou bloquée. |
| Calendrier | Vue semaine/mois, déplacement des créneaux, filtres par chaîne et avertissements de conflit. |
| Tâches | To-do partagée : responsable, échéance, priorité, lien vers une chaîne ou une vidéo. |
| Studio vidéo | Création guidée selon le format, script, sources, voix, visuels, montage, miniature et aperçu. |
| Bibliothèque | Médias, références de style, sources, preuves de droits et anciennes productions. |
| Réglages | Comptes, connexions, budgets, notifications et règles d'automatisation. |
| Delamain | Conversation et actions persistantes de préparation, recherche et production. |

L'agent **Delamain** reste accessible depuis toutes les pages dans un panneau latéral.
Il peut expliquer les problèmes, proposer un programme, créer des tâches, rechercher
un sujet, préparer une vidéo et piloter les outils. Ses actions affichent un état et
un résultat réel. Les règles de la chaîne déterminent s'il doit attendre une validation.

## Parcours à rendre complets

1. **Création manuelle** : choisir une chaîne et un sujet → produire avec ses réglages
   → suivre les étapes → consulter la vidéo et la miniature → valider si nécessaire
   → publier maintenant, programmer ou récupérer le paquet Discord.
2. **Chaîne avec validation** : l'agent prépare les vidéos → elles arrivent dans
   « À valider » → l'un des deux utilisateurs accepte ou demande une correction →
   le créneau confirmé est exécuté. Toute modification du rendu invalide son ancienne validation.
3. **Chaîne automatique** : collecte d'actualités → dédoublonnage et vérification
   → choix d'un sujet récent → création → contrôles → publication au créneau autorisé.
   Si un contrôle échoue, corriger ou remplacer le contenu ; sinon bloquer et afficher
   une explication précise. Ne jamais contourner le blocage pour tenir la cadence.
4. **Après-match** : attendre une fin de match confirmée → recueillir score et
   comptes rendus sourcés → produire le résumé. Un seul score ne suffit pas à inventer une analyse.
5. **Travail à deux** : chacun a son compte, les mêmes données et un journal d'actions.
   Un double clic ou deux utilisateurs ne doivent pas créer deux rendus ou deux publications.

Dates affichées en français, fuseau **Europe/Paris** (heure belge). Stocker les dates
avec fuseau et gérer les changements d'heure ; le navigateur ne décide pas de l'heure de publication.

## Fonctions supplémentaires retenues dans le plan

- **Pause générale** et pause par chaîne, visibles et effectives côté serveur.
- Budget quotidien et par vidéo, coûts enregistrés et avertissement avant dépassement.
- Alertes utiles : stock insuffisant, sujet périmé, rendu arrêté, connexion expirée,
  contrôle échoué. Notifications Discord dans le salon de la chaîne.
- Recherche dans vidéos, tâches et sources ; filtres par chaîne et statut.
- Suivi des performances ensuite, lorsque les autorisations YouTube correspondantes
  sont disponibles. Ne pas afficher de faux taux de clics ou de revenus.

## Direction visuelle

Fond noir bleuté, jaune électrique dominant, cyan pour les informations et rose
Edgerunners en accent. Panneaux aux angles découpés, lignes de console, typographie
lisible, skyline et illustrations originales. Références à Night City, Delamain
et Afterlife dans l'identité visuelle ; labels fonctionnels en français.

Créer un univers cohérent sur toutes les pages, pas seulement un habillage de l'accueil.
Animations discrètes, états de chargement et erreurs soignés, contrastes lisibles,
navigation clavier, option de réduction des animations et version mobile utilisable.
Les compteurs affichent des données réelles ou un état vide explicite.

## Ce qu'on réutilise et ce qu'on remplace

**À conserver et intégrer derrière la nouvelle interface :**

- Chaînes Oddly : `services/pov_engine.py`, scripts et pipeline `production/`,
  références et fiches de `chaines/`.
- Documentaires : services History, `production/history_video.py`, moteur
  `history_engine/`, bibles et projets existants.
- Actualités sportives : `services/newsvid.py`, `production/news.py`,
  `production/news_brief.py`, recherche après-match, contrôles des droits et livraison Discord.
- Connexion/publication YouTube existante dans `routes/youtube.py`, à adapter aux
  nouveaux comptes et contrôles. Données utiles de `database.py` et anciens projets.

**À remplacer puis supprimer lors de la bascule :** ancien accueil, Delamain,
pages de catégories, cadres d'outils, anciennes interfaces de `tool_apps/`, anciens
styles/scripts et écrans de connexion/administration. Supprimer les dépendances
d'interface devenues inutiles après vérification. Les anciens liens utiles
redirigent vers leur équivalent dans le nouveau studio.

Les anciens catalogues d'outils ne reviennent pas dans la navigation. Les fonctions
récentes sont intégrées au Studio vidéo. Aucun effacement des vidéos, projets,
références, base de données ou secrets pour nettoyer l'affichage.

## Construction et validations

### 1. Nouveau site et reprise des données

Créer la navigation et les écrans Cyberpunk, les deux comptes et l'espace partagé.
Relier les premières vues aux chaînes et productions présentes dans le dépôt.
Remplacer toutes les anciennes interfaces ; procéder à leur suppression avec la
bascule fonctionnelle, pour garder une application utilisable pendant la refonte.

Approche technique : interface modulaire React/TypeScript avec Vite ; conserver
Flask et les moteurs de production côté serveur. Ajouter des migrations versionnées
et une sauvegarde préalable des données, sans réinitialiser la base existante.
Les clés restent côté serveur ; aucun équivalent public de `tool_apps/config.js`.
Remplacer la séparation actuelle boss/guest par des comptes individuels capables
de travailler sur le studio, avec permissions explicites pour les connexions et réglages.

Validation : vues ordinateur/mobile, navigation, comptes séparés, absence de secrets
dans le navigateur, données conservées et anciens liens traités.

### 2. Organisation et création de bout en bout

Rendre persistants les réglages des chaînes, les tâches, les créneaux et le tableau
de production. Brancher les formats récents avec des adaptateurs, sans réécrire leurs
moteurs. Une fiche vidéo relie sources, script, fichiers, étapes, coût, contrôles et publication.
Le stock disponible dépend de l'éligibilité du contenu, pas du simple nombre de fichiers.

Validation : parcours complet d'une vidéo sans appel payant, déplacements du calendrier,
droits d'accès, modifications simultanées, calcul du stock et expiration des sujets d'actualité.

### 3. Agent, automatisation et publication

Exécuter les actions de l'agent sur le serveur, via des actions typées et autorisées.
Le planificateur doit continuer lorsque le site est fermé : file de travaux persistante,
verrous, reprise après redémarrage et journal. Le VPS de rendu reste un composant
réutilisé ; l'hébergement permanent du planificateur sera configuré au déploiement.

Une publication passe toujours par un point de contrôle commun : droits, faits,
qualité, format, budget, statut de validation éventuel et absence de doublon.
Brancher `services.news_rights.automation_rights` pour les analyses sportives ; étendre
le manifeste des droits aux autres formats, sans considérer un crédit comme une licence.
Les preuves et contrôles concernent les fichiers effectivement rendus.

Le worker ancien ne gère pas encore les formats récents et n'appelle pas ce contrôle
des droits : ne pas l'activer tel quel. Les actions YouTube et les appels payants
restent désactivés dans les tests et les aperçus de développement.

Publication YouTube : connexion par chaîne, chargement, miniature, description,
programmation et statut confirmé. Conserver l'identifiant de chargement ; après un
incident réseau, vérifier l'état avant toute relance. Une pause empêche les prochaines
publications, y compris celles déjà programmées sur YouTube, ou signale précisément
celles qu'il n'a pas été possible de suspendre.

Validation : deux utilisateurs/double clic, déconnexion, droits manquants, budget atteint,
pause, reprise de rendu, reprise après chargement YouTube, horaires d'été/hiver et erreurs
Discord. Faire une première publication privée de contrôle avant d'activer les cadences.

## Connexions à terminer au bon moment

Les clés des services de production et les deux salons Discord ont déjà été fournis ;
ne pas les redemander pour construire le site. La configuration Google de publication
YouTube n'est pas disponible dans l'environnement actuel. Préparer son intégration,
puis donner des étapes précises de connexion quand l'écran correspondant est prêt.

Pour l'automatisation, documenter les permissions de la voix et des médias. Les
conditions publiques du fournisseur de voix actuel nécessitent une clarification
sur l'accès automatisé : voir `production/NEWS_BRIEFS.md`. L'absence de réclamation
YouTube sur les vidéos livrées n'autorise pas leur recyclage automatique et ne permet
pas de garantir l'absence de toute réclamation future. Ne pas présenter un badge
« droits vérifiés » comme une vérification Content ID effectuée par le programme.

L'hébergement, le domaine et les statistiques avancées viennent après la construction
et les essais du studio. Aucune publication automatique réelle n'est activée par ce plan.
