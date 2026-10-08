# Coelho 2025 Figure 1A curation

Sources: [paper](https://doi.org/10.1038/s42003-024-07269-0) and [supplementary workbook](sources/42003_2024_7269_MOESM4_ESM.xlsx). This example contains Figure 1A OD600 data.

`Figure 1!A1` labels panel 1A. Row 2 contains group names at `B2` (PA14), `J2` (PA14 + VAC1), and `R2` (PA14 + VAC3). Time is `A3:A11`; the raw groups are `B3:I11`, `J3:Q11`, and `R3:Y11`. They yield 24 curves × 9 time points. Source time values are 0, 1, 2, 17, 19, 21, 24, 26 and 40 hours; they are retained without interpolation. Curve IDs run `curve_A`-`curve_X` in Excel left-to-right order. Replicate 1-8 is local column order.

The paper's Figure 1 caption says experiments were performed in three replicates, while the workbook provides eight numeric columns for each condition. All eight are retained as source curves with replicate labels based on column order. Means and sample SD shown by the reader are calculated from those eight columns and may therefore differ from the paper's plotted summary.

Paper Methods, *Phage infections*, reports PA14 inoculation into 5 mL LB, 37 °C, 120 rpm, phage MOI 0.01, and OD600 spectrophotometry. The phage genome accessions come from paper Data Availability, not the workbook.
