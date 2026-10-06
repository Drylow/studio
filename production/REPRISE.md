# Reprise sur un autre compte Claude (historique et état actuel)

## Priorité actuelle — 6 octobre 2026

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
