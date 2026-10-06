# Edgerunners Studio sur o2switch

Guide actualisé le 6 octobre 2026 pour le nouveau studio React/Flask. L'ancien guide,
son archive de déploiement, son écran boss/guest et son cron HTTP ne s'appliquent plus.

## Installation réelle — edgerunners.fr

Le studio est installé sur **https://edgerunners.fr/**, après sauvegarde de l'ancien
site et copie SQLite cohérente vérifiée. Une deuxième copie privée de cette sauvegarde
a été téléchargée dans l'espace de travail cloud. Les anciens fichiers restent dans
un dossier privé distinct sur le serveur ; `public_html` contient seulement les règles
Apache/Passenger et les dossiers système conservés.

- Code : `/home/TONUSER/drylow_studio`, dépôt Git sur `main`.
- Python : `/home/TONUSER/edgerunners_venv/bin/python`, version 3.12.14.
  Ce nouvel environnement laisse intact l'ancien virtualenv pour le retour arrière.
- Node/npm : `/opt/alt/alt-nodejs22/root/usr/bin/`, version 22.23.3.
- Base conservée : `/home/TONUSER/drylow_studio/drylow_studio.db`.
- Deux comptes : `drylow` (propriétaire) et `kanye` (collaborateur).
  Leurs mots de passe initiaux sont dans `/home/TONUSER/edgerunners-access.txt`,
  privé et hors du dossier public. cPanel → Gestionnaire de fichiers → dossier
  principal du compte → ce fichier → Afficher. Chacun peut changer son mot de passe
  dans Réglages → Accès privé.
- Le cron distinct `studio.worker`, relancé chaque minute avec `flock`, est installé
  et son heartbeat ainsi qu'une réponse réelle de Delamain ont été vérifiés.
  L'ancien cron HTTP est désactivé. La publication automatique reste en pause.
- La clé Git de déploiement est autorisée en écriture. Son identité SSH et les clés
  d'hôte GitHub vérifiées sont conservées sur le serveur ; la configuration Git
  s'applique seulement au dépôt du studio et à ses copies privées de développement.
  Le contrôle Git/npm/version publique et le cron `studio.developer` sont installés.

Le premier changement demandé dans **Delamain → Modifier le site** a réellement
modifié le sous-titre des tâches, exécuté les 155 tests et la compilation, sauvegardé
SQLite, redémarré Passenger, contrôlé la version HTTPS et poussé `main`.
Commit de cet essai : `b1da59e48f099e28f9353d05295c0423cd063afb`.

Les connexions HTTPS des deux comptes, les rôles, les cookies Secure/HttpOnly,
CSRF/origine, la révocation d'une session copiée, HSTS et les refus des fichiers privés
ont été contrôlés sur le vrai domaine. Les 155 tests Python passent sur le serveur
avec des processus séparés pour les contrôles de développement. Sept pages et les
connexions ont été rendues à 390 et 1440 px à partir des réponses HTTPS du vrai serveur
via un proxy local privé ; les cookies HTTPS ont été vérifiés séparément par accès direct.

Les clés IA, voix, montage et Discord existantes ont été installées en privé. Le relais
de montage répond à `/status` avec authentification. Les paramètres Google et la chaîne
historique **Le Grand Récap** sont conservés, mais Google refuse son ancien jeton avec
`invalid_grant` : une reconnexion OAuth est nécessaire. Les sept autres chaînes ne sont
pas encore reliées à YouTube. Aucun upload YouTube ni envoi Discord n'a été effectué
pendant ce déploiement. Avant de connecter une chaîne, vérifier l'adresse de retour
Google indiquée à l'étape 3. Cet hébergement réutilise l'ancien chemin enregistré
`/api/youtube/callback` via `OAUTH_CALLBACK_PATH` : le nouveau handler conserve les
contrôles de session, de rôle et d'état à usage unique sur les deux adresses.

Ne pas annoncer une publication quotidienne autonome : les connexions, les contrôles
éditoriaux et les adaptateurs de droits indiqués dans `production/DASHBOARD_STATUS.md`
restent nécessaires.

Les documents publics de Branding sont servis aux chemins `/about`, `/privacy` et
`/terms`, indépendamment de la gate privée. Leurs liens sont affichés sur l’écran
de connexion. La configuration Google correspondante est dans `GOOGLE_YOUTUBE.md`.
Ne pas rendre publiques les APIs, médias, sessions ou callbacks OAuth pour faciliter
une vérification Google. Le blocage OAuth n’est pas une panne de l’hébergement.

## Ce qui continue après l'hébergement

Les chaînes, tâches, réglages, vidéos et créneaux sont enregistrés dans SQLite.
Delamain utilise le service IA configuré sur le serveur ; c'est l'assistant intégré
au site, distinct de la conversation de développement. Il reste utilisable quand
le site est hébergé, avec les permissions du compte connecté et les contrôles habituels.
La publication directe YouTube ne nécessite pas Discord.

L'interface et le code peuvent être mis à jour depuis GitHub même après l'hébergement.
Le mode **Delamain → Modifier le site** utilise maintenant un exécuteur séparé
pour modifier le code, tester, compiler et mettre le site à jour avec contrôle
de version et retour au code précédent en cas d'échec. Il faut le connecter
une fois sur le serveur : suivre [DEPLOY_DELAMAIN.md](DEPLOY_DELAMAIN.md).
L'état de connexion et les résultats sont visibles dans Réglages.
Les fichiers de sécurité, les dépendances et les migrations restent protégés.
Ne pas annoncer que le déploiement sur o2switch fonctionne avant l'essai réel.

## 1. Créer l'application Python

1. cPanel → Logiciels → Setup Python App → Create Application.
2. Choisir Python 3.11 ou une version plus récente compatible avec les dépendances.
3. Application root : `edgerunners_studio`, hors de `public_html`.
4. Application URL : sélectionner le domaine définitif du studio.
5. Application startup file : `passenger_wsgi.py`.
6. Application entry point : `application`.
7. Cliquer Create et conserver la commande `source ...` proposée par cPanel.

Importer le code actuel de `Drylow/studio`, branche `main`, par Git ou gestionnaire
de fichiers. Le bundle compilé dans `static/studio/` est déjà dans le dépôt ; Node
n'est pas requis pour afficher le site. Les moteurs documentaires peuvent en avoir besoin.
Ne pas importer un ancien zip contenant une interface `tool_apps/config.js`.
Conserver les données existantes et configurer leur chemin ; ne pas remplacer une base
en service par une base vide ni publier `.env`, les médias privés ou SQLite sous `public_html`.

Dans cPanel → Terminal : coller la commande `source ...` fournie, se placer dans
le dossier de l'application, puis lancer :

```bash
python -m pip install -r requirements.txt
```

Les dépendances comprennent les moteurs vidéo, pas seulement Flask. Vérifier sur
l'offre choisie le stockage, la mémoire, le temps de rendu et les exécutables Node/ffmpeg.
Si les rendus dépassent les ressources disponibles, utiliser un VPS adapté. Le code
actuel du worker et du serveur nécessite la même base et les mêmes fichiers : deux
copies SQLite sur des machines différentes ne partagent pas les tâches.

## 2. Configurer le serveur une fois

Créer `.env` à partir de `.env.example` dans le dossier privé de l'application,
ou utiliser les variables cPanel pour le serveur. Le worker lancé en cron doit
recevoir les mêmes valeurs : les variables cPanel de l'application web ne lui sont
pas automatiquement transmises. Un `.env` privé commun est lu par les deux processus.

Régler ces valeurs sans afficher les secrets dans les logs :

```dotenv
FLASK_ENV=production
COOKIE_SECURE=1
STUDIO_PREVIEW=0
STUDIO_WORKER_ENABLED=0
STUDIO_HOSTED=1
STUDIO_PUBLIC_URL=https://ton-domaine.fr
DB_PATH=/home/TONUSER/edgerunners_data/studio.db
OAUTH_REDIRECT_BASE=https://ton-domaine.fr
```

Remplacer `TONUSER` et le domaine par ceux de l'hébergement. `DB_PATH` doit désigner
la base conservée ou son transfert contrôlé, avec ses productions disponibles au bon
chemin. `FLASK_SECRET_KEY` doit rester stable entre serveur web, worker et mises à jour.
Les clés IA/voix/montage existantes restent privées côté serveur ; ne pas les redemander
si elles sont déjà configurées. Donner à `.env` des droits de lecture limités au compte.
Le worker intégré est désactivé ici : un worker distinct est lancé à l'étape 5.

Activer HTTPS dans cPanel → SSL/TLS Status → AutoSSL. Puis Setup Python App → Restart.
Passenger active le mode hébergé même si un ancien `.env` indique « développement ».
Il refuse de démarrer en aperçu, sans adresse HTTPS ou avec une clé de session faible.
Le studio est réservé à **deux comptes**, chacun avec un mot de passe personnel fort.
Aucune application, aucun QR code et aucun code téléphone ne sont nécessaires, selon
le choix confirmé par l’utilisateur. Conserver `FLASK_SECRET_KEY` stable pour signer les
sessions ; la sauvegarder en privé.

Le dossier public créé par cPanel doit être vide des anciens fichiers du site.
Les sauvegarder hors de `public_html` avant remplacement. Ajouter les règles de
`public/.htaccess` au `.htaccess` de ce dossier public **en conservant les directives
Passenger générées par cPanel**. Ces règles bloquent les fichiers physiques privés
qu'Apache pourrait servir sans passer par Flask. Ne jamais relier tout le dépôt au
dossier public ; `.env`, SQLite, `work/`, `news/`, `presets/` et les vidéos restent privés.
Donner au dossier de données des permissions `0700` et à `.env` des permissions `0600`.
Flask limite aussi les fichiers publics aux bundles compilés et aux polices.

Au premier lancement, utiliser le code `STUDIO_BOOTSTRAP_TOKEN` du fichier privé dans
l'écran Code d'installation, créer Drylow, puis Réglages → Équipe → Ajouter Kanye.
Ensuite chacun entre simplement son identifiant et son mot de passe. Le code
d'installation ne sert qu'à créer le premier compte et ne revient pas à chaque
connexion. Suivre [PRIVATE_ACCESS.md](PRIVATE_ACCESS.md) pour les étapes.
Les mots de passe ACCESS_PASSWORD/BOSS_PASSWORD et l'ancien triple-clic ne sont plus utilisés.

Avant ouverture, tester sur le **vrai domaine** sans cookie : pages redirigées vers la
connexion, API et vidéos refusées, fichiers privés et anciens médias inaccessibles.
Vérifier le cookie `__Host-edgerunners` Secure/HttpOnly, le retour Google en HTTPS et
la déconnexion immédiate d'une copie de session. Contrôler les deux comptes avant
d'activer le worker. Les essais cloud ne remplacent pas ce contrôle Apache/Passenger.

## 3. Créer l'accès Google pour tout le studio

Cette configuration se fait une seule fois ; la connexion des chaînes se fait ensuite
dans le studio. Utiliser Google Cloud Console : https://console.cloud.google.com/

1. Créer ou sélectionner un projet.
2. APIs et services → Bibliothèque → YouTube Data API v3 → Activer.
3. Google Auth Platform : renseigner Branding, Audience et les adresses demandées.
   Pour un essai en mode Testing, ajouter les comptes Google concernés comme utilisateurs de test.
4. Data Access : configurer les autorisations YouTube correspondant à la lecture et
   à la gestion des vidéos (`youtube.readonly` et `youtube.force-ssl`).
5. Clients → Create client → Web application.
6. Authorized redirect URIs : ajouter exactement l'adresse suivante, avec ton domaine :

```text
https://ton-domaine.fr/api/studio/youtube/callback
```

Pour un client existant enregistré avec `https://ton-domaine.fr/api/youtube/callback`,
conserver cette adresse et ajouter `OAUTH_CALLBACK_PATH=/api/youtube/callback` au `.env`.
Le studio accepte cet ancien chemin avec les mêmes contrôles OAuth. Les nouveaux
clients utilisent le chemin moderne ci-dessus avec `OAUTH_CALLBACK_PATH` vide.

7. Enregistrer le client. Copier son identifiant dans `GOOGLE_CLIENT_ID` et son secret
   dans `GOOGLE_CLIENT_SECRET`, uniquement dans la configuration privée du serveur/worker.
8. Garder `OAUTH_REDIRECT_BASE=https://ton-domaine.fr` cohérent avec cette adresse.
9. Redémarrer l'application et le worker. Réglages → Connexions indique la présence
   de cette configuration ; ce badge n'est pas un test réseau.

Les autorisations en mode Testing peuvent expirer et Google peut exiger une validation
ou un audit pour l'usage prévu et la publication publique via l'API. Un projet non audité
peut rester limité aux chargements privés. Vérifier ces conditions avant d'activer
la publication autonome ; une connexion réussie ne prouve pas que l'application
est autorisée à rendre les vidéos publiques.
Documentation Google : https://developers.google.com/youtube/v3/docs/videos/insert

## 4. Relier chaque chaîne et publier directement

1. Studio → Chaînes → Connecter YouTube sur la chaîne, en Répartition ou Fiches des chaînes.
   Le même bouton est présent dans ses Réglages. La connexion est réservée au propriétaire.
2. Dans la fenêtre : Connecter avec Google → choisir le compte et la chaîne correspondants.
3. Accepter les autorisations ; le studio affiche le nom et l'identifiant de la chaîne reliée.
   La fiche doit correspondre au vrai nom YouTube lors de la première connexion.
   Ensuite, l'identifiant mémorisé empêche de reconnecter accidentellement une autre chaîne.
4. Cliquer Vérifier la connexion pour interroger Google sans envoyer de vidéo.
   Delamain peut aussi le faire si le compte demandeur est propriétaire.
5. Recommencer pour chacune des chaînes.

La connexion ne lance aucune vidéo et n'active pas l'automatisation. Déconnecter demande
confirmation, retire l'accès local et met la chaîne en pause ; son identifiant reste
mémorisé pour les futures reconnexions. Cela ne supprime pas son compte YouTube.

Dans une fiche vidéo : terminer les fichiers, la miniature, les droits et la relecture,
valider si nécessaire, puis Publication → Publier sur YouTube. On peut aussi demander à Delamain
« Publie [titre exact] sur [chaîne] ». Une mise en file attend le worker ; l'identifiant
YouTube et le statut confirmé apparaissent ensuite. Discord reste une action séparée.
Les formats Oddly/History restent bloqués tant que leur adaptateur de droits n'est pas terminé.
Aucun réglage ne remplace les droits ou les contrôles des contenus réellement rendus.

## 5. Garder Delamain et les publications en service

Le processus web Passenger peut être recyclé. Utiliser un worker séparé pour traiter
les demandes et créneaux même quand personne ne regarde le site. Le module actuel
crée son propre accès aux routes protégées ; il ne démarre pas un second serveur web.

Dans cPanel → Tâches cron : choisir Toutes les minutes. Exemple à adapter aux chemins
réels de l'application et du Python du virtualenv fourni par cPanel :

```bash
flock -n /home/TONUSER/.edgerunners-worker.lock /bin/bash -c 'cd /home/TONUSER/edgerunners_studio && exec /home/TONUSER/virtualenv/edgerunners_studio/3.11/bin/python -m studio.worker' >> /home/TONUSER/edgerunners-worker.log 2>&1
```

`flock` évite de lancer plusieurs workers ; le cron relance le processus s'il se termine.
L'ancien `/api/delamain/worker/tick` ne fait pas partie du nouveau site. L'installation
réelle, les limites du compte et un cycle complet doivent être vérifiés sur l'hébergement.
Contrôler Centre de contrôle → moteur disponible et, d'abord, une tâche Delamain sans
production, puis un essai contrôlé sur une vidéo approuvée avant d'activer les cadences.
Le pipeline charge d'abord en privé avant de demander la mise en public ; un essai
restant volontairement privé jusqu'au bout n'est pas encore proposé dans l'interface.

## 6. Mettre à jour le site déjà hébergé

1. Réglages → mettre le studio en pause et attendre la fin des travaux en cours.
2. Désactiver temporairement le cron. Dans Terminal, `ps -u "$USER" -o pid,args`
   affiche les processus ; relever le PID de la ligne `python -m studio.worker`,
   puis `kill PID` pour arrêter uniquement ce worker. Remplacer PID par ce numéro.
3. Sauvegarder la base et les médias avec une méthode cohérente pour SQLite ; ne pas
   copier seulement le fichier `.db` pendant qu'une connexion écrit en WAL.
4. Dans le dossier privé du code : `git pull --ff-only origin main`, ou uploader les
   fichiers modifiés et le bundle compilé. Conserver `.env`, SQLite et les productions.
5. Si requirements.txt a changé, relancer `python -m pip install -r requirements.txt`
   dans le virtualenv cPanel.
6. Setup Python App → sélectionner le studio → Restart.
7. Réactiver le cron, vérifier connexion, tâches, planning et moteur, puis enlever la pause.

En cas de problème, remettre le code de la version précédente et restaurer les données
uniquement selon la migration et la sauvegarde concernées. Garder une sauvegarde indépendante
du serveur. Le script d'un agent de développement devra automatiser ce parcours avant
que Delamain puisse appliquer lui-même une modification du code depuis le site.

Sources o2switch consultées le 5 octobre 2026 :
- Python : https://faq.o2switch.fr/cpanel/logiciels/hebergement-python-multi-version/
- Cron et flock : https://faq.o2switch.fr/hebergement-mutualise/tutoriels-cpanel/taches-cron
