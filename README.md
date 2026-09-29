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

   Des modèles prêts à l'emploi viennent d'une étude NexLev des chaînes 2D en forte croissance.
2. **Script.** Plan (hook, sections, beats, budget de mots), puis écriture section par
   section, puis relecture par un « script doctor » qui réécrit les passages faibles,
   puis ajustement de la longueur à la durée cible. Tu peux éditer le script, le faire
   réécrire avec une consigne, ou restaurer une ancienne version depuis l'historique.
3. **Voix off.**
   - Fournisseurs : Edge TTS (gratuit), ElevenLabs ou OpenAI TTS (avec clé).
   - Timings mot à mot et raccourcissement des silences.
   - Le débit réel de la voix est mesuré pour mieux viser la durée la fois suivante.
4. **Storyboard.**
   - Scènes découpées sur les fins de phrases, avec un rythme réglable et un hook plus rapide.
   - Prompts écrits par un « directeur artistique » IA.
   - Images générées en parallèle, avec l'image de style et la fiche perso en référence.
   - Bouton « Tester le style » pour valider une première image avant tout le lot.
   - Par scène : refaire, éditer le prompt, importer ta propre image, choisir le mouvement de caméra.
5. **Export.**
   - **MP4 monté** : zoom/pan, fondus, sous-titres karaoké ou phrases, titres de section,
     musique baissée automatiquement sous la voix, volume normalisé à -14 LUFS.
   - **Pack montage** : ZIP avec un clip par image dont la durée est exactement celle de sa
     phrase, plus la voix, le `.srt` et les timestamps. On glisse le tout dans CapCut ou Premiere
     et c'est calé.
   - **Métadonnées** : titres, description SEO, tags et chapitres horodatés.

Tout est stocké dans `data/pov/` : chaînes, projets, médias, et `music/` pour tes musiques
de fond. Les générations tournent côté serveur, donc tu peux fermer l'onglet sans rien perdre.

## Sécurité

- Les clés (`AI_API_KEY`, ElevenLabs…) restent dans `.env`, côté serveur, et ne sont jamais
  envoyées au navigateur. Ne commite jamais `.env`.
- Toutes les routes `/api/pov/*` sont réservées au rôle boss.
