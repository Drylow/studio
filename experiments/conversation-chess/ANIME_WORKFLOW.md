# Produire comme le collègue

Le format retenu est son outil `conversation-chess`, avec son moteur graphique
et son montage Kdenlive. `scene.js` et les neuf icônes actives Chess.com sont
conservés. Pour l'anime, Tony est remplacé par un pion neutre provisoire,
conformément au retour utilisateur ; ses images originales restent archivées.
Le personnage définitif n'est pas choisi. Les recherches, plans, variantes et
archives Sopranos restent disponibles.
Le plan Tony/Richie de14m51 est un brouillon éditorial, pas une vidéo terminée.

1. Acquérir le clip anglais via la liaison Algrow configurée, comme décrit dans
   `SOURCE_IMPORT.md`. Mesurer le fichier réellement reçu : une réponse «1080p»
   ne suffit pas. Examiner les images natives et tous les plans pour le détail,
   les textes incrustés et les watermarks. Refuser les Fandango Clips et autres
   surimpressions. Une source insuffisante permet seulement un aperçu marqué.
2. Vérifier les dialogues et choisir une scène qui montre une manœuvre et sa
   conséquence. Le premier locuteur du passage sélectionné est blanc ; garder
   les camps fixes. Les scores expriment notre lecture, pas un moteur d'échecs.
3. Écrire les commentaires à la main sur des événements observés. Une note
   explique une tactique, une erreur ou son résultat ; elle peut être drôle.
   Laisser finir les mots et une courte respiration avant la pause : le premier
   « opinion » est suivi de0.61s selon l'alignement, plutôt que0.11s auparavant.
   Utiliser les neuf catégories, sans Miss. Great et Best ne déplacent ni score
   ni barre. Vérifier chaque repère sur le fichier dont le hash est enregistré.
4. Garder le guide16s, les commentaires anglais tapés, les pauses de3–9s et
   au moins2.5s de lecture après la frappe. Pendant une pause, le replay muet
   revient sur les2–4s précédentes ; le dialogue reprend au même instant.
5. Utiliser les musiques et SFX existants : musique au guide et au bilan,
   clavier pendant la frappe, accent de notation et quelques cues comiques
   explicitement choisis. Pas de voix off. Mesurer les crêtes audio.
6. Écrire un bilan propre à l'épisode, conserver le panneau de fin du collègue
   et compter les annotations une fois. Regarder l'image réellement produite
   avant de marquer la mise en page revue. Garder les crédits musicaux séparés.
7. Préparer les médias puis exporter depuis Kdenlive/MLT. Conserver le projet
   natif, les six pistes séparées, le job d'export et les médias relatifs.
   Régénérer le calque pour modifier le texte ; les mots ne sont pas des titres
   Kdenlive éditables directement. Relire toutes les images et décoder le MP4.

## Épisode en cours : Lelouch contre Schneizel

Titre : **Lelouch vs Schneizel Analysed like Chess | Code Geass**.
Dialogue anglais0–191.6s, cinq commentaires de7s, guide16s et bilan12s :
254.6s, soit4m14.6. Lelouch ouvre et reste blanc. Le dénouement montre sa
victoire ; Schneizel ne gagne pas cette scène.

```powershell
powershell -ExecutionPolicy Bypass -File experiments/conversation-chess/chess.ps1 -Mode Render -Preview -Source work/chess-studio/schneizel/lelouch-vs-schneizel-english-720.mp4 -Timeline experiments/conversation-chess/episodes/lelouch-vs-schneizel.json -Out work/conversation-chess/lelouch-full-new
```

La source actuelle1280×720 est refusée pour la version finale. Le cadre et les
graphismes1080p n'améliorent pas le détail de ce fichier. Le remplacement HD
exigera une nouvelle vérification du dialogue, des repères et de son hash.
Les modèles Ayanokoji/Ryuen et Game of Thrones restent à remplir après
acquisition d'une vraie source répondant à ces critères.

La livraison locale comprend MP4, projet Kdenlive et kit de description avec
crédits. Aucun envoi Discord ni publication YouTube n'est déclenché.
