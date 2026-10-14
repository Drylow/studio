# Continuité des chaînes et scripts à reprendre

État documentaire : 14 octobre 2026, après livraison Viking et Pirate. Lire
[CHANNELS.md](CHANNELS.md), puis les dossiers de chaque épisode. Un titre
similaire, un ancien pilote ou un projet partagé du collègue ne remplace pas
le script du film effectivement reçu par l'utilisateur.

## Suite aliens : bonne série et bon jour 30

La première vidéo demandée dans ce chat est **One Stick Left — Alien Outbreak
Survival: Day 1 to Day 30**. Le kit réel du GoFile original identifie la chaîne
et les personnages. Son film est récupéré, son récit entier transcrit et son
dernier état documenté :

- [Dossier de série](../../chaines/alien-outbreak-survival/README.md).
- [Narration complète récupérée et légèrement corrigée](../../chaines/alien-outbreak-survival/episode-01-day-01-30/narration-recovered-edited.txt).
- [Sortie brute et horloge de reconnaissance](../../chaines/alien-outbreak-survival/episode-01-day-01-30/transcript-recovered-from-final-media.json).
- [Bilan exact de fin J30 et garde-fous J31–J60](../../chaines/alien-outbreak-survival/episode-01-day-01-30/CONTINUITY_DAY30.md).
- [Limite de provenance du script auteur](../../chaines/alien-outbreak-survival/episode-01-day-01-30/ORIGINAL_SCRIPT_STATUS.md).

**Reed et Mara n'ont pas encore quitté la station à la dernière phrase.** Une
ouverture apparaît dans la limite lumineuse, les cercles s'allument vers le
virage, et ils ignorent où les aliens veulent les envoyer. Les sacs gris et
turquoise, les dernières boissons scellées, la nourriture, la lampe faiblissante
et la boîte registre/carte partent avec eux. J31 reprend cette situation ; pas
une ferme atteinte, un refuge nouveau déjà installé ou une évasion inventée.

Le fichier auteur exact n'a pas été retrouvé après inspection des fichiers,
du Git actuel et de la branche historique `codex/lowpoly-cutting`, des projets
TubeForge actifs et archivés et du dossier GoFile. La narration publiée est
récupérée depuis le **vrai MP4**, et honnêtement marquée comme transcription.
Ne pas la rebaptiser « original script » ; une future copie auteur doit être
comparée au film avant de remplacer cette provenance.

**Alien Aftermath** est une autre série. Son
[script de sept jours à la station-service](../../chaines/alien-aftermath-projet/episode-01-gas-station/script-en.txt)
se termine avec Reed seul près d'une ferme ; ce n'est pas le dénouement de
One Stick Left. Ses personnages et assets ne doivent pas être transférés
silencieusement à la suite J31–J60.

## Trois chaînes historiques : mêmes codes, récits distincts

| Chaîne | Narration et références à relire | Situation de l'épisode 1 à conserver |
| --- | --- | --- |
| Samurai Chapters | `chaines/samurai-chapters/episode-01/narration/` : distinguer brouillon, texte envoyé à la voix et paroles récupérées ; maîtres, prompts et contrôles du même dossier | Vie d'un samouraï de rang modeste en temps de paix : obligations, hiérarchie, foyer, paiements et dépenses. La conclusion garde le statut, les sabres, la famille et les contraintes ; ne pas transformer ce récit en bataille constante ou en biographie d'un personnage réel. |
| Viking Chapters | [Script entier](../../chaines/viking-chapters/episode-01/script-en.txt), bible, plans et vraie nouvelle horloge VPS dans `editorial/` | Eirik, fermier norvégien fictif vers 950 : voyage, approche hostile abandonnée, échanges puis retour au travail, hiver et compromis au procès de voisinage. Ni fortune garantie, ni conquête réalisée. Aslaug, Bjorn et les autres identités restent celles des maîtres approuvés. |
| Pirate Pages | [Script entier](../../chaines/pirate-pages/episode-01/editorial/script-en.txt), recherche, bible, plans et nouvelle horloge VPS de l'épisode | Tom, marin fictif des Caraïbes vers 1715, sur un petit sloop : travail, maigres gains, réparation et menaces judiciaires. La fin laisse son choix de vie incertain ; pas de trésor massif, d'exécution montrée ni de pardon ultérieur déjà acquis. |

Ces trois films sont des épisodes originaux de 15–20 minutes, avec images 2D
illustrées cohérentes et voix anglaise. Pour une nouvelle vidéo, sélectionner
un nouvel angle puis rechercher les faits. La formule **Why…** n'autorise pas
de reprendre les mêmes activités avec seulement un nouveau costume.

Les costumes et les décors appartiennent à une époque et un lieu précis. Les
variantes de lumière, angle, état ou dommages sont explicites. Le script,
casting, actions et références sont écrits et relus avant les images ; chaque
plan doit apporter une information ou une conséquence. Les mouvements de
cadrage n'effacent pas une différence de bâtiment entre deux images.

Pour la même histoire, ne pas annuler les dommages : la voile pirate déchirée
est réparée, les états au port/en mer sont distincts et la chemise de remplacement
reste pliée tant que Tom ne change pas de tenue. L'absence de victoire viking
et la modestie des stocks sont des choix du récit, pas des erreurs à corriger.

Les nouveaux films Viking et Pirate ont leur propre voix générée une fois sur
le VPS. Leurs timings actuels remplacent l'ancienne horloge locale. Le dernier
MP4 garde les images du rendu natif VPS, avec une finition de volume audio sans
réencodage vidéo ; utiliser les preuves et fichiers de livraison de la version
finale. Ne pas reprendre les temps d'un ancien brouillon dans ses chapitres.

## Autres projets de survie — conserver leur indépendance

- **Patch Survives**, premier supermarché :
  [script](../../chaines/survivor-projet/episode-01-supermarket/script-en.txt)
  et storyboard. Au jour 30, Patch et Mara ont quitté le magasin par la cour,
  traversé le canal avec le petit chariot et leurs caisses, puis se reposent
  près d'un abri dans les jardins. Les infectés, sacs, portes et état du magasin
  sont ceux de cette série, pas du bunker de Last Safe Door.
- **Deep Sea Survival**, Marin :
  [fiche](../../chaines/deep-sea-survival-projet/README.md) et épisode
  `episode-01-stranded-at-sea/`. Le bateau rouge sombre et ne revient pas ;
  radeau, bouée/cloche et sauvetage sont les étapes de la fin du jour 30.
  Les règles du monstre sont une fiction, pas des faits zoologiques ni des
  consignes réelles de survie.
- **Huit projets du collègue** :
  [index](../../output/scripts/survivor-wave-2026-10-13/README.md), narration,
  `story-bible.json` et `codex-review.json` propres à chaque dossier. Ils sont
  autonomes : trois Patch, trois Alien Aftermath et deux Deep Sea. Le temps
  estimé de script ne prouve pas une voix ou un rendu terminé. Vérifier l'état
  réel du projet VPS avant de relancer quoi que ce soit.
- **Last Safe Door**, bunker zombie, et les autres premiers travaux de ce
  chat : reprendre leurs fichiers réellement retrouvés et leur provenance,
  pas un scénario Patch choisi parce qu'il parle aussi de zombies. Une source
  absente reste signalée comme absente jusqu'à restauration vérifiée.

## Scene Analysis Guy — dialogues analysés comme des coups

Les textes et états sont dans
[experiments/conversation-chess/](../../experiments/conversation-chess/README.md)
et dans la [reprise détaillée](../REPRISE.md). Le film conserve les dialogues
originaux et analyses écrites anglaises, sans voix off ; icônes Chess.com
originales, barre à gauche, pions noir/blanc de même dessin, compteur dérivé
des annotations réelles. Le premier interlocuteur de chaque conversation joue
les Blancs ; une nouvelle conversation remet l'évaluation à zéro.

L'avatar de la chaîne Tony reste distinct du pion d'analyste utilisé dans un
film : Tommy, Landa, Hannibal ou un personnage d'animé doivent garder leurs
assets approuvés, avec leurs badges. L'intro et l'outro utilisent la même liste
de coups que le montage. Conserver les crédits des musiques effectivement
utilisées et les montages natifs éditables, pas seulement un MP4.

Les retours utilisateur sur les réclamations appartiennent au fichier exact
testé : Landa/Sopranos réclamés, Peaky bloqué dans des territoires puis abandonné,
test Hannibal déclaré sans détection. Aucun test court ou montage modifié ne
garantit les droits, l'absence de futur claim ou des revenus conservés. Ne pas
relancer Peaky ou présenter le TXT de procédé comme une garantie universelle.

## Chaînes déjà présentes dans le dépôt

- **Oddly Specific Lives** : narration POV, règles et sujets dans
  `chaines/oddly-specific-lives/`, `CLAUDE.md` et `services/pov_engine.py`.
  Les scripts de nationalités/métiers sont propres à chaque vidéo ; ne pas
  confondre leur casting avec l'humain Reed de la fiction aliens.
- **Oddly Specific Things** : l'objet narrateur reste un objet **sans visage** ;
  sa trajectoire de main en main détermine les scènes. Garder ses états matériels,
  quantités et chronologie dans le script de l'épisode concerné.
- **Oddly Expensive Lives** : montants et somme du « running tab » viennent de
  la recherche de cet épisode. Les factures d'une autre vie ne se recyclent pas.
- **Oddly Fictional Lives**, **Edo Daily**, **Aztec Daily**, **Babylon Daily**,
  **Imperial China Daily**, **Ottoman Daily**, **The Survivor's Account** et
  **Frontier Blood** : leurs dossiers/versionnements et règles existants
  restent conservés. Les nouvelles chaînes Samurai/Viking/Pirate ne remplacent
  pas ces identités ou leurs scripts.
- **Octave Histoire** : outil et journal dans `tiktok_engine/`. L'ancien état
  annoncé de file jusqu'au 22 octobre ne remplace pas un contrôle actuel chez
  Zernio avant de réserver un créneau. Pas de doublon ni de changement d'heure
  pour passer d'une IA à une autre.
- **Cage Dispatch / Pitch Dispatch** : consulter l'état réel et la reprise du
  pilote serveur avant de changer les publications. Le mode Google Testing
  et ses reconnexions ne sont pas résolus par le fait de pousser une passation.
- **Silent Little Worlds / anciennes propositions sleep de ce chat** :
  l'utilisateur a arrêté ce projet avant de reprendre chess. Ne pas réactiver
  le jardin ni une synthèse longue en reprenant le dépôt. Les projets sleep du
  collègue documentés ailleurs (Deep Void / Quiet Paradox) restent distincts.

## Avant toute reprise ou automatisation

Identifier la chaîne YouTube réelle et le profil de destination, le script de
la dernière vidéo effectivement publiée, les fichiers exacts livrés et l'état
de la queue distante. L'utilisateur demande maintenant de préparer l'automatisation
du posting avec son autre outil ; cette passation ne crée ni nouvelle publication
ni programmation. Lire [POSTING_HANDOFF.md](POSTING_HANDOFF.md) avant d'agir.

Pour une suite, consigner en tête du nouveau dossier : état final hérité,
personnages présents, objets disponibles, lieux accessibles, dégâts persistants,
règles connues et inconnues. Toute nouvelle information se produit dans la
nouvelle narration. Un fichier absent ou un résultat de téléchargement incertain
ne se remplace pas par une histoire inventée pour déclarer la sauvegarde complète.
