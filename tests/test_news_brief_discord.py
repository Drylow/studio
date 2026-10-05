import copy
import unittest

from services.news_brief_discord import confirmed_files


def embedded_thumbnail():
    # Real Discord response shape: an image used by an embed can disappear
    # from attachments[], while the ZIP remains listed there.
    return {"id": "test-message", "attachments": [{"filename": "Kit_publication.zip"}],
            "embeds": [{"image": {"url": "https://cdn.discordapp.com/attachments/1/2/miniature.jpg?ex=test"}}]}


class DiscordDeliveryTest(unittest.TestCase):
    def test_accepts_thumbnail_inside_embed_and_zip_as_attachment(self):
        message = embedded_thumbnail()
        before = copy.deepcopy(message)
        self.assertEqual(confirmed_files(message), ["Kit_publication.zip", "miniature.jpg"])
        self.assertEqual(message, before)

    def test_accepts_both_files_in_attachment_list(self):
        message = embedded_thumbnail()
        message["embeds"] = []
        message["attachments"].append({"filename": "miniature.jpg"})
        self.assertEqual(confirmed_files(message), ["Kit_publication.zip", "miniature.jpg"])

    def test_rejects_missing_thumbnail_zip_or_message_id(self):
        for missing in ("embeds", "attachments", "id"):
            message = embedded_thumbnail()
            del message[missing]
            with self.subTest(missing=missing), self.assertRaises(RuntimeError):
                confirmed_files(message)


if __name__ == "__main__":
    unittest.main()
