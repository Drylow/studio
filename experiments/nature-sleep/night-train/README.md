# Quiet Little Worlds — train de nuit

L’utilisateur a choisi **l’image A** le 11 octobre 2026 et demandé son animation.
L’emploi de ce style sur toutes les vidéos reste **conditionné à sa validation
du nouvel extrait animé**. Ne pas lancer un épisode de deux heures avant ce retour.

Le master sélectionné est conservé dans
`../cozy-reset-2026-10-11/A-cinematic-night-train.png`.
Les nouveaux calques photographiques générés et leurs prompts sont décrits
dans `assets.json`. Le décor n’est pas une prise de vue réelle.

## Composition et mouvement

- Wagon fixe, éclairage stable, meubles et cadre de fenêtre préservés.
- Vallée lointaine et trois couches de sapins qui défilent dans le même sens,
  à 50, 90 et 140 pixels source par seconde suivant leur distance.
- Gouttes sur la vitre, coulures réfractant le paysage actuel et pluie fine.
- Vapeur composée de petites particules translucides qui montent depuis la tasse.
- Respiration très discrète du chat, limitée au torse avec un masque doux.

La préparation retire les fleurs et la vapeur figées du master et remplace
la vue extérieure par une zone d’incrustation. La nouvelle forêt est calculée
derrière cette fenêtre ; aucun ancien cottage ou asset marin n’est réutilisé.

Source principale : **1672 × 941**, sortie **1920 × 1080 / 30 i/s**, avec un léger
agrandissement. Ce n’est pas du 4K natif. Extrait de **24 secondes, silencieux** ;
voix et ambiance sonore attendent le choix de l’animation.

## Aperçu livré

https://gofile.io/d/eIVTL3rq — 24 secondes silencieuses en 1080p30.
Reçu, empreinte et état : `DELIVERY.json`. Cinq planches réelles du MP4 dans
`qa/`, avec les comptes rendus technique et visuel. Aucun épisode long lancé.

## Reproduction

Depuis la racine du dépôt, Node et Playwright du frontend, Chromium système,
FFmpeg et Python/Pillow doivent être disponibles. Aucun service ou API payante
de génération vidéo n’est utilisé par le rendu.

```bash
node experiments/nature-sleep/night-train/render.mjs output/nature-sleep/night-train-check --stills
node experiments/nature-sleep/night-train/render.mjs output/nature-sleep/night-train-check
.venv/bin/python experiments/nature-sleep/night-train/verify.py output/nature-sleep/night-train-check
```

Le rendu refuse d’écraser une vidéo existante. Chromium nécessite un exécuteur
permettant ses sockets de processus ; le sandbox restreint peut empêcher son
démarrage. Aucun accès réseau n’est utilisé dans la page de rendu.

Contrôles : empreintes des assets, égalité des extrémités natives, décompte de
toutes les images du MP4, décodage intégral, mesures du raccord et captures
effectivement extraites du fichier exporté. Les mesures seules ne constituent
pas une validation artistique : regarder toutes les planches et les détails.

État de livraison et contrôles finaux conservés dans `DELIVERY.json` après
export et revue. Les vidéos et les réponses privées GoFile restent dans
`output/`, ignoré par Git. Ne jamais pousser de jeton ou d’URL de webhook.
