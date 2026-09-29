# 🚀 Guide mise en ligne — edgerunners.fr (version pas-à-pas, zéro stress)

> Lis une étape, fais-la, passe à la suivante. Aucune ligne de code à inventer :
> tu remplis des cases et tu copies-colles. Compte ~30 min tranquille.
> Bloqué quelque part ? Note le numéro de l'étape et demande-moi, je débloque.

---

## ✅ AVANT DE COMMENCER — ce qu'il te faut sous la main

- [ ] Le fichier **`drylow_deploy.zip`** (dans ton dossier `drylow_studio`).
- [ ] Tes identifiants **o2switch** (pour te connecter à cPanel).
- [ ] Le domaine **edgerunners.fr** déjà rattaché à ton compte o2switch.
- [ ] Tes 2 mots de passe du site (ils sont déjà dans le `.env` du zip) :
      le **boss** (toi) et le **guest** (invités).

---

## ÉTAPE 1 — Se connecter à cPanel

1. Va sur ton espace o2switch et ouvre **cPanel** (le panneau de contrôle).
2. Tu arrives sur une page pleine d'icônes rangées par sections
   (Fichiers, Bases de données, Logiciels, Avancé…). C'est ta « salle de commande ».

👉 *Tu dois voir : une grille d'icônes. Si oui, tu es au bon endroit.*

---

## ÉTAPE 2 — Créer l'application Python (le branchement, une seule fois)

C'est l'étape qui t'inquiétait : rien de technique, juste un formulaire.

1. Dans cPanel, section **« Logiciels »** → clique **« Setup Python App »**
   (ou « Configurer une application Python »).
2. Clique le bouton **« CREATE APPLICATION »** (Créer une application).
3. Remplis les cases comme ça :
   - **Python version** → choisis la plus récente proposée (ex. `3.11` ou plus).
   - **Application root** → tape exactement : `drylow_studio`
     *(c'est le dossier où vivra le site ; surtout PAS « public_html »)*
   - **Application URL** → choisis **`edgerunners.fr`** dans la liste.
   - **Application startup file** → tape : `passenger_wsgi.py`
   - **Application entry point** → tape : `application`
4. Clique **« CREATE »**.

5. ⭐ IMPORTANT : en haut, cPanel affiche une **commande** qui commence par
   `source /home/drdr5446/virtualenv/...`. **Sélectionne-la et copie-la**
   (clic droit → Copier). Garde-la pour l'étape 5. *(Si tu l'as perdue, pas grave :
   reviens sur cette page « Setup Python App », elle est réaffichée.)*

👉 *Tu dois voir : une ligne pour ta nouvelle app, avec un bouton RESTART, et la
fameuse commande `source ...` en haut.*

---

## ÉTAPE 3 — Envoyer le site (uploader le zip)

1. Retourne à l'accueil cPanel → section **« Fichiers »** → **« Gestionnaire de fichiers »**.
2. À gauche, ouvre le dossier **`drylow_studio`** (il a été créé à l'étape 2).
3. En haut, clique **« Téléverser »** (Upload).
4. Glisse **`drylow_deploy.zip`** (ou clique pour le sélectionner). Attends la barre
   verte « 100% » (~10-30 s selon ta connexion).
5. Reviens au Gestionnaire de fichiers (lien « Retour à… » en haut), **rafraîchis**
   le dossier `drylow_studio` → tu vois `drylow_deploy.zip`.
6. **Clic droit sur le zip → « Extraire » (Extract)** → confirme l'extraction dans
   le même dossier `drylow_studio`.
7. Une fois extrait, tu vois apparaître `app.py`, `passenger_wsgi.py`, les dossiers
   `routes/`, `tool_apps/`, etc. **Supprime le zip** (clic droit → Supprimer) pour
   faire propre.

👉 *Si on te demande d'écraser `passenger_wsgi.py` : dis OUI (le nôtre est le bon).*

---

## ÉTAPE 4 — Installer les briques du site (pip install)

1. Accueil cPanel → section **« Avancé »** → **« Terminal »** (une fenêtre noire
   façon console s'ouvre). Pas de panique, tu vas juste coller 2 lignes.
2. **Colle la commande `source ...`** que tu as copiée à l'étape 2, appuie sur
   **Entrée**. Le début de la ligne devient `(drylow_studio)` → ça veut dire « ok,
   je suis dans ton app ».
3. Tape (ou colle) ceci puis Entrée :
   ```
   pip install -r requirements.txt
   ```
4. Ça défile ~30 s puis ça s'arrête. C'est installé. ✅

👉 *Tu dois voir des lignes « Successfully installed Flask … ». S'il y a écrit
« error », copie-moi le texte, je regarde.*

---

## ÉTAPE 5 — Démarrer le site + activer le HTTPS (le cadenas 🔒)

1. Retourne dans **« Setup Python App »** → sur la ligne de ton app, clique
   **« RESTART »** (redémarrer). Ça relance le site avec tout en place.
2. Accueil cPanel → section **« Sécurité »** → **« SSL/TLS Status »** →
   coche `edgerunners.fr` → clique **« Run AutoSSL »** (certificat HTTPS gratuit).
   *(Si c'est déjà actif/vert, rien à faire.)*
3. Ouvre un navigateur → va sur **https://edgerunners.fr**.

👉 *Tu dois voir : la page Night City avec le mot de passe (le « gate »). 🎉
Si oui : le site est EN LIGNE.*

---

## ÉTAPE 6 — Te déclarer BOSS (à faire en premier, important)

1. Sur la page du gate, **triple-clique sur le kanji サムライ** (en bas).
   → le mode passe en **ROOT** (couleur or).
2. Entre ton **mot de passe boss**, valide.
3. Une fois entré, va dans **SURVEILLANCE** (menu) →
   clique **« ★ Mémoriser cet appareil »** → comme ça tu ne retaperas plus le mot
   de passe sur CE PC/navigateur.
4. Clique **« ⚠ Purger — ne garder que moi »** → ça nettoie tous les appareils de
   test et ne garde QUE le tien comme appareil de confiance.

👉 *Important : la connexion auto se fait par APPAREIL (pas par adresse internet),
c'est ce qui rend le site sûr.*

---

## ÉTAPE 7 — Activer la production automatique (le CRON)

Pour que Delamain produise et poste les vidéos **tout seul**, même quand tu n'es
pas sur le site.

1. Ouvre, dans le zip extrait (ou ton dossier local), le fichier **`CRON_COMMAND.txt`**
   → il contient une ligne `curl ...` toute prête (avec ton secret déjà dedans).
   **Copie cette ligne.**
2. Accueil cPanel → section **« Avancé »** → **« Cron Jobs »** (Tâches planifiées).
3. Dans **« Common Settings »**, choisis **« Once every 10 minutes »**
   (ou tape `*/10 * * * *`).
4. Dans **« Command »**, **colle la ligne** copiée à l'étape 1.
5. Clique **« Add New Cron Job »**.

👉 *C'est fait : toutes les 10 min, le serveur fait avancer la production d'une étape,
tout seul.*

---

## ÉTAPE 8 — Connecter ta chaîne YouTube + tester

1. Sur le site (en boss), ouvre **Delamain**, crée/ouvre ta chaîne, et clique
   **« Connecter la chaîne »** → fais le consentement Google.
   *(L'écran Google « application non vérifiée » est NORMAL pour tes propres
   chaînes : clique « Continuer ».)*
2. Demande une petite vidéo de test à Delamain, ou programme-la, et vérifie qu'elle
   apparaît dans la Production puis sur YouTube.

👉 *Si la connexion YouTube refuse : vérifie l'URI Google (voir « À VÉRIFIER » plus bas).*

---

## 🔒 ÉTAPE 9 — Sécurité (à ne pas oublier)

- [ ] **Supprime `drylow_deploy.zip` de ton PC** une fois la mise en ligne finie :
      il contient tes secrets (mots de passe + clés API). Ne le mets JAMAIS sur un
      dépôt public / Drive partagé.
- [ ] Ne donne le **mot de passe guest** qu'aux invités (ils n'ont accès qu'à
      l'accueil, jamais aux outils ni aux clés).

---

## ⚠️ À VÉRIFIER UNE FOIS (sinon YouTube refusera la connexion)

Dans **Google Cloud Console** → ton projet → écran OAuth → **URIs de redirection
autorisés**, il doit y avoir EXACTEMENT :
```
https://edgerunners.fr/api/youtube/callback
```
*(Si tu l'avais mis sur localhost avant, ajoute/remplace par celui-ci.)*

---

## 🆘 SI ÇA MARCHE PAS (les cas courants)

- **Erreur 500 / page blanche** → cPanel → Setup Python App → regarde les logs,
  ou le fichier `stderr.log` dans le dossier `drylow_studio`. Copie-moi le texte.
- **« passenger_wsgi.py not found »** → l'extraction du zip n'a pas mis les fichiers
  au bon endroit (ils doivent être DIRECTEMENT dans `drylow_studio/`, pas dans un
  sous-dossier). Re-extrais.
- **La page reste sur « http » sans cadenas** → relance « Run AutoSSL » (étape 5),
  attends quelques minutes.
- **YouTube refuse la connexion** → l'URI Google (section ci-dessus).

> Dans tous les cas : décris-moi ce que tu vois (capture d'écran si tu peux),
> et je te débloque. On le fait ensemble.
