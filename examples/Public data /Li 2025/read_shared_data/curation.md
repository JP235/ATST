# Li 2025 curation

Sources: [paper](https://doi.org/10.1128/aem.02402-24) and [Supplemental file 2](sources/aem.02402-24-s0002.xlsx), the source of figure statistics.

| Readout | Workbook sheet | Measurement rows | Curves | Figure context |
| --- | --- | --- | ---: | --- |
| Fig_2A | Fig 2A | 2:8 | 30 | OD600, CFS conditions, MOI 2 |
| Fig_2B | Fig 2B | 2:11 | 12 | OD600, synthetic signals, MOI 0.01 |
| Fig_3A | Fig 3A | 2:8 | 21 | OD600, QS mutants, low density, MOI 0.01 |
| Fig_3C | Fig 3C | 2:6 | 21 | OD600, QS mutants, high density, MOI 0.01 |
| Fig_3E | Fig 3E | 2:4 | 21 | OD600 at 8 h after nutrient supplement, MOI 0.01 |
| Fig_4A | Fig 4A | 2:8 | 12 | OD600, baicalein, low density, MOI 0.01 |
| Fig_4C | Fig 4C | 2:8 | 12 | OD600, baicalein, high density, MOI 0.01 |

Time-series sheets use column A as time and three adjacent columns per condition (header in first of three). Figure 3E instead has seven condition headers in A1:G1 and three replicate rows A2:G4. Its Time=8 h is from the Figure 3 caption, not a time cell in the workbook. READINGS contain the measurement rows. The first curve in each readout is `curve_A`; source positions follow the header's left-to-right group order and replicate order. Figure 3E uses top-to-bottom replicate order within each source column.

The layout preserves `signaling_molecules` and `baicalein` fields; Figure 2A source labels provide CFS context. `moi` is 0 for no-phage controls and the figure-caption value for phiPA2-exposed curves. Figure 2A uses the caption's MOI 2 even though the Methods call it approximate. Figure 3E phage exposure and 8-hour timing come from the Figure 3 caption/Methods, not the abbreviated workbook header. The paper reports 37 °C LB growth and the SP-UV 200 spectrophotometer.

`ZS_PA_35` mutant IDs and labels are local normalization of workbook headers, and deletion identity follows paper Methods; genome accession `GCA_020567355.1` refers to the parental strain. phiPA2 accession is `OK539824.1` (paper Data Availability). Condition labels in the layout and paper context should be consulted together to understand CFS source, autoinducers, baicalein and density.

The reading notebooks showcase Figure 2B. Direct reading requires workbook ranges A2:A11, B2:D11, E2:G11, H2:J11 and K2:M11 plus paper Figure 2B and Methods; ATST stores their relationships in one readout with entity and assay blocks.
