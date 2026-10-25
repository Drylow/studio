# Journal des vidéos

## Historical Daily - OVNI integration, 9 October 2026

OVNI is now the default picture renderer for the five manually authored
historical channels, without frontend or prompting changes. The same 36-shot
Edo excerpt renders in 32.263 seconds versus 69.138 seconds with the old engine,
about 2.14x on this workload; encoder quality settings differ. Audio mix, fades,
voice-derived frame clock and explicit creative gates remain.
GPU excerpt: `output/historical-01-2026-10-08/edo-daily/Edo-Daily-01-EXTRAIT-3min-OVNI.mp4`.
5431 frames, 1080p30, full decode clean, 108 captures manually viewed; 56 tests
pass including real GPU blend/colour/audio/cache/cancellation. The original
headband continuity caution remains and no listening review is claimed.
This is still only an excerpt. All five full films remain unfinished; no upload
or publication. See `production/OVNI.md` for installation, measurements and QA.

## Crazy Chef 3D — pack de chaîne et livraison mobile — 8 octobre 2026

Nom choisi : **Crazy Chef 3D**, handle **@CrazyChef3D**. Bio courte proposée :
« Cute chef. Terrible ideas. Delicious destruction. 🍉💥 ».
Les trois exports finaux déjà revus (pastèque 41,8 s, chocolat 66,7 s, frites 63,6 s)
sont sur GoFile ; tailles et MD5 confirmés, SHA-256 identiques aux rapports QA.
Trois covers verticales en pixel art créées et regardées, avec le chef approuvé
à la spatule. Logo, covers, bio, nom, handle, titres et descriptions transmis
au Discord indiqué par l'utilisateur ; message des quatre images relu et leurs
fichiers comparés aux originaux. Kit mobile ZIP également sur GoFile.

Fiche et liens : `chaines/crazy-chef-3d/DELIVERY.md`. Helper dédié :
`production/crazy_chef_delivery.py` ; vérification des exports, cache des uploads,
ZIP stable et protection contre les envois répétés ou incertains.
Livraison GoFile + Discord autorisée pour les prochaines vidéos finalisées et
vérifiées ; publication TikTok / YouTube manuelle. Aucun changement du frontend.

## Fries vs Hydraulic Press — 8 octobre 2026

Nouvelle vidéo originale dans le style pixel art du cuistot : trois tas de
48, 96 et 192 frites sous une presse hydraulique, écrasement progressif,
morceaux irréguliers et huile dorée qui déborde du plateau, dégouline autour
de la planche et forme des flaques au sol. La paume soutient le plateau à
l'entrée ; fin avec la spatule, le sautillement et les confettis. Textes anglais.

Livraison : `experiments/fries-press/fries-hydraulic-press-final.mp4` —
63,6 s, 1080 × 1920, 60 images/s, 3 816 images. Trois nouveaux bruitages
(moteur, écrasement humide, huile), deux sons de la bibliothèque précédente,
sans musique. Le clip X sert seulement à étudier le mouvement ; aucune de
ses images ni de son audio dans la vidéo finale.

Contrôle visuel des 64 planches couvrant chaque image du MP4 ; textes et
indicateurs vérifiés automatiquement sur les 3 816 images. Vérification
HyperFrames : 0 erreur, 0 avertissement. États de l'animation contrôlés sur
toutes les images, huile après contact. Audio AAC : pic −3,7 dB, aucun
échantillon saturé dans le mix source. Détails : `experiments/fries-press/QA.md`.
Rendu terminé et vérifié, pas de publication sur les réseaux.

## Edo Daily — épisode 01 — 8 octobre 2026

**What Did People in Edo Japan Actually Do All Day?** ANCIENNE VERSION REJETÉE
par l'utilisateur : tableaux répétitifs, trop peu d'actions et d'habitants.
Les contrôles techniques et les variantes d'images ne validaient pas le récit.
Le montage de 24 min 59, son ancien script et ses plans ne sont plus une livraison
ni une base à reprendre. Trois dossiers retirés des chemins actifs ; suppression
définitive bloquée par l'outil, fichiers mis à l'écart dans
`work/rejected/edo-01-2026-10-08/`. Références validées et propositions conservées.
Aucun upload ni envoi Discord ; historique Git conservé.

Reprise : analyse de deux vidéos Strangely Ironic Guy par Algrow et vérification
directe d'extraits et des cinq captures locales. Codex réécrit le découpage et les
prompts : cohérence dans chaque scène, nouvelles actions, POV, échanges et groupes.
Dossier de reprise : `chaines/edo-daily/01-rebuild/`. Premier essai de six plans,
quatre lieux et six adultes ; pas encore de nouvelle vidéo complète ou de voix
mesurée. Les nouvelles illustrations passent par le CLI Proxy configuré.
Dix nouvelles références et six scènes produites ; quatre passes de correction
après relecture (literie, peau, objets de la chambre, doigts et stand de nourriture).
Six images retenues et planche dans
`output/imagegen/edo-rebuild-2026-10-08/A-REGARDER/`.
Retour utilisateur : scènes jugées propres, réserve sur les grandes tours et
formes étranges au fond. Deux maîtres et quatre plans corrigés via le CLI Proxy :
toits bas au quai, horizon de rue sans grandes montagnes décoratives. Six retouches
regardées, personnages/actions conservés ; plans 03 et 04 inchangés. Références
sélectionnées dans `horizon-v2/`, dossier A-REGARDER actualisé ; voir `HORIZONS.md`.
Pas encore de nouveau film complet ou d'export prêt à publier ; validation de
chaque retouche non demandée ni présumée. Limites dans `REVIEW.md`.

## Cage Dispatch — première vidéo du pilote automatique — 7 octobre 2026

« Shavkat Rakhmonov teases 19-0 vs 19-0: Is Michael Morales next? » — **publique** :
https://youtu.be/u5ZHjA5Ri0M (21 h 40, Paris). Sujet choisi seul par le radar (8/10), faits
cités mot pour mot de Bloody Elbow, script vérifié, voix Algrow, 4 min 25, photos Commons
(Morales : domaine public ; Shavkat : CC0 recadré sur lui seul à la demande de l'utilisateur,
qui voulait les deux combattants sur la miniature). Planches et miniature regardées par Claude ;
publication demandée par l'utilisateur dans la conversation, envoyée par le serveur o2switch
(morceaux de 1 Mo, `YOUTUBE_CHUNK_MB=1`), miniature confirmée, message Discord envoyé.

## Chocolate vs Crazy Tools — 8 octobre 2026

**Version finale de plus d’une minute : progression compacte des outils en bas.** 66,70 s, 1080 × 1920 à 60 images/s. Deux quantités par outil et trois salves rapides par quantité : fourchette 1 / 4, gant à ressort 4 / 8, marteau-piqueur vers le haut 8 / 16. 123 contacts, fractures différentes à chaque salve, SFX existants réutilisés sans musique. Les trois petites icônes FORK / GLOVE / HAMMER sont visibles dès le début en bas ; cadre et flèche sur l’outil actif, coche sur les outils terminés. Elles remplacent les textes ROUND ; scène recentrée. Même cuistot, pixel art, textes anglais et fin à la spatule. Contrôle strict réussi à 13 instants après la correction, sans erreur ni avertissement. Export final `experiments/chocolate-crunch/chocolate-crazy-tools-final.mp4` terminé ; 4 002 images décodées et regardées sur 67 planches, couverture minimale des titres 99,79 %, des icônes 100 %, outil actif vérifié sur chaque image, pic AAC −3,6 dBFS. Audit dans `experiments/chocolate-crunch/QA.md` ; livraison dans Codex, aucune publication sur les réseaux sociaux.

**Révision précédente courte : fourchette, gant de boxe à ressort et marteau-piqueur vers le haut.** Deux essais par outil : 1 / 4, puis 4 / 8, puis 8 / 16 tablettes. Montage raccourci à 23,30 s, 1080 × 1920 à 60 images/s. Ressort comprimé avant la patate latérale ; pointe du dernier outil orientée vers le haut, moteur et burin vibrant à 22 Hz. 41 contacts de chocolat, avec nouveaux SFX figés de ressort, boxe et percussion mécanique ; sans musique. Même cuistot, pixel art, textes anglais et fin à la spatule. Contrôle strict réussi à 28 instants, sans erreur ni avertissement. MP4 `experiments/chocolate-crunch/chocolate-crazy-tools.mp4` terminé ; 1 398 images décodées et regardées sur 24 planches, titres présents partout, pic AAC −3,6 dBFS. Audit final dans `experiments/chocolate-crunch/QA.md` ; livraison dans Codex, aucune publication sur les réseaux sociaux.

**Version précédente du 7 octobre : fourchette seule.**

Adaptation alimentaire des plaques qui tombent sur une pointe, étudiées chez NodeFan3D : 1 / 2 / 4 / 8 / 16 tablettes de chocolat sur une fourchette géante. Même manche blanche, paume, planche, palette et pixel art intégral que Watermelon ; fin à la spatule avec sautillement et confettis. 27,80 s, portrait 1080 × 1920, 60 images/s, titres anglais. Fractures obliques inégales au contact, 31 craquements synchronisés, retombées regroupées, sans musique. Export `experiments/chocolate-crunch/chocolate-giant-fork.mp4` terminé ; 1 668 images décodées et regardées sur 28 planches, titres présents partout, pic AAC −3,8 dBFS. Vérification de simulation et contrôle strict GPU matériel réussis. Six références téléchargées et analysées dans `experiments/physics-references/2026-10-07/README.md` ; aucun extrait ni son de ces vidéos repris dans notre rendu. Livré dans Codex, aperçu HyperFrames disponible ; aucune publication sur les réseaux sociaux. Simulation stylisée : collisions des éclats avec le décor, sans collisions mutuelles des débris denses.

## Essai de simulation low-poly — 7 octobre 2026

**Révision actuelle : chef, trois outils, éclats irréguliers et célébration.** 41,80 s, portrait 1080 × 1920 à 60 images/s. Paume sous le fruit pendant son arrivée ; départ normal à 1 CUT, puis machettes jusqu’à 32, grande scie flottante et rafales de pistolet cartoon. Les tirs produisent 18 / 40 / 100 morceaux anguleux inégaux. Fin à la spatule avec léger saut, confettis et étincelles pixel art. SFX de scie et de tir figés via Replicate, sans musique. Vérification physique et contrôle strict GPU matériel réussis. MP4 terminé, 2 508 images décodées et regardées dans 42 planches ; titres présents sur toutes les images, pic audio −3,4 dBFS. Livré dans Codex ; aucune publication sur les réseaux sociaux.

**Révision précédente : Pixel Cuts, son adouci et logo cuisto.** Cadence et maximum
32 conservés. Une petite icône pastèque accompagne WATERMELON. Le mix conserve
93 accents de coupe et regroupe 584 impacts en 67 accents discrets, sans saturateur.
Cache exact de palette et réutilisation des sommets entre coupes pour alléger la
preview. Export `experiments/watermelon-lowpoly/watermelon-pixelcuts-32-polished.mp4` :
14,65 s, 1080 × 1920, 60 images/s ; 879 images décodées et regardées sur quinze
planches. Pic audio −4,0 dBFS, contrôle strict GPU matériel sans erreur ni
avertissement. Logo pixel art avec spatule dans la main, selon la correction
utilisateur : `experiments/watermelon-lowpoly/brand/chef-spatula-avatar.png`.
Livraison dans Codex, aucune publication sur les réseaux sociaux.

**Révision précédente : Pixel Cuts, maximum 32.** Dernier retour utilisateur :
retirer 64 et ralentir les salves. Hook de 0,85 s qui coupe avant la chute, puis
1 / 4 / 8 / 16 / 32 CUTS ; salve finale étalée sur 1,90 s, lames visibles 0,15 s,
dispersion et rotation des morceaux modérées. Pixel art intégral et texte anglais.
Preview HyperFrames ouverte dans Codex avant export ; lecture du montage de
14,65 s constatée. MP4 de 1080 × 1920 à 60 images/s :
`experiments/watermelon-lowpoly/watermelon-pixelcuts-32.mp4`. Les 879 images ont été
décodées et regardées sur quinze planches ; titres présents sur chaque image,
pic audio à −1,7 dBFS. Livraison dans la conversation Codex ; aucune publication
externe. Cette version remplace les essais précédents pour la suite du format.

**Version révisée : Pixel Cuts.** Selon le retour utilisateur : pixel art sur toute
l'image, titres exclusivement anglais, coups de lame de 0,145 s espacés de 0,17 s,
un accent sonore par coupe. MP4 de 12 s, 1080 × 1920, 60 images/s :
`experiments/watermelon-lowpoly/watermelon-pixelcuts.mp4`. Les 720 images ont été
décodées et regardées sur douze planches ; contrôle des titres sur chaque image,
lecture complète et pic audio à −3 dBFS. Livraison dans la conversation Codex.
Cette version remplace le premier essai ci-dessous pour la suite du format.

Pastèque découpée en 1, 3 puis 7 passes : prototype original de 18 s, 1080 × 1920,
30 images/s, 2/8/32 fragments, géométrie 3D et physique calculées par code,
bruitages synthétisés. Livré dans la conversation Codex sous
`experiments/watermelon-lowpoly/watermelon-lowpoly.mp4` ; aucune publication externe.
Les 540 images ont été décodées et regardées sur neuf planches ; lecture du MP4
jusqu'à la fin et contrôle du niveau audio réalisés. Le rendu et les planches
restent locaux ; code, reproduction et limites dans le même dossier (`README.md`,
`QA.md`). Fragments rigides, sans jus ni chair souple. Inspiration : tweet
https://x.com/ErnestoSOFTWARE/status/2107832530770829559 ; aucun extrait repris.

État au 5 oct. 2026 : trois analyses sportives livrées sur Discord pour publication manuelle ; France–Belgique attend la fin du match. Mettre à jour à chaque livraison (lien Gofile, mode de livraison, date de publication).

## Oddly Expensive Lives (`oddly_expensive_en`)

| Vidéo | État | Lien |
|---|---|---|
| The Economics of a Divorce | publiée | https://gofile.io/d/hNaYSDIW |
| The Economics of Dying in America | livrée (Discord) | https://gofile.io/d/KCE0o4PZ |
| The Economics of Having a Kid | livrée, **version corrigée** (ticket de caisse) — l'ancienne a7J8p4bS est fausse | https://gofile.io/d/LWalsRCI |
| The Economics of an Ambulance Ride | livrée (Discord), vérifiée | https://gofile.io/d/OPhgqlbK |
| The Economics of a Wedding | **livrée** (vérifiée image par image, corrigée, salon Oddly Expensive Lives, 4 oct. ~13 h heure belge) — https://gofile.io/d/GTLWRLUM (l'ancienne hdhCOEn6 a des erreurs : ne pas poster) | |
| The Economics of a Car Accident | **livrée** (vérifiée image par image, corrigée, salon Oddly Expensive Lives, 4 oct. ~13 h heure belge) — https://gofile.io/d/39fxPk2e (l'ancienne d4mO5Vgd a des erreurs : ne pas poster) | |
| The Economics of a Nursing Home | **livrée** (vérifiée image par image, corrigée, salon Oddly Expensive Lives, 4 oct. ~13 h heure belge) — https://gofile.io/d/EK7nIFaj (l'ancienne OsTkNTv9 a des erreurs : ne pas poster) | |
| The Economics of Retiring With Nothing Saved | **livrée** (vérifiée image par image, corrigée, salon Oddly Expensive Lives, 4 oct. ~13 h heure belge) — https://gofile.io/d/ju2sSJmk (l'ancienne ronqbZRh a des erreurs : ne pas poster) | |
| The Economics of Getting Arrested | **livrée** (vérifiée image par image, corrigée, salon Oddly Expensive Lives, 4 oct. ~13 h heure belge) — https://gofile.io/d/4MfGf0ng (l'ancienne NbdoSLr9 a des erreurs : ne pas poster) | |

Idée suivante déjà discutée : la prison (mise de côté).

## Oddly Specific Things (`oddly_things_en`) — nouvelle chaîne

| Vidéo | État | Miniature |
|---|---|---|
| Your Life as a Stolen Phone | **livrée** (vérifiée, Discord) — https://gofile.io/d/FWMQaSSh | D « STOLEN » (main gantée qui arrache le téléphone) |
| Your Life as a Stolen Car | **refaite, vérifiée image par image, envoyée sur Discord le 2 oct.** (nouveau prompting : objet sans visage) — https://gofile.io/d/8Yh99Wbi (l'ancienne W3RbTNvA est KO : ne pas poster) | « STOLEN » clé de voiture ; 6 variantes renvoyées sur Discord le 2 oct. (SHIPPED, GONE…) |
| Your Life as a Stolen Credit Card | **refaite, vérifiée image par image, envoyée sur Discord le 2 oct.** — https://gofile.io/d/cStfBfSJ (l'ancienne 6Qj38smK est KO : ne pas poster) | « STOLEN » carte bleue ; 6 variantes renvoyées sur Discord le 2 oct. (CLONED, DRAINED…) |
| Your Life as a Stolen Bike | **vérifiée image par image (3 rendus, 52 images refaites : vrai expert retiré, vendeur en homme, vélo jamais entier dans les cartons…), envoyée sur Discord le 2 oct.** — https://gofile.io/d/A2tC0UxR | 7 variantes jointes au paquet (recommandée : FOR SALE), choix à l'utilisateur |
| Your Life as a Fake Designer Bag | **livrée** (vérifiée image par image, corrigée, Discord, 4 oct. ~13 h heure belge) — https://gofile.io/d/DMJl4E8W (l'ancienne 2N4dzqyI a des erreurs : ne pas poster) | 2-3 variantes jointes au paquet |
| Your Life as an Amazon Return | **livrée** (vérifiée image par image, corrigée, Discord, 4 oct. ~13 h heure belge) — https://gofile.io/d/Sgyh9BLj (l'ancienne EZintnGu a des erreurs : ne pas poster) | 2-3 variantes jointes au paquet |
| Your Life as Lost Luggage | **livrée** (vérifiée image par image, corrigée, Discord, 4 oct. ~13 h heure belge) — https://gofile.io/d/96s9jivz (l'ancienne dNT9Yp41 a des erreurs : ne pas poster) | 2-3 variantes jointes au paquet |
| Your Life as a Totaled Car | **livrée** (vérifiée image par image, corrigée, Discord, 4 oct. ~13 h heure belge) — https://gofile.io/d/lF86gVbv (l'ancienne x4FhWukR a des erreurs : ne pas poster) | 2-3 variantes jointes au paquet |
| Your Life as a Donated T-Shirt | **livrée** (vérifiée image par image, corrigée, Discord, 4 oct. ~13 h heure belge) — https://gofile.io/d/lP3cdKSk (l'ancienne N4BCXHTI a des erreurs : ne pas poster) | 2-3 variantes jointes au paquet |

Description de chaîne : « Some things live oddly specific lives. » (+ en option : « Your phone, your car, your
card… followed hand to hand, all the way to where they really end up. »)
Idées suivantes : diamond, $100 bill…

## Oddly Specific Lives (`oddly_specific_en`)

| Vidéo | État | Publication |
|---|---|---|
| Inside The Life Of An Onlyfans Model | publiée | 30 sept. |
| POV: You Marry a Female Triad Boss | publiée | 1er oct. |
| POV: You Marry a Female UFC Fighter | **livrée** (vérifiée, Discord) — https://gofile.io/d/MSC7DFd0 ; miniature : combattante dans la cage, ceinture en or sans logo, en sueur | **3 oct.** |
| POV: You Marry a WNBA Star | **livrée** (vérifiée, Discord) — https://gofile.io/d/u35duG8B ; miniature refaite (femme différente de l'UFC, plus sexy) : tresses, maillot blanc et turquoise n° 23 sans logo, renvoyée sur Discord | **4 oct.** |
| POV: You Marry a Female Assassin | **livrée** (vérifiée image par image, Discord, 3 oct. 17:41 UTC) — https://gofile.io/d/sbzA4FiZ ; 15 min 43 ; Londres, Mara + Biscuit, faits réels (étude Birmingham City University 2014) ; 3 images refaites avant envoi (mariage avec un autre couple, appareil photo après « no photos ») ; miniature : planque, mur de cibles, fusil démonté dans la mallette, pistolet à silencieux levé (sans drapeau ni ville) | à caler |
| POV: You Marry a Singaporean Woman | **livrée** (vérifiée image par image, Discord, 25 oct. 21:05 Belgique) — https://gofile.io/d/wAs0lg8v ; ~27 min ; HDB/BTO, hawker centres (UNESCO 2020), chope, lo hei, tea ceremony, ROM ; miniature B : hawker centre, chicken rice + paquet de mouchoirs | à caler |
| POV: You Marry a Canadian Woman | **livrée** (vérifiée image par image, Discord, 25 oct. 21:32 Belgique) — https://gofile.io/d/5DudSn5G ; 26 min 28 ; Winnipeg, Claire ambulancière, block heater, cabane à sucre, Thanksgiving 1957, poutine, Tim Hortons ; 2 plans de voiture refaits avant envoi (volant à droite → à gauche) ; miniature A : Québec, crosse de hockey | à caler |

Ensuite : d'autres sports (nom de la grande ligue dans le titre).

## The Survivor's Account (History Docs, `survivors_account`)

| Vidéo | État | Publication |
|---|---|---|
| What a 15-Year-Old Girl Saw at Gettysburg Was Too Brutal for Textbooks | **livrée** (vérifiée plan par plan, Discord, 2 oct.) — https://gofile.io/d/XXlkFSbS ; 36 min, voix Earl, rendu RunPod (~2 $) ; miniature « SHE SAW EVERYTHING » | à caler |
| Gettysburg **v2** (même voix, style « peinture d'histoire », regards caméra, réalisme) | **livrée** (vérifiée, Discord, 3 oct. 00:24) — https://gofile.io/d/ydAC4RRY ; 30 s d'Adobe Walls mélangées par le VPS (19:30-20:00) repérées à la relecture et refaites avant envoi ; 3 miniatures sans médaillon (BRUTAL FATE, CHILLING TRUTH, SHE SAW EVERYTHING) | à caler |
| The 17-Year-Old Who Watched Pompeii Die — His Letters Still Exist | **livrée** (vérifiée, Discord, 3 oct.) — https://gofile.io/d/lDhthE4R ; 40 min, rendu 100 % VPS ; 16 plans des fouilles (1738-2024) refaits avant envoi (Romains en toge aux fouilles) ; miniatures CHILLING TRUTH, NO SUN RETURNED, WORSE THAN DEATH | à caler |
| The 15-Year-Old Who Survived Agincourt — His Father Didn't | **livrée** (vérifiée plan par plan, salon Discord The Survivor's Account, 4 oct. 01:46 heure belge) — https://gofile.io/d/LwVV3hfd ; 40 min, rendu 100 % VPS ; témoin Jean de Waurin (15 ans, « was in the French army ») ; miniatures BRUTAL FATE (le garçon porte les armes anglaises : à éviter), CHILLING MEMORY, WORSE THAN DEATH | à caler |
| The Zulu Warrior Britain Blamed for a War — What He Saw at Isandlwana | **livrée** (vérifiée image par image, corrigée, Discord, 4 oct. ~13 h heure belge) — https://gofile.io/d/RWXgYebX (l'ancienne Ct1kMgP0 a des erreurs : ne pas poster) | |

## Frontier Blood (History Docs, `frontier_blood`)

| Vidéo | État | Publication |
|---|---|---|
| How 28 Buffalo Hunters Held Off Hundreds of Warriors at Adobe Walls | **livrée** (vérifiée, Discord, 3 oct. 00:22) — https://gofile.io/d/vWmECEPV ; miniatures renvoyées sans médaillon (HIDDEN TRUTH, BRUTAL DAWN, WORSE THAN DEATH) | à caler |
| The Alamo's Last 90 Minutes, Through the Eyes of a Boy Who Survived | **livrée** (vérifiée image par image, corrigée, salon Frontier Blood, 4 oct. ~13 h heure belge) — https://gofile.io/d/wFy6CQr1 (l'ancienne RA1PIU4T a des erreurs : ne pas poster) | |
| The Comanche Raid That Reached the Sea — And Burned a Texas Town | **livrée** (vérifiée image par image, corrigée, salon Frontier Blood, 4 oct. ~13 h heure belge) — https://gofile.io/d/Q5ObAUrp (l'ancienne LEpCCq85 a des erreurs : ne pas poster) | |
| The Fetterman Fight's Last 30 Minutes Were Worse Than You Were Told | **livrée** (vérifiée image par image, corrigée, salon Frontier Blood, 4 oct. ~13 h heure belge) — https://gofile.io/d/kuTc6gpJ (l'ancienne L1yfYRtc a des erreurs : ne pas poster) | |

## Cage Dispatch (actu MMA, `news/mma_en/`, outil `production/news.py`)

| Vidéo | État | Publication |
|---|---|---|
| “I BROKE HIS FACE!” Justin Gaethje FIRES BACK At Ilia Topuria’s Glove Claim! (titre choisi par l'utilisateur) | **livrée v4 bleue CORRIGÉE** (Discord, 4 oct. 00:11 heure belge) — https://gofile.io/d/y1fhk7Xj ; 14 min 46 ; refaite sans les extraits de One Night with Steiny (revendication Content ID sur la v3), commence par la voix off + photo, tout en bleu ; miniature “I BROKE HIS FACE” (bleu clair) | à caler |
| “IT'S NOT GOING TO HAPPEN!” Arman Tsarukyan SHUTS DOWN Topuria As Ilia Returns To Training! | **livrée** (Discord, 4 oct. 00:52 heure belge) — https://gofile.io/d/potc7Pzl ; 18 min 58 ; sources Double Coverage, Sonnen, Helwani, Submission Radio ; 1ère version montée non envoyée (13 noms mal écrits dans les sous-titres, corrigés) ; transitions douces + logo 4,5 s ; miniature Tsarukyan + Topuria “IT'S NOT GOING TO HAPPEN” | à caler |
| **PITCH DISPATCH #1** “GRAB MY BAG AND LEAVE!” Ronaldo WALKS OUT On Portugal After Jorge Jesus Clash! | **livrée** (Discord, 4 oct. ~04h00 heure belge) — https://gofile.io/d/cguE7OrS ; 21 min 22 ; sources Fabrizio Romano, Coach Ali, On The Continent (toutes IVP) ; miniature verte Ronaldo + Jorge Jesus “GRAB MY BAG AND LEAVE” | à caler |


- 4 oct. : **Ring Dispatch #1** (boxe) « MENTALLY WEAK! » Tyson Fury SLAMS Anthony Joshua… envoyée (https://gofile.io/d/nPQsyecm, 18 min).
- 4 oct. : OSL en préparation (`--gate`, script à relire) : POV: You Marry a Japanese Woman (`work/osl/japanese`), a Female Boxing Champion (`work/osl/boxer`), a Norwegian Woman (`work/osl/norwegian`), a Female WWE Champion (`work/osl/wwe`). Bratva refusée par l'utilisateur. Japanese : envoyée sur Discord comme les autres, il la postera après la monétisation.
- 4 oct. : OSL livrées (salon Discord OSL) : Norwegian Woman https://gofile.io/d/esqXlDcr ; Female Boxing Champion https://gofile.io/d/CJ34Wb0V ; Japanese Woman https://gofile.io/d/mm5KldUF (à poster après la monétisation) ; Female WWE Champion https://gofile.io/d/60IGi9uv. Miniatures : Japanese A, Norwegian B, Boxing B, WWE B.
- 4 oct. (soir) : OSL livrées (salon Discord OSL) : Brazilian Woman https://gofile.io/d/sXBdvVA2 ; Ukrainian Woman https://gofile.io/d/yezV1AP1 ; Korean Woman https://gofile.io/d/n77Xy6Q4. Miniatures refaites (drapeaux collés à la même taille, vrais drapeaux) : Brazilian J (mains corrigées), Korean E, Ukrainian J (Lviv, tenue moderne).
- 4 oct. (soir) : OSL lot 3 « femmes dangereuses » en production : Female Samurai (Aizu 1868, miniature H3 katana), Female Mafia Boss (Naples, miniature G), Female Cartel Boss (barman dans un club de Culiacan, miniature I), Female Hacker (Portland, miniature H). Scripts relus + FOS, images en cours.
- 4 oct. (nuit) : OSL lot 3 livré (salon Discord OSL), vérifié image par image : Female Cartel Boss https://gofile.io/d/kiSnTmGO (miniature I) ; Female Mafia Boss https://gofile.io/d/cxHg6Qbi (miniature G) ; Female Hacker https://gofile.io/d/lwcIlpUY (miniature H) ; Female Samurai https://gofile.io/d/XtBNFLjv (miniature H3, 2 images refaites : salon moderne + cheminée occidentale → tatami + irori).

## Analyses sportives courtes — 5 octobre 2026

Livraison dans la conversation puis sur **Discord, à la demande de l'utilisateur**, pour publication manuelle : chaque lien contient le MP4 et un kit ZIP
(miniature validée, trois titres proposés, description avec chapitres et sources, tags, sous-titres et crédits).
Les trois vidéos sont en anglais avec la voix de leur chaîne. Toutes les planches (une capture toutes les
cinq secondes) ont été regardées ; décodage, format 1080p et recalage des sous-titres sur la voix contrôlés.
Les transferts MP4 et ZIP ont été vérifiés par taille et empreinte MD5. Les deux vidéos MMA sont envoyées
dans Cage Dispatch, Mbappé dans Pitch Dispatch ; aucune publication YouTube automatique.
Chaque message Discord contient la miniature choisie et un kit ZIP avec les titres renforcés du 5 octobre,
description et chapitres, sources, crédits, tags et commentaire épinglé proposé.
Les webhooks restent dans `.env` ; les traces d'envoi sont dans `discord_receipt.json` et `discord_done`.

| Chaîne | Sujet | Durée | Miniature choisie | Lien | Publication |
|---|---|---|---|---|---|
| Cage Dispatch | Parnasse–Topuria : rumeur, stories d'Atch et repost TikTok rapporté par RMC | 4 min 08 | A — TOPURIA NEXT? | https://gofile.io/d/lRKv6ZQW | à publier manuellement |
| Cage Dispatch | Imavov–Strickland : le défi public à 500 000 dollars et sa condition | 4 min 00 | A — $500,000 CHALLENGE | https://gofile.io/d/0IyYUojj | à publier manuellement |
| Pitch Dispatch | Mbappé : la story à vélo, Mourinho et la réaction des médias espagnols | 4 min 33 | B — BIKE RIDE BACKLASH | https://gofile.io/d/w5KntWGY | à publier manuellement |

Dossiers : `news/mma_en/2026-10-05_parnasse-topuria-analysis/`,
`news/mma_en/2026-10-05_imavov-strickland-analysis/` et
`news/football_en/2026-10-05_mbappe-bike-analysis/`.
Le combat Parnasse–Topuria n'est pas présenté comme signé ; le repost original TikTok reste attribué à
RMC, sans prétendre l'avoir vérifié directement. Le défi d'Imavov est conditionnel, sans accord de combat
annoncé. L'intention de Mbappé envers Mourinho reste une interprétation ; sa réponse sur le Ballon d'Or
concerne une autre allégation.

5 octobre, retour utilisateur : import des trois vidéos sur YouTube sans réclamation de droits signalée.
Publication en cours selon l'utilisateur ; état final non vérifié directement dans YouTube Studio.
Le nouveau contrôle de licences (`rights_audit.json`) distingue ce résultat des droits de réutilisation :
miniatures sous licences documentées et musique originale, mais images de presse des montages non autorisées
pour réutilisation automatique tant que leurs droits ne sont pas établis. Pour les prochaines vidéos,
le contrôle des droits est obligatoire et bloquant avant automatisation.
L'utilisateur conserve les deux nouvelles miniatures déjà reçues, valide leur thème pour toutes les suivantes
et demande l'arrêt des variantes supplémentaires. Références sauvegardées dans
`presets/news_thumbnails/approved_2026-10-05/` ; aucun nouvel envoi de variantes après cette demande.

**France–Belgique** : quatrième sujet prévu après le match du 5 octobre (20 h 45 heure belge).
Collecte préparée et testée avec refus des scores provisoires, absents et des matchs abandonnés ;
voir `production/NEWS_BRIEFS.md`. Aucun résumé produit avant résultat final, aucune attente automatique
lancée. L'automatisation quotidienne reste reportée à la demande de l'utilisateur.

## Historical Daily - 8 October 2026, long narration checkpoint

Episode 01 for Edo Daily, Aztec Daily, Babylon Daily, Imperial China Daily and
Ottoman Daily: the user confirmed **20-25 minutes for EACH film**. Codex wrote
five new English scripts with separate daily work, household and social stories.
No reuse of the rejected Edo script, narration or repetitive image sequence.

| Channel | New measured narration | Full film |
| --- | --- | --- |
| Edo Daily | 21:54.19 | Not yet rendered |
| Aztec Daily | 23:39.25 | Not yet rendered |
| Babylon Daily | 22:04.64 | Not yet rendered |
| Imperial China Daily | 22:27.47 | Not yet rendered |
| Ottoman Daily | 22:58.87 | Not yet rendered |

Fresh Algrow voices and actual word measurements are cached separately under
`work/historical-01-2026-10-08/<channel>/`. Measured transcript coverage exceeds
98% for each narration. Duration, cached voice identity and audio fingerprints
are checked before shot timing. The narration-only manifests cannot be rendered
as complete films. Focused narration/timing/reference tests: **32 passed**.

Codex also authored 28 initial opening shots, with exact narration word ranges,
named characters, individual prompts and explicitly ordered references. These
are **partial openings**, not the full films. Full shot writing, distinct scene
generation and final montage remain pending. Never loop these openings to fill
20 minutes. The six-second cadence requires at least 1,133 distinct shots across
the five measured voices, including the closing tail.

Reference masters and white-headed cast are generated through the configured
CLI Proxy and reviewed individually. Skin shadows, crossed collar drift,
invented distant monuments and changing props are corrected explicitly, not
declared solved merely because reference images were sent. Early opening
candidates include faults in shoe shape, produce contents, rope attachment and
hand details; only reviewed corrected selections may enter montage.

All 28 opening shots now have explicit individual visual decisions in
`chaines/_production-01-2026-10-08/opening-reviews.json`: 17 creative candidates
accepted and 11 requiring more correction. These are not render approvals.
Some proxy outputs need verified 16:9 formatting. Remaining faults include
Edo lower garments and counter positions, Aztec neck/grip detail, Babylon
collars, and Ottoman camera axis, grip fingers and a spike invented on a mallet.
No image worker remains running at this checkpoint.

Scripts, sources and partial plans: `chaines/<channel>/01-production-2026-10-08/`.
Batch checkpoint: `chaines/_production-01-2026-10-08/`.
New visuals: `output/imagegen/historical-01-2026-10-08/`.
No frontend changes, no finished full-film delivery, no upload or publication.

## Historical Daily - 8 October 2026, continued production

All 28 opening shots now have individually viewed, creatively accepted
correction selections. Final 16:9 formatting and montage checks remain.
Edo has 56 additional personally authored shots (007-062), linked to actual
narration excerpts and word-clock timings; each generated candidate was opened
individually. Many are explicitly rejected in the visual ledger for changing
objects, clothing or hands. They must not enter montage until corrected.

Separate object image anchors and empty room state variants are being added
to prevent textual descriptions alone from causing disappearing parcels,
changing bucket handles, extra bowls or stacked commercial bolts replacing
a personal garment. Opaque object corrections remove unsolicited alpha.
No completed new full film, no repeated-image padding, no upload/publication
and no frontend edits. Source prompts, actual request receipts and rejection
notes preserve the unfinished work for a truthful continuation.

## Anime Chess - 11 October 2026, L versus Light

Completed local delivery: L Outsmarts Light Analysed like Chess | Death Note.
7m29.1s, 1920x1080, 30fps, seven personally authored annotations, original
English dub, original Chess.com rating icons and native Kdenlive recap.
All 13,473 frames inspected across 68 contact sheets; 38 larger captures and
three full-resolution captures checked. Full decode passed; final sound
-19.2 LUFS, -3.2 dBFS true peak. Source copies remastered upstream; not a
verified studio master. Report and reproduction steps: experiments/conversation-chess/DEATH_NOTE.md.
Current MP4 and editable media bundle remain in work/conversation-chess/death-note-light-l-v1/.
Timeline, publishing text and QA receipt backed up in Git. No upload or publication.

## Anime Chess - 11 October 2026, Death Note publishing kit

Delivered a local A-PUBLIER folder containing the verified 7m29.1s MP4,
1280x720 JPEG thumbnail, title, short English description and music attribution.
Copied video SHA256 matches the reviewed delivery. Thumbnail illustration
and final composite viewed: L calculating, Light surprised, original Brilliant
and Blunder SVGs tilted +10/-10 degrees. SVG hashes verified; artwork outside
badge corners preserved before JPEG encoding. Base, prompt, receipt and export
backed up in experiments/conversation-chess/thumbnails/light-vs-l/.
Windows Explorer opened on the complete delivery folder. No upload or publication.

## Anime Chess - 11 October 2026, Death Note Content ID revision

User's Studio captures show a global Nippon Television audiovisual block
on 358 seconds of the 449.1s original; two VAP episode-music claims also exist.
Original retained. Produced a separate 91s graphics overview, removing all
episode pictures, original dub, episode music and replays, including the guide
and recap backgrounds. Seven native analyses, verified rating SVGs and pawn
colors retained; reading holds extended to nine seconds. Exported with Kdenlive.
All 2730 frames inspected in 14 contact sheets plus 11 full-size captures;
full decode passed. Bundle audit: no episode asset, eight original music/SFX
assets only. Local A-REGARDER-V2-GRAPHICS folder opened with MP4, thumbnail,
title and revised description. QA hash and reproduction saved in Git.
This is a different graphic format; YouTube clearance remains unverified.
No claim dispute, upload or publication performed.

## Anime Chess - 11 October 2026, Death Note scene-led V3

The user rejected the 91-second graphics-only V2 because it removes the scene
and dialogue. Preserve that experiment as an archive and retain V1 unchanged.
V3 uses thirteen explicitly authored scene excerpts with the English dub,
seven native chess analyses, the existing guide and recap. All 26 source cut
boundaries are outside aligned words. Two comments are adapted to retained
context; the full final declaration and fade are preserved.

Final local package: work/conversation-chess/death-note-light-l-v3-edit/A-TESTER-V3/.
182.6 seconds, 1920x1080, 30fps, 5478 frames; 70,124,437 bytes.
SHA256 b3e5d2fb3d6c438acc3587003bcbbf8c2c11c516984d2011fda93ebefe5033ec.
Reviewed all 28 full-frame contact sheets and 35 larger captures. Native export
and full decode pass; dialogue finishing preserves the picture stream,
-19.2 LUFS integrated, -3.0 dBFS true peak. Original V1 hash is unchanged.

Authored edit, reusable source preparation, QA and reproduction notes saved in
experiments/conversation-chess/. Keep video, original sources and full private
transcripts outside Git. Existing thumbnail/title/description included.
The new cut still contains episode footage and soundtrack. Content ID has not
been tested: do not describe the global block as resolved. No automatic upload,
publication or dispute. Unrelated historical production changes preserved.


## Death Note V3 — procédé transmis et retour YouTube, 11 octobre 2026

L’utilisateur rapporte l’absence de problème de copyright après son contrôle
YouTube de la V3. Retour conservé séparément du reçu QA initial dans
`experiments/conversation-chess/episodes/light-vs-l.edit.youtube-report.json` ;
aucune inspection indépendante du compte ni vérification du hash uploadé.
Le guide `experiments/conversation-chess/PROCEDE-V3-A-TRANSMETTRE.txt` décrit
le découpage réellement effectué (372,1 → 105,6 secondes de scène jouée),
les sept analyses, le rendu natif et les contrôles. Il contient un prompt
adaptable aux autres séries, sans promesse de résultat Content ID universel.
Copie du guide et du retour dans le paquet local `A-TESTER-V3/`.
Aucune modification du MP4, aucun upload ni contestation.


## Death Note — quatre styles de miniature, 11 octobre 2026

Nouvelle exploration demandée après le rejet de la miniature initiale.
Quatre illustrations différentes : piège télévisé, duel anime serré, manga
clair et métaphore des pions. Bases, prompts et JPEG dans
`experiments/conversation-chess/thumbnails/light-vs-l/styles-v2/`.
Les SVG Chess.com originaux sont vérifiés et inclinés, avec des placements
adaptés ; le compositeur accepte désormais un fichier de placement optionnel.
Son rendu historique par défaut reste identique par SHA256. Quatre sorties
1280×720 sous 2 Mo, regardées en grand et à 312 pixels de largeur ; aucun
badge ne couvre les yeux ni les accroches. Alternatives créatives non testées
en performance de clics. Paquet local `A-TESTER-V3/THUMBNAILS-4-STYLES/` avec
comparatifs et titre. Ancienne miniature et MP4 conservés ; pas de publication.


## 11 octobre 2026 — Deux Shorts anime chess

Livraison de deux montages anglais indépendants : le leurre télévisé de L dans
Death Note (44,63 s) et Ayanokoji contre Ryuen dans Classroom of the Elite
(48,27 s). Format 1080 × 1920, 30 fps, deux évaluations originales par Short,
icônes Chess.com vérifiées, pions selon les camps, aucune voix off ni musique
ajoutée. Répliques et cadrages contrôlés ; pauses corrigées sur les personnages
qui font les moves. Export natif Kdenlive ; dialogue relevé sans réencoder
la vidéo. Contrôle des 1339 / 1448 images finales, décodage complet et mesures
audio archivés. Tests portrait / paysage validés.

Livraison locale : `work/conversation-chess/shorts/A-UPLOADER-2026-10-11/`.
Vidéos, titres, descriptions, reçus QA et projets éditables conservés en local.
Code, découpages et reprise : `experiments/conversation-chess/SHORTS.md`.
Le clip Classroom public n'est pas un master raw ; les cadrages excluent le
petit logo à son bord. Aucune publication ni vérification YouTube effectuée.


## 11 octobre 2026 — Shorts chess : passages continus et fond noir

Retour utilisateur appliqué aux deux Shorts : moins de coupes, répliques
entières, cadrage large constant et fond extérieur noir pur permanent.
Death Note V2 conserve sa source validée et dure 96,20 s ; une seule ellipse
adoucie de 200 ms. Classroom V3 dure 57,33 s et conserve le passage intégral
44,20–90,733 s, interrompu uniquement par une pause d'analyse. Même clip
anglais public repris dans un flux H264 HD natif : amélioration modeste,
aucun nouveau master raw confirmé. Les anciens exports restent archivés.

Contrôle visuel des 2886 / 1720 images finales et évaluations à taille native,
décodage complet, fond noir testé dans chaque image. Dialogue relevé sans
réencoder le flux vidéo natif : −16,2 / −17,0 LUFS, crêtes −1,2 / −1,1 dBFS.
Deux fichiers 9:16 en 1080 × 1920 / 30 fps, titres et descriptions dans
`work/conversation-chess/shorts/A-POSTER-CORRIGE-2026-10-11/`.
Projets natifs éditables conservés localement. Reprise et reçus :
`experiments/conversation-chess/SHORTS.md` et
`experiments/conversation-chess/episodes/shorts-2026-10-11-smooth.qa.json`.
Aucune publication ni nouvelle vérification YouTube effectuée.


## 11 octobre 2026 — Shorts chess : clip vertical agrandi

Death Note V3 et Classroom V4 : clip central vertical 3:4 de 864 × 1152,
deux fois la surface du cadre horizontal précédent, dans un export 9:16
1080 × 1920 / 30 fps. Titre compacté, analyses sous le clip, fond noir.
Recadrages écrits et revus plan par plan, suivant les coupes natives.
Sources, passages et durées conservés : 96,20 s / 57,33 s.
Audio final précédent repris par copie AAC et vérifié par empreinte ;
aucune nouvelle compression du son ni du flux vidéo après le rendu natif.

Contrôle visuel des 2886 / 1720 images finales, évaluations à taille native,
décodage complet et fond extérieur noir testé dans chaque image.
Livraison avec titres et descriptions :
`work/conversation-chess/shorts/A-POSTER-VERTICAL-2026-10-11/`.
Reprise et reçu : `experiments/conversation-chess/SHORTS.md` et
`experiments/conversation-chess/episodes/shorts-2026-10-11-portrait.qa.json`.
Projets natifs éditables et anciennes versions conservés localement.
Aucune publication ni nouvelle vérification YouTube effectuée.


## 12 octobre 2026 — Dix replays d'échecs supplémentaires

Le dossier demandé contient cinq fichiers restants (06 à 10). Dix nouvelles
parties complètes sont ajoutées sous les numéros 11 à 20, dans le même style
Remotion : échiquier vert, fond sombre, notation à droite. Chaque export dure
180 s, 1280 × 720 / 30 fps, sans audio. Titres dans l'ordre mis à jour pour
les quinze fichiers disponibles. Empreintes des cinq vidéos conservées
identiques avant et après livraison ; aucune vidéo supprimée recréée.

Parties simulées 51 à 60 : coups légaux, PGN complets, aucun doublon avec les
anciens lots. Décodage intégral des dix films ; 1289 positions affichées
contrôlées sur 47 planches et vingt captures à taille native. Livraison :
`C:/Users/ytbyt/Documents/Codex/2026-10-04/j/outputs/chess-10-ancien-style/`.
Projet local `work/chess-remotion` sous le dossier `j`, exports et contrôles
dans `exports-2026-10-12`. PGN et reçus sauvegardés dans
`experiments/board-replays/batches/2026-10-12/`. Aucune publication effectuée.


## 13 octobre 2026 — Chess Analysis, Eren VS Reiner

Attack on Titan : confrontation dans la cave de Liberio, doublage anglais,
sans voiceover, outil conversation-chess conservé. Montage final V2 : 7 min
13,1 s, 1920 × 1080 / 30 fps. Sept analyses : Eren blanc, Reiner noir,
pions selon le camp, pauses après les répliques, replay muet, guide16s
avec Sneaky Snitch et bilan natif12s sans Subscribe. Le passage enregistré
avec curseur/chargement a été remplacé par une acquisition indépendante1080p.
Logo Adult Swim conservé selon l'autorisation explicite de l'utilisateur.

Contrôle des12 993 images sur65 planches,38 captures clés et cadres natifs.
Décodage intégral, flux image inchangé après finition sonore limitée aux
scènes : −19 LUFS, pic réel −1,9dBFS. Deux miniatures anime/manga avec les
SVG Chess.com originaux inclinés. Projet Kdenlive portable,51 médias vérifiés.
Titre, description courte et description avec attribution musicale livrés.

Livraison : `outputs/chess-eren-reiner-2026-10-13/`.
Timeline, reçus et reprise : `experiments/conversation-chess/ATTACK_ON_TITAN.md`,
`episodes/eren-vs-reiner*`, `thumbnails/eren-reiner/` dans ce même outil.
Sources et contrôles détaillés privés dans `work/`. Aucun upload ou contrôle
Content ID effectué pour cet épisode ; la validation porte sur le fichier local.


### Oddly Fictional Lives — episode05 delivered

Your Life Working for Jabba the Hutt:145 inspected static shots, Ryan Kurk narration,16:25,1080p/24fps, hard cuts. Situation-specific acting replaces inherited worried faces. Rendered on VPS CPU; encoded-video QA and independent local SHA/size transfer passed. Delivery: `01 - Videos/Oddly Fictional Lives/05 - Your Life Working for Jabba the Hutt/`. Final VPS MP4 and obsolete frames removed after transfer; required voice/reference/authoring assets preserved. See `chaines/oddly-fictional-lives/videos/05-your-life-working-for-jabba-the-hutt/publication.md`. No YouTube upload performed.


### Survival drawing style — matched-provider short-film test

Delivered two full-frame versions and one synchronized comparison of the same76.61s fictional story:12 inspected shots, one Ryan Kurk narration,1080p/24fps, static camera and hard cuts. Images/render/QA on VPS only; local MP4 transfer verified by SHA-256. Residual accessory/lighting differences documented; not a new channel episode or YouTube upload. Local delivery: `03 - Creation/Bunker Survival - Comparatif video/`. Sources and observed limits: `reference/style-studies/bunker-provider-film-2026-10-16/README.md`.


### 22 octobre 2026 - Oddly Important Guy : avocat livre

Your Life as a Billionaire's Lawyer : 15 min 39, 1920 x 1080 / 24 fps,
157 plans fixes alignes sur la narration originale, aucun nouvel appel vocal.
Les sources finales sont attribuees a 70 inspections directes et 87 revues
assistees ; les alertes de bureau, doublons et termes visibles sont corrigees
avant montage. Les 29 planches du film encode ont ete regardees ; les 22 526
images passent la comparaison technique avec les fondus attendus et le son
conserve la narration originale. Ouverture depuis le noir en une seconde,
transitions de 0,5 seconde, fermeture vers le noir de cinq secondes.

Rendu uniquement sur le serveur. Copie locale complete verifiee par empreinte,
ancienne video archivee, projet natif mis a jour puis seul MP4 final distant
supprime ; sources et voix conservees. Livraison :
`01 - Videos/Oddly Important Guy/07 - Billionaires Lawyer/VIDEO.mp4`.
Empreinte : `08acbebbe0afa10ec42ca1361d7b95b17f1c6877c8311e9726773c6d59921d77`.
Aucune publication ni programmation effectuee.

### 22 octobre 2026 - Casino : revision complete des figurants livree

153 sources finales : 124 inspections directes et 29 revues assistees attribuees.
Les tetes des figurants suivent le contour rond blanc, y compris les profils et
les personnes representees dans une image. Les 150 versions rejetees restent
conservees et exclues du montage. Les 28 planches du nouveau film encode ont
ete regardees ; les 21 955 images, les fondus et le son original passent les
controles techniques. Rendu sur le serveur seulement : 15 min 15, 1080p/24 fps.

Livraison : `01 - Videos/Oddly Important Guy/02 - Working Inside a Las Vegas Casino/VIDEO.mp4`.
143 020 299 octets ; empreinte `f4bb7f8008e6fe9a4ac913f7855ef17847c23984f4effe2558642417751b9fa0`.
Copie locale verifiee, ancienne livraison archivee, projet natif mis a jour puis
seul MP4 final distant supprime ; sources et voix conservees. Aucune nouvelle
synthese vocale, publication ou programmation. Six films livres sur onze.


### 22 octobre 2026 - Oddly Important Guy : pilote livre

Your Life as a Private Jet Pilot : 15 min 43, 1920 x 1080 / 24 fps.
158 plans : 69 inspections directes et 89 revues assistees attribuees avant
montage. Les 29 planches du film encode ont ete regardees ; les 22 639 images
passent les controles techniques, avec la narration originale conservee sans
nouvel appel vocal. Plans fixes, fondus de 0,5 seconde, ouverture depuis le noir
en une seconde et fermeture vers le noir de cinq secondes.

Rendu uniquement sur le serveur. Copie locale verifiee par empreinte, ancienne
livraison archivee, projet natif mis a jour puis seul MP4 final distant supprime ;
sources et voix conservees. Livraison :
`01 - Videos/Oddly Important Guy/05 - Private Jet Pilot/VIDEO.mp4`.
134 148 229 octets ; empreinte `1385beecc13ff8bfe70b693be28675423216f6789c7436babe9243cef8f6a13a`.
Aucune publication ni programmation effectuee. Sept films livres sur onze.
