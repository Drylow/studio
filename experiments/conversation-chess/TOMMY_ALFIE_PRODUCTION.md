# Tommy / Alfie — reprise de production

Production reprise sur demande de l’utilisateur, après résolution de son
problème de compte Google. Aucun envoi YouTube. Le fond Sleep reste prioritaire.

## Correction demandée — validation du pion Shelby en attente

L’utilisateur demande désormais **Thomas Shelby comme pion analyste** dans
cette vidéo Peaky. Le premier export terminé ci-dessous utilise encore Tony :
il reste une archive privée et **ne doit pas être livré**. Le nouveau pion doit
être montré seul à l’utilisateur et validé par lui **avant toute intégration ou
nouveau montage**. Aucun nouvel export n’est lancé à ce stade.

Cette correction concerne le guide, les bulles et le bilan du seul épisode
Peaky. L’avatar Tony de la chaîne, les fichiers Tony génériques et les deux
pions identiques de la barre d’évaluation restent distincts. Le renderer permet
déjà une mascotte par timeline via `mascot.file` et `mascot.overlay_file`,
chemins locaux relatifs au toolkit. Le nouveau PNG transparent devra être
contrôlé et son empreinte enregistrée dans le manifeste après validation.

Un simple rafraîchissement d’intro est insuffisant : le pion figure dans les
32 analyses, l’outro et son fond déjà incrusté. Les sources/replays, dialogues,
SFX, musiques et compteurs restent réutilisables si la timeline ne change pas.
Le MP4 corrigé devra recevoir sa propre QA et revue ; les preuves de l’ancien
export ne l’approuvent pas automatiquement.

## Archive vérifiée du premier export — pion Tony

- Trois originaux anglais locaux : S02E02, S02E06, S03E06. Leurs empreintes
  sont dans [la source map](tommy-alfie-source-map.json). Aucune réacquisition
  des épisodes, aucun nouveau service payant.
- Maximum réellement disponible : 1280×720 natif, sans sous-titres incrustés
  observés sur les captures examinées. Les graphismes et l’export sont en
  1920×1080 ; ce n’est pas une source native 1080p.
- Master sélectionné : **707,233 s / 21 217 images à 30 fps**. Décodage complet
  audio et vidéo passé, empreinte
  `3adba2f578f0db7b3e199fab368b3404a577adf86687d14412ff08cc74c59eca`.
- Ouverture réelle : Tommy, donc **Tommy Blanc / Alfie Noir**. Les sous-titres
  anglais séparés, l’ASR locale et l’image native recoupent la première réplique.
- [Timeline](tommy-alfie-long-timeline.json) : **32 analyses**, 192,667 s de
  pauses, guide 16 s, bilan 12 s. Durée finale mesurée : **15 min 27,900 s**,
  27 837 images. Le compteur vient des annotations, jamais d’un nombre choisi.
- Revue indépendante de douze captures de la troisième confrontation et des
  cartes corrigées. Corrélation technique de l’audio aux quatre sorties de
  dialogue avec les originaux. Aucune écoute humaine continue revendiquée.
- Tir et bagarre coupés avec des transitions explicites. Une arme et du sang
  sur le visage restent visibles. La clarification finale d’Alfie est conservée.

Le préflight de la timeline passe. Les **67 segments** sont préparés sur six
pistes séparées : 33 sources, 32 analyses, guide et bilan. **L’export natif
Kdenlive/MLT est terminé et sa QA technique/audio passe.** Le MP4 fermé fait
441 707 071 octets, 27 837 images en 1080p30, avec audio AAC48k stéréo.
Son empreinte réelle concorde avec le reçu natif :
`24308206f0147649a22af173db41e3a3f50ecedfe8178ade89f1a328cbf73e55`.

Le contrôle du fichier final comprend un décodage A/V complet, 67 comparaisons
audio avec les pistes préparées, les 32 cues de grade et 32 silences de lecture.
Aucune erreur ni avertissement, aucun échantillon écrêté ; true peak −4,9 dBFS.
Les **181 captures réelles** ont été examinées sur 25 planches ; une revue
indépendante de douze images concorde, sans défaut majeur observé. Ce contrôle
par images n’est pas une vision continue du mouvement ni une écoute humaine
complète. **Aucune livraison GoFile/Discord, aucune publication YouTube : la
revue du root reste requise avant livraison.** Le titre et la miniature restent
des propositions.

Le bilan affiché dans le vrai export correspond aux **32 analyses** :
19 Tommy / Blanc et 13 Alfie / Noir. Totaux : Brilliant 7, Great 7, Best 8,
Excellent 0, Good 2, Inaccuracy 2, Mistake 4, Blunder 1 et Book 1. Neuf visuels
officiels du kit, sans Miss ni catégorie violette.

Le checkpoint privé courant se trouve dans
`output/conversation-chess/tommy-alfie-native/RESUME.md`, avec un état précis
dans `progress.json`, le projet éditable `kdenlive/`, les logs et les commandes
de reprise. `FINAL_HANDOFF.md` détaille l’export terminé et ses preuves ;
`qa/audio-technical-qa.json` et `qa/subagent-visual-review.json` gardent les
contrôles réels. Le job autonome ne fait aucun envoi YouTube, GoFile ou Discord.
La description privée `kit/description-draft.txt` inclut les crédits réels de
Sneaky Snitch et Scheming Weasel (faster version), Kevin MacLeod, sous CC BY 4.0.
Conserver ces crédits et leurs liens de licence dans la description livrée.

## Refaire à partir des sources privées

Placer les trois originaux contrôlés, sous les noms de la source map, dans un
dossier local. Depuis la racine du dépôt :

```bash
.venv/bin/python experiments/conversation-chess/prepare-source-master.py \
  --source-map experiments/conversation-chess/tommy-alfie-source-map.json \
  --source-root /chemin/des/originaux \
  --out /chemin/du/master \
  --heading 'TOMMY vs ALFIE' --audio-language eng --workers 1

node experiments/conversation-chess/render-clip.mjs --validate-only \
  --source /chemin/du/master/source-master-native720p30.mp4 \
  --timeline experiments/conversation-chess/tommy-alfie-long-timeline.json

node experiments/conversation-chess/render-clip.mjs --prepare-project \
  --source /chemin/du/master/source-master-native720p30.mp4 \
  --timeline experiments/conversation-chess/tommy-alfie-long-timeline.json \
  --out /chemin/des/pistes

bash experiments/conversation-chess/with-editor-display.sh .venv/bin/python \
  experiments/conversation-chess/export-kdenlive.py \
  --manifest /chemin/des/pistes/project-manifest.json \
  --bundle /chemin/du/projet-kdenlive \
  --render /chemin/du/film.mp4

.venv/bin/python experiments/conversation-chess/check-native-export.py \
  --file /chemin/du/film.mp4 \
  --manifest /chemin/des/pistes/project-manifest.json \
  --bundle-manifest /chemin/du/projet-kdenlive/bundle-manifest.json \
  --timeline experiments/conversation-chess/tommy-alfie-long-timeline.json \
  --out /chemin/du/controle-final --workers 1
```

Comparer le master reconstruit à son reçu avant la préparation. Si une version
de l’encodeur change l’empreinte, vérifier le nouveau master puis mettre à jour
la timeline explicitement. Ne pas retirer le contrôle d’empreinte.

## Contrôles avant livraison

[Le helper QA générique](check-native-export.py) demande un reçu natif
`export_completed: true` correspondant au fichier et à son empreinte. Il
vérifie le profil 1080p30/AAC48k, les durées et l’audio réel, puis extrait guide,
analyses, transitions, chapitres et bilan. Il utilise FFmpeg, ffprobe, NumPy et
Pillow ; les fichiers préparés doivent rester disponibles. Le contrôle complet
garde deux copies PCM locales pour la comparaison et demande de l’espace disque.
`--frames-only` refait seulement les captures après contrôle du reçu et du profil,
sans décoder ni approuver l’audio ; `--skip-frames` omet l’extraction d’images.

Le script n’approuve jamais automatiquement l’apparence, une écoute humaine ou
la livraison. Examiner les vraies captures du film final, notamment l’ouverture
Blancs, la barre gauche, les pions identiques, les textes et les comptes. Les
catégories Chess.com autorisées restent celles du kit approuvé, sans Miss ni
violet. Joindre les crédits musicaux à la description. L’absence de réclamation
et la monétisation ne sont pas garanties par le changement de série : les
extraits restent protégés.
