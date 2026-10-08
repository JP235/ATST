# Costa 2024 curation decisions

The source data are associated with DOI 10.1126/sciadv.adj0341 and Zenodo 10.5281/zenodo.8405451, v1.0. Both local plate-reader files match the archived originals byte-for-byte. The source inventory and local copies are in `sources/`.

## Inputs and identities

- `layout_inputs/` contains one curated TSV per workbook/worksheet. Curve IDs run from `curve_A` in source-column order: Excel B maps to `curve_A`, C to `curve_B`, and so on. Each labelled group spans three columns; replicate 1/2/3 records that column order.
- `entities_definitions/ISOLATES.csv`, `PHAGES.csv` and `MEDIA.csv` are manually generated inputs from the paper's shared data.
- Hosts are engineered PAO1 constructs. Table S8 supplies plasmid names/codes, insert donors, vector and resistance marker. Main paper p. 4 supplies native promoters.
- The worksheet `PAO1` is assigned isolate ID `PAO1` here, while its material is interpreted as PAO1:pEmpty from the liquid-collapse methods (p. 9) and Fig. S8's control-plasmid definition. This cross-source interpretation is marked in the entity row because the workbook alone does not name its plasmid. Table S8 identifies pEmpty as pTU646; p. 9 identifies pEmpty with pUCP20.
- The worksheet/Table S8 label `CBASS Type III` is normalized to the Type III-C label used in Fig. S8 and the main text. Its original sheet label is retained.
- Phage IDs such as Pa3 match the FBPa3 suffix in Table S3. PP7 retains its existing name. Table S3's host strain and the assay-stock propagation host are distinct fields. Published taxonomy, morphology and PhageAI predictions are retained as reported.
- Table S3 `TBD` accessions remain blank in `genome_accession` and are preserved in `accession_as_reported`. Published `NA`/`-` annotations are retained as literal text in descriptive columns. Surrounding whitespace in accession strings is removed.
- `P3 dilution 2` in raw/PAO1 is curated as Pa3 from its paired dilution-series context; `PA33 no phage` in raw/RADAR is normalized to Pa33. These source-label corrections are documented here because LAYOUT contains only the six requested fields.

## Conditions and missing information

- Paper p. 9 provides OD600, 96-well format, LB, approximately 0.1 starting OD600, 37 C, double orbital shaking, 10 min sampling and 24 h duration. Paper p. 10 reports biological triplicates unless otherwise stated. Source Time values are rounded hours (0, 0.17, 0.33, ...); they are retained, not reconstructed as an exact 10-minute grid.
- **MOI source:** `Plate_reader_raw_MOI10.xlsx` does not put MOI in each worksheet header. The value 10 for exposed curves is inferred from the workbook filename and supported by the MOI 10 condition in Fig. S8. Uninfected controls have MOI 0 and no phage entity. This note records the inference.
- **Dilution source:** `Plate_reader_raw.xlsx` uses `dilution 1` and `dilution 2`. Its PAO1 worksheet omits their numeric values, so `dilution 1 = 1*10^7` and `dilution 2 = 1*10^6` are inferred from the same labels explicitly annotated in the other worksheets. The `pfu_ml` column records these source-derived labels for phage-exposed curves. `no dilution` is preserved literally for the three Pa53 and three PP7 curves on raw/PAO1; it is not a numeric PFU/mL value and must not be compared numerically with the numbered `pfu_ml` labels. Uninfected controls have an empty `pfu_ml`. Units and final-well MOI are not established by these labels; Fig. S8's MOI 0.01 curves cannot be assigned to specific raw-workbook columns with confidence.
- Culture selection with carbenicillin 200 ug/mL is reported on p. 7.
- Worksheet column groups define `curve_id` layouts. Matching metadata, assay and Time columns combine these into two workbook-level ATST readouts. The raw/PAO1 sheet has 156 curves; source-column IDs preserve those curves.
- All columns are preserved, including any duplicate trajectories. An entirely blank trailing row in the MOI10/AVAST sheet is ignored.

## Matched notebook demonstration

`../read_atst.ipynb` selects `moi10_all`, host `PAO1_Zorya_Type_I`, phage `Pa3`, and the three preceding uninfected curves. It plots six curves for each host, then immediately prints conditions and accesses both host records plus the phage and medium tables. `../direct_read.ipynb` selects the original Excel ranges for `Zorya Type I` (time A2:A146, controls B2:D146, infected E2:G146) and `PAO1` (time A2:A146, controls B2:D146, infected H2:J146) and uses the same plotting code. Its next cell records the same context with exact paper/table/figure locators. The figure is a full 24-hour replicate plot, not a reproduction of the 12-hour mean plot in Fig. S8.
