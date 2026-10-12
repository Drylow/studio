# Sources maintenues de TubeForge

Etat au 12 octobre 2026. Lire `../../README_REPRISE.md` pour le travail editorial actif et `../../CLAUDE.md` pour les regles generales. L'application installee est dans `../../work/TubeForge/` ; ce dossier contient les modifications a conserver lors des deploiements.

## Carte des modules

| Source | Role |
| --- | --- |
| `workspace.html`, `workspace.js`, `workspace.css` | Interface actuelle, pages chaine/projet, script colle, progression et outils avances |
| `workspace_api.py`, `workspace_management.py` | Donnees et operations du workspace, gestion des chaines/styles/projets |
| `workspace_voice.py` | Parcours de voix, fournisseurs et suivi des jobs |
| `workspace_writing.py`, `scriptwriting/` | Ecriture Survivor depuis un titre : CLI Proxy, Faceless OS et ancres reelles, revision et bible de continuite |
| `workspace_planning.py` | Preparation des plans/prompting du parcours general ; ne pas l'utiliser pour reecrire des prompts diriges par Codex |
| `workspace_generation.py` | Generation individuelle et lot, test des trois premieres images, suite, stop, routes de rendu |
| `workspace_characters.py` | References et variantes des personnages |
| `workspace_visuals.py`, `workspace_composition.py` | Contrats visuels, composition, proportions et protection contre doublons |
| `google_flow.py` | Transport Google Flow/useapi et comptes, distinct du chemin CLI Proxy |
| `studio_bridge.py` | Pont avec les services du depot |
| `workspace_seed.py` | Initialisation/migration des donnees ; ne pas reseeder un workspace existant pour une reprise |
| `vendor.patch`, `voice_ui.json`, `main.py`, `__init__.py`, `import_review.py`, `benchmark.py` | Adaptations de l'installation initiale et outils additionnels |
| `*_tests.py`, `workspace_ui_tests.cjs`, `requirements.lock` | Verification ciblee et dependances de l'installation |

Le script `../tubeforge_workspace.py` copie les modules maintenus dans `work/TubeForge/app/` et le frontend dans `app/web/`, puis applique les points d'integration. Il ne constitue pas une installation complete a lui seul.

## Commandes de maintenance

Depuis la racine du depot, PowerShell :

```powershell
& ./production/tubeforge.ps1 -Action Status
& ./production/tubeforge.ps1 -Action Start
# Seulement apres une modification necessitant deploiement :
& ./venv/Scripts/python.exe ./production/tubeforge_workspace.py --no-seed
```

Un restart, lorsqu'il est necessaire et autorise, consiste a arreter puis relancer avec le meme script. Ne pas le faire pour simplement changer de compte de chat. Le serveur est local sur `http://127.0.0.1:8766/`.

Pour les verifications de code, utiliser le Python de `work/TubeForge/.venv/Scripts/python.exe` et les tests concernes. Ne pas lancer une generation image/voix comme test gratuit suppose. Les tests de mocks et checks de lecture sont distincts des appels facturables.

## Donnees et restauration

- `work/TubeForge/data/` : projets, images, rendus, styles, chaines et archives. Conserver tout le dossier.
- `work/TubeForge/.env` : configuration privee de l'application ; ne pas afficher ni committer.
- `.env` a la racine : configuration privee du depot/CLI Proxy ; distincte de celle de TubeForge.
- `work/TubeForge/.venv/` : dependances locales reinstallables, pas les donnees de travail.
- `work/reprise/latest.json` : dernier snapshot prive verifie, cree par `production/reprise_snapshot.py`.

Pour le meme PC, utiliser l'installation existante. En cas de migration, extraire le snapshot dans un dossier NEUF et verifier son manifeste avant de restaurer un chemin existant. Les scripts d'installation refusent volontairement d'ecraser une installation ; ne pas contourner ce garde-fou. Le snapshot source contient aussi les fichiers qui n'etaient pas suivis par Git au moment de la sauvegarde.

## Consignes utiles

Modifier ici, puis deployer avec `--no-seed` ; une modification uniquement dans l'installation est fragile. Pour produire du contenu, les scripts/prompts editoriaux restent dans `chaines/` et les registres d'images dans `output/imagegen/`. Ne pas modifier le frontend pour fabriquer un episode.

La logique de references peut preparer/envoyer des fichiers, mais la coherence est validee par inspection visuelle de chaque image. Le pack CapCut existant emploie la duree reelle de la voix ; lire les modules de rendu/export avant toute duplication de cette logique.

Les deux premiers episodes Survivor sont aussi documentes dans `README_REPRISE.md` : plans manuels compiles/importes par `production/tubeforge_survivor_episode.py`, montage lance par l'API TubeForge, controle et clips CapCut via `production/tubeforge_survivor_export.py`. La livraison est dans `output/videos/survivor-first-episodes-2026-10-12/`. Les reviews de cette production sont des inspections deleguees a Codex, distinctes d'une validation humaine. Aucun appel supplementaire de generation ni publication n'est necessaire pour recuperer les fichiers termines.

Les integrations disponibles ne constituent pas une autorisation de changer de fournisseur. Les deux derniers kits Survivor emploient le CLI Proxy configure ; God of War utilisait Google Flow. Preserve ces choix par projet.

## References personnages par style

Dans Styles, ouvrir un style puis **References personnages**. Importer une ou plusieurs images avec nom, variante et description fixe ; choisir le personnage principal. Les uploads restent a verifier jusqu'a une validation explicite des images. La validation controle aussi que leurs fichiers/SHA256 sont toujours ceux importes. Les images de personnages sont distinctes des references generales du style.

Routes locales : `POST /api/workspace/management/styles/{sid}/characters` (multipart, images et fiche), `PUT /api/workspace/management/styles/{sid}/characters` (fiche, principal et validation). Les fichiers sont conserves, les variantes existantes ne sont pas ecrasees. Les nouveaux projets figent leur casting dans `style_cast_snapshot`; les plans n'envoient que les identites presentes, via le moteur `workspace_characters` existant.

Les deux styles Survivor ont leurs personnages principaux deja importes. Les regler/editer ici ne lance aucune generation. Import initial reproductible avec `../tubeforge_survivor_styles.py`, sans seed global ni changement des autres styles. Le raccourci se recree avec `../tubeforge_shortcut.ps1`.

## Titre vers script

L'etape Texte expose l'ecriture via le CLI Proxy pour les deux styles Survivor, en anglais. Deux calls sur le modele texte selectionne/fixe au projet : draft puis revision selon les cinq fichiers Faceless OS et les trois transcriptions reelles chargees depuis `STUDIO_ROOT`. Un troisieme call de redaction peut ajuster la longueur mesuree ; maximum trois, pas de retry de transport ni de hedge automatique. Un texte encore hors duree est conserve en brouillon avec un probleme signale, sans adoption automatique. Les prompts publics sont dans `scriptwriting/`; aucune cle ni nom de modele n'y est fige. Les documents de skills servent de methode, mais la fenetre de mots demandee et le format JSON/narration pure ont priorite sur leurs templates de longue video.

Le projet vide sans medias recoit le texte automatiquement si la revue ne signale pas de probleme. Un projet deja ecrit conserve son texte et recoit un brouillon. L'adoption refuse les medias existants et les empreintes de texte perimees. Voix/images ne suivent pas automatiquement. L'audit du modele reste distinct des validations humaines. Scripts, bibles, audits et requests sont sauves dans `script-generations/` du projet prive.

Routes `POST /api/workspace/projects/{pid}/script/generate` et `.../script/apply-draft`. Tests : `workspace_writing_tests.py`, deployes vers `tests/test_workspace_writing.py`. Le deploy copie aussi le dossier `scriptwriting/`. Le code d'ecriture n'autorise pas la preparation automatique des images de styles Codex, ni l'ecriture sur les cinq profils historiques.
