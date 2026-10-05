"""One developer pass per cron invocation; never run inside a web request."""

import argparse
from dotenv import load_dotenv
from studio.store import ROOT
from studio.worker import worker_application
from studio.development import Config, check_setup, run_once


def main():
    parser = argparse.ArgumentParser(description="Exécuteur de modifications Delamain")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Contrôler Git, compilation et version publique sans modifier le site",
    )
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    app = worker_application()
    if app.config["PREVIEW"]:
        raise SystemExit("L’aperçu ne modifie pas le site hébergé.")
    store = app.extensions["studio_store"]
    try:
        if args.check:
            check_setup(store, Config.environment())
            print("Git en lecture/écriture, npm et version publique vérifiés.")
        else:
            run_once(store)
    except Exception:
        raise SystemExit(
            "Exécuteur arrêté. Consulte Réglages → Modifications du site et le guide de connexion."
        )


if __name__ == "__main__":
    main()
