import copy
import unittest

from services.news_rights import RightsNotEstablished, automation_rights, image_rights


def photo():
    return {"url": "https://example.com/photo.jpg", "credit": "Photo: Example author",
            "rights": {"license": "CC BY-SA 4.0", "author": "Example author",
                       "evidence_url": "https://example.com/file-license", "reviewed_at": "2026-10-05",
                       "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
                       "adaptation_license": "CC BY-SA 4.0"}}


class RightsTest(unittest.TestCase):
    def test_credit_alone_does_not_establish_permission(self):
        with self.assertRaises(RightsNotEstablished):
            image_rights({"url": "https://example.com/article-photo.jpg", "credit": "Photo: Publisher"})

    def test_accepts_documented_license_and_preserves_input(self):
        visual = photo()
        before = copy.deepcopy(visual)
        image_rights(visual)
        self.assertEqual(visual, before)

    def test_blocks_noncommercial_no_derivatives_and_unsupported_licenses(self):
        for license_name in ("CC BY-NC 4.0", "CC BY-ND 4.0", "editorial", "all rights reserved"):
            visual = photo()
            visual["rights"]["license"] = license_name
            with self.subTest(license=license_name), self.assertRaises(RightsNotEstablished):
                image_rights(visual)

    def test_requires_evidence_and_share_alike(self):
        for field in ("author", "evidence_url", "reviewed_at", "license_url", "adaptation_license"):
            visual = photo()
            del visual["rights"][field]
            with self.subTest(field=field), self.assertRaises(RightsNotEstablished):
                image_rights(visual)

    def test_image_license_alone_does_not_authorize_automated_voice_or_music(self):
        plan = {"segments": [{"visual": photo()}]}
        with self.assertRaises(RightsNotEstablished):
            automation_rights(plan)
        plan["audio_rights"] = {"voice": {"commercial_use": True, "automated_access": True,
                                         "reviewed_at": "2026-10-05", "evidence_url": "https://example.com/voice-license"}}
        with self.assertRaises(RightsNotEstablished):
            automation_rights(plan)
        plan["audio_rights"]["music"] = {"kind": "original_synthesized", "generation_record": "services/music.py"}
        automation_rights(plan)
        plan["external_clips"] = ["external-interview"]
        with self.assertRaises(RightsNotEstablished):
            automation_rights(plan)


if __name__ == "__main__":
    unittest.main()
