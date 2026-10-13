# Eren contre Reiner — confrontation de Liberio

Titre : **Chess Analysis - Attack on Titan | Eren VS Reiner**.
Vidéo longue horizontale, doublage anglais, sans voiceover. Le montage conserve
la menace dans la cave, les questions sur le mur et la mère d'Eren, la mission
invoquée par Reiner, sa confession, la poignée de main et la transformation.

Eren parle le premier dans le passage sélectionné : blanc. Reiner : noir.
Falco et Willy restent des interlocuteurs de contexte, sans troisième camp.
Les notes décrivent l'initiative et la négociation ; elles ne proviennent pas
d'un moteur d'échecs et ne constituent pas une approbation morale des actions.

## Sources et choix utilisateur

Quatre fichiers distincts acquis en 1920 × 1080 :

- [Reunion, UnFazedReactionz](https://www.youtube.com/watch?v=8HkZD0yI2qM) :
  16,7667–30,60 s puis 87,30–127,50 s. Les commandes de lecteur du début sont
  hors sélection. Le contrôle de chaque image de V1 a révélé un petit indicateur
  de chargement et un pointeur dans la menace : ce passage enregistré entier
  est retiré. De petites bordures et une inscription de diffusion partielle
  restent dans les deux plages conservées.
- [Menace dans la cave, Otaku Gaming](https://www.youtube.com/watch?v=CyFUlxiWbcM) :
  1,40–58,05 s. Cette acquisition indépendante remplace la menace enregistrée,
  jusqu'à la réponse complète de Reiner. La réponse « Okay » de Falco reprend
  dans la plage suivante du premier fichier, sans répétition de dialogue.
- [Questions et justification, Otaku Gaming](https://www.youtube.com/watch?v=BXr5Av_2MVo) :
  0–121,20 s. Le passage se termine après « training » ; la phrase suivante
  se poursuit dans le quatrième fichier, sans doublon.
- [Confession et transformation, Anime Kickstart](https://www.youtube.com/watch?v=vO3K-W7PLlI) :
  0–60 s puis 96,60–160,80 s. Une partie du discours hors scène est retirée
  entre la demande de Reiner et la réponse d'Eren. La déclaration finale reste.
  Le carton « To be continued » n'est pas inclus.

Les autres candidats sont conservés dans le travail privé. Certains comportent
des sous-titres, des marques supplémentaires ou une langue différente.
Le téléchargement MCP Algrow a échoué ; l'acquisition locale a fonctionné.

**Décision explicite du 13 octobre 2026 :** chercher une copie sans logo ; à
défaut, l'utilisateur autorise à conserver le logo Adult Swim. Ce logo reste
dans cette édition. Aucun floutage, suppression de logo ou reconstruction de
détail. Ce sont des copies de diffusion compressées, pas des masters bruts.

## Montage

Outil du collègue conservé, sans modification du frontend : moteur Canvas,
préparation des médias séparés et export natif Kdenlive/MLT. Sept pauses de
sept secondes ; texte anglais écrit manuellement, replay muet de trois secondes,
au moins 2,5 secondes de lecture après la frappe. Pion blanc/noir selon le camp.

Guide de 16 s avec Sneaky Snitch, selon le choix V2. Aucun ajout de musique sur
la scène, les analyses ou le bilan. Audio et musique de l'anime conservés.
Fin de scène par fondu de 0,5 s ; bilan natif de 12 s, sans Subscribe ni Tony.
Great conserve score et barre. Le bilan compte trois Brilliant, un Great,
deux Book et un Blunder. Le rendu final dure 7 min 13,1 s (12 993 images à 30 fps).

Description courte :

> Eren and Reiner's basement confrontation, analysed move by move like chess.

Les crédits nécessaires de Sneaky Snitch doivent accompagner la description ;
aucun crédit à l'écran. Conserver le fichier MUSIC_CREDITS.txt du projet.

## Fichiers

- Timeline : `episodes/eren-vs-reiner.json`.
- Miniatures : `thumbnails/eren-reiner/`, version A anime recommandée,
  version B manga comme alternative. SVG Chess.com vérifiés et inclinés ±10°.
- Sources privées : `work/chess-studio/attack-on-titan/sources/`.
- Rendu final et projet transportable : `work/conversation-chess/eren-reiner-v2/`.
  V1 est conservée comme archive de contrôle, pas comme livraison.
- Livraison : `outputs/chess-eren-reiner-2026-10-13/`.

La timeline V2 sélectionnée est alignée localement sur son audio réel. Les
transcriptions intégrales et les médias de série restent privés dans `work/`.
Ne pas les ajouter au dépôt public. Aucune publication ou envoi externe.

## Refaire l'export

```powershell
./experiments/conversation-chess/chess.ps1 -Mode Render `
  -Source work/chess-studio/attack-on-titan/sources/eren-reiner-selected-v2-1080.mp4 `
  -Timeline experiments/conversation-chess/episodes/eren-vs-reiner.json `
  -Out work/conversation-chess/eren-reiner-v2
```

Ne pas remplacer un export existant. Le projet Kdenlive doit rester avec son
dossier `media/`. La finition sonore vient après le rendu : compression légère
et relèvement maximal de 4 dB sur les seules plages de scène, puis limitation
des pointes. Le PCM du guide, des analyses et du bilan reste identique avant
réencodage AAC. Le flux vidéo est copié et son empreinte comparée.
Exécuteur sauvegardé : `episodes/eren-vs-reiner-finish-audio.py`.

```powershell
python experiments/conversation-chess/episodes/eren-vs-reiner-finish-audio.py --bundle work/conversation-chess/eren-reiner-v2/kdenlive
```

Le fichier final existant est protégé contre l'écrasement. Une modification
manuelle du montage exige de mettre à jour les plages de scène du manifeste
avant cette finition.

## Contrôle de la livraison V2

Décodage intégral réussi. Les 12 993 images ont été examinées sur 65 planches
sans saut d'image, puis 38 captures de contrôle en sept groupes ; les cadres
clés ont aussi été ouverts en 1920 × 1080. Textes complets, camps cohérents,
bilan de sept coups correct, aucun Subscribe ou carton de qualité ajouté.
Temps de lecture après frappe : 2,84 à 3,42 s, sons de frappe terminés.
Le flux image de la livraison est identique au rendu natif vérifié.

Finition sonore mesurée : −19 LUFS intégrés, pic réel −1,9 dBFS.
La copie livrée porte l'empreinte SHA-256
`ed652b917666451e39bd96ab5a6ba7dd1f654f2599d48e61d61e424689820844`.
Les 51 ressources du projet éditable sont présentes et vérifiées après copie.
Reçu : `episodes/eren-vs-reiner.qa.json`. Aucune vérification ou publication
sur YouTube n'a été effectuée ; ce contrôle concerne le montage local.
