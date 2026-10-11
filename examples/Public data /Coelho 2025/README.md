# Coelho 2025 Figure 1A liquid-assay example

One linked ATST study has one OD600 readout for PA14 alone, PA14 + VAC1, and PA14 + VAC3. The [standalone linked package](atst_coelho_2025/) is separate from [sources and curation](read_shared_data/). Each condition retains eight workbook columns at nine source time points.

1. Run [write_atst.ipynb](read_shared_data/write_atst.ipynb) from `read_shared_data/` to regenerate the package.
2. Run [read_atst.ipynb](read_atst.ipynb) from this directory. Both readers plot `Fig_1A` as median lines with min-max whiskers across eight source curves per condition, labelled PA14 control, PA14 + VAC1 and PA14 + VAC3. The ATST reader also displays stored context and summary values.
3. Run [direct_read.ipynb](direct_read.ipynb) from this directory for matching plots read directly from the source files.

Use Python 3.10+ with pandas, openpyxl, matplotlib, IPython/Jupyter, and the local ATST package for writing and reading ATST. The direct reader uses the source workbook. [Curation notes](read_shared_data/curation.md) cover evidence and limitations.

Layouts use `curve_id`, `type`, `isolate_id`, `phage_id`, `moi`, `replicate`. `curve_A` maps to Excel B and `curve_X` to Excel Y. The paper caption reports three experiments although the workbook has eight columns per condition; all source curves are retained.
