# Assets originaux — Depths After Dark

La nouvelle direction illustrée a été choisie après l’abandon explicite des
contraintes 3D. Aucun asset d’un jeu, clip de série ou photo tierce n’est repris.
L’avatar validé est conservé sans changement ; un dérivé avec transparence est
utilisé dans le film. Le récif et ce sprite sont préparés une fois, puis l’eau,
le cadrage et la vie marine sont animés localement en Canvas2D.

## Fichiers sources

| Source | Dimensions | Mode | Octets | SHA-256 |
| --- | --- | --- | --- | --- |
| `assets/nocturnal-reef.png` | 1672×941 | RGB | 2925767 | `454b29694cbe00e405ade9e8212e0b2ca81be72e0a2c68a435a289afbdcb59e0` |
| `assets/jellyfish-cutout.png` | 1254×1254 | RGBA | 1733776 | `65903207e99cca4a3bb62857a818b5e819ae0304bfc36b5954487bc5835648c4` |
| `branding/profile-jellyfish.png` | 1254×1254 | RGB | 2067313 | `43fd52076870e8b3f068c22f60dd132fb7422a0ecc129a2b7284de1533e1c120` |

- **Récif** : illustration originale de canyon marin nocturne, coraux détaillés,
  ouverture centrale calme. Source 1672×941 incorporée byte pour byte ; le
  rendu 1920×1080 l’agrandit légèrement. Pas une source 4K/1080p native.
- **Sprite** : dérivé original de la méduse de l’avatar, fond réellement
  transparent. Animation de la cloche et des tissus calculée par code.
- **Avatar** : illustration générée originale, validée par l’utilisateur le
  10 octobre 2026. Ce fichier ne change pas pour intégrer le sprite à la vidéo.

Créations d’assets pour le film : 2 appels (récif et détourage), avant rendu.
Création du profil : 1 appel séparé. Ce sont des images originales préparées
avec l’outil d’image de la session ; ne pas déclarer zéro image générée.
Aucun appel à Algrow, aucun générateur vidéo, aucun appel réseau par le lecteur,
et aucune génération supplémentaire pour les 9 000 images ou les 24 répétitions
prévues. Aucun montant facturé par l’outil de session n’est calculé ici.

## Reproductibilité et portée

`build.mjs` incorpore les deux PNG dans le JavaScript, sans requête distante.
Les empreintes du build et des sources sont comparées par
`verify-illustrated-loop.mjs`. Le MP4 et le HTML utilisent ce même build.
L’illustration sert à l’ambiance ; elle n’est pas présentée comme une image
scientifique ou une prise de vue réelle. Le récit futur doit être sourcé
indépendamment. La validation de l’avatar ne vaut pas validation du fond vidéo.
