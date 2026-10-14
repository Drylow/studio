# Épisode 01 — Why Being a Samurai Was Worse Than You Think

Livraison finale : **19 min 39 s**, 1 920 × 1 080, 24 images/s, 28 297 images vidéo. Le film natif livré est identifié par SHA-256 **02a4c48d6682adcf8020a3338f02903c506b7590eeb721d250766ff0927d9163**. Le MP4 de 514 023 699 octets reste dans [le GoFile livré](https://gofile.io/d/M9RLsD1P) et sur l'environnement qui possède la production ; il n'est pas intégré à GitHub.

## Fichiers présents et ordre de lecture

1. `narration/spoken.txt` : les **2 795 mots exacts parlés**, SHA-256 `f2d0e1be63b96bb524de524b61f35623ae2618c25f09645afe619e76d1fde3a9`. `draft.md` est le brouillon avec les 12 chapitres. `provider-original.txt` documente la version de texte réellement retrouvée chez le prestataire ; elle n'est pas substituée au script canonique.
2. `visual-bible.txt`, `assets/masters/registry.json` et les **13 PNG de maîtres** : Kenji, Hana, supérieur, marchand, père, mère ; maison, marché, bureau, porte, salle d'entraînement, route et logement de service à Edo.
3. `plan/bound-plan.json` : 108 paragraphes avec texte, chapitre, horloge réelle, action écrite, mouvement natif et références ordonnées. Les chemins des éléments emballés sont relatifs à ce dossier. Les documents JSON historiques sont contenus dans le champ **`document`**, avec leur SHA original séparé : le SHA original n'est jamais annoncé comme celui du JSON portable.
4. `assets/scenes/scene-0001.png` à `scene-0108.png` : les **108 images sélectionnées réellement utilisées**, copies identiques vérifiées. `prompts/selected-scenes-generation.json` sépare arguments créatifs originaux, image sélectionnée, prompt de correction éventuel et revue effective. Les choix de modèles et charges brutes du prestataire ont été retirés de la copie publique.
5. `narration/voice-provider-original.mp3` : voix brute retrouvée, SHA `409839ba19234c22eb2b139116b93f8a92d952eb7b26e0827c8b0a34951ba90c`. `voice-native-derived.mp3` : transcodage natif mono 44 100 Hz / 192 kbit/s, SHA **976f1493619e9266301dc772af362f5a7fe5602433f2a8b66cc728fd1e3a2671**. Il ne s'agit pas de deux générations vocales : la reprise a réutilisé la voix Ryan Kurk existante, vitesse 1, sans nouvel appel vocal payant.
6. `plan/word-timings.json`, `actual-paragraph-timings.json` et `narration/provider-original.srt` : horloge vocale et alignement exact. Le prestataire a transcrit 2 793 tokens avant réalignement aux 2 795 mots canoniques ; ne pas confondre ces comptes.
7. `reviews/` : revues des maîtres, de toutes les images, des 20 corrections, du script et du film encodé. `technical-proof.json` documente le décodage complet, les niveaux et corrélations vocales. Les revues conservées sont des constats historiques réellement enregistrés ; cette copie GitHub ne les présente pas comme une nouvelle inspection du film.
8. `delivery/English-Captions.srt` et `UPLOAD-original.txt` : métadonnées du paquet livré. Le texte initial conseille une vieille miniature A ; **ce conseil est dépassé par le choix utilisateur ultérieur C — PAID IN RICE?**. Les chapitres restent alignés au film inchangé.
9. `thumbnails/revision-A.jpg`, `revision-B.jpg`, `revision-C.jpg` et leurs PNG originaux : les **trois révisions réellement faites**. C est la choisie. Les deux JPG `archive-A/B` sont les anciennes versions livrées. Il n'existe pas de quatrième révision Samurai dans les fichiers retrouvés ; ne pas en inventer une. Les révisions sont natives à 1 672 × 941 ; ne pas les présenter comme un détail 4K natif.
10. `asset-manifest.json` : SHA et taille de chaque fichier inclus, rôle, origine historique et identité réelle des copies. `validate_handoff.py` contrôle ce registre localement, sans génération, réseau ou publication.

## Sujet, écriture et contexte historique

Kenji est un personnage fictif servant à explorer un foyer de petit rang vers **1720 au Japon Tokugawa**. Le film suit rang et héritage, paix relative, dépenses de statut, traitement en riz et besoins d'argent, service administratif, entraînement, famille, voyages du seigneur, condition de rōnin et limites des clichés sur l'honneur. Chaque affirmation importante conserve les variations de domaine, rang, fortune et époque. Ne pas transformer ce cas fictionnel en destin universel de tous les samouraïs.

Le dossier de recherche original complet de l'environnement précédent n'a pas été retrouvé. La revue de texte conservée précise explicitement qu'elle a utilisé les connaissances historiques disponibles, **sans nouvelle consultation indépendante de sources**. C'est un contrôle ciblé des affirmations, pas une bibliographie vérifiée à citer. Avant un nouvel épisode, refaire une recherche traçable avec sources institutionnelles ou scientifiques et conserver les citations réellement lues.

## Comment le film a réellement été monté

Après un remplacement d'environnement, le texte et la voix ont été récupérés ; les images manquantes ont été **regénérées**, avec nouvelles preuves et nouvelle sélection. Elles ne sont pas annoncées comme les anciens octets récupérés. Le projet natif local de cette reprise est `why-being-a-samurai-was-worse-than-you-t-947aab` ; l'ancien projet interrompu `...-8a62fc` n'est pas le rendu final.

La reprise a utilisé le **moteur TubeForge natif inchangé, installé dans l'environnement cloud**, issu du commit `a3d23a2cdea09e044c24250f72e579f092086c84`. Ne pas attribuer ce film Samurai à la nouvelle API VPS du collègue : cette API a servi ensuite aux films Viking/Pirate. `render/native-source-integrity.json` conserve les hashes réels de `render_worker.py` et `steps/render.py`.

Les durées des plans viennent de l'audio décodé, pas d'une estimation en mots/minute. Pour chaque plan : image sélectionnée et contrôlée, dimensions 1 920 × 1 080, 24 images/s, nombre d'images `round(end × 24) − round(start × 24)`, mouvement natif indiqué dans le plan. Les personnages changent de pose entre les tableaux ; il n'y a **pas d'animation séparée continue des membres**. Les zooms/pans sont ceux du moteur natif, pas un nouveau moteur inventé.

La narration a reçu une correction de niveau en deux passes (cible −17 LUFS, crête −1,5 dBTP), sans changer les mots ni les **51 995 520 échantillons** à 44 100 Hz. Le FLAC normalisé peut être recréé à partir du MP3 natif et du procédé conservé ; le gros FLAC n'est pas inclus. Le rendu a assemblé 108 clips natifs vérifiés et la narration normalisée. Pas de musique ni bruitages ajoutés ; le SRT séparé est proposé pour YouTube.

`render/historical-helpers/` conserve les **sources exactes des exécutants historiques**, pas des scripts portables prêts à lancer : ils contiennent les chemins et le projet de l'environnement d'origine. Les lire comme références de l'algorithme, puis importer ce plan et ces images dans l'application native/API actuelle en adaptant les chemins et en recalculant les SHA de toute métadonnée réécrite. Ne pas lancer ces anciens exécutants sans avoir fait cette adaptation, ni déclencher automatiquement une nouvelle voix ou de nouvelles images.

Contrôle final réel : décodage complet audio/vidéo, corrélations vocales, capture de tous les plans et raccords, revue effective des captures, contrôle de texte/chapitres et des fichiers de livraison exacts. Le rapport d'export indiquait encore `pending` avant le contrôle ; les preuves techniques/visuelles finales et la libération finale du manifeste sont les étapes ultérieures, pas une contradiction à effacer.

## Ce qui est exclu ou non retrouvé

- MP4 final, 108 clips natifs, FLAC, profils navigateur, cookies, sessions, clés, archives SSH et charges brutes de prestataires : hors dépôt public.
- Avatar et bannière Samurai approuvés de l'ancien environnement : non retrouvés. L'utilisateur les a déjà installés. Une note historique mentionne une bannière `Samurai-Chapters-banner-2560x1440.jpg`, SHA `24c81a94b26a6a781f9c9c61803d6d4759d8ec2de9d302f606d96032b2b45a6d` ; sans octets présents, ce SHA n'est pas une validation d'un nouveau fichier.
- La sauvegarde privée cPanel temporaire a été supprimée après livraison à la demande de l'utilisateur. Ne pas la ressusciter automatiquement.
- Les chemins historiques non emballés dans les preuves sont des indications d'origine, **pas des fichiers disponibles dans le clone**. Les dépendances nécessaires aux nouvelles générations doivent être fournies en privé.

Publication : vidéo livrée puis publiée manuellement par l'utilisateur. La révision de miniature a été sélectionnée dans le chat. Aucun nouveau travail Samurai ni changement de publication n'est demandé pendant cette passation.
