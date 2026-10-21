"""Text-only contract checks; no image processing or external API calls."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch
import tempfile
import json

spec = importlib.util.spec_from_file_location("visual_audit", Path(__file__).with_name("visual_audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def response():
    return {"confidence": .95, "summary": "Consistent image.", "checks": [
        {"category": c, "severity": "none", "reason": "Visible evidence checked."} for c in audit.CATEGORIES]}


class VisualAuditTests(unittest.TestCase):
    def test_complete_confident_check_passes(self):
        self.assertEqual(audit.validate(response())["decision"], "pass")

    def test_major_defect_rejects_even_if_response_claims_pass(self):
        data = response()
        data["decision"] = "pass"
        data["checks"][3]["severity"] = "major"
        self.assertEqual(audit.validate(data)["decision"], "reject")

    def test_background_cast_cannot_be_omitted_or_hidden_by_correct_hero(self):
        data = response()
        background = next(c for c in data["checks"] if c["category"] == "background_cast")
        background.update(severity="major", reason="Rear patron has a long human face and flesh skin despite the round white reference.")
        self.assertEqual(audit.validate(data)["decision"], "reject")
        data["checks"].remove(background)
        with self.assertRaises(ValueError):
            audit.validate(data)

    def test_uncertainty_minor_and_low_confidence_require_review(self):
        for level in ("uncertain", "minor"):
            data = response()
            data["checks"][3]["severity"] = level
            self.assertEqual(audit.validate(data)["decision"], "needs_review")
        data = response()
        data["confidence"] = .6
        self.assertEqual(audit.validate(data)["decision"], "needs_review")

    def test_missing_category_cannot_pass(self):
        data = response()
        data["checks"].pop()
        with self.assertRaises(ValueError):
            audit.validate(data)

    def test_duplicate_category_cannot_hide_a_missing_one(self):
        data = response()
        data["checks"][3] = dict(data["checks"][0])
        with self.assertRaises(ValueError):
            audit.validate(data)

    def test_desk_camera_risk_escalates_even_when_model_misses_the_bug(self):
        result = audit.validate(response())
        routed = audit.route_primary(result, {"risk_flags": ["desk_camera_change"]})
        self.assertEqual(routed["decision"], "pass")
        self.assertTrue(routed["requires_primary_review"])
        self.assertFalse(audit.route_primary(result, {})["requires_primary_review"])
        with self.assertRaises(ValueError):
            audit.route_primary(result, {"risk_flags": ["unsupported"]})

    def test_invalid_confidence_or_severity_or_empty_evidence_fails_closed(self):
        for value in (True, -1, 2, None, "high"):
            data = response()
            data["confidence"] = value
            with self.assertRaises(ValueError):
                audit.validate(data)
        for field, value in (("severity", "probably_fine"), ("reason", "")):
            data = response()
            data["checks"][3][field] = value
            with self.assertRaises(ValueError):
                audit.validate(data)


class ReceiptTests(unittest.IsolatedAsyncioTestCase):
    async def test_identical_input_reuses_receipt_and_changed_source_invalidates_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.txt"
            source.write_bytes(b"original fixture bytes")
            item = {"id": "one", "path": str(source), "references": []}
            chat = AsyncMock(return_value=json.dumps(response()))
            with patch.object(audit.sys, "platform", "linux"), patch.object(audit, "image_part", return_value={"type": "text", "text": "mock pixels"}):
                first = await audit.review(item, "fixture-model", root / "receipts", chat)
                second = await audit.review(item, "fixture-model", root / "receipts", chat)
                self.assertEqual(first["cache_key"], second["cache_key"])
                self.assertEqual(chat.await_count, 1)
                self.assertEqual(first["source"], "cli_proxy_vision")
                self.assertEqual(first["state"], "proxy_reviewed")
                source.write_bytes(b"changed fixture bytes")
                third = await audit.review(item, "fixture-model", root / "receipts", chat)
                self.assertNotEqual(first["cache_key"], third["cache_key"])
                self.assertEqual(chat.await_count, 2)
                self.assertEqual(chat.await_args.kwargs["attempts"], 1)
                self.assertIs(chat.await_args.kwargs["hedge"], False)

    async def test_proxy_error_is_uncertain_and_not_automatically_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.txt"
            source.write_bytes(b"fixture")
            item = {"id": "one", "path": str(source), "references": []}
            chat = AsyncMock(side_effect=TimeoutError("test timeout"))
            with patch.object(audit.sys, "platform", "linux"), patch.object(audit, "image_part", return_value={"type": "text", "text": "mock pixels"}):
                result = await audit.review(item, "fixture-model", root / "receipts", chat)
                await audit.review(item, "fixture-model", root / "receipts", chat)
            self.assertEqual(result["state"], "needs_review")
            self.assertEqual(result["decision"], "needs_review")
            self.assertEqual(chat.await_count, 1)


if __name__ == "__main__":
    unittest.main()
