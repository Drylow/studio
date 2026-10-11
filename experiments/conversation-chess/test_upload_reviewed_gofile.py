"""Local real-media fixtures and mocked GoFile responses; never uses the network."""
from contextlib import redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("reviewed_gofile", HERE / "upload-reviewed-gofile.py")
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


class Response:
    status_code = 200

    def __init__(self, data):
        self.data = data

    def json(self):
        return {"status": "ok", "data": self.data}


class FakeSession:
    """In-memory API contract test, not an upload client."""
    def __init__(self, mismatch=False):
        self.children = {}
        self.gets, self.posts = [], []
        self.mismatch = mismatch

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        if url == "https://api.gofile.io/servers":
            return Response({"servers": [{"name": "store-test", "zone": "eu"}]})
        if url != "https://api.gofile.io/contents/folder-test":
            raise AssertionError("Unexpected API route")
        children = copy.deepcopy(self.children)
        if self.mismatch:
            children["1"]["size"] += 1
        return Response({"id": "folder-test", "type": "folder", "children": children})

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        name, stream, _ = kwargs["files"]["file"]
        data = stream.read()
        entry = {"type": "file", "name": name, "size": len(data), "md5": hashlib.md5(data).hexdigest()}
        self.children[str(len(self.children) + 1)] = entry
        result = {**entry, "parentFolder": "folder-test", "downloadPage": "https://gofile.io/d/Test123"}
        if len(self.posts) == 1:
            result["guestToken"] = "PRIVATE_TEST_TOKEN_DO_NOT_PRINT"
        return Response(result)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe required")
class ReviewedUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master_directory = tempfile.TemporaryDirectory(prefix="gofile-media-", dir="/tmp")
        cls.master = Path(cls.master_directory.name) / "source.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=blue:s=320x180:r=30:d=1",
                        "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=48000:duration=1",
                        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-threads", "1",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", str(cls.master)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.master_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="gofile-reviewed-", dir="/tmp")
        self.folder = Path(self.directory.name)
        self.manifest = self.folder / "delivery.json"
        source, movie = self.folder / "source.mp4", self.folder / "movie.mp4"
        shutil.copyfile(self.master, source)
        shutil.copyfile(self.master, movie)
        subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(movie), "-f", "null", "-"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        (self.folder / "full-av-decode.log").write_text("")
        (self.folder / "timeline.json").write_text('{"synthetic_fixture":true}\n')
        (self.folder / "MUSIC_CREDITS.txt").write_text("Synthetic test audio; no third-party music.\n")
        (self.folder / "description.txt").write_text("Synthetic local QA fixture.\n")
        (self.folder / "Titles.txt").write_text("Synthetic fixture title\n")
        Image.new("RGB", (320, 180), "blue").save(self.folder / "thumbnail.jpg")
        Image.new("RGB", (320, 180), "blue").save(self.folder / "reviewed-frame.png")
        sha = HELPER.hashes(movie)["sha256"]
        quality = {"accepted_for_final": True, "test_fixture": True}
        self.write("project.json", {"fps": 30, "duration_frames": 30, "width": 320, "height": 180,
            "original_source": str(source), "source_sha256": HELPER.hashes(source)["sha256"],
            "source_dimensions": [320, 180], "source_quality": quality,
            "timeline_file": str(self.folder / "timeline.json"),
            "timeline_sha256": HELPER.hashes(self.folder / "timeline.json")["sha256"],
            "music_attribution": {"file": "MUSIC_CREDITS.txt", "sha256": HELPER.hashes(self.folder / "MUSIC_CREDITS.txt")["sha256"]}})
        self.write("native.json", {"export_completed": True, "final_video": str(movie), "output_sha256": sha,
            "fps": 30, "duration_frames": 30, "source_dimensions": [320, 180], "source_quality": quality,
            "source_sha256": HELPER.hashes(source)["sha256"],
            "music_attribution": self.read("project.json")["music_attribution"]})
        self.write("technical.json", {"file": str(movie), "sha256": sha, "completed": True,
            "technical_audio_passed": True, "failures": [], "full_video_audio_decode_ok": True,
            "full_av_decode": {"returncode": 0, "log": "full-av-decode.log"},
            "probe": HELPER.probe(movie), "expected_frames": 30, "source_dimensions": [320, 180],
            "source_quality": quality})
        self.write("review.json", {"sha256": sha, "technical_audio_passed": True,
            "full_video_audio_decode_ok": True, "finished_render_visual_reviewed": True, "source_quality": quality,
            "sampled_visual_review": {"completed": True, "reviewed_images": 1,
                "method": "Synthetic solid-blue real-media fixture; retained proof frame.",
                "evidence_files": ["reviewed-frame.png"]}})
        self.write("delivery.json", {"kind": "youtube-test", "video": "movie.mp4", "thumbnail": "thumbnail.jpg",
            "titles": "Titles.txt", "title": "Synthetic fixture title", "description": "description.txt",
            "music_credits": "MUSIC_CREDITS.txt", "review": "review.json", "technical_review": "technical.json",
            "prepared_manifest": "project.json", "native_receipt": "native.json"})
        self.addCleanup(self.directory.cleanup)

    def write(self, filename, data):
        (self.folder / filename).write_text(json.dumps(data))

    def read(self, filename):
        return json.loads((self.folder / filename).read_text())

    def change(self, filename, **changes):
        data = self.read(filename)
        data.update(changes)
        self.write(filename, data)

    def test_valid_dry_run_has_five_files_and_never_creates_a_network_session(self):
        with patch.object(HELPER.requests, "Session", side_effect=AssertionError("No network in dry run")), \
                redirect_stdout(io.StringIO()) as output:
            HELPER.run(self.manifest)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "validated-no-upload")
        self.assertEqual(len(result["files"]), 5)
        self.assertIn("Music credits", (self.folder / "description_with_credits.txt").read_text())
        self.assertFalse((self.folder / "gofile-owner-private.json").exists())

    def test_changed_video_sha_is_rejected_before_network_or_description_generation(self):
        with (self.folder / "movie.mp4").open("ab") as stream:
            stream.write(b"changed-after-review")
        with self.assertRaisesRegex(ValueError, "Exact video SHA"):
            HELPER.prepare(self.manifest)
        self.assertFalse((self.folder / "description_with_credits.txt").exists())

    def test_full_decode_requires_completed_result_and_retained_clean_log(self):
        self.change("technical.json", completed=False)
        with self.assertRaisesRegex(ValueError, "actual full A/V decode"):
            HELPER.prepare(self.manifest)
        self.change("technical.json", completed=True)
        (self.folder / "full-av-decode.log").write_text("decode error")
        with self.assertRaisesRegex(ValueError, "error log"):
            HELPER.prepare(self.manifest)

    def test_visual_approval_without_retained_images_is_rejected(self):
        data = self.read("review.json")
        del data["sampled_visual_review"]["evidence_files"]
        self.write("review.json", data)
        with self.assertRaisesRegex(ValueError, "retained evidence_files"):
            HELPER.prepare(self.manifest)

    def test_actual_profile_cannot_be_relabelled(self):
        self.change("project.json", width=1920, height=1080)
        with self.assertRaisesRegex(ValueError, "Actual export profile"):
            HELPER.prepare(self.manifest)

    def test_audio_finished_child_keeps_native_parent_sha_and_requires_explicit_qa_provenance(self):
        parent, child = self.folder / "movie.mp4", self.folder / "finished.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(parent), "-map", "0:v:0", "-map", "0:a:0",
                        "-c:v", "copy", "-af", "volume=1.25", "-c:a", "aac", str(child)], check=True)
        self.change("project.json", segments=[{"kind": "source", "start_frame": 0, "end_frame": 30}])
        child_info = HELPER.hashes(child)
        self.write("finish.json", {"parent_video": str(parent), "parent_sha256": HELPER.hashes(parent)["sha256"],
            "output_video": str(child), "sha256": child_info["sha256"], "bytes": child_info["bytes"],
            "picture_stream_unchanged": True, "picture_stream_sha256": HELPER.picture_hash(parent),
            "preserve_grading_music": True, "full_decode_passed": True,
            "source_output_sample_ranges": [[0, 48000]], "source_interval_policy": "half-open-sample-index",
            "audio_sample_rate": 48000,
            "intro_analysis_outro_audio_gain_db": 0, "source_audio_gain_db": 1.9382, "source_output_ranges": [[0, 1]]})
        self.change("delivery.json", video="finished.mp4", audio_finishing_receipt="finish.json")
        self.change("technical.json", file=str(child), sha256=child_info["sha256"], probe=HELPER.probe(child))
        self.change("review.json", sha256=child_info["sha256"])
        native_sha = self.read("native.json")["output_sha256"]
        with self.assertRaisesRegex(ValueError, "Technical QA must explicitly validate"):
            HELPER.prepare(self.manifest)
        self.change("technical.json", audio_finishing={"receipt_sha256": HELPER.hashes(self.folder / "finish.json")["sha256"],
            "output_sha256": child_info["sha256"], "parent_sha256": native_sha})
        kit = HELPER.prepare(self.manifest)
        self.assertEqual(kit["files"][0]["sha256"], child_info["sha256"])
        self.assertNotEqual(child_info["sha256"], native_sha)
        self.assertEqual(self.read("native.json")["output_sha256"], native_sha)

    def test_preview_does_not_pretend_source_quality_is_accepted(self):
        for name in ("project.json", "native.json", "technical.json", "review.json"):
            self.change(name, source_quality={"accepted_for_final": False})
        with self.assertRaisesRegex(ValueError, "Source quality must be accepted"):
            HELPER.prepare(self.manifest)
        self.change("delivery.json", kind="preview")
        self.assertEqual(HELPER.prepare(self.manifest)["data"]["kind"], "preview")

    def test_no_added_music_requires_explicit_empty_music_tracks_not_invented_credits(self):
        self.change("project.json", music_attribution=None, segments=[{"kind": "source"}])
        self.change("native.json", music_attribution=None, music_segments=[])
        self.assertEqual(len(HELPER.prepare(self.manifest)["files"]), 5)
        self.change("project.json", segments=[{"kind": "analysis", "music_file": "unattributed.wav"}])
        with self.assertRaisesRegex(ValueError, "without prepared/native attribution"):
            HELPER.prepare(self.manifest)

    def test_final_requires_real_publication_evidence(self):
        self.change("delivery.json", kind="final")
        with self.assertRaisesRegex(ValueError, "explicit local file path"):
            HELPER.prepare(self.manifest)
        self.write("publication.json", {"sha256": HELPER.hashes(self.folder / "movie.mp4")["sha256"],
            "source_rights_verified": True, "music_rights_verified": True, "youtube_checks_complete": True,
            "youtube_copyright_status": "clear", "claims": [], "blocked_territories": [], "evidence_files": []})
        self.change("delivery.json", publication_review="publication.json")
        with self.assertRaisesRegex(ValueError, "must retain evidence_files"):
            HELPER.prepare(self.manifest)

    def test_pending_blocks_even_a_second_attempt_before_any_network(self):
        self.write("gofile-pending.json", {"outcome": "uncertain"})
        with patch.object(HELPER.requests, "Session", side_effect=AssertionError("No retry")), \
                self.assertRaisesRegex(RuntimeError, "Previous upload incomplete/uncertain"):
            HELPER.run(self.manifest, True)

    def test_mocked_api_readback_receipt_private_token_and_idempotence(self):
        fake = FakeSession()
        with patch.object(HELPER.requests, "Session", return_value=fake), redirect_stdout(io.StringIO()) as output:
            HELPER.run(self.manifest, True)
        receipt = self.read("gofile-receipt.json")
        self.assertEqual(len(fake.posts), 5)
        self.assertEqual(fake.gets[-1][0], "https://api.gofile.io/contents/folder-test")
        self.assertTrue(all(row["api_readback_matched"] for row in receipt["files"]))
        owner = self.folder / "gofile-owner-private.json"
        self.assertEqual(owner.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("PRIVATE_TEST_TOKEN", output.getvalue() + json.dumps(receipt))
        self.assertEqual(self.read("delivery.json")["gofile_url"], receipt["url"])
        self.assertFalse((self.folder / "gofile-pending.json").exists())
        with patch.object(HELPER.requests, "Session", side_effect=AssertionError("No duplicate upload")), \
                redirect_stdout(io.StringIO()) as repeated:
            HELPER.run(self.manifest, True)
        self.assertEqual(json.loads(repeated.getvalue())["status"], "already-uploaded")

    def test_readback_integrity_failure_never_creates_receipt_and_keeps_pending(self):
        with patch.object(HELPER.requests, "Session", return_value=FakeSession(mismatch=True)), \
                redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "readback MD5/bytes mismatch"):
            HELPER.run(self.manifest, True)
        self.assertTrue((self.folder / "gofile-pending.json").exists())
        self.assertFalse((self.folder / "gofile-receipt.json").exists())
        self.assertNotIn("gofile_url", self.read("delivery.json"))

    def test_freeze_covers_reviewed_evidence_not_only_the_film(self):
        kit = HELPER.prepare(self.manifest)
        Image.new("RGB", (320, 180), "red").save(self.folder / "reviewed-frame.png")
        with self.assertRaisesRegex(RuntimeError, "reviewed input changed"):
            HELPER.unchanged(kit)

    def test_json_changed_during_media_inspection_is_not_frozen_as_if_validated(self):
        real_probe = HELPER.probe
        changed = False
        def changing_probe(path):
            nonlocal changed
            if not changed:
                changed = True
                self.change("review.json", finished_render_visual_reviewed=False)
            return real_probe(path)
        with patch.object(HELPER, "probe", side_effect=changing_probe), \
                self.assertRaisesRegex(ValueError, "reviewed input changed while preparing"):
            HELPER.prepare(self.manifest)

    def test_binding_does_not_reparse_a_changed_manifest_into_a_different_kit(self):
        kit = HELPER.prepare(self.manifest)
        self.change("delivery.json", video="other.mp4")
        with self.assertRaisesRegex(RuntimeError, "manifest changed before binding"):
            HELPER.bind_delivery(kit, self.folder / "gofile-receipt.json", "https://gofile.io/d/Test123")
        self.assertNotIn("gofile_url", self.read("delivery.json"))

    def web_fixture(self):
        """Fresh pending POST acknowledgements plus retained official-browser evidence."""
        for name in ("gofile-receipt.json", "gofile-pending-confirmed.json"):
            (self.folder / name).unlink(missing_ok=True)
        delivery = self.read("delivery.json")
        delivery.pop("gofile_url", None)
        delivery.pop("upload_receipt", None)
        self.write("delivery.json", delivery)
        kit = HELPER.prepare(self.manifest)
        page, folder_id = "https://gofile.io/d/Test123", "folder-test"
        HELPER.save(self.folder / "gofile-owner-private.json", {
            "folder_id": folder_id, "url": page,
            "owner_token": "PRIVATE_WEB_FIXTURE_TOKEN_DO_NOT_PRINT"}, private=True)
        self.write("gofile-pending.json", {
            "fingerprint": kit["fingerprint"], "intended_files": copy.deepcopy(kit["files"]),
            "confirmed_files": copy.deepcopy(kit["files"]), "url": page})
        screenshot = self.folder / "public-listing.png"
        Image.new("RGB", (320, 180), "navy").save(screenshot)
        proof = {
            "public_url": page, "http_status": 200, "api_status": "ok",
            "folder_id": folder_id, "folder_type": "folder",
            "metadata": {"totalCount": 5, "totalPages": 1, "page": 1,
                         "pageSize": 100, "hasNextPage": False},
            "files": [{"id": "file-" + str(i), "type": "file", "name": row["filename"],
                       "size": row["bytes"], "md5": row["md5"]}
                      for i, row in enumerate(reversed(kit["files"]))],
            "expected_file_count": 5, "public_listing_matched": True,
            "expected": copy.deepcopy(kit["files"]),
            "screenshot_sha256": HELPER.hashes(screenshot)["sha256"],
            "generated_utc": "2026-10-11T12:00:00Z",
            "method": "Unmodified official GoFile web client; local synthetic test fixture.",
            "blocked_mutations": [],
            "direct_premium_api_readback_complete": False}
        self.write("public-browser-readback.json", proof)
        return kit, self.folder / "public-browser-readback.json", screenshot

    def reconcile_web(self, proof):
        with patch.object(HELPER.requests, "Session", side_effect=AssertionError("No network in web reconciliation")), \
                redirect_stdout(io.StringIO()) as output:
            HELPER.run(self.manifest, do_upload=False, verify_existing_web=proof)
        return output.getvalue()

    def assert_pending_not_bound(self):
        self.assertTrue((self.folder / "gofile-pending.json").is_file())
        self.assertFalse((self.folder / "gofile-pending-confirmed.json").exists())
        self.assertNotIn("gofile_url", self.read("delivery.json"))
        self.assertNotIn("upload_receipt", self.read("delivery.json"))

    def test_official_web_reconciliation_binds_only_the_exact_kit_and_is_offline_idempotent(self):
        kit, proof, screenshot = self.web_fixture()
        owner = self.folder / "gofile-owner-private.json"
        frozen = {path: HELPER.hashes(path)["sha256"] for path in
                  (proof, screenshot, owner, self.folder / "gofile-pending.json")}
        pending_bytes = (self.folder / "gofile-pending.json").read_bytes()
        with patch.object(HELPER, "ensure_private_ignored", wraps=HELPER.ensure_private_ignored) as ignored:
            output = self.reconcile_web(proof)
        ignored.assert_called_with(owner)
        receipt = self.read("gofile-receipt.json")
        self.assertEqual(receipt["fingerprint"], kit["fingerprint"])
        self.assertTrue(receipt["official_web_client_readback_complete"])
        self.assertIs(receipt["api_readback_complete"], False)
        self.assertIs(receipt["direct_premium_api_readback_complete"], False)
        self.assertEqual(receipt["files"], [{**row, "official_web_client_readback_matched": True}
                                          for row in kit["files"]])
        evidence = receipt["official_web_client_readback"]
        self.assertEqual(evidence["folder_id"], "folder-test")
        self.assertEqual(evidence["proof"], {"path": str(proof), "sha256": frozen[proof]})
        self.assertEqual(evidence["screenshot"], {"path": str(screenshot), "sha256": frozen[screenshot]})
        self.assertEqual(self.read("delivery.json")["gofile_url"], "https://gofile.io/d/Test123")
        self.assertEqual(self.read("delivery.json")["upload_receipt"], "gofile-receipt.json")
        self.assertFalse((self.folder / "gofile-pending.json").exists())
        archive = self.folder / "gofile-pending-confirmed.json"
        self.assertEqual(archive.read_bytes(), pending_bytes)
        self.assertEqual(HELPER.hashes(owner)["sha256"], frozen[owner])
        self.assertEqual(owner.stat().st_mode & 0o777, 0o600)
        repeated = self.reconcile_web(proof)
        self.assertEqual(self.read("gofile-receipt.json"), receipt)
        self.assertEqual(archive.read_bytes(), pending_bytes)
        self.assertNotIn("PRIVATE_WEB_FIXTURE_TOKEN", output + repeated + json.dumps(receipt)
                         + self.manifest.read_text())

    def test_web_reconciliation_rejects_incomplete_pending_changed_fresh_kit_and_unsafe_owner(self):
        cases = ("missing-confirmation", "altered-intention", "old-fingerprint", "changed-fresh-kit",
                 "public-owner", "unignored-owner")
        titles = (self.folder / "Titles.txt").read_bytes()
        for case in cases:
            with self.subTest(case=case):
                (self.folder / "Titles.txt").write_bytes(titles)
                _, proof, _ = self.web_fixture()
                pending = self.read("gofile-pending.json")
                if case == "missing-confirmation":
                    pending["confirmed_files"].pop()
                elif case == "altered-intention":
                    pending["intended_files"][0]["md5"] = "0" * 32
                elif case == "old-fingerprint":
                    pending["fingerprint"] = "0" * 64
                elif case == "changed-fresh-kit":
                    (self.folder / "Titles.txt").write_text("A newly edited title proposal\n")
                elif case == "public-owner":
                    (self.folder / "gofile-owner-private.json").chmod(0o644)
                self.write("gofile-pending.json", pending)
                pending_bytes = (self.folder / "gofile-pending.json").read_bytes()
                if case == "unignored-owner":
                    with patch.object(HELPER, "ensure_private_ignored",
                                      side_effect=ValueError("Private owner-token path is not ignored")), \
                            self.assertRaises((ValueError, RuntimeError)):
                        self.reconcile_web(proof)
                else:
                    with self.assertRaises((ValueError, RuntimeError)):
                        self.reconcile_web(proof)
                self.assert_pending_not_bound()
                self.assertFalse((self.folder / "gofile-receipt.json").exists())
                self.assertEqual((self.folder / "gofile-pending.json").read_bytes(), pending_bytes)

    def test_web_reconciliation_rejects_wrong_identity_status_and_duplicated_listing_entries(self):
        cases = ("proof-url", "owner-url", "pending-url", "folder-id", "owner-folder", "folder-type",
                 "http-error", "status-error", "duplicate-id", "duplicate-name", "nested-folder",
                 "extra-file", "expected-rows", "matched-flag", "expected-count", "api-success-claim",
                 "content-mutation", "missing-method")
        for case in cases:
            with self.subTest(case=case):
                _, proof, _ = self.web_fixture()
                data = self.read(proof.name)
                if case == "proof-url":
                    data["public_url"] = "https://gofile.io/d/Another"
                elif case == "owner-url":
                    self.change("gofile-owner-private.json", url="https://gofile.io/d/Another")
                elif case == "pending-url":
                    self.change("gofile-pending.json", url="https://gofile.io/d/Another")
                elif case == "folder-id":
                    data["folder_id"] = "another-folder"
                elif case == "owner-folder":
                    self.change("gofile-owner-private.json", folder_id="another-folder")
                elif case == "folder-type":
                    data["folder_type"] = "file"
                elif case == "http-error":
                    data["http_status"] = 401
                elif case == "status-error":
                    data["api_status"] = "error-notPremium"
                elif case == "duplicate-id":
                    data["files"][1]["id"] = data["files"][0]["id"]
                elif case == "duplicate-name":
                    data["files"][1]["name"] = data["files"][0]["name"]
                elif case == "nested-folder":
                    data["files"][0]["type"] = "folder"
                elif case == "extra-file":
                    data["files"].append({"id": "unwanted", "type": "file", "name": "extra.txt",
                                          "size": 1, "md5": "0" * 32})
                elif case == "expected-rows":
                    data["expected"][0]["sha256"] = "0" * 64
                elif case == "matched-flag":
                    data["public_listing_matched"] = False
                elif case == "expected-count":
                    data["expected_file_count"] = 4
                elif case == "api-success-claim":
                    data["direct_premium_api_readback_complete"] = True
                elif case == "content-mutation":
                    data["blocked_mutations"] = [{"method": "DELETE", "path": "/contents/file-1"}]
                elif case == "missing-method":
                    data["method"] = ""
                self.write(proof.name, data)
                with self.assertRaises((ValueError, RuntimeError)):
                    self.reconcile_web(proof)
                self.assert_pending_not_bound()
                self.assertFalse((self.folder / "gofile-receipt.json").exists())

    def test_web_reconciliation_rechecks_actual_bytes_md5_and_complete_pagination(self):
        cases = ("bytes", "md5", "total-count", "total-pages", "page", "page-size", "has-next-page")
        for case in cases:
            with self.subTest(case=case):
                _, proof, _ = self.web_fixture()
                data = self.read(proof.name)
                if case == "bytes":
                    data["files"][0]["size"] += 1
                elif case == "md5":
                    data["files"][0]["md5"] = "0" * 32
                else:
                    key, value = {"total-count": ("totalCount", 6), "total-pages": ("totalPages", 2),
                                  "page": ("page", 2), "page-size": ("pageSize", 4),
                                  "has-next-page": ("hasNextPage", True)}[case]
                    data["metadata"][key] = value
                self.write(proof.name, data)
                with self.assertRaises((ValueError, RuntimeError)):
                    self.reconcile_web(proof)
                self.assert_pending_not_bound()
                self.assertFalse((self.folder / "gofile-receipt.json").exists())

    def test_web_evidence_requires_real_image_and_revalidates_proof_image_and_owner_on_repeat(self):
        for case in ("wrong-image-sha", "not-an-image", "changed-proof-after-bind",
                     "changed-image-after-bind", "changed-owner-after-bind"):
            with self.subTest(case=case):
                _, proof, screenshot = self.web_fixture()
                if case.endswith("after-bind"):
                    self.reconcile_web(proof)
                    receipt_bytes = (self.folder / "gofile-receipt.json").read_bytes()
                    manifest_bytes = self.manifest.read_bytes()
                if case == "wrong-image-sha":
                    self.change(proof.name, screenshot_sha256="0" * 64)
                elif case == "not-an-image":
                    screenshot.write_bytes(b"This is not a PNG screenshot")
                    self.change(proof.name, screenshot_sha256=HELPER.hashes(screenshot)["sha256"])
                elif case == "changed-proof-after-bind":
                    self.change(proof.name, generated_utc="2026-10-11T12:00:01Z")
                elif case == "changed-image-after-bind":
                    Image.new("RGB", (320, 180), "red").save(screenshot)
                    self.change(proof.name, screenshot_sha256=HELPER.hashes(screenshot)["sha256"])
                else:
                    owner = self.read("gofile-owner-private.json")
                    owner["url"] = "https://gofile.io/d/Another"
                    HELPER.save(self.folder / "gofile-owner-private.json", owner, private=True)
                with self.assertRaises((OSError, ValueError, RuntimeError)):
                    self.reconcile_web(proof)
                if case.endswith("after-bind"):
                    self.assertEqual((self.folder / "gofile-receipt.json").read_bytes(), receipt_bytes)
                    self.assertEqual(self.manifest.read_bytes(), manifest_bytes)
                else:
                    self.assert_pending_not_bound()
                    self.assertFalse((self.folder / "gofile-receipt.json").exists())

    def test_web_binding_failure_preserves_pending_and_does_not_bind_an_unconfirmed_url(self):
        _, proof, _ = self.web_fixture()
        pending_bytes = (self.folder / "gofile-pending.json").read_bytes()
        with patch.object(HELPER, "bind_delivery", side_effect=RuntimeError("Injected binding failure")), \
                self.assertRaisesRegex(RuntimeError, "Injected binding failure"):
            self.reconcile_web(proof)
        self.assert_pending_not_bound()
        self.assertEqual((self.folder / "gofile-pending.json").read_bytes(), pending_bytes)

    def test_web_evidence_change_after_receipt_save_never_archives_pending_or_leaves_a_bound_url(self):
        for target in ("proof", "screenshot", "owner", "pending"):
            with self.subTest(changed=target):
                _, proof, screenshot = self.web_fixture()
                pending_bytes = (self.folder / "gofile-pending.json").read_bytes()
                real_save = HELPER.save
                injected = False
                def changing_save(path, value, private=False):
                    nonlocal injected
                    real_save(path, value, private=private)
                    if path == self.folder / "gofile-receipt.json" and not injected:
                        injected = True
                        if target == "proof":
                            self.change(proof.name, generated_utc="2026-10-11T12:00:01Z")
                        elif target == "screenshot":
                            Image.new("RGB", (320, 180), "red").save(screenshot)
                        elif target == "owner":
                            owner = self.read("gofile-owner-private.json")
                            owner["owner_token"] = "DIFFERENT_PRIVATE_WEB_FIXTURE_TOKEN"
                            real_save(self.folder / "gofile-owner-private.json", owner, private=True)
                        else:
                            self.change("gofile-pending.json", url="https://gofile.io/d/Another")
                with patch.object(HELPER, "save", side_effect=changing_save), \
                        self.assertRaises((ValueError, RuntimeError)):
                    self.reconcile_web(proof)
                self.assertTrue(injected, "The evidence race must occur after a real receipt save")
                self.assert_pending_not_bound()
                if target != "pending":
                    self.assertEqual((self.folder / "gofile-pending.json").read_bytes(), pending_bytes)

    def test_web_evidence_change_during_binding_preserves_pending_without_a_stale_bound_url(self):
        _, proof, _ = self.web_fixture()
        pending_bytes = (self.folder / "gofile-pending.json").read_bytes()
        original_manifest = self.manifest.read_bytes()
        real_save = HELPER.save
        injected = False
        def changing_save(path, value, private=False):
            nonlocal injected
            real_save(path, value, private=private)
            if path == self.manifest and not injected and "gofile_url" in value:
                injected = True
                self.change(proof.name, generated_utc="2026-10-11T12:00:01Z")
        with patch.object(HELPER, "save", side_effect=changing_save), \
                self.assertRaises((ValueError, RuntimeError)):
            self.reconcile_web(proof)
        self.assertTrue(injected, "The evidence race must occur after the real manifest binding")
        self.assert_pending_not_bound()
        self.assertEqual((self.folder / "gofile-pending.json").read_bytes(), pending_bytes)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)


if __name__ == "__main__":
    unittest.main()
