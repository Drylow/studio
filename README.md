# Edgerunners Studio

Un seul studio pour organiser les chaînes YouTube, préparer leurs vidéos et suivre
leur publication. Interface Cyberpunk en français, backend Flask et moteurs de
production conservés. État détaillé : [DASHBOARD_STATUS](production/DASHBOARD_STATUS.md).

## Ce qu'on peut utiliser

- Vue d'ensemble du stock, des créneaux, travaux et blocages.
- Centre de contrôle : problèmes classés, prochaines actions précises, suivi des
  alertes propre à chaque compte et état du moteur/configurations.
- Huit chaînes importées, réglages propres à chaque chaîne et mode manuel/automatique.
- Répartition Drylow / Kanye par glisser-déposer, déplacement sur téléphone et vue
  « Mes chaînes ». Les chaînes non attribuées restent dans « À répartir ».
- Radar d'actualités MMA et foot : sources RSS datées, sujets récents et préparation
  d'une fiche de recherche. Collecte régulière configurable par chaîne.
- Tableau de production, calendrier mensuel et agenda en heure belge.
- Planning « Qui poste ? » : rythme stable par chaîne, responsable, créneaux
  suggérés et vidéos réservées avec leurs blocages. Une suggestion ne lance aucun travail.
- Export du mois, de la chaîne et du responsable sélectionnés vers un fichier `.ics`.
- Tâches partagées, responsables et échéances ; deux comptes individuels.
- Routines pour la recherche, la vérification d'une publication et l'organisation
  de la semaine. Recherche, filtre par chaîne, tâches en retard et lien vers la vidéo.
- Studio vidéo pour les formats Oddly, History et analyses sportives courtes.
- Fiches réunissant script, sources, fichiers, miniature, contrôles et programmation.
- Liste des étapes avant publication, avec action précise pour chaque blocage.
- Bibliothèque des références approuvées et des productions existantes.
- Agrandissement des miniatures et planches de contrôle, utilisable aussi sur mobile.
- Delamain : assistant connecté aux données et aux actions de préparation du studio.
- File de travaux persistante avec progression, erreurs, annulation et reprise.
- Avertissement de connexion interrompue, heure de dernière lecture et reprise
  automatique de la lecture lorsque le réseau revient.

Le choix éditorial automatique des sujets, la vérification des faits, les contrôles
entièrement autonomes et la production automatique des miniatures sportives restent
à construire. Le radar fournit des pistes de recherche, pas des faits vérifiés ni
des licences de médias. La collecte permanente est désactivée par défaut. La connexion
Google et les permissions des médias doivent être finalisées avant toute publication
réelle. Les adaptateurs de droits pour Oddly et History restent à terminer. Aucun
hébergement public ni cadence automatique n'est activé par cette version.

## Installation

Python 3.10+ ; ffmpeg est fourni par `imageio-ffmpeg`. Node est nécessaire pour modifier
l'interface et pour le moteur documentaire, pas pour servir le bundle déjà compilé.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Sous Windows, activer le venv avec `.venv\Scripts\activate` et copier `.env.example`
en `.env` avec l'explorateur. Ne jamais partager ou committer `.env`.
Les variables des services de production restent côté serveur.

## Voir l'aperçu

```bash
STUDIO_PREVIEW=1 STUDIO_WORKER_ENABLED=0 .venv/bin/python app.py
```

Ouvrir **http://127.0.0.1:5000**. L'aperçu importe les chaînes et livraisons dans une
base séparée, `work/studio/preview.db`. Il accepte les modifications d'organisation,
mais bloque les appels payants, les envois et les publications. Il n'accepte que les
connexions locales.

Cliquer **Tâches → Nouvelle tâche** pour ajouter du travail, ou **Studio vidéo →
choisir une chaîne → Ajouter à la production** pour préparer une fiche. Dans
**Calendrier → Prévoir une publication**, choisir la vidéo et la date, puis cliquer
**Enregistrer le créneau**.

Pour les actualités : **Radar d'actus → choisir Cage Dispatch ou Pitch Dispatch →
Actualiser les infos**. Sur un sujet, cliquer **Préparer une vidéo** : la fiche reprend
le lien et sa date ; compléter les faits vérifiés avant de produire. Les sources et
la fréquence se règlent dans **Sources du radar → Configurer le radar**. L'aperçu autorise la lecture
manuelle des flux publics, mais pas leur collecte permanente.

Pour voir les problèmes : **Centre de contrôle**, ou la cloche en haut. Chaque alerte
propose une action et ses étapes. **Marquer comme lue** ne change que ton suivi,
pas celui du collègue ni les contrôles de publication.

Pour un ensemble de tâches : **Tâches → Ajouter une routine → choisir le type, la
chaîne, éventuellement une vidéo, le responsable et l'échéance → Ajouter les tâches**.
Une routine ouverte du même type sur la même chaîne/vidéo est réutilisée plutôt que
dupliquée. Cocher les tâches ne valide pas les droits ou le rendu.

Pour l'agenda externe : **Calendrier → choisir le mois et la chaîne → Exporter le
mois**. Dans ton agenda, choisir **Importer**, puis le fichier `.ics` téléchargé.
C'est une copie des créneaux prévus, sans synchronisation ni publication automatique.

## Utiliser les comptes

Lancer `python app.py`, ou `START_STUDIO.bat` sous Windows. Au premier lancement,
ouvrir `.env`, copier la valeur de `STUDIO_BOOTSTRAP_TOKEN` dans le champ **Code
d'installation**, puis choisir ses nom, identifiant et mot de passe. Ajouter ensuite
le collègue dans **Réglages → Équipe**. Le code initial ne fonctionne qu'une fois.

Le serveur doit rester allumé pour exécuter les travaux et créneaux. Le choix du mode
« automatique » ne remplace pas les contrôles : droits, fraîcheur, fichiers, qualité,
pause et validation sont vérifiés côté serveur. Les vidéos YouTube sont chargées en
privé avant la miniature et la mise en public ; leur identifiant est conservé pour
reprendre un incident sans créer un second chargement.

Avant un hébergement public : configurer HTTPS, `COOKIE_SECURE=1`, un serveur WSGI,
les sauvegardes et le client Google. Les étapes Google et la connexion par chaîne
figurent dans **Réglages** ; l'essai initial doit être une publication privée.

## Développement et tests

```bash
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m unittest discover -s tests
```

Les sources de l'interface sont dans `frontend/src/`, le bundle dans `static/studio/`
et le nouveau backend dans `studio/`. La migration SQLite conserve les anciennes
données et sauvegarde la base avant sa première migration.

Les essais navigateur nécessitent une seconde instance sur une base d'aperçu dédiée,
puis `cd frontend` et les parcours `smoke`, `smoke:control`, `smoke:news`, `smoke:team`.
Le parcours news nécessite des infos dans le radar de cette base dédiée ; le parcours équipe
nécessite le compte collègue de test. Commandes complètes dans
[DASHBOARD_STATUS](production/DASHBOARD_STATUS.md#développement-et-vérifications).

## Moteurs et références conservés

- Oddly : `services/pov_engine.py`, `services/pov_script.py`, pipeline `production/`.
- Documentaires : `services/history.py`, `history_engine/`, fiches `chaines/`.
- Sport : `services/news_brief.py`, `services/newsvid.py`, contrôle des droits
  `services/news_rights.py` et livraison Discord existante.
- Styles approuvés : `presets/` ; aucune miniature actuelle n'a été refaite.

Les anciennes interfaces de `tool_apps/`, templates, styles et cadres d'outils sont
supprimées. Les anciens liens redirigent vers le nouveau studio. Les guides détaillés
des moteurs restent dans [CLAUDE.md](CLAUDE.md), et la reprise de session dans
[REPRISE.md](production/REPRISE.md). Les passages historiques décrivant les anciennes
pages ne correspondent plus à la navigation actuelle.
