# Les chaînes

Un dossier par chaîne YouTube. Chaque dossier contient :

- **README.md** : le concept, le format, le style (images, voix, miniatures), ce qui marche, et les idées de vidéos.
- **videos/** : une fiche par vidéo, avec :
  - `script.md` : le texte lu par la voix ;
  - `recherche.md` : les faits vérifiés et les consignes données au script ;
  - `publication.md` : les titres, la description, les chapitres, les tags et le commentaire épinglé ;
  - la miniature retenue.

| Chaîne | Format | Dossier |
|---|---|---|
| **Oddly Specific Lives** (@OddlySpecificLives) | « POV: You Marry a … », « Inside the Life of … » | [oddly-specific-lives](oddly-specific-lives/README.md) |
| **Oddly Expensive Lives** (@OddlyExpensiveLives) | « The Economics of … » (le prof explique la facture) | [oddly-expensive-lives](oddly-expensive-lives/README.md) |
| **Oddly Specific Things** (@OddlySpecificThingsYT) | « Your Life as a Stolen … » (tu es l'objet) | [oddly-specific-things](oddly-specific-things/README.md) |

Les trois chaînes ont le même style 2D et la même voix, pour qu'on reconnaisse la même patte d'une chaîne à l'autre :
- des bonshommes à grosse tête ronde blanche, avec des yeux en points noirs et des mains en moufles ;
- la voix Algrow.

## Où trouver le reste

- **Liens des vidéos et état de chaque vidéo** : `production/VIDEOS.md`.
- **Comment on produit, vérifie et publie** : `CLAUDE.md`, à la racine du dépôt.

## Mettre à jour

Les fiches `videos/` sont générées à partir des projets du studio. Après chaque vidéo, relance la commande ci-dessous, puis fais un commit (le push part tout seul) :

```bash
STUDIO_WORK=<dossier de travail> python production/export_channels.py
```

Les fichiers README.md des chaînes sont écrits à la main. La commande ne les écrase jamais.
