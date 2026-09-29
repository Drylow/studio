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
   - bible de style, tirée de transcriptions de vidéos de référence (lien YouTube ou collage) ;
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
2. **Script.** Plan (hook, sections, beats, budget de mots), puis écriture section par
   section, puis relecture par un « script doctor » qui réécrit les passages faibles,
   puis ajustement de la longueur à la durée cible. Tu peux éditer le script, le faire
   réécrire avec une consigne, ou restaurer une ancienne version depuis l'historique.
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
     musique baissée automatiquement sous la voix, volume normalisé à -14 LUFS.
   - **Musique « auto »** : une piste de la bibliothèque par vidéo, très basse, baissée encore sous la
     voix. Si la bibliothèque est vide, 3 ambiances lofi 100 % originales sont générées (aucun
     risque de réclamation Content ID). Tu peux y ajouter des morceaux de la bibliothèque audio de
     YouTube Studio.
   - **Pack montage** : ZIP avec un clip par image dont la durée est exactement celle de sa
     phrase, plus la voix, le `.srt` et les timestamps. On glisse le tout dans CapCut ou Premiere
     et c'est calé.
   - **Miniatures** : 2 variantes dans le style de la chaîne, avec le perso et un texte court en gros.
   - **Métadonnées** : titres, description SEO, tags et chapitres horodatés.

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
