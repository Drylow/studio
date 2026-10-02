# Oddly Expensive Lives (@OddlyExpensiveLives)

## Concept

« The Economics of … ». Un prof (le personnage présentateur) explique **la facture complète** d'un moment de vie, ligne par ligne.

- **Fil rouge** : un ticket de caisse (« running tab ») qui s'allonge à l'écran.
- **Le cas suivi** : un seul cas typique, du début à la fin (par exemple un divorce avec deux enfants, une maison et un 401(k)).
- **Le total final** : il devient le chiffre de la miniature.
- **Modèle dans le code** : `oddly_expensive_en` (format `economics_of`).
  - Mise en page « tableau » : le prof sur le côté, le panneau d'images et d'animations à droite.
  - Réalisateur de montage automatique : compteurs, tickets, listes, barres, tampons.
- **Vidéo de référence** pour la façon de faire : style Marcus (`kY-3P95Ua9Q`, « Gray Economy », « Never Retiring »).

## Style

- **Images** : simples et lisibles, une idée par image, 1 à 3 personnages, des lieux réels (cabinet d'avocat, couloir d'hôpital, cuisine…).
- **Le prof** : présentateur animé, avec des poses (explique, montre, choqué, compte l'argent…).
- **Voix** : Algrow, 158 mots/min.
- **Miniature validée**, façon Marcus :
  - fond plan bleu avec grille ;
  - un gros titre noir à contour blanc, souligné en rouge (ex. « THE DIVORCE TRAP ») ;
  - le prof à droite ;
  - 1 à 2 humains BD à gauche, **différents à chaque vidéo** (demande de l'utilisateur) ;
  - des étiquettes chiffrées et des flèches.

## Règles

- **Le ticket doit être juste du début à la fin.** Pas de ligne « Running total », et le total doit être égal à la somme des lignes. `check_receipts` et `verify.py` le contrôlent.
  - L'erreur est déjà arrivée une fois sur la vidéo Kid : l'utilisateur a dû supprimer une vidéo programmée.
- **Chiffres** : uniquement des faits vérifiés, avec la source citée dans la phrase (CDC, Census, enquêtes…). Une fourchette est présentée comme une fourchette.
- **Chiffres à l'écran** : seulement des chiffres dits dans la narration.

## Ce qui marche

- **Premier jour de la vidéo Divorce** : 75 impressions pour 25 vues. Bon signal, d'après l'utilisateur.

## Vidéos

Voir [videos/](videos/README.md).

| Vidéo | État |
|---|---|
| The Economics of a Divorce | publiée |
| The Economics of Dying in America | livrée |
| The Economics of Having a Kid | livrée, **version corrigée** (le ticket de caisse était faux dans la première version) |
| The Economics of an Ambulance Ride | livrée, vérifiée |

## Idées de vidéos

- **The Economics of Going to Prison** : déjà discutée, mise de côté pour l'instant.

Pistes à vérifier avec NexLev, pas encore validées :
- The Economics of a Wedding
- The Economics of a Car Accident
- The Economics of Owning a Dog
- The Economics of Getting Arrested
- The Economics of Cancer Treatment
- The Economics of a College Degree
- The Economics of Moving Abroad
