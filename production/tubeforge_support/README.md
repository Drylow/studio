# Sources maintenues de TubeForge

Etat au 12 octobre 2026. Lire `../../README_REPRISE.md` pour le travail editorial actif et `../../CLAUDE.md` pour les regles generales. L'application installee est dans `../../work/TubeForge/` ; ce dossier contient les modifications a conserver lors des deploiements.

Pour un nouveau PC ou le collegue qui produit des aliens, commencer par [README_SURVIVOR_TUBEFORGE.md](../../README_SURVIVOR_TUBEFORGE.md). L'installation complete depuis Git est maintenant `../tubeforge_setup.py`, avec la base dans `../tubeforge_base/` et les deux styles modifiables dans `../tubeforge_presets/`. L'ancien installeur utilisant une archive privee n'est pas requis. Les patches d'archive historiques ne sont pas la voie d'installation publique.

## Carte des modules

| Source | Role |
| --- | --- |
| `workspace.html`, `workspace.js`, `workspace.css` | Interface actuelle, pages chaine/projet, script colle, progression et outils avances |
| `workspace_api.py`, `workspace_management.py` | Donnees et operations du workspace, gestion des chaines/styles/projets |
| `workspace_voice.py` | Parcours de voix, fournisseurs et suivi des jobs |
| `workspace_writing.py`, `scriptwriting/` | Ecriture Survivor depuis un titre : CLI Proxy, Faceless OS et exemples identifies par source, revision et bible de continuite |
| `workspace_planning.py` | Preparation des plans/prompting du parcours general ; ne pas l'utiliser pour reecrire des prompts diriges par Codex |
| `workspace_generation.py` | Generation individuelle et lot, test des trois premieres images, suite, stop, routes de rendu |
| `workspace_characters.py` | References et variantes des personnages |
| `workspace_locations.py` | Deux modes de decor, registre des lieux et vues nommees, plan de camera global et audit de variete |
| `workspace_visuals.py`, `workspace_composition.py` | Contrats visuels, composition, proportions et protection contre doublons |
| `google_flow.py` | Transport Google Flow/useapi et comptes, distinct du chemin CLI Proxy |
| `studio_bridge.py` | Pont avec les services du depot |
| `slideshow_render.py` | Rendu technique d'images fixes inspectees, fondus centres sur les coupes et horloge voix conservee ; accepte un job JSON explicite, sans generation ni redaction |
| `workspace_seed.py` | Initialisation/migration des donnees ; ne pas reseeder un workspace existant pour une reprise |
| `main.py`, `__init__.py`, `import_review.py`, `benchmark.py` | Outils additionnels et point d'entree, egalement conserves dans la base distribuable |
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

## Background modes — 13 October 2026

### Navigation performance

Hash navigation reuses short-lived in-memory workspace, management and project reads, with deduplicated requests and stale-while-revalidate behavior. Independent page dependencies load concurrently. Successful writes and logout clear the cache; manual refresh and job polling always fetch current data. No credentials or project payloads are persisted in browser storage by this cache.

Project screen reads use `GET /api/workspace/projects/{id}?view=ui`, excluding archival histories and planning receipts from the response. Default API reads retain full history. Stored metadata, prompts, ordered references and review evidence are preserved; current status is still calculated before building either response. Navigation cache tests: `node production/tubeforge_support/workspace_navigation_tests.cjs`.

Images and review screens render 24 shots per page to avoid constructing hundreds of image cards, reference lists and prompt editors at once. Pagination is local and preserves the entire project for generation/review checks. Off-page prompts remain unchanged when saving; page changes refuse unsaved edits.

Image execution reuses reference upload encoding in a bounded 64 MiB memory cache, keyed by resolved file path and verified source SHA256. Every call still reads and checks the source file before and after obtaining its payload. Changed bytes cause a fresh encoding; prompts, reference order, model choice and review evidence are untouched. This avoids repeatedly encoding identical character/drawing/location references in large shot batches.

**Channels & presets → Preset & settings → Background mode** offers two independent scenery choices:

- **Free backgrounds** (`free`, default): every image can use a different setting.
  No location registry or camera continuity is imposed. Character identity references
  and explicit costume variants still apply, using the same character engine.
- **Consistent locations** (`consistent`, opt-in): the automated fictional planning
  path first plans concrete spaces, fixed world-space landmarks and named viewpoints
  across the WHOLE narration, then writes prompt batches against that shared plan.
  Recurring spaces used in six or more shots need three physical viewpoints;
  changing a crop or shot size alone does not qualify. More than two consecutive
  shots from the same viewpoint is rejected before publishing a partial plan.
  Every shot also contains a new narrated action, object, reaction or consequence.

The choice is saved in the style, copied into a new project's visual settings and
style snapshot, and preserved when the shared style changes later. Existing
projects/media are not migrated or regenerated. New blank styles default to free;
duplicating a style preserves its selected mode. No supplier or model is changed.

`workspace_location_plan` stores the planned geometry, viewpoints and visual beats;
`workspace_camera_audit` records viewpoint distribution, exposed in the Images tab.
Planning text is not proof of visual consistency: inspect generated images.

For reference-backed consistency, import inspected master/view files using the
existing project reference upload, then save a `workspace_location_registry` via
`PUT /api/workspace/projects/{pid}/locations` with `previous_hash` equal to the
project's `location_registry_hash`. Each location has `description`, `layout`,
`anchors`, a verified `master`, and named `views` with `description`, physical
`angle`, and an optional verified `reference`. Reference records specify owner,
path, SHA256, location_id and role `location-master` or `location-view`; a view
reference also specifies `location_view`. This API performs no image generation.
No reference is marked visually approved by planning. The member must actually
inspect an image before recording `review_state=verified`.

When registered, authoring binds the same master plus the chosen approved view
before execution. The generator sends the saved reference order without swapping
views, rewriting prompts or truncating files. Changed geometry, camera metadata
or file hashes invalidate review/generation evidence. Without registered images,
the camera plan is a text layout guide, not a verified image reference kit.
Codex-directed/historical styles still keep manual scene authoring; this update
does not start their automatic writer or modify a completed episode.

## Channel / preset configuration

The primary management entry is **Channels & presets**. Creating a channel creates its drawing preset at the same time, optionally copying a template's drawings and character references. **Preset & settings** groups the channel identity, voice, drawing instructions, background mode, visual guide and cast. **Save channel / preset** saves these settings together. Editing a channel whose legacy style is shared first makes a private preset copy; other channels and existing project snapshots remain unchanged. Legacy style URLs and per-video advanced overrides remain compatible.

Paired management routes: `POST /api/workspace/management/presets` and `PUT /api/workspace/management/presets/{cid}`. Input validation precedes writes; channel write failures roll back the metadata and archive any orphaned new preset. Character approval is explicit and distinct from saving its description.

Choose **Use as drawing guide** on an inspected visual reference to freeze its file/hash in new projects' `drawing_reference_snapshot`. Planning uses that single guide for drawing language, alongside independent character and location references. Before generation, `_validate_drawing_reference` requires the exact reviewed guide among the shot's saved ordered attachments. Execution never silently appends or replaces attachments. Older projects without this optional snapshot retain their existing contract. Drawing consistency still requires actual image inspection and is independent of free/consistent background mode.

## References personnages par style

Dans **Channels & presets**, ouvrir **Preset & settings** puis **Character references**. Importer une ou plusieurs images avec nom, variante et description fixe ; choisir le personnage principal. Les uploads restent a verifier jusqu'a une validation explicite des images. La validation controle aussi que leurs fichiers/SHA256 sont toujours ceux importes. Les images de personnages sont distinctes des references generales du style.

Routes locales : `POST /api/workspace/management/styles/{sid}/characters` (multipart, images et fiche), `PUT /api/workspace/management/styles/{sid}/characters` (fiche, principal et validation). Les fichiers sont conserves, les variantes existantes ne sont pas ecrasees. Les nouveaux projets figent leur casting dans `style_cast_snapshot`; les plans n'envoient que les identites presentes, via le moteur `workspace_characters` existant.

Les deux styles Survivor ont leurs personnages principaux deja importes. Les regler/editer ici ne lance aucune generation. Import initial reproductible avec `../tubeforge_survivor_styles.py`, sans seed global ni changement des autres styles. Le raccourci se recree avec `../tubeforge_shortcut.ps1`.

## Titre vers script

L'etape Texte expose l'ecriture via le CLI Proxy pour les deux styles Survivor, en anglais. Deux calls sur le modele texte selectionne/fixe au projet : draft puis revision selon les cinq fichiers Faceless OS et les exemples d'ecriture. Les transcriptions locales sont utilisees si presentes ; sinon les trois exemples de `scriptwriting/house-voice-examples.json` sont nos narrations originales, explicitement identifiees ainsi et non comme transcriptions concurrentes. Un troisieme call de redaction peut ajuster la longueur mesuree ; maximum trois, pas de retry de transport ni de hedge automatique. Un texte encore hors duree est conserve en brouillon avec un probleme signale, sans adoption automatique. Les prompts publics sont dans `scriptwriting/`; aucune cle ni nom de modele n'y est fige. Les documents de skills servent de methode, mais la fenetre de mots demandee et le format JSON/narration pure ont priorite sur leurs templates de longue video.

Le projet vide sans medias recoit le texte automatiquement si la revue ne signale pas de probleme. Un projet deja ecrit conserve son texte et recoit un brouillon. L'adoption refuse les medias existants et les empreintes de texte perimees. Voix/images ne suivent pas automatiquement. L'audit du modele reste distinct des validations humaines. Scripts, bibles, audits et requests sont sauves dans `script-generations/` du projet prive.

Routes `POST /api/workspace/projects/{pid}/script/generate` et `.../script/apply-draft`. Tests : `workspace_writing_tests.py`, deployes vers `tests/test_workspace_writing.py`. Le deploy copie aussi le dossier `scriptwriting/`. Le code d'ecriture n'autorise pas la preparation automatique des images de styles Codex, ni l'ecriture sur les cinq profils historiques.
