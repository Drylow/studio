# Verification Windows — 9 octobre 2026

Ce rapport decrit le premier extrait historique. La version complete corrigee,
avec pion neutre et pause retardee apres « opinion », est documentee dans
`VALIDATION_ANIME_COMPLETE.md` ; les constats ci-dessous concernent l'ancien test.

L'outil du collegue a ete execute sur Windows, sans changer `scene.js`,
les traces SVG ou les deux images de pion. La preparation Node et l'export
Kdenlive26.08.1/MLT ont reellement produit un extrait Code Geass en anglais.

- Video :1289frames,1920x1080,30fps,42.9667s ; conteneur42.986s avec audioAAC.
- Export : H264CRF17/preset medium, AAC192kb/s,48kHz stereo, confirmes dans
  le jobMLT conserve. La premiere tentative avait repris CRF23 : elle est
  remplacee par l'export dont le vrai profil est controle.
- Decodage integral video/audio sans erreur. True peak -4.9dBFS ; -21.6LUFS.
- Les1289frames figurent sans saut dans13planches examinees. Huit images
  natives supplementaires verifient guide, dialogue, entree du pion/bulle,
  frappe, texte complet et reprise. Pas d'ecoute humaine revendiquee.
- Setup Windows et diagnostic passes. Trois tests passent : octets exacts
  des SVG apres checkout, chemins absolus Windows pour les SFX, blocage d'une
  source insuffisante et d'un premier locuteur non revu.

Le clip original reste1280x720. L'aperçu est marque comme tel ; les nouveaux
exports finaux exigent une source au moins1080p acceptee apres examen.
Le pion Tony du collegue est conserve dans ce test. Aucun avatar anime,
bilan anime ou montage complet des cinq annotations n'est annonce valide.
La parite pixel par pixel avec la chaine de reference n'a pas ete mesuree.

Le dossier local de preuve est `work/conversation-chess/preview/review/` ;
le projet natif et les medias sont dans `work/conversation-chess/preview/kdenlive/`.
Ces fichiers lourds restent hors Git. Empreinte du MP4 retenu :
`a980a1f4573292ac36652ac837ee514d5848865803782dbe0d880f359d4bc284`.
