# References par univers

Demande utilisateur du 11 octobre 2026 : remplacer les anciens styles du site
TubeForge et utiliser uniquement Google Flow pour les images. Suite de la
demande : un style par theme, avec trois nouvelles images de reference chacun.

- Pokemon : dresseur et partenaire, centre de soins, entrainement au combat.
- Naruto : entrainement individuel, pause ramen, exercice avec un clone.
- God of War : passage enneige, forge, confrontation dans des ruines.

Les neuf fichiers selectionnes sont indiques dans `registre.json`, avec les
prompts exacts, les references effectivement envoyees et la relecture visuelle.
Les deux premiers rendus de la forge et de la confrontation sont conserves
comme essais rejetes ; les versions v2 habillees sont celles installees.

Les trois images d'un style illustrent son dessin et son univers. Elles ne
remplacent pas les maitres de lieux ni les fiches de personnages d'un episode.
Chaque plan garde son prompt exact et ses references choisies explicitement.
Les nouvelles references ont ete regardees par Codex ; elles n'ont pas encore
ete validees individuellement par l'utilisateur.

Le catalogue contient uniquement les trois nouveaux styles. Les definitions
retirees sont sauvegardees hors du catalogue dans les donnees privees. Leurs
images restent a leur emplacement pour les projets existants. Les sept
projets existants ont conserve leurs fichiers JSON a l'identique.

La migration est dans `production/tubeforge_support/workspace_visuals.py`.
Elle est explicite et executee une seule fois ; un redeploiement conserve les
modifications suivantes des styles. Le fournisseur image est impose aux
nouvelles videos et aux generations dirigees ; le fournisseur texte reste
le CLI Proxy. `site-validation.json` consigne les controles du site deploye.
