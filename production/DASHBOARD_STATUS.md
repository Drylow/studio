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
- Parcours téléphone : Agenda et Liste de production par défaut, calendrier mensuel
  défilable dans son panneau, commandes tactiles de 44 px et formulaires de 16 px.
  Formulaires sur une colonne, marges de sécurité et chat ajusté à la hauteur du clavier.
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
- Sept chaînes actives reprises des moteurs récents. Les anciennes livraisons sont importées
  sans les transformer en publications YouTube confirmées. Les miniatures approuvées
  restent les références ; aucune miniature des vidéos actuelles n'a été refaite.
- Ring Dispatch (`boxing_en`) retirée à la demande du propriétaire : masquée du studio,
  calendrier, tâches et radar, désactivée et en pause, collecte désactivée, travaux
  en attente annulés et travaux en cours signalés pour annulation. Historique et
  fichiers conservés ; imports et redémarrages ne la réactivent pas. Aucun compte
  YouTube n'est supprimé. API de retrait réutilisable pour les autres chaînes.
- Réglages persistants par chaîne : modèle de production, mode manuel/automatique,
  cadence, premier jour du rythme, fraîcheur de l'actualité, stock cible, instructions, budget et pause.
- Répartition des chaînes en colonnes Drylow / Kanye, avec réserve « À répartir ».
  Ligne turquoise sur Drylow assortie à son D, ligne jaune sur Kanye.
  Glisser-déposer et sélecteur sur mobile/clavier, attribution persistante et protection
  contre les transferts simultanés obsolètes. Les deux comptes gardent accès à toutes
  les chaînes ; le transfert conserve les vidéos, tâches, cadences et réglages.
- Filtres par responsable et « Mes chaînes ». Planning « Qui poste ? » sur sept jours :
  cadence ancrée à une date stable, créneaux suggérés distincts des vidéos réservées,
  pauses et blocages visibles, programmation préremplie sur la chaîne et l'heure proposées.
  Changer le responsable déplace immédiatement son planning ; cela ne crée aucun job.
  Les tâches explicitement attribuées à une personne gardent leur responsable.
- Tâches partagées avec responsable, priorité, échéance, modification et clôture.
  Calendrier mensuel et agenda, déplacement des créneaux, fuseau Europe/Paris,
  refus des collisions et des modifications simultanées obsolètes.
- Trois routines : préparer un sujet, vérifier une publication, organiser la semaine.
  Tâches liées à une chaîne et éventuellement à une vidéo, avec responsable et échéance
  commune. Ajout atomique et réutilisation de la routine ouverte pour éviter les doublons
  entre les deux utilisateurs et après une réponse réseau perdue.
- Recherche de tâches, filtre par chaîne, vue des retards et ouverture de la vidéo liée.
- Export `.ics` du mois, de la chaîne et du responsable affichés. Dates UTC dans le fichier, sélection
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
- Delamain connecté au proxy existant : consulte l'espace partagé, ajoute, modifie,
  retire et attribue les chaînes, crée/modifie/supprime les tâches, prépare les fiches,
  modifie narration et métadonnées, programme les créneaux et annule les travaux.
  Il lance script/rendu/contrôle technique/publication/Discord via les mêmes routes
  protégées que l'interface, avec l'identité du compte ayant envoyé la demande.
  Modes, budgets et activation sont réservés au propriétaire pour l'agent.
  Il peut régler les sources du radar et les pauses du studio selon ces permissions.
- Réponses Delamain avec liens vers chaînes, pages et fiches vidéo ; miniatures
  existantes affichées et agrandissables dans le chat, sans nouvelle génération.
  Sur téléphone, Entrée insère une ligne ; le bouton Envoyer reste distinct.
  Le résultat réel des routes remplace toute affirmation de succès proposée par l'IA.
  Une mise en file n'est jamais annoncée comme une publication YouTube confirmée.
  Plans et résultats persistants, étapes réutilisées après reprise ; une action
  interrompue demande de vérifier l'état plutôt que de répéter une mutation incertaine.
  L'agent ne peut ni valider les droits/faits/relecture, ni contourner OAuth ou les
  contrôles de publication, ni ajouter des permissions à son compte.
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
- Bouton YouTube explicite dans Répartition, Fiches des chaînes et Réglages de chacune.
  Fenêtre affichant nom et identifiant reliés, étapes Google, vérification de l'accès
  sans chargement, reconnexion et confirmation avant déconnexion. Celle-ci suspend
  l'automatisation et conserve l'identifiant pour empêcher une reconnexion accidentelle
  à une autre chaîne. OAuth refuse les doublons et les modifications concurrentes ;
  son retour rouvre la fiche ou affiche l'erreur, sans exposer une réponse fournisseur.
  Les connexions sont réservées au propriétaire ; aperçu et opérations réelles restent distincts.
  Delamain peut vérifier une connexion avec les mêmes permissions, pas accepter OAuth à ta place.
- Publication des vidéos programmées par le worker, sous réserve des contrôles,
  de la validation requise et de l'activation de la chaîne. Elles restent privées
  jusqu'au créneau exécuté par le worker ; le serveur doit rester allumé.
- Livraison Discord des analyses sportives courtes via les webhooks existants.
- Toutes les anciennes interfaces, templates et styles sont supprimés. Les anciens
  liens des outils redirigent vers le studio ; les moteurs, données et références sont conservés.
- Migration SQLite additive avec sauvegarde avant migration. Les anciennes données
  ne passent pas par la réinitialisation de `database.init_db`.
- Guide o2switch réécrit pour le nouveau studio : Passenger, worker distinct via cron/flock,
  configuration Google commune et connexion par chaîne, mises à jour depuis GitHub.
  Le worker distinct utilise désormais les routes protégées nécessaires à Delamain.
  Aucun déploiement ni essai sur l'offre réelle n'a été effectué ; ressources de rendu
  et processus permanents doivent être vérifiés sur le compte au moment de l'hébergement.
- Mode propriétaire **Delamain → Modifier le site** : demandes de modifications de code
  séparées des tâches vidéo, exécuteur `python -m studio.developer` lancé en cron,
  copie Git isolée, lectures et remplacements bornés, tests d'origine protégés,
  compilation TypeScript/Vite et démarrage Flask. Commit et branche de travail,
  sauvegarde SQLite, maintenance brève, redémarrage Passenger, contrôle de la version
  publique avant publication non forcée de `main`. Restauration de l'ancien code si
  le redémarrage ou la publication Git échoue, reprise documentée après interruption.
  Résultats et étapes réels dans le chat et Réglages ; guide [DEPLOY_DELAMAIN.md](../DEPLOY_DELAMAIN.md).
  Les fichiers sensibles et dépendances restent protégés ; l'exécuteur tourne sous
  le compte d'hébergement, sans constituer un bac à sable système. Il doit être
  connecté une fois à Git et au site sur le vrai hébergement avant utilisation.

### Validation des modifications Delamain

- 19 essais dédiés initialement validés : vraie copie Git, tests Python, compilation Node,
  installation et contrôle HTTP, refus des droits/CSRF, secrets et chemins protégés,
  lot de modifications atomique, concurrence Git, restauration après mauvais redémarrage,
  reconnaissance d'une version déjà publiée après interruption. Un cas supplémentaire
  couvre désormais l'interruption de finalisation après un push déjà réussi.
- Essai avec le **vrai service IA existant**, sans fournisseur simulé pour la génération :
  demande authentifiée dans le chat, cinq échanges IA, ajout d'une phrase turquoise sous
  le titre des tâches, **133 tests** exécutés sur la copie, compilation TypeScript/Vite,
  nouveau démarrage Flask et vérification de son commit chargé via HTTP.
  Commit poussé sur un dépôt Git local jetable ; aucun changement publié sur o2switch.
- Navigateur sur cette version réellement modifiée : phrase visible et bonne couleur sur
  téléphone, résultat « En ligne » dans Delamain, véritables comptes rendus des contrôles,
  aucune erreur JavaScript ni débordement horizontal. Les captures d'essai sont dans
  `work/studio/delamain-real-task.png` et `work/studio/delamain-real-checks.png` (non versionnées).
- Nouveaux essais navigateur des états déconnecté/en cours/en ligne/échec, résultats et
  droits aux largeurs 320, 390, 768 et 1440 px. Les onze pages du test mobile existant
  restent validées aux six tailles habituelles ; parcours YouTube simulé toujours validé.
- Raccordement du vrai compte o2switch, redémarrage Passenger et contraintes de ressources
  encore à vérifier une fois le site hébergé. Aucun téléversement YouTube ni livraison
  Discord effectué pendant le développement de cette fonction.

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
8. Brancher l'exécuteur de modifications sur le compte d'hébergement et y réaliser
   le premier changement réel. Le composant est implémenté ; aucun accès o2switch,
   redémarrage Passenger réel ni déploiement public n'a été validé dans le cloud.

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

Pour répartir : **Chaînes → Répartition → glisser la chaîne dans Drylow ou Kanye**.
Sur téléphone ou au clavier : **Déplacer vers… → choisir le responsable** sur la carte.
Les chaînes non attribuées restent dans **À répartir**. Pour consulter ton travail :
**Calendrier → Mes chaînes → Qui poste ?**. Les vues Mois/Agenda respectent aussi
le filtre personnel ; les tâches y suivent leur attribution explicite. Pour régler
les suggestions : **Chaînes → Fiches des chaînes → Réglages → cadence, heure belge
et premier jour du rythme → Enregistrer**. Les heures inexistantes au changement
de mars sont omises ; celles répétées en octobre utilisent la première occurrence.
Une suggestion est à programmer, pas une publication active. Une vidéo réservée
affiche les contrôles déclarés ; les vérifications du fichier et des droits restent
obligatoires lors de la publication.

Pour les routines : **Tâches → Ajouter une routine → choisir le type, la chaîne, la
vidéo facultative, le responsable et l'échéance → Ajouter les tâches**. Une routine
encore ouverte est réutilisée. Les contrôles de droits et de qualité se font dans
la fiche vidéo, même lorsque toutes les tâches sont cochées.

Pour exporter : **Calendrier → Mois ou Agenda → afficher le mois → choisir le
responsable et la chaîne → Exporter le
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

`npm run smoke:team` vérifie le glisser-déposer, le transfert mobile, la persistance,
la programmation préremplie, les filtres et l'export personnel, puis la lecture
depuis le compte de Kanye. Pour ce parcours seulement, préparer le mot de passe du
compte `collegue` dans la base d'aperçu dédiée (jamais la base principale) :

```bash
.venv/bin/python - <<'PY'
from studio.store import Store
from werkzeug.security import generate_password_hash
store = Store('/tmp/studio-ui-smoke.db')
with store.db() as db:
    db.execute('UPDATE studio_users SET password_hash=? WHERE id=?',
               (generate_password_hash('team smoke colleague password'), 'collegue'))
PY
cd frontend
STUDIO_SMOKE_URL=http://127.0.0.1:5001 npm run smoke:team
```

`npm run smoke:mobile` vérifie onze pages en tactile à 320, 375, 390, 430, 768 et
844 pixels, portrait et paysage. Il vérifie aussi menu, ligne d'équipe, formulaire de
tâche, agenda, défilement du mois, miniature Delamain et clavier. Préparer une
pièce jointe de test avec une référence existante, depuis la racine du dépôt :

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from studio.store import Store, now
db_path = Path('/tmp/studio-ui-smoke.db')
assert db_path.is_file(), 'Démarrer la seconde instance avant de préparer le test.'
store = Store(db_path)
channel = next(c for c in store.channels() if c['key'] == 'mma_en')
title = 'Mobile Delamain thumbnail fixture'
video = next((v for v in store.videos() if v['title'] == title), None)
vid = video['id'] if video else store.add_video({'channel_id': channel['id'], 'title': title})
thumb = Path('presets/news_thumbnails/approved_2026-10-05/reference_01.png')
assert thumb.is_file()
store.update('studio_videos', vid, {'thumb_path': str(thumb)})
content = 'Miniature existante — essai mobile, aucune génération.'
if not store.one('SELECT id FROM studio_chat WHERE content=?', (content,)):
    with store.db() as db:
        db.execute('INSERT INTO studio_chat(role,content,actor,created_at,attachments) VALUES(?,?,?,?,?)',
                   ('assistant', content, 'Delamain', now(),
                    json.dumps([{'kind': 'video', 'id': vid, 'title': title}])))
PY
cd frontend
STUDIO_SMOKE_URL=http://127.0.0.1:5001 npm run smoke:mobile
```

Exécuter les parcours successivement : ils modifient la base de test.

`npm run smoke:youtube`, sur la même instance d'aperçu dédiée, vérifie l'identité
affichée au retour Google, quatre largeurs, le résultat du test de connexion,
la confirmation de déconnexion et les commandes propriétaire/collaborateur.
Les réponses Google et les changements de connexion sont simulés dans le navigateur ;
aucun jeton n'est enregistré et aucun compte réel n'est connecté.

Validation actuelle : **114 tests Python réussis**, compilation TypeScript/Vite,
six parcours navigateur, onze pages en ordinateur et mobile, persistance des
tâches, réglages et créneaux, radar sans double fiche et gestion des sources, liste
des étapes, zoom, et blocage des opérations de production externes dans l'aperçu.
Le centre de contrôle, les tâches et le calendrier sont aussi vérifiés à quatre
largeurs (1440, 1024, 768 et 390 pixels). Alertes personnelles, routines concurrentes,
export au changement d'heure, formulaires RSS malformés et reprise réseau sont vérifiés.
Les transferts entre les deux comptes, migrations répétées, séquences de deux/sept
jours, cadence de douze heures, heure inexistante ou répétée et couverture du stock
sur le même rythme sont également vérifiés. Les nouvelles vues passent à 1440,
1024, 768 et 390 pixels.
Les nouveaux essais vérifient les droits de l'agent, l'identité de session, les
modifications concurrentes, le retrait sans perte d'historique, la reprise sans
doublons, les liens/miniatures et le refus de déclarer une publication bloquée réussie.
Ils utilisent des réponses IA simulées et les routes réelles de l'application.
Les six tailles tactiles passent sans débordement de la page ; Enter crée une ligne
dans le chat et la zone d'envoi reste visible avec une hauteur de clavier simulée.
Ces essais Chromium ne remplacent pas une vérification sur appareil iOS/Safari réel.
Le parcours mobile vérifie aussi les trois accès au panneau YouTube et la fermeture
de sa fenêtre sans envoyer le formulaire de réglages. Le nouveau parcours YouTube
teste les retours et commandes avec réponses simulées, et les tests Python utilisent
les vraies routes pour les gardes OAuth, révisions, déconnexion, refus/erreurs Google
et une mission Delamain exécutée par le worker distinct.
Le paquet autonome démarre aussi avec la nouvelle interface. Le proxy textuel a
répondu à une demande de lecture du nombre de chaînes. Aucune vidéo payante, image,
publication ou livraison Discord n'a été lancée pendant la construction.
