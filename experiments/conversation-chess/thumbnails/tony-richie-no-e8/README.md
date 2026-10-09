# Richie Aprile vs Tony Soprano — choix de miniature et titre

Trois propositions pour la coupe **9 min 27, épisodes 3 et 6 seulement**.
Le choix de miniature et celui du titre restent indépendants et attendent
l'utilisateur. La miniature `RESPECT THE BOSS` du premier kit est rejetée.
Cette révision ne remplace pas le film, son kit initial ni ses reçus.

**Nouveau test utilisateur : la coupe est réclamée pour S02E03.** Les options
ci-dessous restent des propositions ; aucune publication n'est déclarée
acceptée. Voir [le rapport](../../COPYRIGHT_REVIEW.md) et les
[sources autorisées envisagées](../../LICENSED_SOURCES.md).

| Option | Style | Fichier |
|---|---|---|
| A | Duel sobre, gros plans séparés, sans texte | [A.jpg](A.jpg) |
| B | Confrontation dans une même pièce, `THE BOSS?` | [B.jpg](B.jpg) |
| C | Visages détourés, humour, `BAD GAMBIT` | [C.jpg](C.jpg) |

Chaque JPEG : **1672×941**, qualité 95, moins de 353 Ko. Bases photographiques
générées depuis deux images des scènes E6 conservées ; Tony à gauche, Richie à
droite. Les acteurs, vêtements, expressions, cadres et textes ont été regardés
à pleine taille et à 320 px. Les bases sans badge et les PNG maîtres sont
conservés dans le dossier privé de révision.

**Icônes : les SVG originaux Brilliant et Blunder du kit Chess.com.** Aucune
pastille redessinée par génération. Couleurs, glyphes et proportions 18:19
sont inchangés ; les fichiers sont contrôlés contre les SHA de `ratings.json`.
Les deux badges restent complètement dans le cadre et dégagent les visages.
Ce sont toujours des assets propriétaires, avec la provenance du kit existant.

Les [cinq titres](titles.txt) contiennent tous **Richie Aprile vs Tony Soprano**
et restent sous 100 caractères. Proposition recommandée : le n° 1,
`The Respect Gambit Backfires`. La veste a été retirée du film court : les
accroches portent sur le respect, le poker et l'ego.

## Recette pour les prochaines miniatures

1. Regarder les références des personnages et choisir un moment du vrai film.
2. Générer une base 16:9 HD sans badge ni faux glyphe, avec deux coins dégagés.
   Conserver les identités, tenues et expressions ; donner une consigne exacte
   de texte court, ou aucun texte. Garder cette base sans la modifier.
3. Poser les SVG du kit avec [compose-thumbnail-badges.mjs](../../compose-thumbnail-badges.mjs).
   Le [layout](badge-layout.json) de ces trois images utilise des coordonnées
   normalisées, à adapter après examen des visages d'une nouvelle image.
4. Regarder le résultat à pleine taille et à 320 px. Vérifier les acteurs,
   badges exacts, expressions, texte et absence de découpe gênante. Exporter un
   JPEG inférieur à 2 Mo et conserver le PNG maître.
5. Livrer les options, attendre le choix utilisateur, puis conserver ce choix
   comme référence des prochaines miniatures. Ne pas présumer une sélection.

Exemple depuis la racine du dépôt, avec une base privée déjà revue :

```bash
node experiments/conversation-chess/compose-thumbnail-badges.mjs \
  --base /chemin/base-sans-badges.png \
  --layout experiments/conversation-chess/thumbnails/tony-richie-no-e8/badge-layout.json \
  --out /chemin/nouvelle-miniature.jpg
```

Le compositeur refuse les fichiers et reçus existants, les SVG dont l'empreinte
diffère et les badges hors cadre. Il conserve le rapport hauteur/largeur des
SVG et vérifie qu'aucun pixel de la base n'est changé hors de leurs rectangles
avant encodage. Le JPEG reste un encodage avec perte. Son sidecar fournit les
empreintes et placements ; `visually_reviewed:false` rappelle qu'une inspection
visuelle séparée du vrai fichier est nécessaire. Cette inspection est consignée
dans le manifest et `finished-visual-review.json` privés.

Les six exports PNG/JPEG et les trois bases ont été vérifiés par empreinte.
Après durcissement des écritures, le nouveau rendu A est identique au JPEG
livré ; les essais d'écrasement d'image et de reçu orphelin sont refusés.

## Livraison

La livraison de cette révision est distincte du kit initial : trois images
A/B/C et `Titres.txt` dans un seul message du Discord dédié Scene Analysis Guy.
Aucun nouvel upload du film ni renvoi de son lien. **Envoi confirmé le 10 octobre
2026**, message `1558242590078279681` : trois images confirmées dans les embeds,
`Titres.txt` confirmé en pièce jointe, aucun envoi incertain en attente.
Les 32 fichiers du film et du premier kit sont identiques à leurs empreintes
avant la révision. Le manifest, les contrôles
locaux du helper et le reçu de confirmation restent sous
`output/conversation-chess/tony-richie-no-e8-native/publication/thumbnail-options-02/`.
Le webhook reste uniquement dans le `.env` privé. Aucun choix final présumé.
