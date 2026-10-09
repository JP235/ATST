# Assay Time Series Tabular Format (ATST)

ATST is a TAB-delimited format for assay time-series readouts. It is designed to be easy to inspect in plain text, straightforward to parse, and structured enough for basic validation of assay metadata, layouts, entities, and time-series readings.

The valid ATST file extensions are `.atst.txt` and `.atst.tsv`. Python 3.10 or newer is required.

## Installation

Install the project from this repository:

```powershell
uv sync
```

Or install with pip from a fresh clone:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Blocks

| Block | Required | Form | Purpose |
| --- | --- | --- | --- |
| `FILE_INFO` | Yes | Long table | File metadata and format version. |
| `STUDY` | Yes | Long table | Study title, ID, authorship, provenance, and context. |
| `READOUT_IDS` | Multi-readout only | One-column wide table | Registry of readout IDs; optional for single-readout files. |
| `METADATA` | Yes | Long table or readout payloads | Instrument, acquisition, software, lab, operator, and run metadata. |
| `ASSAY` | Yes | Long table or readout payloads | Readout type, units, time units, optional plate format, and measurement setup. |
| `ENTITIES` | No | One or more wide tables | Centralized biological, chemical, reagent, strain, or other entity tables. |
| `LAYOUT` | Yes | Wide table or readout payloads | Well or curve annotations keyed by `well_loc` or `curve_id`. |
| `READINGS` | Yes | Wide table or readout payloads | Time-series values keyed by `Time` and the applicable layout identifiers. |

`FILE_INFO`, `STUDY`, `METADATA`, `ASSAY`, `LAYOUT`, and `READINGS` must always be present. `FILE_INFO` and `STUDY` are stored inline. Readout payloads in `METADATA`, `ASSAY`, `LAYOUT`, and `READINGS` may be stored inline or linked to external files. Each external path is declared only in its corresponding payload block. Linking changes where a payload is stored; it does not make its top-level block optional or indicate that its content is missing.

For multi-readout files, `READOUT_IDS` is the source of truth for readout identity. It contains exactly one `readout_id` column, and every readout-specific field or link must use one of its declared IDs. It never contains external file paths.

## Specification

The normative format reference is in [SPEC.md](SPEC.md). It defines delimiter syntax, block order, field forms, linking policy, identifier rules, value formats, and validation expectations.

## Minimal File Shape

```text
===FILE_START
:::FILE_INFO_START
file_name       	minimal.atst.txt
format          	ATST
format_version  	0.1
created_on      	2026-01-01
field_delimiter 	TAB
encoding        	UTF-8
:::FILE_INFO_END

:::STUDY_START
title    	Minimal ATST example
study_id 	ATST_MINIMAL
:::STUDY_END

:::METADATA_START
instrument 	ExampleReader
plate_type 	6 well plate
date_start 	2026-01-01
operator   	OP1
:::METADATA_END

:::ASSAY_START
readout_type 	absorbance
readout_unit 	od600
time_unit    	s
plate_format 	6_well
:::ASSAY_END

:::ENTITIES_START
%%%TABLE_START name=PHAGES pk=phage_id
phage_id 	gene_length 	genome
ph_1     	45031bp     	https://www.ncbi.nlm.nih.gov/datasets/genome/{}
ph_2     	240123bp    	https://www.ncbi.nlm.nih.gov/datasets/genome/{}
%%%TABLE_END

%%%TABLE_START name=ISOLATES pk=isolate_id
isolate_id 	genome
iso_1      	https://www.ncbi.nlm.nih.gov/datasets/genome/{}
%%%TABLE_END
:::ENTITIES_END

:::LAYOUT_START
well_loc	type      	phage_id 	isolate_id
A1      	Treatment 	ph_1       	iso_1
A2      	Control   	         	iso_1
A3      	Blank
B1      	Treatment 	ph_2       	iso_1
B2      	Control   	         	iso_1
B3      	Blank
:::LAYOUT_END

:::READINGS_START
Time	A1   	A2   	A3   	B1   	B2   	B3
0   	0.10 	0.09 	0.01 	0.10 	0.09 	0.01
600 	0.10 	0.12 	0.01 	0.12 	0.12 	0.01
:::READINGS_END
===FILE_END
```

## Curve-keyed layouts

Plate-based data should use `well_loc` as the LAYOUT key. When it is not
practical or convenient to provide the complete well layout and original well
identities, `curve_id` can instead identify the curves included in the file.
This is useful for non-plate assays, selected or exported curves, and derived
curve collections where the original plate geometry is unavailable or not
meaningful.

Each LAYOUT payload must contain exactly one of `well_loc` or `curve_id`. When
`curve_id` is used, each value must be non-empty and unique within that
readout, and every value must exactly match one non-`Time` READINGS column.
Curve-specific annotations such as sample, treatment, concentration, or source
file belong in additional LAYOUT columns.

Curves recorded on different days or with different acquisition settings should
be placed in separate readouts. Each such readout has its own `METADATA`,
`ASSAY`, `LAYOUT`, and `READINGS` payload. Curves acquired together with shared
metadata and assay settings can remain columns in the same READINGS payload.

Curve-keyed ATST files must currently be built using the Python package or other
code. The Streamlit generator and Layout Editor remain plate-oriented and do
not provide options for creating or editing `curve_id` layouts.

Curve-keyed file shape:

```text
:::LAYOUT_START
curve_id    	type      	sample_id 	condition
growth_01   	Treatment 	S001      	drug
growth_ctrl 	Control   	S002      	vehicle
:::LAYOUT_END

:::READINGS_START
Time 	growth_01 	growth_ctrl
0    	0.10      	0.09
600  	0.18      	0.11
:::READINGS_END
```

Python construction (starting from the supplied curve-keyed example):

```python
from ATST import read_atst, validate_atst, write_atst

atst = read_atst("examples/e5/example_5.atst.txt")
atst.study.data["title"] = "My curve collection"
validate_atst(atst)
write_atst(atst, "my_curves.atst.txt")
```

## Streamlit App Walkthrough

Run the app with:

```powershell
uv run streamlit run src/streamlit_app/ATST_Generator.py
```

If you are running it from the virtual environment, this also works:

```powershell
streamlit run src/streamlit_app/ATST_Generator.py
```

The app is a form-based ATST file builder for plate-oriented, `well_loc`-keyed
files. The main sections match the ATST blocks: `STUDY`, `METADATA`, `ASSAY`,
`LAYOUT`, optional `ENTITIES`, and `READINGS`. Press `Generate` at the end to
preview the ATST text and download the finished file. Curve-keyed files are not
supported by the Streamlit interface.

### Recommended Beginner Workflow

1. Start with device output when you have it. Open `Read Device output`, choose the device, and upload the raw output file.

2. Let the device output fill the parts it knows. A device upload fills the file name, most `METADATA`, most `ASSAY`, and the full `READINGS` table. In ATST terms, the device output gives the measurement data and acquisition details, but it does not know your full study description or experimental layout.

3. Add a study template if you have one. Open `Load template` and upload an existing ATST template. If device output was already loaded, the app preserves the parsed device fields and uses the template to fill missing study, metadata, assay, layout, and entity information. This is useful when many runs belong to the same study.

4. Fill anything still blank by hand. Use the `STUDY`, `METADATA`, and `ASSAY` tables like small spreadsheets. The default rows are the common fields. Extra rows let you add fields that are important for your lab or experiment.

5. Define the layout. The `LAYOUT` table explains what each well contains. It should include `well_loc` and `type`, and can include extra columns such as `isolate`, `phage`, `MOI`, `replicate`, or `comments`.

6. Reuse layouts across runs. If the same plate design is used for many experimental runs, create or upload the layout once, then download it from the `LAYOUT` section. For later runs, upload that layout file again or keep it inside an ATST template.

7. Use the layout preview editor for plate-shaped editing. Pick the plate format in `ASSAY`, then edit or preview wells in the `LAYOUT` section. When the editor is active, apply or cancel the edit before downloading or generating.

8. Add entity tables only when needed. `ENTITIES` is for reusable lookup tables such as strains, isolates, phages, reagents, or compounds. Upload one or more CSV/TSV/TXT tables if you want those records stored with the ATST file. The app uses each uploaded filename without its extension as the entity table name and uses the table's first column as its primary key.

9. Upload readings manually only when you are not using a device reader. The `READINGS` section accepts CSV/TSV/TXT tables with `Time` plus well columns such as `A1`, `A2`, and `B1`.

10. Generate and download. Click `Generate`, review the ATST text, then click `Download file`.

### Device Filename Hints

Device readers do not require a strict filename convention. They first read metadata from the file contents, then use the uploaded filename only as a best-effort fallback for fields the output itself does not provide. Plate or device number decisions come from the file contents, not from the filename.

When useful, filenames can still provide these hints:

- A run date written as `YYYY-MM-DD` or `YYYY_MM_DD` becomes `date_start`.
- An export timestamp such as `15-Apr-2026 20-13-11` becomes `date_export`.
- Underscore-separated descriptors are split into operator and experiment type. If there is only one descriptor, it is treated as `experiment_type` and `operator` is left blank.
- A trailing isolate token such as `PAO1` or `A1B2` is used as isolate information when possible.
- A speed token such as `150rpm` is used as a fallback `shaking_frequency` when the device output does not already provide one.

Examples:

- `2026-04-15_JM_QC_PAO1_15-Apr-2026 20-13-11.txt` can provide start date, operator `JM`, experiment type `QC`, isolate `PAO1`, and export time.
- `QC_PAO1.xlsx` can provide experiment type `QC` and isolate `PAO1`, with no operator.
- `test_run_150rpm.xlsx` can provide fallback shaking frequency `150rpm`.

### Layout-First Workflow

For repeated experiments, use the `Layout Editor` page to build a reusable layout before generating any ATST files.

1. Open the `Layout Editor` page in the Streamlit sidebar.
2. Choose the plate format, such as `96_well`.
3. Upload an existing layout table or start from a blank layout.
4. Fill one row per well, using `well_loc` for the well name and `type` for the role of that well.
5. Add columns that describe the experiment design, such as isolate, treatment, concentration, or replicate.
6. Download the layout as TSV.
7. Reuse that TSV in the generator's `LAYOUT` upload, or place it into a study template ATST file.

### Privacy and data handling

The Streamlit app does not persist uploaded or generated assay data beyond the
temporary processing and in-memory session use described below. The application
code does not write assay data to a database, application cache, analytics
service, or application logs.

- Streamlit initially buffers uploaded files in server memory. After each
  processing attempt, whether successful or unsuccessful, the app replaces the
  upload widget so its raw file buffer is released.
- ATST templates and generated ATST output use unique operating-system
  temporary directories because the core reader and writer operate on paths.
  These directories are deleted immediately after parsing or generation,
  including when an exception occurs.
- Parsed and edited tables remain only in that user's Streamlit session memory
  while the form is in use. They are needed to render and edit the form and are
  not written to persistent storage.
- A generated ATST preview and its download data exist only in memory for the
  current rendered page. They are released when another interaction reruns the
  page or the session ends.
- Closing the browser tab ends the Streamlit session, allowing its parsed and
  edited in-memory data to be released.

This statement describes the ATST application code. A deployment provider,
reverse proxy, or operating environment may have separate infrastructure and
logging policies. See Streamlit's documentation for its
[uploaded-file lifecycle](https://docs.streamlit.io/knowledge-base/using-streamlit/where-file-uploader-store-when-deleted)
and [in-memory downloads](https://docs.streamlit.io/develop/api-reference/widgets/st.download_button).

## Python Walkthrough

Use the Python package when you want to read, inspect, edit, plot, or write ATST files from a script or notebook.

1. Read an ATST file.

```python
from ATST import read_atst

atst = read_atst("examples/e1/example_1.atst.txt")
```

2. Inspect the main blocks. Long-table blocks use dictionaries. Wide-table blocks use pandas data frames.

```python
print(atst.file_info.data)
print(atst.study.data)
print(atst.metadata.data)
print(atst.assay.data)

print(atst.layout.data.head())
print(atst.readings.data.head())
```

3. Work with the layout and readings together. The `layout` block explains what each well means, and the `readings` block contains `Time` plus one column per well.

```python
treatment_wells = atst.layout.data.loc[
    atst.layout.data["type"] == "Treatment_1",
    "well_loc",
]

treatment_readings = atst.readings.data[["Time", *treatment_wells]]
print(treatment_readings.head())
```

4. Edit fields or tables with normal Python and pandas operations.

```python
atst.study.data["title"] = "Updated study title"
atst.layout.data.loc[atst.layout.data["well_loc"] == "A1", "comments"] = "checked"
```

5. Write the edited file back to disk.

```python
from ATST import write_atst

write_atst(atst, "updated_example.atst.txt")
```

6. Create each block yourself, combine the blocks into an `ATSTFile`, and save it.

```python
import pandas as pd

from ATST import ATSTFile, write_atst
from ATST.blocks import Assay, Entities, FileMetadata, Layout, Metadata, Readings, Study

file_info = FileMetadata(
    data={
        "file_name": "manual_example.atst.txt",
        "format": "ATST",
        "format_version": "0.1",
        "created_on": "2026-07-08",
        "field_delimiter": "TAB",
        "encoding": "UTF-8",
    }
)
study = Study(data={"title": "Manual ATST example", "study_id": "MANUAL_001"})
metadata = Metadata(
    data={
        "instrument": "ExampleReader",
        "plate_type": "96 well plate",
        "date_start": "2026-07-08",
        "operator": "OP1",
    }
)
assay = Assay(
    data={
        "readout_type": "absorbance",
        "readout_unit": "od600",
        "time_unit": "seconds",
        "plate_format": "96_well",
    }
)
layout = Layout(
    data=pd.DataFrame(
        [
            {"well_loc": "A1", "type": "treatment", "isolate": "ISO_1"},
            {"well_loc": "A2", "type": "blank", "isolate": ""},
        ]
    )
)
readings = Readings(
    data=pd.DataFrame(
        {
            "Time": [0, 600],
            "A1": [0.10, 0.18],
            "A2": [0.01, 0.01],
        }
    )
)

atst = ATSTFile(
    file_info=file_info,
    study=study,
    metadata=metadata,
    assay=assay,
    layout=layout,
    readings=readings,
    entities=Entities(),
)

write_atst(atst, "manual_example.atst.txt")
```

7. Create a multi-readout file when the same experiment has more than one readings table, such as OD600 and GFP.

```python
import pandas as pd

from ATST import ATSTFile, MultiReadoutATST, write_multi_readout_atst
from ATST.blocks import (
    Assay,
    Entities,
    FileMetadata,
    Layout,
    Metadata,
    Readings,
    ReadoutIds,
    Study,
)

file_info = FileMetadata(
    data={
        "file_name": "manual_multi_readout.atst.txt",
        "format": "ATST",
        "format_version": "0.1",
        "created_on": "2026-07-08",
        "field_delimiter": "TAB",
        "encoding": "UTF-8",
    }
)
study = Study(data={"title": "Manual multi-readout example", "study_id": "MULTI_001"})
metadata = Metadata(
    data={
        "instrument": "ExampleReader",
        "plate_type": "96 well plate",
        "date_start": "2026-07-08",
        "operator": "OP1",
    }
)
layout = Layout(
    data=pd.DataFrame(
        [
            {"well_loc": "A1", "type": "treatment"},
            {"well_loc": "A2", "type": "blank"},
        ]
    )
)
readout_ids = ReadoutIds(
    data=pd.DataFrame(
        [
            {"readout_id": "OD600"},
            {"readout_id": "GFP"},
        ]
    )
)

od600 = ATSTFile(
    file_info=file_info,
    study=study,
    readout_ids=readout_ids,
    metadata=metadata,
    assay=Assay(
        data={
            "readout_type": "absorbance",
            "readout_unit": "od600",
            "time_unit": "seconds",
            "plate_format": "96_well",
        }
    ),
    layout=layout,
    readings=Readings(
        data=pd.DataFrame(
            {
                "Time": [0, 600],
                "A1": [0.10, 0.18],
                "A2": [0.01, 0.01],
            }
        )
    ),
    entities=Entities(),
)
gfp = ATSTFile(
    file_info=file_info,
    study=study,
    readout_ids=readout_ids,
    metadata=metadata,
    assay=Assay(
        data={
            "readout_type": "fluorescence",
            "readout_unit": "RFU",
            "time_unit": "seconds",
            "plate_format": "96_well",
        }
    ),
    layout=layout,
    readings=Readings(
        data=pd.DataFrame(
            {
                "Time": [0, 600],
                "A1": [120, 240],
                "A2": [5, 6],
            }
        )
    ),
    entities=Entities(),
)

multi = MultiReadoutATST(
    file_info=file_info,
    study=study,
    readout_ids=readout_ids,
    readouts={"OD600": od600, "GFP": gfp},
    entities=Entities(),
)

write_multi_readout_atst(multi, "manual_multi_readout.atst.txt")
```

To write linked payloads, pass a directory and enable `linked_files`. Omitting
`linked_blocks` links `METADATA`, `ASSAY`, `ENTITIES`, `LAYOUT`, and `READINGS`:

```python
write_multi_readout_atst(multi, "manual_multi_readout", linked_files=True)
```

Select specific blocks for mixed inline/linked output with their case-sensitive
names:

```python
write_multi_readout_atst(
    multi,
    "manual_multi_readout",
    linked_files=True,
    linked_blocks={"METADATA", "READINGS"},
)
```

8. Read multi-readout ATST files by asking for a multi-readout object.

```python
multi = read_atst("examples/e2/example_2.atst.txt", multi_readouts=True)
print(multi.readouts.keys())

od600 = multi.readouts["OD600"]
print(od600.readings.data.head())
```

For most new files, the easiest starting point is to load a known-good template, change the study, layout, and readings data, then write a new `.atst.txt` file.

## Examples

Sample files live in [examples/](examples/):

- [Example 1](examples/e1/write_your_first_atst.ipynb): LogPhase600 input and a single-readout, all-in-one ATST file.
- [Example 2](examples/e2/write_atst.ipynb): two CLARIOstar inputs and a multi-readout file with inline and linked payloads.
- [Example 3](examples/e3/write_atst.ipynb): four Tecan SparkControl inputs and fully linked multi-readout payloads.
- [Example 4](examples/e4/write_atst.ipynb): LogPhase600 input and a larger human-readable ATST file.
- [Example 5](examples/e5/write_atst.ipynb): readings loaded from CSV and a curve-keyed ATST file.

Each folder also contains the generated ATST files and a `read_and_plot.ipynb`
notebook with separate `phage_id` and `isolate_id` plotting examples.

Device readers are part of the main package and implement the `DeviceReader`
protocol:

```python
from ATST import LogPhase600Reader

reader = LogPhase600Reader()
parsed = reader.read(raw_bytes, filename="device_output.txt")

print(parsed.metadata)
print(parsed.assay)
print(parsed.readings.head())
```

`ClariostarReader` and `TecanReader` provide the same `.read()` interface.

## Validation, precision, and missing readings

`validate_atst(atst)` checks the current contents of single- and multi-readout
objects without changing them. Readers and writers apply these checks too, so
editing a previously valid object does not bypass validation. Checks cover
required fields, supported units and format version, declared encoding and
delimiter, recognised date fields, identifiers, entity primary keys, readout
coverage, layout/readings correspondence, and numeric, unique, increasing Time.
`Time` must be the first readings column. Validation establishes structural
conformance, not experimental quality or metadata completeness.

Every annotated LAYOUT row must have a matching READINGS column. A LAYOUT row
that is completely empty apart from `well_loc` or `curve_id` may be omitted
from READINGS; if its column is present, every reading must be empty. An
explicit `NA` is a non-empty error or non-applicable marker and is rejected in
that special unannotated column.

`STUDY` and `METADATA` blocks remain required. `STUDY.title` and
`STUDY.study_id` are mandatory and must be non-empty; other study fields and all
`METADATA` fields are optional. `plate_type` is not required for non-plate
curves. A `well_loc` layout still requires `ASSAY.plate_format`.

`Readings.data` remains a numeric pandas DataFrame. Empty cells and explicit
`NA` both appear as missing numeric values for analysis, while source tokens in
DataFrame attributes retain the distinction and original numeric text for
unchanged cells. Use `atst.readings.to_text()` for an editable text table,
including exact source precision. Use `atst.readings.set_missing(time, column,
kind="NA")` for an explicit error/non-applicable value, or `kind=""` for an
empty cell. Ordinary numeric edits replace the old source value on export.
New missing numeric values without source information are written as empty.

Copying or subsetting the readings DataFrame retains its attributes in normal
pandas operations; rebuilding it from arrays or exporting it through another
format may discard that information. The numeric view uses ordinary numeric
precision; source-text preservation is not arbitrary-precision arithmetic.

Instrument importers preserve exported measurement text without rounding to
six significant digits. They may standardise well labels (`A01` to `A1`),
convert durations into the declared time units, and reorder columns. They do
not subtract blanks, normalise measurement values, or classify susceptibility.
Known acquisition date fields are normalised to ISO 8601. If a source date
cannot be interpreted, it is retained in a `<field>_source` field and the date
field is left empty for correction; filename hints do not override source data.

## Linked payload support

The Python reader supports linked `METADATA`, `ASSAY`, `LAYOUT`, `READINGS`,
and `ENTITIES.TABLE` payloads. Paths are relative to the actual ATST container
file's directory, irrespective of its recorded `FILE_INFO.file_name`.
For example:

```text
:::ENTITIES_START
<<<TABLE name=PHAGES pk=phage_id file=entities/phages.tsv
:::ENTITIES_END
```

The linked file contains only the tab-delimited table, including its header.
All entity tables in a block must be inline or all must be linked. Linked
entities have the same validation requirements as inline tables. Unlike
readout-specific links, `ENTITIES.TABLE` links use `name`, `pk`, and `file` and
must not contain `readout_id`.

By default, `write_atst` and `write_multi_readout_atst` produce standalone files
with inline payloads. With `linked_files=True`, the supplied path is created as
a directory containing the ATST container and linked TSV payloads in
`metadata/`, `assays/`, `layouts/`, `readings/`, and `entities/`. By default all
five linkable blocks are linked; `linked_blocks` selects a case-sensitive subset
and rejects unknown names. Multi-readout payload filenames contain their
`readout_id`, and entity filenames are lowercase.

`write_linked_atst_bundle` remains available when the same fully linked output
is needed as one ZIP. The Streamlit generator exposes that ZIP form as
`Linked-files ZIP` in its download format control.
For browser uploads, use a standalone ATST file: uploading a container alone
does not upload the files referenced by its relative links.

## Condition plots and summaries

`plot()` returns a matplotlib Figure; notebooks display it without importing
matplotlib. Available on a single readout and a multi-readout study:

```python
readout = study.readouts["Fig_1A"]
readout.plot(group_by="phage_id", summary="replicates")
readout.plot(group_by="phage_id", summary="median_minmax")
readout.plot(group_by="phage_id", summary="mean_sd")
stats = readout.summarize(group_by="phage_id")

study.plot(readouts=["Fig_1A"], group_by="phage_id", summary="mean_sd")
stats = study.summarize(readouts=["Fig_1A"], group_by="phage_id")
```

`replicates` draws individual curves, `median_minmax` draws median lines with
min-max whiskers, and `mean_sd` draws mean lines with ±SD shading. `filters`
selects any LAYOUT column (`filters={"phage_id": ["VAC1", "VAC3"]}`);
`facet_by` creates panels within each readout. Each selected readout has its
own panels and time grid. `time_unit="h"` converts ASSAY time units among
`s`, `min`, and `h`; omitted units retain the original scale.

Use `group_by` to specify all columns needed to distinguish conditions.
Blank condition values are retained. `labels` and `colors` map condition
values to legend labels and colours; for multiple grouping columns, use tuple
keys in column order. `title` sets the figure title. Without `group_by`, raw
curves receive individual labels and colours. ENTITIES remain available on the
object; use `labels` for desired entity display names.

Summary data requires explicit `group_by` condition columns. Each curve in a
condition contributes once, including when only one condition remains.
Replicate labels may repeat, be blank, or be absent; they do not define summary
groups. Summaries contain condition columns, `Time`, `n`,
`mean`, `sd`, `median`, `min`, and `max`; multi-readout summaries also include
`readout_id`. Statistics ignore missing readings; `n` counts available values
at each time and SD uses `ddof=1` (undefined for fewer than two values).
Summary times retain the source units. Readouts are never pooled.

`plot_full_plate()` remains available; the `.plt()` shorthand was removed.

## Development

The package uses a `src/` layout and supports Python >=3.10. Python 3.10 uses pandas 2.3; Python >=3.11 uses pandas 3 or newer. The lockfile and exported requirements include these interpreter-specific dependencies.

Useful commands:

```powershell
uv sync
uv run python -m compileall src
uv run python -m unittest discover -s tests -v
uv run streamlit run src/streamlit_app/ATST_Generator.py
```
