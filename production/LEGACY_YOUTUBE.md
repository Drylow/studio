# Publication gratuite : retrouver le parcours de l’ancien site

Le 6 octobre 2026, l’utilisateur refuse les abonnements de publication et rappelle
que son ancien site publiait gratuitement via Google. Ne pas proposer à nouveau
un prestataire payant comme prochaine étape par défaut.

## Ce que les sauvegardes prouvent

La copie privée du site avant remplacement contient `routes/youtube.py`, son `.env`
et sa base. Le client Google, son secret et le callback sont identiques à ceux de
l’hébergement actuel. Aucun changement de client ou de secret n’est nécessaire.
La sauvegarde contient une connexion historique Le Grand Récap ; Google refuse
encore son renouvellement avec `invalid_grant`. Elle ne peut pas être réutilisée
comme si son autorisation était active. Ne pas effacer ce jeton ni relancer les
anciennes vidéos. Cela ne permet pas de conclure que d’autres chaînes n’ont jamais
été automatisées sur un autre déploiement.

L’ancien code demandait **`youtube.upload` + `youtube.readonly`**, puis transmettait
la visibilité publique dans `videos.insert`. Le nouveau parcours privé puis public
demandait **`youtube.force-ssl`**, car il appelle `videos.update`. Le refus réel de
Google pour ce dernier parcours est confirmé. Sa cause exacte reste inconnue :
la différence de permissions est une piste concrète, pas une résolution prouvée.

## Compatibilité implémentée

La configuration privée `YOUTUBE_PUBLICATION_FLOW=legacy-news` active le parcours
historique pour les chaînes `publication_mode=news` uniquement, dont Cage et Pitch.
Les autres chaînes gardent l’envoi privé puis le changement de visibilité.

| Opération | Permission du parcours historique |
| --- | --- |
| Vérifier l’identité réelle de la chaîne | `youtube.readonly` |
| Envoyer la vidéo avec titre, description, tags et visibilité publique | `youtube.upload` |
| Appliquer la miniature | `youtube.upload` |
| Confirmer l’ID, la chaîne et la visibilité retournés | `youtube.readonly` |

Ce parcours n’appelle pas `videos.update` pour un nouvel envoi. Il réutilise le
client Google existant ; aucun abonnement ou intermédiaire n’est ajouté.
Les scopes sont liés à l’état OAuth à usage unique. Les autorisations incomplètes,
une autre chaîne, un doublon ou une modification concurrente restent refusés.

Avant l’envoi : droits liés aux fichiers, empreintes, qualité, actualité, validation
éventuelle et pauses sont contrôlés. Un contrôle supplémentaire précède les derniers
octets. Une miniature de plus de 2 Mo et une réservation future sont refusées avant
tout transfert. Le worker attend la date explicitement réservée sans inventer d’heure.

L’ID et le mode d’envoi sont conservés avant les appels de miniature ou de confirmation.
Une réponse perdue ou une miniature refusée se reprend sur la même vidéo, sans nouvel
envoi. Un ancien chargement privé conserve son mode ; sa finalisation peut encore
nécessiter l’autorisation de gestion. Les tables historiques restent compatibles.

**Limite du parcours original :** la vidéo devient publique à la fin de son transfert,
puis reçoit sa miniature. Une pause ou un échec après cette fin ne peut pas la remettre
en privé avec ces permissions limitées. Le studio signale explicitement un échec de
miniature sur une vidéo déjà publique. Il ne prétend pas avoir retenu cette vidéo.
Une restriction Google qui force un envoi privé ne sera jamais annoncée comme une
publication publique. Une confirmation de miniature et de visibilité est obligatoire
pour marquer l’opération réussie.

## Vérification réelle restante

Sur Google Auth Platform → Data Access, les permissions utilisées doivent comprendre
`https://www.googleapis.com/auth/youtube.upload` et
`https://www.googleapis.com/auth/youtube.readonly`. Pour les autres chaînes qui
conservent le parcours privé puis public, garder également `youtube.force-ssl`.

Puis edgerunners.fr → Chaînes → Cage Dispatch → Connecter YouTube. Ce test utilise
une demande différente du dernier essai refusé. Ne pas promettre qu’elle franchira
le blocage : seule une autorisation acceptée puis une lecture de la bonne chaîne le
prouveront. Les tests simulés et la redirection HTTPS de départ ne le prouvent pas.
Une restriction sur le compte ou le projet peut affecter également ce parcours.

Conserver la pause, les contrôles et l’automatisation désactivée jusqu’à validation.
Le moteur complet de sélection, vérification et création des actualités reste à
terminer. La modification du transport ne le rend pas opérationnel.

Source officielle vérifiée à nouveau : [permissions des méthodes YouTube](https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest).
