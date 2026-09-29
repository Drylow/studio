# Outil HeyGen — pipeline vidéo dans le navigateur

Page **100 % statique** (`index.html`) à héberger sur le site. Tout tourne dans
le navigateur ; seuls le **rendu vidéo** et quelques providers passent par la
**render API** (`render.kanye.studio`). Flux : tête parlante → transcription
(Groq) → plan B-roll (LLM) → clips (Pexels + Pixabay) + images IA (Replicate
Nano Banana 2) → rendu Remotion côté serveur.

---

## ⚠️ NE PAS OUBLIER : la partie « Settings » = `../config.js`

> **Tout passe par `website-tools/config.js`** (un cran au-dessus de ce
> dossier, chargé via `<script src="../config.js">`). **Sans lui, rien ne
> marche.** C'est l'équivalent de l'onglet « Settings » : la seule chose à
> vérifier/maintenir.

`config.js` doit contenir :

| champ | rôle | sans ça… |
|---|---|---|
| `renderApi` | URL du serveur de rendu (ex. `https://render.kanye.studio`) | pas de génération HeyGen, transcription, images, ni rendu |
| `renderToken` | jeton exigé par la render API (rendu / relais / upload) | la render API refuse les appels |
| `keys.heygen` | **clé de TON API self-hosted** `heygen.kanye.studio` (≠ clé HeyGen officielle) | pas d'avatars / génération |
| `keys.groq` | transcription Whisper | pas de transcription |
| `keys.pexels` | clips stock (source 1) | pas de clips Pexels |
| `keys.pixabay` | clips stock (source 2) | pas de clips Pixabay (Pexels seul) |
| `keys.replicate` | images IA (Nano Banana 2) | pas d'images IA |
| `keys.openrouter` | LLM du plan B-roll (ici ton proxy `cliwebproxy`) | pas de plan auto |

⚠️ `config.js` est **lisible par les visiteurs** du site (clés en clair) — choix
assumé. Surveille tes crédits. **À chaque déploiement / changement de domaine,
re-vérifie `config.js`.** Si `renderApi` est vide, la page affiche un bandeau
« Render API non configurée ».

---

## Utilisation

1. **Nouvelle chaîne** (niche, branding, avatar/voix HeyGen par défaut). Stockée
   dans le navigateur (IndexedDB) — propre à ce navigateur.
2. **Créer un projet**, puis dans la carte :
   - **Étape 1 — Tête parlante** : uploade un MP4 d'avatar (recommandé), *ou*
     génère via HeyGen (relais). ⚠️ la génération auto est **en standby**
     (bug d'automation côté `heygen.kanye.studio`) → privilégie l'upload.
   - **Étape 2 — Transcription** (Groq), **Étape 3 — Plan B-roll** (LLM),
     **Étape 4 — Assets** (clips Pexels/Pixabay + images IA), **Étape 5 —
     Rendu** (render API → MP4 final, aperçu + téléchargement).

## Nouveautés de cet update

- **Images IA = Nano Banana 2** (`google/nano-banana-2` sur Replicate).
- **Pixabay en 2ᵉ source** de clips + **choix du meilleur clip** (score :
  résolution, format paysage, durée, correspondance avec la requête), au lieu du
  1ᵉʳ résultat. Moins d'overlays abandonnés.
- **Split-écran** (avatar à gauche / visuel à droite) **et plus de bandeau** :
  le planner émet un champ `layout` (`full`/`split`, ~moitié-moitié) envoyé dans
  le manifest. ⚠️ **Visible seulement si la render API tourne sur le code
  Remotion à jour** de `heygen-tool` (composition `PlanVideo.tsx` mise à jour —
  voir `_render-api-spec/CONTRACT-heygen.md`). Le frontend, lui, est prêt.
- Densité de b-roll légèrement augmentée + thème clair.

## Notes

- Le **rendu se fait sur le serveur** (`render.kanye.studio`), pas dans le
  navigateur. Le reste (scripts, transcription, recherche de clips) est local au
  navigateur.
- `heygen/studio/` est une ancienne SPA optionnelle (gestion avatars/voix de
  l'API self-hosted) — non requise pour le pipeline.
