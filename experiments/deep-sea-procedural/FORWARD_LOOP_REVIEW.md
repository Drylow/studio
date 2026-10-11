Le film final passe les contrôles techniques : 300 secondes, 1 920 × 1 080, 30 i/s, 9 000 trames décodées et tous les PTS exacts. Un seul décodage complet audio/vidéo a été effectué. Le MP4 vérifié et le reçu concordent : SHA256 `37699678ea847830c6992e160064adc8592d4760b2508fa4153b39ae42a8c459`.

La scène compilée est `d3460e0da70312fcfb26134c92ca09c696750ea02a62e11ffba77731c0c8ce5f` ; le code source actuel est `689c282efdaea29fe87f63b69a86bb59588409498886fb8ce68c197b2a696814`. Le rendu a pris 1445.923 secondes (24.10 minutes).

L'examen indépendant a couvert 60 vues générales, 192 captures autour des passages proches à 24/111/219 s et aux extrémités, plus 13 PNG natifs, soit 249 indices de trame distincts. Les 17 planches ont été examinées. Root a aussi examiné les trois planches générales, le raccord encodé, la deuxième planche autour de 111 s et le PNG natif à 65 s. Aucun flash noir/blanc, texte parasite ou saut évident n'a été identifié dans ces échantillons. Les récifs répétés et leurs bords plans restent visibles ; l'approbation artistique appartient à l'utilisateur.

Les pixels source à 0 et 300 s sont identiques. Les trames encodées 8999 et 0 ne le sont pas : RMS du raccord 7.7921, contre 7.6316/7.5044 pour les voisins ordinaires. Les échantillons examinés n'ont pas montré de saut évident.

Audio : 300 secondes utiles en stéréo 48 kHz, plus 512 trames de padding AAC mesurées séparément. Pic -22.985 dBFS, RMS -36.528 dBFS, aucun échantillon non fini ni saturation dans tout le PCM décodé. Les 300 fenêtres d'une seconde sont non silencieuses. La source originale périodique, son reçu et le PCM analysé concordent. Le raccord numérique encodé reste dans les variations voisines mesurées ; cela ne garantit pas son inaudibilité dans chaque lecteur.

Ce contrôle est un examen d'images sélectionnées, avec analyse numérique de tout le média. Aucune lecture humaine continue ni écoute intégrale n'est revendiquée. Les tests source ne constituent pas une preuve complète de collision ou d'occlusion 3D. Le rendu demeure une projection illustrée 2,5D.

Le reçu de capture et les profils QA originaux ont été conservés. Rapports : `final-review.json`, `video-qa.json`, `../qa-final-audio/audio-qa.json` et `../loop-check.json`. Le registre conserve deux créations d'assets, zéro appel Algrow/vidéo/réseau pendant le rendu et `paid_generation_calls: null` ; le coût de calcul/stockage/transfert n'est pas déclaré nul.
