# Costa 2024 liquid-assay example

One Costa study combines the two public plate-reader workbooks into two workbook-level readouts and 783 curves. The linked ATST output is in [`atst_costa_2024/`](atst_costa_2024/); the original sources, curated inputs and writer notebook are in [`read_shared_data/`](read_shared_data/).

## Walkthrough

1. Run [write_atst.ipynb](read_shared_data/write_atst.ipynb) from `read_shared_data/`. It reads the original XLSX files, curated layouts and entity definitions, then writes the linked ATST package to `../atst_costa_2024/`.
2. Run [read_atst.ipynb](read_atst.ipynb) from this directory. The ATST and direct readers select `raw_all`, retain isolates with both Pa2 and uninfected controls, and plot mean ± sample SD for each phage/dose condition. The ATST reader also displays stored assay and entity context.
3. Run [direct_read.ipynb](direct_read.ipynb) from this directory for matching plots read directly from the source files.

Use Python 3.10+ with pandas, openpyxl, matplotlib and a Jupyter/IPython kernel. The writer and ATST reader also require the local ATST package. The direct-reading notebook reads the source workbooks.

## Files

```text
Costa 2024/
  README.md
  read_atst.ipynb
  direct_read.ipynb
  atst_costa_2024/
    atst_costa_2024.atst.txt
    metadata/           two linked metadata files
    assays/             one shared assay.tsv
    entities/           linked isolate, phage and medium tables
    layouts/            one linked layout per readout
    readings/           one linked readings table per readout
  read_shared_data/
    write_atst.ipynb
    curation.md
    layout_inputs/      curated layouts used by the writer
    entities/           curated CSV inputs
    sources/            original XLSX files and supplements
```

Share the whole `atst_costa_2024/` folder to share the standalone ATST package. Its container links to files within that folder. Keep `read_shared_data/` for the source evidence and reproducible conversion. [Curation notes](read_shared_data/curation.md) explain the inferred dose labels and layout derivation; [source inventory](read_shared_data/sources/README.md) records the originals and checksums.

Each layout has exactly six columns: `curve_id`, `type`, `isolate_id`, `phage_id`, `moi` or `pfu_ml`, and `replicate`. The MOI10 workbook uses `moi`; the raw workbook uses `pfu_ml`. Curve IDs start at `curve_A` within each readout. The curated layout inputs retain source-column and worksheet order.

