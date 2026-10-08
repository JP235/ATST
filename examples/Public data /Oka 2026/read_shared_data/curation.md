# Oka 2026 OD600 curation

Sources: [paper](https://doi.org/10.3390/v18010092); [S5](sources/TableS5_growth%20curve%20MOI%20controlled.csv), [S6](sources/TableS6_growth%20curve%20from%20plaque.csv), and [S7](sources/TableS7_growth%20curve%20from%20sewage.csv). Each CSV contributes one OD600 readout and layout.

| Readout | Source structure | Host | Curves | Time points |
| --- | --- | --- | ---: | ---: |
| MOI_controlled | S5 row 1 labels; rows 2-139; 7 T-phages × 3 MOIs × 3 replicates, 3 no-phage, 1 blank | *E. coli* NBRC 13168 | 67 | 138 |
| Plaque_derived | S6 row 1 status, row 2 labels; rows 3-147; 7 T-phages × 3, 3 no-phage, 1 blank | *E. coli* NBRC 13168 | 25 | 145 |
| Sewage_isolates | S7 row 1 genome group/status, row 2 labels; rows 3-147; 24 isolates, 1 no-phage, 1 blank | *E. coli* NBRC 13898 | 26 | 145 |

S5 fields 2-64 are ordered triplets for T1-T7 at MOI 1, 0.1, 0.01; fields 65-67 are no-phage controls and field 68 is blank. S6 fields 2-22 are ordered T1-T7 triplets; 23-25 are controls; 26 is blank. S7 fields 2-25 are isolate 1-24; 26 is control; 27 is blank. Both S6 and S7 have no measured MOI because phages were added without prior titer determination. S7's S1/S2/S3 `genome_based_species` labels are preserved as source classes, not conflated with the isolate IDs or precise taxonomic names.

S6 source field 17 (T6 first replicate) is marked `excluded` in row 1, matching Methods 2.5.2: no lysis, excluded from downstream analysis. S7 fields 3, 17, 22 (isolates 2, 16, 21) are marked `excluded`; Methods 2.5.3 says sample 2 yielded inadequate genomic DNA and 16/21 showed no lysis. All four OD600 curves and their readings remain in ATST; the source exclusions are documented here.

**S5 alignment repair:** source row 139 (time 82199.99 s) has values through field 67 but lacks field 68 (`blank`). Row 140 has no timestamp and only `0.2358` in field 65. The first timed row is complete. The writer assigns that orphan `0.2358` to row 139's blank reading because it is the only missing value and matches adjacent blank readings (about 0.23-0.24). The assignment is inferred from CSV structure and recorded in readout METADATA and both reader notebooks.

Paper Methods 2.1-2.2 identify T1-T7 from NBRC and hosts NBRC 13168/13898. Methods 2.5 reports Varioskan LUX OD600, LB, 96-well plates, 37 °C, continuous 600 rpm orbital shaking, and approximately 10-minute sampling. Source timestamps are preserved in seconds, including 599.99 and 82199.99. S6 triplets retain source replicate order; S7 numbered columns are distinct phage isolates.
