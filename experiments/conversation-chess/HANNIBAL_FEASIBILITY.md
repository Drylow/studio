# Hannibal — faisabilité du format chess

## État actuel — test autorisé, source indisponible

L’utilisateur autorise un aperçu d’environ **deux minutes**, puis son propre
upload privé YouTube avant de décider d’un long de dix à quinze minutes.
Il approuve explicitement le pion « Oui, utilise ce pion », construit à partir
d’une photo officielle de Mads Mikkelsen :
[PNG approuvé](assets/hannibal/hannibal-pawn-approved-2026-10-11.png) et
[reçu JSON](assets/hannibal/hannibal-pawn-approved-2026-10-11.json).
SHA256 PNG vérifié : `2286f6aeb2aaaa41be196efe6741dc33b218bc0bb8ec822d67479ef02decc51d`.
Cette approbation visuelle n’établit pas de droits de réutilisation et
**n’autorise pas le lancement automatique d’un long**.

**S02E08 : `source_not_ready`.** L’accès hors ligne gratuit de Naka est obtenu ;
le manifest répond 200 et annonce 720p, maximum disponible 720p, audio anglais.
Le premier segment média renvoie pourtant HTTP 403, page de blocage fournisseur
Cloudflare, sans redirection. Zéro segment téléchargé, aucun fichier vidéo ni
profil natif vérifié, aucun alignement possible sur l’audio anglais. Le VTT
français reste un repère textuel, pas un alignement validé. Seul l’emplacement
hors ligne du Peaky S02E06 abandonné a été remplacé ; tous les fichiers locaux
antérieurs sont conservés.

NBC refuse l’accès (403), YouTube est refusé par le proxy. Les métadonnées du
clip public AXN sur Dailymotion répondent 200, mais sa playlist 403 : aucune
alternative HD vérifiée. Le diagnostic privé est conservé dans
`output/conversation-chess/hannibal-source-cache/naka-s02e08/SOURCE_NOT_READY_SAFE.json`.
Les URL de médias et identifiants de compte ne figurent pas dans ce document.

Le pion approuvé, quatre annotations en brouillon non alignées et le kit texte
sont conservés ; la chaîne d’export native est prête. Aucun film acquis,
exporté ou livré, aucun test YouTube effectué. Le futur test privé de deux
minutes doit précéder toute décision de long de dix à quinze minutes.
Son résultat ne garantira ni l’absence de nouvelles réclamations ni le
résultat d’un autre montage. Aucun droit de réutilisation établi.

## Recherche initiale conservée

Les sections suivantes décrivent la recherche avant production. La proposition
initiale de trois à quatre minutes est remplacée par le test de deux minutes
autorisé ci-dessus ; aucun long n’est encore engagé.

Recherche initiale du 11 octobre 2026. L’utilisateur confirme la **série avec Mads
Mikkelsen**, pas les films avec Anthony Hopkins. Peaky est abandonné après
le nouveau blocage territorial. Pendant cette recherche initiale, aucun épisode
Hannibal téléchargé, aucun pion créé, montage lancé ou test YouTube effectué.

## Conclusion

**Hannibal–Will convient très bien à l’analyse des dialogues. Aucune preuve
vérifiée ne permet de dire que ses extraits passeront mieux Content ID.**
La présence de vidéos chez d’autres créateurs ne révèle ni leurs licences,
ni leurs réclamations, ni leurs revenus ou les pays où elles sont bloquées.
La recherche n’a pas établi de fréquence fiable des réclamations Hannibal.

La [fiche officielle Gaumont de la saison 1](https://www.gaumont.com/en/series/hannibal-season-1)
nomme les acteurs et porte la mention technique exacte :
« Copyright © 2013 Chiswick Productions LLC. All Rights Reserved. »
Le [rapport Gaumont 2014](https://www.gaumont.com/sites/com/files/finance/2/2015/312832_GAU2014_DRF_EN_VMEL.pdf),
p. 11 imprimée, documente notamment la vente de la saison 2 à NBC aux États-Unis.
Ces sources établissent une exploitation commerciale protégée ; elles ne
donnent pas le demandeur Content ID actuel ou sa politique par territoire.
Aucune licence gratuite de réutilisation monétisée n’a été établie ici.

[YouTube explique](https://support.google.com/youtube/answer/6013276?hl=en)
que le titulaire peut bloquer, monétiser ou suivre une vidéo revendiquée,
avec des choix différents selon les pays. Une réclamation Content ID n’est
pas un avertissement pour atteinte aux droits d’auteur. Aucun ratio d’analyse,
durée d’extrait, icône, recadrage ou habillage ne garantit l’absence de claim.

## Proposition éditoriale

Titre clair : **Hannibal Lecter vs Will Graham | Analyzed Like Chess**.
Angle recommandé : le double jeu de Will dans la saison 2, lorsque chacun
teste les intentions de l’autre et feint une réconciliation.

| Épisode | Échange utilisable | Intérêt pour l’analyse |
| --- | --- | --- |
| S02E08, *Su-Zakana* | Retour de Will en thérapie | Fixer les règles, cacher ses intentions |
| S02E10, *Naka-Choko* | Cuisine et dîner | Tester la crédibilité du changement de Will |
| S02E11, *Kō No Mono* | Abigail, paternité et culpabilité | Manipulation émotionnelle |
| S02E12, *Tome-Wan* | Mason, isolement de Will et proposition concernant Jack | Piège et négociation d’alliance |

Dialogues et ordre consultés dans les [transcriptions publiques](https://www.springfieldspringfield.co.uk/episode_scripts.php?tv-show=hannibal)
de ces épisodes ; numérotation et contexte corroborés par
[TVMaze](https://api.tvmaze.com/singlesearch/shows?q=Hannibal&embed=episodes).
Il s’agit d’une lecture des transcriptions, pas d’un visionnage des épisodes.
Les conversations distinctes doivent rester identifiables ; ne pas les
assembler comme une seule scène ni ajouter des passages graphiques pour
allonger le film. Le contexte s’explique avec nos propres cartes.

**Cible : 10–12 minutes**, avec plusieurs échanges et des analyses utiles.
Cette durée n’est pas mesurée : les transcriptions n’ont pas de timecodes.
Relever les scènes avant de promettre la durée ou le nombre d’annotations.

## Prochaine vérification utile

Préparer d’abord un aperçu représentatif de 3–4 minutes autour du retour
en thérapie de S02E08, avec le véritable habillage prévu. Le pion Hannibal
doit être montré à l’utilisateur avant montage, comme pour les précédents.
Un upload privé peut révéler un blocage sur **ce fichier exact** avant de
consacrer du temps au long. Il ne valide pas les autres épisodes ni un
futur export de dix minutes : vérifier aussi le fichier final complet.

Consigner chaque demandeur, les passages détectés, la liste des territoires
bloqués et l’effet annoncé sur les revenus. Un résultat favorable reste
provisoire et ne vaut pas licence. Aucun contrôle ni droit de réutilisation
n’est acquis à ce stade ; ne pas lancer automatiquement un long ou une livraison.

Les preuves de recherche locales restent sous
`output/conversation-chess/hannibal-feasibility/` (ignoré par Git).
Les recherches généralistes ont rencontré des pages de vérification ou des
résultats non pertinents ; elles ne permettent pas d’affirmer une absence de
plaintes. Les sources officielles et les transcriptions citées ont été lues.
