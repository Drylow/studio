# Dix narrations lancees — 24 octobre 2026

Les cinq nouveaux scripts Deep Void Theories et les cinq Quiet Paradox sont soumis a Algrow. Les vingt parties ont chacune un identifiant confirme. Forgotten Realms ne fait pas partie de ce lot.

Voix : **Mellow Matt**, ID `IsEXLHzSvLH9UMB6SLHj`, vitesse **0,90**. Offre standard habituelle, sans sous-titres payants. Les textes approuves du 22 octobre sont inchanges.

Volume du texte : **1 726 549 caracteres**, espaces et retours inclus. Solde releve avant/apres soumission : **5 093 599 → 3 367 081** (difference de **1 726 518**). Le compteur du fournisseur differe de 31 caracteres du texte local. Il ne s'agit pas d'un devis pour une nouvelle generation.

## Point de reprise — 25 octobre 2026

Neuf MP3 finaux sont recuperes : quatre Deep Void et les cinq Quiet Paradox. Leur presence, taille et SHA256 ont ete verifies. Le deuxieme bloc de DV-12-great-houses a echoue definitivement chez le fournisseur, sans audio recuperable. Son essai est conserve dans failed_attempts du registre prive. Une seule reprise manuelle a ete soumise en quatre blocs contigus plus courts (88 712 caracteres au total), avec le meme texte, la meme voix et les memes reglages. Les quatre nouveaux identifiants sont enregistres ; ne pas les repayer. Le premier bloc deja reussi est conserve.

Le moniteur a repris avec monitor-recovery.log et monitor-recovery-errors.log. Une alerte dans ce chat verifie toutes les quinze minutes et previendra lorsque les dix fichiers seront recuperes et controles ; elle doit ensuite etre desactivee. Aucun sous-titre payant ni nouvel upload n'est lance.

Les durees de certaines moities divergent ; un controle complementaire des fins audio de DV10, DV11 et QP10 est en cours. Ne pas confondre decodage valide et verification integrale du contenu parle.

## Episodes

| Episode | Chaine | Caracteres |
|---|---|---:|
| DV-08-bene-gesserit | Deep Void Theories | 170,210 |
| DV-09-jedi-order | Deep Void Theories | 179,155 |
| DV-10-fremen | Deep Void Theories | 172,822 |
| DV-11-old-republic | Deep Void Theories | 190,498 |
| DV-12-great-houses | Deep Void Theories | 177,776 |
| QP-07-silo-builders | Quiet Paradox | 162,712 |
| QP-08-from-rules | Quiet Paradox | 156,452 |
| QP-09-lumon-building | Quiet Paradox | 181,542 |
| QP-10-silo-outside | Quiet Paradox | 167,251 |
| QP-11-from-cycles | Quiet Paradox | 168,131 |

## Recuperation et reprise

Le suivi en arriere-plan recupere les vingt blocs, controle le decodage audio et assemble un MP3 par episode sans ajout de silence. Les fichiers complets arrivent dans `C:/Users/ytbyt/Desktop/Voix sleep - 24 octobre 2026`. Au moment du lancement, la generation etait encore en cours : ne pas confondre soumission et livraison terminee.

Commande de lecture du statut, depuis la racine du depot :

```powershell
python production/sleep_voiceovers_oct24.py status
```

Si le PC ou le processus s'arrete, reprendre avec cette commande (lecture, telechargement et assemblage seulement, aucun nouvel appel payant) :

```powershell
python production/sleep_voiceovers_oct24.py monitor
```

Ne pas lancer un second moniteur pendant que le premier tourne. Le verrou de processus empeche deux executeurs concurrents. Le PID et les journaux sont dans `work/sleep-voiceovers-2026-10-24/`. Le registre prive `ledger.json` contient les identifiants, empreintes, limites de decoupe et URL des medias. Ne pas publier ce registre ni la cle du `.env`.

Ne pas repayer les jobs soumis. Une reponse de soumission incertaine doit etre reconciliee avant toute nouvelle tentative. La commande `submit` ne relance jamais automatiquement une partie deja soumise.

Les controles de fichier et de duree ne constituent pas une ecoute humaine integrale. Aucune video ni publication YouTube n'est lancee par cet executeur.
