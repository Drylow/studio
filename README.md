# Drylow Studio

TubeGen local avec Flask + Fal AI + ElevenLabs.

## Prerequisites

- Python 3.10+
- `ffmpeg` dans le PATH systeme

## Install

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Environment variables

Cree un fichier `.env`:

```env
FAL_API_KEY=your_fal_key
ELEVENLABS_API_KEY=your_elevenlabs_key
FLASK_SECRET_KEY=change-this-in-production
COOKIE_SECURE=0
```

`COOKIE_SECURE=1` en HTTPS (prod).

## Run (local)

```bash
python app.py
```

Puis ouvrir `http://127.0.0.1:5000`.

## Auth and projects

- Systeme de comptes actif (`/register`, `/login`, `/logout`)
- Les projets sont lies au compte connecte (`user_id`)
- Les endpoints de projets et les operations fichier par projet sont proteges

## Production notes

- Utiliser `gunicorn` derriere `nginx`
- Activer HTTPS (Let's Encrypt)
- Remplacer stockage local media par stockage objet (S3-compatible) si besoin
