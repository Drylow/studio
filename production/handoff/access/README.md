# Accès personnel TubeForge : reprise privée

Le dépôt est public. Le fichier `tubeforge-personal-access.aesgcm` conserve les
**cinq fichiers originaux transmis par l'utilisateur**, sans modifier leurs
octets, dans un coffre chiffré et authentifié AES-256-GCM :

- `ssh.zip` : les clés SSH et fichiers associés fournis ;
- `TUBEFORGE_API_HANDOFF.md` : la documentation complète et l'accès personnel ;
- `LLM.txt` : les instructions du fournisseur ;
- `endpoints.json` : le catalogue des routes ;
- `forge.py` : le CLI original.

La clé de déchiffrement n'est ni dans Git ni dans ce dossier. Elle reste dans un
fichier privé séparé, à transmettre au prochain opérateur par un canal privé.
Le mode **`--key-file` est testé et disponible** ; l'utilisateur reçoit le lien
privé de ce fichier avec la passation. Ne jamais ajouter cette clé au dépôt.

**Le mode `--via-cpanel` n'est pas activé.** Le contrôle d'approbation automatique
a refusé le transfert externe de la clé faute d'accord explicite pour cette
destination. Aucune clé n'a été envoyée à cPanel. Ce mode est conservé comme
option ; il ne fonctionnera qu'après un stockage privé effectivement autorisé
et vérifié dans `~/drylow_studio/work/private-access/tubeforge-vault-key.txt`,
dossier `700`, fichier `600`, hors du site public.
Les identifiants cPanel existants restent fournis par l'environnement ou le
`.env` ignoré par Git. Aucune copie de ces identifiants n'est dans le coffre.

## Reprendre depuis une nouvelle session

Utiliser Python 3.10+ sur Linux/cloud avec `cryptography` installé :

```bash
python -m pip install 'cryptography>=42,<51'
python production/handoff/access/restore_access.py \
  --key-file /chemin/prive/tubeforge-vault-key.txt \
  --output /workspace/tubeforge-personal-access
```

Cette commande déchiffre localement le coffre, ne fait aucun appel réseau et
n'affiche aucune clé. Le support des permissions et écritures avec descripteurs
a été testé sur Linux. Le futur mode `--via-cpanel` utilisera uniquement le
téléchargement privé de `production/cpanel.py`, sans déploiement ni shell ; son
contrat a été testé avec un transport simulé, pas avec une clé réellement déposée.

Si la clé est déjà disponible dans un fichier privé hors du dépôt :

```bash
python production/handoff/access/decrypt_access.py \
  --key-file /chemin/prive/tubeforge-vault-key.txt \
  --output /workspace/tubeforge-personal-access
```

Une variable d'environnement privée `HANDOFF_VAULT_KEY` est aussi acceptée. Pour
un `.env` privé déjà renseigné, ajouter `--env-file .env`. Le lecteur ne charge
que cette variable et n'exécute jamais le fichier. Le format de la clé est
explicitement `hex:` suivi de 64 caractères hexadécimaux ou `base64:` suivi du
codage des 32 octets. Ne jamais passer sa valeur dans un argument de commande,
la coller dans un message ou la committer.

Les fichiers sont restaurés uniquement **hors de tout dépôt Git**, dossier
`700`, fichiers `600`. Les chemins symboliques sont refusés. Les fichiers déjà
présents ne sont jamais remplacés sans `--overwrite`. L'authentification de
l'archive et les SHA-256 de chaque original sont vérifiés **avant toute écriture
des accès**. Une mauvaise clé ou un coffre modifié ne restaure rien.

Lire ensuite les documents dans le dossier privé, sans afficher leurs secrets
dans les logs. L'accès personnel contenu dans les documents sert à ouvrir une
nouvelle session API du collaborateur ; les anciennes sessions expirables de
ce chat ne sont pas incluses. Ne pas substituer un accès propriétaire, une clé
de fournisseur ou un token de worker à cette connexion personnelle.

## Format et preuves

`manifest.json` ne contient que les noms des fichiers, leurs tailles et SHA-256,
le schéma et le SHA-256 du coffre chiffré. Le manifeste privé contenu dans le
coffre conserve aussi l'origine des cinq pièces jointes. L'enveloppe binaire
contient la signature de format versionnée, un nonce aléatoire de 12 octets et
le résultat AES-GCM (tag de 16 octets inclus). La signature et le contexte de
format sont également authentifiés. Chaque création utilise une nouvelle clé
aléatoire de 256 bits et un nouveau nonce ; ne jamais réutiliser un nonce avec
la même clé.

Le rapport `verification.json` décrit les contrôles réellement exécutés sans
inclure de valeur d'accès. Les seules copies en clair sont les originaux privés
transmis par l'utilisateur et les dossiers de restauration explicitement
choisis ; ils ne doivent jamais être ajoutés au dépôt public.
