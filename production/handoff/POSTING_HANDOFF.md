# Reprise pour automatiser la publication

Passation du **14 octobre 2026**. La demande exécutée dans cette session est
la sauvegarde GitHub des méthodes, sources et états de production. **Aucune
vidéo n'est publiée, programmée, supprimée ou déployée par cette passation.**
L'utilisateur veut ensuite travailler sur la publication automatique avec son
collègue, en passant par les profils **Fury sur son PC**.

Lire [le registre des chaînes](CHANNELS.md) avant de connecter quoi que ce soit,
puis [les outils de production et livraison](TOOLS.md). Un rendu TubeForge ou
un GoFile confirmé n'est pas un upload YouTube.

## Derniers fichiers prêts à publier

| Chaîne | Kit final | État de publication connu |
| --- | --- | --- |
| Viking Chapters | [GoFile](https://gofile.io/d/Zd5AhFJi), **19:26**, vidéo + quatre miniatures + `UPLOAD.txt` + SRT | Livré, aucun upload effectué par cet agent ; miniature à choisir. |
| Pirate Pages | [GoFile](https://gofile.io/d/e2AjnCyr), **19:45**, même composition de sept fichiers | Livré, aucun upload effectué par cet agent ; miniature à choisir. |
| Samurai Chapters | [GoFile](https://gofile.io/d/M9RLsD1P), **19:39** | Publication annoncée par l'utilisateur ; ne pas publier un doublon. Miniature finale choisie ensuite : **PAID IN RICE**. |
| Scene Analysis Guy | Voir les fiches par épisode dans [CHANNELS.md](CHANNELS.md) | Uploads manuels et résultats de droits variables ; ne pas republier Peaky, abandonné après blocage. |

Le kit Viking conserve
[UPLOAD.txt](../../chaines/viking-chapters/episode-01/delivery/UPLOAD.txt) et
[English-Captions.srt](../../chaines/viking-chapters/episode-01/delivery/English-Captions.srt)
dans `delivery/`. Le kit Pirate les conserve dans `editorial/` :
[UPLOAD.txt](../../chaines/pirate-pages/episode-01/editorial/UPLOAD.txt) et
[English-Captions.srt](../../chaines/pirate-pages/episode-01/editorial/English-Captions.srt).
Ces fichiers sont propres à leur **film exact et leur horloge de voix VPS**.
Ne pas ajouter une seconde voix au MP4 sonorisé, reprendre des chapitres de
l'ancienne voix ou choisir arbitrairement une des quatre miniatures.

Les hashes du film exact sont dans [CHANNELS.md](CHANNELS.md) et les manifestes
de livraison. Avant d'envoyer un média récupéré, comparer son SHA-256 à celui
du film final retenu. Le futur journal de publication devra lier ce hash au
`video_id` YouTube obtenu : une réussite de livraison n'est pas une preuve de
publication.

## Ce qui manque pour les nouvelles chaînes

**L'intégration Fury vers YouTube n'a pas été réalisée ni testée pour ces
chaînes dans cette conversation.** Le cloud de production ne dispose pas
automatiquement du PC, de ses profils ni des sessions Google de l'utilisateur.
Les demandes antérieures portaient sur la possibilité d'y accéder **après**
la livraison des films ; elles ne prouvent pas un accès déjà opérationnel.

Avant un premier test d'intégration, relever réellement cette correspondance
dans le profil connecté, sans recopier les sessions dans Git :

| Champ de routage | Pourquoi il faut sa valeur réelle |
| --- | --- |
| Nom de la chaîne et identifiant YouTube `UC…` | Confirmer la destination, surtout si plusieurs chaînes partagent le même compte Google. |
| Nom et ID du profil Fury | Ouvrir le profil existant approprié ; un intitulé « Chaîne #30 » n'identifie pas une chaîne YouTube. |
| Propriétaire / opérateur et machine d'exécution | Déterminer qui lance et supervise le processus PC réellement accessible. |
| Publication privée, non répertoriée ou publique, calendrier et fuseau | Ne pas transformer une livraison à l'utilisateur en publication publique ou date inventée. |
| Titre et miniature retenus pour le film exact | Les propositions A/B/C/D ne sont pas une décision finale. |
| Statut de Checks du fichier exact pour les extraits tiers | Documenter blocage, claim et territoires avant de finaliser un contenu réutilisé. |

L'identifiant d'un **projet ou d'une chaîne TubeForge**, l'identifiant d'un
**profil Fury** et l'identifiant public **YouTube** sont trois choses différentes.
Ne pas réutiliser un de ces IDs dans le champ d'un autre service. Ne pas
supposer qu'un handle suggéré par une recherche est le handle attribué.

## Fury : ce que le dépôt sait déjà, dans un autre dossier

Une autre conversation a documenté l'application et des profils de navigateur
sur le PC. Lire
[RECAP_CHESS_PROFILS_2026-10-12.md, section Fury](../RECAP_CHESS_PROFILS_2026-10-12.md).
Elle décrit dix profils locaux **#30 à #39**, pas dix comptes Google créés,
connectés ni associés aux nouvelles chaînes historiques.

- Application et agent Windows : sous
  `C:/Users/ytbyt/AppData/Local/Fury/`.
- Données privées : `C:/Users/ytbyt/AppData/Roaming/Fury/`, dont `fury.db`,
  `profiles/` et le fichier `api-token`. **Ni base, ni profils, ni token dans Git.**
- Dans cette ancienne session, le MCP HTTP local sur `127.0.0.1:35000` refusait
  la connexion. Le canal local de l'application utilisé par les scripts a
  fonctionné pour lire/créer des profils. Ces résultats ne sont pas un test
  de publication YouTube ni un contrôle de disponibilité aujourd'hui.
- Les scripts et reçus Windows cités dans cette reprise étaient dans un autre
  dossier local, pas dans ce clone cloud. Vérifier leur présence et lire leur
  code avant de les utiliser. **Ne pas relancer un script de création de profils
  pour accéder à des profils existants.**

Le premier travail utile est donc une lecture des profils existants et de la
chaîne effectivement connectée, puis un adaptateur testé sur une destination
et un média clairement identifiés. Ne pas inventer un endpoint Fury, installer
une seconde application de publication ou multiplier les profils pour résoudre
un problème d'upload.

## Contrat pratique du futur exécuteur

Conserver un état de publication distinct de la production, avec au minimum :

1. Le nom éditorial de chaîne, son `youtube_channel_id` confirmé et le profil
   autorisé choisi, sans cookies ni token dans le journal public.
2. Le SHA-256 du MP4 final, les empreintes du titre, de la description, de la
   miniature sélectionnée et du SRT éventuellement joint.
3. La demande de visibilité et, si demandé, l'horaire **Europe/Paris**.
4. Un état explicite : préparé, envoyé, traitement, Checks, programmé ou publié.
   En cas d'interruption après un envoi possible, vérifier l'état distant avant
   toute relance ; conserver un résultat inconnu au lieu de créer un doublon.
5. L'identifiant/URL de la vidéo obtenu, le résultat du contrôle de droits et
   la vérification de la bonne chaîne et de la bonne visibilité.

Cette liste décrit l'interface à construire, **pas un exécuteur déjà implémenté**.
L'utilisateur a demandé de préparer ce travail avec son collègue ; le push de
cette passation ne déclenche pas ces actions.

Les garde-fous de livraison existants fournissent déjà empreintes, revue et
gestion des résultats incertains. S'en inspirer sans confondre un reçu GoFile
ou Discord avec un reçu YouTube. Aucun contrôle technique ne remplace le choix
éditorial de titre/miniature ni les droits nécessaires au contenu.

## Publication serveur déjà présente : périmètre distinct

Le dépôt contient aussi une intégration YouTube côté **Edgerunners Studio** :

- `studio/youtube.py` : OAuth, attribution de la chaîne réelle, vérification
  d'accès et déconnexion avec suspension.
- `studio/youtube_permissions.py` : scopes séparés selon le besoin.
- `studio/jobs.py` et `studio/worker.py` : file contrôlée de jobs.
- `studio/autonews.py` : pilote des actualités **Cage Dispatch / Pitch Dispatch**.
- [Passation du 7 octobre](../CLAUDE_HANDOFF_2026-10-07.md),
  [reprise serveur](../REPRISE.md) et `AGENTS.md` : fonctionnement documenté
  sur o2switch, OAuth en Testing et limite historique de deux vidéos par jour
  et par chaîne.

Cette automatisation n'a pas été nouvellement vérifiée à distance dans le push
actuel. L'état du code ou une connexion enregistrée le 7 octobre ne garantit
pas que les jetons sont encore valides le 14 octobre. Ne pas activer le pilote
news pour Samurai/Viking/Pirate : ces chaînes n'ont ni ses sujets ni sa méthode.
Ne pas remplacer une automatisation existante par Fury sans examiner son état.

Le choix futur exprimé pour les nouvelles chaînes est Fury. Les restrictions
historiques du parcours PC dans `CLAUDE.md` concernaient l'ancien problème de
connexion des chaînes news ; elles ne constituent pas la preuve que ce nouveau
parcours a été construit ou testé.

## TikTok : reprendre les horaires sans les annoncer vérifiés aujourd'hui

**Octave Histoire**, `@octave.histoire`, est un compte distinct des chaînes
YouTube ci-dessus. Sa fabrication et sa programmation utilisent
`tiktok_engine/`, Algrow et **Zernio** :
[README](../../tiktok_engine/README.md), [routine](../../tiktok_engine/ROUTINE.md),
[rendu VPS](../../tiktok_engine/VPS.md).

L'état daté du 10 octobre décrit des créneaux à **7 h et 19 h, Europe/Brussels**,
jusqu'au 22 octobre, et les fichiers `zernio.json` correspondants. Ces données
sont conservées, mais aucun nouveau contrôle Zernio n'a été exécuté pour cette
passation Git. Avant de compléter un calendrier, lire la file distante réelle
et les reçus locaux afin de ne pas prendre un créneau déjà occupé. Aucune
nouvelle vidéo TikTok n'est créée ni programmée ici.

## Accès et secrets à transmettre séparément

Le dépôt est public. Les sources et exemples de configuration peuvent donner
**des noms de variables**, jamais les valeurs de : mots de passe cPanel, clés
de fournisseurs, sessions TubeForge/GoFile, jetons de worker, refresh tokens
Google, clés SSH, cookies, sessions Fury ou URL de webhook Discord.

- Edgerunners/o2switch : noms `CPANEL_URL`, `CPANEL_USER`, `CPANEL_PASSWORD`
  fournis par l'environnement privé ; autres paramètres dans le `.env` privé
  du serveur. `production/server_env.py` peut importer des variables nommées
  vers le `.env` local ignoré, sans les afficher.
- TubeForge hébergé : accès personnel du collègue et session privée, procédure
  dans [TOOLS.md](TOOLS.md). Le CLI générique du dépôt ne transporte pas les
  secrets du ZIP SSH ou du handoff original. Les cinq fichiers originaux sont
  conservés dans [le coffre chiffré](access/README.md), avec déchiffrement vérifié
  à l'aide d'une clé privée séparée. Le mode de récupération cPanel n'est pas
  activé : aucun dépôt externe de la clé n'a été effectué.
- Fury : accès local via l'application réellement installée ; ne pas exporter
  les profils de connexion pour « compléter » le dépôt GitHub.
- Discord : routage par variable de webhook propre à chaque chaîne. Pour
  Scene Analysis Guy, `DISCORD_WEBHOOK_SCENE_ANALYSIS_GUY`. Ne jamais tomber
  silencieusement sur le salon Cage/Pitch ou un webhook générique.

Récupérer les valeurs depuis les accès privés autorisés ; ne pas demander de
recoller des mots de passe ou tokens dans un ticket, une pull request ou un
fichier public. Les médias finaux restent accessibles par les GoFile livrés et
leurs hashes ; la sauvegarde Git des méthodes n'est pas une sauvegarde des
comptes connectés.
