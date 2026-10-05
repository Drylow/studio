# Accès privé à Edgerunners Studio

Le site est réservé à **Drylow et Kanye**. Aucun bouton d'inscription publique.
Chaque personne utilise un mot de passe personnel et un code à six chiffres sur
son téléphone. Les vidéos, pages et outils sont protégés par le serveur, même
quand quelqu'un connaît leur adresse exacte.

## Première connexion de Drylow

1. Ouvrir le site. Entrer le code d'installation transmis en privé lors de la mise
   en service, ton nom, ton identifiant et un mot de passe d'au moins 16 caractères.
2. Installer Google Authenticator, Microsoft Authenticator ou 2FAS sur le téléphone.
3. Dans cette application, toucher **+**, puis **Scanner un QR code**. Scanner le
   QR affiché par le studio. Sur le même téléphone, ouvrir **Je suis déjà sur mon
   téléphone** et copier la clé dans **Saisir une clé**, type **basé sur le temps**.
4. Entrer dans le studio les six chiffres affichés par l'application.
5. Toucher **Télécharger mes codes**, conserver le fichier dans un endroit privé,
   puis cocher **J'ai enregistré mes codes de secours** et entrer dans le studio.

L'accès reste bloqué pendant toute cette installation. Le code d'installation
ne peut pas créer un second propriétaire une fois le premier compte créé.

## Ajouter Kanye

Dans **Réglages → Ton équipe → Ajouter**, renseigner Kanye, son identifiant et
un mot de passe initial fort. Lui transmettre ce mot de passe en privé. À sa
première connexion, il configure son propre téléphone et sauvegarde ses propres
codes. Deux comptes maximum, même en passant directement par l'API.
Il peut ensuite changer son mot de passe dans **Réglages → Accès & sécurité**.

## Connexions suivantes

Entrer identifiant et mot de passe, puis le code du téléphone. Un code déjà
confirmé est refusé : attendre le prochain code de l'application si nécessaire.
Les essais incorrects sont limités, y compris quand ils arrivent en parallèle.

Les sessions expirent au bout de douze heures, ou après une heure sans requête.
**Déconnexion** invalide immédiatement le cookie côté serveur. Dans les réglages,
**Déconnecter les autres appareils** ferme les autres connexions de ton compte.
Un changement de mot de passe exige le mot de passe actuel et un nouveau code
du téléphone ; il ferme toutes les anciennes sessions.

## Si tu perds ton téléphone

1. Entrer ton identifiant et ton mot de passe.
2. Toucher **J'ai perdu mon téléphone** et entrer un code de secours enregistré.
3. Configurer une application sur ton nouveau téléphone, confirmer son code et
   sauvegarder les nouveaux codes de secours. Les anciens deviennent invalides.

Chaque code de secours fonctionne une seule fois. Le mot de passe reste requis.
Sans téléphone **et** sans codes, il n'y a pas de remise à zéro publique : une
intervention avec l'accès privé à l'hébergement est nécessaire.

## Protection de l'hébergement

Le guide [DEPLOY_O2SWITCH.md](DEPLOY_O2SWITCH.md) couvre HTTPS, le domaine autorisé,
les cookies sécurisés, les fichiers privés hors du dossier public et les règles
Apache. Le mode d'aperçu est interdit sur Passenger. Les secrets TOTP sont
chiffrés en base, les mots de passe et codes de secours sont conservés sous forme
d'empreintes. La clé privée `FLASK_SECRET_KEY` doit être stable et sauvegardée.
Delamain garde des sessions internes brèves, liées au compte ayant envoyé la
demande ; elles sont détruites après chaque action et ne constituent pas un
accès public. L'agent qui modifie le code ne peut pas réécrire les fichiers de
connexion ou cette protection serveur.

## Validation reproductible

```bash
.venv/bin/python -m unittest discover -s tests
npm --prefix frontend run build
npm --prefix frontend run smoke:security
```

Les essais utilisent des bases jetables et aucun service payant. Le parcours
navigateur teste réellement création de compte, QR, code téléphone, téléchargement
des secours, retour à la page demandée, déconnexion et rejet d'un cookie copié,
avec cinq tailles d'écran. Le contrôle final sur le domaine hébergé reste requis.
