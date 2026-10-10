# Tommy / Alfie — reprise de production

Production reprise sur demande de l’utilisateur, après résolution de son
problème de compte Google. Aucun envoi YouTube. Le fond Sleep reste prioritaire.

## État vérifié

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
  pauses, guide 16 s, bilan 12 s. Durée finale prévue : **15 min 27,900 s**,
  27 837 images. Le compteur vient des annotations, jamais d’un nombre choisi.
- Revue indépendante de douze captures de la troisième confrontation et des
  cartes corrigées. Corrélation technique de l’audio aux quatre sorties de
  dialogue avec les originaux. Aucune écoute humaine continue revendiquée.
- Tir et bagarre coupés avec des transitions explicites. Une arme et du sang
  sur le visage restent visibles. La clarification finale d’Alfie est conservée.

Le préflight de la timeline passe. Les **67 segments** sont préparés sur six
pistes séparées : 33 sources, 32 analyses, guide et bilan. L’export natif
Kdenlive/MLT est en cours, puis le job doit contrôler le vrai MP4 et extraire
ses captures. **Le MP4 final n’est pas encore vérifié ni livré.** Le titre,
la description et la miniature restent des propositions.

Le checkpoint privé courant se trouve dans
`output/conversation-chess/tommy-alfie-native/RESUME.md`, avec un état précis
dans `progress.json`, le projet éditable `kdenlive/`, les logs et les commandes
de reprise. Le job autonome ne fait aucun envoi YouTube, GoFile ou Discord.

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
```

Comparer le master reconstruit à son reçu avant la préparation. Si une version
de l’encodeur change l’empreinte, vérifier le nouveau master puis mettre à jour
la timeline explicitement. Ne pas retirer le contrôle d’empreinte.

## Contrôles avant livraison

Mesurer et décoder le vrai export, comparer l’audio rendu aux pistes préparées,
examiner les images du film final : guide, barre, première parole, analyses,
transitions et tableau. Les catégories Chess.com autorisées restent celles du
kit approuvé, sans Miss ni violet. Joindre les crédits des musiques à la
description. L’absence de réclamation et la monétisation ne sont pas garanties
par le changement de série : les extraits restent protégés.
