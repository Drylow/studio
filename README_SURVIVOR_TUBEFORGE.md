# TubeForge — transmission zombies et aliens

Ce dossier contient les sources complètes de TubeForge et notre méthode de production Survivor. Point d'entrée pour un nouveau PC ou un nouveau chat, état du 12 octobre 2026. Commencer par les **aliens** pour le travail du collègue.

Instance partagée VPS : lire [README_TUBEFORGE_VPS.md](README_TUBEFORGE_VPS.md). `production/tubeforge_install.py` est également un alias de l'installation complète depuis Git ; il ne demande plus d'archive privée.

## Installer depuis un clone

Windows, Python 3.12 ou plus récent et Git. Depuis la racine du clone :

```powershell
py -m venv venv
& ./venv/Scripts/python.exe -m pip install -r production/tubeforge_base/requirements.txt
Copy-Item production/tubeforge_base/studio.env.example .env
notepad .env
# Remplir les clés, URL et IDs privés, puis :
& ./venv/Scripts/python.exe production/tubeforge_setup.py
& ./production/tubeforge.ps1 -Action Start
```

Ouvrir http://127.0.0.1:8766/. Ne pas remplacer un `.env` existant avec l'exemple. Le setup refuse un dossier `work/TubeForge` déjà présent : une installation existante se met à jour par le déploiement ci-dessous. Aucun ZIP privé de l'application d'origine n'est nécessaire.

Le `.env` racine fournit `AI_BASE_URL`, `AI_API_KEY`, `AI_TEXT_MODEL`, `AI_IMAGE_MODEL` et `ALGROW_API_KEY`. Les modèles sont des IDs choisis dans le catalogue de votre CLI Proxy, pas des valeurs figées dans Git. Le setup crée le `.env` distinct de TubeForge et ses deux environnements Python. Le collègue configure ses propres accès ; les secrets, cookies Google, comptes connectés, sauvegardes privées et données locales ne sont pas publiés.

La voix des épisodes est `rU18Fk3uSDhmg5Xh41o4`, Algrow, vitesse 1. Pour une autre voix : `production/tubeforge_setup.py --voice-id VOTRE_ID`. Vérifier que votre fournisseur donne accès à cet ID. AI33 et Google Flow/useapi restent des intégrations disponibles, sélectionnées explicitement. Les nouveaux presets Survivor restent sur **CLI Proxy pour les images et Algrow pour la voix**.

Le setup neuf choisit explicitement le rendu natif FFmpeg pour fonctionner sans environnement GPU particulier. FFmpeg est fourni par `imageio-ffmpeg`, la mesure de durée peut utiliser PyAV sans FFprobe séparé. Les deux productions originales ont utilisé OVNI sur le PC équipé NVIDIA. Pour ce chemin optionnel : `production/ovni.ps1 -Action Install`, puis sélectionner `RENDER_BACKEND=ovni` dans le `.env` de TubeForge. OVNI ne bascule pas silencieusement vers un autre moteur. Consulter `production/OVNI.md` ; ses benchmarks historiques nécessitent leurs fichiers privés, contrairement à l'installation/compilation.

## Sources et styles à modifier

| Chemin | Contenu |
| --- | --- |
| `production/tubeforge_base/` | Base complète de l'application, modules d'origine intégrés, frontend ancien, fonts/sons et dépendances |
| `production/tubeforge_support/` | Sources maintenues de nos ajouts : frontend actuel, étapes, voix, Google Flow, écriture, références et tests |
| `production/tubeforge_setup.py` | Installation sans archive, configuration privée, import des deux presets et de leur casting |
| `production/tubeforge_workspace.py` | Déploiement des modifications maintenues dans l'installation |
| `production/tubeforge_presets/survivor-alien-aftermath.json` | **Style aliens modifiable**, descriptions, références de Reed/Mara/Surveyor/Worker, catalogue des décors |
| `production/tubeforge_presets/survivor-patch.json` | **Style zombies modifiable**, Patch/Mara/Cart Infected/Delivery Infected et décors |
| `skills/facelessos/` | Méthode de script-writing et audits |
| `work/TubeForge/data/` | Données privées d'une installation : styles, chaînes, projets et médias ; jamais écrasées lors d'une mise à jour |

Les presets sont de vrais fichiers source, pas uniquement des images de démonstration. Ils sont importés dans **Styles → Références personnages** et les deux chaînes locales sont créées à l'installation. Vous pouvez ensuite modifier les styles dans TubeForge : le prochain déploiement ne remet pas vos changements à zéro. Les projets déjà créés conservent leurs snapshots de modèle et de casting ; changer le style sert aux prochains projets, sauf modification explicite d'un projet existant.

Pour changer les defaults distribués à d'autres PC, éditer les JSON de `production/tubeforge_presets/`. Pour ajouter/remplacer une image, mettre à jour son chemin et SHA256 **après l'avoir regardée**. Les références livrées portent une inspection Codex, distincte d'une approbation humaine. Un upload nouveau reste à vérifier. Ne pas transférer un statut de validation à une autre image.

Pour modifier le code, éditer les modules maintenus dans `production/tubeforge_support`, pas leur copie sous `work`. La base contient les modules nécessaires hors de cet overlay ; toute adaptation de ces modules se conserve dans `production/tubeforge_base`.

```powershell
& ./production/tubeforge.ps1 -Action Stop
& ./venv/Scripts/python.exe production/tubeforge_workspace.py --no-seed
& ./production/tubeforge.ps1 -Action Start
```

Ne pas utiliser le seed global historique pour mettre à jour ces chaînes. Sauvegarder `work/TubeForge/data` et ses `.env` privés avant une migration. Ne pas écraser les modifications existantes du dépôt. Lire `CLAUDE.md`, puis `README_REPRISE.md` pour l'historique ; les règles des cinq chaînes historiques ne remplacent pas le style Survivor décrit ici.

## Produire une nouvelle vidéo

1. Choisir Alien Aftermath ou Patch Survives. Créer une vidéo en anglais, sélectionner les modèles disponibles sur votre proxy et votre voix.
2. Coller directement un script, ou lancer l'écriture depuis le titre. Celle-ci appelle le CLI Proxy avec cinq documents Faceless OS, écrit une bible de continuité et fait une revue ; elle peut faire un troisième appel pour corriger la longueur. Aucun appel voix/image n'est lancé par l'écriture. Un texte existant est préservé en brouillon. Lire le résultat ; l'audit d'un modèle n'est pas une validation humaine.
3. Générer la voix. La durée estimée du texte est remplacée par la durée réelle ; découper avec les timings de **cette** voix. Les épisodes initiaux font environ 11–12 minutes avec 2 080 mots. Pour viser 15–16 minutes, calibrer sur la voix choisie et son débit réel.
4. Préparer le storyboard : chaque plan contient un extrait exact de narration, un lieu, des personnages nommés, une action/information nouvelle, son prompt et la liste ordonnée des références réellement envoyées. Pour les styles dirigés Codex, l'IA qui travaille dans le dossier écrit ce découpage ; ne pas contourner les blocages en laissant la pipeline réécrire les prompts.
5. Établir et regarder un décor maître par lieu, puis ses variantes explicites de nuit/dégâts. Lier chaque personnage récurrent à ses images d'identité ; une description seule ne suffit pas. Envoyer uniquement le casting présent dans le plan. Ne pas transformer une référence en personnage supplémentaire.
6. Dans Images, tester les trois premières avant la suite. Vérifier les images elles-mêmes : proportions, marques, accessoires, géométrie, interaction et cadrage 16:9. Lancer le reste après ce contrôle ; corriger individuellement les plans défectueux avec le même contrat.
7. Vérifier toutes les images, lancer Export et regarder le montage avec la voix. Le rendu suit les durées des plans et de la voix. Les coupes franches de notre premier pack ne prétendent pas être un montage avec transitions élaborées. La publication YouTube reste une action distincte.

Le dossier public `scriptwriting/house-voice-examples.json` contient **nos propres narrations originales**, utilisables dès le clone. Si des transcriptions concurrentes existent localement sous `work/survivor-launch-2026-10-12/reference-transcripts`, l'écriture peut utiliser ces références identifiées comme telles. Les transcriptions intégrales des concurrents ne sont pas copiées dans Git, et nos exemples ne sont pas présentés comme leurs transcriptions.

## Contrat visuel commun

Personnages adultes avec tête blanche parfaitement ronde, petits yeux noirs, bouche simple, mains blanches en moufles, pieds blancs ovales et corps/bras/jambes en fins traits noirs. Pas de corps humanoïde rempli, cheveux, nez, oreilles ou grandes expressions réalistes. Décors simples, mats, peu profonds, lisibles ; chaque action doit pourtant apporter quelque chose à la narration. Tous les plans sont en paysage 16:9. Chaque identité apparaît une seule fois dans un plan.

**Patch** : pansement orange au-dessus de son œil anatomique droit, à gauche pour le spectateur de face. Sac scolaire orange **posé au sol**, avec base en contact et petite ombre. **Reed** : petite écharpe bleu-gris, pas de pansement, sac scolaire gris au sol. **Mara** : bande violette à l'avant-bras droit, sac turquoise. Pour déplacer un sac, la main saisit visiblement la poignée supérieure ; pas de sac suspendu à rien, de bretelles sur un corps filaire ni de duplication.

Les **zombies** ont tête, deux mains et deux pieds verts `#A8BE87`. Les humains vivants restent blancs. Les **aliens** ont tête et mains menthe, grands yeux ovales noirs, corps gris couvert et bottes foncées. Surveyor porte une bande bleue sur l'épaule droite et un scanner ; Worker n'a ni bande ni scanner. Ne pas transférer les signes distinctifs d'un personnage à l'autre.

La cohérence concerne aussi les portes, les fenêtres, les objets et leur état : une voiture démontée, une vitre cassée ou une réserve consommée ne se rétablit pas sans événement explicite. Une nouvelle vue n'est pas une autorisation de redessiner le lieu au hasard. Lire les maîtres et les registres avant les prompts.

## Exemples complets déjà produits

**Aliens — référence prioritaire :**

- `chaines/alien-aftermath-projet/episode-01-gas-station/` : script original, découpage de 108 plans, notes et audit Faceless OS.
- `output/imagegen/survivor-full-production-2026-10-12/alien-storyboard.json` : storyboard compilé, prompts et références.
- `output/imagegen/survivor-full-production-2026-10-12/scenes/` : images ; choisir les fichiers **sélectionnés dans `scene-reviews.json`**, pas une ancienne variante rejetée.
- `output/videos/survivor-first-episodes-2026-10-12/02-Alien-Aftermath/` : métadonnées, thumbnail, timeline et notes du rendu original, 11:27 environ.

**Zombies :** mêmes dossiers avec `chaines/survivor-projet/episode-01-supermarket/`, `patch-storyboard.json` et `01-Patch-Survives/`. Durée du premier rendu : 11:43 environ.

**Registres communs :** `output/imagegen/survivor-full-production-2026-10-12/reference-index.json`, `asset-registry.json`, `scene-reviews.json`, `generation-provenance.json`, `continuity-corrections.json`. Ils contiennent les sources exactes, états, corrections et inspections. Les maîtres Patch initiaux sont aussi dans `output/imagegen/patch-supermarket-pilot-2026-10-12/masters/`.

**Channel kits :** `chaines/survivor-projet/channel-kit.txt`, `chaines/alien-aftermath-projet/channel-kit.txt` et `output/channel-kits/survivor-launch-2026-10-12/`. Noms/handles suggérés ne prouvent pas qu'une chaîne YouTube a été créée ou qu'un handle est disponible.

Les grosses vidéos finales, les voix originales, les clips et ZIP CapCut restent sur le PC de production ; ils ne sont pas dans Git. Les scripts, sources, images sélectionnées, références et informations de durée sont dans le dépôt. Les outils de reproduction/export des deux épisodes sont `production/tubeforge_survivor_episode.py` et `production/tubeforge_survivor_export.py` ; ce sont des recettes de ces productions avec leur mapping de projets privés, à adapter aux IDs locaux et à une voix régénérée. Ne pas réutiliser leurs timestamps si la voix change.

## Vérifier et poursuivre

```powershell
Push-Location work/TubeForge
& ./.venv/Scripts/python.exe -m pytest -q tests ../../production/test_tubeforge_share.py
Pop-Location
```

Les tests utilisent des fixtures et mocks, sans appeler les APIs payantes. Pour un nouveau chat :

> Lis README_SURVIVOR_TUBEFORGE.md puis production/tubeforge_support/README.md. Travaille sur une nouvelle vidéo Alien Aftermath. Préserve les données existantes. Utilise les sources maintenues et les styles JSON publics, les références d'identité et un maître vérifié par lieu. Écris le script/découpage en appliquant Faceless OS. Inspecte trois images avant la suite et toutes les images avant le montage. Les clés/modèles sont dans les .env privés, jamais dans Git. Ne publie pas automatiquement sur YouTube.

## Hosted team workspace

The English UI is integrated at https://tools.kanye.studio/2d and uses the existing
portal login. Each member has My videos; Team videos, channels and styles are shared.
There is no separate TubeForge account system or permission hierarchy. See
[hosting and updates](README_TUBEFORGE_VPS.md). Production speed is adjustable
in Settings and CLI image batches respect the configured parallelism.
