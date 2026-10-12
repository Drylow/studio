# Dix nouvelles parties — 12 octobre 2026

Demande : reprendre exactement le style des fichiers restant dans
`C:/Users/ytbyt/Documents/Codex/2026-10-04/j/outputs/chess-10-ancien-style`.
Ce sont des replays d'échecs sur échiquier, distincts des analyses d'anime.

Livraison : dix MP4 numérotés 11 à 20 ajoutés au dossier ci-dessus, avec les
cinq fichiers 06 à 10 conservés à l'identique. Le fichier
`00-TITRES-DANS-L-ORDRE.txt` ne liste que les quinze vidéos disponibles.
Chaque nouvelle vidéo dure 180 secondes, en 1280 × 720, 30 fps, sans audio.
La composition Remotion existante est conservée : fond sombre, cases vertes,
derniers déplacements jaunes et notation à droite. Aucune modification du
frontend du studio historique.

Projet éditable : `C:/Users/ytbyt/Documents/Codex/2026-10-04/j/work/chess-remotion`.
Les nouvelles parties sont les identifiants 51 à 60 de `data/games.json` ;
les cinquante parties précédentes sont préservées. `generate-2026-10-12.mjs`
fixe dix ouvertures distinctes puis fait jouer le moteur jusqu'au mat
ou à la nulle. Les parties sont simulées, pas des matchs historiques.
Les PGN du lot sont sauvegardés ici ; ils conservent les coups exacts.

Pour réexporter depuis le projet local, avec Node.js, FFmpeg et les
dépendances du `package-lock.json` déjà installé :

```powershell
$env:CHESS_OUTPUT_DIR = (Join-Path (Get-Location) 'exports-2026-10-12')
node render.mjs --from=51
node verify.mjs --count=10
```

Le renderer conserve chaque position Remotion jusqu'au prochain coup et
encode 5400 images par film. Décodage complet des dix exports, validation
des PGN et absence de doublons face aux anciens lots. Les 1289 positions
affichées sont regardées sur 47 planches extraites des MP4, avec le milieu
et la fin de chaque film à taille native. Empreintes des vidéos nouvelles
et des cinq fichiers conservés : `delivery-receipt.json`.

Les médias, planches et caches restent dans le projet local ; le reçu et
les PGN permettent la reprise. Aucune publication sur YouTube effectuée.
