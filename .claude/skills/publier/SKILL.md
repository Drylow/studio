---
name: publier
description: Sur le PC de l'utilisateur (Windows), publie les vidéos de ses 6 chaînes YouTube (Last Safe Door, One Stick Left, Scene Analysis Guy, Samurai Chapters, Viking Chapters, Pirate Pages) depuis leurs profils Fury ou AdsPower. À lancer quand l'utilisateur tape /publier ou demande de publier, programmer ou automatiser ces chaînes.
---

# Publier sur les chaînes de l'utilisateur depuis Fury et AdsPower

Décision de l'utilisateur du 14 octobre 2026 : ses chaînes se publient depuis les profils de
navigateur où sont ses comptes, **Fury** et **AdsPower**, sur ce PC. Pas de Zernio ni d'API YouTube
pour ces 6 chaînes. Cage Dispatch, Pitch Dispatch (serveur) et Octave Histoire (Zernio) ne changent pas.

Parle-lui en français simple et court (CLAUDE.md §1). Il ne veut rien faire à la main : installe toi-même
ce qui manque, il clique seulement « Autoriser ». Les chaînes du collègue (Patch Survives, Alien Aftermath,
Deep Sea Survival, Oddly Fictional Lives…) ne te concernent pas.

## Les chaînes et leurs profils

`production/publish/channels.json` : le **nom du profil = le nom de la chaîne**.
- AdsPower : **Viking Chapters**, **Pirate Pages**.
- Fury : **Last Safe Door**, **One Stick Left**, **Scene Analysis Guy**, **Samurai Chapters**.

## Étape 1 : trouver comment piloter Fury et AdsPower (lecture seule)

- **AdsPower** a une API locale. L'adresse est affichée dans AdsPower, menu Paramètres → Local API,
  souvent `http://local.adspower.net:50325` ou `http://127.0.0.1:50325`. Routes connues, à vérifier sur
  la version installée :
  - `GET /status` ;
  - `GET /api/v1/user/list?page_size=100` liste les profils (nom, `user_id`) ;
  - `GET /api/v1/browser/start?user_id=…` ouvre le profil et rend `data.ws.puppeteer` ;
  - `GET /api/v1/browser/stop?user_id=…` le ferme.
  Si l'API demande une clé, l'utilisateur la met dans le `.env` de ce dossier (`ADSPOWER_API_KEY=`),
  jamais dans le chat. Explique-lui où la trouver dans AdsPower.
- **Fury** : application dans `C:/Users/ytbyt/AppData/Local/Fury/`, données dans
  `C:/Users/ytbyt/AppData/Roaming/Fury/`. Une autre session a déjà listé ses profils par le canal
  local de l'application (named pipe `fury-df3984eb`, méthodes `profiles.list`, `proxies.list`) avec
  `C:/Users/ytbyt/Documents/Codex/2026-10-04/j/work/create-fury-test-profiles.ps1`. Son MCP local
  (`.../work/fury-mcp/tools/mcp/fury-mcp.py`) propose `status`, `profiles`, `start_profile`,
  `stop_profile`. **Lis ces fichiers avant de t'en servir.** Ne relance aucun script de création de
  profils, ne lis ni ne copie jamais `fury.db`, `profiles/`, `api-token`, cookies ou sessions.
- Écris la correspondance chaîne → application → identifiant du profil dans
  `work/publish/profiles.json` (ignoré par git), puis montre-la à l'utilisateur.

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
la fois.** Le premier envoi sur chaque chaîne se fait avec l'utilisateur qui regarde, en non
répertorié ou en programmé, comme il le demande.

1. Récupère le MP4 (lien Gofile, ou le fichier déjà sur ce PC), puis vérifie son SHA-256 avec celui
   de la fiche. Différent : stop.
2. Ouvre le profil, connecte Playwright, va dans YouTube Studio. Vérifie le nom de la chaîne.
3. Regarde la liste des contenus : si une vidéo avec ce titre existe déjà, ne renvoie rien.
   Note-le et demande à l'utilisateur.
4. Créer → Importer des vidéos. Ensuite :
   - fichier ;
   - titre, description et miniature de la fiche ;
   - « Non, cette vidéo n'est pas conçue pour les enfants » ;
   - sous-titres SRT s'il y en a ;
   - visibilité ou date de programmation de la fiche (heure de Bruxelles).
5. Attends la fin de l'envoi. Relève le lien de la vidéo et l'état des droits d'auteur (vérification
   YouTube). Ferme le profil.
6. Ajoute une ligne à `production/publish/log.jsonl` : chaîne, titre, SHA-256, `video_id`, visibilité,
   date, état des droits. Commit en anglais, `git pull --rebase`, push sur `main`.
7. Un envoi coupé au milieu : **ne recommence pas à l'aveugle**. Regarde d'abord dans Studio si la
   vidéo existe déjà (brouillon compris).

Ne touche jamais une vidéo déjà en ligne (titre, miniature, suppression) sans demande de l'utilisateur.
Après chaque envoi, donne-lui le lien et le titre en une ligne.

## Garde-fous

- Jamais de clé, cookie, jeton, identifiant de profil ou chemin de session dans git ou dans le chat.
- Le dépôt GitHub est public.
- Pas de nom de modèle d'IA dans les commits ou les fichiers.
