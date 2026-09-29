import os
import sys

# Sur o2switch (CloudLinux), Passenger lance déjà ce fichier avec le python du
# virtualenv (un wrapper l.v.e-manager). PAS de re-exec ici : ça partirait en
# boucle infinie car sys.executable (python réel) != le lien du virtualenv.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Variables d'environnement depuis .env (cPanel ne les injecte pas toujours).
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except Exception:
    pass

os.environ.setdefault("FLASK_ENV", "production")

from app import app as application  # noqa: E402
