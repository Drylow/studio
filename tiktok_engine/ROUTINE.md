# Routine quotidienne Octave Histoire (@octave.histoire)

Lancée chaque jour vers 9 h (heure de Bruxelles), dans une session neuve. Elle garde **une semaine
d'avance** : elle remplit le **premier jour sans vidéo programmée**, à **7 h et 19 h**, publiées par
Zernio. Une session lancée pour un jour précis remplit ce jour-là.
Lire d'abord [README.md](README.md) : style, règles de l'utilisateur, moteur. Faits réels uniquement.

## 0. Préparer

- `git pull origin main`, puis `bash tiktok_engine/setup.sh` (qui doit afficher « prêt »).
- `python3 tiktok_engine/zernio.py accounts` doit montrer le compte TikTok. Sinon, arrêter et écrire
  le problème dans le résumé de fin.
- **Créneaux déjà pris** : chaque vidéo programmée a son `tiktok_engine/videos/<nom>/zernio.json`
  (champ `at`). Prendre le premier jour, à partir de demain, qui n'a pas ses deux créneaux
  (07:00 et 19:00). Ne jamais programmer un créneau déjà pris.
- Clés : `ALGROW_API_KEY` et `ZERNIO_API_KEY` sont dans le `.env` du serveur. `setup.sh` copie
  celles qui manquent, avec `production/server_env.py` et les accès cPanel de l'environnement
  (`CPANEL_USER`, `CPANEL_PASSWORD`), dans le `.env` local ignoré par git. N'afficher que
  « présente » ou « absente ». Le dépôt est public : jamais une clé dans git.
  Si une clé manque, s'arrêter et le dire. Ne pas passer par les outils Algrow de la session : ils
  attendent une autorisation que personne ne donnera.

## 1. Choisir les sujets

- Un **personnage historique connu** (ou un objet ou un lieu célèbre lié à un personnage), avec un
  **fait surprenant et chiffré**.
- Refusés par l'utilisateur : « argent caché », science pure, sujets qui endorment.
- Jamais un sujet déjà fait : voir les dossiers `videos/` et la table « Vidéos livrées » du README.
- Pistes notées :
  - le plomb dans les cheveux de Beethoven ;
  - le cerveau d'Einstein ;
  - Cléopâtre plus proche de l'iPhone que des pyramides ;
  - Gengis Khan et ses descendants ;
  - les carnets encore radioactifs de Marie Curie ;
  - Mozart et Salieri.
- **Vérifier chaque chiffre** sur au moins 2 sources sérieuses (recherche web) avant d'écrire. Un
  chiffre incertain est coupé ou dit comme une estimation. Les sources vont dans le champ `sources`.

## 2. Écrire `tiktok_engine/videos/<nom>/script.json`

- Même structure que `videos/joconde_vol/script.json` : bloc `voice`, temps forts `beats` (avec
  `say` et les visuels), blocs `art`, `covers` (3 miniatures) et `caption`.
- Le bloc `voice` reste identique : Tenko `0bKGtCCpdKSI5NjGhU3z`, `eleven_v4`, vitesse 1,06.
- **Les 2 premières secondes accrochent** : le personnage en grand portrait pixel claque dès la
  première image, avec la phrase choc.
- **Plus d'une minute obligatoire** (TikTok ne rémunère que les vidéos de plus d'une minute) : viser
  1 min 10 à 1 min 30, soit **200 à 240 mots** de `say` au total. `zernio.py` refuse une vidéo de
  moins de 61 s. Avec « vous ». **Pas d'outro** : la vidéo s'arrête sur sa chute.
- `caption` : une phrase et 4 hashtags, sans émoji ni sources.

## 3. Images (Algrow, 1 crédit l'image)

1. Lancer `.venv/bin/python tiktok_engine/art.py algrow tiktok_engine/videos/<nom>/script.json`.
   Il passe par l'API, avec la clé `ALGROW_API_KEY` du `.env`, donc sans autorisation à donner.
   Testé le 9 oct. : environ 30 s par image, 4 en parallèle.
2. **Regarder `videos/<nom>/art_review.jpg`** : mains, doigts, bras, visages, objets absurdes.
3. Une image ratée se refait avec `art.py algrow … --only nom`.
4. Sans clé dans l'environnement, passer par les outils Algrow de la session :
   - `art.py prompts` donne la consigne de chaque image ;
   - générer avec `generate_image` ;
   - suivre avec `get_tts_job_status` jusqu'à `completed` ;
   - finir avec `art.py fit … nom=<url>`.

## 4. Voix (Algrow)

1. Avec `ALGROW_API_KEY`, `build.py` (étape 5) fait la voix tout seul.
2. Sans clé, passer par l'outil de la session :
   - le texte est la concaténation des `say` des temps forts, séparés par un espace ;
   - générer avec `generate_tts` (Tenko, `eleven_v4`, vitesse 1,06) ;
   - télécharger le mp3 avec `curl -A "Mozilla/5.0 …"` dans `work/tiktok/<nom>/voice.mp3`, sans `words.srt`.

## 5. Montage et contrôle

1. Lancer `.venv/bin/python tiktok_engine/build.py work/tiktok/<nom> --script tiktok_engine/videos/<nom>/script.json`.
2. **Regarder les planches `work/tiktok/<nom>/check/sheet_*.jpg`** :
   - le chiffre affiché correspond au chiffre dit ;
   - aucun texte coupé ;
   - le hook est là dès le début ;
   - l'image est assez dézoomée pour ne pas déborder des bords du téléphone.
3. Regarder aussi les 3 miniatures `covers/`.
4. Corriger et refaire ce qui ne va pas.

## 6. Programmer et noter

1. Programmer avec `python3 tiktok_engine/zernio.py schedule work/tiktok/<nom> --at AAAA-MM-JJTHH:MM --cover <n>` :
   - l'heure est celle de Bruxelles ;
   - `<n>` est la miniature recommandée.
2. Copier `work/tiktok/<nom>/zernio.json` dans `tiktok_engine/videos/<nom>/`.
3. Copier aussi `livraison.txt` (lien Gofile) dans `tiktok_engine/videos/<nom>/`.
4. Ne pas toucher au README : plusieurs sessions peuvent tourner en même temps.
5. Faire le commit (message en anglais), puis `git pull --rebase origin main` et pousser sur `main`.
   Réessayer si le push est refusé. Les vidéos, elles, restent hors de git.
6. Résumé de fin, en français, en 4 lignes : sujets, heures programmées, crédits Algrow utilisés,
   problèmes éventuels.
