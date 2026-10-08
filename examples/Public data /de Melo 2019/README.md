# de Melo 2019 liquid-assay example

One study readout combines Lfar01 at 10^6 and 10^7 PFU/mL, ATCC 27853 at 10^7, and BOIJ02 at 10^7. The 24 curves contain BrSP1 and matched no-phage triplicates at eight time points. The [standalone linked ATST package](atst_de_melo_2019/) is separate from [sources and curation](read_shared_data/).

1. Run [write_atst.ipynb](read_shared_data/write_atst.ipynb) from `read_shared_data/` to regenerate the linked package.
2. Run [read_atst.ipynb](read_atst.ipynb) from this folder to plot both Lfar01 doses, inspect assay/entities, and calculate mean and sample SD from raw replicates.
3. Run [direct_read.ipynb](direct_read.ipynb) from this folder for the same plot directly from the supplementary workbook; the following markdown gathers assay and identity details with source locations.

Use Python 3.10+ with pandas, openpyxl, matplotlib, IPython/Jupyter and the local ATST package for the writer and ATST reader. The direct reader uses workbook ranges. [Curation notes](read_shared_data/curation.md) document source ranges, decisions and limits.

The six-column layouts use `curve_id`, `type`, `isolate_id`, `phage_id`, `pfu_ml`, `replicate`. Controls have `pfu_ml=0`; exposed curves use the reported dose. Curve IDs are unique across the four source groups. The source workbook’s calculated mean/SD columns are excluded. These are test-tube assays.
