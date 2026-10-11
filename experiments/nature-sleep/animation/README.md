# Quiet Little Worlds — léger aperçu animé

Prototype original créé à partir de **C-botanical-moss-garden.png**. Le choix de C est délégué par l’utilisateur ; le mouvement reste à valider visuellement par lui. Aucun code ou média des anciens fonds marins n’est utilisé.

La boucle dure 24 secondes. La mare et deux zones de fougères bougent de moins de deux pixels ; trois petites lucioles suivent des courbes lentes. Les points lumineux déjà peints restent présents. Le cadrage est fixe, les animaux ne sont pas déformés. Pas de texte à l’écran, de musique ou de narration. Il ne s’agit pas d’une vidéo de deux heures.

`garden.html` dessine l’illustration dans un shader WebGL ; les petits décalages sont masqués dans leurs régions. Le temps est cyclique et reproductible. L’encodeur FFmpeg reçoit les images du navigateur par un pipe, sans conserver des centaines de captures.

Depuis la racine du dépôt, avec Chromium, FFmpeg et la dépendance Playwright déjà installée dans `frontend/` :

```sh
node experiments/nature-sleep/animation/capture-preview.mjs
python experiments/nature-sleep/animation/verify-preview.py
```

Pour une nouvelle sortie, passer un dossier inexistant comme premier argument. Un export déjà présent n’est jamais écrasé. Pour regarder l’animation HTML en direct, servir le dépôt avec un serveur HTTP local et ouvrir ce fichier ; le fichier de référence reste voisin dans `branding/`.

L’image source mesure **1672 × 941** ; le fichier de présentation est exporté en **1920 × 1080, 30 images/s**, sans prétendre à une source 4K. Les reçus, captures de contrôle et vidéo sont dans `output/nature-sleep/light-preview/`, ignoré par Git. Le contrôle du raccord exact du shader ne remplace pas l’examen des images réellement encodées.

Le vérificateur lit les 720 images, contrôle l’absence de son, décode entièrement le fichier, puis extrait seize captures dont le début, la fin et trois phases intermédiaires. Son rapport technique indique encore `visual_review_complete: false` : les vraies revues visuelles sont conservées séparément avec leur périmètre exact. Une capture ou un hash de raccord ne signifie pas que le film a été regardé en lecture continue.

Premier export complet : **24 s, 720 images, 8 436 624 octets**, réalisé en 213 secondes après l’optimisation de capture. SHA-256 du MP4 : `ceda3f813f23f67a7fd7b497c09b55c4919d9e08441e182d030ec59010dc9e6e`. Le décodage entier passe sans erreur. L’auteur a réellement examiné les seize captures du MP4 en planche, dont cinq également en résolution native ; son rapport est `qa/author-visual-review.json`.

Une seconde revue indépendante a examiné les mêmes seize captures, cinq natives et les deux endpoints ; elle conclut que l’aperçu peut être montré, avec la limite de raccord indiquée ci-dessous. Rapport : `qa/independent-review.json`. Aucun visionnage vidéo continu n’est revendiqué.

Le shader produit des images strictement identiques à 0 et 24 secondes. **Le MP4 est compressé avec pertes** : son raccord n’est pas identique pixel par pixel, et la différence moyenne au dernier/premier frame est de 1,5075 sur 255, supérieure à celle des frames voisines. Les captures ne montrent pas de saut manifeste de géométrie ou de lumière, mais cela ne certifie pas un raccord imperceptible en lecture continue. L’aperçu reste à valider par l’utilisateur avant toute production longue.
