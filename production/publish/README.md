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

La miniature et la date sont choisies par l'utilisateur. Une fiche sans choix de miniature ne part pas.
