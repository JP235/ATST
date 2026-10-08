# Li 2025 liquid-assay example

One linked ATST study contains **seven OD600 readouts**, one for each OD600 panel in Figures 2-4: 2A, 2B, 3A, 3C, 3E, 4A and 4C. The [standalone ATST output](atst_li_2025/) is separate from [source files and curation](read_shared_data/). Figure 3E is an 8-hour endpoint; the others are time series.

1. Run [write_atst.ipynb](read_shared_data/write_atst.ipynb) from `read_shared_data/` to regenerate the package.
2. Run [read_atst.ipynb](read_atst.ipynb) from here to plot Figure 2B phiPA2/no-phage triplicates with and without synthetic signaling molecules, print assay and entity context, and calculate mean and sample SD.
3. Run [direct_read.ipynb](direct_read.ipynb) from here for the same plot from hard-coded Excel ranges; its following markdown traces the context to the paper and workbook.

Use Python 3.10+ with pandas, openpyxl, matplotlib, IPython/Jupyter and the local ATST package for writing and reading ATST. The direct reader uses workbook ranges. [Curation notes](read_shared_data/curation.md) document conditions, evidence and limitations.

Layouts use `curve_id`, `type`, `isolate_id`, `phage_id`, `moi`, `signaling_molecules`, `baicalein`, and `replicate`. The two treatment columns preserve signaling-molecule and baicalein conditions within each panel-level readout. Curve IDs start at `curve_A` in source-group/replicate order.
