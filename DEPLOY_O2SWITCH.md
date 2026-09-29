# Déploiement Drylow Studio sur o2switch — edgerunners.fr

Guide clic par clic. ~20–30 min. L'app est en **Flask (Python)** ; les outils
sont 100 % navigateur → aucune lib vidéo/IA côté serveur, install ultra-légère.

> Tu déploies à partir du fichier **`drylow_deploy.zip`** (déjà prêt). Il contient
> tout le nécessaire, y compris le `.env` (avec tes mots de passe) et
> `tool_apps/config.js` (avec tes clés API). **Ces 2 fichiers contiennent des
> secrets — supprime le zip de ton PC après l'upload, et ne le mets jamais sur
> un dépôt public.** Les secrets restent protégés sur le serveur (cf. sécurité).

---

## 1. Créer l'app Python dans cPanel

1. cPanel → section **Logiciels** → **« Setup Python App »** → **CREATE APPLICATION**
2. Remplis :
   - **Python version** : la plus récente (3.11+)
   - **Application root** : `drylow_studio`  → sera `/home/drdr5446/drylow_studio/`
     ⚠️ surtout **pas** dans `public_html` (sécurité)
   - **Application URL** : `edgerunners.fr`
   - **Application startup file** : `passenger_wsgi.py`
   - **Application entry point** : `application`
3. **CREATE**. cPanel affiche une commande du type :
   ```
   source /home/drdr5446/virtualenv/drylow_studio/3.11/bin/activate && cd /home/drdr5446/drylow_studio
   ```
   **Garde-la** (étape 3).

---

## 2. Uploader le code

1. cPanel → **Gestionnaire de fichiers** → `/home/drdr5446/drylow_studio/`
2. **Téléverser** → `drylow_deploy.zip`
3. Clic droit sur le zip → **Extraire** → dans le même dossier
4. Supprime le zip une fois extrait
   - ⚠️ Passenger a peut-être créé un `passenger_wsgi.py` d'exemple : laisse celui
     du zip écraser/remplacer (le nôtre est le bon).

---

## 3. Installer les dépendances

1. cPanel → **Terminal**
2. Colle la commande `source ...` de l'étape 1 (prompt devient `(drylow_studio)`)
3. Lance :
   ```bash
   pip install -r requirements.txt
   ```
   (≈ 30 s : juste Flask + python-dotenv)

---

## 4. Vérifier le `.env`

Le `.env` est déjà dans le zip avec les bonnes valeurs **prod** :
`FLASK_ENV=production`, `COOKIE_SECURE=1`, `DB_PATH=/home/drdr5446/drylow_studio/drylow_studio.db`,
`FLASK_SECRET_KEY` (aléatoire), `ACCESS_PASSWORD` (guest), `BOSS_PASSWORD` (boss),
`OAUTH_REDIRECT_BASE=https://edgerunners.fr` (publication YouTube),
`WORKER_CRON_SECRET` (rempli — sert au CRON de l'étape 8),
+ les clés API (FAL, ElevenLabs, Pexels, LLM, Lore worker, Google OAuth).

→ Rien à faire normalement. (Optionnel sécurité : régénère la clé secrète avec
`python -c "import secrets; print(secrets.token_hex(32))"` et remplace
`FLASK_SECRET_KEY` dans `.env`.)

⚠️ **YouTube OAuth** : dans Google Cloud Console (écran OAuth de l'app), l'URI de
redirection autorisée doit être **`https://edgerunners.fr/api/youtube/callback`**
(sinon la connexion d'une chaîne échouera). À vérifier une fois.

La base de données SQLite se crée **toute seule** au 1er démarrage (fraîche, vide).

---

## 5. Démarrer + HTTPS

1. **Setup Python App** → ton app → **RESTART**
2. cPanel → **SSL/TLS Status** → active **AutoSSL** (Let's Encrypt, gratuit) sur
   `edgerunners.fr` si pas déjà fait.
3. Ouvre **https://edgerunners.fr** → tu dois voir le gate Night City. 🎉

> Erreur 500 ? cPanel → **Setup Python App** → logs, ou `stderr.log` dans le
> dossier de l'app.

---

## 6. Te déclarer boss (IMPORTANT, à faire en 1er)

1. Sur https://edgerunners.fr, **triple-clic sur le kanji サムライ** en bas du gate
   → passe en mode ROOT (gold) → entre le **BOSS_PASSWORD**.
2. Va dans **SURVEILLANCE** → clique **★ MÉMORISER CET APPAREIL** (tu ne
   retaperas plus le mot de passe sur cet appareil).
3. Clique **⚠ PURGER — NE GARDER QUE MOI** → efface tout appareil/IP de test,
   ne garde que le tien.

---

## 7. Donner l'accès à un invité

Donne-lui juste le **ACCESS_PASSWORD** (guest). Il devra se reconnecter à chaque
session, n'aura accès qu'à l'accueil (pas aux outils, pas à la surveillance, pas
aux clés API).

---

## 8. Activer la production automatique (CRON)

Pour que Delamain produise + programme les vidéos **tout seul** (même quand
personne n'est sur le site), il faut un CRON qui « pousse » l'atelier régulièrement.

1. cPanel → section **Avancé** → **« Cron Jobs » (Tâches planifiées)**
2. **Common settings** → choisis **« Toutes les 10 minutes »** (`*/10 * * * *`)
3. **Command** → colle (remplace `CE_SECRET` par la valeur **WORKER_CRON_SECRET**
   de ton `.env`) :
   ```bash
   curl -s "https://edgerunners.fr/api/delamain/worker/tick?key=CE_SECRET" >/dev/null 2>&1
   ```
4. **Add New Cron Job**.

> Chaque appel fait avancer la production d'**une étape** (1 rendu/publication à
> la fois). Les appels qui se chevauchent ne font rien (verrou anti-doublon). Sans
> ce CRON, la production n'avance que quand tu as Delamain ouvert dans le navigateur.

⚠️ **Fuseau horaire** : pour que les heures de publication programmées soient
exactes, le serveur doit être en **Europe/Paris**. cPanel n'expose pas toujours le
fuseau ; en cas de décalage à l'usage, on ajustera (l'heure est interprétée dans le
fuseau du serveur).

---

## Après une mise à jour du code

1. Re-upload les fichiers modifiés (Gestionnaire de fichiers)
2. **Setup Python App** → **RESTART**

> ⚠️ Si ton ami renvoie un zip d'un outil, ré-applique les retouches directes
> (selects, recherche de voix, suppression Studio HeyGen) — demande-moi.

---

## Sécurité (déjà en place, vérifié)

- Tout le site est derrière le gate (mot de passe). Guests bloqués sur outils /
  surveillance / API (403/redirect).
- `config.js` (clés API) servi **uniquement** derrière le gate boss
  (`/toolfiles/`), jamais via une URL publique. Path traversal bloqué.
- Mots de passe comparés en temps constant (anti-timing), anti-bruteforce
  (verrou après 8 essais ratés / 10 min), aucun mot de passe en dur dans le code.
- HTTPS forcé + HSTS en prod, cookies httponly + Secure + SameSite.
- `FLASK_ENV=production` → aucun mode debug exposé.
- **Connexion auto = par appareil uniquement** (cookie secret aléatoire), JAMAIS
  par IP. Une IP est partageable et usurpable (X-Forwarded-For) → ne donne aucun
  accès. C'est pour ça qu'à l'étape 6 tu « mémorises ton appareil » (pas ton IP).
- Secret du CRON (`WORKER_CRON_SECRET`) comparé en temps constant ; secret vide
  = accès cron refusé (pas d'ouverture par défaut).
