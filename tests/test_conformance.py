import tempfile
import unittest
from pathlib import Path

from ATST import read_atst, write_atst
from ATST.errors import ATSTParseError, ATSTValidationError

from tests.helpers import block_text, minimal_atst_text, remove_block, write_atst_text


VALID_ATST_TEXT = minimal_atst_text()

MISSING_FILE_START_TEXT = VALID_ATST_TEXT.replace("===FILE_START\n", "", 1)
MISSING_FILE_END_TEXT = VALID_ATST_TEXT.replace("===FILE_END\n", "", 1)
MISSING_ASSAY_BLOCK_TEXT = remove_block(VALID_ATST_TEXT, "ASSAY")
MISSING_ASSAY_TIME_UNIT_TEXT = VALID_ATST_TEXT.replace("time_unit    \ts\n", "", 1)
MISSING_STUDY_TITLE_TEXT = VALID_ATST_TEXT.replace(
    "title    \tMinimal ATST example\n", "", 1
)
MISSING_STUDY_ID_TEXT = VALID_ATST_TEXT.replace(
    "study_id \tATST_MINIMAL\n", "", 1
)
EMPTY_STUDY_TITLE_TEXT = VALID_ATST_TEXT.replace(
    "title    \tMinimal ATST example", "title    \t", 1
)
EMPTY_STUDY_ID_TEXT = VALID_ATST_TEXT.replace(
    "study_id \tATST_MINIMAL", "study_id \t", 1
)
LAYOUT_WITH_UNMAPPED_WELL_TEXT = VALID_ATST_TEXT.replace(
    ":::LAYOUT_END",
    "C1\tBlank\n:::LAYOUT_END",
    1,
)
READINGS_WITH_UNMAPPED_WELL_TEXT = VALID_ATST_TEXT.replace(
    "\tB3\n",
    "\tB3\tC1\n",
    1,
).replace("\t0.01\n", "\t0.01\t0.20\n")
DUPLICATE_TIME_TEXT = VALID_ATST_TEXT.replace("600 \t", "0   \t", 1)
DECREASING_TIME_TEXT = VALID_ATST_TEXT.replace("600 \t", "-1  \t", 1)
NON_NUMERIC_TIME_TEXT = VALID_ATST_TEXT.replace("600 \t", "ten \t", 1)
DUPLICATE_ENTITY_PRIMARY_KEY_TEXT = VALID_ATST_TEXT.replace(
    "ph_2     \t240123bp",
    "ph_1     \t240123bp",
    1,
)
MIXED_INLINE_AND_LINKED_READINGS_TEXT = VALID_ATST_TEXT.replace(
    ":::READINGS_START\n",
    ":::READINGS_START\n<<<READOUT readout_id=OD600 file=readings.tsv\n",
    1,
)

_VALID_LAYOUT_BLOCK = block_text(VALID_ATST_TEXT, "LAYOUT")
_VALID_READINGS_BLOCK = block_text(VALID_ATST_TEXT, "READINGS")
INCORRECT_BLOCK_ORDER_TEXT = VALID_ATST_TEXT.replace(
    _VALID_LAYOUT_BLOCK,
    "__LAYOUT__",
    1,
).replace(
    _VALID_READINGS_BLOCK,
    _VALID_LAYOUT_BLOCK,
    1,
).replace(
    "__LAYOUT__",
    _VALID_READINGS_BLOCK,
    1,
)

DUPLICATE_READOUT_IDS = """\
:::READOUT_IDS_START
readout_id
OD600
OD600
:::READOUT_IDS_END

"""
DUPLICATE_READOUT_ID_TEXT = VALID_ATST_TEXT.replace(
    ":::METADATA_START",
    DUPLICATE_READOUT_IDS + ":::METADATA_START",
    1,
)

OD600_READOUT_IDS = """\
:::READOUT_IDS_START
readout_id
OD600
:::READOUT_IDS_END

"""
UNREGISTERED_GFP_READINGS_BLOCK = """\
:::READINGS_START
%%%READOUT_START readout_id=GFP
Time\tA1\tA2\tA3\tB1\tB2\tB3
0\t0.10\t0.09\t0.01\t0.10\t0.09\t0.01
600\t0.10\t0.12\t0.01\t0.12\t0.12\t0.01
%%%READOUT_END
:::READINGS_END"""
UNREGISTERED_READOUT_ID_TEXT = VALID_ATST_TEXT.replace(
    ":::METADATA_START",
    OD600_READOUT_IDS + ":::METADATA_START",
    1,
).replace(
    _VALID_READINGS_BLOCK,
    UNREGISTERED_GFP_READINGS_BLOCK,
    1,
)

READOUT_IDS_WITH_FILE_COLUMN = """\
:::READOUT_IDS_START
readout_id\treadings_file
OD600\treadings.tsv
:::READOUT_IDS_END

"""
READOUT_IDS_WITH_FILE_COLUMN_TEXT = VALID_ATST_TEXT.replace(
    ":::METADATA_START",
    READOUT_IDS_WITH_FILE_COLUMN + ":::METADATA_START",
    1,
)
SINGLE_LINKED_READINGS_BLOCK = """\
:::READINGS_START
<<<READOUT file=readings.tsv
:::READINGS_END"""
SINGLE_LINKED_READINGS_TEXT = VALID_ATST_TEXT.replace(
    _VALID_READINGS_BLOCK,
    SINGLE_LINKED_READINGS_BLOCK,
    1,
)
SINGLE_LINKED_READINGS_FILE_TEXT = """\
Time\tA1\tA2\tA3\tB1\tB2\tB3
0\t0.10\t0.09\t0.01\t0.10\t0.09\t0.01
600\t0.10\t0.12\t0.01\t0.12\t0.12\t0.01
"""

LAYOUT_WELL_COLUMN = "well_loc"
TIME_COLUMN = "Time"
UNMAPPED_READINGS_WELL = "C1"
INVALID_OUTPUT_FILE_NAME = "invalid.atst.tsv"


class ParserConformanceTests(unittest.TestCase):
    def assert_rejected(self, text: str, error: type[Exception]) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_atst_text(Path(directory), text)
            with self.assertRaises(error):
                read_atst(path)

    def test_accepts_valid_file_and_matches_wells_by_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            atst = read_atst(write_atst_text(Path(directory), VALID_ATST_TEXT))

        layout_wells = set(atst.layout.data[LAYOUT_WELL_COLUMN])
        readings_wells = set(atst.readings.data.columns) - {TIME_COLUMN}
        self.assertEqual(layout_wells, readings_wells)

    def test_rejects_missing_file_start(self) -> None:
        self.assert_rejected(MISSING_FILE_START_TEXT, ATSTParseError)

    def test_rejects_missing_file_end(self) -> None:
        self.assert_rejected(MISSING_FILE_END_TEXT, ATSTParseError)

    def test_rejects_missing_required_block(self) -> None:
        self.assert_rejected(MISSING_ASSAY_BLOCK_TEXT, ATSTParseError)

    def test_rejects_incorrect_block_order(self) -> None:
        self.assert_rejected(INCORRECT_BLOCK_ORDER_TEXT, ATSTParseError)

    def test_rejects_missing_required_assay_field(self) -> None:
        self.assert_rejected(MISSING_ASSAY_TIME_UNIT_TEXT, ATSTValidationError)

    def test_rejects_missing_required_study_fields(self) -> None:
        self.assert_rejected(MISSING_STUDY_TITLE_TEXT, ATSTValidationError)
        self.assert_rejected(MISSING_STUDY_ID_TEXT, ATSTValidationError)

    def test_rejects_empty_required_study_fields(self) -> None:
        self.assert_rejected(EMPTY_STUDY_TITLE_TEXT, ATSTValidationError)
        self.assert_rejected(EMPTY_STUDY_ID_TEXT, ATSTValidationError)

    def test_rejects_layout_well_missing_from_readings(self) -> None:
        self.assert_rejected(LAYOUT_WITH_UNMAPPED_WELL_TEXT, ATSTValidationError)

    def test_rejects_readings_well_missing_from_layout(self) -> None:
        self.assert_rejected(READINGS_WITH_UNMAPPED_WELL_TEXT, ATSTValidationError)

    def test_rejects_duplicate_time(self) -> None:
        self.assert_rejected(DUPLICATE_TIME_TEXT, ATSTValidationError)

    def test_rejects_decreasing_time(self) -> None:
        self.assert_rejected(DECREASING_TIME_TEXT, ATSTValidationError)

    def test_rejects_non_numeric_time(self) -> None:
        self.assert_rejected(NON_NUMERIC_TIME_TEXT, ATSTValidationError)

    def test_rejects_duplicate_entity_primary_key(self) -> None:
        self.assert_rejected(DUPLICATE_ENTITY_PRIMARY_KEY_TEXT, ATSTValidationError)

    def test_rejects_duplicate_readout_id(self) -> None:
        self.assert_rejected(DUPLICATE_READOUT_ID_TEXT, ATSTValidationError)

    def test_rejects_unregistered_readout_id(self) -> None:
        self.assert_rejected(UNREGISTERED_READOUT_ID_TEXT, ATSTParseError)

    def test_rejects_mixed_inline_and_linked_readings(self) -> None:
        self.assert_rejected(MIXED_INLINE_AND_LINKED_READINGS_TEXT, ATSTParseError)

    def test_rejects_file_columns_in_readout_ids(self) -> None:
        self.assert_rejected(READOUT_IDS_WITH_FILE_COLUMN_TEXT, ATSTValidationError)

    def test_accepts_single_link_without_readout_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "readings.tsv").write_text(
                SINGLE_LINKED_READINGS_FILE_TEXT,
                encoding="utf-8",
            )
            atst = read_atst(write_atst_text(directory, SINGLE_LINKED_READINGS_TEXT))

        self.assertEqual(atst.readings.linked_file, "readings.tsv")


class WriterConformanceTests(unittest.TestCase):
    def test_rejects_unmapped_readings_well_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            atst = read_atst(write_atst_text(directory, VALID_ATST_TEXT))
            atst.readings.data[UNMAPPED_READINGS_WELL] = [0.2, 0.3]

            with self.assertRaises(ATSTValidationError):
                write_atst(atst, directory / INVALID_OUTPUT_FILE_NAME)


if __name__ == "__main__":
    unittest.main()
