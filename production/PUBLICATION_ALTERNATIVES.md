# Autres voies de publication — recherche du 6 octobre 2026

L’utilisateur demande de sortir du parcours OAuth Edgerunners bloqué. Ce parcours
n’est pas la seule manière de publier. Le refus de notre application ne démontre
pas que tous les clients Google ou tous les mécanismes YouTube sont bloqués.
Ne pas revenir par défaut à la demande d’examen Branding.

**Préférence précisée ensuite :** aucun abonnement payant. L’utilisateur rappelle
que l’ancien site publiait gratuitement via Google. La sauvegarde a été comparée
au site actuel et un parcours compatible est implémenté :
[publication historique gratuite](LEGACY_YOUTUBE.md). Cette piste devient prioritaire.

**État au 7 octobre, heure de Paris :** le consentement réel reste bloqué après
restauration du parcours historique. L’utilisateur précise qu’il a lui-même créé
l’ancien studio et configuré Google ; ne pas attribuer cette configuration à Kanye.
Le compte YouTube est le même, le compte Console utilisé auparavant est incertain.
Aucun transport alternatif n’est actuellement connecté ou validé.

Les éléments ci-dessous sont vérifiés dans les documentations publiques. Aucun
prestataire n’a été activé et aucun compte, fichier ou jeton de chaîne ne lui a
été transmis. Aucun envoi alternatif réel n’a encore été testé.

## Relais de publication par API : Upload-Post

La documentation actuelle indique une connexion Google et un quota YouTube gérés
par le prestataire. Aucun projet Google Cloud du studio n’est requis. L’ancien
article de quota propose un client personnel : ce n’est pas la voie à choisir
pour ce test, qui reproduirait notre dépendance au projet bloqué.

Fonctions documentées :

- Vidéos YouTube classiques et Shorts, fichier MP4 envoyé en multipart.
- Titre, description, tags, image de miniature, déclaration du contenu synthétique.
- Visibilité privée, puis modification de visibilité via l’API d’édition.
- Pose séparée de miniature avec résultat explicite.
- Suivi des envois asynchrones et clé d’idempotence contre les doublons.
- Identifiant immuable de chaîne dans le profil, distinct du nom et du @pseudo.
- Connect API : départ depuis notre interface, consentement Google, callback du
  prestataire puis retour au studio ; échange et stockage des jetons chez lui.

Conditions et prix publiés :

| Usage | Limite ou prix |
| --- | --- |
| Essai sans carte bancaire | 2 profils, donc 2 chaînes YouTube ; 10 envois par mois au total |
| Publication régulière par API, Basic | 24 USD/mois en facturation mensuelle ; 16 USD/mois payés 192 USD/an |
| Intégration white-label annoncée dans la grille | Professional, 50 USD/mois en facturation mensuelle |
| Limite quotidienne YouTube du prestataire | 10 envois par chaîne sur 24 heures glissantes |

Ne pas supposer que la connexion entièrement intégrée est incluse dans le forfait
gratuit : la grille réserve le white-label au Professional. Le test gratuit peut
utiliser leur page de connexion une fois, puis l’API pour publier depuis Edgerunners.
Confirmer les droits précis de Connect API sur le forfait choisi avant de promettre
une connexion entièrement intégrée. Vérifier le prix affiché avant tout paiement.

Le prestataire reçoit les fichiers et conserve les autorisations Google nécessaires.
L’utilisateur refuse les abonnements et n’a pas choisi ce prestataire.
Aucune création de compte, souscription ni connexion à sa place.
Une autre application peut encore rencontrer une restriction propre au compte Google :
seul un consentement réel et une lecture de la bonne chaîne prouvent la connexion.

Parcours d’intégration préparé, à implémenter après choix :

1. Formulaire privé réservé au propriétaire pour la clé API, validation serveur et
   état du forfait ; la clé ne doit jamais revenir au navigateur ou à l’assistant.
2. Un profil dédié par chaîne. Lire l’ID YouTube retourné par le serveur et vérifier
   la destination réelle après consentement, avant d’activer une publication.
3. Garder les contrôles actuels de fichiers, empreintes, droits, actualité et pause.
4. Enregistrer un identifiant d’envoi stable avant la requête ; uploader en privé,
   suivre le résultat, appliquer la miniature, puis recontrôler les conditions.
5. Passer en public et confirmer l’ID, la chaîne et la visibilité retournés.
   Ni un HTTP 200 ni une tâche acceptée ne signifient « publié ». Conserver toute
   réponse ambiguë comme non confirmée, sans renvoyer une deuxième vidéo.

Sources : [envoi YouTube sans notre projet Google](https://docs.upload-post.com/guides/post-to-youtube-api/),
[connexion intégrable](https://docs.upload-post.com/api/connect-api/),
[envoi vidéo](https://docs.upload-post.com/api/upload-video/),
[édition de visibilité](https://docs.upload-post.com/api/edit-post/),
[miniature](https://docs.upload-post.com/api/youtube-thumbnail/),
[statut d’envoi](https://docs.upload-post.com/api/upload-status/),
[forfaits et limites](https://docs.upload-post.com/resources/pricing-and-limits/).

Zernio et Ayrshare documentent également des APIs de publication YouTube. Zernio
accepte les vidéos longues et les miniatures. Ayrshare documente l’utilisation des
APIs officielles, mais son forfait d’entrée affiché est bien plus cher (149 USD/mois)
et deux chaînes indépendantes exigent des profils adaptés. Aucun des deux n’a été
activé. Upload-Post offre le test documenté le plus accessible pour nos deux chaînes.

## Ingestion native YouTube par flux podcast RSS

YouTube Studio peut s’abonner à un flux podcast de notre site, créer les vidéos des
épisodes choisis, puis publier automatiquement les nouveaux épisodes. La documentation
indique que la visibilité par défaut peut être publique. Aucun client OAuth du studio
ni prestataire de publication externe n’est requis. France et Belgique sont dans la
liste de disponibilité publiée par YouTube.

Le format est explicitement **audio accompagné d’une image fixe**, créée à partir de
l’illustration du podcast. Cela ne transporte pas le MP4 monté, les visuels animés ou
nos sources affichées à l’écran. Ne pas remplacer le format des chaînes sans accord.
La mise en place peut prendre quelques jours selon YouTube ; aucun délai garanti
n’est documenté pour un nouvel épisode. Cela ne prouve pas une livraison en direct.

Mise en place si ce format est choisi :

1. Créer le flux et ses médias à partir de contenus nouveaux et contrôlés, sans
   réutiliser les trois vidéos déjà publiées. Préserver la gate de tout le studio.
2. YouTube Studio → Créer → Nouveau podcast → Envoyer un flux RSS.
3. Coller le lien, saisir le code envoyé à l’adresse de propriété du flux et choisir
   les épisodes futurs. L’accès aux fonctionnalités avancées est requis par YouTube.
4. Après l’ingestion initiale, Contenu → Podcasts → Publier ; visibilité RSS publique.
   Les épisodes futurs sont ensuite importés et publiés automatiquement par YouTube.

Aucun flux ni média public n’a été créé : choix de format et validation restent requis.

Sources YouTube : [fonctionnement et publication automatique](https://support.google.com/youtube/answer/13525207?hl=fr),
[configuration et mise en ligne](https://support.google.com/youtube/answer/13973017?hl=fr),
[disponibilité par pays](https://support.google.com/youtube/answer/14106258?hl=fr).

## Pilotage automatique du navigateur YouTube Studio

C’est une voie techniquement distincte de notre application OAuth : un navigateur
connecté au compte effectue les actions dans Studio. Elle implique une session Google
sur un serveur, des contrôles de destination et de doublons, et peut s’interrompre à
une reconnexion, un contrôle de sécurité ou un changement de l’interface.

Contrôle natif o2switch : aucun Chromium, Chrome ou Xvfb installé. L’accès aux tâches
du VPS, les permissions d’un navigateur et l’administration de l’hôte sont des
capacités distinctes, contrôlées ci-dessous. Aucune session de compte Google
disponible et aucun upload testé.

**Contrôles supplémentaires du 7 octobre :** l’API authentifiée du worker est
accessible et son endpoint de tâches accepte le code de montage livré par le studio.
Deux tâches de diagnostic bornées, sans envoi de vidéo, ont été exécutées puis
effacées. Elles confirment un conteneur Linux avec droits root et gestionnaire de
paquets, mais aucun navigateur ni serveur d’affichage installé. Le test de création
d’un espace de noms utilisateur par un processus non root retourne un refus de
permission. Cela ne valide pas le démarrage d’un navigateur correctement isolé.
L’accès administratif à l’hôte Docker reste distinct de l’accès aux tâches.

Sur o2switch, le compte n’est pas root et plusieurs bibliothèques nécessaires au
navigateur manquent. Aucun paquet, profil Google ou robot de publication n’a été
installé par ces diagnostics. Aucun contrôle de sécurité n’a été désactivé.
Ne pas présenter « un navigateur sur le VPS » comme un outil déjà opérationnel.

Des exemples publics confirment le principe d’automatisation par session de
navigateur, notamment [un outil Playwright pour Windows](https://github.com/The-Despicable/Youtube_Shorts_tools)
et [un outil WebView2 pour Windows](https://github.com/phongtrannm/nemo-youtube).
Leurs descriptions ne prouvent ni la compatibilité Linux, ni l’accès à nos chaînes,
ni la réussite d’un envoi. Le second contient une affirmation erronée selon laquelle
l’API officielle impose une autorisation à chaque exécution ; ne pas la reprendre.
Les sessions Google restent des accès sensibles, pas des substituts publics aux clés API.

Les conditions YouTube consultées depuis l’hébergement interdisent l’accès automatisé
hors exceptions, dont l’autorisation écrite de YouTube. Ce n’est donc pas une solution
contractuellement validée pour une publication permanente. Aucun contournement de
connexion, de CAPTCHA ou de contrôle de sécurité n’a été tenté.

Source : [conditions YouTube](https://www.youtube.com/static?template=terms).

## Utiliser le PC et sa connexion Internet

L’utilisateur propose ensuite son IP de PC. Lorsqu’il ouvre l’autorisation Google
dans Chrome sur ce PC, Google reçoit déjà la requête de cette connexion Internet,
sous réserve d’un proxy ou VPN configuré chez lui. L’échange du code sur o2switch
n’arrive qu’après acceptation. Déplacer cet échange ou le rendu vers le PC ne prouve
donc pas une résolution du refus affiché avant le retour au site.

Un navigateur de publication peut aussi fonctionner localement. Il utilise alors
la session YouTube et la connexion du PC, sans notre client OAuth. Cela nécessite
un PC allumé et connecté pour les publications ; ce n’est pas un service permanent
quand le PC est éteint. L’utilisateur a accepté cette contrainte : il souhaite
réserver le PC à l’envoi, être informé quand il travaille, et préparer les vidéos
côté serveur pendant son absence. La sélection et la création entièrement
automatiques restent à terminer ; ne pas les présenter comme opérationnelles.

Le diagnostic de la file PC commune a confirmé Windows et Chrome installé sur
l’agent exécutant, sans établir qu’il s’agissait du PC où l’utilisateur cliquait.
Une demande prise par ce relais ne prouve donc pas une fenêtre visible sur ce PC.
Le parcours de connexion n’utilise plus la file partagée : un assistant propre à
Edgerunners est lancé localement par l’utilisateur, via notre protocole Windows.
Son téléchargement privé, ses étapes et ses limites sont décrits dans
[DASHBOARD_STATUS.md](DASHBOARD_STATUS.md#connexion-sur-le-pc-qui-ouvre-le-site--7-octobre-2026).

Cette première étape ne contient pas encore le pilotage des formulaires d’envoi.
Une association Chrome ne marque donc pas la chaîne comme prête à publier et ne
change ni la pause globale, ni les droits, ni les jetons OAuth historiques. Il faut
encore une connexion réelle de l’utilisateur dans le Chrome dédié, puis vérifier
un envoi complet dans l’interface réelle avant d’intégrer cette voie au worker.
Aucun upload local alternatif n’a été testé. Ne pas dire que l’IP du PC résout
le refus OAuth : la connexion première partie à YouTube Studio est un autre parcours.

## État du studio conservé

Ces alternatives concernent le transport des publications. Le moteur qui choisit,
vérifie et produit seul les actualités reste à terminer. L’envoi des vidéos prêtes,
sans heure fixe sur Cage/Pitch, est implémenté et testé pour le transport Google
actuel. Les deux chaînes restent déconnectées, désactivées et le studio en pause.
Les contrôles de droits, de qualité et d’actualité restent obligatoires pour toute voie.
