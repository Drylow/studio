# Production 2D historique dirigee par Codex

Lire CLAUDE.md pour les regles generales du depot. Ne pas annuler les modifications
existantes ni changer le frontend pour produire le contenu.

Pour Edo Daily, Aztec Daily, Babylon Daily, Imperial China Daily et Ottoman Daily :
- L'utilisateur demande que Codex ecrive lui-meme les scripts, decoupages et prompts.
  Ne pas deleguer le prompting a la generation automatique de la pipeline.
- Decision finale du 7 octobre : VIDEOS = decors BD sobres (option 1 du
  comparatif), lignes nettes, aplats mats, textures reduites et ombres simples.
  Garder une architecture detaillee et lisible, sans decor excessivement simplifie.
  PERSONNAGES = adultes a tete ronde blanche, petits yeux noirs, bouche neutre,
  mains blanches en moufles et corps couverts, comme les references du 6 octobre.
- Exception explicite du 7 octobre : pour les MINIATURES seulement, l'utilisateur
  veut des visages humains cartoon expressifs comme la miniature NO JOBS de Rome
  Unscrolled. Cette direction ne change PAS les personnages blancs des videos.
  Conserver les premieres propositions blanches sans les ecraser.
- Les humains testes dans les intros sont abandonnes pour les VIDEOS.
  Conserver ces essais comme archives, pas comme references de personnages.
- Le decor choisi est output/imagegen/comparatif-decors-2026-10-07/01-bd-sobre.png.
  Son personnage humain n'est PAS approuve pour les videos. Les autres variantes
  restent des essais. Adapter et verifier les maitres de chaque lieu a la BD sobre.
- Les cinq miniatures HUMAINES a regarder sont dans
  output/imagegen/miniatures-01-journee-v2-2026-10-07/A-REGARDER/.
  Direction humaine conservee ; ne pas en deduire la validation de chaque image.
- Miniatures des videos 01 : texte relie a l'angle du titre, plusieurs activites
  de la journee dans une seule scene, expressions adaptees. Ne pas recycler
  cinq vendeurs portant un produit ni affirmer NO JOBS sans preuve.
  Relire l'accroche avec le script final avant publication.
- Lire production/COHERENCE_2D_CODEX.txt avant toute production.
- Reutiliser un decor maitre verifie pour chaque lieu et les memes references de
  personnages ; une description textuelle seule ne suffit pas.
- Chaque plan doit avoir un extrait de narration, un lieu, des personnages nommes,
  un prompt ecrit par Codex et une liste ordonnee des images effectivement envoyees.
- Utiliser le CLI Proxy configure dans .env. Ne pas substituer un autre fournisseur.
- Le code ne fait que l'execution technique ; aucun script automatique ne doit
  reecrire les prompts, choisir une autre reference ou regenerer un lieu sans accord.
- Codex regarde chaque image, compare le decor aux references et corrige les ecarts
  avant montage. Ne jamais declarer une coherence parfaite uniquement sur la base
  des prompts ou des references envoyees.
- Les nouvelles vues d'un lieu et les changements de lumiere sont des variantes
  explicites, creees depuis le decor maitre, verifiees et conservees.

Le kit de references initial et le test visuel sont dans
output/imagegen/coherence-codex-2026-10-07/.
