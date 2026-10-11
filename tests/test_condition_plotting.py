import unittest
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import pandas as pd

from ATST.plotting import plot_readouts, summarize


class ConditionPlottingTests(unittest.TestCase):
    def setUp(self):
        self.atst = SimpleNamespace(
            readout_id="growth",
            assay=SimpleNamespace(time_unit="h", readout_unit="OD600"),
            layout=SimpleNamespace(data=pd.DataFrame({
                "curve_id": ["curve_1", "curve_2", "curve_3", "curve_4"],
                "type": ["control", "treated", "treated", "treated"],
                "phage_id": ["", "P", "P", "P"],
                "isolate_id": ["A", "A", "A", "B"],
                "replicate": ["1", "1", "1", ""],
            })),
            readings=SimpleNamespace(data=pd.DataFrame({
                "Time": [0, 1], "curve_1": [0, 4], "curve_2": [0, 2],
                "curve_3": [0, 6], "curve_4": [0, 8],
            })),
        )

    def tearDown(self):
        plt.close("all")

    def test_summary_counts_curves_without_replicate_labels(self):
        for remove_replicate in [False, True]:
            if remove_replicate:
                self.atst.layout.data = self.atst.layout.data.drop(columns="replicate")
            stats = summarize(self.atst, group_by="isolate_id", filters={"isolate_id": "A"})
            row = stats.iloc[1]
            self.assertEqual(row["n"], 3)
            self.assertEqual(row["mean"], 4)
            self.assertEqual(row["sd"], 2)
            self.assertEqual(row["median"], 4)
            self.assertEqual(row["min"], 2)
            self.assertEqual(row["max"], 6)

    def test_facet_requires_every_filter_value_by_default(self):
        options = {"group_by": "phage_id", "facet_by": "isolate_id",
                       "filters": {"phage_id": ["", "P"]}, "return_fig": True}
        strict = plot_readouts([self.atst], **options)
        partial = plot_readouts([self.atst], require_all_filters=False, **options)
        self.assertEqual(len(strict.axes), 1)
        self.assertEqual(len(partial.axes), 2)
        self.assertEqual([t.get_text() for t in partial.legends[0].get_texts()], ["control", "P"])
        self.assertEqual(partial.legends[0].get_title().get_text(), "phage_id")
        self.assertTrue(all(ax.get_legend() is None for ax in partial.axes))

    def test_points_summary_and_supplied_axis(self):
        with self.assertRaisesRegex(ValueError, "points_only"):
            plot_readouts([self.atst], group_by="phage_id", summary="mean_sd", points_only=True)
        fig, ax = plt.subplots()
        result = plot_readouts([self.atst], group_by="phage_id", summary="median_minmax",
                              points_only=True, axes=ax, title="Selected conditions")
        self.assertIsNone(result)
        self.assertEqual(ax.get_title(), "Selected conditions")
        self.assertEqual(len(fig.axes), 1)
        for container in ax.containers:
            self.assertEqual(container.lines[0].get_linestyle(), "None")
        self.assertEqual(len(ax.containers), 2)
