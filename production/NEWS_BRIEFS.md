# Analyses courtes d'actualité sportive

## Pilote automatique Cage / Pitch (7 octobre 2026)

`studio/autonews.py`, lancé par le moteur du site toutes les 10 minutes, seulement si le
studio n'est pas en pause et que la chaîne est **automatique, activée, connectée**.
1. Radar : flux vérifiés (MMA : MMA News, Sherdog, Bloody Elbow, Cageside Press, BJPenn ;
   foot : BBC, Guardian, Sky Sports, talkSPORT), infos de moins de 18 h, notées 0–10 par
   l'IA (« croustillant » pour les fans) ; ≥ 7 seulement. **2 vidéos par jour et par chaîne**
   au maximum (`NEWS_AUTO_DAILY`), 5 essais au plus par jour.
2. Lecture des articles sources ; ne restent que les faits dont la citation est retrouvée
   **mot pour mot** dans l'article (5 au minimum, sinon arrêt).
3. Script 640–780 mots à partir de ces faits seuls, puis **vérification phrase par phrase** ;
   2 réécritures au plus, sinon arrêt. `reviewed_at` = contrôle automatique, noté comme tel.
4. Photos : Wikimedia Commons uniquement, licence réutilisable (CC0, domaine public,
   CC BY / BY-SA 2.0–4.0), auteur + page de preuve enregistrés ; crédits dans la description.
5. Voix Algrow (choix du propriétaire, risque des conditions accepté et noté dans le
   manifeste), musique générée, montage existant (`news_brief.build`) sur o2switch.
6. Miniature dans le thème validé (`presets/news_thumbnails/approved_2026-10-05/`), avec les
   portraits Commons ; texte contrôlé en vision (sinon arrêt).
7. Contrôle des planches en vision, décodage, manifeste des droits, statut `ready` →
   `studio/auto_publication.py` publie (contrôles habituels) → message Discord avec le lien.
`NEWS_AUTO_DRY=1` : fabrique et contrôle sans publier (statut `review` + message Discord).

Format demandé le 5 octobre 2026 : analyses **4–6 minutes**, voix de la chaîne,
sources affichées, photos sourcées et cartes originales. Les interviews de 15–20
minutes continuent à utiliser `production/news.py`. Publication manuelle par
l'utilisateur ; l'automatisation quotidienne est reportée.

Chaque dossier `news/<chaîne>/<date_sujet>/` contient un `brief.json` relu : titre,
sources nommées avec URL et date, narration par segment, points à l'écran et
crédits des images. Toute rumeur est signalée comme telle. Un repost décrit par
un article reste attribué à cet article tant que l'original n'est pas vérifié.

## Droits de réutilisation et automatisation

Demande de l'utilisateur du 5 octobre : aucune publication automatique avec des droits
non établis. Un article accessible, un crédit photo, une source indépendante ou une
absence de réclamation Content ID **ne prouve pas une autorisation de réutilisation**.
L'utilisateur rapporte un contrôle YouTube sans réclamation pour les trois vidéos du jour.
Les contrôles de licences sont conservés dans leurs `rights_audit.json` : photos des
miniatures vérifiées, musique synthétisée localement, mais droits des images de presse
des montages non établis. Ces anciens montages ne sont pas autorisés à être recyclés automatiquement.

La validation des nouveaux briefs refuse une image sans `visual.rights` documenté :
licence compatible avec la réutilisation et les modifications, auteur, page de preuve,
date de contrôle et lien de licence. Les adaptations BY-SA gardent la même licence.
Les mentions « editorial », « fair use », « photo: média » ou une licence NC/ND
ne passent pas ce contrôle. Choisir une image sous licence appropriée ou une création originale.
Une relance des anciens briefs exige donc d'abord le remplacement de leurs visuels de presse.

Pour le futur dashboard, `services.news_rights.automation_rights(plan)` doit être appelé
avant toute publication automatique. Il exige aussi une autorisation documentée de
réutilisation commerciale de la voix **et** d'accès automatisé à son fournisseur, ainsi
qu'une trace de génération de la musique originale. La clé API seule ne suffit pas.
Les conditions Algrow consultées le 5 octobre (`https://algrow.online/terms`, section 13)
contiennent une restriction d'usage automatisé de la fonction voix ; la portée de
l'offre API doit être confirmée avant de choisir ce fournisseur pour l'automatisation.
Le programme ne promet pas zéro réclamation future et ne programme aucune publication.

Miniatures futures : suivre `presets/news_thumbnails/approved_2026-10-05/` ; l'utilisateur
a validé ce thème et a demandé d'arrêter les variantes pour les trois vidéos actuelles.

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
