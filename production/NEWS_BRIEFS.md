# Analyses courtes d'actualité sportive

Format demandé le 5 octobre 2026 : analyses **4–6 minutes**, voix de la chaîne,
sources affichées, photos sourcées et cartes originales. Les interviews de 15–20
minutes continuent à utiliser `production/news.py`. Publication manuelle par
l'utilisateur ; l'automatisation quotidienne est reportée.

Chaque dossier `news/<chaîne>/<date_sujet>/` contient un `brief.json` relu : titre,
sources nommées avec URL et date, narration par segment, points à l'écran et
crédits des images. Toute rumeur est signalée comme telle. Un repost décrit par
un article reste attribué à cet article tant que l'original n'est pas vérifié.

```bash
cd /workspace/studio
.venv/bin/python production/news_brief.py voice news/mma_en/2026-10-05_parnasse-topuria-analysis
.venv/bin/python production/news_brief.py build news/mma_en/2026-10-05_parnasse-topuria-analysis
```

Les voix et rendus restent dans `work/news_brief/<nom_du_dossier>/` (ignoré par
git). Relancer reprend la même voix, avec le cache des requêtes du fournisseur.
Le montage écrit `result.json`, `captions.srt`, `script.txt` et les planches
`check/sheet_*.jpg` (une capture toutes les cinq secondes). **Regarder toutes
les planches et contrôler le son avant livraison**, puis noter la vérification.
Le montage ne publie pas et n'envoie pas de message Discord.
Si l'alignement audio local est installé, les sous-titres sont recalés sur la voix
enregistrée en conservant l'orthographe du script ; une transcription trop
différente interrompt la production pour contrôle. Une relance conserve ce recalage.

## Livraison sur Discord

À la demande de l'utilisateur, le 5 octobre : livrer les analyses MMA dans Cage Dispatch
et les analyses foot dans Pitch Dispatch. Webhooks dans `.env` seulement :
`DISCORD_WEBHOOK_MMA_EN` et `DISCORD_WEBHOOK_FOOTBALL_EN`. La publication YouTube reste manuelle.

```bash
.venv/bin/python production/news_brief.py send news/mma_en/2026-10-05_parnasse-topuria-analysis --dry-run
.venv/bin/python production/news_brief.py send news/mma_en/2026-10-05_parnasse-topuria-analysis
```

La commande exige `review_ok`, un résultat vérifié et la miniature choisie. Chaque vidéo
part en un seul message : lien MP4, miniature, titres proposés, description et chapitres,
tags, commentaire épinglé proposé et kit ZIP à jour. Les requêtes attendent la confirmation
Discord des deux pièces jointes ; `discord_receipt.json` garde l'identifiant du message,
sans webhook secret. Une relance du même paquet confirmé ne crée pas de doublon.
Le verrou `work/discord.lock` sépare les livraisons. Aucun envoi quotidien n'est programmé.

## Résumé après France–Belgique

Le match du 5 octobre commence à **20 h 45 heure belge**. L'événement ESPN est
`401861129`. La collecte refuse un score provisoire, absent ou une autre équipe.

```bash
.venv/bin/python production/news_brief.py postmatch \
  work/news/football_en/2026-10-05_france-belgium-postmatch \
  401861129 --teams France Belgium
```

Ajouter `--watch` pour attendre la fin confirmée (requêtes toutes les 45 secondes,
huit heures maximum). Un redémarrage cloud peut arrêter cette attente : relancer
la même commande. Ce mode enregistre `match_raw.json`, `match_facts.json` et un
statut, puis s'arrête. Il **ne transforme pas le seul score en analyse tactique**.
Après le match, compléter la recherche par des comptes rendus et réactions
authentiques, relire le script, puis employer le même format court.

Vérification sans appels payants :

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_news_postmatch.py' -v
```
