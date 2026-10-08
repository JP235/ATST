import unittest

from ATST import read_atst
from streamlit_app.generator.plotting import plot_readings_by_layout
from tests.helpers import MINIMAL_ATST_PATH


class GeneratorPlottingTests(unittest.TestCase):
    def test_ignored_types_are_removed_from_groups_and_references(self):
        atst = read_atst(MINIMAL_ATST_PATH)

        figure = plot_readings_by_layout(
            atst,
            show_reference=["Control"],
            ignore_types=["Control"],
            include_in_legend=[],
        )

        self.assertEqual(
            [trace.name for trace in figure.data],
            ["A1", "A3", "B1", "B3"],
        )

    def test_non_ignored_reference_types_are_still_shown(self):
        atst = read_atst(MINIMAL_ATST_PATH)

        figure = plot_readings_by_layout(
            atst,
            group_by=["type"],
            show_reference=["Blank", "Control"],
            ignore_types=["Control"],
            include_in_legend=[],
        )

        trace_names = [trace.name for trace in figure.data]
        self.assertNotIn("A2", trace_names)
        self.assertNotIn("B2", trace_names)
        self.assertFalse(any("reference: Control" in name for name in trace_names))
        self.assertTrue(any("reference: Blank" in name for name in trace_names))


if __name__ == "__main__":
    unittest.main()
