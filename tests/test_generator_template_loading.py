from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd

from streamlit_app.generator import state
from streamlit_app.generator.templates import read_atst_lax
from ATST.device_readers import DeviceOutput


INCOMPLETE_TEMPLATE = """\
===FILE_START
:::STUDY_START
description\tOnly the fields present should be loaded
:::STUDY_END

:::LAYOUT_START
sample_id
sample-1
:::LAYOUT_END
===FILE_END
"""


INCOMPLETE_MULTI_READOUT_TEMPLATE = """\
===FILE_START
:::READOUT_IDS_START
readout_id
OD600
GFP
:::READOUT_IDS_END

:::METADATA_START
%%%METADATA_READOUT_START readout_id=OD600
operator\tJM
%%%METADATA_READOUT_END
%%%METADATA_READOUT_START readout_id=GFP
operator\tAB
%%%METADATA_READOUT_END
:::METADATA_END
===FILE_END
"""

SINGLE_BASELINE_TEMPLATE = """\
===FILE_START
:::METADATA_START
laboratory\tShared lab
:::METADATA_END
:::ASSAY_START
wavelength\t600 nm
:::ASSAY_END
:::LAYOUT_START
well_loc\tsample_id
A1\tsample-1
:::LAYOUT_END
===FILE_END
"""

CURVE_LAYOUT_TEMPLATE = """\
===FILE_START
:::STUDY_START
title\tCurve template
:::STUDY_END
:::METADATA_START
laboratory\tCurve lab
:::METADATA_END
:::ASSAY_START
wavelength\t600 nm
:::ASSAY_END
:::LAYOUT_START
curve_id\ttype\tsample_id
growth_01\tTreatment\tsample-1
growth_ctrl\tControl\tsample-2
:::LAYOUT_END
===FILE_END
"""


class SessionState(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class LaxTemplateLoadingTests(unittest.TestCase):
    def read_template(self, contents: str):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "template.atst.txt"
            path.write_text(contents, encoding="utf-8")
            return read_atst_lax(path)

    def test_loads_present_data_without_required_blocks_or_fields(self):
        template = self.read_template(INCOMPLETE_TEMPLATE)

        self.assertEqual(
            template.study.data,
            {"description": "Only the fields present should be loaded"},
        )
        self.assertEqual(
            template.layout.data.to_dict("records"), [{"sample_id": "sample-1"}]
        )
        self.assertEqual(template.file_info.data, {})
        self.assertEqual(template.metadata.data, {})
        self.assertEqual(template.assay.data, {})
        self.assertFalse(template.multi_readout_file)

    def test_loads_first_available_readout_without_required_fields(self):
        template = self.read_template(INCOMPLETE_MULTI_READOUT_TEMPLATE)

        self.assertEqual(template.readout_id, "OD600")
        self.assertTrue(template.multi_readout_file)
        self.assertEqual(template.metadata.data, {"operator": "JM"})
        self.assertEqual(list(template.readouts), ["OD600", "GFP"])  # type: ignore
        self.assertEqual(template.readouts["GFP"].metadata, {"operator": "AB"}) # type: ignore
        self.assertFalse(template.shared_blocks["metadata"]) # type: ignore

    def test_curve_layout_template_loads_other_blocks_and_skips_layout(self):
        template = self.read_template(CURVE_LAYOUT_TEMPLATE)

        self.assertEqual(template.study.data, {"title": "Curve template"})
        self.assertEqual(template.metadata.data, {"laboratory": "Curve lab"})
        self.assertEqual(template.assay.data, {"wavelength": "600 nm"})
        self.assertTrue(template.layout.data.empty)

    def test_curve_layout_template_does_not_break_streamlit_state_loading(self):
        uploaded_file = SimpleNamespace(
            name="curve-template.atst.txt",
            getvalue=lambda: CURVE_LAYOUT_TEMPLATE.encode("utf-8"),
        )
        fake_streamlit = SimpleNamespace(session_state=SessionState())

        with patch.object(state, "st", fake_streamlit):
            state.init_state()
            message = state.load_template(uploaded_file)

        self.assertEqual(message, "Loaded template.")
        self.assertEqual(
            fake_streamlit.session_state.study_default_table.iloc[0]["value"],
            "Curve template",
        )
        self.assertIn(
            "laboratory",
            fake_streamlit.session_state.metadata_extra_table["field"].tolist(),
        )
        self.assertIn("well_loc", fake_streamlit.session_state.layout_table.columns)
        self.assertNotIn("curve_id", fake_streamlit.session_state.layout_table.columns)

    def test_load_template_applies_an_incomplete_template(self):
        uploaded_file = SimpleNamespace(
            name="partial.atst.txt",
            getvalue=lambda: INCOMPLETE_TEMPLATE.encode("utf-8"),
        )
        fake_streamlit = SimpleNamespace(session_state=SessionState())

        with patch.object(state, "st", fake_streamlit):
            state.init_state()
            message = state.load_template(uploaded_file)

            self.assertEqual(message, "Loaded template.")
            self.assertEqual(state.st.session_state.file_name, "partial.atst.txt")
            self.assertEqual(
                state.st.session_state.study_extra_table.to_dict("records"),
                [
                    {
                        "field": "description",
                        "value": "Only the fields present should be loaded",
                    }
                ],
            )

    def _fake_output(self, filename: str) -> DeviceOutput:
        return DeviceOutput(
            file_name=f"{Path(filename).stem}.atst.txt",
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
            },
            layout=pd.DataFrame([{"well_loc": "A1", "type": "sample"}]),
            readings=pd.DataFrame({"Time": [0], "A1": [0.1]}),
        )

    def test_single_template_loaded_first_applies_to_every_later_output(self):
        template_file = SimpleNamespace(
            name="baseline.atst.txt",
            getvalue=lambda: SINGLE_BASELINE_TEMPLATE.encode("utf-8"),
        )
        uploads = [
            SimpleNamespace(name=name, getvalue=lambda: b"raw")
            for name in ("one.txt", "two.txt")
        ]
        fake_streamlit = SimpleNamespace(session_state=SessionState())
        reader = SimpleNamespace(
            read=lambda raw, filename="": self._fake_output(filename)
        )
        with patch.object(state, "st", fake_streamlit), patch.dict(
            state.DEVICE_READERS, {"Fake": reader}, clear=True
        ):
            state.init_state()
            state.load_template(template_file)
            messages = state.load_device_outputs(uploads, device="Fake")
            drafts = list(state.st.session_state.readout_drafts.values())

        self.assertEqual(len(messages), 2)
        self.assertIn("one.txt", messages[0])
        self.assertIn("two.txt", messages[1])
        for draft in drafts:
            self.assertEqual(draft.metadata["laboratory"], "Shared lab")
            self.assertEqual(draft.assay["wavelength"], "600 nm")
            self.assertIn("sample_id", draft.layout.columns)
            self.assertIn("type", draft.layout.columns)

    def test_single_template_loaded_after_outputs_applies_to_every_readout(self):
        template_file = SimpleNamespace(
            name="baseline.atst.txt",
            getvalue=lambda: SINGLE_BASELINE_TEMPLATE.encode("utf-8"),
        )
        uploads = [
            SimpleNamespace(name=name, getvalue=lambda: b"raw")
            for name in ("one.txt", "two.txt")
        ]
        fake_streamlit = SimpleNamespace(session_state=SessionState())
        reader = SimpleNamespace(
            read=lambda raw, filename="": self._fake_output(filename)
        )
        with patch.object(state, "st", fake_streamlit), patch.dict(
            state.DEVICE_READERS, {"Fake": reader}, clear=True
        ):
            state.init_state()
            state.load_device_outputs(uploads, device="Fake")
            message = state.load_template(template_file)
            drafts = list(state.st.session_state.readout_drafts.values())

        self.assertIn("applied it to all 2 readouts", message)
        for draft in drafts:
            self.assertEqual(draft.metadata["laboratory"], "Shared lab")
            self.assertEqual(draft.assay["wavelength"], "600 nm")
            self.assertIn("sample_id", draft.layout.columns)

    def test_multi_template_loaded_first_is_reconciled_with_later_outputs(self):
        template_file = SimpleNamespace(
            name="multi.atst.txt",
            getvalue=lambda: INCOMPLETE_MULTI_READOUT_TEMPLATE.encode("utf-8"),
        )
        uploads = [
            SimpleNamespace(name=name, getvalue=lambda: b"raw")
            for name in ("one.txt", "two.txt")
        ]
        fake_streamlit = SimpleNamespace(session_state=SessionState())
        reader = SimpleNamespace(
            read=lambda raw, filename="": self._fake_output(filename)
        )
        with patch.object(state, "st", fake_streamlit), patch.dict(
            state.DEVICE_READERS, {"Fake": reader}, clear=True
        ):
            state.init_state()
            state.load_template(template_file)
            state.load_device_outputs(uploads, device="Fake")
            drafts = list(state.st.session_state.readout_drafts.values())

        self.assertEqual([draft.readout_id for draft in drafts], ["OD600", "GFP"])
        self.assertEqual([draft.metadata["operator"] for draft in drafts], ["JM", "JM"])
        self.assertTrue(all(not draft.readings.empty for draft in drafts))


if __name__ == "__main__":
    unittest.main()
