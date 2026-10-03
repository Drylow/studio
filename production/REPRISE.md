# Reprise sur un autre compte Claude (état au 3 oct. 2026, 20 h UTC)

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

## 2. Ce que l'utilisateur veut maintenant (dans l'ordre)

1. **Cage Dispatch #2 : Ilia Topuria reprend l'entraînement** (c'est le dernier sujet de Fight Night MMA, la
   chaîne modèle). À poster **dès qu'elle est prête**. Même chaîne `mma_en`, même montage v3.
2. Lancer les chaînes **boxe** (`boxing_en`, RING DISPATCH, or #D4A017) et **foot** (`football_en`, PITCH
   DISPATCH, vert #1DB954) : configs prêtes dans `newsvid.CHANNELS`, **sources vides** (à remplir : chaînes
   YouTube originales des promoteurs, conférences, podcasts ; jamais des compilations). Vérifier la demande et
   les concurrents avec NexLev avant.
3. **Volume avant perfection pour l'actu** (l'utilisateur, 3 oct. : « faut pas que ce soit parfait… dès qu'il va
   y avoir de l'actualité, il va falloir poster beaucoup, beaucoup ») : vite, mais toujours vérifié (planches,
   pas de nom sur la mauvaise personne, pas de faux propos).

En attente d'une réponse de l'utilisateur :
- **Oddly Specific Lives, sport suivant** : proposé « POV: You Marry a Female Premier League Footballer » (ou
  NWSL) ; il n'a pas encore choisi.
- **Chaîne « listes sombres » façon Riff Rotten** (`chaines/_nouvelles/README.md` §1) : outil à construire,
  il doit choisir le thème.

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
   `pc-fetch <dossier> --wait` en tâche de fond (le PC passe toutes les 15 min ; montage ≈ 18 min pour 20 min
   de vidéo ; il faut que son PC soit allumé).
4. Regarder **toutes** les planches `check/sheet_*.jpg` (une image / 10 s), puis
   `python production/news.py send <dossier>` (`--corrigee` si c'est une version refaite) → donner le lien.

Réglages validés par l'utilisateur (v3, après « pas carré ») : voir `CLAUDE.md` §11 « Montage façon Fight
Night MMA ». Miniature : deux photos face à face (`photos/`), citation énorme blanche + mot fort jaune,
**texte assez haut, jamais coupé**.

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
- Il est sur téléphone : réponses courtes, heures UTC, chiffres.
