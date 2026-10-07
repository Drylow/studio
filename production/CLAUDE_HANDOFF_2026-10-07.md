# Passation Edgerunners Studio à Claude — 7 octobre 2026

L'utilisateur demande explicitement de pousser tout le travail sur GitHub pour
continuer avec Claude et réparer la publication automatique. **Il n'a pas effectué
la dernière connexion Google proposée.** Cette passation remplace les anciennes
questions en attente ; ne pas considérer son silence comme une authentification.
Elle documente les résultats déjà obtenus, sans promettre un fix qui n'a pas été testé.

## 1. État à reprendre

| Élément | État observé avant la passation |
| --- | --- |
| Dépôt | `https://github.com/Drylow/studio`, branches `main` et `work` |
| Code de référence | `2795223feaca0cd22ca59c46e2119a74575cdaa9`, déjà poussé sur les deux branches |
| Site | `https://edgerunners.fr`, ce même code déployé sur o2switch |
| Cette passation | Documentation ajoutée après ce code ; aucun nouveau déploiement requis |
| Utilisateurs | `drylow` propriétaire, `kanye` collaborateur ; comptes personnels privés |
| Cage Dispatch / Pitch Dispatch | `mma_en` / `football_en`, mode actualité `publication_mode=news` |
| Autorisation Google de ces sports | Aucun consentement OAuth accepté, aucune connexion réelle confirmée |
| Activation | Sports désactivés, pause globale conservée |
| Ancienne autorisation Le Grand Récap | Conservée, renouvellement refusé par Google avec `invalid_grant` |
| Navigateur privé VPS | Activé, écran et échanges réels testés sans connexion Google |
| Envoi par navigateur | **Non implémenté** ; la fonction actuelle est un écran de connexion/inspection |
| Publication API | Code et contrôles présents, aucune publication réelle validée dans cette reprise |
| Production éditoriale entièrement autonome | **À terminer** ; un radar et des pipelines ne constituent pas ce moteur complet |

Le but n'est pas simplement d'afficher « connecté » : il faut publier sur la bonne
chaîne, avec la vidéo, le titre, la description et la miniature, confirmer l'ID et
la visibilité, gérer les échecs sans doublons et respecter les contrôles existants.
Un test simulé, une redirection Google, un heartbeat ou une page de connexion ne
prouvent ni une autorisation de chaîne ni un upload.

## 2. Décisions de l'utilisateur à conserver

- Nom : **Edgerunners Studio**, un mot avec un S. Interface française, cyberpunk,
  désormais simple : Accueil, Chaînes, Statistiques, Vidéos, Calendrier, Tâches,
  Delamain ; fonctions secondaires dans « Autres outils », réglages en bas.
- Très bon usage mobile ; listes et agenda par défaut, détails techniques repliés.
  Ne pas remettre un accueil rempli de chiffres et de panneaux.
- Travail partagé **Drylow / Kanye**, chaînes transférables par glisser-déposer
  et commande équivalente sur téléphone ; non attribuées dans une section commune.
- Cage/Pitch : publication automatique selon **les actualités en direct**, sans
  horaire quotidien, cadence ou stock cible imposé. Les autres chaînes gardent
  leurs modes manuel, validation ou automatique configurables.
- Publication gratuite, pas d'abonnement à un prestataire de publication. Il a
  refusé les relais externes et **toute nouvelle installation sur son PC**.
  Les anciennes pistes d'assistant PC ont été retirées : ne pas les reproposer.
- Les statistiques sont reportées par l'utilisateur : priorité à la publication.
  La clé publique Data API est déjà configurée ; ne pas redemander sa création.
- **Ring Dispatch (`boxing_en`) retirée**, historique conservé, aucune nouvelle
  production ni réactivation automatique. Conserver les outils Oddly et History.
- Trois analyses sportives du 5 octobre (Parnasse–Topuria, Imavov–Strickland,
  Mbappé) ont été publiées manuellement par lui. **Ne pas les republier**, ni refaire
  leurs miniatures. Pour les futures : consulter les deux références approuvées
  dans `presets/news_thumbnails/approved_2026-10-05/` avant toute création.
- Format choisi pour les sujets alimentés par des posts : analyse **4–6 minutes**,
  sources et contexte. Une rumeur reste une rumeur ; un repost rapporté par un
  article ne devient pas une source primaire vérifiée.
- Aucun copyright garanti par l'absence de réclamation sur les trois anciennes
  vidéos. Droits non établis des images, extraits, musique ou voix = automatisation
  bloquée. Voir `NEWS_BRIEFS.md` et `services/news_rights.py`. Les anciennes règles
  « source indépendante = OK » ne remplacent pas une licence documentée.
- Les conditions d'usage commercial **et automatisé** du fournisseur de voix
  restent à établir pour ce mode. Une clé API présente ne prouve pas ces droits.
- Ne jamais annoncer « 100 % fonctionnel » ou « zéro copyright » sur des mocks.
  Répondre en français court, donner des nouvelles, expliquer chaque action
  demandée par son chemin, son bouton et le résultat attendu. Heure Paris/Belgique.
- Commit et push de chaque changement sur la branche de travail **et `main`**,
  sans force push ni écrasement des changements d'un autre contributeur.

## 3. Travail livré et carte du projet

Les anciennes interfaces ont été remplacées, mais les données, pipelines récents
et références sont conservés. Le bundle servi est versionné dans `static/studio/`.
Modifier `frontend/src/`, compiler et committer le bundle correspondant ; ne pas
modifier uniquement un fichier JavaScript généré.

| Partie | Sources et documentation principales |
| --- | --- |
| Application, routes, migrations, stockage | `app.py`, `studio/web.py`, `studio/store.py`, `studio/domain.py` |
| Interface simplifiée | `frontend/src/main.tsx`, `pages.tsx`, `daily-home.tsx`, `components.tsx`, `workspace.css`, `style.css` |
| Attribution et calendrier | `studio/planning.py`, `studio/schedule.py`, `frontend/src/team-board.tsx`, `personal-planning.tsx` |
| Tâches, routines et contrôle | `studio/control.py`, `frontend/src/control.tsx`, `routines.tsx`, `readiness.tsx` |
| Actualité et fiches de recherche | `studio/newsroom.py`, `frontend/src/newsroom.tsx`, `production/news_auto.py` |
| Fiches, fichiers et validation | `studio/imports.py`, `studio/review.py`, `studio/jobs.py`, `frontend/src/review.tsx` |
| Publication et reprise | `studio/publishing.py`, `studio/auto_publication.py`, `studio/worker.py` |
| Consentement et identité YouTube | `studio/youtube.py`, `studio/youtube_permissions.py`, `routes/youtube.py`, `frontend/src/youtube-connection.tsx` |
| Navigateur privé nouveau | `studio/browser_connection.py`, `production/private_browser_service.py`, `frontend/src/browser-connection.tsx`, `PRIVATE_BROWSER.md` |
| Statistiques publiques par @pseudo | `studio/public_statistics.py`, `frontend/src/statistics-page.tsx`, `statistics-page.css` |
| Statistiques nécessitant OAuth | `studio/channel_stats.py`, `tests/test_channel_stats.py` ; distinctes du suivi public |
| Accès privé | `studio/security.py`, `frontend/src/private-access.tsx`, `tests/test_security.py` |
| Delamain, gestion du studio | `studio/agent.py`, `tests/test_agent_management.py` |
| Delamain, modification/déploiement du code | `studio/development.py`, `studio/developer.py`, `frontend/src/development.tsx`, `../DEPLOY_DELAMAIN.md` |
| Pages publiques Google | `studio/public_pages.py`, `studio/templates/public.html` : `/about`, `/privacy`, `/terms` |
| Analyses sportives et droits | `production/news_brief.py`, `services/news_brief.py`, `services/news_rights.py`, `NEWS_BRIEFS.md` |
| Interviews, montage VPS et relais | `production/news.py`, `production/news_worker.py`, `services/newsvid*.py` |
| Oddly | `services/pov_engine.py`, `services/pov_script.py`, `production/pipeline.py`, `steps.py`, `verify.py` |
| History | `services/history*.py`, `production/history_video.py`, `history_engine/`, `presets/history_channels/` |
| Livraisons et références | `VIDEOS.md`, `chaines/`, `presets/`, `skills/references/` |

Les pistes de concepts/styles historiques ajoutées le 6 octobre sont aussi dans
l'historique Git ; les conserver, sans les confondre avec des chaînes déjà
connectées. Les outils existants de montage PC sous `standalone/pc_agent/` sont
conservés, mais le **nouvel assistant YouTube PC a été supprimé**.

Delamain est l'assistant intégré, distinct de la conversation Codex/Claude. Il
utilise les routes protégées pour gérer chaînes, tâches, attribution, fiches et
programmation et montrer les miniatures existantes. L'exécuteur séparé « Modifier
le site » a réellement fait une modification testée, déployée et poussée :
`b1da59e`. Cela ne lui donne ni l'administration Google ni une autorisation YouTube.
Il ne remplace pas les droits, l'identité de chaîne ou les vérifications éditoriales.

Repères Git (ne pas annuler les suivants en restaurant aveuglément l'ancien site) :

| Commit | Résultat |
| --- | --- |
| `dbab2af` | Nouveau studio et remplacement des interfaces historiques |
| `77cba49`, `a944b27` | Attribution partagée, parcours mobiles, gestion Delamain |
| `b727a18`, `b1da59e` | Exécuteur de développement et premier changement réel déployé |
| `e247623` | Accès privé simplifié à mots de passe personnels ; QR/app d'authentification retirés à sa demande |
| `257dee4` | Callback Google historique conservé |
| `43a4510`, `280b854` | Publication d'actualité sans heures fixes, interface simplifiée |
| `d6912bd` | Statistiques publiques par @pseudo |
| `002b6cd`, `c49431d` | Envoi des vidéos d'actualité prêtes et compatibilité des scopes historiques |
| `824ad79`, `c765727` | Refus réels de consentement et diagnostic exact de l'ancienne autorisation |
| `63d1295`, `5deb755` | Retrait des parcours PC et statuts de connexion honnêtes |
| `2795223` | Écran privé Firefox sur VPS, sans installation PC |

## 4. Google : faits établis et inconnues

Projet : **507920096990**. Client public conservé :
`507920096990-jm0qmtftoevmaje5p5nhsuuc7hgna4l7.apps.googleusercontent.com`.
Callback enregistré : **`https://edgerunners.fr/api/youtube/callback`**, alias
maintenu avec les contrôles de rôle, session et état à usage unique.

1. Le refus réel **« This app is blocked »** arrive chez Google avant le callback.
   Le warning contient un paramètre opaque ; aucun code précis de cause n'a été
   extrait. La cause compte/projet n'est **pas déterminée**.
2. Le parcours avec `youtube.force-ssl` a été refusé. Le retour exact à
   `youtube.upload` + `youtube.readonly` a aussi été essayé par l'utilisateur le
   6 octobre à **23 h 10 Paris** pour Cage, puis refusé. Aucun nouveau jeton.
3. Le serveur utilise `YOUTUBE_PUBLICATION_FLOW=legacy-news` : chaînes d'actualité
   avec ces deux scopes, visibilité publique dans `videos.insert` ; autres chaînes
   avec `youtube.force-ssl`, envoi privé puis `videos.update`. Voir `LEGACY_YOUTUBE.md`.
   L'identité de chaîne ne peut pas être validée par `channels.list(mine=true)` avec
   le seul scope upload : ne pas le retirer au prix de publier sur une autre chaîne.
4. L'ancienne autorisation Le Grand Récap répond HTTP 400 `invalid_grant`, sans
   sous-type. Le **code exact antérieur**, depuis sa copie privée, exécuté avec son
   `.env`, son jeton et son proxy, donne le même refus. Les fonctions de config et
   de renouvellement sont identiques. Client, secret, callback et jeton correspondent.
5. Treize sauvegardes de config, Passenger/Python/Apache et les états de l'ancien
   outil n'ont pas révélé un autre client. Le test n'établit **ni quand ni pourquoi**
   le jeton a cessé de fonctionner ; ne pas prétendre que la migration est innocentée
   pour tous les comportements ou que les autres chaînes n'ont jamais fonctionné.
6. Les 25 IDs d'envoi de l'ancien historique existent dans l'API publique et sont
   associés à Le Grand Récap, actuellement non répertoriés. Dates enregistrées en
   base : 29 juin–1er juillet. Cela ne prouve pas leur ancienne visibilité publique.
7. Search Console a validé la propriété DNS d'**edgerunners.fr**. Conserver le TXT.
   Google Branding a demandé jusqu'à 24 h pour son cache ; prochaine vérification
   pertinente indiquée : **7 octobre après 17 h 25 Paris**. Ce délai ne prouve pas
   la cause du blocage et ne garantit pas le consentement après expiration.
8. Captures : application External/In production, cap 1/100, permissions sensibles
   YouTube non vérifiées. Association entre propriétaire Search Console et rôle
   du projet non vérifiée ; l'utilisateur a refusé les demandes IAM compliquées.
9. La capture de Protection Avancée affiche **« Enroll »** : elle n'est pas activée
   sur le compte montré. Le premier lien avait donné 404. Ne pas lui demander de
   s'inscrire, de désactiver une protection ou de refaire ce contrôle inchangé.
10. cPanel n'est pas Google Cloud. Aucun accès Google administrateur/ADC n'a été
    trouvé ou fourni. La clé Data API lit les compteurs publics, **n'autorise pas
    l'upload**. Les accès cloud ne se transfèrent pas automatiquement à Claude.

Les recherches de relais payants, RSS podcast (image fixe), Apps Script et PC sont
dans `PUBLICATION_ALTERNATIVES.md`, mais ne sont pas des solutions acceptées et
validées. Les anciennes questions de préférence y sont dépassées. Ne pas emprunter
le client OAuth d'un tiers, exporter des cookies ou contourner les protections
Google. Ne pas répéter les mêmes instructions de scopes/Branding sans nouveau fait.

## 5. Nouvelle piste : navigateur privé, ce qui est réellement construit

Le propriétaire peut ouvrir **Chaînes → chaîne → Connecter YouTube → Ouvrir YouTube
sur le serveur**. Un Firefox graphique avec barre d'adresse apparaît dans le site ;
clic dans la capture, texte dans le champ protégé, « Écrire dans Google », « Entrée ».
Le parcours API reste replié sous « Autre méthode : API Google ».

- Sur o2switch, `YOUTUBE_BROWSER_ENABLED=1` a été ajouté à la config privée.
  Le navigateur n'est pas une connexion Google acceptée ou une activation de chaîne.
- Écran réservé au **propriétaire**, à sa session, à la chaîne et à sa révision ;
  expiration 20 minutes, CSRF, révocation et fermeture. Éditeur/aperçu refusés.
- VPS → site par HTTPS sortant. POST `/api/studio/youtube-browser/bridge` : signature
  HMAC dérivée pour cet usage du jeton existant, timestamp ±120 s, nonce non rejouable.
  Cette route spéciale ne désactive ni HTTPS/hôte ni maintenance. Aucun port VNC,
  Firefox ou Marionette public.
- Saisie chiffrée dans le navigateur client : RSA-OAEP 3072 et AES-GCM 256, session
  liée aux données authentifiées. Clé privée éphémère en mémoire sur le VPS ; relais
  et SQLite voient du chiffré. Pas de mot de passe Google en argument/env/fichier/log.
- Captures privées `no-store`, temporaires en SQLite, effacées à la fermeture.
  Ne pas les exporter dans le dépôt ou un service de capture externe.
- Firefox sous compte non privilégié `edg_browser`, home
  `/data/edgerunners-browser-service`, profils 700 par `channel-<id numérique>`.
  Environnement du navigateur sans clés worker/fournisseurs. Xvfb privé avec
  Xauthority, `-nolisten tcp`, écran 480 × 820. TLS et protections normales conservés.
- Runtime privé `/data/edgerunners-browser-runtime/` : code, dépendances, PID et
  configuration de démarrage limitée à l'URL du site. Démarrage à la demande par
  l'API de montage déjà autorisée. Code vérifié par digest SHA256 dans le heartbeat.
- Paquets Debian signés Firefox ESR/Xvfb/xauth/xdotool ; cryptography 46.0.3 installé
  par TLS dans les dépendances privées. Pas de navigateur sur le PC utilisateur.
- Connexion initiale en Firefox normal ; l'inspection redémarre ensuite le même
  profil avec le débogage local standard Marionette. Aucun masquage WebDriver,
  bypass CAPTCHA, désactivation TLS ou sandbox. **L'acceptation de cette inspection
  après une vraie connexion Google n'a pas été testée.**
- Inspection attend l'application Studio et un `CHANNEL_ID` conforme à l'ID public
  attendu, pas uniquement une URL. Cette lecture DOM nécessite une validation sur
  un vrai compte. Elle ne configure pas l'uploader existant.
- Tables additives `studio_browser_worker`, `studio_browser_nonces`,
  `studio_browser_sessions`, `studio_browser_commands`. Données historiques conservées.
  `production/news_worker.py` n'a pas été modifié par cette livraison.

**Manques / risques à traiter avant de poursuivre cette piste :** transport upload
absent ; inspection authentifiée non testée ; stabilité UID/permissions des profils
après recréation de conteneur non vérifiée ; boucle de commandes synchrone, donc
jobs longs à séparer du heartbeat/lease ; reconnexion, fermeture, annulation et
résultat incertain à gérer sans doublons. Ne pas présenter ces points comme résolus.

## 6. Validation obtenue, limites des preuves

Ces résultats ont été obtenus pendant les travaux précédents ; la passation est
documentaire et ne prétend pas avoir refait tous ces essais.

| Vérification | Résultat et portée |
| --- | --- |
| Suite Python complète avant le dernier test navigateur ajouté | **213 tests passent** ; ne pas annoncer une nouvelle suite complète de 214 passée |
| Sélection actuelle pour le déploiement | **122 tests passent**, cloud et o2switch, incluant les 6 tests du navigateur privé |
| TypeScript/Vite | Vérification des types et build production réussis, bundle versionné |
| Interface navigateur privé | 320/390/768/1440 px, saisie RSA/AES réellement déchiffrée par la fixture, refus éditeur ; services simulés |
| Firefox anonyme sur le vrai VPS | Page Google YouTube officielle, capture 480 × 820, touche normale, connexion nécessaire, aucune chaîne reconnue |
| Parcours réel edgerunners.fr → VPS | Heartbeat signé, écran anonyme, touche chiffrée, inspection puis fermeture vérifiés ; session propriétaire de test révoquée |
| Accès natif | Propriétaire autorisé, éditeur refusé, bridge non signé refusé après sortie de maintenance, gate et assets HTTPS contrôlés |
| Données/config du déploiement | Digest des six tables principales identique ; credentials préservés ; seul opt-in navigateur ajouté à `.env` |
| Google authentifié et upload | **Non exécutés / non validés** |

Une première tentative de déploiement a été restaurée parce que le test exigeait
403 sur le bridge pendant la maintenance, qui renvoie légitimement 503. C'était
une erreur d'ordre du test, corrigée avant le second déploiement réussi, pas un
nouveau refus Google. Conserver cette protection de maintenance.

Preuves privées o2switch, dans le repo natif `~/drylow_studio` :
`work/studio/private-browser-deployment.json` et
`work/studio/private-browser-live-test.json`. Ce dernier confirme explicitement :
`google_login_performed=false`, `video_uploaded=false`,
`publication_validated=false`, `sports_automation_still_disabled=true`.
Ne pas publier les rapports, sessions ou captures privés dans Git.

## 7. Hébergement, accès et secrets : où les retrouver

### o2switch

- Code `~/drylow_studio`, branche `main`, dossier 700 ; `.env` et
  `drylow_studio.db` privés 600. **Ne pas recréer la base ou écraser `.env`.**
- Python `~/edgerunners_venv/bin/python` 3.12.14 ; Node 22.23.3 et npm sous
  `/opt/alt/alt-nodejs22/root/usr/bin/`.
- `public_html` contient les règles Apache/Passenger et dossiers système, pas les
  secrets. Redémarrage Passenger via `~/drylow_studio/tmp/restart.txt`.
- Crons séparés `studio.worker` et `studio.developer`, verrous `flock`, heartbeat ;
  l'ancien cron HTTP est désactivé. Respecter `developer.lock` et la maintenance
  `work/studio/development-maintenance.json` avant toute modification déployée.
- Accès cPanel par **`CPANEL_URL`, `CPANEL_USER`, `CPANEL_PASSWORD`**, déjà fournis
  dans l'environnement Codex. Ils peuvent ne pas exister dans la nouvelle session
  Claude. Vérifier présence/accessibilité avant de demander un ajout sécurisé.
- Mots de passe initiaux de la gate dans `~/edgerunners-access.txt`, hors public.
  Cela ne garantit pas qu'ils n'ont pas été changés depuis ; ne pas les afficher.
- Sauvegardes `~/edgerunners_backups/`, copie pré-migration
  `~/drylow_studio_legacy_20261006` et archive privée `site-before.zip`.
  Dernière sauvegarde du navigateur : `private-browser-connection-20261007T014715`
  (horodatage UTC du nom, 03 h 47 Paris). Garder les copies cohérentes SQLite.
- Git de déploiement en écriture déjà vérifié, clés privées sur le serveur ; ne
  pas recréer les clés, exporter une clé privée ni désactiver la vérification d'hôte.
- `/health/studio` est privé, preuve HMAC à usage dédié avec `FLASK_SECRET_KEY`.
  Tests autorisés : sessions temporaires courtes et révocation en `finally`, jamais
  d'ouverture publique de la gate ou des médias pour faciliter une vérification.

### VPS de montage et navigateur

- `NEWS_WORKER_URL` / `NEWS_WORKER_TOKEN` configurés en privé. HTTPS avec
  `X-Worker-Token`. Vérifier GET `/status` et les jobs actifs avant toute soumission.
- PUT `/job?name=...&upload=0` accepte le paquet de job, GET `/file` récupère son
  résultat/log/planches. DELETE seulement son job terminé ; le montage efface
  `/data/work`, d'où le runtime navigateur situé ailleurs.
- Le code de montage s'exécute dans le conteneur ; `/w.py` est monté en lecture
  seule. Aucun accès SSH hôte ni socket Docker démontré. Root dans le conteneur
  ne constitue pas un accès root à l'hôte.
- Les anciennes routes `/pcjob` et `/pc/*` servent au montage préexistant. Ne pas
  réclamer `/pc/next` pour diagnostiquer : cela prendrait un vrai job.
- Le proxy résidentiel existant est limité à yt-dlp/YouTube. Ne pas y envoyer
  pip, Gofile ou le navigateur ; ne pas multiplier des téléchargements coûteux.

### Configuration privée et passage à une nouvelle machine

Noms utiles : `AI_BASE_URL`, `AI_API_KEY`, `ALGROW_API_KEY`, `AI33_API_KEY`,
`NEWS_WORKER_URL`, `NEWS_WORKER_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`OAUTH_CALLBACK_PATH`, `YOUTUBE_PUBLICATION_FLOW`, `YOUTUBE_BROWSER_ENABLED`,
`YOUTUBE_API_KEY`, `FLASK_SECRET_KEY`, `STUDIO_PUBLIC_URL`, `STUDIO_HOSTED`,
`STUDIO_WORKER_ENABLED`, `STUDIO_DEV_ENABLED`, `STUDIO_DEV_HEALTH_URL`,
`STUDIO_DEV_NPM`, `CPANEL_URL`, `CPANEL_USER`, `CPANEL_PASSWORD` et les webhooks
`DISCORD_WEBHOOK_<CLÉ>`. Les valeurs effectives sont sur le serveur ou dans les
variables/secrets de la session, **jamais dans cette passation**.

GitHub transfère code, tests et documentation ; il ne transfère **ni ces secrets,
ni les cookies Google, ni SQLite, ni les rendus privés**. Réutiliser les accès
existants via les paramètres sécurisés de l'outil utilisé par Claude. Ne pas
demander un token GitHub parce qu'une variable manque : tester d'abord l'accès
Git fourni par l'environnement. Le réseau Codex utilise son proxy et son CA ;
préserver TLS. Aucun accès Google Cloud administrateur injecté n'a été observé.

Les helpers de diagnostic dans `/tmp/edgerunners_*.py` et fichiers de session
privés sont temporaires propres à la machine Codex, pas un contrat de reprise.
Ne pas en dépendre, ne pas exporter leurs cookies ni les ajouter au dépôt. Les
modules versionnés, docs de déploiement et preuves privées natives font référence.

## 8. Reprendre efficacement

1. Ouvrir le dépôt **Drylow/studio** à jour et lire ce fichier, `../CLAUDE.md`,
   `LEGACY_YOUTUBE.md`, `PRIVATE_BROWSER.md`, puis `../DEPLOY_O2SWITCH.md`.
   Vérifier branche, fichiers modifiés et accès avant de lancer des scripts.
   Ne pas réinitialiser le projet ou restaurer aveuglément l'interface historique.
2. Choisir une correction justifiée du consentement API **ou** terminer un
   transport serveur par le vrai Studio après avoir vérifié que Google accepte
   normalement ce compte. Les refus du parcours historique sont déjà confirmés.
   Le nouveau parcours navigateur n'a pas été essayé par le propriétaire ; il
   n'existe aucune session Google authentifiée prouvée sur laquelle travailler.
3. Si cette piste est retenue, authentification normale par le propriétaire dans
   l'écran privé, sans mot de passe en conversation ni désactivation de protection.
   Valider l'ID immuable de la bonne chaîne sur un vrai compte avant tout upload.
4. Pour le transport navigateur, construire transfert vérifié des fichiers,
   titre/description/tags/miniature/visibilité, contrôle de traitement, conservation
   immédiate de l'ID vidéo et réconciliation des réponses incertaines. Réutiliser
   les verrous/révisions, pauses, droits, hashes, QA, fraîcheur, budget et règles
   de validation de `studio/publishing.py`, sans marquer artificiellement connecté.
   Prévoir jobs longs, heartbeat, reprise après redémarrage et aucune duplication.
5. Le mode historique API devient public à la fin de l'envoi, puis pose la miniature.
   Sans scope de gestion il ne peut pas remettre en privé après cette fin ; une
   erreur de miniature est une erreur sur vidéo déjà publique, pas un envoi retenu.
   Une restriction Google imposant privé ne peut pas être annoncée comme public.
6. Valider d'abord une fixture nouvelle autorisée sur la bonne chaîne ; aucun
   des trois anciens montages. Confirmer côté YouTube ID, chaîne, médias et
   visibilité, puis les échecs/reprises sans doublons. Documenter ce qui a été
   réellement envoyé, pas uniquement les tests unitaires.
7. Terminer la sélection autonome d'actualité, faits sourcés, droits/licences,
   choix des visuels/voix, production et QA. Les pipelines de fabrication et le
   radar existants ne suffisent pas à justifier la boucle sans intervention.
   Lever la pause et activer les sports seulement lorsque ces exigences sont
   satisfaites et le vrai parcours de publication validé.

Ne pas interpréter l'autorisation d'automatiser comme une autorisation d'ignorer
ces contrôles. Inversement, l'utilisateur a déjà choisi l'autonomie par chaîne :
une validation manuelle à chaque vidéo ne satisfait pas sa demande finale.

## 9. Développement et contrôles reproductibles

Utiliser le clone existant, examiner `git status` avant un `git pull --ff-only`.
Dans le cloud Codex, le checkout était `/workspace/studio`, virtualenv `.venv/`.
Sur une nouvelle machine Claude, suivre le README et installer les dépendances
avec le lockfile frontend ; ne pas supposer que `.venv` et les processus existent.

Depuis la racine, les 122 contrôles ciblés du dernier déploiement :

```bash
.venv/bin/python -m unittest \
  tests.test_auto_publication tests.test_security tests.test_youtube_connections \
  tests.test_studio tests.test_team_planning tests.test_newsroom \
  tests.test_browser_connection
npm --prefix frontend run build
```

Suite complète : `.venv/bin/python -m unittest discover -s tests`. Les tests de
développement créent leur propre dépôt/fixtures ; sur o2switch respecter l'exécution
des cas dans des processus distincts documentée dans `../DEPLOY_DELAMAIN.md`.
Ne pas lancer les tests ou fixtures contre la base de production.

L'aperçu local utilise une **base dédiée** et le worker coupé, voir README.
`frontend/scripts/browser-connection-smoke.mjs` exige cet aperçu, Chromium/Playwright
et une image **synthétique** `BROWSER_FIXTURE_IMAGE` ; défaut temporaire
`/tmp/edgerunners-browser-ui-fixture.jpg`. Exemple, l'aperçu déjà démarré :

```bash
cd frontend
STUDIO_SMOKE_URL=http://127.0.0.1:5004 \
  BROWSER_FIXTURE_IMAGE=/chemin/prive/fixture-synthetique.jpg \
  node scripts/browser-connection-smoke.mjs
```

Tous les appels au service navigateur y sont simulés : ne jamais prendre ce
parcours Chromium de test pour un test Google réel ni y saisir un compte.
`git diff --check`, revue des secrets et vérification des hashes distants avant
de déclarer un push terminé. L'ancien hook post-commit pousse automatiquement :
vérifier ce qu'il fait avant un commit. Pas de force push. Suivre les sauvegardes,
maintenance, tests et retour arrière de `DEPLOY_O2SWITCH.md` pour le prochain
déploiement, puis vérifier la version réellement servie en HTTPS.
