# Reprendre ce dossier sur un autre compte

Etat au 12 octobre 2026. Ce fichier est le point d'entree du travail en cours. Les chemins ci-dessous sont relatifs a la racine du depot, donc restent utilisables si le dossier est deplace.

Nouveau PC / collegue aliens : lire [README_SURVIVOR_TUBEFORGE.md](README_SURVIVOR_TUBEFORGE.md). La base TubeForge complete, son installation sans archive privee et les presets zombies/aliens editables sont maintenant conserves dans Git sous `production/`.

TubeForge integre dans https://tools.kanye.studio/2d (comptes existants du portail, aucune seconde authentification). Calcul sur VPS2 : [README_TUBEFORGE_VPS.md](README_TUBEFORGE_VPS.md). Le workspace du VPS devient la reference pour les nouvelles productions ; la copie PC est conservee comme archive. Les acces prives se trouvent dans le fichier bureau de connexion, jamais dans Git.

## Lire dans cet ordre

1. `AGENTS.md`, s'il est present, puis `CLAUDE.md` pour les regles du depot.
2. Ce fichier pour les decisions les plus recentes et l'etat reel.
3. `production/COHERENCE_2D_CODEX.txt` pour la methode de references.
4. `chaines/survivor-projet/channel-kit.txt` et `chaines/alien-aftermath-projet/channel-kit.txt`.
5. Les deux `notes-production.txt` a cote des scripts, puis les images de reference elles-memes.
6. `production/tubeforge_support/README.md` avant toute modification de TubeForge.

La suite de `production/REPRISE.md` contient l'etat d'autres productions et de l'historique. Le conserver : la reprise de ce chat ne relance ni n'annule ces travaux. Les regles des cinq chaines historiques ne remplacent pas la direction visuelle Survivor choisie ici.

## Deux premiers episodes rendus et inspectes

L'utilisateur part et demande explicitement une video TERMINEE pour chacune des deux chaines, en reutilisant les sujets/scripts Faceless OS et TubeForge. La restriction precedente "arreter apres trois apercus / attendre validation" est levee pour cette production. Codex inspecte les assets et plans avant montage ; ne pas fabriquer une validation humaine. Aucune publication YouTube n'est demandee. Voix fournie pour les deux : `rU18Fk3uSDhmg5Xh41o4`, Algrow uniquement, vitesse 1. Les deux voix sont reelles et deja generees : Patch 702.98 s (11:43), Alien 686.88 s (11:27). Aucun faux timing estime.

Projets : Patch `zombie-outbreak-30-days-trapped-in-a-sup-e56f42` ; Alien `alien-invasion-7-days-trapped-in-a-gas-s-6bdb2e`. Chaine LOCALE Alien Aftermath creee dans TubeForge, pas une chaine YouTube. Les deux bibles/castings sont figes dans leurs projets. Sources : `production/tubeforge_survivor_episode.py` (compilation TECHNIQUE des choix manuels et import seulement), chaque `storyboard-production.txt` et `faceless-os-production-audit.json` a cote des scripts. Scripts finaux : Patch 2081 mots, Alien 2083, audites selon Faceless OS et ancres brutes des trois references deja conservees. Retrait de l'expose FDA pour rester dans le recit fictionnel et correction de la derniere mention de sac porte a l'epaule.

Assets : `output/imagegen/survivor-full-production-2026-10-12/`, `reference-index.json`, `asset-registry.json`, `patch-storyboard.json`, `alien-storyboard.json`, `prompts/scenes/`. EXACTEMENT 108 plans par episode, couverture integrale du texte et timings de la voix verifies. Le code n'ecrit aucun nouveau beat, ne choisit aucun lieu/reference et n'appelle pas un modele auteur : il compile les lignes et references explicites ecrites par Codex. Les 216 images retenues ont ete regardées par Codex. `scene-reviews.json` liste les choix/rejets, `generation-provenance.json` les vrais prompts et listes ordonnees de fichiers envoyes. Les retakes corrigent principalement chariots/cargaison, bracelet de Mara sur Patch, porte publique alien, canopy demonte, cabine industrielle ajoutee et cargo alien. Le plan Patch094 exigeait une retouche masquee ; masque et recu reel conserves. Aucun appel payant supplementaire n'est necessaire pour reprendre ces videos.

Les DEUX MP4 TubeForge sont termines et inspectes. Patch : 16 872 frames, 703 s video / 702.98 s voix. Alien : 16 485 frames, 686.875 s video / 686.88 s voix. 1920x1080, 24 fps, mouvements discrets et coupes franches, aucun texte incruste ni musique. Toutes les frames ont ete decodees sans erreur, la voix finale comparee integralement a l'original (correlation >0.9997) et les 108 images du milieu de chaque plan inspectees apres rendu. Les deux voix ont aussi une retranscription locale comparee au texte (Patch 98.78 %, Alien 99.72 % de tokens communs ; ces ecarts incluent la ponctuation et les choix de transcription). Les fichiers QA sont dans `render-checks/`. Ce sont des reviews DELEGUEES A CODEX, pas des clics de validation humaine ni une ecoute humaine.

Livraison : `output/videos/survivor-first-episodes-2026-10-12/01-Patch-Survives/` et `02-Alien-Aftermath/`. Chaque dossier comprend `video.mp4`, `voiceover.mp3`, `thumbnail.jpg`, `subtitles.srt`, `script-en.txt`, `timeline.csv`, `UPLOAD.txt`, `CAPCUT.txt`, `verification.json`, `manifest.json` et `clips-capcut/001.mp4` a `108.mp4`. ZIP separe par chaine a cote. Les clips sont muets, numerotes et cales sur les memes limites arrondies a 24 fps ; placer la voix au temps zero dans CapCut. Ne pas ajouter une seconde voix au MP4 deja sonorise. Les grandes variations de composition/props corrigees sont conservees comme archives ; des variations mineures d'expression et de rangement restent, ne pas promettre de coherence parfaite.

Outils techniques ajoutes : `production/tubeforge_survivor_export.py`. `inspect patch|alien` avec le Python du depot decode/compare/extrait les contacts ; `accept patch|alien --notes ...` avec le Python TubeForge enregistre seulement une inspection REELLEMENT faite par Codex ; `export patch|alien` avec le Python du depot produit les clips sans changer leur longueur. Le rendu principal a ete lance par `POST /api/workspace/projects/{pid}/render` dans TubeForge. Pas de changement de frontend, pas de publication YouTube.

Reprise des jobs : `work/survivor-full-production-2026-10-12/projects.json`, marqueurs `*-started.json` / recus `*-receipt.json`. Le nom de modele/cles reste PRIVE. Ne pas relancer un call dont le marqueur existe sans inspecter son issue : pas de retries/hedges caches. Les montages et miniatures sont egalement disponibles dans les deux projets TubeForge. La sauvegarde privee verifiee la plus recente est pointee par `work/reprise/latest.json` ; contient credentials, medias, scripts et recus, ne jamais publier ce ZIP prive. God of War reste termine et hors perimetre.

Les sections de pilote ci-dessous sont l'HISTORIQUE : les mentions "trois apercus seulement", "Mara reste a produire" et "Surveyor reste a produire" ne s'appliquent plus a ces deux premiers episodes termines.

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
| `chaines/survivor-projet/episode-01-supermarket/script-en.txt` | Narration anglaise V1, 2083 mots, deuxieme personne, trente jours fictifs, fin concrete avec Patch et Mara hors du magasin |
| `chaines/survivor-projet/episode-01-supermarket/notes-production.txt` | Casting, quatre acces externes, porte interne distincte, objets/payoffs, six lieux a figer et appui factuel FDA |
| `chaines/alien-aftermath-projet/episode-01-gas-station/script-en.txt` | Narration anglaise V1, 2078 mots, sept jours fictifs, visiteurs qui inspectent/recuperent du materiel, depart a pied avant demontage |
| `chaines/alien-aftermath-projet/episode-01-gas-station/notes-production.txt` | Reed/Surveyor/Loader, deux pompes, trajets, etats persistants, regles alien de fiction, boucles et relecture |
| `chaines/survivor-projet/ideation-01.txt` | Huit idees de lieux, supermarche selectionne ; autres sujets encore proposes |
| `chaines/survivor-projet/benchmark-2026-10-12.json` | Snapshot de dix uploads recents recuperes via Algrow, pas toute l'historique des chaines |
| `output/imagegen/survivor-launch-2026-10-12/` | Reference approuvee de Patch, crop de tete, deux prototypes supermarche et prompts/registres |
| `output/imagegen/patch-channel-kit-2026-10-12/` | Photo de profil ronde de Patch, PNG natif 1254 x 1254, prompt, registre de references et inspection |
| `output/imagegen/alien-channel-kit-2026-10-12/` | Proposition de logo alien, PNG natif 1254 x 1254, prompt et registre ; pas une reference approuvee de Reed |
| `output/channel-kits/survivor-launch-2026-10-12/` | Copies de livraison des deux kits, profils, scripts et notes ; les sources editoriales restent dans `chaines/` |
| `output/channel-kits/survivor-launch-2026-10-12.zip` | ZIP de ces kits, contenu verifie fichier par fichier |

Les scripts sont ECRITS et relus sur texte, pas des films produits. Estimation autour de 12-14 minutes selon la voix ; ne pas promettre une duree precise avant l'audio. Aucun des deux pilotes n'a encore de voix, de plans complets, de serie d'images complete ou de montage. Patch a maintenant six decors maitres inspectes et trois images d'ouverture, decrits ci-dessous ; le pilote alien n'a pas encore ses decors. Les scripts propres ne contiennent pas de notes a faire lire au TTS.

Les images et registres indiquent ce qui a ete regarde par Codex. L'approbation du personnage Patch ne vaut pas approbation automatique des scenes, de la marque, du script ou du nouveau profil.

## Style a conserver

Patch : grosse tete blanche parfaitement ronde, petits yeux noirs, bouche courte, petit pansement orange au-dessus de l'oeil anatomique DROIT, a GAUCHE pour le spectateur de face. Corps en traits noirs fins, mains et chaussures blanches, sac a dos scolaire orange SEPARE, pose debout au sol a cote de lui, fermeture eclair et poche avant zippee, aucune bretelle sur le corps. Pas de bonnet, cheveux, barbe, oreilles, nez ou visage humain realiste.

Ouvrir `output/imagegen/survivor-grounded-bags-2026-10-12/characters/patch.png` avant de generer. L'essai porte sur le dos est rejete par l'utilisateur et archive. L'ancienne reference a rabat est archivee. Le fichier visuel fait foi pour ses proportions et son sac ; ne pas inventer une bandouliere noire a partir d'un vieux prompt. Le profil seul ne remplace pas la reference de corps entier.

Pour Survivor : decors tres simples et peu profonds, contours nets, aplats mats, un geste ou objet lisible par plan. Cela differe des decors plus riches des chaines historiques. L'utilisateur a approuve les essais simples, pas une nouvelle direction cinematographique.

Correction utilisateur du 12 octobre : les ZOMBIES ont maintenant la tete, les DEUX mains en moufles et les DEUX pieds ovales VERTS, meme vert pale desature (cible #A8BE87). Patch et les humains vivants gardent tete/mains/pieds BLANCS. Corps en traits noirs et tenues propres a chacun conserves. Aucun tatouage/pansement/sac de Patch sur les infectes. Les essais tete verte seulement sont archives et remplaces par les references `cart-green-full.png` / `delivery-green-full.png` dans `output/imagegen/patch-green-zombies-2026-10-12/characters/`.

Le logo alien est un symbole de chaine. Le protagoniste humain Reed a maintenant sa reference de corps entier ; l'alien recurrent de l'episode a encore besoin de ses propres references. Le design mint du symbole ne transforme pas tous les personnages humains en aliens.

Mise a jour TubeForge du 12 octobre : une reference de corps entier de Reed a maintenant ete generee et regardee, dans `output/imagegen/survivor-grounded-bags-2026-10-12/characters/reed.png` (sac a dos scolaire gris SEPARE, pose au sol ; ancienne version portee dans le dos rejetee et archivee). Elle est installee dans le nouveau style, sur demande de l'utilisateur, mais son image n'a pas encore ete approuvee explicitement par celui-ci. Surveyor et les autres personnages secondaires restent a produire.

Les deux styles sont installes sous les IDs `survivor-patch` et `survivor-alien-aftermath`. Chacun a son `workspace_main_character` et son `workspace_cast_registry` : Patch a deux references (corps entier et tete), Reed une reference de corps entier. La page Styles expose maintenant une section **References personnages** pour importer plusieurs images par personnage/variante, enregistrer sa description, choisir le principal et valider les images apres inspection. Les nouveaux projets avec un casting en heritent via `style_cast_snapshot` ; les changements ulterieurs du style ne remplacent pas ce casting. L'auteur des plans selectionne seulement les identites effectivement presentes.

Ces styles sont configures pour le CLI Proxy et des prompts ecrits par Codex (`workspace_authoring_mode=codex`), sans appliquer les regles automatiques de proportions/tatouage de God of War. La configuration globale Google Flow des autres styles est preservee. L'import initial de styles ne cree pas de chaines YouTube. Le test Patch a depuis cree une fiche LOCALE TubeForge, avec la voix existante du studio heritee provisoirement et aucun appel de voix.

## Pilote visuel Patch : trois images, arret avant la suite

Projet local : `zombie-outbreak-30-days-trapped-in-a-sup-e56f42`, chaine locale `channel-c589e9b6a252` (Patch Survives). Page : `http://127.0.0.1:8766/#/video/zombie-outbreak-30-days-trapped-in-a-sup-e56f42/images`.

Sources editoriales : `chaines/survivor-projet/episode-01-supermarket/pilote-visuel.txt` et `references-refresh-2026-10-12.json`. Script V1 conserve apres relecture de son hook et de sa causalite avec Faceless OS et les trois transcriptions deja sauvegardees. Vues observees : Mr. Doomsday 254780, StickFallout 475605 ; Beanie 114616 dans le snapshot recent precedent. Pas de score outlier mesure ni de retention privee.

Assets : `output/imagegen/patch-supermarket-pilot-2026-10-12/`. Regarder `trois-plans.jpg` puis les trois PNG de `A-REGARDER/` (1920 x 1080 exact). Les natifs dans `scenes/` sont preserves ; mise au format par fit/pad technique seulement. Le `registre.json` contient SHA, narration exacte, prompts reels, ordre des fichiers reellement envoyes et notes d'inspection. `plan-lieux.svg` donne les connexions des quatre acces externes et portes internes, sans pretendre etre un plan a l'echelle.

Six maitres inspectes : `masters/front.png`, `stockroom.png`, `staff.png`, `yard.png`, `canal-v2.png`, `gardens.png`. Le premier `canal.png` est REJETE (pont longeant le canal) ; ne pas le reutiliser. La cour/canal/jardins sont des vues de JOUR ; des plans nocturnes exigeront leurs variantes explicites. Deux secondaires individuels dans `characters/` : Cart Infected (gilet olive) et Delivery Infected (gilet navy). Aucun ne porte le pansement/sac de Patch. Mara reste a produire avant son apparition.

Images retenues pour montrer a l'utilisateur : `plan-01-v2.png`, `plan-02-v2.png`, `plan-03.png`. Premiers essais 1/2 conserves comme REJETES : chariot parallele a vitre, puis rideau ne couvrant pas porte publique et proportions trop petites. Correction manuelle des prompts et nouveaux appels explicites, aucun retry automatique. Les images retenues sont inspectees par Codex, PAS encore approuvees par l'utilisateur.

Ces trois versions blanches sont desormais des ARCHIVES. Les versions vertes avec ancien sac sont aussi conservees. Les apercus ACTUELS avec sac a dos scolaire orange POSE AU SOL sont dans `output/imagegen/survivor-grounded-bags-2026-10-12/A-REGARDER/01.png`, `02.png`, `03.png` (1920 x 1080), avec nouvelle planche `trois-plans.jpg` et registre des vrais appels/referecences/inspections. Tous les elements exposes des infectes visibles sont verts. Au plan 2, tete et mains du zombie restent masquees par le rideau ; ses deux pieds visibles sont verts. Au plan 3, tete/main sont vertes et pieds/corps masques par la porte. Patch reste blanc partout. Le modele conserve parfois de legeres variations de teinte : les SHA prouvent les fichiers envoyes, pas un aplat numeriquement identique sur chaque pixel.

Import technique reproductible : `production/tubeforge_patch_green.py`. Il ne genere ni image ni prompt narratif et refuse un import partiel non inspecte. Les sources authoriales et refs utilisees sont fixes ; seul le bloc technique d'identites pour futurs retries est ajoute. Il conserve l'ancien casting/les anciennes scenes dans `workspace_visual_revision_history`, garde tous les fichiers et installe les deux infectes verts dans le style Patch et le projet. Aucun nouveau lot complet ni voix lance. `workspace_green_zombie_revision=head-hands-feet-v1` rend la migration idempotente et preserve les edits futurs.

TubeForge contient exactement TROIS moments visuels d'ouverture non minutes, pas un decoupage couvrant les 2083 mots. Pas de voix, pas de timestamps inventes, pas de rendu. `workspace_preview_only=true`, file `waiting_for_preview_review`, references copiees avec verification des SHA et media servis verifies. Voix heritee du studio via Algrow, a choisir/confirmer avant production sonore ; aucune synthese lancee.

Dans les prompts TubeForge, un bloc technique d'identites a ete ajoute pour les FUTURS retries API. Le prompt exact effectivement envoye au CLI reste conserve separement (`original_cli_prompt`, `workspace_external_generation`, fichier prompt source et recu prive). Ne pas pretendre que le bloc ajoute a ete envoye lors de la generation des apercus. Chaque plan garde l'ordre et les octets des references originales, plus la scene precedente pour le deuxieme plan, avec le decor maitre toujours present. Les validations humaines restent a verifier.

Reprise : attendre le retour visuel utilisateur sur ces trois tests avant de generer la suite. Ensuite, preparer Mara et les variantes necessaires, choisir/generer la voix, decouper manuellement TOUT le texte avec timings reels, puis seulement envoyer le lot autorise. Ne pas traiter les trois images comme une video complete ou reutiliser la geometrie facade dans chaque piece.

Import idempotent : `production/tubeforge_survivor_styles.py`, a lancer avec le Python de TubeForge apres deploiement. Il preserve un style deja installe et les edits existants. Le raccourci bureau `TubeForge.lnk` appelle `production/tubeforge_desktop.ps1` : lancement local si necessaire, puis ouverture du navigateur. Recreation du raccourci : `production/tubeforge_shortcut.ps1`. Le bureau reel est resolu via Windows, pas suppose dans un chemin fixe.

## Coherence : methode a executer

- Codex ecrit les decoupages et prompts. Le code execute ; aucun appel automatique ne doit reecrire un prompt dirige ou remplacer une reference.
- Exception explicitement demandee ensuite pour les SCRIPTS des deux styles Survivor : l'utilisateur veut pouvoir entrer un titre et faire ecrire le CLI Proxy sans intervention du chat. Cette exception ne change ni les cinq chaines historiques ni l'autorisation/maniere de preparer les images.
- Figer un plan du batiment et un decor maitre par lieu, avec portes et objets reconnaissables. Les lieux necessaires sont listes dans chaque note de production.
- Figer les personnages secondaires recurrents, notamment Mara ; reference textuelle seule insuffisante.
- Un plan a un extrait de narration, un lieu, des personnages nommes, une action, un prompt et une liste ORDONNEE des images vraiment envoyees.
- Variantes de vues, de lumiere, de stock et de destruction explicites. Une vitre cassee ou une pompe retiree ne reapparait pas intacte ensuite.
- Aucun double de Patch dans une image. Les persos d'une reference ne sont pas des figurants ajoutes a la scene.
- Chaque plan apporte une information/action/consequence nouvelle ; ne pas produire seulement des zooms du meme tableau.
- Regarder chaque sortie, comparer aux references et corriger les ecarts avant montage. Ne pas annoncer coherence parfaite sur la seule base du prompt, du hash ou du transport des references.
- Images et clips de video en paysage 16:9. Les sorties observees de notre proxy ne garantissent pas la taille demandee ; mesurer les dimensions reelles et conserver les natifs. Les profils sont carres.

## Sacs a dos scolaires : premiere revision ARCHIVEE et rejetee

Demande utilisateur du 12 octobre : remplacer les deux anciens sacs par des sacs a dos scolaires normaux. Patch ORANGE, Reed GRIS, deux bretelles, fermeture eclair principale et poche avant zippee. Ne changer ni tete/pansement/foulard ni proportions en traits fins. Ref Patch : `output/imagegen/survivor-backpacks-2026-10-12/characters/patch-v2.png` ; ref Reed : `characters/reed.png` dans le meme dossier. `characters/patch.png` est un ESSAI REJETE (torse gris rempli). PFPs conserves, seulement tetes. Les nouveaux personnages et trois plans ont ete regardes par Codex, pas encore approuves explicitement par l'utilisateur.

`production/tubeforge_survivor_backpacks.py` a importe les deux identites dans les styles et les trois apercus du pilote ; anciens fichiers et historiques conserves. Le script Patch a maintenant 2083 mots (vocabulaire backpack/zipper), sans changement du recit. Reed conserve 2078 mots. Le prompt d'ecriture depuis un titre emploie les nouveaux sacs et suit les etats porte/pose/ouvert. Aucune voix ni suite du lot lancee.

`registre.json` conserve les QUATRE references vraiment envoyees a chaque retouche : ancien plan vert, decor maitre, Patch corps entier actualise, tete Patch. La regeneration future dans TubeForge ajoute explicitement la reference de l'infecte vert comme image 5 avec binding, sauvegarde a part : ne pas pretendre qu'elle a ete envoyee a ces retouches. Reprise des calls/recus privee : `work/survivor-backpacks-2026-10-12/`. Media natifs 1672 x 941 conserves ; apercus convertis techniquement en 1920 x 1080 sans retouche de contenu.

## Sacs poses AU SOL : decision actuelle

Correction utilisateur du 12 octobre : sacs portes sur les traits fins rejetes car semblent suspendus a rien. Garder les sacs scolaires, mais objets SEPARES : Patch orange, Reed gris, debout au sol a cote de leur proprietaire, base en contact avec ombre de contact, aucune bretelle sur le corps. Pour une relocalisation necessaire au recit seulement, prise visible par la poignee puis sac repose dans le nouveau lieu ; jamais sac dans le dos. Un seul sac par proprietaire, pas de duplication ou flottement.

References actuelles : `output/imagegen/survivor-grounded-bags-2026-10-12/characters/patch.png` et `characters/reed.png` dans le meme dossier. Exemples utilisateur : les trois essais `output/imagegen/survival-styles-tests-2026-10-12/`, utilises pour placement du sac uniquement, pas pour changer pansement/foulard/visage. PFPs inchanges. Les nouvelles sorties ont ete inspectees par Codex, pas encore approuvees explicitement par l'utilisateur.

Migration explicite : `production/tubeforge_survivor_grounded_bags.py`. Met les deux styles, la reference figee du pilote Patch, ses trois apercus et le vocabulaire du script a jour ; historique conserve. Ne PAS rerun l'ancien import de sacs portes ni le prendre comme direction actuelle. Script Patch 2083 mots, Reed 2078 mots ; premiers beats inchanges, pas de voix ni de lot suivant lance. Prompt d'ecriture automatique actualise : sac au sol pendant actions sur place, transport visible par poignee si le recit le requiert.

Calls et recus PRIVES sous `work/survivor-grounded-bags-2026-10-12/`. Registre public de chaque prompt, fichiers et references vraiment envoyees : `output/imagegen/survivor-grounded-bags-2026-10-12/registre.json`. Les identites et maitres sont toujours envoyes, sans remplacement de fournisseur. Le plan 2 initial et sa v2 sont des essais de repositionnement archives ; la version courante est precisee dans le registre. Natifs preserves, trois livraisons exactes 1920 x 1080 dans `A-REGARDER/`.

## Recherche deja faite

References principales : `@Mr.Doomsday2`, `@BeanieSurvives`, `@stickfallout`. Analyse reelle via Algrow, trois transcriptions ouvertes et 276 commentaires classes par likes (76 + 100 + 100). Les critiques de changements de decor/personnage, de voix monotone et les demandes de suite ont guide le projet. Echantillon non representatif : aucune retention, CTR ou part de trafic Reels mesuree.

Transcriptions, commentaires et retours bruts sont encore dans `work/survivor-launch-2026-10-12/`, dont `reference-transcripts/`. Le benchmark public et les notes editoriales suffisent pour comprendre le raisonnement, mais lire les trois extraits reels avant d'ancrer la voix. Ne pas refaire toute l'analyse par defaut ni inventer des chiffres de croissance. Nexlev n'a pas ete utilise dans cette passe.

Methodes d'ecriture : `skills/facelessos/`, en particulier voice-anchoring, script-structures, retention-mechanics, humanizer et greenlight-audit. Ancres de forme, pas copie d'intrigues ou d'accroches. Regles alien et calendrier de fiction explicitement inventes ; ne pas leur attribuer de fausses sources documentaires.

## Ecriture automatique depuis un titre

Sources maintenues : `production/tubeforge_support/workspace_writing.py` et `scriptwriting/survival.txt`, `scriptwriting/review.txt`. Deploiement avec le script habituel `--no-seed`, puis restart si aucun job actif. L'interface de l'etape Texte montre **Ecrire depuis un titre** pour `survivor-patch` et `survivor-alien-aftermath`, sur une chaine locale geree, en anglais. Les cinq profils historiques restent manuels. La preparation automatique des images reste desactivee pour ces styles diriges par Codex.

Titre, duree souhaitee (3-30 minutes, defaut 15) et bref supplement facultatif -> DEUX appels au modele TEXTE fige du projet sur le CLI Proxy : ecriture, puis revision Faceless OS ; un TROISIEME appel de redaction seulement si la longueur mesuree doit etre ajustee. Maximum trois calls, sans substitution de fournisseur, retry de transport ou requete jumelle automatique. L'interface annonce verification/ajustement, et la progression passe a trois etapes si besoin. Les cinq vrais fichiers Faceless OS et les 210 premiers mots des trois transcriptions sauvegardees sont charges a chaque demande depuis `STUDIO_ROOT`. Ces transcriptions servent de registre oral, pas de plot/hooks a recopier. Ne pas committer leurs longs extraits ; les backups prives les conservent.

Sorties : narration pure, bible de personnages/lieux/chronologie/etats/setup-payoff, audit AUTOMATIQUE A-E avec preuves. Ce controle du modele n'est pas une approbation humaine, une preuve de faits reels ou une garantie de diction/retention. Fiction interne explicite, pas de faux conseil medical ou quotas de survie presentes comme fiables. Comptage technique des mots et tolerance de cinq mots aux bornes pour ne pas jeter une reponse sur une difference de segmentation ; la duree reelle reste celle de la voix. Si l'ajustement unique ne suffit pas, le texte est conserve comme brouillon avec probleme explicite de longueur, pas jete ou rempli automatiquement.

Sur projet VIDE sans medias et sans probleme restant dans l'audit, le script est rempli automatiquement et devient editable. Sur projet deja ecrit, resultat conserve en brouillon ; bouton **Utiliser ce brouillon** seulement sans medias existants et avec empreinte du texte actuel. Un projet avec images/voix ne remplace pas son script par ce parcours : copier dans une nouvelle video. Les brouillons precedents et medias sont conserves. Aucun appel de voix ou d'images ne suit automatiquement.

Routes : `POST /api/workspace/projects/{pid}/script/generate` avec `title`, `minutes`, `brief`, `script_hash`; `POST .../script/apply-draft` avec `draft_id`, `script_hash`. Progression via job projet habituel. Les generations et requetes completes restent PRIVEES sous `work/TubeForge/data/projects/{pid}/script-generations/` ; pas de cle ou nom de modele dans les fichiers publics. Une erreur laisse le texte actuel intact et ne relance aucun call.

Validation : tests de conservation, catalogue fige, absence de retry/hedge, audits incomplets, bornes de mots, conflits d'edition, historique manuel, resultats existants et medias servis. Premier test reel de trois minutes : brouillon trop long, puis reponse finale de 523 mots rejetee par une borne de 522 ; erreur corrigee avec tolerance explicite. La reponse deja recue a ete recuperee sans nouveau call pour conserver son resultat. Un resultat suivant encore trop long a conduit a ajouter l'etape bornee d'ajustement ; pas de retry de transport. Le NOUVEAU TEST API AUTONOME a termine avec 503 mots, trois appels et script rempli automatiquement dans un projet vide, sans intervention de finition manuelle. Preuve publique : `output/imagegen/patch-green-zombies-2026-10-12/verification.json`. Traces completes privees : `work/patch-green-zombies-2026-10-12/`. Les deux projets de test sont archives de maniere reversible. Ils ne sont pas des scripts de production choisis et leur geographie n'est pas celle du pilote trente jours. L'episode original conserve ses 2083 mots, ses quatre acces et ses trois images seulement.

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

Continuer les deux pilotes depuis les scripts V1, sans re-ideation de Patch. Pour le supermarche selectionne : etablir plan et maitres des lieux, creer/inspecter la reference de Mara et les infectes, puis test de trois plans bien differents avec references explicites avant un grand lot. Pour la seconde : conserver l'option station-service comme proposition tant que l'utilisateur n'a pas choisi un autre lieu ; reutiliser la reference de Reed installee et figer le Surveyor, la machine et le plan avant images.

La voix doit preceder le calage final : utiliser sa duree reelle et ses timings. Le futur pack CapCut comporte clips MP4 numerotes dans l'ordre, chaque duree calee sur la voix, voix originale, SRT et timestamps ; ne pas fabriquer tous les clips avec une duree fixe estimee. La logique d'export existe deja dans les outils, a lire avant de la reimplementer.

## Sauvegarde locale et Git

`production/reprise_snapshot.py` cree un nouveau snapshot sous `work/reprise/`, sans modifier les sources, la configuration ou les projets. Il sauvegarde les sources TubeForge, le runtime applicatif (sans les environnements/dependances reinstallables), toutes ses donnees, les configurations privees, les kits/references/recherche Survivor et les skills disponibles. Il produit un ZIP et un manifeste avec tailles et SHA256, puis relit le ZIP pour verification. Le pointeur `work/reprise/latest.json` donne le dernier snapshot.

Cette sauvegarde contient la configuration privee. Elle reste dans `work/`, ignore par Git : ne pas la publier ni l'envoyer comme ZIP de channel kit. Pour le meme PC et un autre compte IA, garder ce dossier suffit ; `.env`, projets et references sont deja accessibles localement. Un clone Git seul sur une autre machine ne recupere pas les donnees/cles ignorees : restaurer la sauvegarde privee de facon appropriee.

Les sources/publications recentes sont poussees sur la branche de session et `main`. Le depot contient aussi beaucoup de changements d'autres travaux : ne pas faire `git add .`, reset, clean ou restauration globale. Publier seulement le perimetre modifie et scanner les secrets avant push. Les copies de livraison des kits doivent etre resynchronisees si leurs sources editoriales changent.

## Message a donner au prochain compte

> Travaille dans ce dossier. Lis README_REPRISE.md, AGENTS.md et CLAUDE.md. Reprends les deux nouveaux projets Survivor depuis les scripts et notes de production existants : principale Patch, premier episode zombie au supermarche ; seconde aliens des le premier upload. Garde le personnage approuve et les decors simples. Ecris toi-meme les prompts avec references explicites, verifie les images reelles, puis prepare voix et clips cales pour CapCut. Preserve TubeForge, ses sources dans production/tubeforge_support et ses donnees locales. Ne relance pas les retouches God of War abandonnees.


## Portal integration — 12 October 2026

Open https://tools.kanye.studio/2d using the existing portal access key. Sources:
`production/tubeforge_portal`; do not create a separate account registry. The
existing portal is on VPS1 (185.249.225.176); TubeForge runs on VPS2 (13.140.129.97).
`README_TUBEFORGE_VPS.md` documents private connection files, deployment and rollback.
All TubeForge capabilities are available to any signed-in member. My videos uses
the portal member ID; Team videos opens shared history. Styles/channels stay shared.
The maintained UI and advanced tools are English. CLI image batches now use
configured parallelism (deployed target 24), with 8 text calls and 6 planning batches.
Google Flow retains its own limit (3). No new paid media generation is needed
for deployment checks. Preserve the completed episodes and their references.
