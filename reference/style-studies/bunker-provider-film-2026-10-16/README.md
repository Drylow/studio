# Même court film, deux fournisseurs visuels

Test demandé le16 octobre2026 : reprendre le style du [Bunker Survival de référence](https://www.youtube.com/watch?v=RmyjNoz2pw4) avec les deux connexions déjà présentes dans Studio. Ce test ne modifie aucun preset de chaîne ni aucune vidéo existante.

## Livré

Un récit fictif de76,61 secondes et203 mots,12 plans, une seule voix Ryan Kurk, deux versions plein écran et un comparatif synchronisé. Tous les exports sont en1920×1080 à24 images/s, sans zoom animé, avec coupes franches. Fabrication des images, montage, rendu et décodage de contrôle sur le VPS ; PC limité au pilotage et au transfert final.

Dossier de livraison local : `03 - Creation/Bunker Survival - Comparatif video/`. Son unique README contient script et timings. Les MP4 ne sont pas versés au dépôt public. Après transfert vérifié par taille et SHA-256, les exports temporaires sont retirés du serveur selon la règle du propriétaire ; les scènes, la voix, les maîtres et reçus nécessaires sont conservés.

## Comparaison contrôlée

- A : CLI Proxy configuré dans Studio.
- B : Flow/useapi configuré dans Studio.
- Mêmes prompts exacts, mêmes fichiers de référence dans le même ordre, mêmes plans et mêmes limites temporelles alignées sur la voix réelle.
- Les deux maîtres communs sont joints ici en PNG natif. Ils ont été préparés avec la connexion A : ce test compare la reproduction de ces mêmes références, pas deux processus indépendants de création de personnage.
- Les cadres source ne servent que de références artistiques et restent privés. Leur vidéo, leur timestamp et leur empreinte sont inscrits dans `visual-plan.json`. Aucun extrait de la vidéo concurrente n'entre au montage.
- Les quatre planches comparent les24 images réellement sélectionnées. La vérification décrit des résultats observés, pas une mesure statistique de qualité ou de vitesse.

## Observations

Les deux connexions peuvent reprendre le stickman fin, le visage simple, le décor sobre, les objets isolés et les schémas sur blanc. La géométrie de la pièce fonctionne après réduction des références à un maître de lieu et une identité de personnage explicitement liés. Des variations de visage, d'échelle des objets et de lumière restent visibles.

Le premier test B, plus chargé en références de style, redessinait la pièce. Ce test a été repris sur les deux connexions avec les mêmes deux références explicites. Les plans9,11 et12 ont reçu une correction commune de lumière ou d'emplacement du chiffon. Une requête A sur le premier plan a expiré après360s ; le nouvel essai explicite, avec entrées identiques, a réussi. Les variantes et reçus sont conservés dans le travail privé.

Écarts encore visibles : B place le chiffon trop loin du seuil aux plans9/11 et en change l'échelle au plan12. A respecte mieux cet accessoire, mais dessine des lumières plus nuancées que la référence sur certains inserts. Ces sorties sont utiles pour comparer ; elles ne valent pas validation de cohérence pour un épisode final destiné à publier.

## Vérification

Codex a regardé les24 sorties et les corrections, puis les planches issues des MP4. Les contrôles techniques relisent chaque vidéo, vérifient dimensions, nombre d'images, durée, ordre des plans, trois images par plan et absence de zoom. Les trois pistes audio décodées doivent être identiques. Les preuves détaillées et les reçus fournisseur restent dans `work/bunker-provider-film-2026-10-16/`, ignoré par Git ; aucun jeton, compte ou accès n'est inclus ici.

## Script original commun

Your first night in the shelter starts with something you didn't put on the checklist: a knock at the door.

You reach for the radio. One voice, any voice, would help. All you get is static.

You turn the dial again. The same hiss. Then the ceiling light goes out.

The backup battery has one green bar left. You stare at it as if disappointment might charge it.

That little box is keeping the lamp, the fan and the radio alive. Tonight, you can't keep all three.

You switch off the work lamp and take out your flashlight. The radio stays on. You're not ready for silence.

Something cold touches your shoe. A thin trail of water is creeping under the steel door.

You crouch beside it. Rainwater. For once, the explanation is less frightening than the noise.

You pull the folded cloth off the workbench and press it against the gap. The dripping slows.

The knocking comes again. You lift the flashlight. On the shelf, a metal cup rocks against a bottle.

You move the cup. Finally, quiet. Then a burst of music crackles out of the radio.

You sit down, smiling. One dry corner, one working radio. For tonight, that's enough.
