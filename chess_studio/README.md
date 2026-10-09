# Chess Studio — atelier local

Base de montage pour **les films d’animation**, puis **Game of Thrones**. Le gabarit est recalé sur les images d’Analysed Like Chess : clip plein écran, portraits carrés, barre d’évaluation, grandes icônes et cartes à texte progressif, sans narration ajoutée. Voir [REFERENCE.md](REFERENCE.md) pour la comparaison et ses limites.

## Ouvrir

Double-cliquer **Ouvrir Chess Studio.bat**, ou lancer :

```powershell
cd chess_studio
npm ci
npm start
```

L’atelier est accessible sur **http://127.0.0.1:4317**, uniquement sur cette machine. Node.js 22.12+ et FFmpeg/FFprobe doivent être disponibles. yt-dlp sert à l’import YouTube. Variables facultatives : `CHESS_FFMPEG`, `CHESS_FFPROBE`, `CHESS_YTDLP`, `CHESS_PORT`, `REMOTION_BROWSER`. Le lanceur Windows utilise le port par défaut.

## Préparer une vidéo

1. Créer un projet **Animation** ou **Thrones** et nommer les deux personnages.
2. Importer un fichier local, ou un lien vers un clip YouTube public (30 minutes maximum). La meilleure définition disponible est conservée ; l’audio anglais ou français est préféré quand disponible. L’original est téléchargeable depuis sa fiche. Vérifier sa langue et l’absence de sous-titres, logos ou montages déjà incrustés : l’import ne les efface pas.
3. Cliquer **Vérifier la source**, regarder le clip entier et confirmer l’absence de logo et de texte incrusté. La planche de contrôle facilite le repérage mais ne remplace pas le visionnage. Les sources Fandango / Movieclips sont exclues. Seuls les clips validés peuvent être ajoutés et exportés.
4. Ajouter le clip au montage. Régler ses points d’entrée et de sortie, sa cadence et le volume des dialogues.
5. À la fin d’une réplique ou d’un geste, cliquer **Ajouter un coup au curseur**. Écrire le nom du coup, la note, le commentaire, la durée de pause et l’évaluation. Déplacer la carte à gauche ou à droite pour préserver l’action. La citation est facultative et doit correspondre exactement au dialogue.
6. Importer un portrait par personnage. Les portraits apparaissent en haut et en bas de la barre. Le pion est une variante facultative dans les réglages.
7. Ajuster **Placement précis** pour placer séparément la carte et la grande icône selon l’action. Ajouter, si utile, une meilleure alternative et des tags.
8. **Sauvegarder** prépare les images fixes dans la qualité de la source. **Exporter le film** produit le MP4 et propose son téléchargement.

Les commentaires, décisions éditoriales et scores sont saisis à la main. La barre d’évaluation est une interprétation éditoriale ; aucun moteur d’échecs ne calcule une scène de film. La lecture continue conserve les dialogues ; la pause les arrête, puis la lecture reprend au même point source. Les mouvements sont sobres et déterministes : entrée/sortie brève de la carte, texte progressif, glissement de la barre et bruitage facultatif discret. Le zoom est désactivé par défaut. Pas de coupe ou de transition ajoutée automatiquement dans le clip.

## Qualité, sauvegarde et export

- Les originaux restent dans `public/media/`, avec leur résolution native. Aucun agrandissement n’améliore une source basse définition.
- Si nécessaire, un aperçu MP4 est préparé au même format : la vidéo H.264 est recopiée sans recompression ; les autres codecs sont convertis en H.264 CRF 17. **L’export utilise l’original**, pas cet aperçu.
- Export 1080p ou 4K, H.264 CRF 16, AAC 256 kbit/s, cadence choisie. Les sources sont conservées entières ; le découpage est non destructif.
- Projets et provenance : `.local/library.json`. Exporter aussi le découpage JSON depuis les réglages pour en garder une copie lisible.
- Rendus et snapshots : `../work/chess-studio/exports/<identifiant>/`. Chaque export fige son montage, ses sources et ses icônes. Modifier le projet ensuite ne modifie pas l’export en cours.
- Au redémarrage, la bibliothèque et les projets sont conservés. Les tâches en cours ne reprennent pas automatiquement ; relancer un import ou un export interrompu. Un export à la fois.
- Remotion réutilise le navigateur headless local s’il le trouve dans le cache connu ; sinon il utilise son téléchargement standard. `REMOTION_BROWSER` permet de choisir explicitement un exécutable.

## Icônes

Les **dix icônes SVG de classification proviennent du client public de Chess.com**. `public/chesscom/sources.json` conserve la source exacte, la date et les empreintes. Les géométries et couleurs ne sont pas redessinées. Ces assets restent propriétaires de Chess.com ; aucune licence ouverte n’est affirmée. Une option **Notation classique** permet de remplacer les assets dans le montage.

Pour actualiser les fichiers depuis la page publique, avec Python :

```powershell
python scripts/chesscom-assets.py
```

Les deux sons courts sont originaux et générés localement par `scripts/setup.mjs`.

## Développement et vérification

```powershell
npm test
npm run build
npm run demo
```

`npm run demo` crée une **mire technique**, destinée aux tests et à exclure des exports éditoriaux. L’atelier installé contient aussi un test de gabarit sur un extrait propre de Big Buck Bunny (02:20–02:34, 1080p natif). Attribution : Big Buck Bunny © Blender Foundation | www.bigbuckbunny.org — CC BY 3.0. Les médias et projets locaux ne sont pas inclus dans Git. Lancer `npm start` après un build sert le build ; pour le développement, retirer uniquement le dossier `chess_studio/dist` pour activer Vite à la prochaine ouverture.

Vérifications du 9 octobre 2026 : neuf tests de découpage et de validation des sources réussis ; build TypeScript/Vite réussi. Les anciens projets de mire et Movieclips sont archivés, les sources marquées sont rejetées et l’export exige une validation complète.

Cette base est autonome : elle ne modifie ni le frontend Flask, ni les chaînes historiques, ni les pipelines existantes. Pas de publication automatique. Pour obtenir un extrait vraiment propre et dans sa meilleure qualité, privilégier le fichier original disponible et vérifier visuellement chaque source.
