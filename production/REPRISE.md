# Reprise sur un autre compte Claude (historique et état actuel)

## Priorité actuelle — 5 octobre 2026

L'utilisateur veut construire un nouveau site central de gestion des chaînes, après la
livraison des trois analyses sportives du jour. **Lire `production/DASHBOARD_PLAN.md`** :
plan et réponses confirmées. Toute l'interface doit être remplacée (anciens studios inclus),
en thème Cyberpunk 2077 / Edgerunners. Conserver les outils récents et les données.
Deux comptes dans un espace partagé. Autonomie par chaîne ; MMA et foot seront en automatique,
avec contrôles obligatoires avant publication. Le plan est enregistré ; le site n'est pas encore refait.

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
