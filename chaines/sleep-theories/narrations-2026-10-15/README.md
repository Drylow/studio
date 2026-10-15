# Six narrations — 15 octobre 2026

Commande utilisateur : générer les six scripts finaux dans Algrow Voiceover avec la voix **Mellow Matt**, ID `IsEXLHzSvLH9UMB6SLHj`.

Douze parties acceptées, deux par épisode, en cours côté service. 1 MP3 complet vérifié et 5/12 parties récupérées au dernier relevé. Voir `suivi.json` pour les identifiants acceptés ; ne pas les soumettre de nouveau.

Le compte professionnel limite chaque demande à 100 000 caractères : les scripts sont coupés à une séparation de paragraphes proche du milieu, sans réécriture. Leur concaténation textuelle reproduit exactement chaque source finale contrôlée. Vitesse 0,90, réglages standards existants, sous-titres demandés. Les crédits de sous-titrage peuvent s'ajouter à ceux du texte ; le débit sera relevé à la fin.

Exécuteur : `production/sleep_voiceovers.py`. Depuis la racine du dépôt : `python production/sleep_voiceovers.py monitor`. Cette commande lit uniquement les jobs acceptés, télécharge les parties terminées, vérifie leur décodage complet, assemble les MP3 sans réencodage puis mesure la durée finale. Elle ne lance aucune génération payante.

Le registre privé `work/sleep-voiceovers-2026-10-15/ledger.json` conserve les réponses du service et les URL de téléchargement. Les médias sont dans son sous-dossier `parts`, puis les six fichiers finaux sur le Bureau dans **Voix sleep - 15 octobre 2026**. Les URL et MP3 ne vont pas dans Git. Préserver le registre en cas de changement de compte.

La clé valide est celle du `.env` du dépôt. Une ancienne variable Windows du même nom est refusée ; l'exécuteur choisit explicitement le `.env` pour ce processus, sans modifier Windows. Ne jamais afficher ni copier sa valeur dans la passation.

Le premier envoi du script Force intégral a reçu un refus HTTP 400 pour dépassement de taille : aucun job accepté et aucun crédit consommé. Il a été remplacé par deux demandes sous la limite.

Les deux heures minimum seront validées sur les audios réels. Pas de silence, boucle ou répétition ajoutés. Aucun montage ou upload autorisé par cette demande.
