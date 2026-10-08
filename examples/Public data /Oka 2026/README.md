# Oka 2026 OD600 example

One [linked ATST study](atst_oka_2026/) contains all three shared OD600 tables: controlled MOI T-phages (S5), plaque-derived T-phages (S6), and sewage isolates (S7). The [writer](read_shared_data/write_atst.ipynb) reads the original CSV files from [sources](read_shared_data/sources/) and creates three readouts. Excluded source curves are retained and annotated.

Run the writer from `read_shared_data/`. Run [read_atst.ipynb](read_atst.ipynb) or [direct_read.ipynb](direct_read.ipynb) from this folder. Both readers show T1 at MOIs 1, 0.1 and 0.01 alongside no-phage controls, with raw triplicates and median/min-max whiskers. The ATST reader also displays assay and entity tables; the direct reader points to their separate paper and CSV sources.

Python 3.10+, pandas, matplotlib, IPython/Jupyter and the local ATST package are needed for writing and ATST reading. The direct reader uses the source CSVs. [Curation notes](read_shared_data/curation.md) cover source columns, exclusions and the S5 alignment repair.

Each layout uses `curve_id`, `type`, `isolate_id`, `phage_id`, `moi`, `replicate`. IDs start at `curve_A` per readout. Times are stored in seconds and shown in hours only in plots.
