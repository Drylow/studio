# Connexion directe à YouTube Studio sur le VPS

Ce parcours permet au propriétaire de se connecter au **vrai site YouTube Studio**
dans un Firefox privé sur le VPS, depuis Edgerunners. Rien à installer sur son PC,
aucun prestataire de publication et aucun client OAuth emprunté. Les vérifications
Google restent obligatoires ; une page de connexion accessible ne prouve pas une
connexion ni un envoi réussi.

**État : connexion interactive et contrôle de session. Le transport d’envoi par le
navigateur reste à terminer et à tester avec une chaîne réellement connectée.**
Ne pas annoncer l’autopublication opérationnelle. Ne pas activer Cage/Pitch ni la
pause globale sur la seule base de ce parcours. Ne pas réenvoyer les vidéos déjà
publiées manuellement.

## Utilisation

Après activation serveur de `YOUTUBE_BROWSER_ENABLED=1`, ouvrir Chaînes → chaîne
concernée → Connecter YouTube → **Ouvrir YouTube sur le serveur**. Cliquer sur le
champ Google dans l’écran, saisir le texte dans le champ protégé du studio, puis
**Écrire dans Google** et **Entrée**. Terminer les contrôles Google habituels et
choisir la chaîne. **J’ai terminé la connexion Google** vérifie son identité ; cela
ne constitue pas un test de publication. Fermer l’écran privé après utilisation.

L’API Google historique reste dans « Autre méthode : API Google ». Ses jetons,
permissions et l’historique ne sont pas modifiés par cette connexion navigateur.

## Fonctionnement et accès

- `studio/browser_connection.py` : écran réservé au propriétaire et à sa session
  privée actuelle, CSRF, version de chaîne, expiration de 20 minutes, fermeture
  après déconnexion/changement de rôle/retrait ou modification de la chaîne.
- Le VPS initie les échanges HTTPS avec une route machine dédiée. HMAC à usage
  séparé dérivé du jeton du worker, horodatage et nonce à usage unique ; aucun port
  de navigateur ou VNC public. Cette route n’accepte pas la connexion d’un visiteur.
- Le texte saisi est chiffré dans le navigateur du propriétaire : RSA-OAEP et
  AES-GCM, clé privée temporaire uniquement en mémoire sur le VPS. Le relais et
  SQLite ne reçoivent pas de mot de passe Google en clair. Ni shell, argument de
  programme, fichier temporaire ou log ne reçoit la saisie déchiffrée.
- Les images d’écran sont privées, sans cache, conservées temporairement dans la
  base privée et effacées lors de la fermeture ou de l’expiration. Ne jamais les
  exporter dans Git ou des services de captures externes.
- Firefox s’exécute sous `edg_browser`, avec son compte/home dédié. Aucune clé du
  worker/fournisseur ne passe dans son environnement. Les protections et contrôles
  TLS du navigateur restent activés. Xvfb exige une autorisation privée et n’écoute
  pas sur TCP. Pas de drapeau anti-détection ni de contournement de CAPTCHA.
- Chaque chaîne a un profil 700 sous `/data/edgerunners-browser-service/profiles/`.
  Les sessions Google restent sur le VPS de confiance ; aucun export de cookies ou
  récupération d’identifiants dans les anciens profils du propriétaire.
- Le service est démarré à la demande via l’API de montage déjà autorisée, dans
  `/data/edgerunners-browser-runtime/`, hors du dossier de travail effacé après un
  montage. Debian vérifie ses paquets ; cryptography est installé depuis PyPI avec
  TLS dans un dossier privé. Après recréation/redémarrage du conteneur, rouvrir le
  navigateur le redémarre. L’écran n’annonce jamais une connexion disponible avant
  réception du heartbeat signé.

## Vérifications effectuées

Le test anonyme du VPS ouvre la page Google officielle de YouTube dans le Firefox
graphique, capture un écran 480 × 820 et exécute une touche normale. Le contrôle
retrouve un compte non connecté et aucun accès de chaîne. Aucun mot de passe ni
vidéo utilisé. Le test local du site couvre l’accès privé, le refus des entrées non
chiffrées, des requêtes rejouées, de l’éditeur et de l’aperçu, ainsi que les révocations.
Les tests d’interface utilisent uniquement des réponses fictives et ne prouvent
aucune autorisation Google ou publication.

Le 7 octobre, le parcours complet a aussi été testé **sur edgerunners.fr**, avec une
session propriétaire de test de 300 secondes révoquée à la fin : heartbeat signé
du VPS, écran Google anonyme 480 × 820, aller-retour d'une touche chiffrée, inspection
« connexion nécessaire », fermeture de l'écran et maintien de la pause sportive.
L'éditeur et une requête machine sans signature sont refusés. Le navigateur n'a
pas été refusé sur cette page anonyme ; cela ne prédit pas l'acceptation d'un vrai
compte. Aucun identifiant Google, accès de chaîne ou fichier vidéo n'a été utilisé.

Le code déployé est `2795223`. Les preuves restent privées sur o2switch dans
`work/studio/private-browser-deployment.json` et
`work/studio/private-browser-live-test.json`. L'utilisateur n'a pas effectué la
connexion proposée et a demandé une passation à Claude. Lire
[le dossier de reprise](CLAUDE_HANDOFF_2026-10-07.md) pour les limites et la suite.
