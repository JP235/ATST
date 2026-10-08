import tempfile
import unittest
from pathlib import Path

import pandas as pd

from ATST import read_atst, write_atst, write_multi_readout_atst

from tests.helpers import MINIMAL_ATST_PATH


class RoundTripTests(unittest.TestCase):
    def test_public_examples_are_valid(self) -> None:
        examples = Path(__file__).resolve().parents[1] / "examples"
        for number in range(1, 6):
            path = examples / f"e{number}" / f"example_{number}.atst.txt"
            with self.subTest(path=path):
                read_atst(path, multi_readouts=number in {2, 3})

    def test_write_and_reread_preserves_measurements_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            imported = read_atst(MINIMAL_ATST_PATH)
            output_path = directory / "round_trip.atst.tsv"
            write_atst(imported, output_path, human_readable=False)
            reread = read_atst(output_path)

        pd.testing.assert_frame_equal(
            imported.readings.data,
            reread.readings.data,
            check_dtype=False,
            check_exact=True,
        )
        pd.testing.assert_frame_equal(
            imported.layout.data,
            reread.layout.data,
            check_dtype=False,
            check_exact=True,
        )

    def test_multi_readout_write_and_reread_preserves_measurements(self) -> None:
        example = Path(__file__).resolve().parents[1] / "examples" / "e2" / "example_2.atst.txt"
        imported = read_atst(example, multi_readouts=True)

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "multi-round-trip.atst.tsv"
            write_multi_readout_atst(imported, output_path)
            reread = read_atst(output_path, multi_readouts=True)

        self.assertEqual(set(imported.readouts), set(reread.readouts))
        for readout_id in imported.readouts:
            pd.testing.assert_frame_equal(
                imported.readouts[readout_id].readings.data,
                reread.readouts[readout_id].readings.data,
                check_dtype=False,
                check_exact=True,
            )


if __name__ == "__main__":
    unittest.main()
