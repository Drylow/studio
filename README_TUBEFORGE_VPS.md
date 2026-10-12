# TubeForge partagé sur VPS2

Point d'entrée de l'instance hébergée : **https://tubeforge.13-140-129-97.sslip.io/**.
Les identifiants privés sont transmis au propriétaire dans un fichier local, jamais dans Git.

L'application complète est dans Git : `production/tubeforge_base/` et
`production/tubeforge_support/`. Ni le Dockerfile ni l'installation PC ne nécessitent
un ZIP privé. Lire [le guide complet](README_SURVIVOR_TUBEFORGE.md).

## Organisation du serveur

- Conteneur indépendant `drylow-tubeforge`, réseau Docker `coolify`.
- HTTPS/redirect HTTP via le Traefik déjà présent ; aucun nouveau port hôte public.
- Application avec un seul processus web : les jobs et verrous restent cohérents.
- Rendu natif FFmpeg sur CPU, quatre processus de rendu, un rendu à la fois.
  Plafond du conteneur : six CPU, 12 Go de RAM. Pas d'OVNI GPU sur ce VPS.
- `/opt/tubeforge/data/` : styles, chaînes, projets, références, images, voix et rendus persistants.
- `/opt/tubeforge/config/app.env` : réglages privés modifiables par le propriétaire dans TubeForge.
- `/opt/tubeforge/config/studio.env` : clés privées du pont vocal/CLI, à administrer sur le serveur.
- `/opt/tubeforge/config/users.json` : identités et empreintes de mots de passe, accessibles au conteneur.
- `/opt/tubeforge/compose.env` : domaine et version de l'image utilisée.
- `/opt/tubeforge/repository/` : clone de Git ; `/opt/tubeforge/releases/` : versions immuables pour les updates.
- `/opt/tubeforge/backups/` : manifeste de migration et sauvegardes privées avant mises à jour.

Les fichiers GPU intermédiaires `render/studio/` de l'ancien PC ne sont pas migrés :
ils faisaient doublon avec les MP4 finaux. Ils restent conservés sur le PC. Les médias
retenus sont transférés avec contrôle SHA256. La migration ne réécrit ni narration,
ni prompts, ni images ; elle adapte les chemins de fichiers et le moteur des futurs rendus.
Le PC conserve sa copie, mais les nouvelles productions doivent se faire sur le VPS :
aucune synchronisation bidirectionnelle n'est activée entre les deux installations.
Le raccourci bureau utilise `work/tubeforge-host.json` lorsqu'il est présent.
Pour ouvrir volontairement l'archive locale : `production/tubeforge_desktop.ps1 -Local`.

Le casting Survivor livré dans les presets est complété lors de la migration
uniquement pour les identités manquantes : Mara côté zombies, Mara/Surveyor/Worker
côté aliens. Les identités déjà modifiées par le propriétaire sont conservées.

## Accès des workers

Le navigateur demande un nom et un mot de passe à l'ouverture. Chaque worker peut
avoir son propre accès ; il retrouve les mêmes chaînes, styles et projets que les
autres. C'est un **workspace partagé**, sans séparation des données par worker.
Les comptes worker peuvent produire et modifier les styles ; seuls les comptes
admin peuvent modifier les connexions API dans Réglages.

Depuis une session SSH interactive sur le VPS :

```bash
python3 /opt/tubeforge/repository/production/tubeforge_host/users.py add alice --role worker
python3 /opt/tubeforge/repository/production/tubeforge_host/users.py list
python3 /opt/tubeforge/repository/production/tubeforge_host/users.py remove alice
```

Le mot de passe est demandé sans l'afficher. Le changement est pris en compte sans
redémarrage ; un compte révoqué perd aussi son accès en cache. Ne pas partager le
compte admin avec les workers. Ne pas leur distribuer les clés des fournisseurs.

## Mises à jour

Modifier et pousser les sources, puis depuis SSH :

```bash
bash /opt/tubeforge/repository/production/tubeforge_host/update.sh
```

Le script récupère `main`, construit une version séparée, refuse d'interrompre des
jobs actifs, sauvegarde données/configuration et remplace uniquement TubeForge.
Il conserve les styles modifiés dans l'interface et les médias existants. Les
presets publics zombies/aliens restent modifiables sous `production/tubeforge_presets/`.
Une sauvegarde ne déclenche aucune génération ni publication.

Après une update, vérifier la connexion, les aperçus, la voix et un petit rendu.
Pour revenir à l'image précédente, reprendre `TUBEFORGE_IMAGE` dans le fichier
`backups/compose-*.env` correspondant, puis relancer uniquement le service TubeForge
avec la même commande Docker Compose. Ne pas restaurer les données par-dessus des
nouvelles productions sans avoir vérifié et conservé celles-ci.

Les conteneurs Coolify, AvatarForge, les autres applications et leurs volumes ne
sont pas modifiés par ce déploiement. Ne pas exposer directement le port 8766,
retirer l'authentification ou lancer plusieurs processus web avec ce store JSON.
