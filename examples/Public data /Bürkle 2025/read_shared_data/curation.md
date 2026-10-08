# Bürkle 2025 OD600 curation

Sources: [paper](https://doi.org/10.1093/ismejo/wraf065) and [figure-source workbook](sources/raw_data_set_wraf065.xlsx). The five OD600 blocks are listed below.

| Readout | Workbook source | Host | Curves × times | Condition columns |
| --- | --- | --- | --- | --- |
| Fig_1A | Figure 1!I7:U12 | PAO1 | 12 × 6 | J:L untreated; M:O JG005; P:R JG024; S:U simultaneous pair |
| Fig_6A | Figure 6!I6:R11 | PAO1 | 9 × 6 | J:L untreated; M:O simultaneous pair; P:R sequential pair |
| Fig_S1B | Figure S1!I84:U88 | PAO1 ΔretS | 12 × 5 | J:L untreated; M:O JG005; P:R JG024; S:U pair |
| Fig_S1C | Figure S1!I94:Q99 | CHA | 8 × 6 | J:K untreated; L:M JG005; N:O JG024; P:Q pair |
| Fig_S6B | Figure S6!I9:U153 | PAO1 | 12 × 145 | J:L untreated; M:O Bhz17; P:R pair; S:U pair + Bhz17 |

Main Figures 1A and 6A share *identical* untreated and simultaneous-condition source curves. Both readouts retain their paper panel boundaries, so these trajectories recur in the linked study; they are not independent measurements. The Figure 6 worksheet's note says “for Fig. 5”, while the paper labels the sequential-treatment panel Figure 6A. Its source header `JG025 + JG005 sequential` is interpreted as JG024 followed by JG005 from the paper's Figure 6 caption and Methods; the exact source label remains in readout metadata. Do not treat JG025 as a distinct study phage.

`Not done` is present in Figure 1 cells L9, O9, R9 and U9, and Figure 6 cells L8 and O8. All six are represented by empty READINGS cells while their curves and 4-hour time points remain. Source time units remain hours for the first four readouts and minutes for S6B. S6B is 0-1440 min at 10-min intervals; both reading notebooks display time in hours without changing the stored values. Median/min-max whiskers are shown hourly for legibility, while all time points contribute to lines and summary values.

The paper reports a 1:1 phage-to-bacterium ratio for Figure 1A, and JG024 followed 2 h later by JG005 at 1×10^7 PFU/mL each for the sequential planktonic experiment. ASSAY descriptions record the source-supported doses. General planktonic Methods report LB, approximately OD600 0.01, 37 °C and 5% CO₂. The paper's Figure 1 caption identifies three biological replicates; the source uses `exp` columns.

`JG005_JG024` and `JG005_JG024_Bhz17` are local mixture entities so every exposed layout row links to PHAGES. Their `components` fields identify individual phages. JG005 and JG024 genome accessions are taken from the paper.
