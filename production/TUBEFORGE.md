# TubeForge local - 10 octobre 2026

Installation privee : `work/TubeForge`, extraite du ZIP fourni par l'utilisateur.
Archive figee : SHA-256
`a1c870ff57bc0adba8d34a8c851379f4bb8d42d1c9fd5a8d5f90f07791aacd16`.
Le ZIP, son code, ses donnees, ses medias et ses secrets ne sont pas publies.

## Utilisation

Serveur : http://127.0.0.1:8766 (uniquement sur ce PC).
Le port 8765 est deja utilise par une autre application, conservee intacte.

Depuis la racine du studio, dans PowerShell :

```powershell
./production/tubeforge.ps1 -Action Start
./production/tubeforge.ps1 -Action Status
./production/tubeforge.ps1 -Action Stop
```

Arreter les taches actives dans TubeForge avant d'arreter le serveur.
`work/TubeForge/start.bat` utilise aussi le nouvel environnement isole.
Pas de service Windows, de tache programmee ni d'exposition reseau ajoutes.

## Interface simplifiee

Navigation : Videos, Chaines, Reglages. Nouvelle video rassemble le titre,
la chaine, la duree cible, le script colle ou importe (.txt/.md UTF-8, 1 Mo max),
le style visuel avec apercu et les deux modeles de generation.
Seuls les styles existants non archives sont proposes ; POV style est le preset
commun prepare. Un choix visuel ne remplace jamais la voix Algrow de la chaine.
Le script importe reste exact. Creation et lots ne lancent aucune production.
Chaque projet conserve ses reglages de style et son choix de modeles.
Le titre peut ensuite etre modifie sans reecriture du texte ni des prompts.

Les modeles viennent du catalogue reel du CLI Proxy. Les capacites annoncees
et les capacites non confirmees sont distinguees ; la presence dans la liste
ne prouve pas qu'une generation reussira avec un compte donne.
Les modeles de texte et d'image peuvent etre choisis avant creation, sans IDs
de modeles figes dans le depot et sans changement de fournisseur.

Les cinq profils separent les apercus video (personnages blancs) des miniatures
(humains expressifs). Les anciens presets sont conserves en archives privees.
Les captures de reference presentes datent du 30 septembre au 2 octobre ;
les nouvelles captures de l'utilisateur restent attendues.

Parcours : Texte, Voix, Images, Verification, Export. Chaque plan montre
sa narration, son lieu, son casting, son prompt exact et ses references ordonnees.
Refaire un plan demande de confirmer ce prompt et le modele enregistre ;
aucune nouvelle reference, reecriture ou correction automatique n'est appliquee.
Les versions precedentes sont conservees. Une image nouvelle redevient a verifier.
Un rendu disponible ne signifie jamais valide pour publication.

Mettre a jour l'interface sans reconfigurer les fournisseurs (serveur inactif) :

```powershell
./venv/Scripts/python.exe production/tubeforge_workspace.py
```

Tests sans requete de generation payante :

```powershell
./work/TubeForge/.venv/Scripts/python.exe -m pytest work/TubeForge/tests production/test_tubeforge_workspace.py -q
node production/tubeforge_support/workspace_ui_tests.cjs
```

## Voix et generation

Algrow est le fournisseur par defaut, avec la voix historique existante.
Aucun moteur de voix locale n'a ete installe. Aucune voix de chaine remplacee.
Les cles sont chargees depuis les configurations privees ; la cle Algrow reste
dans le `.env` du studio, pas dans les requetes JSON de la passerelle.
Le proxy texte/images reprend la configuration du studio.
Algrow impose 200 caracteres minimum : un texte trop court est refuse, jamais
complete automatiquement. Le bouton d'apercu utilise un exemple assez long.
Les narrations de projet identiques sont mises en cache avec controle d'empreinte.

## Rendu

`auto` utilise OVNI pour les videos sans sous-titres incrustes ni habillage TikTok.
Un rendu OVNI utilise le runtime NVIDIA isole deja installe dans le studio.
Le decoupage est repris de TubeForge a 24 images/seconde, cale sur la voix reelle.
Les sous-titres SRT sont exportes separement, pas perdus.
Les titres/captions/TikTok restent au moteur natif : aucun habillage n'est
silencieusement supprime. OVNI force avec ces options est refuse explicitement.
Une panne GPU ne declenche pas de remplacement silencieux par le CPU.
FFmpeg reste utilise pour l'audio, le MP4 et les controles, pas pour les images
animees du rendu OVNI. DaVinci est optionnel, pas necessaire a l'export MP4.

Six projets peuvent etre traites dans une instance, un seul rendu a la fois.
Le CSV accepte `provider=algrow`. Le lanceur batch attend la fin et signale
les erreurs. Ne pas lancer simultanement plusieurs instances CLI et web pour
produire sur le meme GPU : le verrou de rendu est propre a chaque instance.

## Production dirigee

La configuration creative livree dans le ZIP est un exemple, PAS la direction
validee pour nos cinq chaines. Aucun script ou prompt historique n'a ete genere
automatiquement pendant cette installation.
Les projets `codex_directed` attendent le contenu ecrit et verifie par Codex.
Les etapes automatiques de reecriture, voix/decoupage, personnages, prompts et
images sont bloquees sur ces imports. La passerelle ne choisit aucune reference.
L'import d'extrait verifie les empreintes des images et des references, conserve
le transcript exact, la timeline et les recus, sans remplacer les originaux.
Les corrections creatives restent dans la production dirigee par Codex.
Un export technique reste non publiable tant que la relecture n'est pas faite.

## Verification effectuee

- Appel reel au proxy texte : OK.
- Appel reel au proxy image avec prompt existant et deux references ordonnees : OK.
  Test isole dans `data/api-check/`, pas ajoute a l'episode. Image regardee ; ce
  test technique ne constitue pas une approbation creative de remplacement.
- Apercu Algrow reel : 16,57 secondes, lu et mesure techniquement, pas d'ecoute revendiquee.
- Deux exports complets en file sur le meme extrait Edo : 36 plans, 180,62 s de voix,
  1920 x 1080 a 24 i/s, 4335 images video. Les cinq films complets ne sont PAS termines.
- Rendu natif : 122 s ; OVNI : 25,00 s hors attente de file et demarrage de passerelle.
  Environ 4,9 fois plus rapide sur ce test. Reglages differents : natif CRF 20,
  OVNI debit cible 12 Mbit/s ; courbes de camera differentes. Ce n'est pas une
  comparaison a qualite identique ni un benchmark contre DaVinci.
- Arret reel d'un rendu : tache stoppee, aucun worker GPU restant.
- Rendu OVNI du comparatif decode integralement, horloges audio/video verifiees,
  108 captures sur six planches regardees : pas de corruption noire ni marge vide.
  Reserve creative existante : orientation du noeud du bandeau entre les deux
  premiers plans. Aucune coherence parfaite ni ecoute de voix revendiquee.
- 20 tests TubeForge passent ; 59 tests studio passent, un test GPU optionnel
  ignore. L'export GPU reel ci-dessus a bien ete execute.
- Reconstruction du code depuis le ZIP verifiee ; `pip check` sans erreur.

Recus et rendus du comparatif : `work/TubeForge/data/benchmark.json`.
Controle technique et captures : sous-dossier `render/check/` du projet OVNI.
Les projets de benchmark sont archives pour ne pas encombrer la liste active.

## Reinstallation

Necessite le ZIP prive et le studio avec ses dependances et runtime OVNI existants.
Ne pas executer les anciens installateurs de voix locale du ZIP.

```powershell
./venv/Scripts/python.exe production/tubeforge_install.py C:/Users/ytbyt/Downloads/TubeForge.zip
```

L'installation refuse un dossier existant et une archive d'une autre version.
`tubeforge_support/vendor.patch` ne contient que les modifications techniques.
Les ajouts de voix UI sont deployes par `voice_ui.json`, sans reprendre les
anciens choix de modele. Les dependances testees sont figees dans `requirements.lock`.
`tubeforge_configure.py` est un outil de configuration initiale : le relancer
reapplique les voix/modeles/paralleles du studio aux styles et chaines TubeForge.
Il n'est pas execute par le serveur a chaque demarrage.
