# The Little Railway of Quiet Places

**EN RÉSERVE — ne pas livrer.** Après l’export du train, l’utilisateur veut une
première vidéo située dans un **petit jardin cosy**, plus cohérente avec Quiet
Little Worlds. Le film du train n’a été ni envoyé sur GoFile ni livré à Discord.
`HOLD.json` bloque ces deux actions. La voix et le montage sont conservés, mais
le récit dépend du train : ne pas simplement remplacer son image par un jardin.
La nouvelle direction sera préparée après comparaison des performances publiques
de Stephen Dalton, puis choix d’un décor de jardin.

Premier épisode de **Quiet Little Worlds**, autorisé explicitement le 11 octobre
2026 après le choix du train A : deux heures d’histoires, voix apaisante, recherche
du traitement musical chez Stephen Dalton et réflexion sur les sous-titres.

## Choix éditoriaux

Huit histoires originales anglaises, reliées par une collection de cartes
postales à bord du train : gare, serre, atelier de couture, librairie, maison
au port de rivière, boulangerie du verger, poste, jardin de gare. Mara accompagne
le voyage ; Pip dort dans le compartiment. Fiction explicite, aucun emprunt de
texte, de voix clonée ou de musique à la chaîne de référence.

L’anglais et la fiction sont le choix de production annoncé à l’utilisateur,
sur la base de la direction proposée. Une question facultative a été envoyée,
sans réponse au moment du lancement. Ne pas transformer cette absence de
réponse en validation explicite d’une option.

La boulangère du village mentionnée au chapitre 3 n’est pas Tomas, qui tient
une boulangerie différente au verger. Ruth habite près de l’estuaire ; sa lampe
a une base verte et un abat-jour en verre laiteux à petites feuilles peintes.

Les sous-titres anglais sont **activables via un fichier SRT** ; aucun texte
permanent ni changement de carton lumineux dans la vidéo. Les chapitres sont
présents dans le MP4 et dans la description. Ne pas prétendre qu’une animation,
des sous-titres ou l’absence de claim garantissent la monétisation.

## Son et image

Voix narrative Earl Blackwood déjà disponible dans le service configuré,
vitesse 0,75. Chaque prise possède une empreinte, un reçu privé et la
transcription native, comparée au texte relu. Les erreurs réseau de lecture
ne relancent pas une nouvelle commande payante. Aucun achat ni abonnement
supplémentaire, aucun usage d’Algrow pour cet épisode.

Pluie/roulement et musique composés de zéro : voir [AMBIENCE.md](AMBIENCE.md).
Le mix conserve la voix au premier plan, les deux fonds restant très bas.
Les pauses ajoutées sont aux limites des paragraphes ; les mots sont calés
sur les timings vocaux réels, puis les sous-titres décalés avec le montage.
Les deux heures ne répètent pas l’histoire et ne finissent pas par une heure
de silence ou d’ambiance seule.

Le cycle animé de 24 secondes est répété 300 fois. La voix déroule des visites
imaginaires ; l’image reste le refuge dans le train, pas une reconstitution de
chaque phrase. Sortie 1080p30, source légèrement agrandie depuis 1672 × 941.
La compression de livraison conserve la même animation. Aucun rendu de
216 000 images nouvelles ni génération vidéo payante n’est nécessaire.

## Reproduction et reprise

Résultats privés : `output/nature-sleep/night-train-production/`. Le `.env`
reste privé. NumPy, SciPy, Requests, python-dotenv et FFmpeg sont nécessaires.

```sh
.venv/bin/python experiments/nature-sleep/night-train/episode-01/narrate.py \
  00-welcome 01-platform 02-conservatory 03-mender 04-bookshop \
  05-tide-tables 06-orchard-bakery 07-postcards 08-last-lantern
.venv/bin/python experiments/nature-sleep/night-train/episode-01/make_ambience.py \
  --out output/nature-sleep/night-train-production/ambience
.venv/bin/python experiments/nature-sleep/night-train/episode-01/build.py voice
.venv/bin/python experiments/nature-sleep/night-train/episode-01/build.py mix
.venv/bin/python experiments/nature-sleep/night-train/episode-01/build.py package
.venv/bin/python experiments/nature-sleep/night-train/episode-01/build.py verify
```

Avant `package`, le cycle livré doit être préparé à partir du MP4 de 24 secondes
contrôlé (SHA-256 `7245dd4f90b9606ce78ceec49dee2b115566b568868b64220ac739ffdff8d0f1`) :

```sh
ffmpeg -i output/nature-sleep/night-train-preview/Quiet-Little-Worlds-Night-Train-24s.mp4 \
  -an -c:v libx264 -preset slow -crf 22 -pix_fmt yuv420p -threads 2 \
  -movflags +faststart output/nature-sleep/night-train-production/loop-delivery-test.mp4
```

Le cycle de livraison comporte exactement 720 images à 30 i/s. `package`
limite explicitement la copie à 216 000 images pour éviter deux B-frames
supplémentaires à la fin. `voice` calibre des pauses naturelles plutôt que de
ralentir artificiellement la narration. Le build bloque si la marge de pauses
sort de 0,3–4,5 secondes ; il faut alors revoir le texte ou les prises.

Les tâches vocales déjà soumises sont reprises. Une requête incertaine reste
marquée et bloque la répétition aveugle. Le générateur d’ambiance refuse
d’écraser un dossier existant. Vérifier le cycle source et ses empreintes avant
de reconstruire ; contrôler le film assemblé avant toute livraison.

Livraison prévue : MP4 sur GoFile, miniature issue du film, SRT et kit de
publication dans le Discord **dédié Quiet Little Worlds**. Le branding déjà
reçu ne doit pas être renvoyé. Aucune publication YouTube automatique autorisée
dans cette tâche. Les reçus et le bilan final sont ajoutés après contrôles.
