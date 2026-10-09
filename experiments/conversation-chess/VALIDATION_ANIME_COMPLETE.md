# Verification du duel anime complet — 9 octobre 2026

Le rendu corrige est dans `work/conversation-chess/lelouch-full-v2/kdenlive/` :
`APERCU-LELOUCH-SCHNEIZEL.mp4`, `project.kdenlive`, ses medias et le job natif.
Il remplace les apercus precedents pour la revue de cet episode.

- Video de254.6s :7638frames,1920x1080,30fps. Le dialogue anglais couvre
  sans trou les0–191.6s de la source ; guide16s, cinq analyses7s, bilan12s.
- Premiere pause deplacee de14.95 a15.45s source. L'alignement termine
  « opinion » a14.84s, laissant0.61s avant la pause. Le fondu audio commence
  a15.415s. Les echantillons PCM prepares de14.2 a15.35s sont identiques
  a la reference originale attenuee a0.65 : la fin du mot est preservee.
- Tony est remplace par un pion neutre provisoire dans le guide, les analyses
  et le bilan. Les assets historiques, `scene.js` et les neuf SVG Chess.com
  restent conserves. Le personnage definitif reste a choisir.
- Export natif Kdenlive26.08.1/MLT : H264CRF17/medium, AAC192k,48kHz stereo.
  Les40ressources du projet sont presentes. Six pistes separees ; textes
  regenerables depuis le JSON, pas titres Kdenlive editables mot par mot.
- Decodage integral video/audio sans erreur. Mesure du MP4 : -23.18LUFS,
  true peak -2.31dBTP, LRA15.70. Le gain de dialogue0.65 evite les pics
  interechantillons positifs mesures dans la source.
- Les39planches `review/frames-00.jpg` a `frames-38.jpg` ont ete examinees :
  toutes les7638frames sont representees en miniatures, sans saut. Dix-neuf
  captures1920x1080 complementaires ont ete regardees pour lire les deux
  guides, les cinq commentaires complets, le bilan et la premiere transition.
  Pas de calque manquant, texte debordant ou portrait Tony observe. Les
  eclairs blancs du montage Geass appartiennent a la source. Le fondu final
  est present. Ce controle n'est pas une inspection de chaque pixel en taille
  native ni une comparaison pixel par pixel avec la chaine de reference.
- Apres frappe, les cinq pistes SFX ont un pic PCM nul pendant la lecture :
 3.04,3.20,3.34,3.08 et3.18s. Deux accents comiques choisis ; musique
  seulement au guide et au bilan. Pas d'ecoute humaine revendiquee.
- Trois tests du portage passent (SVG Windows, chemins SFX, garde source et
  premier locuteur). La preparation et le rendu complet ont execute les
  nouveaux parametres de gain et de mascotte. Les changements concurrents
  du collegue jusqu'a `e67121c` ont ete repris. Son nouveau preset de
  preparation superfast a ete verifie sur une seconde de source ; les medias
  de ce rendu avaient deja ete prepares avec fast. L'export final est medium.

La source reste1280x720 issue de YouTube, sans sous-titres ni watermark
Fandango observes. Cet export porte le marquage «720p source» et reste un
apercu technique, pas une livraison de source native1080p. L'exception
documentee pour les originaux Naka720p ne s'applique pas a ce clip anime.

Preuves locales : `review/coverage.json`, `probe.json`, `audio.txt`,
`decode.txt`, `delivery/LOCAL_RECEIPT.json`, `BOUNDARY_FIX.json` et
`VISUAL_REVIEW.json`. Le kit titre/description/credits est local ; aucun
envoi Discord ni publication YouTube n'a ete effectue.

MP4 :122043293octets ; SHA256
`d86c5e21bfe39b3d9228d5924924514feeb9900d45337c8266d40d3e3a4e2993`.
