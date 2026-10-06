# Connexion officielle à YouTube

Edgerunners Studio utilise directement OAuth Google et l’API YouTube, sans service
de publication intermédiaire. Une clé API seule ne permet pas de publier sur une chaîne.
Réutiliser le client Google existant ; ne pas créer un nouveau client pour chaque chaîne.

L’utilisateur demande maintenant une recherche des autres moyens de publier.
[Deux autres voies documentées](production/PUBLICATION_ALTERNATIVES.md) : relais API
avec l’application Google du prestataire, ou ingestion native de podcasts RSS
(audio et image fixe). Le refus de notre client ne démontre pas que toutes ces voies
sont bloquées. Le choix d’un prestataire ou d’un changement de format reste en attente.
Ne pas reprendre par défaut les mêmes instructions d’examen Branding.

## État constaté le 6 octobre 2026

Le nouvel essai de l’utilisateur, après déploiement du parcours à une seule
permission, affiche encore **« This app is blocked »**. Le contrôle natif suivant
confirme qu’aucun jeton de renouvellement ni identifiant YouTube n’est enregistré
pour Cage ou Pitch. Ne pas lui demander de refaire cet essai inchangé.
Les 108 tests du dernier déploiement valident le code, pas le consentement Google.
Voir [le dossier d’examen prêt à utiliser](production/GOOGLE_REVIEW.md).

Le projet existant est **External / In production**. Les permissions auparavant
demandées sont déclarées dans Data Access et Google affiche « not yet verified ».
Le studio demande désormais uniquement `youtube.force-ssl`, qui couvre les quatre
opérations requises ; cela ne prouve pas que Google lève le refus. La validation
Search Console du domaine a réussi après ajout d'un TXT à l'apex, sans modification
des autres enregistrements. Conserver ce TXT. Cette preuve ne vaut pas approbation OAuth.

Le contrôle Branding indique encore une propriété de domaine manquante et demande
24 heures après sa validation. Réessayer **le 7 octobre après 17 h 25, heure de Paris** :
Branding → View issues → I have fixed the issues → Proceed. Si Google affiche
Ready to publish, cliquer Publish branding, puis ouvrir Verification Center pour
examiner les éventuelles étapes Data Access. Ne pas annoncer une résolution avant
un consentement réel puis une vérification de chaîne réussis.
Ce délai concerne le contrôle de domaine. Il ne prouve pas la cause du refus OAuth
et son expiration ne garantit pas que la connexion fonctionnera.

Alternative officielle au contrôle automatique : View issues →
I believe the issues found are incorrect → Proceed demande un examen manuel,
justifiable puisque Search Console confirme la propriété. Ce n'est pas un déblocage
immédiat et son délai n'est pas maîtrisé. Ne pas recommander de contourner un blocage
par un client emprunté, une clé API ou une permission incompatible avec la publication.
L'exception Google pour usage personnel peut éviter une revue complète pour un petit
groupe connu, mais elle ne permet pas de franchir un écran « This app is blocked ».

Références : [vérification des scopes sensibles et examen manuel](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification),
[Audience et restrictions des comptes](https://support.google.com/cloud/answer/15549945).

## Statistiques publiques par @pseudo

La page indépendante **Statistiques** utilise YouTube Data API v3 :
`channels.list(forHandle=...)`, puis la playlist des publications et `videos.list`.
Une seule clé API de serveur suffit pour toutes les chaînes ; aucun consentement
OAuth du propriétaire d’une chaîne n’est nécessaire pour lire ces données publiques.
Le blocage de connexion Google et la vérification Branding ne bloquent pas ce suivi.

Sur le site : Statistiques → Configurer la clé. Le formulaire contient les liens
vers le projet existant et les instructions pour activer YouTube Data API v3,
créer une clé API et la coller. Le serveur valide une vraie lecture avant de
l’enregistrer dans la base privée ; seule la présence de la clé est retournée
au navigateur. Seul Drylow peut la remplacer. Variante de configuration :
`YOUTUBE_API_KEY` dans l’environnement privé. Limiter la clé à YouTube Data API v3 ;
les restrictions par référent de site web ne conviennent pas au serveur.

Puis Ajouter une chaîne → son @pseudo ou son lien YouTube. L’association à une
chaîne du studio est facultative et sert aux filtres Drylow/Kanye. Les compteurs
actuels de vues, abonnés arrondis ou masqués et vidéos publiques arrivent au premier
relevé. Les vidéos donnent leurs vues, likes, commentaires et durée publics.
Un lien déjà suivi ne crée pas un deuxième suivi ni ne réinitialise son historique.

**L’API publique ne donne pas l’historique privé des dernières 48 h ou 7 jours.**
Les gains affichés sont les différences réellement observées entre les relevés
datés. Le suivi commence à l’ajout ; les périodes incomplètes et corrections
négatives sont explicites. Ne pas confondre les vues cumulées d’une vidéo récente
avec les vues de toute la chaîne gagnées pendant cette période. Durée de visionnage,
revenus et taux de clics restent dans YouTube Analytics, qui demande OAuth.

Périodes 24 h, 48 h, 7, 14 et 28 jours, classement triable, comparaison des courbes,
fiche de vidéos, recherche, filtres de responsable et export CSV privé. Maximum
20 chaînes et 200 dernières publications publiques par chaîne. Le collecteur relève
les compteurs chaque heure, indépendamment des longs montages et de la pause de
publication. Une collecte complète utilise au plus 9 unités par chaîne par heure
(hors retries/ajouts), soit 4 320 unités pour 20 chaînes sur 24 heures. Actualiser
respecte 15 minutes entre tentatives et un bail transactionnel ; les GET du navigateur
lisent seulement le cache. Les données restent privées et sont purgées après 29 jours.
Retirer un suivi supprime ses relevés sans retirer la chaîne du studio. Une déconnexion
OAuth n’arrête pas ce suivi public, qui est géré séparément dans Statistiques.

La clé de lecture publique a depuis été configurée par l’utilisateur. Les statistiques
sont reportées à sa demande ; ne pas lui redemander cette clé.
Les tests de compteurs utilisent une base dédiée et Google simulé ; ils ne prouvent
pas encore un relevé réel. Les anciennes routes de cache lié à OAuth restent privées
pour compatibilité, mais ne pilotent plus la nouvelle interface Statistiques.

Références officielles : [recherche par handle](https://developers.google.com/youtube/v3/docs/channels/list#forHandle),
[compteurs publics](https://developers.google.com/youtube/v3/docs/channels#statistics),
[configuration de l’API](https://developers.google.com/youtube/v3/getting-started),
[rapports privés Analytics](https://developers.google.com/youtube/analytics/reference/reports/query).

## Limite du raccourci YouTube Studio

Ouvrir YouTube Studio depuis le site ne préremplit pas la vidéo, la miniature,
le titre ou la description. Cela demanderait encore un envoi et une saisie manuels.
Ne pas présenter cette proposition temporaire comme « juste cliquer Publier ».
L’utilisateur n’a pas accepté cette proposition ; ne pas remplacer son objectif de
publication directe par un autre éditeur ou par un faux envoi automatique.

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
se limitent à `youtube.force-ssl` : elle couvre la lecture de l’identité, l’envoi,
la miniature et la mise à jour de visibilité après l’upload privé. Ne pas la remplacer par `youtube.upload`
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

## Publication d’actualité sans créneau

`studio/auto_publication.py` remplace le déclenchement exclusivement calendaire. Une
vidéo `ready` d’une chaîne `publication_mode=news`, autonome, activée, connectée et
non suspendue est mise en file dès que tous les contrôles passent. Les deux sports
n’ont pas besoin d’une heure. Une réservation future explicite reste respectée ;
les autres chaînes conservent leur calendrier et leur validation éventuelle. Les
travaux actifs ne sont pas dupliqués. L’envoi vérifie l’identité réelle du jeton
Google avant tout chargement, puis confirme la visibilité publique retournée.

Au contrôle serveur du 6 octobre, Cage et Pitch n’ont aucun jeton OAuth. La clé API
publique est présente, les identifiants OAuth du projet existant aussi, mais aucun
consentement n’a encore abouti pour ces deux chaînes. Les activations restent
désactivées et le studio en pause tant que la connexion réelle n’a pas réussi.
La collecte du radar prépare seulement des fiches de recherche : la recherche
éditoriale, le choix des faits et les contrôles autonomes de la création ne sont
pas un pipeline sans intervention déjà opérationnel. Ne pas confondre ce correctif
de publication avec une automatisation complète de la création.

Les voies examinées ne fournissent pas de raccourci garanti : Apps Script utilise
la même API et doit être autorisé, les comptes de service ordinaires ne disposent
pas des chaînes YouTube des comptes personnels, une clé API ne publie pas, et un
nouveau projet non audité peut être limité aux vidéos privées. Ne pas emprunter
le client d’une autre application ni déplacer les vidéos vers un éditeur tiers.
La règle d’usage personnel peut dispenser une petite équipe connue de revue,
mais ne donne pas de permission quand Google affiche réellement « This app is blocked ».
Un test réel du consentement et de la mise en ligne reste indispensable.

Références : [permissions des méthodes (discovery officiel)](https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest),
[envoi et restrictions des projets non audités](https://developers.google.com/youtube/v3/docs/videos/insert),
[service YouTube Apps Script](https://developers.google.com/apps-script/advanced/youtube).
