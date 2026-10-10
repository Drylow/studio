# Reprendre le projet anime après un changement de compte

État enregistré le 10 octobre 2026. Lire ce fichier avant de reprendre ;
il synthétise les choix de cette conversation, sans nécessiter son historique.

## Instruction à donner au nouveau chat

> Ouvre le projet local `C:/Users/ytbyt/Documents/ChatGPT/2D Slop`.
> Lis `CLAUDE.md`, puis `experiments/conversation-chess/REPRISE_ANIME.md`.
> Continue le projet de chaîne anime avec l'outil conversation-chess du collègue.
> Préserve les modifications présentes et les exports précédents.
> La dernière vidéo est la V7 Lelouch–Schneizel ; les propositions de logo
> restent à choisir. Ne relance pas de rendu avant une nouvelle demande.

## Projet et intention

- Dépôt : https://github.com/Drylow/studio.
- Outil retenu : `experiments/conversation-chess/`, moteur graphique du collègue
  et montage natif Kdenlive/MLT, six pistes séparées. Ne pas le remplacer par
  un nouvel outil et ne pas modifier le frontend du studio pour produire la vidéo.
- Référence : https://www.youtube.com/@analysedlikechess/videos.
- Chaîne anime : stratégie, conversations, manipulations et outplays analysés
  comme des coups d'échecs. Les noms Anime Checkmate / Animes Checkmate ont été
  discutés ; l'orthographe finale n'est pas confirmée dans les éléments conservés.
- Ne pas confondre avec la chaîne Scene Analysis Guy documentée ailleurs
  dans `channel-profile/`, ni reprendre son avatar Tony pour l'anime.
- Réponses en français, courtes et directes. Titres et commentaires anglais.
- Utiliser des formats existants prouvés, adaptés aux séries, pour les prochaines
  propositions de chaînes et vidéos. Nexlev et Algrow sont les outils demandés.

## Vidéo actuelle : Lelouch contre Schneizel

**Dernier titre demandé :**

`Chess Analysis - Code Geass | Lelouch VS Schneizel`

Description courte proposée, pas une validation définitive :

`Schneizel thought he understood the game. Lelouch had already changed the rules. Their final confrontation, analysed one move at a time. ♟️`

Export actuel sur ce PC, relatif à la racine du projet :

`work/conversation-chess/lelouch-full-v7/kdenlive/APERCU-LELOUCH-SCHNEIZEL.mp4`

- 255 secondes / 4 min 15, 7 650 images, export 1920 × 1080 à 30 fps.
- Taille : 122 831 308 octets.
- SHA256 : `a31200b5d1abf82c46e7dd3dcc9d4fe882210c6369dd6f0ee6979b6420a1f340`.
- Le même dossier contient le projet `project.kdenlive`, ses médias, les
  manifestes, le job d'export natif et `MUSIC_CREDITS.txt`. Garder le bundle entier.
- Source : `work/chess-studio/schneizel/lelouch-vs-schneizel-english-720.mp4`.
- Source réellement 1280 × 720, dub anglais. Le fichier 1080p n'en améliore pas
  le détail. `source_quality.accepted_for_final` reste faux : ne pas prétendre
  qu'une source HD finale a été acquise. Nouvelle source = revoir les temps et le hash.
- Timeline : `episodes/lelouch-vs-schneizel.json`.
- Guide 16 s, source complète 0–192 s, cinq analyses de 7 s, bilan natif 12 s.
- Pas de voix off. Dialogues et musique du clip conservés.
- Sneaky Snitch rétabli comme V2, uniquement au guide. Pas de musique ajoutée
  aux analyses et au bilan. Pas de crédit à l'écran ; l'attribution du morceau
  doit accompagner la description publiée, depuis `MUSIC_CREDITS.txt`.
- Le mot « opinion » finit avant la pause : premier repère source 15,45 s,
  avec 0,61 s après la fin du mot.
- Lelouch est blanc, Schneizel noir. V7 : deux analyses noires puis trois
  blanches, via `analysis_pawn_by_speaker: true`. Le bilan conserve le pion
  commentateur neutre. Aucun portrait Tony en haut à droite.
- V7 : le bandeau jaune « SOURCE QUALITY PREVIEW » est retiré avec
  `show_source_quality_label: false`. Il venait de notre overlay, pas de la source.
- Subscribe rejeté. Fin de scène : fondu image/son 0,5 s, puis bilan natif
  et fondu final. Pas de carton Subscribe.
- QA achevée : décodage complet sans erreur, 39 planches couvrant toutes les
  images et captures natives examinées. Rapport : `VALIDATION_ANIME_CLEAN_OVERLAYS.md`.
  Preuves locales dans `work/conversation-chess/lelouch-full-v7/review/`.
- Les corrections V7 sont publiées dans main, commit `8299049`.

Commande pour un futur nouvel export, à lancer uniquement si demandé :

```powershell
powershell -ExecutionPolicy Bypass -File experiments/conversation-chess/chess.ps1 -Mode Render -Preview -Source work/chess-studio/schneizel/lelouch-vs-schneizel-english-720.mp4 -Timeline experiments/conversation-chess/episodes/lelouch-vs-schneizel.json -Out work/conversation-chess/lelouch-full-new
```

Lire aussi `ANIME_WORKFLOW.md`, `WINDOWS.md` et `SOURCE_IMPORT.md`.
Certains documents historiques contiennent des choix dépassés : cet état et
les dernières demandes utilisateur priment.

## Miniature retenue et logo encore en discussion

- Miniature : variante B choisie. Version corrigée avec les vrais SVG Chess.com
  et badges inclinés : `thumbnails/lelouch-schneizel/B-chesscom-tilted.jpg`.
- Le cavalier avec œil violet a été rejeté.
- Un personnage anime original tenant un roi près du visage avait été demandé ;
  fichiers préservés dans `branding/original-mascot-2026-10-09/`.
- L'utilisateur cherche ensuite un logo centré sur un **pion**, avec éventuellement
  un **crâne**. Il a envoyé un portrait sur corps de pion comme inspiration.
- La première planche de portraits sur pion avec !! et ?? a été rejetée :
  elle recopiait la référence au lieu de proposer une identité originale.
- Dernière planche : `branding/pawn-concepts-2026-10-10/concepts.png`.
  A : regard manga ; B : crâne expressif sur pion incliné ; C : pion avec encre
  manga ; D : crâne intégré à une silhouette simple. Aucun choix utilisateur
  après cette planche. Ne pas présenter une proposition comme approuvée.

## Suite envisagée

- Ayanokoji vs Ryuen, Classroom of the Elite : clip anglais propre et réellement
  HD à trouver ; modèle `episodes/ayanokoji-vs-ryuen.empty.json` non rempli.
- Attack on Titan et autres anime, puis Game of Thrones quand le format sera prêt.
- Aucun temps ni événement à inventer pour les sources non acquises.
- Pas de watermarks ou textes de distributeur : Fandango Clips explicitement rejeté.
- Pas de publication YouTube ou envoi Discord autorisé pour cette chaîne ici.

## Où se trouve la sauvegarde

GitHub contient le code, les timelines, les assets suivis, la miniature, la
dernière planche de logos et ce fichier de reprise. Les vidéos et sources lourdes
du dossier `work/` sont locales et ignorées par Git : elles ne sont pas dans GitHub.
Un changement de compte ne change pas leur emplacement sur ce PC.

Une copie privée locale de l'historique de cette conversation est conservée dans
`work/chess-studio/account-backup/historique-anime-chess.jsonl`.
Elle n'est pas publiée dans GitHub : l'historique brut inclut des sorties d'outils
et des informations locales. Ce fichier de reprise est le support à partager
avec le prochain chat, pas une migration automatique de la conversation.

Les accès aux outils et identifiants dépendront du nouveau compte ; les secrets
restent dans la configuration privée. Ne jamais les inclure dans un commit.
Préserver les autres travaux locaux non liés à l'anime. Publier les changements
de ce projet sur la branche de session et sur main via un checkout propre.


## Deuxième anime choisi le 11 octobre 2026

L'utilisateur a choisi **L Outsmarts Light Analysed like Chess | Death Note**.
Production documentée dans `DEATH_NOTE.md`, timeline `episodes/light-vs-l.json`.
L blanc, Light noir ; Lind L. Tailor est le représentant du piège de L.
Sources anglaises 1080p déjà remasterisées en amont, pas un master studio brut.
Sept analyses écrites à la main, guide Sneaky Snitch, bilan natif sans Subscribe.
État précis de l'export et de sa QA dans la fiche de production ; ne pas
confondre une timeline validée avec une vidéo déjà vérifiée.
