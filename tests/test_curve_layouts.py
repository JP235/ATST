import tempfile
import unittest
from pathlib import Path

import pandas as pd

from ATST import read_atst, validate_atst, write_atst, write_multi_readout_atst
from ATST.errors import ATSTValidationError


EXAMPLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "e5"
    / "example_5.atst.txt"
)
VALID_CURVE_TEXT = EXAMPLE_PATH.read_text(encoding="utf-8")
MULTI_CURVE_TEXT = """\
===FILE_START
:::FILE_INFO_START
file_name\tmulti_curve.atst.txt
format\tATST
format_version\t0.1
created_on\t2026-07-29
field_delimiter\tTAB
encoding\tUTF-8
:::FILE_INFO_END
:::STUDY_START
title\tSeparate curve acquisitions
study_id\tCURVE_RUNS
:::STUDY_END
:::READOUT_IDS_START
readout_id
growth_01_run
growth_ctrl_run
:::READOUT_IDS_END
:::METADATA_START
%%%METADATA_READOUT_START readout_id=growth_01_run
instrument\tReader_A
plate_type\tnon_plate
date_start\t2026-07-01
operator\tOP1
%%%METADATA_READOUT_END
%%%METADATA_READOUT_START readout_id=growth_ctrl_run
instrument\tReader_A
plate_type\tnon_plate
date_start\t2026-07-03
operator\tOP1
%%%METADATA_READOUT_END
:::METADATA_END
:::ASSAY_START
%%%ASSAY_READOUT_START readout_id=growth_01_run
readout_type\tabsorbance
readout_unit\tOD
time_unit\tmin
gain\t40
%%%ASSAY_READOUT_END
%%%ASSAY_READOUT_START readout_id=growth_ctrl_run
readout_type\tabsorbance
readout_unit\tOD
time_unit\tmin
gain\t55
%%%ASSAY_READOUT_END
:::ASSAY_END
:::LAYOUT_START
%%%LAYOUT_READOUT_START readout_id=growth_01_run
curve_id\ttype
growth_01\tTreatment
%%%LAYOUT_READOUT_END
%%%LAYOUT_READOUT_START readout_id=growth_ctrl_run
curve_id\ttype
growth_ctrl\tControl
%%%LAYOUT_READOUT_END
:::LAYOUT_END
:::READINGS_START
%%%READOUT_START readout_id=growth_01_run
Time\tgrowth_01
0\t0.10
60\t0.18
%%%READOUT_END
%%%READOUT_START readout_id=growth_ctrl_run
Time\tgrowth_ctrl
0\t0.09
60\t0.11
%%%READOUT_END
:::READINGS_END
===FILE_END
"""


class CurveLayoutTests(unittest.TestCase):
    def read_text(self, text: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "curve.atst.txt"
            path.write_text(text, encoding="utf-8")
            return read_atst(path)

    def assert_rejected(self, text: str, message: str) -> None:
        with self.assertRaisesRegex(ATSTValidationError, message):
            self.read_text(text)

    def assert_invalid(self, atst, message: str) -> None:
        with self.assertRaisesRegex(ATSTValidationError, message):
            validate_atst(atst)

    def test_accepts_curve_layout_without_plate_format(self) -> None:
        atst = read_atst(EXAMPLE_PATH)

        curve_ids = atst.layout.data["curve_id"].tolist()
        self.assertEqual(curve_ids, atst.readings.data.columns[1:].tolist())
        self.assertNotIn("plate_format", atst.assay.data)
        treated = atst.layout.data.loc[
            atst.layout.data["type"] == "treated", "curve_id"
        ].tolist()
        pd.testing.assert_frame_equal(
            atst.data_by_type("treated"),
            atst.readings.data[treated],
        )

    def test_curve_layout_round_trip_preserves_tables(self) -> None:
        imported = read_atst(EXAMPLE_PATH)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "curve-round-trip.atst.tsv"
            write_atst(imported, output, human_readable=False)
            reread = read_atst(output)

        pd.testing.assert_frame_equal(imported.layout.data, reread.layout.data)
        pd.testing.assert_frame_equal(imported.readings.data, reread.readings.data)

    def test_multi_readout_curves_keep_separate_metadata_and_assay_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "multi_curve.atst.txt"
            source.write_text(MULTI_CURVE_TEXT, encoding="utf-8")
            imported = read_atst(source, multi_readouts=True)
            output = directory / "multi_curve_round_trip.atst.txt"
            write_multi_readout_atst(imported, output)
            reread = read_atst(output, multi_readouts=True)

        self.assertEqual(
            reread.readouts["growth_01_run"].metadata.date_start,
            "2026-07-01",
        )
        self.assertEqual(reread.readouts["growth_01_run"].assay.gain, "40")
        self.assertEqual(reread.readouts["growth_ctrl_run"].assay.gain, "55")
        self.assertEqual(
            reread.readouts["growth_ctrl_run"].layout.data["curve_id"].tolist(),
            ["growth_ctrl"],
        )

    def test_curve_plot_uses_non_plate_ordering(self) -> None:
        from matplotlib import pyplot as plt

        atst = read_atst(EXAMPLE_PATH)
        figures = atst.plot_full_plate(show=False)
        try:
            self.assertEqual(len(figures), 1)
            self.assertEqual(len(figures[0].axes), len(atst.layout.data))
        finally:
            plt.close(figures[0])

    def test_rejects_layout_with_both_key_columns(self) -> None:
        atst = read_atst(EXAMPLE_PATH)
        atst.layout.data["well_loc"] = [
            f"curve_{index}" for index in range(len(atst.layout.data))
        ]
        self.assert_invalid(atst, "exactly one")

    def test_rejects_layout_without_a_key_column(self) -> None:
        atst = read_atst(EXAMPLE_PATH)
        atst.layout.data = atst.layout.data.rename(
            columns={"curve_id": "series_name"}
        )
        self.assert_invalid(atst, "exactly one")

    def test_rejects_blank_curve_id(self) -> None:
        atst = read_atst(EXAMPLE_PATH)
        atst.layout.data.loc[0, "curve_id"] = ""
        self.assert_invalid(atst, "non-empty")

    def test_rejects_duplicate_curve_id(self) -> None:
        atst = read_atst(EXAMPLE_PATH)
        atst.layout.data.loc[1, "curve_id"] = atst.layout.data.loc[0, "curve_id"]
        self.assert_invalid(atst, "must be unique")

    def test_rejects_layout_curve_without_matching_readings_column(self) -> None:
        atst = read_atst(EXAMPLE_PATH)
        atst.layout.data.loc[0, "curve_id"] = "unknown_curve"
        self.assert_invalid(atst, "missing from READINGS")

    def test_rejects_readings_column_without_matching_curve(self) -> None:
        atst = read_atst(EXAMPLE_PATH)
        atst.readings.data["unknown_curve"] = atst.readings.data.iloc[:, 1]
        self.assert_invalid(atst, "missing from LAYOUT.curve_id")

    def test_rejects_well_layout_without_plate_format(self) -> None:
        atst = read_atst(EXAMPLE_PATH)
        atst.layout.data = atst.layout.data.rename(columns={"curve_id": "well_loc"})
        self.assert_invalid(atst, "plate_format is required")

    def test_accepts_linked_curve_layout_and_readings(self) -> None:
        layout_block = """\
:::LAYOUT_START
<<<LAYOUT_READOUT file=layout.tsv
:::LAYOUT_END"""
        readings_block = """\
:::READINGS_START
<<<READOUT file=readings.tsv
:::READINGS_END"""
        layout_start = VALID_CURVE_TEXT.index(":::LAYOUT_START")
        layout_end = VALID_CURVE_TEXT.index(":::LAYOUT_END") + len(":::LAYOUT_END")
        readings_start = VALID_CURVE_TEXT.index(":::READINGS_START")
        readings_end = VALID_CURVE_TEXT.index(":::READINGS_END") + len(
            ":::READINGS_END"
        )
        text = (
            VALID_CURVE_TEXT[:layout_start]
            + layout_block
            + VALID_CURVE_TEXT[layout_end:readings_start]
            + readings_block
            + VALID_CURVE_TEXT[readings_end:]
        )

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "layout.tsv").write_text(
                "curve_id\ttype\ncurve-a\tTreatment\ncurve-b\tControl\n",
                encoding="utf-8",
            )
            (directory / "readings.tsv").write_text(
                "Time\tcurve-a\tcurve-b\n0\t0.1\t0.2\n60\t0.3\t0.4\n",
                encoding="utf-8",
            )
            path = directory / "linked-curve.atst.txt"
            path.write_text(text, encoding="utf-8")
            atst = read_atst(path)

        self.assertEqual(atst.layout.data["curve_id"].tolist(), ["curve-a", "curve-b"])


if __name__ == "__main__":
    unittest.main()
