# Connexion officielle à YouTube

Edgerunners Studio utilise directement OAuth Google et l’API YouTube, sans service
de publication intermédiaire. Une clé API seule ne permet pas de publier sur une chaîne.
Réutiliser le client Google existant ; ne pas créer un nouveau client pour chaque chaîne.

## Branding du projet existant

Sur Google Auth Platform → Branding, utiliser :

| Champ | Valeur |
| --- | --- |
| App name | Edgerunners Studio |
| User support email | Adresse de support déjà choisie dans le projet |
| Logo | Facultatif, peut rester vide |
| Application home page | https://edgerunners.fr/about |
| Application privacy policy link | https://edgerunners.fr/privacy |
| Application terms of service link | https://edgerunners.fr/terms |
| Authorized domains → Add domain | edgerunners.fr |
| Developer contact information | Adresse de contact déjà choisie dans le projet |

Cliquer Save, puis revenir sur Audience. L’application est externe. En Testing,
seuls les comptes Google ajoutés comme utilisateurs de test peuvent autoriser
l’accès ; leurs autorisations et jetons de renouvellement expirent après sept jours.
Un utilisateur de test peut autoriser une chaîne Brand Account qu’il gère.
En Production, l’ajout de chaque nouvelle adresse comme utilisateur de test n’est
plus nécessaire, mais Google peut demander une vérification de l’application.
Le consentement du titulaire reste nécessaire pour chaque connexion de chaîne.

Le bouton Publish app devient utilisable uniquement lorsque Google considère
la configuration requise complète. Terminer Branding ne prouve pas à lui seul
que le message « This app is blocked » est résolu. Lire l’état affiché par Google
avant d’annoncer que la connexion ou la vérification est réussie. Des règles du
compte ou de son organisation peuvent aussi empêcher une autorisation.

## Client et permissions

L’adresse de retour actuellement conservée sur l’hébergement est
`https://edgerunners.fr/api/youtube/callback`. Le handler protège la session,
le rôle propriétaire et un état OAuth à usage unique. Les permissions demandées
sont `youtube.readonly` et `youtube.force-ssl` : cette dernière permet la mise
à jour de visibilité après l’upload privé. Ne pas la remplacer par `youtube.upload`
seul, qui ne couvre pas `videos.update` dans ce parcours.

La connexion est validée par l’identité réelle retournée par YouTube, avec rejet
des mauvaises chaînes et doublons. Les tests locaux simulent Google ; seule une
autorisation réelle puis une vérification API prouvent l’accès d’une chaîne.
Le blocage Google demeure à résoudre tant que ce parcours réel n’a pas abouti.

## Pages publiques et accès privé

Les trois documents `/about`, `/privacy` et `/terms` sont publics, rendus côté
serveur et accessibles sans JavaScript ni connexion. Leurs exceptions d’accès
portent sur trois endpoints exacts. Les APIs, médias, routes OAuth et données du
studio gardent leur protection. Des liens sont présents sur l’écran de connexion.
Les documents décrivent notamment la conservation des jetons, le contexte transmis
à l’assistant et la déconnexion qui conserve l’identité et l’historique d’une chaîne.
Les demandes de suppression passent par le contact administrateur affiché.

La publication et ses contrôles éditoriaux restent indépendants du paramétrage
OAuth. La vérification OAuth et les éventuelles exigences d’audit de l’API YouTube
sont des processus distincts ; un consentement réussi ne garantit pas à lui seul
qu’un upload puisse être rendu public ou qu’une automatisation soit opérationnelle.
