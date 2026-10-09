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

## Lot ciblé supplémentaire et première vérification Naka

Cinqnouveaux clips identifiés ont ensuite été importés une seule fois par la
même route normale. `lKm5SXyQn20` est refuséHTTP400 avec une erreur du proxy
YouTube du fournisseur ; `R0dNYdum5ss` échoueHTTP400 ; `8PPVQJdUcZM` dépasse150s ;
`-7BHfJOgm80` échoueHTTP400 après expiration de sa recherche vidéo. Aucun fichier
pour ces quatretests, aucun retryinchangé. Les recherchesAPI répondentHTTP200,
donc ces erreurs ne prouvent pas une cléAlgrow manquante côté utilisateur.

`wUs8M0yglX0` est réellement téléchargé :74,234s,1280×704,60fps,1,027Mb/s vidéo,
SHA256`36bcfd1f60075b72a8e02894d88d6c5111abf6403b689b96f6e073c42ec43f9f`.
Siximages et16segmentsASR revus, décodageA/V complet. RéunionS2E12 des routes,
Tony ouvre vers2,86s. Visages mous et watermarkJWPLAYER permanent : préparation
uniquement, **pas une source finale acceptée**. Rapportprivé dans
`/tmp/sopranos_sources/new-richie-source-lot/LOT_REPORT.md`.

État antérieur, avant réception effective des accès de compte :
l'utilisateur propose ensuite l'accès à son compteNaka. La page publique et
ses scripts répondentHTTP200 à cette nouvelle vérification normale. Le site
annonce une fonction horsligne et le téléchargement épisode par épisode enVO/VF.
Le client conserve des médias segmentés en stockage navigateur ; ce n'est pas
encore une preuve de fichierMP4 exportable ni de résolution réelle desSopranos.
Aucune connexion de compte, téléchargement d'épisode ou récupération protégée
n'a été effectuée. Ne pas affirmer que Naka est opérationnel avant de mesurer
un vrai fichier acquis par une fonction autorisée. Aucun motdepasse dansGit/chat.

## Naka : acquisition normale réussie et vérifiée le 9 octobre 2026

L'état précédent est désormais dépassé : les variables `NAKA_EMAIL` et
`NAKA_PASSWORD` ont été reçues dans l'environnement, la connexion normale a
réussi et les trois épisodes autorisés ont été réellement téléchargés par
la fonction hors ligne du compte. **Le résultat est du 720p natif**, et non
du 1080p : c'est la seule qualité proposée à ce compte gratuit. Aucun accès
à une qualité ou à un quota supplémentaire n'a été forcé.

Les fichiers contiennent chacun une piste H.264 de 1280×720 à 24000/1001 fps
et une piste AAC anglaise stéréo à 48 kHz. Les sous-titres anglais proposés
par le service ont été conservés uniquement comme repères privés ; ils ne
sont pas intégrés aux MP4. Les images natives représentatives du don, des
confrontations et de la découverte ne montrent ni watermark ni sous-titres
incrustés. Le détail des visages et du tissu est meilleur que sur les anciens
clips YouTube compressés. Cela ne transforme pas ces sources en Full HD et
ne dispense pas de vérifier les plans effectivement utilisés au montage.

| Épisode | Durée mesurée | Taille exacte | SHA-256 |
|---|---:|---:|---|
| S2E3 | 3046,720 s | 948853656 octets | `941ae249547c50175f666fdcbbf66ab64e72466f8f7e9307591d44c26ff5d3e1` |
| S2E6 | 3059,861333 s | 952233038 octets | `68f1a8cebe052c11bc10143404ed681f5e34327ac7b9cb4b7bdf4a6c99a70194` |
| S2E8 | 2573,888 s | 800612325 octets | `f639555648e1f66131107c9f8ff1cf4b618de7cd9824eac1c9641fa6465fc54f` |

Les trois décodages audio **et** vidéo complets ont terminé avec le code 0.
Les contrôles `ffprobe` confirment deux pistes par fichier et aucune piste
de sous-titres. Les reçus enregistrent les mesures et les contrôles réels ;
aucune écoute humaine intégrale ni inspection de chaque image n'est annoncée.

### Contrat du client effectivement utilisé

Toutes les requêtes de compte utilisent `https://naka.cx/api/v1`, avec le
proxy hérité et la vérification TLS. Le jeton reste réservé à cet hôte ;
il n'est pas transmis aux hôtes des médias. Les valeurs d'accès, réponses
de connexion et URL signées restent hors Git et ne doivent pas être affichées.

1. `POST /auth/login` avec les variables de compte configurées, puis
   `GET /profiles` et sélection normale d'un profil existant accessible.
2. `GET /browse/search?q=The%20Sopranos&type=tv` et
   `GET /browse/{contentId}/season/2` pour identifier réellement la série
   et ses épisodes. Ne pas confondre l'identifiant interne avec celui de TMDB.
3. `GET /offline/price/{contentId}?scope=episode&season=2&episode=N`
   et lecture de la bibliothèque existante. Vérifier `enabled`, `available`,
   `isFree`, `price`, `limitReached`, `alreadyOwned` et les sources proposées.
4. Pour les trois épisodes expressément autorisés et gratuits, acquisition
   normale via `POST /offline/purchase`, avec `contentId`, `scope: episode`,
   `season`, `episode` et l'`encodingJobId` réellement proposé. Réutiliser
   un accès déjà acquis plutôt que créer une nouvelle acquisition.
5. `GET /offline/manifest/{entitlementId}` : prendre le média anglais et la
   meilleure qualité proposée, dans la limite du `maxHeight` retourné.
   Télécharger les segments HLS non chiffrés proposés et réunir la vidéo
   et l'audio anglais sans réencodage, sous-titres ni agrandissement.

Ce chemin a effectivement fonctionné pour S2E3, S2E6 et S2E8. Il s'arrête
sur refus d'accès, CAPTCHA, exigence de licence, restriction réseau ou média
chiffré ; aucun contournement n'est fourni. Un prix non nul exige une nouvelle
validation avant acquisition.

### Quota et cache à réutiliser

Les **trois acquisitions gratuites autorisées sont utilisées**. Après les
trois téléchargements, la lecture du prix d'un épisode non acquis renvoie
`freeUsed: 3`, `freeLimit: 3`, `limitReached: true`. La réponse optimisée d'un
épisode déjà acquis peut afficher `freeUsed: 0` : ce n'est pas une remise à
zéro du quota. Aucun quatrième épisode, suppression d'accès ou contournement
de la limite n'a été tenté.

Les copies exactes et vérifiées sont dans le dossier ignoré par Git
`output/conversation-chess/source-cache/` :

- `the-sopranos-s02e03-english-acquired.mp4`, puis les mêmes noms pour `06` et `08` ;
- `s02eNN-source-safe.json` et `SOURCE_INVENTORY_SAFE.json` : reçus sans accès privés ;
- `s02eNN-english-timing-reference.vtt` et
  `s02eNN-english-subtitle-cues-private.json` : repères privés de découpage.

Les liens physiques depuis `/tmp` sont impossibles entre ces deux systèmes
de fichiers ; les copies ont été vérifiées par SHA-256. Réutiliser ce cache
pour les montages et préserver les originaux. Ce dossier n'est pas envoyé
sur GitHub et ne sera pas automatiquement disponible dans une autre machine.
Les jetons, profils de compte et manifestes privés ne sont pas dans ce cache.

Sur cette machine uniquement, les scripts réellement exécutés restent privés
dans `/tmp/naka_acquire_sopranos_episode.py` et
`/tmp/naka_acquire_approved_episode.py`, avec le contrat détaillé dans
`/tmp/NAKA_DOWNLOAD_VERIFIED_HANDOFF.md`. Aucun secret n'est incorporé aux scripts.

### Alignement utile au montage

Recalculer les timings depuis les nouveaux épisodes ; les offsets des clips
YouTube ne sont pas réutilisables. Pour S2E8 : don de la veste vers 719–849 s,
question sur la veste au dîner vers 1273–1289 s, anecdote répétée à Satriales
vers 1644–1654 s, puis découverte de la veste portée par le mari de Liliana
vers 2051–2056 s. Le passage vers 1645 s n'est pas la découverte finale.

Dans S2E3, Tony présente Richie à Christopher vers 771 s. L'avertissement
vers 780 s est adressé à Christopher : ne pas noter une réponse de Christopher
comme un coup de Tony. Vérifier le premier interlocuteur retenu et attribuer
les Blancs au joueur qui ouvre effectivement la partie.
