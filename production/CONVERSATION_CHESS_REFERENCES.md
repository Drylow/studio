# Références — conversations analysées comme des parties d'échecs

Recherche du **9 octobre 2026**. Ce document conserve les preuves consultées et
les limites de l'étude. Il ne constitue ni une vidéo terminée ni une validation
des droits sur les extraits de séries.

**Référence prioritaire choisie par l'utilisateur :
[ConversationAnalysisGuy](https://www.youtube.com/@ConversationAnalysisGuy).**
[Analysed Like Chess](https://www.youtube.com/@analysedlikechess) reste une
référence complémentaire. La première adaptation demandée est **The Sopranos**,
avec **Tony Soprano** comme personnage central et une mascotte pion à sa tête.

## Instructions de l'utilisateur

- Décision après visionnage v3 : **Tony contre Richie / The Jacket** sera le
  premier long, pas Tony/Janice. Le montage est validé dans son style, mais la
  qualité des clips et le tableau final doivent changer. Titre/miniature après.
- **Premier personnage qui parle = blanc**, dans toutes nos vidéos. Attribuer
  les camps à partir du vrai début, pas de la première annotation.
- **Miss retiré** du jeu de notes actif à sa demande ; neuf grades conservés,
  aucun Interesting violet. Cela ne réécrit pas les observations historiques
  des catégories effectivement présentes chez la référence.
- Dialogues et annotations **en anglais**.
- **Aucune voix off ajoutée** : conserver les dialogues des personnages.
- La mascotte Tony explique par des panneaux écrits, expressions et mouvements.
- Une barre d'évaluation sur le côté et un petit guide initial pour comprendre
  les catégories, notamment le coup brillant et la gaffe.
- Montage soigné, analyse des échanges et humour ; sélectionner des moments
  clés de la série. Les chiffres d'une autre chaîne ne garantissent pas nos vues.
- Correction après le premier test : **barre à gauche**, vrais visuels
  Chess.com, bruitages de frappe et de note, sourceHD. Ces demandes priment
  sur le placement et les icônes différents de la référence.
- Le choix de cette nouvelle référence prime sur la direction précédente.
  Aucun titre définitif, durée finale ou découpage synchronisé n'est validé par
  cette recherche.

Le prototype original et ses limites sont documentés séparément dans
[experiments/conversation-chess/README.md](../experiments/conversation-chess/README.md).
Ne pas confondre une démonstration d'habillage avec un montage de vrais extraits.

## Ce qui a réellement été examiné

### Limite actuelle : le vrai tableau final et les nouvelles sources HD

La fin de `InM2zft-iQs` n'a pas pu être visionnée. Durée recoupée970–971s.
Le lecteur public normal indique playabilityOK, jusqu'à1080p30, mais aucun
frame ne décode : CDN et URL exacte du storyboard final refusésCONNECT403,
confirmés par requests puiscurl avec proxy/TLS hérités. Deux requêtes Algrow
distinctes échouent avec « YouTube proxy authentication failed » ; aucune
reproduction fidèle de cette fin n'est établie. Le GAME REVIEW du pilote est
une proposition désormais rejetée, pas une observation de la référence.

The Jacket sur la chaîne officielle HBO (`UHvUDYKrFmw`,217s) est la source
prioritaire du nouveau sujet. Le lecteur annonce1080p30 ; une seule demande
normale1080p10–20s échoue côté fournisseur. Ces métadonnées ne prouvent pas la
qualité d'un fichier acquis. Le test Janice mesure1280×720 mais seulement
~0,687Mb/s vidéo : remplacer l'original, pas simplement l'agrandir.

### Musiques et accents — recherche après le retour sur le piloteHD

La description de **Business with Tuco — re-upload** crédite
[Sneaky Snitch](https://www.youtube.com/watch?v=QrqjLoPbnyY) à l'ouverture et
[Scheming Weasel (faster version)](https://www.youtube.com/watch?v=y4zXHvaQ7Ng)
à la fin, tous deux deKevin MacLeod. Les titres ont été recoupés avec leurs
pagesIncompetech, ISRCUSUAN1100772/USUAN1100085 et licenceCCBY4.0.
Les originaux de l'auteur, pas un rip de la vidéo de référence, sont conservés
avec crédits et hashes dans `experiments/conversation-chess/assets/music/`.

La comparaison PCM des12 premières secondes de la référence avec l'original
Sneaky Snitch trouve le début à **66,103875s**, corrélation0,96646 malgré la
compressionAAC. Cette preuve établit le morceau et le passage ; aucune écoute
humaine n'est prétendue. La capture du passage547–558s, notamment9:12, montre
un effet **feu/explosion** plein écran sur la scène deTuco. Elle guide le choix
d'un accent comique ; le son exact n'a pas été identifié à l'oreille et n'est
pas copié. Les extraits de référence restent privés, horsGit.

L'API Algrow configurée a renvoyé les catalogues, descriptions, dates, durées et
statistiques publiques des deux chaînes. Des commentaires publics des trois
longs les plus vus de chaque chaîne ont été lus : dix par vidéo pour Analysed
Like Chess, douze pour ConversationAnalysisGuy. Ces messages sont des exemples
triés par likes, pas une enquête représentative du public.

**L'avatar officiel de ConversationAnalysisGuy a été téléchargé et regardé
directement**, en 176 × 176 puis 800 × 800 pixels. Il n'est pas une capture de
vidéo. Aucun fichier de cet avatar ni extrait de la référence n'est ajouté au
dépôt public.

**Mise à jour : les 25 premières secondes de « Business with Tuco » ont été
récupérées et leurs images examinées directement.** La requête normale Algrow
`download-video`, JSON `format=video`, `quality=360p`, `start=0`, `end=25`, a
répondu HTTP 200 après environ 73 s. Le fichier mesure 640 × 360, dure 25,033 s
et contient vidéo et audio. Le média et les captures restent dans `/tmp`.

Les essais précédents avaient échoué ; le lecteur anonyme sur le VPS montrait
un contrôle anti-bot. Ce résultat ultérieur vient du contrat documenté de l'API,
sans contourner ce contrôle. Il établit le vrai guide et le début de la scène,
**pas le rythme des annotations de toute la vidéo**. L'audio de cet extrait n'a
pas été écouté. Ne pas confondre une image regardée, une description publiée et
une écoute effective.

### Dispositif réellement observé dans cet extrait

- Environ 0–6,5 s : « Annotation Symbols Guide », sur une image de série
  assombrie. Titre blanc en caractères à chasse fixe, petit pion Walter près du
  titre, deux colonnes de six et cinq catégories avec icônes rondes colorées.
- Environ 7–14 s : écran distinct « What is the Evaluation Bar? », texte blanc
  sur image assombrie et barre de démonstration **à gauche**.
- Vers 15 s : fondu noir ; vers 16 s : début de la scène.
- Pendant la scène, la barre est **à droite**, noir au-dessus et blanc en dessous.
  Vers 21 s, noms des camps et petits portraits apparaissent.

Les onze catégories visibles sont **Brilliant (!!), Great (!), Best (étoile),
Excellent (pouce), Good (coche), Book (livre), Blunder (??), Miss (croix),
Mistake (?), Inaccuracy (?!), Interesting (!?)**. Forced, Checkmate et Draw
ne figurent pas dans ce guide ; des demandes en commentaire ne prouvent pas
leur présence à l'écran.

Le second écran décrit un départ à égalité, des camps noir/blanc indépendants
de l'ordre de parole, Best/Great sans déplacement, Book avec un petit avantage,
Brilliant avec un gain et les autres grades avec une perte pour le locuteur.
Une tierce personne ne compte que si sa parole affecte un des camps principaux.
La barre dessinée dans ce guide n'est pas toujours à égalité : distinguer
l'explication écrite de l'exemple affiché.

Le premier guide adaptait ces pages avec onze catégories et des icônes
redessinées. Ce choix a été rejeté après visionnage du pilote. La révision
utilise maintenant dix SVG Chess.com existants, vérifiés par empreinte, et
une barre fine à gauche demandée par l’utilisateur. Le symbole officiel Miss
est un signe moins jaune ; Interesting n’a pas d’asset officiel établi.
Les nouveaux bruitages sont CC0 : clavier enregistré, clic et accents courts.
Les fichiers de la référence servent à l’étude ; ils ne sont pas redistribués.

### Annotations examinées ensuite : extrait 25–100 secondes

Une deuxième requête normale a livré un extrait de 75,166 s en 640 × 360,
avec vidéo et audio. Ses images montrent maintenant les analyses dans la scène :
grade et icône **en haut à gauche**, pion Walter **en bas à gauche**, grande
bulle blanche arrondie avec pointe vers le pion, texte noir révélé progressivement.
La scène est floutée et assombrie pendant ces bulles ; la barre à droite reste
visible. Les paragraphes expliquent le choix, pas seulement le nom du grade.

Le fond ne reste pas sur une seule image : il reprend au ralenti un passage
juste précédent. Des correspondances visuelles et comparaisons normalisées
hors overlays établissent trois exemples : passage d'analyse 50,5–56 s versus
scène claire 42,73–46,5 s, 65,5–69,5 s versus 60,6–61,77 s, et 82,5–86 s versus
75,9–77,87 s. Ce sont des mesures sur cet extrait, pas une règle universelle
sur toutes les vidéos de la chaîne.

L'ASR locale retrouve les dialogues entre les bulles, pas dans les cinq bulles
Book examinées. Quatre maintiens du texte sont quasi muets (environ −72 dBFS),
alors que la révélation du texte comporte des transitoires. Cette mesure
établit une pause de dialogue dans ces exemples ; elle ne remplace pas une
écoute humaine ni n'identifie tous les sons de la vidéo.

Le pilote adapte ce procédé : relecture muette et ralentie des dernières
secondes de sa propre scène derrière la bulle, puis reprise au même repère
du dialogue. Ne pas supprimer les répliques sous un commentaire ni présenter
une image figée ou un simple bandeau noir comme ce dispositif observé.

## Comparaison des deux chaînes

| Élément au relevé du 9 octobre | ConversationAnalysisGuy — priorité | Analysed Like Chess — complément |
|---|---|---|
| Identifiant | `UCLbgX6QFnP19s2aIMl_AkFA` | `UC6BqwJRjN-qmNMFJSM-A0Xw` |
| Abonnés annoncés | Environ 5 140 | Environ 14 400 |
| Catalogue retrouvé | 5 longs + 17 Shorts | 14 longs |
| Durées des longs | 8:40–20:34, médiane 16:11 | 3:22–9:45, médiane 4:48,5 |
| Construction annoncée | Une confrontation ou un arc réunissant plusieurs scènes | Principalement une scène et un duel |
| Guide initial documenté | 16–18 secondes dans les deux longs les plus récents | Non établi par les données consultées |
| Mascotte | Avatar regardé et petit pion constaté dans le vrai guide | Non vérifiée |
| Déclinaisons courtes | 17 Shorts de 35–124 secondes, issus des longs | Aucun Short retrouvé dans le catalogue étudié |
| Sopranos | Aucun upload retrouvé | Aucun upload retrouvé |

Les statistiques du prestataire sont légèrement désynchronisées. Pour
ConversationAnalysisGuy, About annonce **886 925 vues**, alors que les cinq
longs totalisent **698 186** et les Shorts **211 180**, soit **909 366**. Pour
Analysed Like Chess, About annonce **2 313 429 vues**, mais les 14 longs
totalisent **2 752 897**. Ne pas calculer une croissance exacte à partir de ces
réponses incompatibles. Aucune rétention, aucun CTR ou revenu n'a été consulté.
Un upload publié quelques minutes avant le relevé ne se compare pas à une vidéo
qui circule depuis une semaine.

## ConversationAnalysisGuy : structure et identité

La bio annonce une analyse des scènes et dialogues comme des parties d'échecs,
centrée actuellement sur l'univers Breaking Bad. Les descriptions disent
analyser les répliques avec des annotations de coup brillant, gaffe, etc.

Le compte est déclaré créé le **4 septembre 2026**. Son catalogue long contient :

| Vidéo | Durée | Vues relevées | Publication |
|---|---:|---:|---|
| [Gus and Max meet Don Eladio](https://www.youtube.com/watch?v=0XXnB31SOnc) | 13:12 | 329 005 | 20 sept. |
| [Skyler wants a divorce](https://www.youtube.com/watch?v=OM2VFVr_pFs) | 18:40 | 131 106 | 12 sept. |
| [Walt discusses options with Gus](https://www.youtube.com/watch?v=JPd0sTyVdAI) | 8:40 | 104 285 | 5 sept. |
| [Business with Tuco — reupload](https://www.youtube.com/watch?v=InM2zft-iQs) | 16:11 | 67 788 | 6 oct. |
| [The Rivalry between Hector and Gus](https://www.youtube.com/watch?v=PjbHczDl-hI) | 20:34 | 66 002 | 24 sept. |

### Chapitres publiés par le créateur

**Business with Tuco** annonce à **0:00** « Annotation Symbols & Eval Bar
guide », puis démarre la première scène à **0:16**. Les passages suivants sont
datés **6:39**, **10:18** et **10:53**. Ils vont de S01E06 à S02E02 : c'est un
arc de plusieurs rencontres, pas un résumé de toute la série.

**The Rivalry between Hector and Gus** annonce le même guide à **0:00**, puis
la première scène à **0:18**. Les chapitres suivants sont à **8:05**, **9:37**,
**12:37**, **15:07**, **15:47**, **17:05** et **18:50**, jusqu'à S4E7. Un passage
est explicitement nommé « Deleted Scene ».

**Skyler wants a divorce** regroupe trois épisodes : S03E01 à **0:00**, S03E02
à **5:53**, S03E03 à **10:41**. Ces timecodes viennent des descriptions
effectivement lues. Ils établissent le découpage annoncé ; le contenu exact
du guide et les plans de ce long restent à vérifier dans le média. Le guide de
« Business with Tuco » a depuis été examiné directement comme décrit plus haut.

### Avatar regardé directement

Sur fond blanc, une tête photographique de Walter / Heisenberg en noir et
blanc, lunettes, bouc et chapeau noir, remplace la boule du pion. Le corps est
une forme plate gris bicolore, trapue, avec base arrondie ; il ne s'agit pas
d'un pion réaliste en 3D. Une médaille teal **!!** est à gauche et une médaille
rouge **??** à droite. L'ensemble reste lisible à petite taille.

Notre adaptation reprend le principe du **pion à tête de Tony** avec un dessin,
des poses et un habillage originaux. L'avatar Walter ne doit pas devenir une
image de notre marque ni être copié dans Git. L'étude de l'avatar ne prouve pas
comment le personnage est animé ou intervient pendant les vidéos.

### Ce que les commentaires apprécient

Sur **Gus et Max chez Eladio**, les spectateurs discutent les sous-entendus
d'une réplique et le manque de respect que Gus ne mesure pas. Un aspirant
scénariste apprécie l'explication des doubles sens. Le public raisonne sur les
alternatives et conteste certaines évaluations : ce sont des arguments à
écrire, pas seulement des icônes à afficher.

Sur **Skyler et le divorce**, un commentaire décrit le lancer de pizza comme
une action brillante sans explication, ce qu'il trouve particulièrement drôle.
Un autre demande des indicateurs « forced move », « draw », « resign » et « win ».
Cela donne des pistes d'humour et de lisibilité, pas des catégories que nous
avons nous-mêmes constatées à l'écran.

Sur **Walt et Gus**, « Any time Mike speaks: BEST MOVE » devient une plaisanterie.
Plusieurs réponses distinguent les décisions déjà prises du moment où elles
sont révélées : le raisonnement doit suivre la scène, sans inventer les
motivations des personnages comme des faits incontestables.

Des commentaires très aimés demandent une barre sur **deux anciens longs**.
Ils ne prouvent pas son absence dans les deux plus récents, dont les chapitres
annoncent explicitement un guide pour la barre.

## Analysed Like Chess : ce qui reste utile

La bio assigne les Blancs et les Noirs aux protagonistes, transforme actions
et répliques en coups, puis analyse psychologie, bluff et rapport de force.
Ses descriptions commencent souvent par un enjeu concret : une licence
d'avocat, une crédibilité de témoin, un choix sous la menace.

Trois repères du catalogue :

- [Chicanery — Better Call Saul](https://www.youtube.com/watch?v=mA4t3Ph9DI4),
  **7:32**, environ **1,52 million de vues**.
- [Dexter vs Doakes](https://www.youtube.com/watch?v=WUNJZQyuaY4), **4:55**,
  environ **290 000 vues**.
- [Pretending to be Teacher](https://www.youtube.com/watch?v=4PZXqt0zWkI),
  **4:12**, environ **277 000 vues**.

Les commentaires lus apprécient un montage soigné qui dépasse la simple pause
avec une icône. Ils discutent une option manquée, un sacrifice et une riposte
possible. Plusieurs décrivent une **barre à gauche**, mais critiquent un score
qui se comporte comme un rapport de force narratif plutôt qu'un vrai moteur
d'échecs. Il faut donc expliquer notre convention et rester cohérent : une
faute ouvre une possibilité ; la réponse peut l'exploiter.

Cette première référence aide pour le duel lisible et les annotations
argumentées. Elle ne doit pas imposer sa durée ou son identité visuelle à la
nouvelle direction choisie par l'utilisateur.

## Conséquences pour notre première vidéo

Propositions de réalisation, distinctes des constats sur les références :

1. Expliquer les catégories et le sens de la barre avant la première analyse.
   La barre décrit l'avantage **dans cet échange**, pas la moralité ni un résultat
   calculé par un moteur d'échecs.
2. Définir les deux camps et ce qu'ils cherchent à obtenir. Les annotations
   évaluent une décision liée à une réplique ou une action visible.
3. La mascotte Tony fait apparaître une explication courte en anglais. Conserver
   les dialogues ; ne pas masquer un visage ou les sous-titres nécessaires.
4. Alterner explication du sous-texte et rares punchlines. Une annotation doit
   apporter quelque chose, sans transformer chaque phrase en interruption.
5. Si plusieurs scènes sont retenues, leur donner un arc compréhensible :
   pression, piège, erreur, renversement. Une compilation sans objectifs clairs
   ne suffit pas à reproduire le principe.

Un titre candidat issu du cadrage Tony / Ralph est **Tony Wins Without Giving
an Order**. Il reste une proposition à relire avec le vrai média, pas un titre
approuvé ou une promesse de performance. Les durées, positions et évaluations
finales doivent être synchronisées sur les extraits réellement obtenus.

## Son, droits et limites techniques

ConversationAnalysisGuy cite des musiques pour intro/outro, parfois pendant la
vidéo, et indique employer **Chess.com Brand Resources**. Ce sont les
déclarations de l'auteur ; elles ne donnent pas de licence transférable sur
ses sons ou graphiques. Créer nos symboles et transitions, avec des bruitages
autorisés si nous en ajoutons. Aucune voix ou musique n'a été écoutée directement
pendant cette étude.

Les disclaimers « fair use » et les champs `licensed_content` du prestataire
ne prouvent ni des droits sur Sopranos ni une absence de Content ID. Les
contrôles et manifestes du moteur sportif ne couvrent pas automatiquement
les extraits de séries. Ne pas qualifier notre prototype de publication sûre
ou de film prêt à envoyer avant le contrôle du média et du montage.

Les accès directs à YouTube et à ses miniatures ont été refusés par le proxy.
L'API Algrow a fourni les métadonnées, mais trois demandes de téléchargement
de la première référence ont donné deux timeouts et une erreur
« YouTube proxy authentication failed ». Une seule analyse assistée à coût
borné a atteint un timeout sans identifiant ni résultat. Aucun résultat
de vision externe n'est donc utilisé comme preuve ici. Aucune déduction de
crédits n'était observée au relevé suivant ; aucun appel payant supplémentaire
n'a été lancé. La deuxième chaîne n'a fait l'objet que de lectures de données
et du téléchargement de son avatar.

## Sources et reproduction de la recherche

Sources primaires : les deux chaînes et les vidéos liées ci-dessus,
leurs descriptions, chapitres et commentaires publics. Métadonnées obtenues
par les endpoints documentés d'Algrow, sans imprimer les identifiants :

- [Channel Data](https://algrow.online/docs/api/channel-data) :
  `GET /api/channels/:id/about`, `/videos`, `/shorts`.
- [YouTube Search](https://algrow.online/docs/api/youtube-search) :
  `GET /api/search`, paramètres `q`, `type`, `limit`.
- [YouTube Scraper](https://algrow.online/docs/api/youtube-scraper) :
  `POST /api/youtube-scraper-fast`, `include_comments` et `max_comments`.
- [Video Analysis](https://algrow.online/docs/mcp/video-analysis) et
  [Credits & Limits](https://algrow.online/docs/credits) : capacités et limites,
  sans résultat vidéo obtenu pour cette recherche.

Les réponses brutes et les avatars d'étude restent dans les répertoires privés
de travail ; le dépôt conserve cette synthèse et les liens nécessaires pour
refaire les lectures publiques. N'y ajouter ni clés, ni cookies, ni images
de référence protégées.
