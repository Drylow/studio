# Drylow Studio — guide pour Claude (à lire en entier avant de travailler)

Studio YouTube faceless (Flask, Python) qui fabrique des vidéos 2D de bout en bout : recherche, script,
voix, images, montage animé, rendu, miniature, publication. Ce fichier dit **comment on travaille ici**,
pour qu'une nouvelle session (ou le compte d'un collègue) continue exactement pareil.

## 1. L'utilisateur et la façon de lui parler

- Il parle **français, familier** (« frérot », souvent dicté à la voix, donc parfois haché). Réponds en
  français, simple, court, direct. Pas d'anglais, pas de jargon, pas de pavé.
- Il est souvent sur téléphone : statut en une ligne quand il demande « ça dit quoi ? ». Donne des heures
  (UTC) et des chiffres concrets (images 86/123, rendu en cours…).
- Il décide des titres, miniatures et du calendrier ; propose 2-4 options visuelles (planches d'images),
  recommande-en une, puis applique son choix sans redemander.
- **Git : commit + push après chaque changement, sans qu'il ait à le demander** (voir §8). Ne lui dis
  jamais que « c'est local » ou que tu « ne peux pas pousser ».

## 2. Règles absolues

1. **Jamais une vidéo envoyée sans l'avoir vérifiée image par image** (§5). Une erreur à l'écran (ticket faux,
   chiffre jamais dit, texte bizarre) l'oblige à supprimer une vidéo programmée : c'est arrivé, plus jamais.
2. **Un lien envoyé = un seul lien, le bon, marqué clairement** (« KIDS CORRIGÉE – à poster »). Ne cite pas
   l'ancien lien dans le même message.
3. **Secrets** : clés (IA, Algrow, ai33pro) et webhook Discord seulement dans `.env` (ignoré par git). Jamais dans le
   code, les commits ou les messages. Avant un push, vérifie qu'aucun secret n'est dans le diff.
4. Jamais de nom de modèle d'IA dans les commits, le code ou les fichiers du dépôt.
5. Faits réels uniquement (sources nommées dans la phrase) ; un chiffre incertain est coupé ou présenté
   comme une estimation. Jamais de mode d'emploi pour voler, frauder, contourner un verrou.
6. Personnes réelles : jamais comme personnages. Marques/ligues (UFC, WNBA…) OK **dans le titre** (usage
   descriptif) mais jamais de logos, ceintures/maillots officiels, vrais joueurs ou événements.
   Pareil pour les objets : pas de logo Mastercard/Visa, Apple, marque de voiture sur les images (à vérifier sur
   les planches ; sinon régénérer l'image avec `job_regen` et une consigne « no logos »).
7. Miniatures « sexy » : femme adulte, tenue de son univers (ex. tenue de combat), jamais explicite ; **jamais
   de sexualisation à côté d'un enfant ou d'un bébé** (refusé net). Trop sexy = risque de restriction d'âge
   YouTube : le dire une fois.

## 3. Les chaînes (modèles dans `services/pov_engine.py` → `TEMPLATES`)

Les trois chaînes partagent le même style 2D (bonshommes à grosse tête ronde blanche, yeux en points noirs,
mains en moufles ; style `osl_stick`) et la même voix Algrow. Studio web : `/tools/osl-studio?studio=<clé>`.

| Clé | Chaîne | Format | Miniature validée |
|---|---|---|---|
| `oddly_specific_en` | **Oddly Specific Lives** (@OddlySpecificLives) | « POV: You Marry a … / Fall in Love with a … » (`pov_marry`), variante « Inside the Life of » (`pov_life`) | BD colorée : la femme 3/4 corps, contour blanc, monument du pays + drapeau en haut à gauche, bouquet de roses. **Pour un sport : dans son décor (cage, parquet), sans roses**, en tenue de son sport, ceinture/trophée sans logo, un peu de sueur. **Une femme différente à chaque vidéo** (visage, peau, cheveux : jamais la même que la miniature de référence ni qu'une vidéo précédente), bien sexy (jamais explicite). **Drapeau + monument seulement pour une nationalité** ; pour un métier (assassin…), tout est dans son monde : décor (planque, armurerie…), ses vrais outils, pas de ville touristique ni de gadget « mignon » (mallette de fusil remplie de roses : refusée, 3 oct.). |
| `oddly_expensive_en` | **Oddly Expensive Lives** | « The Economics of … » : le prof explique la facture ligne par ligne, ticket de caisse (« running tab ») | façon Marcus : fond plan bleu, gros titre noir contour blanc souligné rouge, le prof à droite, 1-2 humains BD à gauche (**différents à chaque vidéo**), étiquettes chiffrées + flèches |
| `oddly_things_en` | **Oddly Specific Things** — « Some things live oddly specific lives. » | « Your Life as a Stolen … » (`object_journey`) : TU es l'objet, suivi de main en main (cartes « HAND #n », trajets animés) | très simple (`presets/oddly_things_en/thumb.jpg`) : fond gris clair, une main moufle blanche (manche verte) tient l'objet, une main gantée noire l'arrache, traits jaunes, énorme mot noir arrondi en haut (STOLEN). **Varier l'action à chaque vidéo** (demande de l'utilisateur : « ça commence à faire répétitif ») : même style, mais une scène différente (arraché sous la voiture, pesé contre du cash, pêché dans un portefeuille, cadenas coupé vide, mis en carton, tir à la corde, grue + conteneur…) **et le mot du haut** (pas toujours STOLEN : un mot-clé de l'histoire, ex. SNATCHED, SOLD, PRECIOUS, GONE, SHIPPED, FOR SALE, CLONED, DRAINED ; retouche du mot seul : `thumb.py --edit`) ; proposer 3-4 variantes en planche |

**Dossier `chaines/`** : une fiche par chaîne (concept, style, ce qui marche, idées de vidéos — écrite à la
main) et, pour chaque vidéo, script, recherche, publication et miniature (générés par
`python production/export_channels.py` : le relancer après chaque vidéo, puis commit).

Références : `presets/<clé>/` (style.jpg = style des images, thumb.jpg = style de miniature), bibles de
style dans `TEMPLATE_BIBLES`, vidéos de référence dans `skills/references/<id YouTube>.txt`.

**Oddly Specific Things — images (validé par l'utilisateur, oct. 2026)** : l'objet narrateur (« You ») est un
**vrai objet sans visage** (ni yeux ni bouche : un smiley sur un téléphone « fait bizarre »), à taille réaliste ;
son humeur passe par ce qui lui arrive (écran, fissures, sachet alu, carton) et par les visages autour. Le reste
du style de la chaîne ne change pas (`osl_stick`, décors riches) : c'est l'option qu'il a choisie. Appliqué via
`style_rev` du modèle : seules les vidéos créées après ce changement le prennent (`_with_style_rev`), une vidéo
déjà lancée garde son style d'origine. Le contrôle en vision refuse un objet avec un visage.
**Dans les prompts, l'objet reste un objet** (sinon : smiley sur la calandre, carte transformée en humain,
voiture dans une voiture, bras en trop) : le rédacteur de prompts l'appelle par son nom (« the stolen car »,
`object_noun`), jamais « You » ; il ne fait aucune action (on décrit ce qu'on LUI fait) ; un seul exemplaire
par image ; « à l'intérieur » = l'habitacle, jamais une 2ᵉ voiture ; les données = une vraie scène (écran
flou, reçu). Son image de référence est décrite comme un objet, pas comme un personnage. Les persos ont
deux bras, deux mains. Tout ça dans `pov_engine.py` (`_prompt_batch`, `_style_parts`, `build_image_prompt`,
`detect_cast`, `check_image`), actif pour les vidéos sans visage (`faceless_object`).

Idées de vidéos : vérifier la demande et la concurrence avec les outils NexLev (youtube_search,
youtube_channel_outliers sur la chaîne et ses concurrents) avant de proposer. Ce qui marche sur OSL :
nationalités (Russian 102k, Latina 85k, Indian 70k) et femmes « dangereuses / hors norme » (Yakuza 117k,
Serial Killer 68k). Sports (UFC, WNBA…) : nouvelle série, nom de la grande ligue dans le titre.

## 4. Produire une vidéo (dossier de travail = `$STUDIO_WORK`, défaut `work/`, ignoré par git)

```bash
# 0. recherche : faits vérifiés (web), écrits dans work/<chaîne>/<vidéo>/notes.txt
#    (« VERIFIED FACTS … », puis « STORY SHAPE / RUNNING TAB … », puis « RULES … ») — voir les notes existantes
python production/new_video.py oddly_things_en work/ost/watch "Your Life as a Stolen Watch"
echo "ost/watch --gate" >> work/active.txt          # dossier relatif + options de pipeline.py
production/supervisor.sh                             # en tâche de fond SUIVIE (Bash run_in_background)
```

`pipeline.py` enchaîne : script FacelessOS + audit → **relecture** (avec `--gate`) → voix, persos, plan de
montage, images → contrôle images en vision → rendu (un par dossier de chaîne, verrou `render.lock`) →
Gofile (md5 vérifié) → `verify.py` → **attente de `review_ok`** → paquet Discord. Chaque étape a son log et
son marqueur (`AUDIT DONE`, `PROD DONE`, `QA DONE`, `RENDER DONE`, `ALL DONE`) : relancer reprend où ça en était.

- **Relire le script** (`script.txt`) : pas de vrais joueurs/équipes, rien de sexualisé, chiffres = notes,
  pas de phrases méta (« this story is constructed »), titres de parties propres (pour OST : « Hand N: … »
  donne une carte, les autres parties pas de numéro). Corriger le fichier, puis
  `python production/steps.py save <dossier>` et `touch <dossier>/script_ok`.
- **Miniature** : `production/thumb.py` avec la référence de la chaîne, 2-4 variantes en planche, le choix
  de l'utilisateur va dans `<dossier>/thumb_choice.txt` (chemin absolu).
- Durée par défaut 14 min. Une vidéo prend ~1 h 30 à 2 h (images ≈ 4-5/min, rendu ≈ 25 min).

## 5. Vérifier avant d'envoyer (obligatoire)

`verify.py` écrit `check/report.txt` (contrôles automatiques : ticket juste de bout en bout, chiffres
affichés = chiffres dits, intro) et `check/fx_*.jpg` (une image par animation). **Regarde toutes les
planches** : intro, tickets (total juste, pas de ligne « Running total »), compteurs, cartes HAND, trajets,
textes coupés, images absurdes. Doute sur une capture ? extraire 3-4 images autour avec ffmpeg
(`imageio_ffmpeg.get_ffmpeg_exe()`). Seulement ensuite : `touch <dossier>/review_ok`.

## 6. Publication

- Vidéo sur **Gofile** (lien `gofile_link.txt`), paquet sur **Discord** via `production/discord_send.py`
  (lien + miniature, titre, description + chapitres, tags, commentaire épinglé). Webhook :
  `DISCORD_WEBHOOK_URL` dans `.env` (à demander à l'utilisateur, jamais dans git).
- **Le paquet part en UN seul message à embeds** (couverture + miniature, description + chapitres, tags,
  commentaire épinglé) et un verrou (`$STUDIO_WORK/discord.lock`) fait passer les envois un par un : avant,
  deux vidéos envoyées ensemble mélangeaient leurs messages (Credit Card avec la description de Car).
  Vérifier sans poster : `python production/discord_send.py <dossier> <lien> --dry-run`.
- Donner aussi le lien dans le chat, avec le titre de la vidéo.
- Calendrier (oct. 2026) : Oddly Specific Lives MMA le 3 oct., basket le 4 oct. ; d'autres sports ensuite.

## 7. Environnement cloud : pièges connus

- **La machine redémarre souvent** (toutes les 40 min environ quand la session est inactive) et tue les
  processus. Toujours lancer `production/supervisor.sh` en tâche de fond suivie ; à la fin de la tâche
  (redémarrage), relancer `production/resume_all.sh` puis le superviseur. Programmer aussi un rappel
  (send_later) toutes les ~45 min tant qu'une production tourne.
- ffmpeg : fourni par `imageio_ffmpeg` (pas dans le PATH).
- Coupures réseau de l'IA (« IA injoignable ») : les étapes réessaient ; relancer suffit.
- `pgrep -f motif` se trouve lui-même si le motif est dans ta propre ligne de commande : vérifier les
  processus avec `pgrep -af` et lire le résultat.

## 8. Git

- **`main` est toujours à jour** : on travaille sur la branche de la session, et chaque commit est poussé
  sur cette branche ET sur `main` (avance rapide). **Commit + push après chaque changement**, sans attendre
  qu'on le demande. Installer le hook qui le fait tout seul :
  `cp production/git-post-commit .git/hooks/post-commit && chmod +x .git/hooks/post-commit`.
  Si `main` a avancé ailleurs : `git fetch origin main && git merge origin/main` avant de pousser.
- Messages de commit en anglais, courts, qui disent le « pourquoi ». Ne pas créer de PR sans qu'on le demande.

## 9. Carte du code

- `services/pov_engine.py` : chaînes/modèles (`TEMPLATES`, `TEMPLATE_BIBLES`), projets, jobs (script, voix,
  casting, images + contrôle en vision, réalisateur du montage `plan_montage`, cartes de partie
  `chapter_card`, ticket juste `check_receipts`, rendu, métadonnées, miniatures).
- `services/pov_script.py` : formats (`FORMATS`), écriture FacelessOS (recherche, hooks, plan, rédaction,
  audit « greenlight »).
- `services/motion.py` : animations à l'écran (counter, receipt, label, stamp, list, timeline, bars, pie,
  split, sheet, route, chapter, intro, outro). `services/render.py` : montage ffmpeg (calques, fondus,
  durées min. des cartes). `services/tts.py` : voix (Algrow). `services/ai.py` : texte + images.
- `production/` : scripts de production sans surveillance (ce guide). `production/VIDEOS.md` : journal des
  vidéos livrées et en cours — **le tenir à jour** à chaque livraison.
- **History Docs** (format à part, §10) : `services/history.py` (pipeline + montage), `history_ai.py`
  (script, plan visuel, styles d'image), `history_geo.py` (cartes), `history_sources.py` (vraies archives),
  `history_audio.py` (musique + bruitages), `align.py` (Whisper), `routes/history.py`,
  `tool_apps/history-studio/`, moteur Remotion `history_engine/`.

## 10. History Docs (format Histoire, `/tools/history-studio`)

Documentaires d'histoire façon *Dose of History* (vidéo de référence analysée : narration à la 2ᵉ personne,
images + quelques animations). **Deux chaînes** (fiches et kit YouTube dans `chaines/`) :
**The Survivor's Account** (`survivors_account`, @SurvivorsAccount : un vrai témoin par vidéo, ses mots cités
mot pour mot) et **Frontier Blood** (`frontier_blood`, @FrontierBlood : la frontière américaine). Config :
`services/history_channels.py` + `presets/history_channels/<clé>/` (idées, images de miniature, bible).
Script : **FacelessOS** (format `history_doc`, référence de voix `skills/references/EDGm3821yE8.txt`) + 2 tours
d'audit en plus ; recherche avec les vraies sources (mémoires du domaine public) dans les notes.
Indépendant des chaînes 2D : ne pas mélanger avec `pov_engine.py`. Détail des étapes et des
templates : section History Docs du `README.md`.

- **Pipeline** : script → voix (ElevenLabs via ai33pro, **Earl** à 0,9 validé par l'utilisateur ; `AI33_API_KEY`) → sous-titres calés par Whisper local sur
  l'orthographe du script → plan visuel IA + passe « monteur image » (variété des plans) → images (portraits
  du casting d'abord, puis plans avec le portrait en référence) → `build_timeline` → rendu Remotion
  (`history_engine/render.mjs`) → loudnorm -14 LUFS. Projets dans `data/history/<id>/`.
- **Production sans surveillance** (comme §4) : script relu → `python production/history_video.py new
  work/<chaîne>/<vidéo> <clé> <script.md>` puis `echo "<chaîne>/<vidéo>" >> work/active.txt` (le superviseur
  lance `history_video.py run` : voix → plan → images → rendu → miniature → Gofile → planches `check/sheet_*.jpg`
  (un plan par vignette) → **attente de `review_ok`** → paquet Discord comme les vidéos POV ; réessaie si l'IA sature).
  Le rendu se fait **par morceaux** de 30 s (`render.mjs --chunk-dir`, `CHUNK_FRAMES`) : un redémarrage reprend
  au morceau suivant. **Rendu pas cher** (l'utilisateur : « drain pas ma balance », « 2 $ c'est trop ») : la machine
  cloud rend gratuitement (≈ 11 images/s sur 4 cœurs, x264 `veryfast` : une vidéo de 36 min ≈ 1 h 40 seule), du dernier
  morceau au premier, pendant qu'**une seule** machine RunPod de 32 cœurs (`RUNPOD_PODS`, défaut 1) part du premier
  (`services/runpod_render.py`) ; ils se rejoignent au milieu (marques `claim_XXX.rp/.local`), le son se fait en local.
  ≈ 0,3-0,5 $ par vidéo au lieu de ~2 $ (avant : 8 machines, surtout payées à démarrer). La machine RunPod est
  **toujours supprimée** (même après un rendu interrompu, notée dans `chunks/pods.json`).
  **VPS de l'utilisateur (gratuit, 18 vCPU EPYC, 94 Go)** : prioritaire sur RunPod quand `RENDER_WORKERS` (URL https)
  et `RENDER_WORKER_TOKEN` sont dans le .env ; installé par `python production/vps_setup.py` → `work/vps_setup.sh`
  (à lancer en root sur le VPS : Docker + serveur de rendu derrière Caddy, `<ip>.sslip.io`, jeton). Une vidéo à la
  fois sur le VPS (`work/vps0.lock`). **Depuis le 2 oct. (« utilise 100 % le VPS ») : tout le rendu va sur le VPS**
  (morceaux + son ; `RR.vps_only`), une 2e vidéo attend son tour ; la machine cloud ne fait que l'assemblage final
  (ffmpeg, -14 LUFS) et ne rend en local que si le VPS tombe. `RENDER_LOCAL=1` remet l'ancien mode mixte.
  Serveur des pods : `production/runpod_worker.js`.
- **Rendu Remotion** : Node 18+ ; `npm install` se fait tout seul au 1er rendu. Dans le cloud :
  `REMOTION_BROWSER=/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell` (ne pas
  télécharger Chrome) et `REMOTION_CONCURRENCY=4` ; une vidéo de 3-4 min ≈ 15-25 min de rendu.
- **Tester sans dépenser** (ni IA ni voix) : écrire un `timeline.json` à la main (contrat dans
  `history_engine/src/schema.ts`) et sortir des images fixes :
  `node history_engine/render.mjs --project <dossier> --stills "5,12.5" --stills-dir <dossier>/st`.
  Toujours **regarder** ces images avant d'annoncer qu'une animation est prête.

Ce que l'utilisateur a validé (ne pas revenir en arrière sans qu'il le demande) :
- **Peu d'animations** (1,5 par minute max, types variés). **Bataille, graphique et itinéraire désactivés
  par défaut** : il n'en veut pas (trop d'animations le gênait). Il **adore les citations** synchronisées
  mot à mot avec le portrait à droite.
- Une animation reste à l'écran **jusqu'au bout puis tient** (`CARD_MIN` dans `history.py`) : jamais
  coupée avant d'être finie.
- **Style dessiné par défaut** (encre & aquarelle, thème parchemin cohérent dans les animations) ; BD,
  peinture et photoréaliste au choix. Pas trop sombre (voile léger).
- **Époque exacte sur chaque image** (`period` du projet, calculée une fois par `period_brief`) + contrôle en
  vision `check_shot` (autre époque, bras en trop, texte, gore en gros plan) : image refaite une fois si ratée.
  Sans ça, Gettysburg avait des tuniques rouges, des shakos, des légionnaires et des casques de 1940.
- **Variété des images** : pas deux chevaliers qui regardent dans le même sens à chaque plan (les plans copient
  le regard du portrait de référence : `_balance_gaze` mesure le sens du regard de chaque plan en vision et
  retourne en miroir celui qui regarde du même côté que le précédent ; Gettysburg : 86 à droite / 30 à gauche
  avant, 58 / 58 après) ; au moins la
  moitié des plans sans personnage, un seul personnage de référence par plan, jamais de collage/split.
- **Regards vers la caméra aussi** (l'utilisateur, 2 oct. : « pourquoi ils regardent que à gauche ou à droite ») :
  les portraits de référence sont de face, et un plan à personnage sur deux regarde la caméra (`_vary_gaze`).
- **Pas d'images « goofy »** : réalisme documentaire (`REALISM` dans `history.py`, règles du plan et du monteur
  image) : objets à leur vraie taille, architecture et paysage du lieu exact (`period_brief` les décrit), rien de
  surréaliste ; `check_shot` refuse aussi les objets démesurés et les décors d'un autre pays (Gettysburg avait un
  obus géant dans un mur et une cathédrale gothique).
- **Plans d'une autre époque** (fouilles, musée, étude moderne, le témoin qui écrit des années plus tard) : le plan
  visuel écrit l'année en tête du prompt (« In 1748, … ») et `_shot_period` remplace alors l'ancre d'époque du récit
  par cette année (génération + contrôle en vision) ; sinon Pompéi avait des Romains en toge aux fouilles de 1748 et
  à l'étude ADN de 2024.
- **Jamais de tête coupée** : recadrage ancré en haut, zooms sans mouvement vertical.
- **Texte toujours lisible** sur les images claires (plaques sombres, bande sous les sous-titres).
- **Sous-titres exacts** sur toute la durée (orthographe du script, timings Whisper).
- **Cartes de mouvements propres** : une seule flèche par armée, la pointe s'arrête avant la ville/le
  marqueur, lieux trop proches fusionnés, noms placés automatiquement (`_layout_map_labels`) pour
  qu'aucune flèche, marqueur ou cartouche ne recouvre un texte.
- Vraies images d'archive (The Met, Wikimedia Commons) quand elles existent, image IA en secours.
- **Miniatures History** façon Dose of History (`job_thumbnail`, 3 variantes jointes au paquet Discord) : une peinture
  saturée, un personnage face caméra, 2-3 mots blancs avec le mot fort en rouge. **Jamais de portrait noir et blanc
  en médaillon** (l'utilisateur, 3 oct. : « tête goofy superposée, on n'en veut pas du tout »).
- Rendus envoyés sur **Gofile** (un seul lien, le bon).

Pièges connus : **disque** (allocation fixe ~38 Go) : chaque appel de `render.mjs` copie les médias dans
`/tmp/remotion-webpack-bundle-*` (~300 Mo) ; il les efface maintenant à la sortie, mais après un redémarrage brutal
vérifier `df -h /` et supprimer les vieux `/tmp/remotion-webpack-bundle-*` (le 2 oct. : disque plein, rendu en échec).
Wikimedia Commons répond 429 depuis le cloud (marche sur PC) ; l'API Hugging Face aussi,
donc `align.py` télécharge le modèle Whisper par URL directe dans `data/models/` ; les côtes Natural Earth
(~17 Mo) sont téléchargées une fois dans `data/geo/`.

## 11. Actu sport (format Fight Night MMA) : `services/newsvid*.py`, `production/news.py`

Un seul outil pour toutes les chaînes d'actu (MMA d'abord, puis boxe, foot…) : config par chaîne dans
`newsvid.CHANNELS` (nom affiché, couleurs, voix Algrow, sources). Une vidéo = 15-20 min de **vraies interviews
du jour** (podcasts, conférences, émissions) reliées par une voix off neutre de 2-3 phrases (≈ 20-25 %),
ouverture de ~60 s sans voix off (les phrases chocs), fin « drop your thoughts below ». Format analysé :
`chaines/_nouvelles/README.md` (référence `skills/references/W7ey58X8lJs*.txt`).

- **YouTube bloque le cloud** (téléchargement vidéo et vite les sous-titres) : dans le cloud on prépare, le **PC
  de l'utilisateur monte** (`NEWS_PC.bat` = `python production/news.py pc` : git pull, télécharge, voix off,
  montage, Gofile, **supprime tous les clips** — demande de l'utilisateur —, git push de `result.json` + planches
  `check/sheet_*.jpg` + `build.log`). Transfert PC → cloud par Gofile/hébergeurs : refusé, ne pas chercher.
- **Préparer une vidéo (cloud)** : sources trouvées avec NexLev (`youtube_search` upload_date today/week,
  sort date), **jamais les compilations des concurrents** (Fight Night met de vieux extraits hors contexte : on
  ne copie pas ça), seulement les originaux (podcast, chaîne du combattant, conférence). Transcriptions NexLev
  `get_bulk_video_transcripts` (le fichier enregistré) → `news.py new` / `import` (+ meta.json : titre, chaîne,
  date) → `moments` → `plan --context "faits vérifiés"` → **relire plan.json** → `voice` → `thumb` → commit.
- **Relire le plan** : chaque voix off colle à son extrait ; pas de mots lus présentés comme dits par la
  personne citée (le message de Topuria lu sur Flagrant) ; pas d'extrait rejoué d'une autre émission quand
  l'original est là ; l'ouverture n'utilise pas les extraits du corps ; extraits ≤ 50 s (`MAX_CLIP`), coupés sur
  des phrases entières (`clip_spec`) ; titres = **clickbait léger** : la citation entre guillemets est vraiment
  dite (vérifié par le code, `quote_in`). `plan_raw.json` permet de corriger puis `materialize` sans l'IA.
- **Vrai montage, pas des clips collés** (l'utilisateur, 3 oct. : « si c'est juste coller des clips, ça sert à
  rien ») : volet penché aux couleurs de la chaîne + whoosh entre chaque partie, logo animé (« CAGE DISPATCH /
  DAILY MMA NEWS ») après l'ouverture, nom de qui parle (glisse, en haut à gauche du cadre), **citation choc en
  grand** (Anton, mot fort en jaune, zoom « punch-in » + impact) au moment où elle est dite (`seg["quote"]`, calée
  par `clip_spec`), voix off : titre de l'info (`headline`) + nom + fil d'actu qui défile (`plan["ticker"]`, écrits
  par `news.py headlines` : rien que ce que dit la voix off) + b-roll en zoom lent ; rappel d'abonnement une fois.
  Anton s'affiche ~40 % plus petit que sa taille ASS : vérifier les tailles sur des images fixes. L'ouverture ne
  rejoue jamais un passage du corps (`materialize` le retire) et **vérifier qui parle vraiment** dans un teaser
  (l'animateur qui relit une vieille interview ≠ le combattant).
- **Montage sur le VPS (prioritaire, rien à faire pour l'utilisateur)** : serveur `production/news_worker.py`
  (Docker, HTTPS, jeton) installé par une ligne en root sur le VPS : `curl -fsSL
  https://raw.githubusercontent.com/drylow/studio/main/production/vps_news_setup.sh | bash` (script généré par
  `vps_news_setup.py` : le régénérer et committer après chaque changement du serveur). `NEWS_WORKER_URL` +
  `NEWS_WORKER_TOKEN` dans `.env`. `news.py vps-check` (YouTube accepte-t-il le VPS ?), `news.py vps <dossier>`
  (envoie code + plan + voix off, suit le montage, rapatrie `result.json`, `build.log`, `check/sheet_*.jpg`).
  Le VPS efface clips, segments et vidéo après l'envoi Gofile. SSH est fermé depuis le cloud : HTTPS seulement.
  VPS du pote de l'utilisateur (`news.13-140-129-97.sslip.io`, 3 oct.) : YouTube le bloque aussi (« Sign in to
  confirm you're not a bot ») → proxy résidentiel Decodo (choisi par eux, payé au Go) **pour yt-dlp seulement**
  (`YTDLP_PROXY`, ou `HTTPS_PROXY` que le serveur retire de l'environnement général : Gofile, pip, deno passent en
  direct). IP « sticky » obligatoire (les liens vidéo de YouTube sont liés à l'IP). ~1,2 Go par vidéo de 18 min.
  Les IP « ISP » de Decodo (`isp.decodo.com`) sont bloquées elles aussi (testé 3 oct., 5 clients yt-dlp) : essayer le
  pool résidentiel en session sticky, sinon `cookies.txt` d'un compte YouTube **jetable** (risque de blocage du
  compte) : `docker cp cookies.txt drylow-news:/data/cookies.txt`, le serveur le prend tout seul (`--cookies`).
- **Deux Claude, un dépôt** : le Claude du cloud prépare (même PC éteint) et marque la vidéo prête
  (`news/<chaîne>/<vidéo>/ready`, après relecture du plan) ; le **Claude du PC** (app Claude Desktop, onglet Code,
  dossier = clone de `drylow/studio`) monte avec **`/monter`** (`.claude/skills/monter/SKILL.md`) et pousse le
  résultat. `news.py pc` ne monte que les dossiers `ready`, 3 essais max par vidéo (`work/news_attempts.json`).
- **Sans Claude sur le PC : dossier autonome** (son studio PC vient d'un zip, pas de git) : `standalone/news_pc/`
  (« Monter les videos.bat » + `monter.ps1`), envoyé en zip. Il installe tout dans son dossier (Python embarqué,
  Git portable, deno), clone le dépôt public dans `studio\`, demande la connexion GitHub au début (pour le push du
  résultat), puis lance `news.py pc`. Python embarqué = mode isolé : pas de PYTHONIOENCODING, `open()` en cp1252
  (toujours `encoding="utf-8"`), le dossier du script n'est pas dans sys.path (ajouté dans le `._pth`).
- **Après le montage PC** : `git pull`, regarder `check/sheet_*.jpg` (+ `build.log`), puis
  `python production/news.py send <dossier>` (Discord) seulement si tout est bon.
