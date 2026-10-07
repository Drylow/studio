# Reprise sur un autre compte Claude (historique et état actuel)

## Reprise Claude — 7 octobre 2026, après-midi

- **Google débloqué (7 oct., confirmé par l'utilisateur)** : en *Testing* avec son Gmail en
  utilisateur de test, le consentement passe (plus de « This app is blocked »). Le refus suivant
  « déjà reliée à une autre fiche » venait de la fiche historique **Le Grand Récap** (id 3) : sa
  chaîne YouTube `UC0kWhUDz5-dvl-KqfSw8f4A` a été **renommée Cage Dispatch** (@CageDispatch).
  Correctif : à la connexion, une fiche inactive qui garde l'ancien nom d'une chaîne renommée
  lui cède le lien (historique conservé). Connexion datée (`yt_connected_at`) ; avec
  `YOUTUBE_TOKEN_DAYS=7` sur le serveur, alerte sur le site et rappel Discord la veille de la
  coupure Google hebdomadaire. Plusieurs chaînes sur un même Gmail : une connexion par chaîne.
  Cage Dispatch reliée le 7 oct. à 18 h 30 (Paris) à `UC0kWhUDz5-dvl-KqfSw8f4A`. Les profils
  Google gardent d'anciens noms : quand le profil choisi n'est pas la chaîne de la fiche, le
  site montre la vraie chaîne et le propriétaire choisit sa fiche (`studio_youtube_pending`).
- **Publication réelle validée (7 oct., 21 h 00 Paris)** : vidéo test de 6 s envoyée par le
  serveur sur Cage Dispatch en **non répertoriée** (`MnthNFxqadY`) : titre, description et
  miniature acceptés, visibilité respectée (pas de verrouillage en privé du projet Google).
  Pitch Dispatch reliée (`UC7IbPH4JICJSDN-gyFP7PDA`), accès vérifié en direct pour les deux.
  Choix de l'utilisateur : voix Algrow conservée malgré la restriction d'usage automatisé
  (risque accepté par lui), 2 vidéos par jour et par chaîne au maximum.
- **Pilote automatique Cage/Pitch** (`studio/autonews.py`, détails dans `NEWS_BRIEFS.md`) : essai réel
  sur le serveur le 7 oct. (21 h 23), sujet « Shavkat Rakhmonov teases 19-0 vs 19-0 » choisi 8/10,
  vidéo `77db6e8c11094c0f936e7c9c1c367c6f` (4 min 25) en `review`, non publiée. Corrigé pendant
  l'essai : threads ffmpeg (`FFMPEG_THREADS=4` sur o2switch), photos à une seule personne,
  jamais le visage d'une autre personne (cartes et miniature), référence de style sans visage.
  `NEWS_AUTO_DRY=1` reste dans le `.env` du serveur jusqu'au « go » de l'utilisateur ; ensuite :
  retirer cette ligne, activer l'automatisation de Cage/Pitch et lever la pause du studio.
  Limite connue : peu de photos libres → images répétées ; texte seul quand aucune n'existe.
- **Delamain codé par Claude (option 2, mise en ligne sans validation)** : routine
  `trig_01GfMnci6KHo8W7cB7amCy84` (Sonnet, environnement sans accès o2switch). À compléter
  par l'utilisateur sur claude.ai : dépôt Drylow/studio + déclencheur API, puis adresse et
  jeton dans Réglages → Modifications du site. Le site peut être en retard sur `main` :
  chaque modification part du dernier `main` (contrôle exécuteur OK le 7 oct. à 20 h 36).
- **Piste Google (historique)** : le projet était en *Testing* jusqu'au 6 octobre. En Testing,
  un jeton de renouvellement expire après 7 jours : explication probable de l'`invalid_grant`
  de Le Grand Récap (envois du 29 juin au 1er juillet, puis plus rien). Le passage en
  *Production* non vérifiée a précédé « This app is blocked ». Aucune note ne montre l'essai
  **Testing + Gmail du propriétaire en utilisateur de test** (projet et chaînes sur le même
  Gmail, confirmé par l'utilisateur). Étapes données : Audience → Back to testing → Test users
  → Add users → puis Chaînes → Connecter YouTube → Autre méthode : API Google. Limite connue :
  reconnexion hebdomadaire tant que l'application n'est pas vérifiée. Résultat en attente.
- **Navigateur VPS** : ne pas terminer l'envoi par automatisation de YouTube Studio (envoi
  automatisé hors API contraire aux conditions YouTube, risque pour les chaînes).
- **Delamain** : il code aujourd'hui avec `AI_TEXT_MODEL` (défaut gpt-5.5) via le proxy de
  `AI_BASE_URL`. L'utilisateur veut Claude (Sonnet, usage léger) via une routine Claude Code
  déclenchée par le site. Le branchement entièrement autonome (code + mise en ligne sans
  validation) a été refusé par la sécurité de la session ; variante proposée : Claude prépare
  la branche, le propriétaire valide la mise en ligne d'un geste. Choix en attente.
- **o2switch depuis le cloud Claude** : `CPANEL_*` présents dans l'environnement de la session.
  Le port 2083 est injoignable depuis le cloud ; la connexion cPanel fonctionne par le
  sous-domaine proxy sur 443. L'exécution de commandes sur le serveur demande une validation
  explicite de l'utilisateur (mode « Accept edits ») : ne pas la contourner. Aucune commande
  serveur exécutée, aucun déploiement. Selon la passation, site à `2795223`, `main` à `647a509` (docs).

## Passation à Claude — 7 octobre 2026

L'utilisateur demande de mettre toutes les modifications et les informations de
reprise sur GitHub pour continuer avec Claude. **Lire d'abord
[CLAUDE_HANDOFF_2026-10-07.md](CLAUDE_HANDOFF_2026-10-07.md).** Ce dossier est l'état
de référence ; les entrées datées ci-dessous décrivent les essais précédents.

Tout le code jusqu'à `2795223` était déjà poussé sur `main` et `work` et déployé sur
edgerunners.fr. La passation ajoute de la documentation. Le navigateur privé a été
activé et testé sur le vrai site avec une session propriétaire temporaire révoquée
après le contrôle : écran Google anonyme, heartbeat signé, touche chiffrée et
fermeture vérifiés. **Aucune connexion Google réelle ni vidéo envoyée.** Le dernier
parcours proposé n'a pas été effectué par l'utilisateur. Cage/Pitch restent sans
autorisation OAuth, désactivées et en pause globale. Le transport d'upload navigateur
et la production éditoriale autonome restent à terminer.

## Diagnostic et navigateur privé — 7 octobre 2026

Nouvelle piste concrète : Firefox **graphique** sur le VPS ouvre la vraie page de
connexion YouTube, avec ses protections normales, sans programme à installer sur
le PC. Capture et clavier vérifiés sans compte ; aucune authentification ni vidéo
envoyée. Parcours privé dans `studio/browser_connection.py` et
`production/private_browser_service.py`, guide `PRIVATE_BROWSER.md`.
Opt-in `YOUTUBE_BROWSER_ENABLED=1`. Il fournit la connexion interactive uniquement :
**le transport de publication par navigateur est encore à terminer et valider**.
Ne pas confondre ce parcours, sa page de connexion ou ses tests avec le fix livré.
Le PC de l’utilisateur est éteint ; il peut utiliser cet écran depuis son téléphone.

L’utilisateur exige une publication réellement automatique, gratuite, sans
prestataire intermédiaire ni nouvelle installation sur son PC. Les connexions
Cage/Pitch restent absentes ; ne pas annoncer cet objectif livré. La production
éditoriale autonome reste également à terminer.

La nouvelle comparaison exécute le code exact de l’ancien site avec sa sauvegarde
d’origine : Google refuse aussi son jeton (`invalid_grant`, HTTP 400). Les fonctions
de renouvellement et de configuration sont inchangées ; client, secret, callback
et jeton conservés correspondent. Les réglages Python/Passenger et les états de
l’ancien outil ne révèlent pas un autre client. Voir `LEGACY_YOUTUBE.md`.
Cela ne prouve ni la date ni la cause du refus, et restaurer l’interface ancienne
ne rétablit pas cette autorisation. Aucun envoi effectué pendant le diagnostic.

La capture Google propose « Enroll in Advanced Protection » : ce programme n’est
pas activé sur le compte affiché. Ne pas demander de l’activer ou de désactiver une
protection. Le premier lien fourni, `/advanced-protection`, était erroné ; le lien
officiel corrigé est `https://account.google.com/advanced-protection/enroll/details`.
Ne pas reprendre les mêmes essais OAuth ou les mêmes demandes de clés sans un
nouveau diagnostic. Les accès Git/o2switch ne donnent pas l’administration Google.

## Historique du diagnostic — 6 octobre 2026

Cette entrée précède le retour aux scopes historiques et le navigateur privé.
Ses mentions de méthode courante et de question en attente sont historiques ;
la passation du 7 octobre décrit l'état final et les refus de l'utilisateur.

Dernière instruction : **chercher d’autres moyens de publier**, sortir du seul client
Google Edgerunners et cesser les mêmes demandes de revue Branding. Recherche terminée
dans `production/PUBLICATION_ALTERNATIVES.md` : Upload-Post propose son propre parcours
Google et l’envoi complet par API ; YouTube propose aussi l’ingestion podcast RSS
gratuite, avec image fixe, sans notre client OAuth. Aucun de ces parcours n’a encore
été testé sur les chaînes. Question de préférence en attente sur un relais externe,
auparavant refusé par l’utilisateur. Ne pas supposer ce refus levé ni changer le format
des vidéos sans accord. Aucun prestataire, flux public ou navigateur Google activé.

L’utilisateur reporte les statistiques et exige la publication automatique de Cage
et Pitch. Diagnostic serveur : identifiants OAuth présents, clé publique déjà
enregistrée, mais aucun jeton de chaîne pour ces deux sports. Publication immédiate
des vidéos prêtes ajoutée dans `studio/auto_publication.py`, sans créneau fixe, avec
tous les contrôles conservés. Google reçoit une permission `youtube.force-ssl`,
suffisante selon discovery officiel. Aucun déblocage Google ou envoi réel confirmé.
L’utilisateur a essayé le nouveau parcours et confirme encore **« This app is
blocked »**. Le contrôle serveur suivant retrouve les deux chaînes sans identifiant
YouTube ni jeton, activations désactivées, pause globale conservée. Les 108 tests
réussis ne prouvent aucun consentement. Ne pas redemander un essai inchangé ni une
clé API ; le dossier d’examen Google est dans `production/GOOGLE_REVIEW.md`.
La génération éditoriale totalement autonome reste à construire ; ne pas la présenter
comme activée ni recycler les trois vidéos déjà publiées manuellement.


À la demande explicite de l’utilisateur, la rubrique principale **Statistiques**
remplace les petites fiches dépendantes de la connexion OAuth. Recherche officielle
par @pseudo : YouTube Data API v3 `channels.list(forHandle=...)`, une clé API privée
pour toutes les chaînes, aucun compte à connecter pour les chiffres publics.
Périodes 24/48 h, 7/14/28 jours, comparaison et classement des chaînes, détail des
200 dernières vidéos, filtres Drylow/Kanye, likes/commentaires publics, CSV privé.
Relevés horaires indépendants des montages et de la pause, conservation 29 jours.
Les gains commencent au premier relevé et ne constituent pas l’historique privé
YouTube Analytics. La clé API de lecture a été configurée par l’utilisateur et sa
présence a été vérifiée sur le serveur ; ne pas lui redemander de la configurer.
Ne pas redemander OAuth pour ce suivi. Voir `studio/public_statistics.py` et
`GOOGLE_YOUTUBE.md`. Les essais utilisent exclusivement des données synthétiques.

Search Console confirme la propriété du domaine après ajout du TXT, à conserver.
Google Branding utilise encore l'ancien état et demande 24 heures : réessayer le
7 octobre après 17 h 25 (Paris), ou demander l'examen manuel dans View issues.
Le projet est External / In production. Les scopes auparavant déclarés restent non
vérifiés ; le site demande désormais seulement `youtube.force-ssl`.
« This app is blocked » reste non résolu ; ne pas annoncer une connexion réussie.
Le délai Branding n’établit pas la cause exacte de ce refus et ne garantit pas un
déblocage après 24 heures. Le compte propriétaire Search Console doit aussi être
Owner ou Editor du projet selon Google ; cette association n’a pas été vérifiée.

**Site en ligne sur https://edgerunners.fr/**. Sauvegarde privée de l'ancien site et
de SQLite vérifiée, ancienne interface remplacée, données conservées. Le code Git
reste dans `~/drylow_studio`, avec le nouveau Python `~/edgerunners_venv/bin/python`
et Node 22 disponible. Les vrais comptes sont `drylow` / `kanye` ; les mots de passe
initiaux sont dans `~/edgerunners-access.txt`, privé, jamais dans Git ni les logs.
Le worker autonome et le cron de développement sont installés ; Git en écriture,
npm et la version HTTPS réelle ont été vérifiés. Delamain a répondu sur le vrai site.
Son premier changement de code a été testé, installé, redémarré, vérifié en HTTPS
et poussé sur `main` (`b1da59e`) sans intervention manuelle dans son exécution.
Lire `DEPLOY_O2SWITCH.md` pour les chemins, les vérifications et les limites actuelles.
Le vieux cron HTTP est désactivé ; ne pas le relancer. Automatisation en pause.

**Publication sport, choix confirmé le 6 octobre** : Cage Dispatch et Pitch Dispatch
suivent l’actualité, sans heure fixe ni cadence quotidienne (`publication_mode=news`).
Leurs réglages masquent heure/cadence/stock cible et le planning ne suggère aucun
créneau. Les réservations explicites restent visibles ; les autres chaînes gardent
leur rythme. Ce choix n’active pas la production automatique, encore à terminer.

**Interface simplifiée à la demande de l'utilisateur le 6 octobre** : conserver le thème
Cyberpunk mais limiter la navigation principale à Accueil, Chaînes, Vidéos, Calendrier,
Tâches et Delamain. Les outils complémentaires sont sous « Autres outils », les Réglages
en bas du menu. Accueil : trois compteurs, actions à faire et trois dernières vidéos.
Liste des vidéos et agenda par défaut à toutes les tailles. Identité/style, budgets,
consignes, durée et priorité sont dans des sections à ouvrir ; les formulaires restent
fonctionnels et les erreurs de validation ouvrent la section concernée.
Les connexions YouTube sont accessibles depuis Chaînes ou Réglages → Connecter mes chaînes.
Le blocage Google « This app is blocked » reste à résoudre dans le projet existant ;
la connexion et l'automatisation ne sont pas déjà opérationnelles. Les captures du
6 octobre montrent une application externe en Testing et des liens/domaine Branding
non renseignés. Les pages publiques `/about`, `/privacy`, `/terms` et les liens de
l’écran de connexion sont ajoutés pour terminer cette configuration. Voir
`GOOGLE_YOUTUBE.md` pour les valeurs exactes et les limites du diagnostic.
L’utilisateur refuse les services de publication intermédiaires : API YouTube directe.

Les clés Google préexistaient sur o2switch et ont été conservées : ne pas redemander
un nouveau client sans vérifier l'existant. Le Grand Récap garde ses données de connexion,
mais Google retourne `invalid_grant` ; il faut une reconnexion. Les sept autres chaînes
ne sont pas reliées. Le relais de montage est joignable avec son jeton. Aucune vidéo
n'a été publiée automatiquement lors de cette installation.
L'ancien callback Google `/api/youtube/callback` est conservé via `OAUTH_CALLBACK_PATH`,
avec le nouveau handler protégé ; ne pas demander de recréer le client Google.

**Accès privé, choix confirmé par l’utilisateur** : la gate utilise seulement l'identifiant
et le mot de passe fort de chacun. L'utilisateur refuse toute application à installer
ou QR code ; ne pas remettre le code téléphone. Deux comptes maximum, sessions
révocables, essais limités, HTTPS obligatoire sur Passenger et aperçu interdit.
Lire `PRIVATE_ACCESS.md` et le guide o2switch actualisé. Préserver `FLASK_SECRET_KEY`.
Le domaine et le comportement réel Apache/Passenger ont été vérifiés, avec refus
des fichiers privés et révocation des sessions. Les accès cPanel sont fournis en variables privées `CPANEL_URL`,
`CPANEL_USER`, `CPANEL_PASSWORD` ; ne pas afficher leurs valeurs. Le bouton Save draft
peut les rendre disponibles sans publication : vérifier le runtime avant toute demande.

L'utilisateur veut construire un nouveau site central de gestion des chaînes, après la
livraison des trois analyses sportives du jour. **Lire `production/DASHBOARD_PLAN.md`** :
plan et réponses confirmées. Toute l'interface doit être remplacée (anciens studios inclus),
en thème Cyberpunk 2077 / Edgerunners. Conserver les outils récents et les données.
Deux comptes dans un espace partagé. Autonomie par chaîne ; MMA et foot seront en automatique,
avec contrôles obligatoires avant publication. **La première version est construite** :
onze pages, espace partagé, tâches/calendrier persistants, adaptateurs des moteurs récents,
agent, file de travaux et publication protégée. Toutes les anciennes interfaces sont supprimées.
Lire `production/DASHBOARD_STATUS.md` : lancement, vérifications et limites réelles.
Le radar lit les flux datés de BBC Sport, The Guardian et MMA News ; collecte régulière
configurable, désactivée par défaut. Delamain peut actualiser le radar et préparer une
fiche sans lancer de production. Les liens et titres identiques sont dédoublonnés.
Les faits, licences et choix éditoriaux autonomes restent à vérifier ; aucune cadence
de publication automatique réelle n'est active. Le serveur est déployé ; les connexions
Google doivent encore être finalisées. Les fiches affichent les étapes à compléter avant publication,
et les miniatures/planches de contrôle s'agrandissent avec zoom.

Nom choisi par l'utilisateur : **Edgerunners Studio**, en un seul mot avec un S.
L'ancien nom est remplacé dans l'affichage et les guides ; les noms techniques du
dépôt et des bases sont conservés pour préserver les données. Validation : 114 tests
Python et six parcours navigateur, sur ordinateur et mobile.

Chaque chaîne possède maintenant un bouton YouTube visible en Répartition, Fiches
et Réglages : connexion/reconnexion propriétaire, identité reliée, vérification réelle
de l'accès, confirmation avant déconnexion et pause automatique. Discord est facultatif
pour la publication directe. Aucun compte Google n'est connecté ici et aucun upload réel
n'a été testé. Guide `DEPLOY_O2SWITCH.md` réécrit : l'ancien zip, gate et cron HTTP ne
correspondent plus au nouveau site. Worker indépendant corrigé pour exécuter les actions
de Delamain via les mêmes routes que l'interface ; cron/flock documenté selon o2switch.
Le site pourra être mis à jour après hébergement via GitHub/redémarrage. Delamain est
un assistant intégré distinct de cette conversation ; l'agent de développement capable
de modifier, tester et déployer son code depuis le chat reste à brancher.

**Ring Dispatch est retirée le 5 octobre à la demande de l'utilisateur.** Sept chaînes
restent actives ; son historique est conservé, ses travaux en attente sont annulés.
Ne pas reprendre une ancienne production de cette chaîne ni la réactiver à l'import.
Le bloc Drylow possède maintenant sa ligne turquoise, assortie à l'avatar D.
Sur téléphone : Agenda/Liste par défaut, calendrier mensuel défilable sans élargir
la page, formulaires de 16 px et commandes tactiles, chat adapté au clavier.
Les essais couvrent six tailles, portrait et paysage, avec Chromium tactile émulé ;
ils ne constituent pas un essai sur un vrai iPhone/Safari.

Delamain gère les chaînes (ajout, retrait, réglages, attribution), les tâches,
fiches et créneaux, le radar et ses sources ; il lance les étapes script/rendu/contrôle,
publication et livraison protégées, annule un travail et affiche les miniatures
existantes avec lien vers la fiche. Il utilise l'identité de la session et les mêmes
routes que l'interface. Budgets, activation et modes sont réservés au propriétaire
pour l'agent. Plans et résultats sont conservés ; une action interrompue ne se répète
pas aveuglément. Une mise en file n'est pas une publication confirmée. Connexion
Google, droits et relecture humaine restent nécessaires ; la génération automatique
des miniatures sportives reste à construire. Hébergement permanent avec worker et
configuration IA nécessaire. Nouveaux essais d'actions avec réponses IA simulées,
sans appel payant ni publication réelle.

Ajouts demandés ensuite : centre de contrôle avec alertes et prochaines actions,
lecture propre à chaque utilisateur, état local des configurations et du moteur.
Routines partagées de recherche, publication et organisation hebdomadaire, sans
doublons et sans appels payants. Recherche/filtres/retards dans les tâches, accès à
la vidéo liée. Export mensuel `.ics` par chaîne ; copie du planning, pas abonnement.
Une perte de connexion affiche la dernière lecture et un bouton pour réessayer ;
la lecture reprend au retour du réseau. `studio/control.py` et les six parcours
`frontend/scripts/*smoke.mjs` portent ces contrôles. L'automatisation éditoriale,
les droits complets et la connexion réelle Google restent à terminer comme indiqué
dans le document d'état ; ne pas les présenter comme opérationnels.

L'équipe utilise les pseudos **Drylow** et **Kanye**. La page Chaînes propose une
répartition par glisser-déposer et sélecteur mobile ; les chaînes restent à répartir
tant que l'utilisateur ne les attribue pas. Ne pas deviner leur responsable.
Attribution par identifiant du vrai compte, sans restriction d'accès ni changement
des vidéos, tâches ou modes. Le calendrier possède un filtre « Mes chaînes » et la
vue « Qui poste ? » : suggestions de cadence ancrées, vidéos réellement réservées
et contrôles encore nécessaires. Une suggestion ne programme rien et ne lance
aucun job. Le transfert suit immédiatement dans le planning et l'export personnel.
Les comptes d'aperçu sont `drylow` et `collegue` (affichage Kanye) ; les vrais comptes
se créent dans Réglages → Équipe. Le serveur utilise Europe/Paris, y compris le
changement d'heure. Modules `studio/schedule.py` / `planning.py`, parcours `smoke:team`.

Les miniatures récentes sont approuvées : références dans
`presets/news_thumbnails/approved_2026-10-05/`. L'utilisateur demande de ne plus refaire
celles des vidéos actuelles et de garder ce thème pour les prochaines. Les preuves de droits
et les limites de l'automatisation sont décrites dans `production/NEWS_BRIEFS.md`.
Les anciennes étapes de connexion ci-dessous sont un historique : ne pas redemander des
clés déjà fournies ni refaire l'onboarding cloud terminé dans cette conversation.

## Historique de reprise — 3 octobre 2026

L'utilisateur arrive au bout de son usage sur son compte et continue sur **le compte de son pote**, « comme
si je travaillais ici ». Ce fichier dit **où on en est** et **comment démarrer**. Le guide de travail reste
`CLAUDE.md` (à lire en entier) ; le journal des vidéos, `production/VIDEOS.md`.

## 1. Démarrer sur le nouveau compte (une fois)

1. **GitHub** : le compte GitHub relié au Claude du pote doit pouvoir **pousser** sur `drylow/studio` (le
   propriétaire du dépôt l'ajoute en collaborateur, ou installe l'app Claude GitHub sur le dépôt). Connexion :
   https://claude.ai/connect-github. Ouvrir la session avec le dépôt `drylow/studio` sélectionné.
2. **Secrets** (jamais dans git) : dans l'environnement cloud du compte (menu de l'environnement dans la barre
   de titre de la session → Modifier → variables d'environnement), coller les lignes du `.env` (l'utilisateur a
   ses clés ; jamais par le chat ni dans git). Le code lit le `.env` du dépôt, que `production/session_start.sh`
   recrée depuis ces variables.
   Variables : `FLASK_ENV`, `COOKIE_SECURE`, `FLASK_SECRET_KEY`, `ACCESS_PASSWORD`, `BOSS_PASSWORD`,
   `AI_BASE_URL`, `AI_API_KEY`, `AI_TEXT_MODEL`, `AI_FAST_MODEL`, `AI_IMAGE_MODEL`, `AI_IMAGE_CONCURRENCY`,
   `ALGROW_API_KEY` (voix), `DISCORD_WEBHOOK_URL` (paquets), `NEWS_WORKER_URL` + `NEWS_WORKER_TOKEN` (relais du
   VPS → PC). Pour History Docs en plus : `AI33_API_KEY`, `RUNPOD_*`, `RENDER_WORKERS` / `RENDER_WORKER_TOKEN`.
   **Ne jamais demander de coller une clé dans le chat.**
3. **Connecteur NexLev** (recherche YouTube, transcriptions, analyse de vidéos) : à connecter sur
   https://claude.ai/customize/connectors, puis nouvelle session. Indispensable pour l'actu (sources du jour).
4. Au début de chaque session : `bash production/session_start.sh` (hook git commit = push branche + main, et `.env`
   recréé depuis les variables d'environnement s'il manque).
5. Rien à refaire côté PC : l'agent « Drylow Actu » du PC et le relais du VPS marchent avec l'URL + le jeton du
   `.env` (mêmes valeurs).

## 2. En cours au moment du changement de compte (3 oct., ~23 h 50 heure belge)

Deux vidéos Cage Dispatch en montage sur le PC de l'utilisateur, **toutes les deux en bleu** (thème de la chaîne,
demandé par l'utilisateur : « on va faire que du bleu »). Il attend les liens pour les poster :
1. **Gaethje v4** (`news/mma_en/2026-10-02_gaethje-topuria`) : refaite **sans les extraits de One Night with Steiny**
   (revendication Content ID sur la v3), commence par la voix off + photo, titre « “HE HAS TO BELIEVE THAT I
   CHEATED!” Justin Gaethje FIRES BACK At Ilia Topuria’s Glove Claim! », miniature validée “I BROKE HIS FACE” (bleu
   clair). Une version rouge a été montée juste avant le passage au bleu : **ne pas l'envoyer** ; la bleue est
   redéposée automatiquement après (script `requeue` de la session).
2. **Topuria #2** (`news/mma_en/2026-10-03_topuria-…`) : « “IT'S NOT GOING TO HAPPEN!” Arman Tsarukyan SHUTS DOWN
   Topuria As Ilia Returns To Training! », ~18 min, miniature validée Tsarukyan + Topuria “IT'S NOT GOING TO HAPPEN”.

Pour chacune : `python production/news.py pc-fetch <dossier> --wait` (en tâche de fond), vérifier `result.json`
(heure récente, durée ~16 min Gaethje / ~18 min Topuria, cadre **bleu**) puis **toutes** les planches
`check/sheet_*.jpg` (pas de morceaux de l'ancien style rouge/jaune, pas de Steiny), puis
`python production/news.py send <dossier> --corrigee` pour Gaethje, `send <dossier>` pour Topuria, et donner le lien.
Si l'état est encore « claimed » avec l'ancienne vidéo : la redéposer avec `news.py vps <dossier> --pc --no-wait`.

Ensuite, ce qu'il veut :
1. **Poster vite et beaucoup** dès qu'il y a de l'actu MMA (« faut pas que ce soit parfait… il va falloir poster
   beaucoup, beaucoup ») : vite, mais toujours vérifié (planches, bon nom sur la bonne personne, vraies citations,
   sources sans revendication).
2. Lancer les chaînes **boxe** (`boxing_en`, RING DISPATCH) et **foot** (`football_en`, PITCH DISPATCH) : configs
   prêtes dans `newsvid.CHANNELS`, **sources vides** (à remplir avec des chaînes sans Content ID, vérifiées avec
   NexLev `get_content_owner`). Vérifier la demande et les concurrents avec NexLev avant.

En attente d'une réponse de l'utilisateur :
- **Oddly Specific Lives, sport suivant** : proposé « POV: You Marry a Female Premier League Footballer » (ou
  NWSL) ; il n'a pas encore choisi.
- **Chaîne « listes sombres » façon Riff Rotten** (`chaines/_nouvelles/README.md` §1) : outil à construire,
  il doit choisir le thème.

## 2 bis. État au 4 oct., 04h35 heure belge

- **Cage Dispatch #2 (Topuria)** et **Pitch Dispatch #1 (Ronaldo / Jorge Jesus)** : envoyées sur Discord, à poster.
- **Ring Dispatch #1 (Fury vs Joshua, “MENTALLY WEAK!”)** : tout est prêt (plan relu, voix, miniature dorée), le
  montage a été coupé parce que l'utilisateur a éteint son PC. Le job est redéposé sur le relais : le PC le monte tout
  seul au prochain démarrage. Ensuite : `python production/news.py pc-fetch news/boxing_en/2026-10-03_tyson-fury-vs-anthony-joshua-turns-ugly-eddie-he --wait`,
  vérifier les planches (sous-titres au-dessus de la bande bleue de The Stomping Ground), puis `news.py send <dossier>`.
- Mode 100 % auto (`news_auto.py`) : en attente de la décision de l'utilisateur (voir CLAUDE.md §11) ; il pense le
  faire plus tard avec un tableau de bord des chaînes.

## 3. Cage Dispatch : comment on fait une vidéo d'actu (rodé le 3 oct.)

Tout est dans `CLAUDE.md` §11 ; la chaîne de commandes est en tête de `production/news.py`. En bref :
1. Sources du jour avec NexLev (`youtube_search`, upload_date today/week) : interviews originales (podcast du
   combattant, Flagrant, Helwani, Cormier, Sonnen, Bisping, conférences). `youtube_channel_videos` sur Fight
   Night MMA pour voir le sujet du moment (ne jamais reprendre leurs extraits).
2. Transcriptions `get_bulk_video_transcripts` → `news.py new mma_en "<sujet>"` → `import` → `moments` →
   `plan --context "faits vérifiés"` → **relire plan.json** (voix off = ce que dit l'extrait ; ouverture qui
   donne le contexte ; titres = citations vraiment dites) → `headlines` → `voice` (vérifier les noms à
   l'oreille avec Whisper si nouveau nom : `newsvid.PRONOUNCE`) → `thumb` (2 photos + citation, variante A
   validée) → relire les sous-titres (`_wrap_subs` sur chaque extrait, corriger les noms via
   `plan["spelling"]`) → commit.
3. Montage sur le PC de l'utilisateur : `python production/news.py vps <dossier> --pc --no-wait`, puis
   `pc-fetch <dossier> --wait` en tâche de fond. Depuis le 3 oct. au soir l'agent du PC **reste à l'écoute** (vérifie
   le relais toutes les 20 s, enchaîne les vidéos ; mis à jour tout seul par `news.py build` → `update_pc_agent`) ;
   montage ≈ 18 min pour 20 min de vidéo ; le PC doit être allumé. Chaque montage part d'un dossier neuf (avant : des
   morceaux d'un vieux montage resté bloqué avaient été recollés dans la vidéo).
4. Regarder **toutes** les planches `check/sheet_*.jpg` (une image / 10 s), puis
   `python production/news.py send <dossier>` (`--corrigee` si c'est une version refaite) → donner le lien.

Réglages validés par l'utilisateur (v3, après « pas carré ») : voir `CLAUDE.md` §11 « Montage façon Fight
Night MMA ». **Tout en bleu** (cadre, logo, bandeaux #12A8E0, phrase forte et miniature #40DCF8 = bleu de la
bannière @CageDispatch). Miniature : deux photos face à face (`photos/`, jamais une photo à plusieurs combattants),
la citation **entre guillemets**, sur 2 lignes, mot fort en bleu clair, assez haute, jamais coupée. La vidéo
**commence par la voix off d'intro sur la photo** (plus d'ouverture en extraits). **Droits** : sources seulement
de chaînes sans Content ID (`newsvid.CLAIMERS` refusées : Steiny, Full Send, UFC, MMA Fighting, Mighty).

Pièges vus le 3 oct. :
- Le relais peut renvoyer un **vieux build.log** (un ancien agent du PC, endormi pendant un montage, renvoie
  encore son journal) : se fier à `result.json` (heure, nombre de segments) et aux planches, pas au journal.
  Amélioration possible (pas faite) : un numéro de prise de la vidéo dans `/pc/next`, que le relais exige pour
  `/pc/result` et `/pc/done` (demande de relancer l'installateur du VPS au pote + nouveau zip d'agent).
- Le pote doit relancer l'installateur du VPS une fois pour avoir la version « reproposer après 20 min sans
  nouvelles » du relais (pas urgent).
- Transcriptions NexLev : noms écorchés (« Sukian » = Tsarukyan, « Iliotia » = Ilia Topuria) et tirets « — »
  dans certaines (Kolos MMA) : `_tidy` les transforme en « ... ».

## 4. Vidéos livrées récemment (détail dans `production/VIDEOS.md`)

- **Cage Dispatch #1** « HE SHOULD HAVE QUIT ON THE STOOL! » Justin Gaethje SHUTS DOWN Ilia Topuria Rematch! —
  v3 CORRIGÉE envoyée sur Discord le 3 oct. 19:33 UTC (https://gofile.io/d/CRp2y8tX, 20 min 12). L'utilisateur
  la poste.
- **Oddly Specific Lives** : POV: You Marry a Female Assassin (livrée 3 oct.), UFC Fighter, WNBA Star…
- **Oddly Specific Things** : Stolen Phone, Car, Credit Card (livrées).

## 5. Ce que l'utilisateur a dit sur sa façon de travailler (à respecter)

- Il ne veut **rien faire lui-même** : « c'est toi qui vas monter mes vidéos… tu vas tout faire toi-même ».
  Pas de manip à lui demander s'il y a un autre moyen ; pas de compte Google jetable, pas de cookies.
- Il poste lui-même depuis Discord ; il veut un seul lien, le bon, marqué clairement.
- Il juge vite sur la 1re minute : l'ouverture doit être claire (on voit de qui on parle), rien qui coupe une
  réponse, pas d'effets « bizarres », texte propre.
- Il est sur téléphone : réponses courtes, **jamais d'heure UTC** : « dans 20 min » + heure belge, chiffres.
