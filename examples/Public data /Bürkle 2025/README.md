# Bürkle 2025 OD600 example

One study links five OD600 source blocks: main Figures 1A and 6A, supplementary Figures S1B, S1C and S6B. The [standalone linked ATST package](atst_burkle_2025/) is separate from [sources and curation](read_shared_data/). The package contains OD600 readings.

1. Run [write_atst.ipynb](read_shared_data/write_atst.ipynb) from `read_shared_data/` to regenerate the package.
2. Run [read_atst.ipynb](read_atst.ipynb) from this folder for S6B raw curves, medians with hourly min-max whiskers, assay/entity details and a summary table.
3. Run [direct_read.ipynb](direct_read.ipynb) here for matching plots from hard-coded workbook ranges, followed by paper/workbook source pointers.

Use Python 3.10+ with pandas, openpyxl, matplotlib, IPython/Jupyter and the local ATST package for the writer and ATST reader. The direct reader uses the source workbook. [Curation notes](read_shared_data/curation.md) document source positions, missing readings, duplicate curves and unresolved provenance.

Each layout has `curve_id`, `type`, `isolate_id`, `phage_id`, `treatment`, `replicate`. Curve IDs start at `curve_A` per readout. Combination IDs in PHAGES are local mixture records with explicit constituent phages; they are not single genomes.
