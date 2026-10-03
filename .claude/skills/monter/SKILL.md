---
name: monter
description: Sur le PC de l'utilisateur (Windows), monte les vidéos d'actu sport préparées par le Claude du cloud (news/**/ready) — téléchargement des extraits YouTube, montage, Gofile, suppression des clips, renvoi du lien et des planches dans git. À lancer quand l'utilisateur tape /monter ou dit « monte les vidéos ».
---

# Monter les vidéos d'actu sur le PC

Deux Claude travaillent ensemble par GitHub (`drylow/studio`, branche `main`) :
- **le Claude du cloud** trouve l'actu, écrit le plan, fait la voix off et la miniature, relit, puis marque la
  vidéo prête (`news/<chaîne>/<vidéo>/ready`) et pousse. YouTube bloque les téléchargements depuis le cloud.
- **toi, le Claude du PC**, tu fais seulement le montage (YouTube laisse télécharger depuis une connexion maison).

Parle à l'utilisateur en français simple et court (voir CLAUDE.md §1). Il ne veut rien faire à la main :
installe toi-même ce qui manque, il n'a qu'à cliquer « Autoriser ».

## Étapes

1. **Projet à jour** : `git pull --ff-only` (dans ce dossier, clone de `https://github.com/drylow/studio`).
   Pas de clone ? `git clone https://github.com/drylow/studio` puis travaille dedans.
2. **Python 3.10+** : `py -3 --version` ou `python --version`. Absent → `winget install -e --id Python.Python.3.12`
   (ou l'installateur de python.org), puis rouvre le terminal.
3. **Modules** : `python -m pip install -U "yt-dlp[default]" imageio-ffmpeg Pillow python-dotenv requests`
   (ffmpeg vient d'`imageio-ffmpeg` : rien d'autre à installer).
4. **Moteur JavaScript pour YouTube (deno)**, une fois, dans `tools\deno` (ignoré par git) :
   ```
   mkdir tools\deno
   curl -sSL -o tools\deno\deno.zip https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip
   tar -xf tools\deno\deno.zip -C tools\deno && del tools\deno\deno.zip
   ```
   (`services/newsvid.py` → `yt_js_args` le trouve tout seul.)
5. **Montage** : `set PYTHONIOENCODING=utf-8` puis `python production\news.py pc` — en tâche de fond suivie,
   ça dure 30 min à 1 h par vidéo. Il monte chaque dossier `news/**` qui a `plan.json` + `narration/` + `ready`
   et pas encore `result.json`, envoie sur Gofile, **supprime tous les clips et fichiers de montage** (demande de
   l'utilisateur : son disque), puis pousse `result.json`, `build.log` et `check/sheet_*.jpg`.
6. **Compte rendu** : donne le lien Gofile (« >>> LIEN DE LA VIDEO ») et dis que le Claude du cloud va vérifier
   les planches puis envoyer le paquet Discord. Un échec : lis `build.log`, corrige si c'est un souci du PC
   (module, réseau, deno) et relance ; si c'est le plan, dis-le simplement (le Claude du cloud le corrigera).

## À ne pas faire

- Ne modifie pas les plans, titres, voix off ou miniatures : c'est le travail du Claude du cloud, déjà relu.
- N'envoie rien sur Discord d'ici (le paquet part après vérification des planches, depuis le cloud).
- Ne garde aucun clip téléchargé après le montage. Ne mets jamais de clé ou de webhook dans git.
- N'installe pas de tâche planifiée ni de programme qui tourne en arrière-plan sans que l'utilisateur
  l'ait demandé clairement.
