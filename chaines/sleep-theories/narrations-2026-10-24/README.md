# Dix narrations livrees et controlees — 25 octobre 2026

Les **10 MP3 complets** sont recuperes : **5 Deep Void Theories + 5 Quiet Paradox**. La fin manquante de Silo est corrigee dans le fichier final. Voix **Mellow Matt**, ID `IsEXLHzSvLH9UMB6SLHj`, vitesse **0,90**. Forgotten Realms ne fait pas partie de ce lot.

Dossier de livraison : `C:/Users/ytbyt/Desktop/Voix sleep - 24 octobre 2026`. Le detail des empreintes, tailles et durees est dans `suivi.json` et dans `CONTROLES.json` sur le Bureau.

| Episode | Duree | Fichier |
|---|---:|---|
| DV-08-bene-gesserit | 4:10:25 | 01-DV-08-bene-gesserit.mp3 |
| DV-09-jedi-order | 4:23:30 | 02-DV-09-jedi-order.mp3 |
| DV-10-fremen | 3:40:47 | 03-DV-10-fremen.mp3 |
| DV-11-old-republic | 4:08:11 | 04-DV-11-old-republic.mp3 |
| DV-12-great-houses | 4:10:51 | 05-DV-12-great-houses.mp3 |
| QP-07-silo-builders | 3:56:26 | 06-QP-07-silo-builders.mp3 |
| QP-08-from-rules | 3:48:15 | 07-QP-08-from-rules.mp3 |
| QP-09-lumon-building | 4:25:39 | 08-QP-09-lumon-building.mp3 |
| QP-10-silo-outside | 4:04:36 | 09-QP-10-silo-outside.mp3 |
| QP-11-from-cycles | 4:03:20 | 10-QP-11-from-cycles.mp3 |

## Controles et limites

Les dix fichiers finaux et leurs 25 blocs sources ont des empreintes conformes. Le decodage integral des MP3 est valide. Les decoupages couvrent les textes approuves sans trou ni chevauchement. Les debuts et fins de chaque bloc ont ete confrontes au script par reconnaissance vocale locale ; les deux raccords de la correction Silo ont ete controles dans le MP3 assemble. Aucun blocage reste ouvert.

Ces controles portent sur les fichiers et des passages cibles. Ils ne constituent pas une transcription mot a mot ni une ecoute humaine de toutes les narrations. Les rapports detailles restent prives dans `work/sleep-voiceovers-2026-10-24/`.

## Corrections terminees

- DV-12 Great Houses : le deuxieme gros bloc avait echoue. Il a ete remplace par quatre blocs contigus, tous recuperes et verifies.
- QP-10 Silo Outside : un job marque termine avait pourtant coupe avant la fin. La reprise utilise exactement les **29 377 derniers caracteres**, depuis le debut de la phrase interrompue. L ancien second bloc a ete coupe dans un silence a 4 750,490 secondes, puis les deux nouvelles parties ont ete ajoutees. Le fichier corrige dure **4:04:36**. Les premiers fichiers et le registre precedent sont conserves en archives privees.

## Reprise

Aucune nouvelle generation necessaire. Ne pas relancer `submit`. L executeur `production/sleep_silo_repair.py` conserve les etapes plan, submit, monitor, assemble et finalize ; la finalisation exige le rapport independant de raccord et une empreinte conforme. Les identifiants des jobs et les URL restent dans les registres prives, jamais dans Git. La cle reste dans le `.env` prive.

Les dix voix seules sont livrees : aucune nouvelle video, publication ou programmation YouTube n a ete lancee. La surveillance de fin est arretee apres cette livraison.
