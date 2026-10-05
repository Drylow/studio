"""Analyses de 4–6 minutes, sources affichées et contrôle avant livraison.

  python production/news_brief.py voice <dossier>
  python production/news_brief.py build <dossier>
  python production/news_brief.py send <dossier> [--dry-run]
  python production/news_brief.py postmatch <dossier> <event> [--watch]

postmatch attend une fin de match confirmée et écrit les faits à relire.
Il ne génère pas une analyse tactique à partir du seul score, ni ne publie.
"""
import argparse
import json
import time
from pathlib import Path

from common import WORK
from services import news_brief, news_postmatch


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("voice", "build"):
        sub.add_parser(command).add_argument("job", type=Path)
    delivery = sub.add_parser("send")
    delivery.add_argument("job", type=Path)
    delivery.add_argument("--dry-run", action="store_true")
    match = sub.add_parser("postmatch")
    match.add_argument("job", type=Path)
    match.add_argument("event")
    match.add_argument("--league", default="uefa.nations")
    match.add_argument("--teams", nargs=2)
    match.add_argument("--watch", action="store_true")
    match.add_argument("--hours", type=float, default=8)
    args = parser.parse_args()
    args.job.mkdir(parents=True, exist_ok=True)
    if args.command == "send":
        from services import news_brief_discord
        try:
            news_brief_discord.send(args.job, WORK, args.dry_run)
        except (ValueError, RuntimeError) as exc:
            raise SystemExit(str(exc)) from None
        return
    if args.command in ("voice", "build"):
        plan = json.loads((args.job / "brief.json").read_text(encoding="utf-8"))
        if args.command == "voice":
            result = news_brief.voice(plan, Path(WORK) / "news_brief" / args.job.name)
            print(f"Voix prête : {result['duration']:.1f} secondes.", flush=True)
        else:
            news_brief.build(args.job, WORK, log=lambda s: print(s, flush=True))
        return
    deadline = time.monotonic() + args.hours * 3600
    while True:
        try:
            data = news_postmatch.summary(args.event, args.league)
            news_brief.save_json(args.job / "match_raw.json", data)
            final = news_postmatch.facts(data, args.event, args.teams)
            news_brief.save_json(args.job / "match_facts.json", final)
            news_brief.save_json(args.job / "match_status.json", {"status": "facts_ready", "event": args.event})
            print("Résultat final disponible : faits enregistrés, relecture du résumé requise.", flush=True)
            return
        except news_postmatch.MatchNotFinished as exc:
            news_brief.save_json(args.job / "match_status.json", {"status": "waiting", "event": args.event,
                                                                  "message": str(exc)})
            print(str(exc), flush=True)
            if not args.watch:
                return
        if time.monotonic() >= deadline:
            raise SystemExit("Délai dépassé : relancer la même commande reprend l'attente.")
        time.sleep(45)


if __name__ == "__main__":
    main()
