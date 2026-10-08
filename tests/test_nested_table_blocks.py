import unittest

import pandas as pd

from ATST.blocks import Assay
from ATST.blocks.base_classes import (
    LongTable,
    LongTableBlock,
    WideTable,
    WideTableBlock,
)
from ATST.errors import ATSTValidationError


class LongTableBlockTests(unittest.TestCase):
    def test_per_readout_exposes_readouts_fields_and_common_names(self):
        block = LongTableBlock.per_readout(
            name="METADATA",
            data={
                "first": {"instrument": "reader-a", "first_only": "yes"},
                "second": {"instrument": "reader-b", "second_only": "yes"},
            },
        )

        self.assertIs(block.first, block.readouts["first"])
        self.assertEqual(
            block.instrument,
            {"first": "reader-a", "second": "reader-b"},
        )
        self.assertIn("first", dir(block))
        self.assertIn("instrument", dir(block))
        self.assertNotIn("first_only", dir(block))

    def test_rejects_mixed_leaf_and_per_readout_data(self):
        with self.assertRaisesRegex(TypeError, "LongTableBlock cannot mix"):
            LongTableBlock(
                name="METADATA",
                data={"instrument": "reader-a"},
                per_readout_data={
                    "first": LongTable(
                        name="METADATA",
                        data={"instrument": "reader-b"},
                    )
                },
            )

    def test_subclass_required_fields_are_validated_for_every_readout(self):
        with self.assertRaisesRegex(ATSTValidationError, "time_unit"):
            Assay.per_readout(name="ASSAY", data={
                "first": {"readout_type": "absorbance", "readout_unit": "OD", "time_unit": "s"},
                "second": {"readout_type": "absorbance", "readout_unit": "OD"},
            })


class WideTableBlockTests(unittest.TestCase):
    def test_per_readout_exposes_readouts_columns_and_common_names(self):
        first = pd.DataFrame({"Time": [0, 1], "A1": [0.1, 0.2]})
        second = pd.DataFrame({"Time": [0, 1], "B1": [0.3, 0.4]})
        block = WideTableBlock.per_readout(
            name="READINGS",
            data={"first": first, "second": second},
        )

        self.assertIs(block.first, block.readouts["first"])
        time_by_readout = block.Time
        if not isinstance(time_by_readout, dict):
            self.fail("Nested column access should return values by readout ID")
        pd.testing.assert_series_equal(time_by_readout["first"], first["Time"])
        pd.testing.assert_series_equal(time_by_readout["second"], second["Time"])
        self.assertIn("first", dir(block))
        self.assertIn("Time", dir(block))
        self.assertNotIn("A1", dir(block))

    def test_rejects_mixed_leaf_and_per_readout_data(self):
        with self.assertRaisesRegex(TypeError, "WideTableBlock cannot mix"):
            WideTableBlock(
                name="READINGS",
                data=pd.DataFrame({"Time": [0]}),
                per_readout_data={
                    "first": WideTable(
                        name="READINGS",
                        data=pd.DataFrame({"Time": [0]}),
                    )
                },
            )

    def test_required_columns_are_validated_for_every_readout(self):
        block = WideTableBlock.per_readout(
            name="READINGS",
            data={
                "first": pd.DataFrame({"Time": [0], "A1": [0.1]}),
                "second": pd.DataFrame({"A1": [0.2]}),
            },
        )

        with self.assertRaisesRegex(ATSTValidationError, "Time"):
            block.__post_init__({"Time"})

    def test_nested_value_equality_uses_leaf_table_contents(self):
        left = WideTableBlock.per_readout(
            name="LAYOUT",
            data={
                "first": pd.DataFrame({"well_loc": ["A1"]}),
                "second": pd.DataFrame({"well_loc": ["B1"]}),
            },
        )
        same = WideTableBlock.per_readout(
            name="LAYOUT",
            data={
                "first": pd.DataFrame({"well_loc": ["A1"]}),
                "second": pd.DataFrame({"well_loc": ["B1"]}),
            },
        )
        different = WideTableBlock.per_readout(
            name="LAYOUT",
            data={
                "first": pd.DataFrame({"well_loc": ["A1"]}),
                "second": pd.DataFrame({"well_loc": ["C1"]}),
            },
        )

        self.assertTrue(left.values_equal(same))
        self.assertFalse(left.values_equal(different))

    def test_repr_and_len_are_inherited_from_wide_table(self):
        leaf = WideTableBlock(name="LAYOUT", data=pd.DataFrame({"well_loc": ["A1"]}))

        self.assertTrue(repr(leaf).startswith("WideTableBlock("))
        self.assertEqual(len(leaf), 1)


if __name__ == "__main__":
    unittest.main()
