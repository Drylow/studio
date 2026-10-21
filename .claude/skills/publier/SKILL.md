---
name: publier
description: Sur le PC de l'utilisateur (Windows), publie les vidéos de ses chaînes YouTube (Last Safe Door, Scene Analysis Guy, Última Puerta Segura) depuis leurs profils Fury ou AdsPower. À lancer quand l'utilisateur tape /publier ou demande de publier, programmer ou automatiser ces chaînes.
---

# Publier sur les chaînes de l'utilisateur depuis Fury et AdsPower

Décision de l'utilisateur du 14 octobre 2026 : ses chaînes se publient depuis les profils de
navigateur où sont ses comptes, **Fury** et **AdsPower**, sur ce PC. Pas de Zernio ni d'API YouTube
pour ces 5 chaînes. Samurai Chapters est retirée (compte Google mort, 15 oct.) : ne rien publier dessus. **21 oct. : Viking Chapters, Pirate Pages et One Stick Left sont supprimées** (décision de l'utilisateur) : ne plus rien publier dessus, leurs fiches sont dans `production/publish/retired/`. Cage Dispatch, Pitch Dispatch (serveur) et Octave Histoire (Zernio) ne changent pas.

Parle-lui en français simple et court (CLAUDE.md §1). Il ne veut rien faire à la main : installe toi-même
ce qui manque, il clique seulement « Autoriser ». Les chaînes du collègue (Patch Survives, Alien Aftermath,
Deep Sea Survival, Oddly Fictional Lives…) ne te concernent pas.

## Les chaînes et leurs profils

`production/publish/channels.json` : le **nom du profil = le nom de la chaîne**.
- AdsPower : **Última Puerta Segura** (chaîne espagnole, 21 oct. ; profil renommé par l'utilisateur ; fiches `ltima-puerta-segura--*.json`, `visibility: public` = publier tout de suite, dans l'ordre des épisodes 1 → 4).
- Fury : **Last Safe Door**, **Scene Analysis Guy**.

## Étape 1 : le PC et ses outils (en place depuis le 14 oct.)

Notice locale du PC : `work/publish/LISEZMOI-PC.md` (pas dans git). L'essentiel :
- PC Windows, utilisateur `drylo`. Clone : `C:\Users\drylo\Bureau\2D slop\studio`, depth 1, sparse
  (`/CLAUDE.md /AGENTS.md /.claude/ /production/publish/`). Ajoute au sparse les chemins cités par une
  fiche (description, SRT, miniature) avant de la traiter.
- Venv `work/venv` : Python 3.13 + Playwright, branché en CDP sur les profils. Aucun navigateur
  téléchargé.
- `work/publish/profile.py open|close|status "<Chaîne>"` ouvre le profil et donne l'adresse CDP pour
  `connect_over_cdp`. Correspondance chaîne → profil dans `work/publish/profiles.json` (local).
- **Fury 0.2.23** : `%LOCALAPPDATA%\Fury\fury-agent.exe mcp`, un serveur MCP stdio qui pilote
  seulement les profils locaux.
  - Les chaînes Fury utilisent les copies locales « <Chaîne> - local import », chacune avec son
    proxy. Ne plus utiliser les copies d'équipe.
  - `fury_start_profile` ne donne pas l'adresse CDP : le navigateur part avec
    `--remote-debugging-port=0`. Le vrai port est celui qu'écoute, sur 127.0.0.1, le processus
    principal (exe sous `%APPDATA%\Fury\core.bundle\`, sans `--type=`) et qui répond à `/json/version`.
  - Un seul profil Fury ouvert à la fois.
- **AdsPower 7.12** : API locale.
  - Port variable, retrouvé automatiquement.
  - En-tête `Authorization: Bearer <clé du .env>`, environ 1 requête par seconde au maximum.
  - Routes : `/api/v1/browser/start|stop?user_id=…`, puis `data.ws.puppeteer`.
- **YouTube Studio** (interface en anglais sur les chaînes) :
  - nom de la chaîne : `#entity-name` après la redirection vers `/channel/UC…` ;
  - langue : `document.documentElement.lang` ;
  - proxys parfois lents : `wait_until="commit"`.
- Jamais lus ni copiés : `%APPDATA%\Fury\profiles\`, `fury.db`, cookies, `api-token`.

**Passages programmés** : une tâche de l'appli Claude passe toutes les 3 h, de 8 h à 23 h (heure de
Belgique). Elle fait `git pull` puis relit ce fichier et traite les fiches de `production/publish/queue/`.
Fury et AdsPower sont relancés au besoin. Le PC doit être allumé, avec l'appli Claude ouverte.

## Étape 2 : contrôle sans rien publier

Pour chaque chaîne, une à la fois :
1. Ouvre son profil par l'API de son application.
2. Connecte Playwright au profil ouvert (`chromium.connect_over_cdp(ws)`), sans lancer un autre navigateur.
3. Ouvre `https://studio.youtube.com` et lis le nom de la chaîne affichée. Il doit être exactement
   celui du profil.
4. Ferme le profil.

Donne le résultat à l'utilisateur en une ligne par chaîne. Une chaîne qui ne correspond pas : stop, on
ne publie rien dessus. Ne touche à aucun réglage du compte, du profil ou de la chaîne.

## Étape 3 : publier une vidéo

Une vidéo à publier = un fichier `production/publish/queue/<chaîne>--<vidéo>.json` préparé par le
Claude du cloud (format dans `production/publish/README.md`). **Une vidéo à la fois, un profil ouvert à
la fois.** Avant le bouton final, fais une capture de l'écran et relis-la : bonne chaîne, bon
titre, bonne miniature, « not made for kids », bonne visibilité et bonne date. Au moindre doute, ne
publie pas et note pourquoi.

1. Récupère le MP4 (lien Gofile, ou le fichier déjà sur ce PC), puis vérifie son SHA-256 avec celui
   de la fiche. Différent : stop.
2. Ouvre le profil, connecte Playwright, va dans YouTube Studio. Vérifie le nom de la chaîne.
3. Regarde la liste des contenus : si une vidéo avec ce titre existe déjà, ne renvoie rien.
   Note-le et demande à l'utilisateur.
4. Créer → Importer des vidéos. Ensuite :
   - fichier ;
   - titre, description et miniature de la fiche ;
   - « Non, cette vidéo n'est pas conçue pour les enfants » ;
   - tags du fichier `tags_file` s'il est dans la fiche (« Afficher plus » → Tags, séparés par des virgules) ;
   - sous-titres SRT s'il y en a ;
   - visibilité ou date de programmation de la fiche (heure de Bruxelles).
   - si `publish_at` est déjà passé (le PC était éteint), ne refuse pas la fiche : publie en public
     tout de suite. Une chaîne qui a deux fiches en retard : seulement la plus ancienne (l'épisode le plus
     petit) à ce passage, la suivante garde sa date si elle est encore à venir.
   - **fiche avec `"copyright_check": "private_first"`** (Scene Analysis Guy : extraits de films et
     séries) : à l'envoi, mets la visibilité **Privée**, pas la date. Attends la fin de
     « Checks / Vérifications » (onglet Contenu, colonne Restrictions, ou étape Checks de l'envoi), puis :
     - « No issues found » ou **claim simple** (Content ID, revenus au titulaire ou suivi, **sans blocage
       ni avertissement**) → programme à la date de la fiche (en public tout de suite si elle est passée) ;
       note le ou les claims (titulaire, passages) dans le journal ;
     - **blocage** (monde entier ou quelques pays), retrait, avertissement / strike → **ne publie pas**,
       laisse la vidéo en privé, note « blocked » avec les détails. Ne conteste rien, ne retouche pas la
       vidéo pour tromper la détection ;
     - Checks pas finis en 30 min → laisse en privé, note « checks_pending », reprends au passage suivant
       (la vidéo existe déjà : ne la renvoie pas).
     - fiche avec un champ `copyright_rule` : il prime sur les deux premières règles (ex. claim simple
       refusé : laisse en privé et note « claimed »).
5. Attends la fin de l'envoi. Relève le lien de la vidéo et l'état des droits d'auteur (vérification
   YouTube). Ferme le profil.
6. Ajoute une ligne au journal : chaîne, titre, SHA-256, `video_id`, visibilité, date, état des
   droits. Pour l'instant, c'est le journal local `work/publish/log.jsonl`, car le PC n'a pas
   d'accès GitHub. Quand GitHub sera connecté sur le PC : `production/publish/log.jsonl`, commit en
   anglais, `git pull --rebase`, push sur `main`.
   Une fiche déjà traitée (publiée ou refusée) ne se retraite jamais : le journal fait foi.
7. Un envoi coupé au milieu : **ne recommence pas à l'aveugle**. Regarde d'abord dans Studio si la
   vidéo existe déjà (brouillon compris).

Ne touche jamais une vidéo déjà en ligne (titre, miniature, suppression) sans demande de l'utilisateur.
Après chaque envoi, donne-lui le lien et le titre en une ligne.

## Garde-fous

- Jamais de clé, cookie, jeton, identifiant de profil ou chemin de session dans git ou dans le chat.
- Le dépôt GitHub est public.
- Pas de nom de modèle d'IA dans les commits ou les fichiers.
