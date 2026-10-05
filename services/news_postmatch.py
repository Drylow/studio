"""Read a soccer result without turning a scheduled/live score into a final score."""
import datetime
import json
import re
import urllib.request


class MatchNotFinished(ValueError):
    pass


def summary(event, league="uefa.nations"):
    if not re.fullmatch(r"\d+", str(event)) or not re.fullmatch(r"[a-z.]+", league):
        raise ValueError("Identifiant de match ou compétition invalide.")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary?event={event}"
    req = urllib.request.Request(url, headers={"User-Agent": "EdgerunnersStudio/1.0"})
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.load(response)


def _score(value):
    if isinstance(value, dict):
        value = value.get("displayValue", value.get("value"))
    if isinstance(value, bool) or not re.fullmatch(r"\d+", str(value)):
        raise ValueError("Score final absent ou invalide : aucune vidéo ne sera créée.")
    return int(value)


def facts(data, event, expected_teams=None):
    header = data.get("header") or {}
    if str(header.get("id")) != str(event):
        raise ValueError("La réponse correspond à un autre match.")
    comps = header.get("competitions") or []
    if len(comps) != 1:
        raise ValueError("Match ambigu ou absent.")
    competition = comps[0]
    status = (competition.get("status") or {}).get("type") or {}
    if status.get("completed") is not True or status.get("state") != "post":
        raise MatchNotFinished("Match pas terminé : résumé en attente du résultat final.")
    if status.get("name") not in ("STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FINAL_AET", "STATUS_FINAL_PEN"):
        raise MatchNotFinished("Fin de match non confirmée (report, abandon ou statut inconnu).")
    competitors = competition.get("competitors") or []
    teams = {c.get("homeAway"): c for c in competitors}
    if len(competitors) != 2 or set(teams) != {"home", "away"}:
        raise ValueError("Les deux équipes ne sont pas identifiées.")
    names = [teams[side]["team"]["displayName"] for side in ("home", "away")]
    if expected_teams and set(names) != set(expected_teams):
        raise ValueError("Les équipes ne correspondent pas au match attendu.")
    final = {"event": str(event), "kickoff": competition.get("date"),
             "status": status["name"], "status_label": status.get("detail"),
             "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "teams": [{"name": teams[side]["team"]["displayName"], "side": side,
                        "score": _score(teams[side].get("score"))} for side in ("home", "away")],
             "source": f"https://www.espn.com/soccer/match/_/gameId/{event}"}
    penalties = [teams[side].get("shootoutScore") for side in ("home", "away")]
    if status["name"] == "STATUS_FINAL_PEN":
        if any(p is None for p in penalties):
            raise ValueError("Résultat des tirs au but absent.")
        final["penalties"] = [_score(p) for p in penalties]
    # Preserve only supplied statistics and scoring events. Do not infer tactics,
    # lineups, qualification or players' quotes from the score alone.
    final["statistics"] = (data.get("boxscore") or {}).get("teams") or []
    final["scoring_plays"] = data.get("scoringPlays") or []
    return final
