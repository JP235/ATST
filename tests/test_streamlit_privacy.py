import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from streamlit_app import privacy


class UploadLifecycleTests(unittest.TestCase):
    def test_expiring_upload_changes_its_widget_key(self):
        state = {}

        with patch.object(privacy.st, "session_state", state):
            self.assertEqual(privacy.upload_widget_key("template"), "template_0")
            privacy.expire_upload_widget("template")
            self.assertEqual(privacy.upload_widget_key("template"), "template_1")

    def test_processed_upload_is_removed_from_streamlit_widget_state(self):
        app = AppTest.from_file("src/streamlit_app/ATST_Generator.py").run(
            timeout=20
        )
        layout_upload = next(
            uploader
            for uploader in app.get("file_uploader")
            if uploader.key == "layout_file_upload_0"
        )

        layout_upload.upload(
            "layout.tsv",
            b"well_loc\ttype\nA1\tSample\n",
            "text/tab-separated-values",
        ).run(timeout=20)

        uploader_keys = {
            uploader.key for uploader in app.get("file_uploader")
        }
        self.assertNotIn("layout_file_upload_0", uploader_keys)
        self.assertNotIn("layout_file_upload_0", app.session_state)
        self.assertIn("layout_file_upload_1", uploader_keys)

if __name__ == "__main__":
    unittest.main()
