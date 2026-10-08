from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest

from ATST import read_atst, write_multi_readout_atst
from ATST.errors import ATSTParseError, ATSTValidationError
from ATST.device_readers import DeviceOutput
from streamlit_app.generator.builder import make_multi_readout_atst
from streamlit_app.generator.readouts import (
    ReadoutDraft,
    copy_shared_block,
    infer_readout_id,
    ordered_readouts,
)


class GeneratorMultiReadoutTests(unittest.TestCase):
    def _app_draft(self, key: str, readout_id: str, order: int) -> ReadoutDraft:
        return ReadoutDraft(
            key=key,
            readout_id=readout_id,
            upload_order=order,
            source_name=f"{readout_id}.txt",
            metadata={
                "instrument": "reader",
                "plate_type": "96 well",
                "date_start": "2026-07-14",
                "operator": "JM",
            },
            assay={
                "readout_type": "absorbance",
                "readout_unit": "OD",
                "time_unit": "seconds",
                "plate_format": "96_well",
                "plate_num": str(order + 1),
            },
            layout=pd.DataFrame([{"well_loc": "A1", "type": "old"}]),
            readings=pd.DataFrame({"Time": [0], "A1": [0.1]}),
        )

    def _upload_conflicting_layout(self, app: AppTest) -> AppTest:
        layout_upload = next(
            uploader
            for uploader in app.get("file_uploader")
            if (uploader.key or "").startswith("layout_file_upload_")
        )
        layout_upload.upload( # type: ignore
            "layout.tsv",
            b"well_loc\ttype\tsample_id\nA1\tnew\tsample-1\n",
            "text/tab-separated-values",
        )
        app = app.run(timeout=30)
        next(
            button for button in app.button if button.label == "Replace column"
        ).click()
        return app.run(timeout=30)

    def test_uploaded_layout_persists_for_active_readout_after_merge_rerun(self):
        app = AppTest.from_file("src/streamlit_app/ATST_Generator.py").run(
            timeout=30
        )
        app.session_state["readout_drafts"] = {
            "one": self._app_draft("one", "one", 0),
            "two": self._app_draft("two", "two", 1),
        }
        app.session_state["shared_readout_blocks"] = {
            "metadata": False,
            "assay": False,
            "layout": False,
        }
        app = self._upload_conflicting_layout(app.run(timeout=30))

        self.assertFalse(app.exception)
        drafts = app.session_state["readout_drafts"]
        self.assertEqual(drafts["one"].layout.iloc[0]["type"], "new")
        self.assertEqual(drafts["one"].layout.iloc[0]["sample_id"], "sample-1")
        self.assertEqual(drafts["two"].layout.iloc[0]["type"], "old")

    def test_uploaded_shared_layout_persists_for_every_readout(self):
        app = AppTest.from_file("src/streamlit_app/ATST_Generator.py").run(
            timeout=30
        )
        app.session_state["readout_drafts"] = {
            "one": self._app_draft("one", "one", 0),
            "two": self._app_draft("two", "two", 1),
        }
        app.session_state["shared_readout_blocks"] = {
            "metadata": False,
            "assay": False,
            "layout": True,
        }
        app.session_state["share_layout"] = True
        app = self._upload_conflicting_layout(app.run(timeout=30))

        self.assertFalse(app.exception)
        drafts = app.session_state["readout_drafts"]
        for draft in drafts.values():
            self.assertEqual(draft.layout.iloc[0]["type"], "new")
            self.assertEqual(draft.layout.iloc[0]["sample_id"], "sample-1")

    def test_infers_killcurves_plate_id_then_filename_fallback(self):
        output = DeviceOutput(
            file_name="ignored.atst.txt",
            metadata={"plate_id": "2026_04_15_JM_QC_PAO1"},
            assay={},
            readings=pd.DataFrame(),
        )
        self.assertEqual(
            infer_readout_id(output, "raw.txt"), "2026_04_15_JM_QC_PAO1"
        )
        fallback = DeviceOutput(
            file_name="ignored.atst.txt",
            metadata={},
            assay={},
            readings=pd.DataFrame(),
        )
        self.assertEqual(infer_readout_id(fallback, "reader output.xlsx"), "reader output")

    def test_shared_copy_is_immediate_detached_and_plate_ordered(self):
        first = ReadoutDraft(
            key="first",
            readout_id="first",
            upload_order=0,
            source_name="first.txt",
            metadata={"operator": "old"},
            assay={"plate_num": "2"},
        )
        second = ReadoutDraft(
            key="second",
            readout_id="second",
            upload_order=1,
            source_name="second.txt",
            metadata={"operator": "canonical"},
            assay={"device_plate_number": "1"},
        )
        drafts = {first.key: first, second.key: second}

        self.assertEqual([item.key for item in ordered_readouts(drafts)], ["second", "first"])
        copy_shared_block(drafts, "metadata")
        self.assertEqual(first.metadata, {"operator": "canonical"})
        second.metadata["operator"] = "edited later"
        self.assertEqual(first.metadata, {"operator": "canonical"})

    def test_registry_rejects_duplicate_ids_before_children_are_built(self):
        with self.assertRaisesRegex(ATSTValidationError, "identifiers must be unique"):
            make_multi_readout_atst(
                file_name="duplicate.atst.txt",
                study_data={"title": "Duplicate registry", "study_id": "DUPLICATE"},
                readout_data=[
                    ("same", {}, {}, pd.DataFrame(), pd.DataFrame()),
                    ("same", {}, {}, pd.DataFrame(), pd.DataFrame()),
                ],
                entities=None,  # type: ignore[arg-type]
            )

    def test_registry_rejects_blank_ids_before_children_are_built(self):
        with self.assertRaisesRegex(ATSTParseError, "Identifiers must be non-empty"):
            make_multi_readout_atst(
                file_name="blank.atst.txt",
                study_data={"title": "Blank registry", "study_id": "BLANK"},
                readout_data=[("", {}, {}, pd.DataFrame(), pd.DataFrame())],
                entities=None,  # type: ignore[arg-type]
            )

    def test_build_write_and_read_multi_readout(self):
        layout = pd.DataFrame([{"well_loc": "A1", "type": "sample"}])
        readout_data = []
        for identifier, value in (("OD600", 0.1), ("GFP", 12.0)):
            readout_data.append(
                (
                    identifier,
                    {
                        "instrument": "reader",
                        "plate_type": "96 well",
                        "date_start": "2026-07-14",
                        "operator": "JM",
                    },
                    {
                        "readout_type": "absorbance",
                        "readout_unit": "AU",
                        "time_unit": "seconds",
                        "plate_format": "96_well",
                    },
                    layout,
                    pd.DataFrame({"Time": [0, 60], "A1": [value, value + 1]}),
                )
            )
        multi = make_multi_readout_atst(
            file_name="multi.atst.txt",
            study_data={"title": "Multi", "study_id": "M1"},
            readout_data=readout_data,
            entities=None, 
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "multi.atst.txt"
            write_multi_readout_atst(multi, path)
            loaded = read_atst(path, multi_readouts=True)
        self.assertEqual(list(loaded.readouts), ["OD600", "GFP"])
        self.assertEqual(loaded.readouts["GFP"].readings.data.iloc[0]["A1"], 12.0)


if __name__ == "__main__":
    unittest.main()
