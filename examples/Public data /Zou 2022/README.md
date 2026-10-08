# Zou 2022 longitudinal absorbance example

The supplied publication is Zou *et al.* (2022), DOI 10.1038/s41467-022-31934-9; this example folder was renamed from `Zou 2021` to match the paper. One [linked ATST study](atst_zou_2022/) contains OD600 from seven worksheets (`Fig. 1b-1c`, `Fig. 3a-c`, `SFig. 3`, `SFig. 6`, `Fig. 4e`, `Fig. 4f`, `Fig. 4g`) and separate OD445 DAAO-reaction absorbance readouts for Figures 4e and 4f. Figure 4 bioreactor readouts contain longitudinal absorbance.

Run [write_atst.ipynb](read_shared_data/write_atst.ipynb) from `read_shared_data/` to regenerate the package. Run [read_atst.ipynb](read_atst.ipynb) or [direct_read.ipynb](direct_read.ipynb) from this folder for matching Figure 1c T1 plots across three MOIs and PT-/PT+ hosts. The ATST reader shows assay and entity context; the direct reader points to separate source positions.

Requires Python 3.10+, pandas, openpyxl, matplotlib, IPython/Jupyter, and the local ATST package for writing and ATST reading. The direct reader uses the source workbook. [Curation notes](read_shared_data/curation.md) document source structure and mixed assay modes.

Each layout has `curve_id`, `type`, `isolate_id`, `phage_id`, `moi`, `replicate`, `assay_mode`. Curve IDs start at `curve_A` per readout. Source time remains in hours.
