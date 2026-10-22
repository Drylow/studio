# Production continue sur le serveur

## Diagnostic du 22 octobre

Les mesures du lot en cours montrent des requetes image completes medianes de
50 a 57 secondes selon le film, references comprises. Trois appels simultanes
restent une limite de debit, pas une promesse de delai final. Des erreurs de
capacite du service captcha et deux interruptions du service web ont aussi ralenti
la production. Le processus de production est maintenant isole du service web.

Le casino a surtout accumule des retouches de figurants : 220 versions reussies
supplementaires pour les identifiants presents dans les recus de cette reprise.
Ce nombre ne represente ni 220 nouveaux plans utiles ni un taux de rejet de tous
les films. Le controle initial avait confondu couleur blanche et contour de tete
circulaire. La correction de cette regle apres generation du film entier a cree
un travail evitable. Le guide de tetes approuve fait maintenant partie des
references des nouvelles requetes.

Les derniers rendus des films yacht, garde du corps et avocat, y compris leurs
controles techniques, ont pris environ six minutes chacun. La principale attente
etait donc avant le rendu : references, generation, retouches et reprise manuelle
de petits lots. Les traitements media restent exclusivement sur le serveur.

## Ce qui change

`production_watch.py` observe uniquement les films et les stages enumeres dans
un contrat prive explicite. Le contrat donne, pour chaque intervalle, l'identifiant
exact attendu, le prompt ecrit par l'auteur, les references ordonnees inspectees,
l'action, la distribution et l'horloge de la voix. Il ne redige rien.

Des qu'un resultat arrive, le superviseur verifie les empreintes et reutilise les
preuves de controle existantes si le contenu et le contexte correspondent. Les
images sans preuve partent au controle au fil de l'eau, par petites vagues. Ce
controle avance pendant que d'autres images generent. Un verrou global empeche
de multiplier les analyses en lancant plusieurs superviseurs.

Les resultats ordinaires acceptes sont attribues au controle par proxy, jamais a
une inspection directe imaginaire. Les scenes qui servent de nouvelles references,
les alertes, doutes, plans signales et risques de posture au bureau restent en file
de revue directe. Les anciens rejets priment sur un PASS automatique. Les vrais
defauts de visages, pupilles, bras, posture et decor restent bloquants. Une variation
illustrative sans contradiction materielle ne doit pas provoquer une retouche.

Quand toutes les sources attendues sont effectivement acceptees et que le script
et la voix d'origine ont leurs empreintes attendues, le superviseur peut lancer le
rendu autorise. Un verrou separe serialise ces rendus sans bloquer la generation
ni les analyses. La reservation du rendu est ecrite avant son lancement. Le MP4
reste en attente de revue finale : aucune publication, programmation, notification,
suppression du fichier distant ou revendication de livraison n'est automatique.

Les erreurs d'image a issue inconnue ne sont jamais renvoyees. Le superviseur ne
fait aucun appel de generation, aucune nouvelle voix ni changement de fournisseur.
Une pause du proprietaire empeche les nouveaux controles et rendus. Un contrat
incomplet ou modifie bloque son film sans bloquer les autres films autorises.

## Execution

Depuis la racine de l'installation, sur le serveur uniquement :

```bash
python -m app.production_watch --config /chemin/prive/contrat.json --once --no-audit
python -m app.production_watch --config /chemin/prive/contrat.json
```

La premiere commande inspecte la disponibilite des preuves sans nouvel appel de
vision. Elle peut lancer un rendu si le contrat l'autorise explicitement et si
tous ses controles sont deja complets ; `automatic_render: false` le desactive.
La seconde observe continuellement le lot, meme si le chat ou le PC sont fermes,
tant que le processus et le conteneur de production restent actifs. Elle ne
redemarre pas automatiquement un conteneur arrete.

Le contrat contient `base`, `audit_model` choisi dans le catalogue configure,
`audit_concurrency` (maximum trois), `audit_wave`, `poll_seconds` et `films`.
Chaque film contient `key`, `project_id`, `directory`, `project_root`, `style_root`,
`stages`, `expected`, `timings`, `script_sha256`, `voice_sha256` et les chemins et
empreintes des deux fichiers de rendu. Un plan non encore ecrit peut porter
`frozen: false` : il attend l'auteur et ne peut jamais etre genere ou rendu par
ce superviseur. Les risques supplementaires de l'auteur doivent etre explicitement
normalises vers une revue directe, pas supprimes silencieusement.

Etat global : `continuous-status.json`. Par film : `continuous-qc/status.json`,
`selected.json` et `evidence/report.json`. Les recus caches conservent les vrais
pixels controles, leur contexte et leur attribution. Ces donnees restent hors Git.

Tests sans API ni traitement media : `production_watch_tests.py` et
`visual_audit_tests.py`. Le controle porte notamment sur les sources changees,
les risques au bureau, les rejets, la pause, les reprises et l'absence de double
appel sur une preuve deja enregistree.
