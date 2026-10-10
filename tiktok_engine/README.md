# Octave Histoire (@octave.histoire) : l'outil du compte TikTok (démarré le 7 oct. 2026)

Outil propre à ce compte TikTok : tout est dans `tiktok_engine/`, indépendant des chaînes
YouTube. La publication des vidéos programmées est automatique par Zernio ; une session
prépare et contrôle les nouveaux contenus avant de les ajouter à la file.

Demande de l'utilisateur (7 oct., soir) : un compte TikTok français **dans le même style visuel
que @archibald.media**, codé de A à Z en HTML et JavaScript, sans vidéo IA. Vidéos de plus d'une
minute, voix ElevenLabs **v4** (via Algrow, crédits existants), zéro dépense. La piste des persos à
tête d'objet (`production/TIKTOK_PLAN.md`) est **en pause**.

## Ce que l'utilisateur a fixé

- **Copie du style d'Archibald**, pas de ses vidéos : fond **noir**, une seule couleur d'accent,
  un **bleu foncé vif** à la place de son rouge (pas de fond coloré : refusé le 7 oct.).
- **Thèmes** : des **personnages historiques** connus (Napoléon, Mozart, Beethoven…) avec un fait
  surprenant, chiffres à l'appui. Les idées « argent caché » et science pure ont été refusées
  (« à dormir debout »).
- **Les deux premières secondes doivent accrocher** (retour du 7 oct. sur la 1re vidéo : « pas assez
  accrocheur ») : le personnage en grand portrait pixel claque dès la première image (flash), avec la
  phrase choc. Le compteur seul ne suffit pas.
- **Pas d'outro** (« demain on fera… » : refusé) : la vidéo s'arrête sur sa chute.
- **Illustrations : Algrow depuis le 9 oct.**
  - Le modèle est `nano-banana-2`, à 1 crédit l'image. On l'a choisi parce que les crédits Replicate
    sont presque épuisés, et que la version gratuite (vrais tableaux pixelisés) a été jugée « affreuse ».
  - `art.py prompts videos/<nom>/script.json` donne, pour chaque image du bloc `"art"`, la consigne,
    le format et deux références de style. Les références sont nos anciennes images `rd-plus`, sur le
    dépôt public.
  - On génère chaque image avec l'outil Algrow `generate_image`. L'état du travail se lit avec
    `get_tts_job_status`, qui sert aussi pour les images.
  - Ensuite, `art.py fit videos/<nom>/script.json nom=<url> …` recadre l'image, la met sur la palette
    à la taille demandée, rend transparent le noir relié aux bords, puis refait `art_review.jpg`.
  - Les petits dessins codés de `sprites.js` restent pour les icônes (soldats, crânes, thermomètre…).
  - Ancienne voie Replicate : `art.py batch` (clé `REPLICATE_API_TOKEN`).

## Le compte (retenu par l'utilisateur le 8 oct.)

- **Nom et pseudo :** **Octave**, pseudo **@octave.histoire**. Octave est le premier nom de l'empereur
  Auguste, et c'est aussi un terme de musique (Mozart, Beethoven).
- **Bio :** « L'Histoire comme on ne te l'a jamais racontée. 1 vidéo par jour. 📜 » (sur le modèle
  d'Archibald, « 1 vidéo de qualité par jour. 🧠 »). Elle ne change pas d'une vidéo à l'autre.
- **Photo de profil :** la **couronne** bleue en pixel art, centrée sur fond noir pur :
  `brand/photo_profil_couronne.png`. Les 8 autres propositions sont dans `brand/noir_*.jpg`
  (les cercles bleus derrière ont été refusés le 7 oct.).
- **Description de vidéo**, simple comme la 1re d'Archibald : **une phrase + 4 hashtags**, sans
  sources ni émoji (ex. « La Joconde est devenue célèbre grâce à un voleur. #histoire #vulgarisation
  #joconde #louvre »). Champ `caption` du script ; les sources restent dans `sources`, pour nous.

## Règles de qualité ajoutées après la 1re vidéo

- **Vérifier chaque illustration** (mains, doigts, bras, visages) avant le montage. Sur la vidéo
  Napoléon, l'image de Napoléon écrivant avait des mains ratées (remarqué par l'utilisateur, publiée
  quand même). Une image ratée se refait avec `art.py batch … --only nom`.

## Le style d'Archibald (analysé image par image, 5 vidéos, 1 min 40 à 2 min)

- **Mise en page :**
  - Titre blanc en grotesque très gras, en haut (environ 16 % de la hauteur).
  - Gros chiffre en police pixel juste dessous.
  - Le dessin occupe le milieu ; le bas de l'écran reste vide (légende TikTok).
- **Animations :**
  - Le chiffre arrive en grand puis claque, avec un flash plein écran d'une image.
  - Les compteurs défilent (14 506 → 150 000) et s'éclaircissent en fin de course.
  - Tampons inclinés (« TCHERNOBYL », « 1 AN »).
  - Mots barrés.
  - Grilles de carrés ou d'icônes (une icône = N personnes).
  - Barres en segments.
- **Fond :**
  - Noir avec une grille très légère.
  - Poussières colorées qui montent.
  - Lueur ronde derrière le sujet.
  - Vignette.
- **Dessins :** pixel art tramé en damier, petites boucles (fumée, feu, « ? » qui clignote).
- **Son :** voix seule, sans musique ; quelques bruitages (impact sur les chiffres, grondement au début).
- **Récit :**
  - Accroche chiffrée.
  - « vous pensez sûrement à ça ».
  - « sauf que les chiffres… ».
  - « mais attendez ».
  - La leçon.
  - Une suite annoncée (carte de fin pleine couleur « LA SUITE DEMAIN ▶ »).
  - Sources dans la description.

## Le moteur (`tiktok_engine/`)

- **`engine.js` + `sprites.js` :**
  - Dessinent l'image du temps t sur un canevas 1080×1920, de façon déterministe.
  - Éléments : `text` (préréglages `title`, `big`, `num`, `label`, `sub` ; `*mot*` = bleu), `counter`, `stamp`,
    `img` (illustration, effets `in: slam|scan|pop|fade`, `fx: breathe|shiver|bob|zoom`), `sprite`, `icons`,
    `grid`, `bars`, `flow` (bande de Minard), `line`, `forest`, `dna`, `rect`, `endcard`.
  - Les gros chiffres utilisent Tiny5, avec des rayures façon écran LED.
- **`render.mjs` :**
  - Chromium dessine chaque image et ffmpeg l'encode, sur 3 pages en parallèle (environ 13 images/s ici).
  - `--stills` sort des images fixes pour la relecture.
  - `--serve` lance un lecteur local.
- **`build.py <dossier> --script videos/<nom>/script.json` :**
  - La voix vient d'Algrow (ou de `voice.mp3` déposé), puis les mots sont datés (SRT d'Algrow, sinon Whisper).
  - La `timeline.json` est calée sur les mots, puis viennent les planches `check/sheet_*.jpg`, le mix (bruitages synthétisés, -14 LUFS) et `video.mp4`.
- **Ancres de temps dans un script :**
  - `"at": "mot"` (début du mot dans ce temps fort), `"mot#2"`, `"mot+0.3"`, `"mot>"` (fin du mot).
  - Un nombre veut dire des secondes depuis le début du temps fort.
  - Avec `"keep": true`, la scène précédente continue.

Polices sous licence OFL (fichiers et licences dans `fonts/`).

## Livraison de chaque vidéo (demande du 7 oct.)

À chaque vidéo, l'utilisateur reçoit le **même paquet** :
- la vidéo en **qualité maximale** (lien Gofile + fichier) ;
- **3 miniatures** 1080×1920 (bloc `covers` du script, une recommandée) ;
- la **description** à coller, simple comme Archibald : une phrase + 4 hashtags (`caption`).

`build.py` fait tout à la fin du rendu (`deliver` : `covers/`, `description.txt`, `gofile_link.txt`,
`livraison.txt`). Les illustrations se relisent sur `videos/<nom>/art_review.jpg` (pixels ×3) avant le montage.

## Publication (recherche du 8 oct.)

- **Rythme : 2 TikTok par jour, à 7 h et 19 h (heure belge)**, publiés tout seuls par Zernio.
  Fabrication : routine quotidienne « Octave Histoire : 2 TikTok par jour » (vers 8 h 47), qui suit
  [ROUTINE.md](ROUTINE.md) et garde une semaine d'avance. Première semaine (9-15 oct.) faite le 9 oct.
  par 7 sessions en parallèle ; durées contrôlées (toutes > 61 s, Einstein refaite à 1 min 41).
  Le 8 oct. au soir, l'utilisateur a hésité
  avec 3 par jour (7 h, 12 h, 19 h), puis a dit : « je pense que c'est plus smart d'en poster deux ».
- **API TikTok (Content Posting API)** : pas une solution pour nous.
  - Les règles de TikTok refusent noir sur blanc « un outil pour envoyer du contenu sur le(s)
    compte(s) que vous ou votre équipe gérez ».
  - Sans leur audit, les vidéos postées par l'API restent privées (`SELF_ONLY`), et le compte
    doit lui-même être privé.
  - Source : developers.tiktok.com/doc/content-sharing-guidelines.
- **Pas d'automatisation du site TikTok** (risque pour le compte, même règle que YouTube).
- **Piste proposée le 9 oct. pour poster sans l'utilisateur : Zernio**, l'ancien « Late »
  (zernio.com, docs.zernio.com/platforms/tiktok).
  - Ses 2 premiers comptes connectés sont gratuits, avec des posts illimités et l'accès complet à l'API.
  - C'est une appli que TikTok a validée, donc les posts sont publics.
  - Envoi : `POST /v1/posts` avec `mediaItems` (vidéo par URL publique ou par leur envoi de fichiers),
    `platforms` (tiktok + `accountId`) et `tiktokSettings` (`privacy_level` pris dans `creator-info`,
    `content_preview_confirmed` et `express_consent_given` à true, `video_made_with_ai`).
  - Programmation à une heure donnée (champ à vérifier : `scheduledFor`).
  - Limite : 15 vidéos par 24 h et par compte.
  - À faire par l'utilisateur, une fois : créer le compte, y connecter le TikTok, créer une clé API et
    la mettre en variable d'environnement `ZERNIO_API_KEY` (jamais dans le chat).
- Piste de secours : le planificateur de TikTok Studio (sur ordinateur).
  - Il programme jusqu'à 10 jours à l'avance.
  - Il demande un compte pro.
  - Nous, on prépare un paquet par semaine (vidéos, miniatures, descriptions, horaires) ;
    l'utilisateur programme tout en une fois.

## Ce que coûte une vidéo (calculé le 8 oct.)

- **Illustrations Algrow (depuis le 9 oct.)** : environ **12 crédits par vidéo** (1 par image, plus
  1 par image refaite), soit presque rien à côté de la voix.
- **Ancien coût Replicate** (clé de l'utilisateur) : environ **0,60 $ par vidéo** pour une douzaine
  d'images. Prix `rd-plus`, style `default`, à l'image : 0,044 $ jusqu'à 192×192, 0,058 $ jusqu'à
  256×256 (320×192 compris), 0,077 $ jusqu'à 320×320. Napoléon : 0,58 $ ; Joconde : 0,64 $. Chaque image
  refaite (mains ratées…) coûte le même prix. Les icônes de `sprites.js` sont gratuites.
- **Voix** : crédits Algrow, v4 compte 3 crédits par caractère. Napoléon ≈ 5 100, Joconde ≈ 3 600.
  Une voix refaite après correction se paie une 2e fois.
- **Gratuit** : rendu (machine cloud), datation des mots (Whisper local), bruitages (synthétisés),
  polices (OFL), hébergement Gofile.

## Vidéos livrées

| Date | Vidéo | Lien qualité max |
|---|---|---|
| 7 oct. 2026 | Napoléon en Russie (Minard, les poux, « La santé de Sa Majesté… ») | https://gofile.io/d/XfHd6IAK |
| 8 oct. 2026 | La Joconde, célèbre grâce à un voleur (vol de 1911) | https://gofile.io/d/DOWccY1j |
| ven. 9 oct. 2026, 07 h (publiée) | Beethoven : 95 fois trop de plomb | https://gofile.io/d/7ANl9981 |
| ven. 9 oct. 2026, 19 h (publiée) | Le cerveau d'Einstein, coupé en 240 morceaux | https://gofile.io/d/bRKTUWbQ |
| sam. 10 oct. 2026, 07 h (programmée) | Cléopâtre plus proche de l'iPhone que des pyramides | https://gofile.io/d/fzxJzPB2 |
| sam. 10 oct. 2026, 19 h (programmée) | Les Vikings n'ont jamais porté de casques à cornes | https://gofile.io/d/9L3GIfeF |
| dim. 11 oct. 2026, 07 h (programmée) | Gengis Khan et 16 millions d'hommes | https://gofile.io/d/eg8Sy58k |
| dim. 11 oct. 2026, 19 h (programmée) | Marie-Antoinette n'a jamais dit ça | https://gofile.io/d/yIuSw80p |
| lun. 12 oct. 2026, 07 h (programmée) | Les carnets de Marie Curie sont encore radioactifs | https://gofile.io/d/ryrkE6D9 |
| lun. 12 oct. 2026, 19 h (programmée) | La malédiction de Toutankhamon en chiffres | https://gofile.io/d/qflqThSp |
| mar. 13 oct. 2026, 07 h (programmée) | Salieri n'a pas empoisonné Mozart | https://gofile.io/d/V6S1IU3w |
| mar. 13 oct. 2026, 19 h (programmée) | Pierre le Grand et la taxe sur la barbe | https://gofile.io/d/EWrYy6bK |
| mer. 14 oct. 2026, 07 h (programmée) | Lincoln, le président lutteur | https://gofile.io/d/LYvljZde |
| mer. 14 oct. 2026, 19 h (programmée) | Le doigt de Galilée | https://gofile.io/d/fpWk4ev0 |
| jeu. 15 oct. 2026, 07 h (programmée) | L'erreur de calcul de Christophe Colomb | https://gofile.io/d/wxa6QISa |
| jeu. 15 oct. 2026, 19 h (programmée) | Jules César et les pirates | https://gofile.io/d/HwH5CZsH |

## Semaine du 16 au 22 octobre 2026

14 nouvelles vidéos programmées le 10 octobre, à 07:00 et 19:00 Europe/Brussels.
Voix et images via Algrow, rendus sur le VPS existant, fichiers 1080×1920 à 30 images/s,
durées de 1 min 27 à 1 min 39. Chaque illustration, planche et cover a été revue ;
les MP4 ont été décodés intégralement puis examinés au début, au milieu et à la fin.
Audit Zernio : 14 posts publics programmés, médias accessibles, aucun doublon.
Le compte compte 28 posts au total, dont les deux du 9 octobre déjà publiés.
Le prochain jour libre après cette file est le 23 octobre, à confirmer dans Zernio
avant de le remplir. Rendu réutilisable : [VPS.md](VPS.md).

| Date | Vidéo | Lien qualité max |
|---|---|---|
| ven. 16 oct. 2026, 07 h (programmée) | Henri VIII : six femmes, mais seulement deux exécutées | https://gofile.io/d/qg16U0vY |
| ven. 16 oct. 2026, 19 h (programmée) | Néron ne pouvait pas jouer du violon | https://gofile.io/d/aXT4Qwtl |
| sam. 17 oct. 2026, 07 h (programmée) | Titanic : vingt canots pour plus de deux mille personnes | https://gofile.io/d/ZbiAuSs4 |
| sam. 17 oct. 2026, 19 h (programmée) | La tour Eiffel devait rester vingt ans : la radio a contribué à la sauver | https://gofile.io/d/yuPYyeWe |
| dim. 18 oct. 2026, 07 h (programmée) | Jeanne d'Arc, réhabilitée vingt-cinq ans trop tard | https://gofile.io/d/T2qRcN4Q |
| dim. 18 oct. 2026, 19 h (programmée) | Élisabeth I : plus de quarante-quatre ans de règne, aucun mari | https://gofile.io/d/fqn9Sqbf |
| lun. 19 oct. 2026, 07 h (programmée) | La pierre de Rosette, trois écritures mais deux langues | https://gofile.io/d/WEuyNlq5 |
| lun. 19 oct. 2026, 19 h (programmée) | Catherine II a accepté la variole pour lui échapper | https://gofile.io/d/nEiW5M8E |
| mar. 20 oct. 2026, 07 h (programmée) | Gandhi : une poignée de sel contre un empire | https://gofile.io/d/rDAuRo1x |
| mar. 20 oct. 2026, 19 h (programmée) | Mandela : de vingt-sept ans de prison à la présidence | https://gofile.io/d/V1l4BozC |
| mer. 21 oct. 2026, 07 h (programmée) | Le mur de Berlin et l’annonce qui a tout accéléré | https://gofile.io/d/KUM2F1Lk |
| mer. 21 oct. 2026, 19 h (programmée) | Bismarck : un message raccourci, une guerre six jours après | https://gofile.io/d/WvOcngTQ |
| jeu. 22 oct. 2026, 07 h (programmée) | Londres : treize mille maisons perdues dans le Grand Incendie | https://gofile.io/d/GuxlKznO |
| jeu. 22 oct. 2026, 19 h (programmée) | Patton et la fausse armée du Débarquement | https://gofile.io/d/0pWqhrfg |
