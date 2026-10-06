# Connexion officielle à YouTube

Edgerunners Studio utilise directement OAuth Google et l’API YouTube, sans service
de publication intermédiaire. Une clé API seule ne permet pas de publier sur une chaîne.
Réutiliser le client Google existant ; ne pas créer un nouveau client pour chaque chaîne.

## État constaté le 6 octobre 2026

Le projet existant est **External / In production**. Les deux scopes nécessaires
sont déclarés dans Data Access et Google affiche « not yet verified ». La validation
Search Console du domaine a réussi après ajout d'un TXT à l'apex, sans modification
des autres enregistrements. Conserver ce TXT. Cette preuve ne vaut pas approbation OAuth.

Le contrôle Branding indique encore une propriété de domaine manquante et demande
24 heures après sa validation. Réessayer **le 7 octobre après 17 h 25, heure de Paris** :
Branding → View issues → I have fixed the issues → Proceed. Si Google affiche
Ready to publish, cliquer Publish branding, puis ouvrir Verification Center pour
examiner les éventuelles étapes Data Access. Ne pas annoncer une résolution avant
un consentement réel puis une vérification de chaîne réussis.

Alternative officielle au contrôle automatique : View issues →
I believe the issues found are incorrect → Proceed demande un examen manuel,
justifiable puisque Search Console confirme la propriété. Ce n'est pas un déblocage
immédiat et son délai n'est pas maîtrisé. Ne pas recommander de contourner un blocage
par un client emprunté, une clé API ou une permission incompatible avec la publication.
L'exception Google pour usage personnel peut éviter une revue complète pour un petit
groupe connu, mais elle ne permet pas de franchir un écran « This app is blocked ».

Références : [vérification des scopes sensibles et examen manuel](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification),
[Audience et restrictions des comptes](https://support.google.com/cloud/answer/15549945).

## Statistiques sans permission supplémentaire

Les fiches et le classement utilisent `channels.list`, `playlistItems.list` et
`videos.list` avec l'autorisation existante. Aucun scope YouTube Analytics supplémentaire.
Les vues affichées sont les compteurs cumulés ; les progressions sont leurs différences
entre deux relevés datés. Les périodes incomplètes, abonnés masqués, corrections négatives,
erreurs de connexion et données anciennes sont indiqués. Aucun historique n'est inventé.
Stock, projets et réglages restent consultables avant la connexion Google.

Le worker consulte une chaîne échue par passage inactif, environ toutes les 4 heures,
indépendamment de la pause des publications. Actualiser utilise un délai de 15 minutes
et un verrou transactionnel, sans accès distant déclenché par les GET du navigateur.
Les caches sont privés, purgés après 29 jours, lors d'une déconnexion, d'un retrait
ou d'un changement d'identité YouTube. Les mêmes chaînes reconnectées gardent leurs
relevés historiques valides. Aucun appel d'upload dans le module de statistiques.

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
