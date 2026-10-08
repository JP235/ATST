# de Melo 2019 curation

Sources: [paper](https://doi.org/10.1186/s12866-019-1481-z) and [Additional file 8](sources/12866_2019_1481_MOESM7_ESM.xlsx), the shared absorbance workbook.

| Readout | Sheet | Phage dose annotation | Infected time + raw triplicates | Control time + raw triplicates |
| --- | --- | --- | --- | --- |
| Lfar01_1e6 | Plan1 | B3:B4 | B7:E14 | B21:E28 |
| Lfar01_1e7 | Plan1 | B32:B34 | B37:E44 | B51:E58 |
| ATCC27853_1e7 | Plan2 | A16:A17 | A21:D28 | A6:D13 |
| BOIJ02_1e7 | Plan3 | A17:A18 | A22:D29 | A7:D14 |

The single readout combines four strain/dose groups with their matched no-phage controls. Source triplicate columns are C:E in Plan1 and B:D in Plan2/Plan3. The numeric `pfu_ml` field records the workbook's 10^6 or 10^7 PFU/mL annotation; controls are 0. These are PFU/mL dose labels rather than MOI. Mean and SD columns are derived workbook calculations and excluded from READINGS.

The paper's Methods, p. 11, gives medium, salts, tube volume, temperature, shaking, sampling schedule, OD600 instrument and triplicate assays. Fig. 3, p. 6, matches the four strain/dose conditions. The workbook alone lacks this assay context. The paper's Methods, p. 10, reports Lfar01 origin as unknown; BOIJ02 provenance remains as stated in ENTITIES. BrSP1 accession and genome properties are reported on p. 3. Entity IDs normalize source names; source labels remain in metadata and this note.

The paper describes test-tube assays with time-point samples; the workbook presents replicate columns. The ATST readout groups the four strain/dose conditions from that workbook.
