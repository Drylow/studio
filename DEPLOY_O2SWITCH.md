# Edgerunners Studio sur o2switch

Guide du 5 octobre 2026 pour le nouveau studio React/Flask. L'ancien guide,
son archive de déploiement, son écran boss/guest et son cron HTTP ne s'appliquent plus.
Aucun déploiement o2switch ni connexion Google réelle n'a été effectué ici.

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
Au premier lancement, utiliser le code `STUDIO_BOOTSTRAP_TOKEN` du fichier privé dans
l'écran Code d'installation, créer Drylow, puis Réglages → Équipe → Ajouter Kanye.
Les mots de passe ACCESS_PASSWORD/BOSS_PASSWORD et l'ancien triple-clic ne sont plus utilisés.

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
