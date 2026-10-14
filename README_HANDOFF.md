# Reprise complète des productions — 14 octobre 2026

Ce document est le point d'entrée de cette passation demandée par l'utilisateur.
Il conserve les sources disponibles, les décisions, les méthodes et les derniers
films livrés. Les autres productions des collègues, récupérées sur `main`, restent
intactes. Une reprise du dépôt ne lance aucun ancien job ni aucune publication.

## Lire dans cet ordre

1. [AGENTS.md](AGENTS.md) et [CLAUDE.md](CLAUDE.md) pour les règles générales.
2. [Les chaînes et leurs décisions](production/handoff/CHANNELS.md).
3. [Continuité et épisodes suivants](production/handoff/CONTINUITY.md), en particulier
   le véritable premier épisode alien de **One Stick Left**.
4. [Outils et production](production/handoff/TOOLS.md), puis
   [les commandes de finition](production/history_delivery/README.md).
5. [Publication et Fury](production/handoff/POSTING_HANDOFF.md) avant toute automatisation.
6. [Accès personnels chiffrés](production/handoff/access/README.md).

Les anciennes notes de coupure, les pilotes remplacés et les calendriers datés
restent de l'historique. Les indications « en cours » de ces anciens documents
ne remplacent pas les états vérifiés ci-dessous.

## Sources des vidéos à conserver

| Chaîne | Dossier | Contenu et dernier état |
| --- | --- | --- |
| Samurai Chapters | [Épisode 01](chaines/samurai-chapters/episode-01/README.md) | Script anglais exact, 108 images retenues, maîtres, prompts/corrections, voix et timings, contrôles finaux. Film 19:39 livré ; publication rapportée par l'utilisateur. Miniature choisie : C, **PAID IN RICE?**. |
| Viking Chapters | [Épisode 01](chaines/viking-chapters/episode-01/README.md) | Script exact, 88 images retenues, références et variantes, recherche, narration officielle, horloge finale VPS, quatre miniatures et contrôles. Film 19:26 livré. |
| Pirate Pages | [Épisode 01](chaines/pirate-pages/episode-01/README.md) | Script exact, 85 images retenues, références et états du navire, recherche, narration officielle, horloge finale VPS, quatre miniatures et contrôles. Film 19:45 livré. |
| One Stick Left | [Premier Alien J1–J30](chaines/alien-outbreak-survival/README.md) | Film historique original réellement récupéré, kit et miniature de cette livraison, narration complète transcrite, horloge/SRT et bilan J30 pour préparer J31–J60. Le fichier auteur original n'est pas retrouvé : la transcription est étiquetée comme telle. |
| Scene Analysis Guy | [Studio chess](experiments/conversation-chess/README.md) | Sources éditoriales, timelines, montage natif, pions, règles des Blancs, badges, miniatures et résultats de réclamations documentés. Peaky Blinders abandonné ; ne pas le republier. |
| Autres chaînes | [Registre complet](production/handoff/CHANNELS.md) | OSL, objets, économie, Last Safe Door, autres historiques, news/TikTok et projets des collègues restent distincts. Les lacunes de récupération et d'attribution sont nommées, jamais comblées avec un autre projet. |

**One Stick Left n'est pas Alien Aftermath.** Le premier récit de trente jours
contient Reed **et Mara** et se termine encore à la station-service, devant une
ouverture lumineuse vers une destination inconnue. Le pilote séparé de sept jours
et sa fin à la ferme ne doivent pas servir de continuité pour cette suite.
Lire le [bilan vérifié au jour 30](chaines/alien-outbreak-survival/episode-01-day-01-30/CONTINUITY_DAY30.md)
avant de rédiger la partie 2 ; ne pas réinitialiser les sacs, les stocks,
les marques du terrain, le registre ou les connaissances des personnages.

## Derniers packs de publication

- Samurai : https://gofile.io/d/M9RLsD1P — la révision de miniature choisie est
  conservée dans le dossier Git, pas dans un nouveau GoFile annulé.
- Viking : https://gofile.io/d/Zd5AhFJi — sept fichiers réellement envoyés et
  contrôlés, MP4 `c684fbf2a4f72df556f9fb327705f642abbbaf0c1e03f338625b33db1b5dbb5a`.
- Pirate : https://gofile.io/d/e2AjnCyr — sept fichiers réellement envoyés et
  contrôlés, MP4 `3822680745ba50409ccccd3804985062c6e8d0052c9a6d8c01e2211855c1d8c7`.
- Alien historique : https://gofile.io/d/rtK6vmpj — les trois fichiers ont été
  relus et récupérés pendant cette passation ; cette version ne prouve pas la
  récupération de toutes les corrections visuelles livrées ultérieurement.

Les grands MP4, caches d'encodage, environnements et profils de navigateur ne
sont pas incorporés dans l'historique Git. Leurs liens, hashes et sources utiles
le sont. Les binaires d'images sélectionnées, maîtres, miniatures et les narrations
historiques disponibles restent conservés sans réencodage dans les packs.

## Fabriquer le prochain épisode

Écrire une narration originale et sourcée, puis un découpage explicite avant
de générer. Pour chaque plan : texte exact, action utile, lieu/variante, casting,
état des objets, prompt réellement écrit et références ordonnées. Réutiliser les
maîtres inspectés et comparer les images obtenues avant montage. Pour une suite,
figer son état initial d'après le véritable film précédent.

L'application complète est déjà dans `production/tubeforge_base` et
`production/tubeforge_support`. Le [client officiel](production/tubeforge_support/forge_docs/README.md)
et les contrats de l'API maintenue servent à créer/importer les projets sur
**https://tools.kanye.studio/api/forge/v1**. Les deux derniers films historiques
ont été rendus sur le VPS ; seule la finition du volume a été appliquée ensuite
avec copie exacte du flux vidéo. Leurs archives distinguent le rendu natif brut
et le MP4 sonorisé livré, leurs deux hashes et leurs vraies preuves.

Mesurer la vraie voix et utiliser son horloge, ne pas estimer les timecodes.
Un timeout de POST ne justifie jamais de recommencer une génération payante ou
un rendu : vérifier le véritable état et les fichiers d'abord. Conserver les
limitations de provenance des images récupérées sans reçu certain.

Les [helpers portables](production/history_delivery/README.md) réalisent la
normalisation, le remux sans réencodage vidéo, le décodage audiovisuel complet,
les contrôles de voix, les captures de scènes/raccords et la livraison GoFile.
Ils ne remplacent pas une inspection visuelle réelle et ne fabriquent pas une
approbation humaine. Préparer quatre miniatures réellement différentes dans
la famille approuvée et conserver le titre/description/SRT du bon épisode.

## Automatiser la publication ensuite

L'utilisateur veut étudier Fury avec le collègue après ces livraisons. Le dépôt
contient des travaux Fury d'une autre session, mais aucune correspondance
vérifiée entre leurs profils et les nouvelles chaînes de cette conversation.
Relever le vrai profil, le `UC…`, l'opérateur, le calendrier et l'accès effectif
avant de publier. Une chaîne locale TubeForge, un @ proposé et une livraison
GoFile ne sont pas des preuves de connexion à YouTube.

Les automatisations news et TikTok existantes sont séparées et leurs derniers
calendriers documentés sont des snapshots datés. Ne pas les relancer ni les
modifier en reprenant ce dossier. La chaîne sleep abandonnée ne doit pas repartir.

## Accès et données privées

Les **cinq pièces d'accès originales** fournies par l'utilisateur sont conservées
byte pour byte dans le [coffre AES-256-GCM](production/handoff/access/README.md).
Le dépôt public ne contient ni clé SSH en clair, ni clé personnelle API, ni cookie.
La clé d'ouverture est séparée ; consulter le statut effectif de son stockage
privé dans le guide du coffre avant de lancer un mode de récupération automatique.
Les identifiants cPanel restent dans les paramètres privés déjà autorisés.

Ce push ne déploie aucun serveur et ne publie aucune vidéo. Les nouveaux outils
et archives complètent les sources existantes sans modifier le frontend ou la
configuration des services en cours.
