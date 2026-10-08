# Coelho 2025 Figure 1A liquid-assay example

One linked ATST study has one OD600 readout for PA14 alone, PA14 + VAC1, and PA14 + VAC3. The [standalone linked package](atst_coelho_2025/) is separate from [sources and curation](read_shared_data/). Each condition retains eight workbook columns at nine source time points.

1. Run [write_atst.ipynb](read_shared_data/write_atst.ipynb) from `read_shared_data/` to regenerate the package.
2. Run [read_atst.ipynb](read_atst.ipynb) here to plot all 24 curves followed by group median with min-max whiskers, print assay and entity details, and display the summary values.
3. Run [direct_read.ipynb](direct_read.ipynb) here for the same raw-curve and median/min-max whisker plots directly from hard-coded Excel ranges; the following markdown identifies paper and workbook sources.

Use Python 3.10+ with pandas, openpyxl, matplotlib, IPython/Jupyter, and the local ATST package for writing and reading ATST. The direct reader uses the source workbook. [Curation notes](read_shared_data/curation.md) cover evidence and limitations.

Layouts use `curve_id`, `type`, `isolate_id`, `phage_id`, `moi`, `replicate`. `curve_A` maps to Excel B and `curve_X` to Excel Y. The paper caption reports three experiments although the workbook has eight columns per condition; all source curves are retained.
