"""Frozen-contract, evidence and restart tests: no media or external requests."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch

spec = importlib.util.spec_from_file_location("production_watch", Path(__file__).with_name("production_watch.py"))
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


def fixture(root):
    project = root / "project"
    project.mkdir()
    style = root / "style"
    style.mkdir()
    (style / "drawing.bin").write_bytes(b"approved drawing fixture")
    (project / "one.bin").write_bytes(b"candidate fixture")
    stage = root / "film" / "frozen-stage"
    stage.mkdir(parents=True)
    reference = {"owner": "style", "path": "drawing.bin", "sha256": watch.sha(style / "drawing.bin"),
                 "role": "style-only", "review_state": "verified"}
    expected = {"shot_id": 1, "asset_id": "shot-001-v1", "prompt": "Primary-authored action.",
                "references": [reference], "characters": ["Worker"], "authored_action": "Worker reads a file.",
                "narration": "You read the file.", "risk_flags": []}
    row = dict(expected, state="done", path="one.bin", sha256=watch.sha(project / "one.bin"))
    watch.write(stage / "shot-001-v1-receipt.json", row)
    film = {"key": "fixture", "directory": str(stage.parent), "project_root": str(project),
            "style_root": str(style), "stages": [str(stage)], "expected": [expected],
            "timings": [{"id": 1, "start": 0, "end": 6, "duration": 6}], "automatic_render": False}
    item = watch.review_item(film, expected, row)
    proof = {"id": 1, "item": item, "source": "cli_proxy_vision", "state": "proxy_reviewed",
             "hashes": [reference["sha256"], row["sha256"]], "confidence": .95,
             "checks": [{"category": c, "severity": "none", "reason": "Specific fixture evidence."}
                        for c in watch.audit.CATEGORIES], "summary": "Consistent fixture.", "cache_key": "fixture-key"}
    return film, row, proof


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.film, self.row, self.proof = fixture(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def evaluate(self, proof=True):
        evidence = {(self.proof["item"]["path"], self.row["sha256"]): self.proof} if proof else {}
        return watch.select(self.film, {self.row["asset_id"]: self.row}, evidence)

    def test_exact_routine_pass_is_attributed_never_primary(self):
        selected, pending, jobs = self.evaluate()
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["source"], "cli_proxy_vision")
        self.assertFalse(selected[0]["primary_inspection_claimed"])
        self.assertEqual((pending, jobs), ([], []))

    def test_missing_proof_requests_audit_without_approval(self):
        selected, pending, jobs = self.evaluate(False)
        self.assertFalse(selected)
        self.assertEqual(pending[0]["state"], "awaiting_proxy_review")
        self.assertEqual(len(jobs), 1)

    def test_scene_anchor_always_requires_actual_primary_review(self):
        self.film["expected"][0]["requires_primary"] = True
        selected, pending, jobs = self.evaluate()
        self.assertFalse(selected)
        self.assertEqual(pending[0]["state"], "awaiting_primary_anchor")
        self.assertFalse(jobs)

    def test_primary_rejection_cannot_be_overruled_by_proxy(self):
        watch.write(Path(self.film["directory"]) / "primary-rejections.json", [self.row])
        selected, pending, _ = self.evaluate()
        self.assertFalse(selected)
        self.assertEqual(pending[0]["state"], "primary_rejected")

    def test_exact_actual_primary_review_is_retained(self):
        primary = dict(self.row, state="verified", source="primary_agent_actual_pixel_inspection", notes="Actual inspection.")
        watch.write(Path(self.film["directory"]) / "primary-shot-review.json", [primary])
        selected, pending, _ = self.evaluate(False)
        self.assertEqual(selected[0]["source"], primary["source"])
        self.assertFalse(pending)

    def test_owner_flag_and_desk_risk_hold_even_a_pass(self):
        for risk in ("owner_flagged", "desk_camera_change"):
            self.film["expected"][0]["risk_flags"] = [risk]
            selected, pending, _ = self.evaluate()
            self.assertFalse(selected)
            self.assertEqual(pending[0]["state"], "awaiting_primary_review")

    def test_minor_uncertain_and_major_are_never_silently_dismissed(self):
        for level in ("minor", "uncertain", "major"):
            self.proof["checks"][0]["severity"] = level
            selected, pending, _ = self.evaluate()
            self.assertFalse(selected)
            self.assertEqual(pending[0]["state"], "awaiting_primary_review")

    def test_changed_context_invalidates_old_audit(self):
        self.film["expected"][0]["authored_action"] = "Worker returns the file."
        selected, pending, jobs = self.evaluate()
        self.assertFalse(selected)
        self.assertEqual(len(jobs), 1)

    def test_changed_image_or_reference_never_passes(self):
        (Path(self.film["project_root"]) / "one.bin").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_changed_prompt_or_ordered_references_never_passes(self):
        self.row["prompt"] = "Unexpected prompt."
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_old_success_cannot_satisfy_expected_new_version(self):
        self.film["expected"][0]["asset_id"] = "shot-001-v2"
        selected, pending, jobs = self.evaluate()
        self.assertFalse(selected)
        self.assertEqual(pending[0]["state"], "awaiting_image")
        self.assertFalse(jobs)

    def test_unfrozen_authoring_never_generates_or_renders(self):
        self.film["expected"][0].update(frozen=False, prompt="", references=[])
        watch.validate_contract(self.film)
        selected, pending, jobs = self.evaluate()
        self.assertFalse(selected)
        self.assertEqual(pending[0]["state"], "awaiting_primary_authoring")
        self.assertFalse(jobs)

    def test_missing_timing_and_duplicate_asset_are_rejected(self):
        self.film["timings"].append(dict(self.film["timings"][0]))
        with self.assertRaises(ValueError):
            watch.validate_contract(self.film)

    def test_asset_path_cannot_leave_project(self):
        self.row["path"] = "../outside.bin"
        with self.assertRaises(ValueError):
            self.evaluate()


class TickTests(unittest.IsolatedAsyncioTestCase):
    async def test_continuous_tick_reuses_receipt_and_saves_proxy_attribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            film, row, proof = fixture(base)
            reviewer = AsyncMock(return_value=proof)
            config = {"base": str(base), "films": [film], "audit_model": "fixture-model"}
            await watch.tick(config, reviewer=reviewer)
            await watch.tick(config, reviewer=reviewer)
            await watch.tick(config, reviewer=reviewer)
            self.assertEqual(reviewer.await_count, 1)
            selected = watch.read(Path(film["directory"]) / "continuous-qc" / "selected.json")
            self.assertEqual(selected[0]["source"], "cli_proxy_vision")
            self.assertFalse((Path(film["directory"]) / "render").exists())

    async def test_pause_prevents_all_audits_and_render_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            film, _, _ = fixture(base)
            watch.write(base / "OWNER_PAUSED.json", {"paused": True})
            reviewer = AsyncMock()
            await watch.tick({"base": str(base), "films": [film]}, reviewer=reviewer)
            reviewer.assert_not_awaited()
            self.assertEqual(watch.read(base / "continuous-status.json")["state"], "owner_paused")

    async def test_invalid_contract_does_not_stop_another_film(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            film, _, _ = fixture(base)
            invalid = copy.deepcopy(film)
            invalid['key'] = 'bad-fixture'
            invalid['timings'] = []
            result = await watch.tick({'base': str(base), 'films': [invalid, film]}, do_audit=False)
            self.assertEqual(result[0]['state'], 'blocked_contract')
            self.assertEqual(result[1]['state'], 'in_progress')


class RenderHandoffTests(unittest.TestCase):
    def test_complete_gate_dispatches_once_without_touching_original_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            film, row, proof = fixture(base)
            selected, _, _ = watch.select(film, {row['asset_id']: row},
                                         {(proof['item']['path'], row['sha256']): proof})
            voice = Path(film['project_root']) / 'voice.bin'
            voice.write_bytes(b'original narration fixture')
            worker = base / 'worker.py'
            renderer = base / 'renderer.py'
            worker.write_bytes(b'# frozen worker fixture')
            renderer.write_bytes(b'# frozen renderer fixture')
            project = {'script': 'Original script.', 'voiceover': {'file': 'voice.bin'}}
            film.update(automatic_render=True, project_id='fixture',
                        script_sha256=watch.hashlib.sha256(project['script'].encode()).hexdigest(),
                        voice_sha256=watch.sha(voice), render_worker=str(worker),
                        render_worker_sha256=watch.sha(worker), renderer=str(renderer),
                        renderer_sha256=watch.sha(renderer))
            fake = types.ModuleType('app')
            fake.store = types.SimpleNamespace(get_project=lambda _: project)
            with patch.dict('sys.modules', {'app': fake}), patch.object(watch.subprocess, 'Popen') as launch:
                launch.return_value.pid = 123
                self.assertEqual(watch.prepare_render(film, selected, base), 'render_dispatched')
                self.assertEqual(watch.prepare_render(film, selected, base), 'render_already_reserved')
                self.assertEqual(launch.call_count, 1)
                self.assertEqual(launch.call_args.args[0][0], 'flock')
            self.assertEqual(voice.read_bytes(), b'original narration fixture')
            plan = watch.read(Path(film['directory']) / 'render' / 'final-plan.json')
            self.assertEqual(plan['voice_sha256'], film['voice_sha256'])
            self.assertEqual(plan['transition_seconds'], .5)

    def test_incomplete_sources_never_dispatch_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            film, _, _ = fixture(Path(tmp))
            film['automatic_render'] = True
            with patch.object(watch.subprocess, 'Popen') as launch:
                self.assertEqual(watch.prepare_render(film, [], tmp), 'not_ready')
                launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
