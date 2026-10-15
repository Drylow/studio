# Outils et reprise sur un autre compte

## Ultravid

L'utilisateur a confirmé le nom **Ultravid** et précisé qu'il s'agit d'un site.
La création de FROM y est en cours selon sa déclaration. Aucun projet n'a été
inspecté depuis cette IA. L'URL de sa session et les identifiants de projets
ne sont pas enregistrés : ne pas choisir un site homonyme au hasard.

Sur le même PC, accéder au compte Ultravid déjà utilisé si la session est encore
ouverte. Sinon, l'utilisateur doit s'y reconnecter lui-même. Un changement de
compte IA ne copie pas les identifiants, sessions, crédits ni projets d'un service
externe. Relever les liens des projets et exporter les vidéos terminées dans le
dossier de la bonne chaîne dès qu'ils sont disponibles.

Ne pas reconstruire le site ni annoncer avoir sauvegardé son code. Ce dossier
sauvegarde les décisions, ressources locales et méthodes de notre projet.

## Scriptwriting local

Lot du 15 octobre : `scripts-2026-10-15/` contient les six narrations,
les plans éditoriaux, les sources et les relectures. Les textes complets
ne nécessitent aucun outil pour être lus ou importés dans Ultravid.

Exécuteurs techniques du dépôt : `production/sleep_script_batch.py`,
`sleep_script_supplements.py`, `sleep_script_review.py` et
`sleep_script_finalize.py`. Ils utilisent `services/ai.py` et le fournisseur
déjà configuré dans le `.env` privé ; aucune clé n'est incluse dans la reprise.
La sélection de rédaction du `.env` était obsolète lors du travail : une
sélection disponible a été passée dans l'environnement du processus, sans
modifier le fichier partagé. Sur une nouvelle session, consulter les capacités
annoncées par ce même proxy. Ne pas changer de fournisseur par défaut.

Les plans et les ajouts de sujets sont écrits par Codex ; la rédaction assistée
et les rapports ne valent pas approbation. Les relectures séparées sont suivies
de corrections et d'arbitrages sourcés. Ne pas relancer l'exécuteur de brouillons
sur les textes corrigés : son seuil de reprise pourrait écraser un chapitre
raccourci volontairement. Le finaliseur assemble les chapitres existants sans
appel IA. Les décomptes de mots ne mesurent pas la durée de la voix.

Dans le dépôt :

- services/facelessos.py : lecture des skills, scanner et statistiques.
- skills/facelessos/ : pack original de scriptwriting et audits.
- chaines/quiet-paradox/01-silo/ : narration finale et contrôles.

Dans le paquet autonome : copies dans outils/scriptwriting/ et
quiet-paradox/silo-dossier-original/. Ces copies ne dépendent pas de la mémoire
du chat. Python 3.10+ suffit aux fonctions locales de lecture et scanner.
Les outils IA externes restent à reconnecter si nécessaire.

Adaptation sleep : narration naturelle, calme et modulaire, pas de rehooks
agressifs. Compter les mots, puis mesurer la narration générée. Les anciennes
estimations Silo ne remplacent pas la durée observée de sa vidéo publiée.

## Recherche de sujets

Algrow et Nexlev sont des connexions liées au compte de l'application, pas des
fichiers exportables. Les reconnecter sur le nouveau compte si disponibles.
Une recherche publique sur YouTube peut compléter le travail en leur absence.
Les références et observations sont sauvegardées dans RECHERCHE.md.

Vérifier les dates et compteurs avant de présenter un sujet comme actuel.
Les vues publiques ne sont pas des métriques Studio privées ni une preuve causale.
Ne pas inventer de score d'outlier.

## Miniatures

La méthode technique de génération et les recettes exactes sont préservées dans
outils/miniatures/ du **paquet autonome**, avec les archives correspondantes.
Cet exécuteur envoie les prompts et références explicitement indiqués ; il ne les
réécrit pas, ne choisit pas d'autres images et ne relance pas automatiquement un échec.
Le mode normal contrôle les entrées sans lancer de génération payante.

Replicate est le service externe utilisé pour les derniers tests. La clé reste
uniquement dans l'environnement local ou le .env ignoré du dépôt :
**REPLICATE_API_TOKEN**. Ne pas la recopier dans ce dossier, le chat ni Git.
Sur un autre PC, renseigner la clé dans un fichier privé séparé ou une variable
d'environnement, puis utiliser l'option --env-file de l'exécuteur.
Sur le même PC, le .env existant peut être lu sans afficher son contenu.

Les recettes conservées reproduisent des demandes déjà exécutées. Leur présence
n'est pas une invitation à refaire les miniatures désormais acceptées. Inspecter
le résultat et conserver chaque nouvelle version avant de la soumettre à l'utilisateur.

## Autonomie et limites

Le dossier sauvegarde les assets qui nous ont été accessibles. Il ne contient pas
les MP4 des quatre Deep Void ni les exports finaux Quiet, faute de fichiers fournis.
L'ancien lien Claude partagé peut servir de contexte supplémentaire ; le README
doit suffire à reprendre sans dépendre de ce lien.

Le dépôt principal contient d'autres travaux et modifications en cours.
Ne pas faire de reset, de nettoyage global, de push forcé ou de commit de fichiers
étrangers à cette reprise. En cas de branches divergentes, intégrer les changements
de cette reprise sur la branche principale dans un checkout isolé.

## Voix Algrow du 15 octobre

Les six narrations ont été produites avec l'API Algrow, voix Mellow Matt
`IsEXLHzSvLH9UMB6SLHj`, vitesse 0,90. Les parties sources sont terminées ;
ne pas les relancer. Voir `narrations-2026-10-15/README.md` et le registre privé
`work/sleep-voiceovers-2026-10-15/ledger.json`. MP3 complets sur le Bureau dans
**Voix sleep - 15 octobre 2026**, et dans **VOIX-FINALES** de la sauvegarde.

Cet accès API utilise `ALGROW_API_KEY` dans le `.env` privé du dépôt ; il peut
fonctionner après un changement de compte ChatGPT sur le même PC. La connexion
MCP de recherche reste propre au compte de l'application. Une ancienne variable
Windows du même nom est refusée : l'exécuteur choisit la clé du `.env` uniquement
pour son processus. Ne pas modifier Windows ni afficher la clé.

Compte professionnel : 100 000 caractères maximum par génération, et sous-titres
avec supplément. Les fichiers sont découpés sans réécriture puis réunis en MP3
sans silence ou répétition ajoutés. Les SRT sont automatiques, noms à relire.
L'exécuteur de reprise ne soumet pas de nouveau job en mode `monitor`.
