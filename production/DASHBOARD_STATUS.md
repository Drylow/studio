# Edgerunners Studio — état de construction

Version du 5 octobre 2026. Le cadrage reste dans `DASHBOARD_PLAN.md` ; ce document
décrit ce qui fonctionne réellement et ce qui reste à construire.

## Disponible

- Onze pages React/TypeScript, servies par Flask : accueil, chaînes, centre de contrôle, radar d'actus,
  production, calendrier, tâches, studio vidéo, bibliothèque, réglages et Delamain.
- Nom Edgerunners Studio dans l'interface, les écrans de connexion, les lanceurs et
  les guides. Les noms techniques du dépôt et des bases restent compatibles.
- Thème Cyberpunk commun, illustration originale de Night City, polices locales,
  navigation mobile, recherche globale et réduction des animations.
- Centre de contrôle dans un poste Netwatch : stock des chaînes, configurations,
  signal du moteur et alertes de production/planning, tâches en retard, flux en erreur.
  Les alertes indiquent des étapes précises et ouvrent la fiche ou la page concernée.
  Elles disparaissent lorsque la cause se résout. Le moteur au repos n'est pas présenté
  comme en panne ; les collectes de chaînes en pause n'exigent pas son activité.
- Cloche et compteur d'alertes non lues. Accusés de lecture persistants par compte,
  liés à l'état du problème. Les lire ne résout pas un blocage et ne change aucun contrôle.
  La présence de clés est indiquée comme configuration, pas comme test réseau réussi.
- Avertissement de perte de connexion : données potentiellement anciennes, dernière
  lecture en heure belge, bouton de reprise et lecture automatique au retour du réseau.
- Huit chaînes reprises des moteurs récents. Les anciennes livraisons sont importées
  sans les transformer en publications YouTube confirmées. Les miniatures approuvées
  restent les références ; aucune miniature des vidéos actuelles n'a été refaite.
- Réglages persistants par chaîne : modèle de production, mode manuel/automatique,
  cadence, fraîcheur de l'actualité, stock cible, instructions, budget et pause.
- Tâches partagées avec responsable, priorité, échéance, modification et clôture.
  Calendrier mensuel et agenda, déplacement des créneaux, fuseau Europe/Paris,
  refus des collisions et des modifications simultanées obsolètes.
- Trois routines : préparer un sujet, vérifier une publication, organiser la semaine.
  Tâches liées à une chaîne et éventuellement à une vidéo, avec responsable et échéance
  commune. Ajout atomique et réutilisation de la routine ouverte pour éviter les doublons
  entre les deux utilisateurs et après une réponse réseau perdue.
- Recherche de tâches, filtre par chaîne, vue des retards et ouverture de la vidéo liée.
- Export `.ics` du mois et de la chaîne affichés. Dates UTC dans le fichier, sélection
  du mois en heure belge, identifiants stables, révisions et échappement/folding des titres.
  Les créneaux exportés sont des intentions ; fichier ponctuel, aucune synchronisation.
- Fiche vidéo : titre, description, script, faits, sources datées, programmation,
  aperçu, fichiers disponibles et déclaration d'une publication manuelle.
- Liste des étapes avant publication : fichiers, faits renseignés, droits, relecture,
  fraîcheur, connexion, créneau et validation. Chaque blocage décrit quoi faire et
  ouvre l'onglet concerné ; cette liste ne dispense pas des contrôles serveur.
- Miniatures et planches de contrôle agrandissables, zoom de 50 à 400 %, remise à
  l'échelle et accès à l'image originale. Navigation clavier et mobile.
- Deux rôles de compte : propriétaire et collaborateur. Sessions individuelles,
  mots de passe hachés, protection CSRF, limitation des tentatives de connexion,
  journal partagé. Les connexions et réglages sensibles sont réservés au propriétaire.
- Agent textuel connecté au proxy existant. Il consulte l'espace partagé, crée des
  tâches et idées, et lance script/rendu sur une fiche existante. Ses actions sont
  typées, persistantes et protégées contre les doublons après reprise.
- Radar d'actualités : lecture des flux RSS/Atom datés, sources modifiables, fenêtre
  de fraîcheur par chaîne, date et lien visibles, erreurs des sources explicites.
  Flux MMA News pour Cage Dispatch, BBC Sport et The Guardian pour Pitch Dispatch.
  Déduplication par URL canonique et titre normalisé identique ; repérage des sujets
  déjà présents dans les vidéos. Ce n'est pas un rapprochement sémantique des articles.
- Préparation d'une fiche de recherche depuis le radar, sans narration ni faits
  préremplis avec le texte RSS. Deux utilisateurs préparant le même article obtiennent
  la même fiche. Delamain peut actualiser un radar et préparer un article sélectionné.
  Les articles sont des pistes de recherche, pas des faits vérifiés ni des médias licenciés.
- Collecte régulière configurable par chaîne, indépendante de la publication, avec
  pauses générales et par chaîne. Elle est désactivée par défaut ; le worker et le
  serveur doivent rester actifs. L'aperçu autorise seulement la lecture manuelle.
- Adaptateurs vers les moteurs Oddly, History et analyses sportives courtes.
  Les modifications de narration invalident les étapes dépendantes. Les reprises
  d'analyses sportives utilisent un dossier séparé et conservent l'archive originale.
- File de travaux persistante, progression, erreurs, annulation, verrou global et
  reprise après redémarrage. Enveloppes autorisées par lancement avec plafond journalier.
  Ces enveloppes ne représentent pas les factures réelles des fournisseurs.
- Contrôle technique du fichier par décodage complet ; relecture humaine distincte
  pour l'audio, les faits, les images et sous-titres. Contrôles liés à l'empreinte du rendu.
- Import d'une miniature JPEG/PNG avec contrôle du format ; sources, crédits et
  justificatifs des droits dans la fiche. Adaptateur des droits pour les analyses
  sportives courtes, lié aux empreintes vidéo et miniature.
- OAuth YouTube par chaîne, chargement reprenable d'abord en privé, miniature avant
  mise en public, conservation de l'identifiant et confirmation du statut par l'API.
  Un incident de réseau déclenche une vérification de la session de chargement.
- Publication des vidéos programmées par le worker, sous réserve des contrôles,
  de la validation requise et de l'activation de la chaîne. Elles restent privées
  jusqu'au créneau exécuté par le worker ; le serveur doit rester allumé.
- Livraison Discord des analyses sportives courtes via les webhooks existants.
- Toutes les anciennes interfaces, templates et styles sont supprimés. Les anciens
  liens des outils redirigent vers le studio ; les moteurs, données et références sont conservés.
- Migration SQLite additive avec sauvegarde avant migration. Les anciennes données
  ne passent pas par la réinitialisation de `database.init_db`.

## À terminer avant les chaînes entièrement autonomes

1. Vérification des faits et choix éditorial autonome des sujets ; suivi d'après-match.
   La collecte et le dédoublonnage exact fonctionnent, mais ne confirment pas les rumeurs
   et ne donnent aucun droit de réutiliser les photos ou extraits des articles.
2. Contrôle éditorial et visuel automatisé suffisamment complet pour remplacer les
   étapes de relecture humaine. Le mode « automatique » est configuré mais les chaînes
   ne sont pas activées. Aucun moteur ne déclare seul les droits ou faits vérifiés.
3. Production de miniatures dans le thème sportif approuvé ; l'import manuel fonctionne,
   mais le nouveau studio ne génère pas encore ces miniatures automatiquement.
4. Extension du manifeste de droits aux formats Oddly et History. Leur production est
   intégrée, mais leur publication reste bloquée tant que ce contrôle n'est pas adapté.
5. Configuration Google côté serveur et essai réel d'une publication privée. OAuth et
   publication ont été vérifiés avec des réponses simulées ; aucune chaîne n'est connectée
   dans l'environnement actuel. Aucun chargement YouTube n'a été effectué pendant ces essais.
6. Permissions documentées de la voix pour un usage commercial automatisé, et licences
   des médias effectivement utilisés. Voir `NEWS_BRIEFS.md`. Un dossier de preuves ne
   constitue pas un contrôle Content ID et ne garantit pas l'absence de réclamation future.
7. Hébergement permanent, sauvegardes récurrentes et notifications des blocages.
   Statistiques YouTube, facturation réelle et exports Discord des autres formats ensuite.

## Ouvrir et utiliser

### Aperçu de développement

```bash
STUDIO_PREVIEW=1 STUDIO_WORKER_ENABLED=0 .venv/bin/python app.py
```

Ouvrir `http://127.0.0.1:5000`. Une session locale de démonstration est créée dans
`work/studio/preview.db`, séparée de la base principale. Les chaînes et livraisons
réelles y sont reprises. Les tâches, fiches et créneaux peuvent être modifiés ; les
appels payants, l'agent externe, les envois Discord et la publication sont bloqués.
Cet aperçu accepte uniquement les connexions locales et n'est pas un site public.

Pour tester l'organisation : cliquer **Tâches → Nouvelle tâche**, ou
**Studio vidéo → choisir une chaîne → Ajouter à la production**. Pour programmer :
**Calendrier → Prévoir une publication → choisir la vidéo et l'heure → Enregistrer le créneau**.

Pour la recherche : **Radar d'actus → Cage Dispatch ou Pitch Dispatch → Actualiser les
infos**, puis **Préparer une vidéo** sur un sujet. Compléter les faits vérifiés dans
la fiche ; aucun rendu payant ne démarre à cette étape. Modifier les flux dans
**Sources du radar → Configurer le radar**. Hors aperçu, activer la collecte régulière dans ce panneau,
choisir l'intervalle, puis conserver le serveur et son worker allumés.

Pour le suivi : **Centre de contrôle → choisir un filtre → suivre l'action de l'alerte**.
La cloche de la barre du haut y conduit depuis chaque page. **Marquer comme lue**
conserve le problème visible ; le filtre **Non lues** concerne uniquement ton compte.

Pour les routines : **Tâches → Ajouter une routine → choisir le type, la chaîne, la
vidéo facultative, le responsable et l'échéance → Ajouter les tâches**. Une routine
encore ouverte est réutilisée. Les contrôles de droits et de qualité se font dans
la fiche vidéo, même lorsque toutes les tâches sont cochées.

Pour exporter : **Calendrier → afficher le mois → choisir la chaîne → Exporter le
mois**, puis **Importer** le fichier `.ics` dans l'agenda externe. Les dates restent
des créneaux prévus. Les modifications ultérieures nécessitent un nouvel export.

### Application avec comptes individuels

```bash
.venv/bin/python app.py
```

Au premier lancement hors aperçu, `STUDIO_BOOTSTRAP_TOKEN` est créé dans `.env` s'il
manque. Ouvrir `.env`, copier uniquement la valeur de cette variable dans le champ
**Code d'installation** de l'écran initial, puis choisir nom, identifiant et mot de
passe. Ce code ne sert qu'à créer le premier propriétaire. Ne pas le publier.
Ensuite : **Réglages → Équipe → Ajouter un collaborateur**, renseigner son nom,
son identifiant et un mot de passe d'au moins douze caractères. Les deux comptes
partagent les tâches et productions. L'hébergement public n'est pas configuré ici.

### Développement et vérifications

```bash
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m unittest discover -s tests
```

Le bundle compilé est suivi dans `static/studio/` ; Node n'est pas requis pour servir
le dashboard, mais reste nécessaire au moteur documentaire. Pour les essais navigateur,
lancer une seconde instance d'aperçu sur le port 5001 avec une base dédiée :

```bash
.venv/bin/python -c "from studio.web import create_app; app=create_app({'PREVIEW':True,'DB_PATH':'/tmp/studio-ui-smoke.db','WORKER_ENABLED':False}); app.run(host='127.0.0.1',port=5001,debug=False,threaded=True)"
```

Dans un autre terminal, exécuter `cd frontend` puis `npm run smoke`.
Le script utilise Chromium (`CHROMIUM_PATH` si son emplacement diffère) et
`STUDIO_SMOKE_URL` pour une autre instance. Ne pas le lancer sur une base de production.

Pour le second parcours, charger d'abord les flux dans le radar de cette base dédiée,
puis exécuter `npm run smoke:news` avec la même `STUDIO_SMOKE_URL`. Il vérifie la fiche
de recherche, les blocages, la gestion des sources et le zoom, sans produire de vidéo.

`npm run smoke:control` ajoute une vidéo de recherche et une routine dans cette base
de test. Il vérifie les ajouts sans doublons, les filtres, la lecture personnelle des
alertes, le téléchargement du planning et le retour après coupure réseau. Il n'utilise
pas la base principale, n'appelle pas les fournisseurs et ne lance aucun rendu.

Validation actuelle : **67 tests Python réussis**, compilation TypeScript/Vite,
trois parcours navigateur, onze pages en ordinateur et mobile, persistance des
tâches, réglages et créneaux, radar sans double fiche et gestion des sources, liste
des étapes, zoom, et blocage des opérations de production externes dans l'aperçu.
Le centre de contrôle, les tâches et le calendrier sont aussi vérifiés à quatre
largeurs (1440, 1024, 768 et 390 pixels). Alertes personnelles, routines concurrentes,
export au changement d'heure, formulaires RSS malformés et reprise réseau sont vérifiés.
Le paquet autonome démarre aussi avec la nouvelle interface. Le proxy textuel a
répondu à une demande de lecture du nombre de chaînes. Aucune vidéo payante, image,
publication ou livraison Discord n'a été lancée pendant la construction.
