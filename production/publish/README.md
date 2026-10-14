# Publication des chaînes de l'utilisateur (Fury et AdsPower, sur son PC)

Le Claude du PC publie avec la compétence `/publier` (`.claude/skills/publier/SKILL.md`).
Le Claude du cloud prépare les vidéos et dépose une fiche par vidéo dans `queue/`.

- `channels.json` : les 6 chaînes, leur application (Fury ou AdsPower) et leur profil.
- `queue/<chaîne>--<vidéo>.json` : une vidéo prête à publier.
- `log.jsonl` : une ligne par vidéo réellement envoyée. Elle contient : chaîne, titre, SHA-256,
  `video_id`, visibilité, date et état des droits.

## Fiche d'une vidéo

```json
{
  "channel": "Viking Chapters",
  "title": "Why Being a Viking Was Worse Than You Think",
  "description_file": "chaines/viking-chapters/episode-01/delivery/UPLOAD.txt",
  "video": {"gofile": "https://gofile.io/d/…", "file": "nom.mp4", "sha256": "…"},
  "thumbnail": "chemin/vers/miniature.jpg",
  "captions": "chaines/viking-chapters/episode-01/delivery/English-Captions.srt",
  "visibility": "unlisted | private | public | scheduled",
  "publish_at": "2026-10-16T18:00 (heure de Bruxelles, seulement si scheduled)"
}
```

Le PC refuse une fiche dans ces cas :
- `sha256` absent ;
- miniature absente ;
- `channel` qui n'est pas exactement un des 6 noms ;
- `publish_at` déjà passé.

Il passe à 8 h, 11 h, 14 h, 17 h, 20 h et 23 h (heure de Belgique). Une vidéo programmée doit
donc être poussée sur `main` au moins un passage avant son heure. Pour 10 h, il faut la pousser
avant 8 h.

Le PC n'a pas encore d'accès GitHub, donc son journal reste sur le PC (`work/publish/log.jsonl`).
Pour savoir si une vidéo est partie, il faut regarder la chaîne.

## Miniatures

Règle de l'utilisateur (14 oct.) : chaque nouvelle miniature reprend **exactement** la miniature déjà
publiée sur la chaîne (style, mise en page, police, couleur et place du texte), adaptée au nouveau
titre. Les miniatures publiées sont dans `published-thumbnails/` (lues sur YouTube le 14 oct.) et
`channels.json` les relie à chaque chaîne :

```bash
python production/daily/thumbs.py <dossier> idées.json --adapt --ref production/publish/published-thumbnails/<chaîne>.jpg --ref <personnage>.png
```
