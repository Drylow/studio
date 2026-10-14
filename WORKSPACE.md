# Dossier de travail

Les livraisons se trouvent dans les catégories numérotées :

- **01 - Videos** : une chaîne, puis un dossier par vidéo. MP4 final, miniatures et **un seul `PUBLICATION.txt`** regroupant titre, description, tags et informations de publication.
- **02 - Chaines** : photo de profil et **un seul `CHAINE.txt`** par channel kit.
- **03 - Creation** : accès aux scripts, références visuelles, recherches, styles et méthodes.
- **04 - Documentation** : accès aux consignes, à la reprise et aux guides techniques.
- **90 - Archives** : anciennes versions, essais et archives uniques conservées.
- **99 - Technique** : accès au code, aux données, aux journaux et aux preuves de production.

Cette organisation des livraisons est locale. Les catégories contiennent les fichiers prêts à utiliser ; les raccourcis donnent accès aux sources conservées à leurs chemins habituels. Les anciens points d'entrée techniques sont masqués dans l'Explorateur pour rendre la racine lisible, sans modifier leurs noms, les imports ou les accès de TubeForge.

Pour reprendre avec une IA : lire **AGENTS.md**, **CLAUDE.md** et **README_REPRISE.md**, toujours présents à la racine, puis la reprise privée de la production concernée dans `work/`. Le rangement ne relance aucune chaîne ou génération. Les nouvelles productions, leurs images et leur montage s'exécutent sur le VPS via le Studio existant.

Les commandes peuvent toujours lire directement les chemins masqués. Pour rechercher dans ces sources avec ripgrep, utiliser `rg --hidden --no-ignore` sur le dossier concerné.

**Format des prochaines livraisons :** ne plus créer de fichiers TITLE, DESCRIPTION, TAGS, UPLOAD et README séparés pour chaque vidéo. Regrouper le texte destiné à l'utilisateur dans `PUBLICATION.txt`. Les prompts de miniatures peuvent figurer à la fin de ce même fichier. Garder les scripts de travail, historiques, reçus et contrôles dans la partie technique, sans les mélanger au dossier de publication. Ne pas créer de ZIP ni d'exports de clips individuels sauf demande explicite.

Les suppressions du 14 octobre concernent des fragments déjà concaténés, des ZIP dont les entrées ont été comparées aux fichiers conservés, les exports CapCut devenus inutiles et les caches reconstruisibles. Les références originales, films complets, voix sources, paramètres, données et consignes sont conservés. Le journal précis et les empreintes se trouvent dans `work/organisation-2026-10-14/`.
