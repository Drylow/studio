# fframes — évaluation pour cette boucle

Outil proposé par l'utilisateur le 10 octobre : [fframes.studio](https://fframes.studio/).
Le [tweet d'Ashton Chew](https://x.com/iamashtonchew/status/2108713173461160133)
annonce un export de 700 secondes réduit à moins de 21 secondes. Son matériel
n'est pas indiqué. La vidéo jointe, réellement inspectée sur une planche
complète, dure environ 81 secondes en 1080p60 : textes, ASCII, logos, chiffres
et cartes Cornell Venture Capital. Cette mesure ne décrit pas notre scène 3D.

Le [dépôt officiel](https://github.com/dmtrKovalenko/fframes) décrit un outil
local en Rust/SVG, sous [licence MIT](https://github.com/dmtrKovalenko/fframes/blob/main/LICENSE.txt),
avec rendu Skia, Metal/Vulkan et des backends CPU. Il pourrait servir aux
habillages, diagrammes et animations de texte. Aucun abonnement n'est requis
pour ce chemin local documenté ; le calcul et le matériel restent nécessaires.

Il possède de vrais [shaders 3D et un exemple de raymarching](https://github.com/dmtrKovalenko/fframes/blob/main/examples/shaders/src/shaders.rs).
Cela ne constitue pas un import direct des meshes, animations et JavaScript
Three.js de cette scène. Aucun tel adaptateur n'a été trouvé dans la
documentation examinée. Un port demanderait une réécriture ou une intégration
de séquences déjà rendues. Le rendu CPU tiny-skia et l'aperçu SVG du navigateur
n'exécutent pas ces shaders ; le rendu Skia natif le peut. Les conversions
Shadertoy ont également des limites de syntaxe documentées.

**Décision actuelle : conserver Three.js pour fabriquer et vérifier les
volumes de la boucle.** fframes reste une option pour les futurs habillages,
sans lui attribuer une accélération 3D non mesurée sur notre machine sans GPU.
Aucune installation ni conversion fframes n'est présentée comme réalisée.

Sources primaires supplémentaires :

- [Guide API](https://github.com/dmtrKovalenko/fframes/blob/main/skills/fframes-video/references/api.md).
- [Implémentation des shaders](https://github.com/dmtrKovalenko/fframes/blob/main/fframes/src/shader.rs).
- [README et exigences](https://github.com/dmtrKovalenko/fframes/blob/main/README.md#requirements).

Les pages, métadonnées X officielles et captures de cette recherche sont
conservées hors du dépôt public. Aucun média du tweet n'entre dans notre film.
