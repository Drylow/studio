# Routine quotidienne Octave Histoire (@octave.histoire)

Lancée chaque jour vers 9 h (heure de Bruxelles), dans une session neuve. Elle fabrique **2 vidéos**
et les programme sur TikTok par Zernio : la première **aujourd'hui à 19 h**, la seconde **demain à 7 h**.
Lire d'abord [README.md](README.md) : style, règles de l'utilisateur, moteur. Faits réels uniquement.

## 0. Préparer

- `git pull origin main`, puis `bash tiktok_engine/setup.sh` (qui doit afficher « prêt »).
- `python3 tiktok_engine/zernio.py accounts` doit montrer le compte TikTok. Sinon, arrêter et écrire
  le problème dans le résumé de fin.
- **Créneaux déjà pris** : chaque vidéo programmée a son `tiktok_engine/videos/<nom>/zernio.json`
  (champ `at`). Si un dossier a déjà `at` = aujourd'hui 19:00 ou demain 07:00, ce créneau est fait :
  ne pas le refaire. Si les deux sont pris, terminer.

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
- Environ 1 min 20, avec « vous ». **Pas d'outro** : la vidéo s'arrête sur sa chute.
- `caption` : une phrase et 4 hashtags, sans émoji ni sources.

## 3. Images (Algrow, 1 crédit l'image)

1. Lancer `.venv/bin/python tiktok_engine/art.py algrow tiktok_engine/videos/<nom>/script.json`.
   Il passe par l'API, avec la clé `ALGROW_API_KEY` de l'environnement, donc sans autorisation à donner.
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
3. Ajouter la ligne de la vidéo dans la table « Vidéos livrées » du README, avec son lien Gofile.
4. Faire le commit (message en anglais) et pousser sur `main`. Les vidéos, elles, restent hors de git.
5. Résumé de fin, en français, en 4 lignes : sujets, heures programmées, crédits Algrow utilisés,
   problèmes éventuels.
