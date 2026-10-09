# Scene Analysis Guy — livraison Discord

L'utilisateur a demandé le9octobre2026 que les vidéos de cette chaîne soient
livrées dans son salon Discord : **un lien GoFile**, titreanglais, description
prête à copier, miniature, chapitres/tags/commentaire si utiles, crédits des
musiques réellement utilisées. Il publie lui-même sur YouTube.

Le webhook dédié est `DISCORD_WEBHOOK_SCENE_ANALYSIS_GUY`, conservé dans les
`.env` privés local et o2switch. **Aucune valeur dansGit. Aucun fallback vers
Cage, Pitch ou le salon générique.** Sur une nouvelle machine, l'importer avec
`python production/server_env.py DISCORD_WEBHOOK_SCENE_ANALYSIS_GUY`.

## Envoi vérifié

```bash
.venv/bin/python experiments/conversation-chess/deliver-discord.py \
  output/conversation-chess/discord/<livraison>/delivery.json --dry-run
.venv/bin/python experiments/conversation-chess/deliver-discord.py \
  output/conversation-chess/discord/<livraison>/delivery.json
```

Le manifest privé contient :

```json
{
  "kind": "final",
  "video": "../../video.mp4",
  "review": "../../check/technical-qa.json",
  "upload_receipt": "../../gofile-receipt.json",
  "gofile_url": "https://gofile.io/d/IDENTIFIANT",
  "title": "English title chosen for this finished video",
  "description": "description.txt",
  "music_credits": "../../MUSIC_CREDITS.txt",
  "thumbnail": "miniature.png",
  "tags": ["The Sopranos", "conversation analysis"]
}
```

Les chemins sont relatifs au manifest. `description.txt` contient la description
de **la vidéo**, pas la bio de la chaîne. Les crédits sont ajoutés automatiquement
à la description et fournis séparément. `chapters` (liste de lignes) et
`pinned_comment` sont facultatifs. Le titre/miniature du long viennent après
le montage ; ne pas présenter des propositions comme décisions approuvées.

L'envoi contrôle le SHA256 du MP4 contre la revue et le reçu d'upload GoFile,
la taille réellement uploadée, le décodageA/V et la revue visuelle. Le reçu
d'upload contient `url` et `files:[{sha256,bytes,...}]`. La revue contient
`sha256`, `full_video_audio_decode_ok`, `finished_render_visual_reviewed` et,
pour une livraison finale, `source_quality.accepted_for_final:true`.
Une finale requiert sa miniature. Un aperçu est marqué explicitement
**APERÇU — pas destiné à publication** et n'utilise pas une photo de profil
comme fausse miniature définitive.

Un seul message comprend les informations et `Kit_publication.txt`,
`MUSIC_CREDITS.txt`, plus la miniature pour une finale. `allowed_mentions` est
vide. La réponse `wait=true` doit confirmer l'identifiant et les pièces jointes.
Le reçu local empêche de renvoyer un paquet identique dans le même salon.
Un envoi incertain conserve `discord_pending.json` : ne pas relancer à l'aveugle.
Le verrou partagé `work/discord.lock` évite les envois concurrents mélangés.

## Premier long livré

Tony/Richie, 15 min 11, est terminé et livré :
[film et kit GoFile](https://gofile.io/d/mdNDwQQ4).
Huit fichiers vérifiés, puis message du salon dédié confirmé avec
`Kit_publication.txt`, `MUSIC_CREDITS.txt` et `thumbnail.png`.
Les reçus sont privés dans
`output/conversation-chess/tony-richie-long-native/publication/`.
Titre et miniature restent des propositions ; publication YouTube manuelle.
Contrôles réellement effectués et limites : [fiche de livraison](TONY_RICHIE_DELIVERY.md).

## Historique — première livraison réelle

L'aperçu `outro-v5-clean` a été envoyé et confirmé : kittexte et crédits joints,
lien du dossier GoFile déjà vérifié. Il ne représente que l'outro12secondes,
avec les cinq notes du test Tony/Janice ; **le long Tony/Richie reste en
préparation**. Son titre et sa description portent explicitement cette limite.
Le manifest et le reçu restent dans
`output/conversation-chess/discord/outro-v5-clean/` (ignoré parGit).

Cette livraison n'active aucune publication YouTube et ne modifie pas les
automatisations Cage/Pitch/TikTok. Aucun processus permanent n'est lancé.
