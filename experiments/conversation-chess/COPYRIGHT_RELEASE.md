# Droits et restrictions avant publication

## Incident Peaky signalé le 11 octobre 2026

Le montage Tommy/Alfie a été livré et vérifié techniquement. L’utilisateur
l’a mis sur YouTube, a reçu une réclamation **audiovisuelle** avec blocage
dans certains territoires, puis l’a **supprimé**. Le demandeur, les pays et
les passages précis ne sont pas connus. « Audiovisuel » ne prouve pas que
les musiques ajoutées sont réclamées. Conserver les fichiers comme archive,
sans proposer ce montage pour une nouvelle publication.

Les épisodes S02E02, S02E06 et S03E06 viennent d’un accès Naka ; cet accès
n’est pas une licence de republication. La source map compte 679,833 secondes
de scènes, soit 11 min 19,833 et environ 73,3 % du film, avant les replays
d’analyse. Cette durée est un constat, pas un seuil juridique. Les deux musiques Kevin MacLeod ont
leurs crédits CC BY 4.0 dans le kit. La QA du décodage, des images, du son et
des crédits ne remplace ni les droits sur les épisodes ni le contrôle YouTube.
La formulation ancienne « Vidéo vérifiée — à publier manuellement » était
trop large : elle confondait la fin du montage avec une publication validée.

## Procédure pour les prochains montages

1. **Avant le montage**, vérifier les droits de chaque source image, vidéo et
   audio, les usages autorisés, la monétisation et l’attribution. Conserver les
   licences ou autorisations réelles avec la source. Une vidéo visible chez un
   concurrent ou disponible en streaming ne démontre pas ces droits. En leur
   absence, ne pas déclarer le format compatible avec l’objectif « aucun claim ».
   Proposer un contenu original ou des médias avec une licence adaptée ; aucune
   nouvelle série n’est automatiquement validée par le changement de titre.
2. Vérifier le montage effectivement exporté. Le livrer, si nécessaire, en
   **youtube-test**, destiné uniquement à un premier dépôt privé. Ne pas le
   présenter comme prêt à publier. Ce dépôt n’a pas encore eu lieu pour un
   prochain film ; la procédure ne constitue pas un accès à YouTube Studio.
3. Attendre la fin de **Vérifications / Checks** dans YouTube Studio, regarder
   toutes les réclamations, les éventuels pays bloqués et l’impact sur les
   revenus. Conserver les résultats liés au fichier et à la vidéo testée.
   L’API YouTube Data seule ne fournit pas ces détails complets de Content ID.
4. Une livraison **final** exige maintenant un `publication_review` correspondant
   au SHA-256 de la vidéo, des droits vidéo et musique documentés et un résultat
   initial YouTube sans réclamation ni territoire bloqué. Une réclamation
   active garde la publication bloquée ; résoudre le problème en fonction des
   détails réels, sans modifier le film pour tromper la détection.

Exemple de structure de revue, à renseigner seulement après les contrôles réels :

```json
{
  "sha256": "SHA-256 du fichier exact contrôlé",
  "source_rights_verified": false,
  "music_rights_verified": false,
  "youtube_checks_complete": false,
  "youtube_copyright_status": "not_checked",
  "claims": [],
  "blocked_territories": [],
  "evidence_files": []
}
```

Les preuves se trouvent dans des fichiers privés voisins de la revue. Le helper
valide leur présence et la cohérence du rapport, mais ne peut pas déterminer
lui-même la validité juridique d’une licence ni lire les Checks d’un compte
YouTube. Un résultat initial favorable **ne garantit pas** l’absence de
réclamation ultérieure ou l’acceptation de la monétisation. Ne jamais promettre
« zéro copyright » sur des extraits de séries commerciales sans droits établis.

La piste *Inglourious Basterds* / strudel reste une idée pour une prochaine
reprise. Aucun extrait ni montage lancé ; les mêmes contrôles s’appliquent.

## Sources officielles consultées

Consultées le 11 octobre 2026, réponses HTTP 200 :

- [Réclamations pour atteinte aux droits d’auteur](https://support.google.com/youtube/answer/6013276?hl=fr) : les politiques du titulaire peuvent bloquer, monétiser ou suivre une vidéo, selon les pays.
- [Fonctionnement de Content ID](https://support.google.com/youtube/answer/2797370?hl=fr) : les titulaires choisissent la politique appliquée aux correspondances.
- [Mettre en ligne une vidéo et vérifications](https://support.google.com/youtube/answer/57407?hl=fr) : un dépôt peut rester privé pendant les Checks ; leurs résultats ne sont pas définitifs.
