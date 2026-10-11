# Livrer un montage natif contrôlé sur GoFile

`upload-reviewed-gofile.py` valide les fichiers localement par défaut. L’option
`--upload` est nécessaire pour créer un dossier invité via l’API normale GoFile.
Le helper envoie exactement cinq fichiers : film, miniature unique, propositions
de titres, description complète et crédits musicaux. Il n’envoie rien sur YouTube
ou Discord.

Exemple de `delivery.json`, dans un dossier ignoré par Git :

```json
{
  "kind": "youtube-test",
  "video": "Film.mp4",
  "thumbnail": "thumbnail.jpg",
  "titles": "Titles.txt",
  "title": "A reviewed title — analyzed like chess",
  "description": "description.txt",
  "music_credits": "MUSIC_CREDITS.txt",
  "review": "../qa/delivery-review.json",
  "technical_review": "../qa/audio-technical-qa.json",
  "prepared_manifest": "../prepared/project-manifest.json",
  "native_receipt": "../kdenlive/bundle-manifest.json"
}
```

Tous les chemins sont locaux et relatifs au fichier qui les contient ; les
chemins absolus sont également acceptés. `description.txt` contient seulement le
texte de présentation. Le helper génère `description_with_credits.txt`, avec les
éventuelles lignes du tableau `chapters` et les crédits, comme `deliver-discord.py`.
Le total ne doit pas dépasser 5 000 caractères. Les crédits doivent correspondre
exactement à l’attribution de la préparation et du bundle natif, sans imposer un
nombre de morceaux. Un projet sans musique ajoutée doit conserver un fichier
de crédits expliquant ce choix et ne pas contenir de piste musicale non créditée.

```bash
.venv/bin/python experiments/conversation-chess/upload-reviewed-gofile.py \
  --manifest output/conversation-chess/film/publication/delivery.json --dry-run
```

Le film doit correspondre aux empreintes de la revue technique et visuelle.
Le décodage complet doit avoir réellement réussi, avec son journal conservé et
vide. L’export natif doit être terminé. Le helper relit les profils réels, les
empreintes de la source et de la timeline, ainsi que les images de preuve.
Il ne transforme jamais une sortie 1080p en preuve que la source était 1080p.

La revue visuelle conserve des chemins explicites vers les images examinées :

```json
{
  "sampled_visual_review": {
    "completed": true,
    "reviewed_images": 12,
    "method": "Description précise des images effectivement examinées.",
    "evidence_files": ["contacts/intro-00.jpg", "contacts/analyses-00.jpg"]
  }
}
```

Les feuilles contact peuvent contenir plusieurs images ; le nombre d’images
examinées est déclaré par le réviseur. La présence des fichiers ne remplace pas
son examen. Aucun helper n’accorde automatiquement la revue visuelle ni une
écoute humaine.

`preview` conserve l’état de qualité de la source, même lorsqu’elle n’est pas
acceptée. `youtube-test` et `final` exigent une qualité acceptée dans la
préparation, le bundle natif et les deux revues. `youtube-test` est destiné au
contrôle privé YouTube : aucune exemption de réclamation n’est affirmée.
`final` exige aussi `publication_review`, avec preuves de droits et de contrôles
YouTube identiques à celles exigées par `deliver-discord.py`.

## Finition audio après le montage natif

Si le film livré est une finition audio de l’export natif, ajouter au manifeste
`"audio_finishing_receipt": "Film.audio.json"`. Le bundle natif conserve son
fichier et son SHA originaux. Le reçu de `finish-dialogue-audio.py` identifie le
parent, le résultat, les plages de dialogue et le gain. Le gain est évalué à
chaque échantillon, avec des intervalles semi-ouverts : le début d’une analyse
ne reçoit jamais le gain de la scène précédente. La revue technique finale
se crée avec :

```bash
.venv/bin/python experiments/conversation-chess/check-native-export.py \
  --file /chemin/Film.mp4 --manifest /chemin/prepared/project-manifest.json \
  --bundle-manifest /chemin/kdenlive/bundle-manifest.json \
  --audio-finishing-receipt /chemin/Film.audio.json --out /chemin/qa
```

Le checker recalcule les empreintes des deux films et de leurs flux image,
vérifie les plages exactes de la préparation, puis compare l’audio final au PCM
préparé avec le gain déclaré uniquement pendant les scènes source. Le guide,
les analyses et le bilan gardent leurs niveaux attendus. Les comparaisons
examinent des fenêtres de chaque segment, les attaques de grade et les pauses
de lecture complètes ; elles ne constituent pas une écoute continue ni une
comparaison de chaque échantillon du film final. La provenance est
conservée dans le rapport technique et dans le plan des captures.

## Confirmation et reprise

Après validation locale, la même commande avec `--upload` sélectionne un serveur
GoFile officiel. Avant tout POST, elle écrit `gofile-pending.json`. Chaque
réponse d’envoi doit confirmer MD5 et taille. La lecture du dossier doit ensuite
confirmer les cinq noms, identifiants, MD5 et tailles avant la création de
`gofile-receipt.json` et l’ajout du lien dans `delivery.json`.

Le GET direct `/contents/<id>` est réservé aux comptes Premium dans l’API
[officielle GoFile](https://gofile.io/api). Une réponse `error-notPremium`, même
avec HTTP 401, ne prouve pas que les POST ont échoué ou que le jeton est invalide.
Elle laisse l’opération en attente de confirmation ; ne pas refaire l’upload.

Pour un dossier déjà envoyé, ouvrir son URL publique avec le site officiel
GoFile dans un navigateur normal. Conserver la capture de la liste et le reçu
JSON de cette lecture réelle, avec les cinq fichiers et la réponse complète.
Le helper peut alors les réconcilier avec les POST et les fichiers locaux :

```bash
.venv/bin/python experiments/conversation-chess/upload-reviewed-gofile.py \
  --manifest output/conversation-chess/film/publication/delivery.json \
  --verify-existing-web output/conversation-chess/film/publication/gofile-web-verification/public-browser-readback.json
```

`--verify-existing-web` est exclusif de `--upload` et `--dry-run`. Cette opération
est hors réseau et n’envoie aucun fichier. Elle refait les contrôles locaux,
exige les cinq réponses POST réussies, puis compare l’URL et l’identifiant du
dossier, les noms et identifiants des fichiers, les tailles et MD5. Elle vérifie
aussi la liste complète sans pagination omise, les preuves HTTP 200 et
l’empreinte de la capture. Une simple image, un lien ou une liste saisie à la
main ne remplace pas la preuve de lecture du site officiel.

Le reçu distingue cette méthode : `official_web_client_readback_complete: true`,
`api_readback_complete: false` et `direct_premium_api_readback_complete: false`.
Chaque fichier porte `official_web_client_readback_matched: true`. Le JSON et
la capture sont liés par leur SHA au reçu. Aucun succès de l’API Premium n’est
ainsi affirmé. Le navigateur conserve son fonctionnement officiel : ne pas
fabriquer ni rejouer ses en-têtes internes pour imiter un autre accès.

Le pending devient `gofile-pending-confirmed.json` seulement après écriture du
reçu, liaison au manifeste et dernier contrôle des empreintes. Si un fichier
change entre ces étapes, la liaison échoue et l’état pending est conservé.

Ce mode a été exécuté avec succès pour le kit Landa long du 11 octobre 2026 :
cinq fichiers confirmés, reçu lié au manifeste et pending archivé après le
refus Premium de la lecture API directe. La livraison Discord a ensuite son
propre reçu. Cet essai vérifie le transport ; il ne vaut pas contrôle YouTube.

Le jeton propriétaire reste dans `gofile-owner-private.json`, permissions 600,
dans un chemin ignoré par Git. Il n’est affiché ni dans la console ni dans le
reçu public. Le proxy et la confiance TLS de l’environnement sont conservés.

Un reçu identique évite un nouvel envoi. Une opération interrompue, une réponse
incertaine, des fichiers modifiés ou une discordance de lecture arrêtent le
helper et conservent l’état pending : inspecter le dossier distant et les preuves
avant toute décision de reprise, sans supprimer aveuglément cet état.

Le manifeste confirmé est ensuite consommable par `deliver-discord.py`. L’envoi
Discord reste une action séparée, avec son propre reçu et sa propre protection
contre les doublons.

## Limiter les copies de travail

`export-kdenlive.py --hardlink-media` est facultatif. Sur le même système de
fichiers, les médias préparés stables et leurs chemins dans le bundle partagent
les mêmes octets ; sur un autre système, l’export fait une copie vérifiée.
Chaque chemin du bundle reste autonome après suppression du chemin de travail.
Modifier les octets d’un média lié affecte les deux chemins : réserver cette
option aux médias figés et préparer un nouveau bundle pour changer le montage.
Sans cette option, le comportement reste une copie indépendante. Les projets,
sources, vidéos finales et preuves de contrôle doivent être conservés.
