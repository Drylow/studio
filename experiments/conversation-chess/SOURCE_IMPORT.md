# Récupération des clips : méthode effectivement utilisée

Le téléchargement est notre tâche. L'utilisateur a explicitement refusé
de fournir les clips ou de les télécharger sur son PC. Reprendre la méthode
ci-dessous et les sources du `PLAN_TONY_RICHIE.md`, sans recommencer à lui
demander les fichiers.

## API et requête qui ont réellement réussi

Utiliser la liaison existante `ALGROW_API_KEY` via l'application normale.
Si elle est absente, suivre les instructions d'accès du dépôt, sans afficher
les valeurs ni ajouter de clé au code. Conserver proxy hérité et vérificationTLS.

- `POST https://api.algrow.online/api/download-video`.
- En-tête `Authorization: Bearer <ALGROW_API_KEY configurée>`.
- En-tête `Accept: application/json`.
- Corps JSON, envoyé comme JSON structuré :

```json
{
  "video_url": "https://www.youtube.com/watch?v=Mc5qO4mnd2Q",
  "format": "video",
  "quality": "1080p"
}
```

Sans `start`/`end`, la requête porte sur le clip individuel complet. Ici ce
sont des scènes publiques de quelques secondes/minutes, pas un épisode entier.
La réponse fournit `success`, `download_url`, `duration_seconds`, `size_bytes`,
`cached` et `quality`. Vérifier réussite, durée et taille bornée, puis récupérer
l'URL HTTPS renvoyée par le fournisseur avec les mêmes proxy et confianceTLS.
Ne pas imprimer ni enregistrer cette URL signée dans Git. Ne pas envoyer
l'en-tête d'authentification de l'API à l'hôte du fichier.

Paramètres des imports récents : connexion15s, réponse150s, au plus150MiB pour
les courts clips ; une tentative par source choisie. Les deux anciennes
compilations avaient une limite250MiB. Pas de boucle sur une requête inchangée.
Conserver réponse brute privée et reçu séparé sans secrets ni URL de stockage.

## Contrôle du fichier acquis

`quality:1080` dans la réponse peut simplement reprendre la demande. Des
réponses fraîches `cached:false` ont réellement fourni360p,720p ou1080p.
Mesurer **le fichier** et examiner des images natives avant de l'accepter :

```bash
ffprobe -v error -show_streams -show_format -of json SOURCE.mp4
ffmpeg -v error -i SOURCE.mp4 -map 0:v:0 -map '0:a:0?' -f null -
ffmpeg -v error -ss 7 -i SOURCE.mp4 -frames:v 1 native-frame-7.png
```

Vérifier dimensions, codec, débit, audio, durée et fps ; regarder un gros plan
stable et des images en mouvement. La résolution seule ne prouve pas le détail.
Un agrandissement ne répare pas une source molle. Une autre copie exige de
réaligner les dialogues, le premier locuteur et les annotations.

Les docs publiques ne proposent pas de sélecteurDASH/format_id, de fusion de
flux séparés ni de qualité minimale stricte. Ne pas inventer ces paramètres.
Le vrai fichier1080p du payoff montre que l'API peut fournir1080p ; les raisons
des retours inférieurs sur d'autres sources ne sont pas établies.

## Bilan acquis et limites

| Identifiant public | Fichier mesuré | Utilisation actuelle |
|---|---|---|
| `cRtAotacluI` |1280×720,147,516s,1,416Mb/s vidéo|Don/essayage, dialogue et repères revus ; qualité finale refusée|
| `Mc5qO4mnd2Q` |1920×1080,9,985s,3,043Mb/s vidéo|Découverte et réaction, images natives et dialogue revus|
| `PvKkpnT2sEs` |1280×720,162,93s,1,044Mb/s vidéo|Autre copie du don ; ne pas réutiliser les repères de la première|
| `JQlpKya4HtM` |640×360,106,12s,0,336Mb/s vidéo|Avertissement sur les routes, recherche de découpage seulement|
| `ORFLR7cgY3s` |640×360,397,689s,0,116Mb/s vidéo|Confrontations distinctes, recherche seulement ; aucune veste|

Le dernier import `js7lnh8JrZw` (réunion annoncéeS2E12) a dépassé150s : aucun
fichier, aucune scène certifiée par ce test. Les autres sources qui ont échoué
restent notées dans le reçu privé ; aucun retry automatique. Le lot est clos.
Seul le court payoff est livré en1080p mesuré : pas de longFullHD annoncé.

Les médias et transcriptions complètes restent horsGit. Dans cette machine,
reçus/probes/images sont dans `/tmp/sopranos_sources/current-source-audit/`,
les scripts réellement exécutés dans `/tmp/sopranos_sources/acquire_*_full.py`.
Ces fichiers temporaires ne sont pas garantis sur une autre machine : les
requêtes ci-dessus et les identifiants publics permettent leur récupération.
Cette méthode n'utilise ni shellVPS pour contourner unCDN refusé, ni connexion
Naka, ni modification du site ou des automatisations existantes.
