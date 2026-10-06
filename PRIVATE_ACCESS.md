# Accès privé à Edgerunners Studio

Choix confirmé par l’utilisateur : accès simple par **identifiant et mot de passe
personnel**, sans application à installer et sans QR code. Deux comptes maximum :
Drylow et Kanye. Aucune inscription publique. Les pages, vidéos et outils sont
protégés par le serveur, même si quelqu'un connaît leur adresse exacte. Seules les
pages d’information `/about`, `/privacy` et `/terms` sont publiques pour présenter
l’application et ses règles à Google et aux visiteurs ; elles n’exposent aucune
donnée du studio.

## Première ouverture

1. Ouvrir le site. Entrer le code d'installation transmis en privé lors de la mise
   en service, ton nom, ton identifiant et un mot de passe d'au moins 16 caractères.
2. Cliquer **Créer mon compte** : le studio s'ouvre directement.
3. Dans **Réglages → Ton équipe → Ajouter**, renseigner Kanye, son identifiant et
   un mot de passe initial fort. Lui transmettre ce mot de passe en privé.

Le code d'installation sert une seule fois, à la création du propriétaire. Les
connexions suivantes ne demandent que l'identifiant et le mot de passe. Kanye peut
changer son mot de passe dans **Réglages → Accès & sécurité**. Chacun choisit un
mot de passe différent ; une phrase de plusieurs mots ou le générateur du navigateur
convient. Aucun code téléphone ni téléchargement de codes de secours.

## Gestion de ton accès

**Afficher le mot de passe** permet de vérifier ce que tu tapes. Le navigateur peut
l'enregistrer dans son gestionnaire intégré. **Déconnexion** invalide immédiatement
la session côté serveur. **Réglages → Accès & sécurité → Déconnecter les autres
appareils** ferme les autres connexions de ton compte, en gardant celle-ci.

Pour changer de mot de passe : **Changer mon mot de passe**, entrer l'actuel, choisir
un nouveau de 16 à 128 caractères, puis **Enregistrer mon mot de passe**. Toutes les
anciennes sessions sont fermées. Un accès utilisant l'ancien mot de passe ne peut
pas recréer une session pendant ce changement.

Les sessions expirent au bout de douze heures, ou après une heure sans requête.
Les essais incorrects sont limités, même en parallèle ou depuis plusieurs adresses.
Une session expirée ou révoquée referme l'interface à la prochaine réponse du serveur.
En cas de mot de passe perdu, une intervention avec l'accès privé à l'hébergement
est nécessaire ; il n'y a pas de remise à zéro publique.

## Installation sur o2switch

Le guide [DEPLOY_O2SWITCH.md](DEPLOY_O2SWITCH.md) couvre HTTPS, le domaine autorisé,
les cookies sécurisés, les données hors du dossier public et les règles Apache.
Passenger interdit l'aperçu et les clés de session faibles. Les mots de passe sont
hachés, les identifiants de session sont aléatoires et conservés sous forme
d'empreintes en base. La clé `FLASK_SECRET_KEY` reste privée et stable.

Delamain utilise des sessions internes brèves, liées au compte ayant envoyé la
mission ; elles sont détruites après chaque action. L'agent qui modifie le code
ne peut pas réécrire les fichiers de sécurité. Les anciennes données éventuelles
d'authentification par téléphone sont conservées mais ne servent plus à la connexion.

## Vérifications

```bash
.venv/bin/python -m unittest discover -s tests
npm --prefix frontend run build
npm --prefix frontend run smoke:security
```

Le parcours navigateur démarre une base jetable et vérifie vraiment création de
compte, connexion directe, mot de passe visible/masqué, retour à la page demandée,
changement de mot de passe, déconnexion, rejet d'un cookie copié et fermeture de
l'interface après révocation. Il couvre cinq tailles d'écran sans service payant.
Le contrôle final sur le domaine hébergé reste nécessaire avant ouverture.
