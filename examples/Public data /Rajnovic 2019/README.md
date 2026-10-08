# Rajnovic 2019 OD600 example

One linked ATST study includes the ten bacterial-concentration sheets (90 conditions) and the LB-only blank from the [shared S1 Dataset workbook](read_shared_data/sources/pone.0216292.s002.xlsx). Matching metadata, assay and Time values combine three sheets, yielding nine readouts; the [standalone ATST package](atst_rajnovic_2019/) is separate from [sources and curation](read_shared_data/). The package contains source OD600 time series.

1. Run [write_atst.ipynb](read_shared_data/write_atst.ipynb) from `read_shared_data/` to regenerate the package.
2. Run [read_atst.ipynb](read_atst.ipynb) from this folder to plot all 10^5 CFU/mL conditions, calculate median/min-max, and inspect linked assay/entities.
3. Run [direct_read.ipynb](direct_read.ipynb) here for matching plots from fixed workbook ranges and source pointers into the paper/workbook.

Requires Python 3.10+, pandas, openpyxl, matplotlib, IPython/Jupyter and the local ATST package for writing and ATST reading. The direct reader uses fixed workbook ranges. [Curation notes](read_shared_data/curation.md) document gaps, starred text cells, and provenance.

Layouts contain `curve_id`, `type`, `isolate_id`, `phage_id`, `bacteria_cfu_ml`, `pfu_ml`, `replicate`. IDs start at `curve_A` per readout. The blank has no bacterial or phage entity ID.
