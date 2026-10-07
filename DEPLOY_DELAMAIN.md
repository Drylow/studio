# Brancher les modifications du site dans Delamain

Cette fonction est connectée à **edgerunners.fr** depuis le 6 octobre 2026. Le premier
changement réel a modifié le sous-titre des tâches, passé 155 tests et la compilation,
redémarré Passenger, vérifié la version HTTPS et poussé le commit `b1da59e` sur `main`.
Les installations supplémentaires doivent réussir les contrôles ci-dessous avant
de se déclarer connectées. Le VPS de montage et ses clés ne donnent pas d'accès au code.

## Claude comme codeur (7 octobre 2026)

À la demande du propriétaire, Delamain peut faire coder ses demandes par **Claude (Sonnet)**
au lieu du service IA du serveur. Le site lance une **routine Claude Code** (déclencheur API)
avec la demande ; la session Claude suit `production/DELAMAIN_ROUTINE.md`, pousse une branche
`claude/delamain-…` avec un commit final `Delamain-Job` / `Delamain-Status`, puis l'exécuteur
reprend cette branche et applique **exactement les mêmes contrôles** : fichiers autorisés
seulement, tests d'origine copiés hors de la branche, compilation, démarrage Flask, sauvegarde
SQLite, maintenance, contrôle de version HTTPS, retour arrière et push de `main`. Mise en ligne
sans validation manuelle, choix explicite du propriétaire. Attente maximale : 45 minutes.

Brancher : **Réglages → Modifications du site → Brancher Claude**, coller l'adresse
`https://api.anthropic.com/v1/claude_code/routines/trig_…/fire` et le jeton générés sur
claude.ai (routine → Modifier → déclencheur API → Generate token). Le jeton est stocké dans la
base privée et n'est jamais renvoyé au navigateur. `STUDIO_DEV_ROUTINE_URL` et
`STUDIO_DEV_ROUTINE_TOKEN` dans `.env` sont aussi acceptés. Sans routine, l'ancien codeur
(`AI_BASE_URL`) reste utilisé. Les sessions lancées consomment l'abonnement Claude du compte.

## Ce que fait l'exécuteur

Le propriétaire choisit **Delamain → Modifier le site**, décrit le changement et
envoie le message. Une tâche réelle est créée, séparée de la production vidéo.
Le processus de développement prépare une copie Git privée, lit les fichiers utiles,
applique les changements, lance les tests Python d'origine et compile l'interface.
Les tests sont copiés hors du code modifiable ; l'agent ne peut pas les affaiblir.
Chaque cas de test s'exécute dans un processus distinct pour libérer la mémoire
entre les contrôles sur un hébergement mutualisé. Une découverte vide ou un seul
test en échec bloque toujours la mise en ligne.
Un démarrage Flask vérifie aussi l'accueil et l'espace de travail authentifié.

Quand les contrôles passent, l'exécuteur enregistre un commit et une branche
`delamain/site-…`, sauvegarde SQLite, met le site brièvement en maintenance,
installe le code, demande le redémarrage Passenger et contrôle la version réellement
chargée à `/health/studio`. Il pousse ensuite `main`, sans forcer ni écraser le
travail d'un autre contributeur. Une erreur de tests ne déploie rien ; un échec
après installation restaure le code précédent et contrôle son redémarrage.
Les vidéos, fichiers privés et clés restent en place. Les sauvegardes sont dans
`work/studio/backups/`, hors du dossier public.

Les demandes, états, contrôles, changements de code et commits sont visibles dans
le chat et **Réglages → Modifications du site**. « En ligne » exige le contrôle
de la version publique, pas seulement une commande Git réussie.

## Installation unique sur o2switch

Terminer d'abord [le déploiement du studio](DEPLOY_O2SWITCH.md).
Le site doit être installé par Git, sur `main`, sans modification locale en attente.
Le serveur web, le moteur vidéo et l'exécuteur de développement utilisent la même
base SQLite et les mêmes fichiers. Les modifications ne sont pas exécutées dans
une requête web ; fermer le navigateur n'interrompt pas une demande.

1. **cPanel → Terminal** : coller la commande `source …` affichée dans
   **Setup Python App**, puis se placer dans le dossier du studio :

   ```bash
   cd /home/TONUSER/edgerunners_studio
   git switch main
   git pull --ff-only origin main
   python -m pip install -r requirements.txt
   ```

2. Installer une version de Node compatible avec `frontend/package.json`.
   Dans **cPanel → Setup Node.js App**, créer/activer l'environnement Node si
   nécessaire, puis conserver le chemin absolu de son executable `npm`.
   Si Node n'est pas disponible sur l'offre, l'exécuteur ne peut pas compiler les
   changements : demander son activation à o2switch avant d'activer cette fonction.
   Les ressources du compte doivent permettre une copie du dépôt, les tests et la
   compilation. L'exécution n'est pas un bac à sable système : ce code tourne sous
   le compte d'hébergement, réservé au propriétaire. Les sous-processus de tests et
   de compilation ne reçoivent pas les secrets du site dans leur environnement.

3. Autoriser **l'écriture Git depuis ce serveur** avec une clé de déploiement du
   dépôt. Si l'accès existant fonctionne, le réutiliser. Sinon, dans Terminal :

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/edgerunners_deploy -N '' -C 'Edgerunners deployment'
   cat ~/.ssh/edgerunners_deploy.pub
   ```

   Copier uniquement la **clé publique** affichée. Sur GitHub :
   **Drylow/studio → Settings → Deploy keys → Add deploy key**, coller cette clé,
   cocher **Allow write access**, puis **Add key**.
   Dans `~/.ssh/config`, ajouter :

   ```sshconfig
   Host github-edgerunners
       HostName github.com
       User git
       IdentityFile ~/.ssh/edgerunners_deploy
       IdentitiesOnly yes
   ```

   Puis :

   ```bash
   chmod 600 ~/.ssh/config
   git remote set-url origin git@github-edgerunners:Drylow/studio.git
   git ls-remote origin main
   ```

   À la première connexion SSH, vérifier l'empreinte GitHub avec
   [la documentation officielle](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints)
   avant d'accepter. Ne jamais désactiver ce contrôle ni envoyer la clé privée dans le chat.

4. **cPanel → Gestionnaire de fichiers** : ouvrir le fichier privé `.env` dans
   le dossier `edgerunners_studio` et ajouter :

   ```dotenv
   STUDIO_DEV_ENABLED=1
   STUDIO_DEV_HEALTH_URL=https://ton-domaine.fr/health/studio
   STUDIO_DEV_NPM=/chemin/absolu/vers/npm
   ```

   Remplacer le domaine et le chemin npm. Les clés `AI_BASE_URL`/`AI_API_KEY`
   déjà configurées sont réutilisées ; aucune nouvelle clé IA n'est nécessaire.
   Le `.env` commun est nécessaire car les variables de l'application cPanel ne
   sont pas automatiquement disponibles en cron. Conserver `STUDIO_PREVIEW=0`.
   Ajouter Node au `PATH` du cron pour que `npm` puisse trouver `node`.
   Le cache npm est réutilisé dans `work/studio/npm-cache`, avec les sommes de
   contrôle du lockfile. Un cache existant peut être indiqué par
   `STUDIO_DEV_NPM_CACHE=/chemin/du/cache` ; aucune vérification TLS ou d'intégrité
   n'est désactivée.

5. **Setup Python App → Restart**, puis dans Terminal, avec le virtualenv actif :

   ```bash
   python -m studio.developer --check
   ```

   Cette commande vérifie le dépôt, l'accès Git en écriture sans pousser, npm et
   la version chargée par l'adresse publique. Elle ne modifie pas le site.
   Une erreur est enregistrée dans **Réglages → Modifications du site**.

6. **cPanel → Tâches cron → Ajouter**, choisir **chaque minute**. Dans Commande :

   ```bash
   /bin/bash -c 'export PATH=/DOSSIER_DES_EXECUTABLES_NODE:/usr/local/bin:/usr/bin:/bin; cd /home/TONUSER/edgerunners_studio && exec /home/TONUSER/virtualenv/edgerunners_studio/3.11/bin/python -m studio.developer' >> /home/TONUSER/edgerunners-developer.log 2>&1
   ```

   Remplacer `TONUSER`, `3.11` et `DOSSIER_DES_EXECUTABLES_NODE` par les chemins
   donnés dans cPanel. Le verrou interne empêche deux exécuteurs de travailler
   simultanément. Chaque invocation traite au plus une demande, puis sort : la
   suivante charge le nouveau code. Le moteur vidéo existant quitte à la fin de
   son travail après un changement de version ; son cron habituel le relance.

7. Attendre le passage du cron puis actualiser **Réglages → Modifications du site**.
   L'état **CONNECTÉ** exige une configuration complète, un contrôle réussi et
   un signe de présence récent de l'exécuteur. Tester une petite demande :
   **Delamain → Modifier le site → « Ajoute une courte phrase sous le titre
   de la page des tâches » → Envoyer**. Contrôler le résultat et la version affichée.
   Ce premier essai sur le vrai hébergement reste indispensable ; les essais de
   développement ne prouvent pas les accès ni les ressources d'o2switch.

## Limites et reprise

- Le compte propriétaire peut demander des changements de présentation et des
  fonctionnalités dans `frontend/src/`, les services, les routes et certains modules
  `studio/`. Les fichiers d'authentification, de base de données, de connexion YouTube,
  l'exécuteur, les tests, les dépendances et l'hébergement sont protégés. Leur modification
  passe par le développement du dépôt ; le chat ne peut pas tout réécrire sans limite.
- Pas de génération autonome de nouveaux secrets, pas de création de compte cPanel,
  pas d'achat de domaine. Ces accès et services doivent exister au départ.
- Une seule modification est autorisée à la fois, avec au maximum 16 échanges IA.
  Une demande peut échouer ou nécessiter une précision ; un résultat n'est jamais garanti.
  Une demande en attente peut être annulée via son endpoint ; une exécution commencée
  est laissée terminer pour éviter une interruption pendant une installation.
- Si un travail vidéo tourne au moment du déploiement, la mise en ligne est refusée.
  Attendre sa fin et redemander le changement. La branche préparée est conservée.
- Une interruption ne répète pas aveuglément un déploiement. Le passage suivant du
  cron réconcilie son journal avec Git et la version publique. Si l'ancien site ne
  redémarre pas, la maintenance est conservée et un contrôle serveur est requis.
- Le retour automatique restaure le code, pas la base SQLite. Les migrations de base
  ne sont pas modifiables dans ce mode ; la sauvegarde est conservée pour une intervention
  si nécessaire. Les sauvegardes/branches nécessitent une gestion de rétention à terme.
- Les contrôles exécutent les tests Python d'origine, la compilation TypeScript/Vite,
  un démarrage Flask et une vérification de version HTTP. Ils ne garantissent pas qu'une
  modification visuelle sera parfaite sur tous les téléphones, ni l'absence de tout bug.

Sources : [redémarrage Passenger](https://www.phusionpassenger.com/docs/advanced_guides/troubleshooting/apache/restart_app.html),
[Python sur o2switch](https://faq.o2switch.fr/cpanel/logiciels/hebergement-python-multi-version/),
[cron sur o2switch](https://faq.o2switch.fr/hebergement-mutualise/tutoriels-cpanel/taches-cron).
