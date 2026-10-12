# Reprendre ce dossier sur un autre compte

Etat au 12 octobre 2026. Ce fichier est le point d'entree du travail en cours. Les chemins ci-dessous sont relatifs a la racine du depot, donc restent utilisables si le dossier est deplace.

## Lire dans cet ordre

1. `AGENTS.md`, s'il est present, puis `CLAUDE.md` pour les regles du depot.
2. Ce fichier pour les decisions les plus recentes et l'etat reel.
3. `production/COHERENCE_2D_CODEX.txt` pour la methode de references.
4. `chaines/survivor-projet/channel-kit.txt` et `chaines/alien-aftermath-projet/channel-kit.txt`.
5. Les deux `notes-production.txt` a cote des scripts, puis les images de reference elles-memes.
6. `production/tubeforge_support/README.md` avant toute modification de TubeForge.

La suite de `production/REPRISE.md` contient l'etat d'autres productions et de l'historique. Le conserver : la reprise de ce chat ne relance ni n'annule ces travaux. Les regles des cinq chaines historiques ne remplacent pas la direction visuelle Survivor choisie ici.

## Demande actuelle et decisions acquises

L'utilisateur veut lancer DEUX nouvelles chaines distinctes. Il veut avancer vite, avec des illustrations simples et coherentes. Il cree les chaines YouTube lui-meme depuis les kits ; aucune chaine n'a ete creee, aucun handle reserve et aucun pilote publie par Codex.

| Projet | Valide par l'utilisateur | Encore propose |
| --- | --- | --- |
| Principale | Nouveau projet dedie, personnage au petit pansement orange, premier episode zombie dans un supermarche | Nom `Patch Survives`, handle `@PatchSurvives`, script integral, nouvelle photo de profil |
| Seconde | Chaine distincte, ALIENS des le premier upload, confirmation explicite apres une ambiguite zombies/aliens | Nom `Alien Aftermath`, handle `@AlienAftermath`, pilote station-service, humain Reed, nouveau logo alien et script integral |

Le mot zombies ecrit a la fin d'un message sur la seconde chaine a ete clarifie : la reponse utilisateur est bien ALIENS. Ne pas creer deux chaines zombies par erreur.

La marque principale peut accueillir d'autres catastrophes plus tard. Son premier sujet reste le supermarche. Ne pas changer le personnage approuve pour reprendre l'ideation ou le logo.

## Fichiers prets

| Fichier/dossier | Contenu et statut |
| --- | --- |
| `chaines/survivor-projet/episode-01-supermarket/script-en.txt` | Narration anglaise V1, 2079 mots, deuxieme personne, trente jours fictifs, fin concrete avec Patch et Mara hors du magasin |
| `chaines/survivor-projet/episode-01-supermarket/notes-production.txt` | Casting, quatre acces externes, porte interne distincte, objets/payoffs, six lieux a figer et appui factuel FDA |
| `chaines/alien-aftermath-projet/episode-01-gas-station/script-en.txt` | Narration anglaise V1, 2075 mots, sept jours fictifs, visiteurs qui inspectent/recuperent du materiel, depart a pied avant demontage |
| `chaines/alien-aftermath-projet/episode-01-gas-station/notes-production.txt` | Reed/Surveyor/Loader, deux pompes, trajets, etats persistants, regles alien de fiction, boucles et relecture |
| `chaines/survivor-projet/ideation-01.txt` | Huit idees de lieux, supermarche selectionne ; autres sujets encore proposes |
| `chaines/survivor-projet/benchmark-2026-10-12.json` | Snapshot de dix uploads recents recuperes via Algrow, pas toute l'historique des chaines |
| `output/imagegen/survivor-launch-2026-10-12/` | Reference approuvee de Patch, crop de tete, deux prototypes supermarche et prompts/registres |
| `output/imagegen/patch-channel-kit-2026-10-12/` | Photo de profil ronde de Patch, PNG natif 1254 x 1254, prompt, registre de references et inspection |
| `output/imagegen/alien-channel-kit-2026-10-12/` | Proposition de logo alien, PNG natif 1254 x 1254, prompt et registre ; pas une reference approuvee de Reed |
| `output/channel-kits/survivor-launch-2026-10-12/` | Copies de livraison des deux kits, profils, scripts et notes ; les sources editoriales restent dans `chaines/` |
| `output/channel-kits/survivor-launch-2026-10-12.zip` | ZIP de ces kits, contenu verifie fichier par fichier |

Les scripts sont ECRITS et relus sur texte, pas des films produits. Estimation autour de 12-14 minutes selon la voix ; ne pas promettre une duree precise avant l'audio. Aucun des deux pilotes n'a encore de voix, de plans complets, de decors maitres verifies, de serie d'images finale ou de montage. Les scripts propres ne contiennent pas de notes a faire lire au TTS.

Les images et registres indiquent ce qui a ete regarde par Codex. L'approbation du personnage Patch ne vaut pas approbation automatique des scenes, de la marque, du script ou du nouveau profil.

## Style a conserver

Patch : grosse tete blanche parfaitement ronde, petits yeux noirs, bouche courte, petit pansement orange au-dessus de l'oeil anatomique DROIT, a GAUCHE pour le spectateur de face. Corps en traits noirs fins, mains et chaussures blanches, petit sac orange a rabat avec bouton noir et anse orange. Pas de bonnet, cheveux, barbe, oreilles, nez ou visage humain realiste.

Ouvrir `output/imagegen/survivor-launch-2026-10-12/01-patch-character.png` avant de generer. Le fichier visuel fait foi pour ses proportions et son sac ; ne pas inventer une bandouliere noire a partir d'un vieux prompt. Le profil seul ne remplace pas la reference de corps entier.

Pour Survivor : decors tres simples et peu profonds, contours nets, aplats mats, un geste ou objet lisible par plan. Cela differe des decors plus riches des chaines historiques. L'utilisateur a approuve les essais simples, pas une nouvelle direction cinematographique.

Le logo alien est un symbole de chaine. Le protagoniste humain Reed et l'alien recurrent de l'episode ont encore besoin de leurs propres references. Le design mint du symbole ne transforme pas tous les personnages humains en aliens.

## Coherence : methode a executer

- Codex ecrit les decoupages et prompts. Le code execute ; aucun appel automatique ne doit reecrire un prompt dirige ou remplacer une reference.
- Figer un plan du batiment et un decor maitre par lieu, avec portes et objets reconnaissables. Les lieux necessaires sont listes dans chaque note de production.
- Figer les personnages secondaires recurrents, notamment Mara ; reference textuelle seule insuffisante.
- Un plan a un extrait de narration, un lieu, des personnages nommes, une action, un prompt et une liste ORDONNEE des images vraiment envoyees.
- Variantes de vues, de lumiere, de stock et de destruction explicites. Une vitre cassee ou une pompe retiree ne reapparait pas intacte ensuite.
- Aucun double de Patch dans une image. Les persos d'une reference ne sont pas des figurants ajoutes a la scene.
- Chaque plan apporte une information/action/consequence nouvelle ; ne pas produire seulement des zooms du meme tableau.
- Regarder chaque sortie, comparer aux references et corriger les ecarts avant montage. Ne pas annoncer coherence parfaite sur la seule base du prompt, du hash ou du transport des references.
- Images et clips de video en paysage 16:9. Les sorties observees de notre proxy ne garantissent pas la taille demandee ; mesurer les dimensions reelles et conserver les natifs. Les profils sont carres.

## Recherche deja faite

References principales : `@Mr.Doomsday2`, `@BeanieSurvives`, `@stickfallout`. Analyse reelle via Algrow, trois transcriptions ouvertes et 276 commentaires classes par likes (76 + 100 + 100). Les critiques de changements de decor/personnage, de voix monotone et les demandes de suite ont guide le projet. Echantillon non representatif : aucune retention, CTR ou part de trafic Reels mesuree.

Transcriptions, commentaires et retours bruts sont encore dans `work/survivor-launch-2026-10-12/`, dont `reference-transcripts/`. Le benchmark public et les notes editoriales suffisent pour comprendre le raisonnement, mais lire les trois extraits reels avant d'ancrer la voix. Ne pas refaire toute l'analyse par defaut ni inventer des chiffres de croissance. Nexlev n'a pas ete utilise dans cette passe.

Methodes d'ecriture : `skills/facelessos/`, en particulier voice-anchoring, script-structures, retention-mechanics, humanizer et greenlight-audit. Ancres de forme, pas copie d'intrigues ou d'accroches. Regles alien et calendrier de fiction explicitement inventes ; ne pas leur attribuer de fausses sources documentaires.

## Outils et configuration locale

Racine sur ce PC : `C:/Users/ytbyt/Documents/ChatGPT/2D Slop`.

- Studio historique principal : Flask a la racine, normalement port 5000. Il ne faut pas le confondre avec TubeForge.
- TubeForge installe : `work/TubeForge/`, backend `app/`, frontend `app/web/`, donnees `data/`, configuration privee `.env` a sa racine. Il n'y a pas de dossier `backend/` separe.
- Sources de nos modifications : `production/tubeforge_support/`. Deploiement : `production/tubeforge_workspace.py`. Lancement : `production/tubeforge.ps1`.
- Python du depot : `venv/Scripts/python.exe`. Python de TubeForge : `work/TubeForge/.venv/Scripts/python.exe`.
- Adresse TubeForge : `http://127.0.0.1:8766/`.
- Cles, URL et choix effectifs de modele sont dans le `.env` prive du depot et/ou celui de TubeForge. Ne jamais imprimer leur contenu, les coller dans un message ou les committer.
- Les derniers essais Survivor et profils utilisent le CLI Proxy configure du depot. TubeForge possede aussi l'integration Google Flow/useapi utilisee pour God of War. Ne pas intervertir ces chemins ni changer silencieusement de fournisseur.
- Images : utiliser le CLI du skill imagegen installe (`C:/Users/ytbyt/.codex/skills/.system/imagegen/scripts/image_gen.py`), lire son `SKILL.md` et ses docs. `AI_IMAGE_MODEL` et les cles viennent de `.env`. Pas de nom de modele fige dans le code public.
- Pour les generations dirigees : un essai facturable explicite, SDK `max_retries=0`, trace de demarrage dans `work/`, prompt final conserve, refs ordonnees/hashees, sortie native mesuree, inspection visuelle. Si une erreur laisse l'issue inconnue, inspecter avant de refaire un appel.
- Les marqueurs et recus prives des profils sont dans `work/patch-channel-kit-2026-10-12/` et `work/alien-channel-kit-2026-10-12/`. Ne pas utiliser un logo comme decor maitre.
- Voix : l'utilisateur a demande Algrow en priorite, puis Algrow uniquement pour le relancement God of War. Les scripts Survivor n'ont encore ni voix choisie explicitement ni audio genere ; ne pas reutiliser une voix sans expliquer ce choix si on doit le fixer.

## TubeForge : reprise sans effacer les donnees

Depuis la racine, en PowerShell :

```powershell
& ./production/tubeforge.ps1 -Action Status
& ./production/tubeforge.ps1 -Action Start
```

Une mise a jour autorisee des sources se deploie avec `--no-seed`, pour conserver les chaines/styles/projets existants :

```powershell
& ./venv/Scripts/python.exe ./production/tubeforge_workspace.py --no-seed
```

Ne pas lancer install/configure/seed pour simplement reprendre le contenu. Ne pas modifier seulement `work/TubeForge/app`, car le prochain deploiement reprend les sources de `production/tubeforge_support/`. Ne pas relancer ou arreter des jobs a l'aveugle. Un changement de compte IA ne demande pas de reinstall ni de restart du serveur.

## God of War : termine, ne pas reprendre les retouches

Projet TubeForge `your-life-as-the-god-of-war-c001a0`. L'utilisateur a termine la premiere video lui-meme dans CapCut et a explicitement abandonne les retouches. Ne pas relancer le batch d'images, la voix ou les vieux scripts de correction.

Titre choisi : `Your Life as Kratos, the God of War`. Voix existante environ 11:20, 110 images. Pack de 110 clips silencieux dans l'ordre, 1920 x 1080 a 24 fps, avec voix/SRT/timestamps : `output/deliveries/oddly-fictional-lives/god-of-war-capcut-2026-10-12-version-actuelle/`, ZIP voisin. Apercu MP4 voisin. Le script n'a pas de chapitres `Level 4`.

Profil Kratos : `output/imagegen/kratos-pfp-round-head-2026-10-12/pfp.png`. Ce personnage n'est pas Patch. Google Flow/captcha et ses anciens comptes sont un contexte technique conserve, pas une demande active de regeneration.

## Prochaine action utile

Continuer les deux pilotes depuis les scripts V1, sans re-ideation de Patch. Pour le supermarche selectionne : etablir plan et maitres des lieux, creer/inspecter la reference de Mara et les infectes, puis test de trois plans bien differents avec references explicites avant un grand lot. Pour la seconde : conserver l'option station-service comme proposition tant que l'utilisateur n'a pas choisi un autre lieu ; figer Reed, le Surveyor, la machine et le plan avant images.

La voix doit preceder le calage final : utiliser sa duree reelle et ses timings. Le futur pack CapCut comporte clips MP4 numerotes dans l'ordre, chaque duree calee sur la voix, voix originale, SRT et timestamps ; ne pas fabriquer tous les clips avec une duree fixe estimee. La logique d'export existe deja dans les outils, a lire avant de la reimplementer.

## Sauvegarde locale et Git

`production/reprise_snapshot.py` cree un nouveau snapshot sous `work/reprise/`, sans modifier les sources, la configuration ou les projets. Il sauvegarde les sources TubeForge, le runtime applicatif (sans les environnements/dependances reinstallables), toutes ses donnees, les configurations privees, les kits/references/recherche Survivor et les skills disponibles. Il produit un ZIP et un manifeste avec tailles et SHA256, puis relit le ZIP pour verification. Le pointeur `work/reprise/latest.json` donne le dernier snapshot.

Cette sauvegarde contient la configuration privee. Elle reste dans `work/`, ignore par Git : ne pas la publier ni l'envoyer comme ZIP de channel kit. Pour le meme PC et un autre compte IA, garder ce dossier suffit ; `.env`, projets et references sont deja accessibles localement. Un clone Git seul sur une autre machine ne recupere pas les donnees/cles ignorees : restaurer la sauvegarde privee de facon appropriee.

Les sources/publications recentes sont poussees sur la branche de session et `main`. Le depot contient aussi beaucoup de changements d'autres travaux : ne pas faire `git add .`, reset, clean ou restauration globale. Publier seulement le perimetre modifie et scanner les secrets avant push. Les copies de livraison des kits doivent etre resynchronisees si leurs sources editoriales changent.

## Message a donner au prochain compte

> Travaille dans ce dossier. Lis README_REPRISE.md, AGENTS.md et CLAUDE.md. Reprends les deux nouveaux projets Survivor depuis les scripts et notes de production existants : principale Patch, premier episode zombie au supermarche ; seconde aliens des le premier upload. Garde le personnage approuve et les decors simples. Ecris toi-meme les prompts avec references explicites, verifie les images reelles, puis prepare voix et clips cales pour CapCut. Preserve TubeForge, ses sources dans production/tubeforge_support et ses donnees locales. Ne relance pas les retouches God of War abandonnees.
