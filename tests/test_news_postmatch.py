import copy
import unittest

from services.news_postmatch import MatchNotFinished, facts


def finished():
    # Fictional test data, never used as production match results.
    return {"header": {"id": "123", "competitions": [{
        "date": "2026-10-05T18:45Z",
        "status": {"type": {"name": "STATUS_FULL_TIME", "state": "post", "completed": True}},
        "competitors": [
            {"homeAway": "away", "team": {"displayName": "Away test team"}, "score": "1"},
            {"homeAway": "home", "team": {"displayName": "Home test team"}, "score": "2"},
        ],
    }]}}


class PostmatchTest(unittest.TestCase):
    def test_reads_final_and_orders_home_before_away(self):
        result = facts(finished(), "123", ["Home test team", "Away test team"])
        self.assertEqual([(t["name"], t["score"]) for t in result["teams"]],
                         [("Home test team", 2), ("Away test team", 1)])
        self.assertEqual(result["scoring_plays"], [])
        self.assertEqual(result["statistics"], [])

    def test_scheduled_and_live_scores_never_become_final(self):
        for name, state in [("STATUS_SCHEDULED", "pre"), ("STATUS_IN_PROGRESS", "in")]:
            data = finished()
            data["header"]["competitions"][0]["status"]["type"] = {
                "name": name, "state": state, "completed": False}
            with self.subTest(name=name), self.assertRaises(MatchNotFinished):
                facts(data, "123")

    def test_abandoned_is_not_a_finished_match(self):
        data = finished()
        data["header"]["competitions"][0]["status"]["type"]["name"] = "STATUS_ABANDONED"
        with self.assertRaises(MatchNotFinished):
            facts(data, "123")

    def test_does_not_default_missing_score_to_zero(self):
        data = finished()
        del data["header"]["competitions"][0]["competitors"][0]["score"]
        with self.assertRaises(ValueError):
            facts(data, "123")

    def test_accepts_explicit_zero_and_score_objects(self):
        data = finished()
        data["header"]["competitions"][0]["competitors"][0]["score"] = {"displayValue": "0"}
        self.assertEqual(facts(data, "123")["teams"][1]["score"], 0)

    def test_rejects_different_event_and_teams(self):
        with self.assertRaises(ValueError):
            facts(finished(), "456")
        with self.assertRaises(ValueError):
            facts(finished(), "123", ["France", "Belgium"])

    def test_shootout_needs_both_penalty_scores(self):
        data = finished()
        comp = data["header"]["competitions"][0]
        comp["status"]["type"]["name"] = "STATUS_FINAL_PEN"
        with self.assertRaises(ValueError):
            facts(data, "123")
        for competitor, score in zip(comp["competitors"], [3, 4]):
            competitor["shootoutScore"] = score
        self.assertEqual(facts(data, "123")["penalties"], [4, 3])

    def test_preserves_supplied_evidence_without_inventing_players(self):
        data = finished()
        data["scoringPlays"] = [{"text": "Test goal", "clock": {"displayValue": "20'"}}]
        data["boxscore"] = {"teams": [{"team": {"displayName": "Home test team"},
                                       "statistics": [{"name": "totalShots", "value": "10"}]}]}
        before = copy.deepcopy(data)
        result = facts(data, "123")
        self.assertEqual(result["scoring_plays"], data["scoringPlays"])
        self.assertEqual(result["statistics"], data["boxscore"]["teams"])
        self.assertEqual(data, before)


if __name__ == "__main__":
    unittest.main()
