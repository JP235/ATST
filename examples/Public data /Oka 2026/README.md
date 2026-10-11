# Oka 2026 OD600 example

One [linked ATST study](atst_oka_2026/) contains all three shared OD600 tables: controlled MOI T-phages (S5), plaque-derived T-phages (S6), and sewage isolates (S7). The [writer](read_shared_data/write_atst.ipynb) reads the original CSV files from [sources](read_shared_data/sources/) and creates three readouts. Excluded source curves are retained and annotated.

Run the writer from `read_shared_data/` and the readers from this folder. Both readers select `MOI_controlled`. Individual curves are faceted by phage after selecting the recorded host; a second plot shows mean ± sample SD by MOI in each phage facet, including the recorded controls and blank. Plot times remain in seconds.

Python 3.10+, pandas, matplotlib, IPython/Jupyter and the local ATST package are needed for writing and ATST reading. The direct reader uses the source CSVs. [Curation notes](read_shared_data/curation.md) cover source columns, exclusions and alignment repair.

Each layout uses `curve_id`, `type`, `isolate_id`, `phage_id`, `moi`, `replicate`. IDs start at `curve_A` per readout. Times are stored and plotted in seconds.
