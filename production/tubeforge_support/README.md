# Sources maintenues de TubeForge

Etat au 12 octobre 2026. Lire `../../README_REPRISE.md` pour le travail editorial actif et `../../CLAUDE.md` pour les regles generales. L'application installee est dans `../../work/TubeForge/` ; ce dossier contient les modifications a conserver lors des deploiements.

## Carte des modules

| Source | Role |
| --- | --- |
| `workspace.html`, `workspace.js`, `workspace.css` | Interface actuelle, pages chaine/projet, script colle, progression et outils avances |
| `workspace_api.py`, `workspace_management.py` | Donnees et operations du workspace, gestion des chaines/styles/projets |
| `workspace_voice.py` | Parcours de voix, fournisseurs et suivi des jobs |
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

Les integrations disponibles ne constituent pas une autorisation de changer de fournisseur. Les deux derniers kits Survivor emploient le CLI Proxy configure ; God of War utilisait Google Flow. Preserve ces choix par projet.
