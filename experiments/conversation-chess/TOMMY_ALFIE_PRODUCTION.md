# Tommy / Alfie — reprise de production

Production reprise sur demande de l’utilisateur, après résolution de son
problème de compte Google. Le nouveau film Shelby et son kit sont livrés sur
GoFile et Discord. Aucun envoi YouTube. La direction Sleep est désormais une
recherche de concepts doux pour adultes ; le fond marin inquiétant est abandonné.

## Correction Shelby validée — export contrôlé et livraison confirmée

L’utilisateur a validé le portrait frontal **Thomas Shelby comme pion analyste**
et demandé le montage final, puis la livraison sur son webhook avec titre,
description et choix de miniatures. Le premier export terminé ci-dessous
utilise encore Tony : il reste une archive privée et **ne doit pas être livré**.
Le nouveau pipeline natif a terminé dans un dossier distinct. Le MP4 Shelby
est fermé, son décodage complet A/V et sa QA technique/audio passent ; la
revue du root est terminée et les reçus GoFile/Discord sont confirmés.

- Sprite final intact : [PNG Shelby](assets/peaky/shelby-pawn-approved-2026-10-11.png),
  1254×1254 RGBA, SHA256
  `de053ed15db958a0444d3327571c5223a2d53471cb876d49f11bb1011e7b3c04`.
- [Timeline corrigée](tommy-alfie-shelby-timeline.json), SHA256
  `70de2668c233341fd8d47e97a53e63701ebeda5c94be039e978b3ffdd398fd0a` :
  32 analyses, ouverture Tommy Blanc, anglais sans voix off ; seulement la
  configuration de mascotte change. Préflight réel passé.
- Le nouveau guide, les 32 analyses et le bilan, y compris le fond incrusté,
  sont régénérés. Source, dialogues, replays et musiques inchangés réutilisés
  après vérification de timeline et des empreintes. Projet Kdenlive séparé,
  preset medium/CRF17 et AAC192, deux threads d’encodage. L’affinité initiale
  CPU0/1 a été élargie à CPU0–3 après la QA lourde du fond marin, sans
  redémarrage ni changement de preset ; reçu privé d’affinité conservé.
- Checkpoint privé : `output/conversation-chess/tommy-alfie-shelby-native/`,
  `progress.json` et `resume-shelby-native.py`. Le job n’envoie aucun fichier ;
  le root gère livraison et Git après la QA du nouveau MP4.

Le fichier corrigé est `Tommy-Alfie-Shelby-15m28.mp4` dans ce checkpoint :
**444 369 182 octets, 27 837 images, 1920×1080 à 30 fps**, vidéo 927,900 s
(conteneur 927,914 s), audio AAC48k stéréo. L’empreinte du MP4 concorde avec le
reçu natif `export_completed: true` :
`97725d9abe363e8c421adaab5367464275a0700efb27cd8eb2ad88743c59a694`.
L’export natif a pris environ 26 minutes ; le délai observé n’est pas une
garantie pour les prochains montages.

La QA propre à ce fichier passe : décodage complet A/V, 67 comparaisons
audio, 32 cues de grade et 32 silences de lecture, zéro erreur ou avertissement,
zéro échantillon écrêté, true peak −4,9 dBFS. Les 181 captures sont extraites
du MP4 terminé, jamais des pistes préparées. Les 132 captures de raccord
ont été regardées, ainsi que le guide, l’ouverture Tommy/Blanc, une analyse
finale et l’outro en plein cadre : aucun Tony ni ancien essai, aucun texte
coupé observé. La revue indépendante est terminée : 14 planches, les
32 analyses, le guide, les chapitres et le bilan ont été regardés. Elle a
recalculé l’empreinte du MP4 et ne trouve pas de défaut dans ce périmètre.
Les 181 captures sont ainsi couvertes par les deux revues, sur 25 planches.
Cette inspection par images ne constitue ni une vision continue du mouvement
ni une écoute humaine complète. Les reçus `audio-technical-qa.json`,
`boundary-visual-review.json`, `subagent-visual-review.json` et
`team-final-review.json` sont dans `qa/`. Le reçu de livraison du root
ajoute sa revue de 85 captures distinctes, dont trois vues natives.
GoFile et Discord sont confirmés : [kit final](https://gofile.io/d/cCuEdqOv),
message `1558649618949079100`, pièces jointes `Kit_publication.txt`,
`MUSIC_CREDITS.txt` et `thumbnail.jpg`. Aucune publication YouTube effectuée.
Voir [le reçu public](PEAKY_SHELBY_DELIVERY.json).

Le bilan du fichier corrigé affiche exactement 32 annotations : 19 Tommy/Blanc
et 13 Alfie/Noir. Brilliant 7, Great 7, Best 8, Excellent 0, Good 2, Inaccuracy 2,
Mistake 4, Blunder 1 et Book 1. Neuf visuels du kit officiel, sans Miss ni violet.
Les extraits restent natifs 720p ; les graphismes et l’export sont en 1080p.
Conserver dans la description les crédits de Sneaky Snitch et Scheming Weasel
(faster version), Kevin MacLeod, sous CC BY 4.0.

Cette correction concerne le guide, les bulles et le bilan du seul épisode
Peaky. L’avatar Tony de la chaîne, les fichiers Tony génériques et les deux
pions identiques de la barre d’évaluation restent distincts. Le renderer permet
déjà une mascotte par timeline via `mascot.file` et `mascot.overlay_file`,
chemins locaux relatifs au toolkit. Le PNG transparent est validé ; son
empreinte doit concorder avec le nouveau manifeste. L’édition photographique
par générateur reconstruit des détails ; la
[fiche d’asset](assets/peaky/shelby-pawn-approved-2026-10-11.json) conserve
la vraie référence BBC et ne revendique pas des pixels de visage inchangés.

Un simple rafraîchissement d’intro est insuffisant : le pion figure dans les
32 analyses, l’outro et son fond déjà incrusté. Les sources/replays, dialogues,
SFX, musiques et compteurs restent réutilisables si la timeline ne change pas.
Le MP4 corrigé a reçu sa propre QA, ses captures réelles et sa revue de
livraison. Les preuves de l’ancien export ne l’approuvent pas automatiquement.
La miniature livrée reprend exactement le style demandé de Sopranos A :
Tommy à gauche, Alfie à droite, trait blanc incliné et badges officiels !!/??.
Les quatre titres restent des propositions ; aucun choix final utilisateur
n’est enregistré.

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
  --timeline experiments/conversation-chess/tommy-alfie-shelby-timeline.json

node experiments/conversation-chess/render-clip.mjs --prepare-project \
  --source /chemin/du/master/source-master-native720p30.mp4 \
  --timeline experiments/conversation-chess/tommy-alfie-shelby-timeline.json \
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
  --timeline experiments/conversation-chess/tommy-alfie-shelby-timeline.json \
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
