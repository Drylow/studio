# Référence Stephen Dalton — forme centrale animée

Vérification du 11 octobre 2026 pour Quiet Little Worlds.

## Résultat

**La petite bulle organique centrale décrite par l’utilisateur n’a pas pu être
vérifiée en vidéo dans cet environnement.** Sa description « façon Siri » est une
référence donnée par lui ; ce n’est pas une observation directe de notre part.
Ne pas écrire que nous avons regardé le mouvement ou mesuré son rythme.

L’accès aux vidéos YouTube et à oEmbed avait déjà échoué via le proxy ; le serveur
de miniatures avait répondu 403 avec un refus de politique réseau. Aucun nouvel
essai sur ces destinations, autre hostname, relais, VPS ou contournement n’a été
utilisé pour cette vérification.

## Ce qui a réellement été inspecté

- [Accueil officiel](https://stephen-dalton.com/) : HTTP 200 ; liens de produits
  audio et lien vers la chaîne YouTube, aucun fichier vidéo ni lecteur vidéo
  trouvé dans le HTML récupéré.
- [The Jungle Treehouse](https://stephen-dalton.com/products/sleep-story-the-jungle-treehouse) :
  HTTP 200 ; couverture fixe et lecteur d’extrait MP3. Page aussi ouverte dans
  Chromium et **capture d’écran réellement examinée**. L’image montre une maison
  dans un arbre, de nuit, avec pluie représentée et fenêtres ambrées ; le lecteur
  visible est audio. Aucune bulle centrale animée visible sur cette page.
- [The Antique Store](https://stephen-dalton.com/products/sleep-story-the-jungle-treehouse-kopie) :
  HTTP 200 ; couverture fixe et lecteur MP3 dans le HTML. Aucun fichier vidéo
  trouvé.

Après rendu JavaScript, les deux iframes de la page Treehouse servent aux fonctions
Shopify de mesure et de paiement ; ce ne sont pas des players vidéo. Les médias
audio n’ont pas été chargés ni écoutés. Aucun achat effectué. Ces constats portent
sur trois pages précises, pas sur l’intégralité du site ou de la chaîne.

Le flux podcast et les statistiques publiques déjà recueillis peuvent documenter
des titres, durées et descriptions. **Ils ne prouvent ni la présence d’un
visualiseur, ni sa forme, ni son lien exact avec la voix.**

## Application à notre production

L’utilisateur demande une forme centrale originale qui accompagne la voix. On
peut donc réaliser ce principe sans reprendre un asset de Stephen Dalton : petite
forme souple translucide, mouvements lents, variations modérées pilotées par
l’enveloppe de **notre narration**, retour doux au repos pendant les pauses.
Il s’agit d’une proposition propre au projet, pas d’une reproduction vérifiée.

La palette, l’emplacement et l’intensité restent à juger sur notre aperçu. Ne pas
affirmer que Stephen utilise un algorithme, un logiciel, un spectre audio, une
fréquence ou une animation précise : aucun de ces paramètres n’a été observé.

## Preuves locales

Dans `output/nature-sleep/cozy-garden/reference-visualizer/` (ignoré par Git) :

- `media-scan.json` : URLs, réponses HTTP, tailles, SHA-256, balises médias et
  liens pertinents des trois pages ;
- `home.html`, `treehouse.html`, `antique.html` : pages consultées ;
- `browser-media.json` : éléments audio/iframes après rendu de Treehouse ;
- `treehouse-visible.png` : capture effectivement inspectée.

Aucun média du créateur n’a été copié dans les assets de production et aucun
fichier de montage ou de voix n’a été modifié par cette recherche.
