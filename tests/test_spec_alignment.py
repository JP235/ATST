"""Regression coverage for precision, linked entities, and current-object validation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd
from ATST import read_atst, write_atst, write_multi_readout_atst, validate_atst
from ATST.blocks import Assay, Metadata, Readings, Study
from ATST.errors import ATSTError, ATSTValidationError
from ATST.parser.block_parser import read_wide_table
from ATST.device_readers.logphase600 import build_metadata, time_value_to_seconds
from ATST.device_readers.tecan import parse_tecan_readings
from ATST.device_readers.clariostar import parse_time_minutes, format_number
from streamlit_app.generator.builder import prepare_wide_table
from streamlit_app.tables.uploads import read_delimited_table, UploadedTableParseError
from tests.helpers import MINIMAL_ATST_PATH, minimal_atst_text, block_text


class SpecAlignmentTests(unittest.TestCase):
    def fixture(self):
        return read_atst(MINIMAL_ATST_PATH)

    def write_and_read(self, atst):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "result.atst.txt"
            write_atst(atst, path, human_readable=False)
            return read_atst(path), path.read_text()

    def test_precision_and_missing_tokens_survive_round_trip(self):
        atst = self.fixture()
        values = atst.readings.to_text()
        values.loc[0, "A1"] = "0.123456789123456789"
        values.loc[0, "A2"] = "NA"
        values.loc[0, "A3"] = ""
        atst.readings = Readings(data=values)
        self.assertTrue(pd.isna(atst.readings.data.loc[0, "A2"]))
        reread, text = self.write_and_read(atst)
        self.assertIn("0.123456789123456789\tNA\t", text)
        self.assertEqual(reread.readings.to_text().loc[0, "A2"], "NA")
        self.assertEqual(reread.readings.to_text().loc[0, "A3"], "")
        pd.testing.assert_frame_equal(values, reread.readings.to_text())

    def test_numeric_edit_overrides_original_token(self):
        atst = self.fixture()
        atst.readings.data.loc[0, "A1"] = 0.987654321
        reread, _ = self.write_and_read(atst)
        self.assertEqual(reread.readings.data.loc[0, "A1"], 0.987654321)

    def test_missing_setter_and_form_preparation_preserve_tokens(self):
        atst = self.fixture()
        atst.readings.set_missing(0, "A1", kind="NA")
        atst.readings.set_missing(0, "A2", kind="")
        prepared = prepare_wide_table(atst.readings.data, block_name="READINGS")
        self.assertEqual(prepared.loc[0, "A1"], "NA")
        self.assertEqual(prepared.loc[0, "A2"], "")
        reread, _ = self.write_and_read(atst)
        self.assertEqual(reread.readings.to_text().loc[0, "A1"], "NA")

    def test_missing_tokens_follow_time_when_rows_reordered(self):
        atst = self.fixture()
        atst.readings.set_missing(0, "A1")
        atst.readings.data = atst.readings.data.iloc[::-1].reset_index(drop=True)
        text = atst.readings.to_text()
        self.assertEqual(text.loc[1, "A1"], "NA")
        self.assertNotEqual(text.loc[0, "A1"], "NA")

    def test_linked_entities_resolve_relative_to_container(self):
        original = minimal_atst_text()
        linked = ":::ENTITIES_START\n<<<TABLE name=PHAGES pk=phage_id file=entities/phages.tsv\n:::ENTITIES_END"
        text = original.replace(block_text(original, "ENTITIES"), linked)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "entities").mkdir()
            (root / "entities/phages.tsv").write_text("phage_id\tlabel\nph_1\tfirst\nph_2\tsecond\n")
            path = root / "renamed.atst.txt"
            path.write_text(text)
            atst = read_atst(path)
            assert atst.entities
            self.assertEqual(atst.entities.PHAGES.data["phage_id"].tolist(), ["ph_1", "ph_2"])
            self.assertEqual(atst.entities.PHAGES.linked_file, "entities/phages.tsv")
            reread, output = self.write_and_read(atst)
            self.assertNotIn("<<<TABLE", output)
            assert reread.entities
            pd.testing.assert_frame_equal(atst.entities.PHAGES.data, reread.entities.PHAGES.data)

    def test_invalid_linked_entities_rejected(self):
        original = minimal_atst_text()
        cases = {
            "duplicate": "phage_id\na\na\n",
            "missing_pk": "wrong\na\n",
            "delimiters": "%%%TABLE_START name=x pk=phage_id\nphage_id\na\n%%%TABLE_END\n",
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name, payload in cases.items():
                with self.subTest(name=name):
                    (root / "table.tsv").write_text(payload)
                    block = ":::ENTITIES_START\n<<<TABLE name=PHAGES pk=phage_id file=table.tsv\n:::ENTITIES_END"
                    path = root / "case.atst.txt"
                    path.write_text(original.replace(block_text(original, "ENTITIES"), block))
                    with self.assertRaises(ATSTError): read_atst(path)
            for declaration in ("<<<TABLE name=PHAGES pk=phage_id file=missing.tsv", 
                                "<<<TABLE name=PHAGES pk=phage_id file=/tmp/table.tsv",
                                "<<<TABLE name=PHAGES pk=phage_id file=table.tsv\n%%%TABLE_START name=X pk=id\nid\na\n%%%TABLE_END"):
                path.write_text(original.replace(block_text(original, "ENTITIES"),
                    ":::ENTITIES_START\n" + declaration + "\n:::ENTITIES_END"))
                with self.assertRaises(ATSTError): read_atst(path)

    def test_mutations_rejected_before_writing(self):
        def duplicate_time(a): a.readings.data.loc[1, "Time"] = 0
        def wrong_unit(a): a.assay.data["time_unit"] = "fortnights"
        def missing_field(a): del a.assay.data["time_unit"]
        def missing_study_title(a): del a.study.data["title"]
        def missing_study_id(a): del a.study.data["study_id"]
        def bad_encoding(a): a.file_info.data["encoding"] = "latin1"
        def bad_date(a): a.metadata.data["date_start"] = "2026_01_01"
        def duplicate_pk(a): a.entities.PHAGES.data.loc[1, "phage_id"] = "ph_1"
        def reserved_pk(a): a.entities.PHAGES.data.loc[0, "phage_id"] = "FILE_INFO"
        def not_first(a): a.readings.data = a.readings.data[["A1", "Time", "A2", "A3", "B1", "B2", "B3"]]
        def non_numeric(a): a.readings.data["A1"] = ["broken", "0.1"]
        for mutation in (duplicate_time, wrong_unit, missing_field,
                         missing_study_title, missing_study_id, bad_encoding, bad_date,
                         duplicate_pk, reserved_pk, not_first, non_numeric):
            with self.subTest(mutation=mutation.__name__), TemporaryDirectory() as directory:
                atst = self.fixture()
                mutation(atst)
                path = Path(directory) / "invalid.atst.txt"
                with self.assertRaises(ATSTError): write_atst(atst, path)
                self.assertFalse(path.exists())

    def test_duplicate_headers_rejected_before_pandas_mangling(self):
        with self.assertRaises(ATSTError):
            read_wide_table("Time\tA1\tA1\n0\t1\t2", allow_reserved_columns={"Time"})
        with self.assertRaises(UploadedTableParseError):
            read_delimited_table("Time,A1,A1\n0,1,2", name="readings.csv")

    def test_required_study_fields_and_optional_metadata_fields(self):
        for data in ({}, {"title": "Study"}, {"study_id": "STUDY_1"}):
            with self.subTest(data=data), self.assertRaises(ATSTValidationError):
                Study(data=data)

        atst = self.fixture()
        atst.metadata = Metadata(data={})
        atst.layout.data = atst.layout.data.rename(columns={"well_loc": "curve_id"})
        del atst.assay.data["plate_format"]
        self.write_and_read(atst)

    def test_invalid_time_values_and_units(self):
        for times in ([0, 0], [1, 0], [0, "NA"], [0, ""], [0, float("inf")]):
            with self.subTest(times=times), self.assertRaises(ATSTError):
                Readings(data=pd.DataFrame({"Time": times, "A1": [1, 2]}))
        with self.assertRaises(ATSTValidationError):
            Assay(data={"readout_type": "OD", "readout_unit": "OD", "time_unit": "days"})

    def test_registry_revalidated_for_multi_export(self):
        example = MINIMAL_ATST_PATH.parents[2] / "examples/e2/example_2.atst.txt"
        atst = read_atst(example, multi_readouts=True)
        atst.readout_ids.data.loc[0, "readout_id"] = "undeclared"
        with TemporaryDirectory() as directory, self.assertRaises(ATSTError):
            write_multi_readout_atst(atst, Path(directory) / "bad.atst.txt")

    def test_filename_fallback_and_iso_dates(self):
        metadata = build_metadata(
            {"date_start": "2026_09_21", "operator": "instrument"},
            {"date_start": "2026-01-01", "operator": "filename"})
        self.assertEqual(metadata["operator"], "instrument")
        self.assertEqual(metadata["date_start"], "2026-09-21")
        metadata = build_metadata({"date_start": "unparseable"}, {"date_start": "2026-01-01"})
        self.assertEqual(metadata["date_start"], "")
        self.assertEqual(metadata["date_start_source"], "unparseable")

    def test_time_conversion_without_six_digit_rounding(self):
        self.assertEqual(time_value_to_seconds("0.123456789"), "0.123456789")
        self.assertEqual(time_value_to_seconds("01:02:03.123456789"), "3723.123456789")
        self.assertEqual(format_number(parse_time_minutes("0.123456789min")), "0.123456789")

    def test_tecan_preserves_export_precision_empty_rows_and_na(self):
        readings, _ = parse_tecan_readings([
            (0, ["Time [s]", "A01", "A02"]),
            (1, ["0.123456789", "0.123456789123456789", "NA"]),
            (2, ["0.223456789", "", ""]),
        ])
        self.assertEqual(list(readings.columns), ["Time", "A1", "A2"])
        self.assertEqual(readings["Time"].tolist(), ["0.123456789", "0.223456789"])
        self.assertEqual(readings["A1"].tolist(), ["0.123456789123456789", ""])
        self.assertEqual(readings["A2"].tolist(), ["NA", ""])

    def test_linked_and_multi_readout_missing_precision_round_trip(self):
        example = MINIMAL_ATST_PATH.parents[2] / "examples/e2/example_2.atst.txt"
        atst = read_atst(example, multi_readouts=True)
        for readout in atst.readouts.values():
            values = readout.readings.to_text()
            values.iloc[0, 1] = "0.123456789123456789"
            values.iloc[0, 2] = "NA"
            readout.readings = Readings(data=values)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "multi.atst.txt"
            write_multi_readout_atst(atst, path, human_readable=False)
            reread = read_atst(path, multi_readouts=True)
        for key, readout in reread.readouts.items():
            pd.testing.assert_frame_equal(atst.readouts[key].readings.to_text(), readout.readings.to_text())

    def test_duplicate_file_markers_and_extra_table_cells_rejected(self):
        from ATST.parser.parser import parse_file
        with self.assertRaises(ATSTError):
            parse_file(minimal_atst_text().replace(":::STUDY_START", "===FILE_START\n:::STUDY_START").splitlines())
        with self.assertRaises(ATSTError):
            read_wide_table("Time\tA1\n0\t1\t2", allow_reserved_columns={"Time"})

    def test_reserved_and_blank_registry_ids_rejected(self):
        from ATST.blocks import ReadoutIds
        for value in ("FILE_INFO", "", "NA"):
            with self.subTest(value=value), self.assertRaises(ATSTError):
                ReadoutIds(data=pd.DataFrame({"readout_id": [value]}))

    def test_readonly_validation_does_not_change_current_data(self):
        atst = self.fixture()
        before = atst.readings.to_text()
        validate_atst(atst)
        pd.testing.assert_frame_equal(before, atst.readings.to_text())

    def test_arrow_conversion_keeps_readings_provenance_serializable(self):
        import pyarrow as pa
        atst = self.fixture()
        atst.readings.set_missing(0, "A1")
        values = atst.readings.to_text()
        table = pa.Table.from_pandas(atst.readings.data)
        restored = Readings(data=table.to_pandas())
        pd.testing.assert_frame_equal(values, restored.to_text())

    def test_clariostar_metadata_is_iso_and_source_first(self):
        from ATST.device_readers.clariostar import build_metadata as clario_metadata
        metadata = clario_metadata(
            {"date": "21/09/2026", "time": "13:04:05", "user": "instrument"},
            {"date_start": "2026-01-01", "operator": "filename"}, "export.csv")
        self.assertEqual(metadata["date_start"], "2026-09-21T13:04:05")
        self.assertEqual(metadata["operator"], "instrument")
        metadata = clario_metadata({"date": "unknown"}, {}, "export.csv")
        self.assertEqual(metadata["date_start"], "")
        self.assertEqual(metadata["date_start_source"], "unknown")

    def test_unannotated_layout_row_may_be_absent_from_readings(self):
        atst = self.fixture()
        atst.layout.data.loc[len(atst.layout.data)] = {
            "well_loc": "C1",
            "type": "",
            "phage_id": "",
            "isolate_id": "",
        }
        reread, _ = self.write_and_read(atst)
        self.assertIn("C1", reread.layout.data["well_loc"].tolist())
        self.assertNotIn("C1", reread.readings.data.columns)

    def test_unannotated_layout_row_may_have_only_empty_readings(self):
        atst = self.fixture()
        atst.layout.data.loc[len(atst.layout.data)] = {
            "well_loc": "C1",
            "type": "",
            "phage_id": "",
            "isolate_id": "",
        }
        text = atst.readings.to_text()
        text["C1"] = ["", ""]
        atst.readings = Readings(data=text)
        reread, _ = self.write_and_read(atst)
        self.assertEqual(reread.readings.to_text()["C1"].tolist(), ["", ""])

    def test_unannotated_layout_row_rejects_data_and_na(self):
        for values in (["0.1", ""], ["NA", ""]):
            with self.subTest(values=values):
                atst = self.fixture()
                atst.layout.data.loc[len(atst.layout.data)] = {
                    "well_loc": "C1",
                    "type": "",
                    "phage_id": "",
                    "isolate_id": "",
                }
                text = atst.readings.to_text()
                text["C1"] = values
                atst.readings = Readings(data=text)
                with self.assertRaisesRegex(
                    ATSTValidationError, "must be absent from READINGS or have only empty"
                ):
                    validate_atst(atst)

    def test_annotated_layout_row_still_requires_readings(self):
        atst = self.fixture()
        atst.layout.data.loc[len(atst.layout.data)] = {
            "well_loc": "C1",
            "type": "Blank",
            "phage_id": "",
            "isolate_id": "",
        }
        with self.assertRaisesRegex(
            ATSTValidationError, "Annotated LAYOUT well_loc values missing"
        ):
            validate_atst(atst)


if __name__ == "__main__":
    unittest.main()
