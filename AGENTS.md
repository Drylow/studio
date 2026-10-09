# Reprise par Codex — 9 octobre 2026 au soir (après Claude)

L'utilisateur passe de Claude à Codex et veut que **tout continue exactement pareil**. Lire dans
l'ordre : `CLAUDE.md` (règles, ton avec l'utilisateur : français familier, court, heures de
Belgique, jamais UTC), le haut de `production/REPRISE.md` (état en ligne), puis
`tiktok_engine/README.md` et `tiktok_engine/ROUTINE.md` (TikTok).

**Ce qui tourne tout seul, sans agent :**
- **Cage Dispatch et Pitch Dispatch** : pilote `studio/autonews.py` sur le serveur o2switch
  (worker lancé par cron). Il publie au plus 2 vidéos par jour et par chaîne, seulement les
  sujets notés 7/10 ou plus. Rien à lancer. Pour couper : `NEWS_AUTO_DRY=1` dans le `.env` du
  serveur.
- **TikTok @octave.histoire** : 14 vidéos programmées sur Zernio du 9 au 15 oct., à 7 h et 19 h
  (Bruxelles). Chaque vidéo programmée a son `tiktok_engine/videos/<nom>/zernio.json`.

**Ce qu'il reste à faire :**
- **Chaque jour, `tiktok_engine/ROUTINE.md`** : 2 nouvelles vidéos dans le premier jour libre.
  - Une routine Claude (vers 8 h 47) le fait aussi, tant que l'utilisateur a de l'usage Claude.
  - Avant de prendre un créneau : `git pull`, lire les `zernio.json`, et `zernio.py posts`
    (l'état réel chez Zernio). Jamais deux vidéos sur un même créneau.
- **Avant le 14 oct. au soir, rappeler à l'utilisateur de reconnecter Cage et Pitch.** Google est
  en mode *Testing* et coupe l'accès au bout de 7 jours. Sur le site : Chaînes → la chaîne →
  Connecter YouTube → Autre méthode : API Google.

**Clés.** Le dépôt est **PUBLIC** : jamais une clé dans git ni dans un message.
- Dans l'environnement Codex, seulement 3 **variables d'environnement** : `CPANEL_URL`,
  `CPANEL_USER`, `CPANEL_PASSWORD`. Pas des « secrets » : Codex retire les secrets avant que
  l'agent travaille.
- Tout le reste est dans le `.env` du serveur (`~/drylow_studio/.env`, 45 variables :
  `ALGROW_API_KEY`, `ZERNIO_API_KEY`, `AI_API_KEY`, `DISCORD_WEBHOOK_*`, `GOOGLE_CLIENT_*`…).
  - `python production/server_env.py NOM [NOM…]` copie les variables voulues dans le `.env`
    local (ignoré par git), sans les afficher.
  - `bash tiktok_engine/setup.sh` le fait pour Algrow et Zernio. Il installe aussi la venv,
    playwright et Chromium.
- L'environnement doit avoir **accès à Internet** : zernio.com, api.algrow.online,
  edgerunners.fr, gofile.io et les sources pour vérifier les faits.

**Serveur :** `python production/cpanel.py` (`pip install websocket-client`).
- `sh '<commande>'` lance une commande sur le serveur.
- `deploy <étiquette>` met `main` en ligne : sauvegarde de la base, avance rapide, relance du
  worker et du site.
- Toujours sauvegarder la base avant un changement sur le serveur.

**Git :** commit en anglais qui dit le « pourquoi ». `git pull --rebase origin main` puis push
sur `main` après chaque changement. Aucun nom de modèle d'IA dans les commits ou les fichiers.
`production/session_start.sh` ne sert que dans une session Claude.

---

# Production 2D historique dirigee par Codex

Lire CLAUDE.md pour les regles generales du depot. Ne pas annuler les modifications
existantes ni changer le frontend pour produire le contenu.

Pour Edo Daily, Aztec Daily, Babylon Daily, Imperial China Daily et Ottoman Daily :
- L'utilisateur demande que Codex ecrive lui-meme les scripts, decoupages et prompts.
  Ne pas deleguer le prompting a la generation automatique de la pipeline.
- Decision finale du 7 octobre : VIDEOS = decors BD sobres (option 1 du
  comparatif), lignes nettes, aplats mats, textures reduites et ombres simples.
  Garder une architecture detaillee et lisible, sans decor excessivement simplifie.
  PERSONNAGES = adultes a tete ronde blanche, petits yeux noirs, bouche neutre,
  mains blanches en moufles et corps couverts, comme les references du 6 octobre.
- Exception explicite du 7 octobre : pour les MINIATURES seulement, l'utilisateur
  veut des visages humains cartoon expressifs comme la miniature NO JOBS de Rome
  Unscrolled. Cette direction ne change PAS les personnages blancs des videos.
  Conserver les premieres propositions blanches sans les ecraser.
- Les humains testes dans les intros sont abandonnes pour les VIDEOS.
  Conserver ces essais comme archives, pas comme references de personnages.
- Le decor choisi est output/imagegen/comparatif-decors-2026-10-07/01-bd-sobre.png.
  Son personnage humain n'est PAS approuve pour les videos. Les autres variantes
  restent des essais. Adapter et verifier les maitres de chaque lieu a la BD sobre.
- Les cinq miniatures HUMAINES a regarder sont dans
  output/imagegen/miniatures-01-journee-v2-2026-10-07/A-REGARDER/.
  Direction humaine conservee ; ne pas en deduire la validation de chaque image.
- Miniatures des videos 01 : texte relie a l'angle du titre, plusieurs activites
  de la journee dans une seule scene, expressions adaptees. Ne pas recycler
  cinq vendeurs portant un produit ni affirmer NO JOBS sans preuve.
  Relire l'accroche avec le script final avant publication.
- Lire production/COHERENCE_2D_CODEX.txt avant toute production.
- Reutiliser un decor maitre verifie pour chaque lieu et les memes references de
  personnages ; une description textuelle seule ne suffit pas.
- Chaque plan doit avoir un extrait de narration, un lieu, des personnages nommes,
  un prompt ecrit par Codex et une liste ordonnee des images effectivement envoyees.
- Utiliser le CLI Proxy configure dans .env. Ne pas substituer un autre fournisseur.
- Le code ne fait que l'execution technique ; aucun script automatique ne doit
  reecrire les prompts, choisir une autre reference ou regenerer un lieu sans accord.
- Codex regarde chaque image, compare le decor aux references et corrige les ecarts
  avant montage. Ne jamais declarer une coherence parfaite uniquement sur la base
  des prompts ou des references envoyees.
- Les nouvelles vues d'un lieu et les changements de lumiere sont des variantes
  explicites, creees depuis le decor maitre, verifiees et conservees.

Le kit de references initial et le test visuel sont dans
output/imagegen/coherence-codex-2026-10-07/.

Correction utilisateur du 8 octobre : la coherence ne doit PAS produire un film
fait de variations des memes tableaux. L'episode Edo initial est rejete.
Chaque plan apporte une information nouvelle liee a la narration : action,
objet, interlocuteur, reaction ou consequence. Un zoom ou nouveau fichier seul
ne compte pas. Ajouter les lieux et personnages necessaires aux evenements.
Conserver l'identite d'une piece dans SA scene, pas la recopier partout.
Etudier reference/strangely-ironic-guy/ et ses videos pour la mise en scene :
POV, gestes, echanges, groupes, gros plans et espaces occupes.
Reecrire script et decoupage avant une nouvelle production integrale.

Retour utilisateur du 8 octobre sur les horizons : garder la mise en scene et
les decors detailles, mais supprimer les grandes tours et architectures fantaisie
ajoutees au loin. Arriere-plan lointain sobre, a echelle credible et adapte au lieu.
Un monument n'apparait que s'il est documente et necessaire a la scene, pas comme
decoration generique. Corriger le maitre puis les plans concernes sans changer
les personnages, gestes, objets proches ou geometrie de la scene.
