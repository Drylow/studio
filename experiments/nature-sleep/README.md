# Petits mondes naturels — propositions de branding

Concept choisi par l’utilisateur le 11 octobre 2026 : récits longs pour dormir
destinés aux adultes, autour de mousse, jardins, serres et petits bassins.
L’objectif reste deux heures. Nom, bio et avatar sont déjà livrés sur Discord.

Le 11 octobre 2026, l’utilisateur rejette l’aperçu botanique C et demande
une nouvelle DA **pixel art cozy, chill, couleurs pastel**. Il aime explicitement
le nouveau décor de cottage/serre/mare, puis demande beaucoup plus d’animation
et de détails. **Image fixe approuvée ; animation encore à valider.**

Nouvel aperçu révisé : **https://gofile.io/d/rGAUzFXX**, `Quiet-Little-Worlds-Living-Cottage-24s.mp4`,
24 s, 1080p30, 720 images, sans son, 8378235 octets. SHA-256 :
`332485ac7f819fcb1dbfa52e506b8e85ee1197f9dd6a5829a55517616c973d6f`.
L’utilisateur a demandé de corriger le saule du premier aperçu pixel, qui
bougeait par bandes, et d’ajouter une petite grenouille. Le pixel art concerne
le dessin ; les mouvements doivent rester fluides. Nouveau rendu directement
en 1080p, fond propre et calque de saule transparent animé séparément : le ciel
reste fixe. Grenouille avec respiration, clignement, petits sauts et repos sur
la pierre. Reflets, pluie, lucioles et papillon conservés. Caméra fixe.
Sources générées 1672×941 ; aucun master natif 4K revendiqué.
Décodage complet passé ; cinq planches/73 captures et trois vues natives revues ;
upload confirmé par taille/MD5. Pas de visionnage continu prétendu.
Cycle natif exact, sans garantie de raccord MP4 imperceptible.
Code : `experiments/nature-sleep/pixel-cozy/render-smooth.mjs` ;
reçu : `experiments/nature-sleep/pixel-cozy/SMOOTH_DELIVERY.json`.
Les premiers essais restent en archives ; l’aperçu botanique C est rejeté.
**Avis utilisateur attendu avant de commencer le long.** Aucun aperçu Discord,
script intégral, voix ou film de deux heures lancé.

Montage proposé : quatre à six vues liées au récit, transitions lentes,
ambiance sonore adaptée et sous-titres activables ; essai de texte central
sobre possible. Comparer deux courts essais de voix après l’animation.
Ces ajouts ne garantissent pas la monétisation. Règles officielles YouTube
consultées : https://support.google.com/youtube/answer/1311392?hl=en .
Voir `experiments/nature-sleep/pixel-cozy/EDITING_AND_VOICE.md`.

L’utilisateur demande une explication précise du format de deux heures.
**Proposition à discuter, non validée :** histoires originales en anglais pour
adultes, imaginaires et apaisantes, dans de petits refuges naturels. Exemple :
une nuit de pluie dans le cottage. Narration évolutive pendant près de deux
heures et fond animé en boucle ; ne pas répéter le récit pour remplir la durée.
Les faits naturels présentés comme réels seront vérifiés. Voir
`experiments/nature-sleep/pixel-cozy/CHANNEL_FORMAT_PROPOSAL.md`.
Ne pas présenter la fiction comme un choix utilisateur déjà confirmé.

## Anciennes propositions — archives

- **A — jardin nocturne cinématographique** : feuillage détaillé, mare,
  profondeur et lumière lunaire. Le prompt demandait de la peinture, mais
  le résultat paraît proche du réalisme ; ne pas le décrire comme une gouache.
- **B — macro réaliste** : mare vue au ras du sol, profondeur de champ,
  feuillages humides, grenouille et escargot. Image générée, pas une photo réelle.
- **C — illustration botanique douce** : contours fins, textures aquarellées,
  palette du crépuscule et vie discrète. Première proposition recommandée.

Les trois scènes sont originales et indépendantes des anciens décors marins
rejetés. C est choisi pour l’aperçu par délégation de l’utilisateur ; aucune
validation visuelle explicite de cette image n’est enregistrée. Le nombre de pixels
mesuré dans le manifeste est la résolution réelle ; aucun master natif 4K.
Les détails figurés ne servent pas de preuve biologique ou de prise de vue.

## Avatar proposé

[Avatar fougère, lune et luciole](branding/avatar-fern-moon.png), sans texte,
fond opaque, composition centrale destinée au recadrage circulaire YouTube.
Il ne reprend pas l’ancien avatar méduse. Son envoi a été demandé par
l’utilisateur, qui confirme le nom, la bio et l’image reçus dans Discord.

## Nom choisi et autres pistes

1. **Quiet Little Worlds — @QuietLittleWorlds**, nom choisi explicitement.
2. **Glowfern Stories — @GlowfernStories**.
3. **Little Wilds Sleep — @LittleWildsSleep**.

Recherche de collisions dans les index publics : aucun homonyme exact repéré
dans les réponses exploitables, avec des contrôles limités pour les deux
derniers noms. **Aucun @ confirmé disponible ou réservé.** Certaines recherches
ont été élargies par le moteur ou limitées. Le choix ne vaut pas confirmation
de disponibilité ; celle-ci se vérifie dans YouTube lors de la création.
Voir [recherche de noms](NAME_RESEARCH.md) et [résumé](name-research.json).

## Bio proposée

> Slow stories. Small worlds. Deep rest.
>
> Gentle bedtime stories for adults, inspired by moss gardens, moonlit ponds,
> quiet greenhouses, and the hidden wonders of nature.
>
> Settle into peaceful little worlds with soothing narration, soft natural
> ambience, and calm visuals.
>
> Take a breath. Let the world grow quiet.

Dans chaque futur épisode, distinguer histoire naturelle documentée et
promenade imaginaire. Vérifier les faits annoncés comme réels. La bio définit
le thème de la chaîne sans prétendre que des épisodes sont déjà publiés.

## Ancien aperçu C — rejeté par l’utilisateur

Créer un aperçu court uniquement du style choisi : reflets légers, feuillage
discret, lucioles lentes et, éventuellement, une dérive de caméra imperceptible.
Éviter flashes, mouvements brusques et variations de volume. Utiliser le
décor choisi comme référence puis contrôler les images du film effectivement
exporté et le raccord avant de le montrer. Aucun appel Algrow ni génération
vidéo nécessaire ; la préparation des mouvements peut être codée.

[Aperçu C — 24 secondes, 1080p30, sans son](https://gofile.io/d/VOaYXcYo) :
eau, feuillage et petites lucioles très discrètement animés, cadrage fixe.
Les 720 images ont été décodées sans erreur ; captures du film revues par
l’auteur, un examinateur indépendant et le root. Le raccord du shader est
exact ; celui du MP4 conserve les différences de compression. Aucune lecture
continue revendiquée. L’utilisateur a depuis rejeté cet aperçu. Voir
[preuve de livraison](PREVIEW_DELIVERY.json) et [moteur](animation/README.md).
Le nom est choisi et le kit de branding est livré dans
Discord, confirmé par l’utilisateur. Aucun film de deux heures ni voix lancé.
Voir BRANDING_DELIVERY.json : le contrôle API des pièces jointes a échoué,
mais l’utilisateur confirme les trois éléments reçus ; aucun doublon envoyé.
Le webhook dédié est enregistré dans les .env privés local et serveur,
sans clé dans le dépôt. Aucun compte YouTube créé ou renommé.

## Projet chess indépendant

Tommy/Alfie a été livré, puis publié et supprimé par l’utilisateur après
une réclamation audiovisuelle et un blocage dans certains pays. La publication
est désormais bloquée ; la QA technique ne démontrait pas les droits sur les
épisodes. Voir [protocole de droits et contrôles](../conversation-chess/COPYRIGHT_RELEASE.md).
La scène du strudel Landa/Shosanna dans *Inglourious
Basterds* est une piste retenue pour la prochaine reprise, pas une production
lancée. Attendre la demande de reprise de l’utilisateur. Titres : inclure
**Analyzed Like Chess**, avec un z. Ne pas affirmer que Landa reconnaît
Shosanna : le film entretient cette incertitude, qui participe à la tension.
