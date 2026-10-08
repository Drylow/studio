# Crazy Chef 3D

- Nom : **Crazy Chef 3D**
- Handle : **@CrazyChef3D**
- Description proposée : **Cute chef. Terrible ideas. Delicious destruction. 🍉💥**
- Plateformes : TikTok et YouTube Shorts.
- Identité : cuistot souriant en toque et veste blanches, moustache, clin d'œil,
  spatule ; pixel art crème et vert forêt, aliments très lisibles, humour absurde.
- Contenu : destruction cartoon de nourriture, bruitages synchronisés et montée
  en puissance des outils. Les prochains films visent plus d'une minute.

## Livraison autorisée par l'utilisateur

Pour chaque nouvelle vidéo terminée et vérifiée image par image : exporter le
MP4 final, préparer sa cover verticale 9:16 en pixel art, puis envoyer son lien
GoFile, la cover, son titre et sa description au salon Discord de cette chaîne.
Pas de nouvel accord nécessaire pour cet envoi. La publication sur les comptes
TikTok et YouTube reste manuelle, depuis le téléphone de l'utilisateur.

La destination est uniquement `DISCORD_WEBHOOK_CRAZY_CHEF_3D` dans le `.env`
ignoré du dépôt. Ne jamais recopier l'URL dans les sources ou les journaux.
Ne pas utiliser le webhook d'une autre chaîne en remplacement.

`videos.json` référence uniquement les versions finales validées, avec leur
empreinte SHA-256 et leur rapport QA. Ajouter une nouvelle entrée après revue,
jamais par simple détection d'un nouveau MP4. Covers sous `covers/`, logo sous
`brand/`. Les textes courts pour la publication sont en anglais.

```powershell
python production/crazy_chef_delivery.py --dry-run
python production/crazy_chef_delivery.py
```

Le script contrôle les empreintes avant upload, compare les MD5 renvoyés par
GoFile, conserve ses reçus sous `work/crazy-chef-delivery/` et évite de renvoyer
un paquet déjà confirmé. Un résultat incertain de l'envoi Discord est conservé
comme tel et ne déclenche pas de seconde publication automatique.

Les trois vidéos et le kit mobile (logo, covers, nom, handle, bio et textes)
sont présentés ensemble dans un seul message Discord avec les images jointes.
Le kit est également téléchargeable sur GoFile.

[Dernière livraison et liens](DELIVERY.md) · [Covers et prompts](covers/README.md).
