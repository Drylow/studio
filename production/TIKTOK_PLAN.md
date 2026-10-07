# TikTok : vidéos IA « persos à tête d'objet » (plan, 7 oct. 2026)

Demande de l'utilisateur : un nouvel outil pour lancer plusieurs comptes TikTok
avec le même type de vidéos que les comptes qui marchent. Il faut la même fluidité,
le même genre de personnages et des voix vivantes avec des tics (« fuck me if I'm wrong »).
Les vidéos font un peu plus d'une minute, et la production doit coûter le moins possible.
Rien n'est construit pour l'instant. Ce fichier décrit l'analyse et les tests proposés.

## Comptes de référence (relevés le 7 oct. 2026)

| Compte | Abonnés | Langue | Meilleures vidéos |
|---|---|---|---|
| @brokenfruitsofc (Broken Fruits) | 39,5 k | anglais (argot US) | 3 LOCKS, 1 KEYVON 5,9 M ; NEEGY CAN UNLOCK ANYTHING 3,2 M ; KEYVON MESSED UP THREE FAMILY TREES 1,8 M |
| @unknowwkil (Tekzooo) | 292 k | français | Le sale boulot 985 k ; Le choix qui change tout 507 k |
| @sketchiamagueule (sketchia) | 107 k | français | Elle trouve un secret dans ses cheveux 1,4 M ; ils vont devoir se sacrifier 430 k |

Liste des vidéos : page d'intégration `https://www.tiktok.com/embed/@<compte>`. La page profil
ne liste rien sans connexion. Analyse image et son : NexLev `watch_tiktok_video_and_ask`.

### Ce qui est commun

- Images 3D façon Pixar, en vertical. Les personnages sont des humains avec une tête d'objet,
  de fruit ou de légume, et des vêtements de tous les jours. Ils restent identiques d'un plan à l'autre.
- **Ce sont les personnages qui parlent, avec les lèvres synchronisées.** Il n'y a pas de narrateur.
  Les voix sont très jouées : argot, insultes légères, tics.
- Chaque plan est une génération vidéo IA séparée. Les plans durent 2 à 8 s, il y en a 16 à 28 par vidéo,
  pour une durée totale de 1 min à 1 min 44.
  Le modèle le plus probable est Veo 3.x : voix et lèvres sont générées avec l'image, en clips de 8 s maximum.
- Un beat en fond (lo-fi ou trap). Bruitages : déclic, « ding », bip d'hôpital.
- Sous-titres gros, mot par mot, blancs avec contour noir, et un mot en jaune.
  Le nom du compte est affiché en filigrane.

### Broken Fruits (la référence choisie par l'utilisateur : « le perso, la clé »)

- Le héros récurrent est un homme à tête de clé, Keyvon ou Neegy selon les épisodes.
  Il porte un sweat noir, une chaîne et des Dunk. Sa voix est grave et sûre de lui, en argot US.
- Formule d'un épisode (1 min 18 à 1 min 26, 18 à 22 plans) :
  1. Il rencontre successivement trois femmes à tête de serrure, coffre, porte, boîte à bijoux ou glacière.
  2. Sa phrase fétiche ouvre chaque rencontre : « Fuck me if I'm wrong, cuh, but you look like… »,
     et il se trompe d'objet.
  3. Elle le corrige avec une réplique sèche (« I'm a treasure chest, asshole »). Elle le défie,
     il « ouvre », puis elle annonce sa grossesse en une phrase-chute.
  4. Retournement : les trois femmes sont dans la même chambre d'hôpital.
  5. Chute finale avec le médecin à tête de pigeon, par exemple
     « Cuh, I don't make the locks. I just fit in 'em. »
- C'est une série : même héros, même médecin, et un titre en capitales sur le héros.

### Tekzooo et sketchia (français)

- Tekzooo : humour pipi-caca. Un ouvrier « caca » nettoie un intestin, avec saucisse et virus.
  1 min, 28 plans très courts, sous-titres jaune et blanc.
- sketchia : conte en épisodes (cheveux en or, coiffeuse aubergine, patronne citrouille).
  1 min 44, 16 plans, musique orchestrale, cliffhanger « dernière partie ».

## Ce qu'on garde, ce qu'on change

- On garde le format : tête d'objet, héros récurrent avec sa phrase fétiche,
  trois rencontres, retournement et chute, voix jouées, plus d'une minute.
- On crée **notre propre héros et notre propre phrase**. Copier Keyvon, son nom ou sa phrase
  expose aux signalements et au filtre « contenu non original » de TikTok,
  qui fait baisser la portée et peut bloquer la rémunération.
- La mention « contenu généré par IA » de TikTok est à activer sur chaque vidéo.
- Le sous-entendu adulte reste du sous-entendu : rien d'explicite, jamais d'enfant concerné.

## Monétisation

Le programme de récompenses des créateurs ne paie que les vidéos de plus d'une minute,
d'où la durée visée de 65 à 80 s. Il faut aussi 10 000 abonnés et 100 000 vues sur 30 jours.
Il n'est disponible que dans certains pays : FR, DE, UK, US, JP, KR, BR selon les listes trouvées.
La Belgique n'y figure pas : à vérifier dans TikTok Studio pour le compte de l'utilisateur.

## Coût de génération (prix relevés le 7 oct. 2026)

- **API Gemini, prix officiels** (pas d'offre gratuite pour Veo), son compris, par seconde générée :
  - Veo 3.1 Lite : 0,05 $ en 720p, 0,08 $ en 1080p.
  - Veo 3.1 Fast : 0,10 $ en 720p.
  - Veo 3.1 : 0,40 $.
  - Une vidéo de 72 s se fait en environ 9 à 12 clips de 8 s. Avec les ratés,
    elle coûte environ 5 à 7 $ en Lite et 10 à 14 $ en Fast.
  - Les images de référence des personnages (Nano Banana 2 Lite) coûtent environ 0,03 $ pièce.
- **Algrow** (déjà payé par l'utilisateur) : `generate_video`, par exemple veo3-fast à 10 crédits par clip
  en 720p, ou seedance-2-5 jusqu'à 30 s avec le son. Le solde de crédits n'est pas connu.
- **Gratuit mais à la main** : Google Flow donne 50 crédits par jour aux comptes sans abonnement,
  soit environ 2 à 5 clips par jour, en 720p avec filigrane. Kling, Grok et Meta ont aussi des quotas
  quotidiens. C'est trop lent pour plusieurs comptes, et ça ne s'automatise pas.
- **Essai Google Cloud** : 300 $ offerts aux nouveaux comptes de facturation, pendant 90 jours.
  Il faudrait vérifier que Veo sur Vertex AI y est accepté et que l'essai n'a pas déjà servi.
- **Open source sur GPU loué** : LTX-2.x (image, son et lèvres en une passe, licence gratuite
  sous 10 M$ de CA) ou InfiniteTalk. Une heure de GPU coûte quelques dizaines de centimes,
  mais la qualité est en dessous de Veo. À garder comme piste de réduction des coûts.
- Le VPS de l'utilisateur n'a pas de GPU et ne peut pas générer ces vidéos.

## Voix

- **Voie A, comme eux** : Veo génère la réplique avec la voix et les lèvres dans le même clip.
  C'est le plus fluide. Le risque : la voix d'un personnage peut changer d'un plan à l'autre.
  On peut la stabiliser en passant chaque réplique dans un changeur de voix ElevenLabs,
  qui garde le rythme, donc les lèvres restent synchronisées.
- **Voie B** : voix ElevenLabs v3 d'abord, avec des balises d'émotion ([laughs], [sighs]),
  via Algrow ou ai33pro. Ensuite l'image et le son passent dans un modèle de synchronisation des lèvres.
  On contrôle mieux la voix, mais les lèvres sont moins naturelles.
- Le test compare A et B sur les mêmes plans.

## Pipeline prévu (outil « TikTok » du studio)

1. **Bible de série par compte** : le héros (image de référence, tenue, voix, phrase fétiche),
   les personnages récurrents, la formule d'épisode et la langue.
2. **Script** : 65 à 80 s, 12 à 16 plans, une réplique de 8 s maximum par plan.
   L'accroche tombe dans les 2 premières secondes, la chute est à la fin.
   Le titre est en capitales, avec le nom du héros.
3. **Personnages** : une image de face par personnage, réutilisée comme référence dans chaque plan.
4. **Plans** : image vers vidéo en 9:16 avec la réplique dans le prompt (voie A).
5. **Contrôles** :
   - en vision : le bon personnage, pas de texte parasite, pas de bras en trop ;
   - Whisper : la réplique dite est bien celle du script ;
   - un plan raté est refait automatiquement, au maximum 2 fois.
6. **Montage** : coupes, beat libre de droits, bruitages, sous-titres mot par mot, filigrane du compte,
   durée de plus de 61 s.
7. **Livraison** : un paquet Discord par compte (vidéo, légende, hashtags) que l'utilisateur poste.
   La publication automatique viendra plus tard : l'API TikTok n'autorise que des posts privés
   tant que l'application n'a pas passé l'audit.

## Tests proposés

1. Une bible et un épisode complet en anglais, avec notre propre héros, en voie A.
   Environ 12 clips ; le coût dépend du moyen de paiement choisi.
2. Les 3 mêmes plans en voie B, pour comparer les voix.
3. L'utilisateur choisit, puis on construit l'outil dans le studio.
