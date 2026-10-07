# Production 2D historique dirigee par Codex

Lire CLAUDE.md pour les regles generales du depot. Ne pas annuler les modifications
existantes ni changer le frontend pour produire le contenu.

Pour Edo Daily, Aztec Daily, Babylon Daily, Imperial China Daily et Ottoman Daily :
- L'utilisateur demande que Codex ecrive lui-meme les scripts, decoupages et prompts.
  Ne pas deleguer le prompting a la generation automatique de la pipeline.
- Le style approuve est celui des cinq images background-v3 du 6 octobre 2026 :
  personnages adultes a tete ronde blanche, mains blanches en moufles, corps couverts,
  bouches neutres ; decors 2D colores avec textures et profondeur moderees.
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
