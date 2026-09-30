# Drylow Studio

Studio YouTube local (Flask). L'outil principal, **2D Videos** (`/tools/pov-studio`),
fait des vidéos faceless en 2D façon TubeGen, entièrement sur ta machine.

## Installation (PC)

- Python 3.10+
- Rien d'autre : ffmpeg est fourni par `imageio-ffmpeg`. Pour utiliser un ffmpeg
  à toi, renseigne `FFMPEG_BIN`.

```bash
python -m venv venv
venv\Scripts\activate          # Windows  (Linux/Mac : source venv/bin/activate)
pip install -r requirements.txt
```

Copie `.env.example` en `.env`, puis remplis au minimum :

```env
FLASK_SECRET_KEY=une-longue-chaine-aleatoire
ACCESS_PASSWORD=...            # mot de passe guest
BOSS_PASSWORD=...              # mot de passe boss (accès aux outils)
AI_BASE_URL=https://.../v1     # proxy OpenAI-compatible (CLIProxyAPI / comptes Codex)
AI_API_KEY=...
```

Lance `START_STUDIO.bat`, ou `python app.py`, puis ouvre `http://127.0.0.1:5000`.
Passe en mode boss sur l'écran d'accueil (triple-clic sur サムライ) et entre le
mot de passe boss.

## 2D Videos : le pipeline

1. **Chaîne.** C'est l'ADN de toutes ses vidéos :
   - langue et niche ;
   - format de script : Every Rank, Your Life If…, Ancient Life, Survie, Every X Explained, Histoire, Top ;
   - **vidéo de référence du format** : une vidéo populaire de la niche (lien YouTube ou transcription
     collée). L'app en tire une analyse FacelessOS (hook, découpage en % de la durée, rythme, dialogues,
     fin) et garde un extrait mot pour mot de la narration comme « ancre de voix ». Le style est repris,
     jamais le contenu. Sans référence, le script reste dans le ton de la chaîne ;
   - direction artistique : prompt de style, image de référence, description automatique depuis des captures ;
   - personnages récurrents avec fiche perso ;
   - voix, rythme et montage par défaut.

   - mise en page « tableau » optionnelle avec un prof animé (voir plus bas).

   Des modèles prêts à l'emploi viennent d'une étude NexLev des chaînes 2D en forte croissance.
   Par exemple, **Business Explained** reprend le format de Marcus Explains (« How X Actually Makes
   Money ») : bible d'écriture tirée de ses transcriptions, persos blancs à tête ronde, fond ardoise
   bleu nuit et prof à tête blanche animé.
   L'assistant **🧪 Niche bending** prend un format qui marche et propose des niches transposées
   (moins saturées ou mieux payées), avec des titres. La chaîne se crée d'un clic.
2. **Script (méthode FacelessOS).** Le pack FacelessOS v5.1 est dans `skills/facelessos/` et ses
   fichiers sont cités tels quels dans les prompts. Pour le mettre à jour, remplace le contenu du dossier.
   - **Research** : brief à 5 champs (angle, faits réels vérifiables, direction du hook, structure).
   - **Brainstorm** : 3 hooks sur 3 ouvertures différentes, notés contre la vidéo de référence et
     contre les ouvertures des dernières vidéos de la chaîne. Le meilleur est gardé.
   - **Structure** : plan avec boucles ouvertes/fermées, motifs, grand payoff annoncé 3 fois,
     choix de rotation (variety-rotation) différents de ceux des derniers scripts.
   - **Write** : section par section, ancré sur l'extrait de la vidéo de référence.
   - **Greenlight** : audit A à E (hook, rétention, fil rouge, voix + anti-slop, authenticité)
     plus le scanner d'origine `trailer-voice-scan.py`. Les fixes sont appliqués, puis l'audit
     complet repasse, jusqu'à 3 fois (`FOS_MAX_ROUNDS`). Un HOLD renvoie au plan une fois.
   - Le panneau « Audit FacelessOS » montre le verdict, chaque passe et ses fixes, le brief et
     les hooks proposés. Le bouton **🛡 Audit FacelessOS** relance la boucle sur un script collé
     ou retouché.
   - Tu peux éditer le script, le faire réécrire avec une consigne, ou restaurer une ancienne
     version depuis l'historique.
3. **Voix off.**
   - Fournisseurs : **Algrow** (voix ElevenLabs ou modèle Stealth, `ALGROW_API_KEY`), Edge TTS (gratuit),
     ElevenLabs ou OpenAI TTS (avec clé).
   - Algrow : les crédits restants s'affichent et « Écouter » joue l'extrait officiel de la voix, sans
     rien consommer. Les timings viennent du SRT d'alignement (ElevenLabs). Pour Stealth, ils sont
     estimés puis recalés sur les pauses de la voix.
   - Timings mot à mot et raccourcissement des silences.
   - Le débit réel de la voix est mesuré pour mieux viser la durée la fois suivante.
4. **Personnages de la vidéo** (persos consistants, façon TubeGen).
   - L'IA lit le script et fixe le casting : toi, elle, son père, sa grand-mère…
   - Chaque perso reçoit un look fixe (cheveux, tenue, couleurs, âge) et une image de référence
     dans le style de la chaîne.
   - À chaque scène, les images des persos présents sont envoyées au générateur. Ils gardent donc
     le même look du début à la fin.
   - Dans le storyboard, tu peux modifier la fiche d'un perso, régénérer ou importer son image,
     en ajouter ou en retirer, et cocher les persos présents dans chaque scène.
   - Tout se fait automatiquement au lancement des images si tu n'y touches pas.
5. **Storyboard.**
   - Scènes découpées sur les fins de phrases, avec un rythme réglable et un hook plus rapide.
   - Prompts écrits par un « directeur artistique » IA.
   - Images générées en parallèle, avec l'image de style et la fiche perso en référence.
   - Bouton « Tester le style » pour valider une première image avant tout le lot.
   - Par scène : refaire, éditer le prompt, importer ta propre image, choisir le mouvement de caméra.
6. **Export.**
   - **MP4 monté** : zoom/pan, fondus, sous-titres karaoké ou phrases, titres de section,
     musique baissée automatiquement sous la voix, voix normalisée à -14 LUFS (la musique reste
     constante, elle ne remonte pas pendant les pauses).
   - **Musique « auto »** : une piste de la bibliothèque par vidéo, très basse, baissée encore sous la
     voix. Si la bibliothèque est vide, 3 ambiances lofi 100 % originales sont générées (aucun
     risque de réclamation Content ID). Tu peux y ajouter des morceaux de la bibliothèque audio de
     YouTube Studio.
   - **Pack montage** : ZIP avec un clip par image dont la durée est exactement celle de sa
     phrase, plus la voix, le `.srt` et les timestamps. On glisse le tout dans CapCut ou Premiere
     et c'est calé.
   - **Miniatures** : 2 variantes dans le style de la chaîne, avec le perso et un texte court en gros.
   - **Métadonnées** : titres, description SEO, tags et chapitres horodatés.

## Studio Oddly Specific Lives (titre → vidéo)

Outil **ODDLY SPECIFIC LIVES** dans la barre de gauche : la version simple, pour sortir les vidéos
de la chaîne sans passer par les étapes.

- **Nouvelle vidéo** : le titre (ex. « POV: You Marry a Japanese Woman ») et la durée (curseur de 3
  à 30 min, ou les raccourcis 5 / 8 / 10 / 14 / 20 / 25). La durée fixe la longueur du script
  (158 mots par minute pour la voix de la chaîne). L'estimation affiche les mots, les images, les
  caractères Algrow et le temps de fabrication.
- **Format** : « Auto » le choisit d'après le titre. Un titre qui parle de mariage ou d'amour
  (« Marry », « Fall in Love », « Wife »…) prend le format **POV: You Marry**. Les autres
  (« Inside The Life Of… », « POV: You Become… ») prennent **Inside the Life of** : le spectateur EST
  la personne du titre, sa vie racontée en « you », avec la même voix, le même style et la même
  narration que la vidéo de référence. Le menu permet de forcer l'un ou l'autre.
- **Créer la vidéo** lance tout, dans l'ordre :
  1. script FacelessOS calé sur la vidéo de référence ;
  2. voix Algrow ;
  3. casting des personnages et images ;
  4. montage avec zoom doux, fondus et musique libre de droits.
- Chaque vidéo affiche sa progression. On peut fermer l'onglet, tout tourne côté serveur.
- Quand c'est fini : lecture dans la page et **Télécharger la vidéo**. Si ça s'arrête (quota, réseau),
  **Reprendre** repart de l'étape en cours sans refaire ce qui est fait.
- **✎ Éditeur** ouvre la vidéo dans 2D Videos pour retoucher le script, une image ou le montage.
- **Miniatures** :
  - Colle le lien d'une vidéo YouTube : sa miniature sert de modèle (composition, style, couleurs).
    Ajoute si tu veux des images de référence (perso, objet, style), un prompt, et choisis de 1 à 4 images.
  - Sans lien ni image, la miniature de référence de la chaîne sert de modèle.
  - **2 idées auto** : l'IA propose elle-même des concepts à partir du script.
  - Sur chaque miniature : **↻** la regénère (même prompt, mêmes références) à la même place,
    **🗑** la supprime, **⬇** la télécharge.
- **📝 Titre & description YouTube** (sous chaque vidéo finie) : générés automatiquement à la fin de
  la fabrication avec la skill packaging de FacelessOS, dans le style de tes descriptions. On y trouve
  le titre et 2 autres idées, la description, les tags (dans la limite de 500 caractères de YouTube)
  et un commentaire à épingler. Chaque champ a son bouton **📋 Copier**, et **↻ Regénérer** refait le tout.
- **Onglet Projets** : la place prise par chaque vidéo et le total.
  - **Alléger** supprime les clips de travail du montage. Ils pèsent à peu près autant que la vidéo
    finale. La vidéo, les images, la voix et les miniatures restent.
  - **Supprimer** efface tout le dossier de la vidéo, définitivement. Une vidéo en cours est d'abord
    arrêtée.
- La chaîne se crée toute seule au premier lancement, à partir du modèle `oddly_specific_en` :
  vidéo de référence, style (`presets/oddly_specific_en/style.jpg`), miniature modèle (`thumb.jpg`),
  voix Algrow et montage.

**Pour une future chaîne** : on crée son modèle dans `services/pov_engine.py` (`TEMPLATES`, avec son
style d'images, sa voix et sa vidéo de référence), ses images dans `presets/<modèle>/`, puis on
duplique `tool_apps/osl-studio` (ou on l'ouvre avec `?studio=<modèle>`) et on l'ajoute à
`routes/tools.py`.

## History Docs (format Histoire)

Outil **HISTORY DOCS** dans la barre de gauche. C'est un format à part des POV : des documentaires
d'histoire dans le style de *Dose of History*, à partir d'un titre et d'une durée.

**Prérequis en plus :** [Node.js](https://nodejs.org) 18+. Au premier rendu (ou au lancement de
`START_STUDIO.bat`), les dépendances du moteur d'animation s'installent dans `history_engine/`.

**Le pipeline** (côté serveur, reprise possible à chaque étape) :
1. **Script** : narration immersive à la 2ᵉ personne (date et lieu, « rien à voir avec les films »),
   phrases courtes, chiffres et sources réels, 153 mots/min comme la référence
   (`presets/history_doc/reference_excerpt.txt` sert d'ancre de style).
2. **Voix off** : Algrow (Timothy, Elliott, Connery) ou Edge gratuit, avec les timings mot à mot.
3. **Plan visuel** : l'IA choisit ce qu'on voit à chaque phrase. Dans le hook, une image toutes les
   ~5 s. Ensuite, des images de 12 à 20 s et environ 30 % d'animations calées sur la narration.
4. **Images** : portraits du casting d'abord, réutilisés comme références pour garder les mêmes
   visages. Puis plans photoréalistes (tons ocre, lumière dure, 35 mm), terrains vus du ciel,
   objets d'archive.
5. **Montage Remotion** (`history_engine/`) : zoom lent sur les images, animations, grain et rayures
   de pellicule, sous-titres (masqués pendant le hook), nappe musicale sombre et bruitages générés
   (aucun risque Content ID), mixage final à -14 LUFS.

**Les animations** (templates Remotion, `history_engine/src/templates/`) :

| Template | Ce qu'il montre |
|---|---|
| Phrase choc | serif en capitales, mots clés en rouge, flash au moment où le narrateur le dit |
| Bataille | terrain vu du ciel, blocs d'unités qui manœuvrent, étiquettes, ligne de front, titre et date |
| Fiche perso | portrait encadré, nom, rôle, 2-3 faits |
| Comparaison | fiche d'armée puis écran partagé A vs B |
| Graphique | barres qui montent avec les chiffres qui défilent |
| Archive | objet ou document encadré façon photo de musée |
| Itinéraire | ligne dorée tracée de ville en ville (vraies coordonnées), la caméra suit |
| Citation | citation révélée mot à mot à côté du portrait |

Aperçu et réglage des templates : `cd history_engine && npm run studio` (Remotion Studio).
Rendu à la main : `node history_engine/render.mjs --project <dossier media> --out video.mp4`.
Données : `data/history/<id>/` (vidéo finale à la racine, médias et `timeline.json` dans `media/`).

Variables utiles (`.env`) : `REMOTION_CONCURRENCY` (onglets de rendu en parallèle, défaut : moitié des
cœurs), `REMOTION_BROWSER` (chemin d'un Chrome à utiliser plutôt que celui téléchargé par Remotion),
`HISTORY_DATA_DIR`.

## Mise en page tableau et prof animé

Réglage par chaîne (section 4 de la fiche chaîne), puis par vidéo dans le montage :

- **Fond** : ardoise bleu nuit, graphite, noir et jaune, cahier jaune, papier millimétré, pois orange,
  tableau à craie, ou tes propres couleurs. Le fond est dessiné par le code, sans IA.
- **Panneau** : l'image de la scène est posée au centre avec un contour, des coins arrondis et une ombre.
  Le zoom lent reste à l'intérieur du panneau.
- **Prof animé** en bas à gauche, avec une animation 2D pose à pose :
  - l'IA dessine le prof en pied, baguette levée, sur fond transparent ;
  - elle redessine ensuite **uniquement son bras** dans 3 positions (mi-hauteur, pointé, tapotement) ;
  - seule la zone du bras est recollée, donc la tête, le corps et les pieds restent identiques au pixel près ;
  - une image de transition entre deux poses adoucit le mouvement.
- **Animation** calée sur la voix off : double tapotement vers le panneau sur les chiffres clés ($, %,
  nombres), et un geste « regardez ça » de temps en temps quand il parle. Au repos il ne bouge pas.
- **Pack montage** : chaque clip contient la mise en page et l'animation du prof. Le ZIP inclut aussi le
  fond et le prof en PNG séparés.

## Quotas du proxy

Les comptes Codex ont chacun une limite d'utilisation sur une fenêtre de quelques heures, et les images
en consomment beaucoup. Quand **tous** les comptes sont en pause, le proxy répond « model_cooldown » :

- **texte** : l'outil bascule automatiquement sur `AI_TEXT_FALLBACK` (Gemini par défaut) ;
- **images** : la génération s'arrête proprement avec l'heure de reprise. Ce qui est déjà fait est
  conservé, et « Générer les images » reprend là où ça s'est arrêté.

Tout est stocké dans `data/pov/` : chaînes, projets, médias, et `music/` pour tes musiques
de fond. Les générations tournent côté serveur, donc tu peux fermer l'onglet sans rien perdre.

## Sécurité

- Les clés (`AI_API_KEY`, ElevenLabs…) restent dans `.env`, côté serveur, et ne sont jamais
  envoyées au navigateur. Ne commite jamais `.env`.
- Toutes les routes `/api/pov/*` sont réservées au rôle boss.
