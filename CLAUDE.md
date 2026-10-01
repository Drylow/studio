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
3. **Secrets** : clés (IA, Algrow) et webhook Discord seulement dans `.env` (ignoré par git). Jamais dans le
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
| `oddly_specific_en` | **Oddly Specific Lives** (@OddlySpecificLives) | « POV: You Marry a … / Fall in Love with a … » (`pov_marry`), variante « Inside the Life of » (`pov_life`) | BD colorée : la femme 3/4 corps, contour blanc, monument du pays + drapeau en haut à gauche, bouquet de roses. **Pour un sport : dans son décor (cage, parquet), sans roses**, en tenue de son sport, ceinture/trophée sans logo, un peu de sueur. **Une femme différente à chaque vidéo** (visage, peau, cheveux : jamais la même que la miniature de référence ni qu'une vidéo précédente), bien sexy (jamais explicite). |
| `oddly_expensive_en` | **Oddly Expensive Lives** | « The Economics of … » : le prof explique la facture ligne par ligne, ticket de caisse (« running tab ») | façon Marcus : fond plan bleu, gros titre noir contour blanc souligné rouge, le prof à droite, 1-2 humains BD à gauche (**différents à chaque vidéo**), étiquettes chiffrées + flèches |
| `oddly_things_en` | **Oddly Specific Things** — « Some things live oddly specific lives. » | « Your Life as a Stolen … » (`object_journey`) : TU es l'objet, suivi de main en main (cartes « HAND #n », trajets animés) | très simple (`presets/oddly_things_en/thumb.jpg`) : fond gris clair, une main moufle blanche (manche verte) tient l'objet, une main gantée noire l'arrache, traits jaunes, énorme mot noir arrondi en haut (STOLEN) |

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
images + quelques animations). Pas de chaîne pour l'instant : on règle le format sur des démos (Hastings,
Cannae). Indépendant des chaînes 2D : ne pas mélanger avec `pov_engine.py`. Détail des étapes et des
templates : section History Docs du `README.md`.

- **Pipeline** : script → voix (Algrow, Timothy par défaut) → sous-titres calés par Whisper local sur
  l'orthographe du script → plan visuel IA + passe « monteur image » (variété des plans) → images (portraits
  du casting d'abord, puis plans avec le portrait en référence) → `build_timeline` → rendu Remotion
  (`history_engine/render.mjs`) → loudnorm -14 LUFS. Projets dans `data/history/<id>/`.
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
- **Variété des images** : pas deux chevaliers qui regardent dans le même sens à chaque plan ; au moins la
  moitié des plans sans personnage, un seul personnage de référence par plan, jamais de collage/split.
- **Jamais de tête coupée** : recadrage ancré en haut, zooms sans mouvement vertical.
- **Texte toujours lisible** sur les images claires (plaques sombres, bande sous les sous-titres).
- **Sous-titres exacts** sur toute la durée (orthographe du script, timings Whisper).
- **Cartes de mouvements propres** : une seule flèche par armée, la pointe s'arrête avant la ville/le
  marqueur, lieux trop proches fusionnés, noms placés automatiquement (`_layout_map_labels`) pour
  qu'aucune flèche, marqueur ou cartouche ne recouvre un texte.
- Vraies images d'archive (The Met, Wikimedia Commons) quand elles existent, image IA en secours.
- Rendus envoyés sur **Gofile** (un seul lien, le bon).

Pièges connus : Wikimedia Commons répond 429 depuis le cloud (marche sur PC) ; l'API Hugging Face aussi,
donc `align.py` télécharge le modèle Whisper par URL directe dans `data/models/` ; les côtes Natural Earth
(~17 Mo) sont téléchargées une fois dans `data/geo/`.
