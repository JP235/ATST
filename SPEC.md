# Assay Time Series Tabular Format (ATST) Specification

**File extensions:** `.atst.txt`, `.atst.tsv`  
**Version:** `0.1`

ATST is a TAB-delimited data-sharing format for assay time-series readouts.

## Table of contents

- [Purpose and scope](#purpose-and-scope)
- [Normative language](#normative-language)
- [Sigils and delimiters](#sigils-and-delimiters)
- [Top-level block order](#top-level-block-order)
- [Field and table forms](#field-and-table-forms)
- [File body](#file-body)
- [Reserved names and identifiers](#reserved-names-and-identifiers)
- [Field names](#field-names)
- [Text values](#text-values)
- [Numeric values](#numeric-values)
- [Date and datetime values](#date-and-datetime-values)
- [Whitespace and TAB handling](#whitespace-and-tab-handling)
- [Linking policy](#linking-policy)
- [Validation expectations](#validation-expectations)
- [Examples](#examples)

## Purpose and scope


Assay Time Series Tabular Format (ATST) is a TAB-delimited data-sharing format for assay time-series readouts. The format is intended to support interchange of assay readouts with sufficient structure for parsing, human inspection, and basic validation.

This specification defines the syntax, required blocks, optional `READOUT_IDS` and `ENTITIES` blocks, field forms, linking behavior, and validation rules for `.atst.txt` and `.atst.tsv` files.

## Normative language


The keywords MUST, MUST NOT, SHOULD, SHOULD NOT, MAY, and OPTIONAL are normative and are to be interpreted as requirement levels for producers and consumers of ATST files.

## Sigils and delimiters


The following tokens are reserved as structural sigils and delimiter suffixes:

```text
===
:::
%%%
<<<
_START
_END
```

ATST files use the following structural delimiters:

```text
===FILE_START
:::{block_name}_START
:::{block_name}_END
%%%{sub_field_name}_START
%%%{sub_field_name}_END
<<<{linked_field_name} file={relative_file_path.tsv}
<<<{linked_field_name} readout_id={readout_id} file={relative_file_path.tsv}
===FILE_END
```

The delimiter semantics are as follows:

```text
::: delimits top-level blocks.
%%% delimits in-file multi-line fields.
<<< declares an external linked field.
```

A `%%%` field MAY contain one of the following payload forms:
- a long two-column table
- a wide table
- a readout-specific in-file payload of one of the previous two forms

A linked external field declared with `<<<` MUST refer to a file that contains only the field payload. Linked files MUST NOT contain block delimiters or field delimiters.

## Top-level block order


An ATST file MUST contain every top-level block below except `READOUT_IDS` and `ENTITIES`. `READOUT_IDS` is REQUIRED for multi-readout files and OPTIONAL for single-readout files. Blocks MUST appear in the following order:

```text
FILE_INFO
   Contains ATST file metadata.
STUDY
   Contains study-level descriptive metadata, including authorship, provenance, purpose, funding, and related study information.
READOUT_IDS (optional for single-readout files)
   Declares the readout identifiers used by a multi-readout file.
METADATA
   Contains instrument, acquisition, software, laboratory, and run-level metadata.
ASSAY
   Contains readout type, unit, time unit, optional plate format, and measurement setup information.
ENTITIES (optional)
   Contains centralized tables describing biological, chemical, or other entities used in the study.
LAYOUT
   Contains annotations keyed by well location or curve identifier.
READINGS
   Contains assay time-series readings.
```

## Field and table forms


Inline fields are represented as a single TAB-separated key-value pair:
Inline field:

```text
{field_name}<TAB>{value}
```

Long tables are represented as rows of inline fields without a header:
```text
{field_name}<TAB>{value}
{field_name}<TAB>{value}
{field_name}<TAB>{value}
...
```

Wide tables are represented as a single header row followed by one or more data rows. 
Wide tables MUST NOT include index-number columns unless such columns are explicitly part of the data model:
```text
{column_1_name}<TAB>{column_2_name}<TAB>...
{value_row_1_column_1}<TAB>{value_row_1_column_2}<TAB>...
{value_row_2_column_1}<TAB>{value_row_2_column_2}<TAB>...
{value_row_3_column_1}<TAB>{value_row_3_column_2}<TAB>...
...
```

## File body

```text
===FILE_START
```

### FILE_INFO

```text
:::FILE_INFO_START
```

Long table
The FILE_INFO block is REQUIRED. It MUST be encoded as a long table and MUST contain the following fields:

```text
file_name       	{name}.atst.tsv
format          	ATST
format_version  	0.1
created_on      	{created_on_date}
field_delimiter 	TAB
encoding        	UTF-8
```

The field_delimiter value MUST be TAB.
The encoding value MUST be UTF-8.
The format value MUST be ATST. This specification and implementation support
format_version 0.1; an unsupported version MUST be reported explicitly.
```text
:::FILE_INFO_END
```
### STUDY

```text
:::STUDY_START
```
Long table

The STUDY block is REQUIRED. It MUST be encoded as a long table and MUST contain the following non-empty fields:

```text
title         	{title}
study_id      	{study_id}
```

The `title` MUST be a human-readable study title. The `study_id` MUST be a stable identifier for the study. Additional provenance, authorship, funding, purpose, or contextual fields SHOULD be included when they are needed to interpret the assay.

```text
:::STUDY_END
```

### READOUT_IDS

```text
:::READOUT_IDS_START
readout_id
OD600
GFP
:::READOUT_IDS_END
```

The `READOUT_IDS` block is REQUIRED for multi-readout files and OPTIONAL for
single-readout files. It MUST be encoded as a wide table containing exactly one
column named `readout_id`. Each value MUST be unique.

Every `readout_id` used by a readout-specific inline field or external link MUST
appear in `READOUT_IDS`. METADATA, ASSAY, and LAYOUT payloads MAY be shared across all declared
readouts or supplied separately for every declared readout. READINGS MUST
contain a separate READOUT payload for every readout in a multi-readout file.

`READOUT_IDS` identifies readouts only. External file paths MUST be declared in
the corresponding `METADATA`, `ASSAY`, `LAYOUT`, or `READINGS` block and MUST
NOT be repeated in `READOUT_IDS`.

When `READOUT_IDS` is omitted, payloads MUST NOT use `readout_id`. A
single-readout payload MAY be stored inline or represented by one external link
without a `readout_id` attribute.

### METADATA

```text
:::METADATA_START
```

Long table(s)
The METADATA block is REQUIRED and MAY be empty. The example fields below are recommended descriptive fields, not mandatory fields; in particular, plate_type is not required for curve-keyed data. It contains file-level, study-run, acquisition, instrument, software, operator, and laboratory metadata. It MAY contain a file-level long table, readout-specific in-file metadata payloads, linked metadata payloads, or a combination permitted by this specification's linking policy rules.

example 1:
```text
instrument   	SuperDuperReader
plate_type   	Corning 96 well for SuperDuperReader
date_start   	2026-01-01
operator     	OP1
```

example 2:
```text
<<<METADATA_READOUT file=meta.tsv
```

example 3:
```text
<<<METADATA_READOUT readout_id=OD600_1 file=meta_00001.tsv
<<<METADATA_READOUT readout_id=OD600_2 file=meta_00002.tsv
<<<METADATA_READOUT readout_id=OD600_3 file=meta_00003.tsv
<<<METADATA_READOUT readout_id=OD600_4 file=meta_00004.tsv
```

```text
:::METADATA_END
```

### ASSAY

```text
:::ASSAY_START
```
Long table(s)

The ASSAY block is REQUIRED. It describes the measurement performed for a readout. Its inline or externally linked payload MUST contain the following fields for each applicable readout:

```text
readout_type   	string
readout_unit   	string
time_unit      	time_unit
```

Additional fields MAY be included to describe device configuration, environmental conditions, or measurement setup.

The `plate_format` field is REQUIRED when the corresponding LAYOUT payload is
keyed by `well_loc`. It is OPTIONAL when the corresponding LAYOUT payload is
keyed by `curve_id`.

The time_unit field MUST be one of:
- s, seconds 
- min, minutes
- h, hours

For multiple readouts, readout-specific assay metadata MUST be represented either as linked files or as ASSAY_READOUT fields with readout_id values. The representation MUST follow the linking policy rules in this specification.

example 1:
```text
readout_type      	absorbance
readout_unit      	od600
time_unit         	s
plate_format      	96_well
temperature       	37C
shaking           	ON
shaking_frequency 	100rpm
```

example 2:
```text
%%%ASSAY_READOUT_START readout_id=GFP
readout_type         	GFP
readout_unit         	RFU
time_unit            	s
plate_format         	96_well
temperature_gradient 	ON
%%%ASSAY_READOUT_END

%%%ASSAY_READOUT_START readout_id=OD600
readout_type         	absorbance
readout_unit         	od600
time_unit            	s
plate_format         	96_well
temperature_gradient 	ON
%%%ASSAY_READOUT_END
```

example 3:
```text
<<<ASSAY_READOUT readout_id=OD600_1 file=assay_00001.tsv
<<<ASSAY_READOUT readout_id=OD600_2 file=assay_00002.tsv
<<<ASSAY_READOUT readout_id=OD600_3 file=assay_00003.tsv
<<<ASSAY_READOUT readout_id=OD600_4 file=assay_00004.tsv
```

```text
:::ASSAY_END
```

### ENTITIES

```text
:::ENTITIES_START
```
Wide table(s)

The ENTITIES block is OPTIONAL. When present, it SHOULD be used as the centralized location for describing entities referenced by the study, such as isolates, phages, small molecules, strains, media, reagents, or other experimental entities.

Each entity table MUST be declared as a TABLE field. Each TABLE declaration MUST include name and pk attributes. Primary key values MUST be non-empty. Each entity table MUST contain the declared primary key column, and primary key values MUST be unique within that table.

The table declaration forms are:
```text
%%%TABLE_START name={table_name} pk={pk_column}
<<<TABLE name={table_name} pk={pk_column} file=study_1_entities.tsv
```

example:
```text
%%%TABLE_START name=PHAGES pk=PHAGE_ID
PHAGE_ID 	source         	family         	genome
ph_1     	sputum_isolate 	Myoviridae     	phage_genes/ph_1.fasta
ph_2     	engineered     	Bruynoghevirus 	phage_genes/ph_2.fasta
%%%TABLE_END

%%%TABLE_START name=ISOLATES pk=ISOLATE_ID
ISOLATE_ID
ISO_1
ISO_2
%%%TABLE_END

%%%TABLE_START name=SMALL_MOLECULE pk=SMALL_MOLECULE_ID
SMALL_MOLECULE_ID 	pubchem_id
SM_MOL_1          	0001
%%%TABLE_END
```

```text
:::ENTITIES_END
```

### LAYOUT

```text
:::LAYOUT_START
```
Wide table

The LAYOUT block is REQUIRED. Its payload MUST be encoded as a wide table when stored inline, or represented by permitted external link declarations when sourced externally.

Each LAYOUT payload MUST contain exactly one layout key column:

```text
well_loc
curve_id
```

`well_loc` MUST be used for plate-based layouts. `curve_id` MAY be used when
the time-series curves are not identified by well location, or when providing
the complete original well layout is not practical or convenient. A LAYOUT
payload MUST NOT contain both `well_loc` and `curve_id`.

Layout key values MUST be non-empty and unique within the payload. A `curve_id`
identifies one curve within its corresponding readout. The same `curve_id` MAY
appear in different readouts, where the combination of `readout_id` and
`curve_id` identifies the curve unambiguously.

All non-key LAYOUT values are interpreted as strings. Curve-specific
experimental annotations, such as sample, treatment, concentration, or source
file, SHOULD be stored as additional LAYOUT columns.

An empty annotation cell means the column does not apply to that row. A LAYOUT
row with at least one non-key annotation value MUST have a corresponding column
in READINGS. A row MAY be empty except for its layout key when no data was
collected for that well or curve. For such a completely unannotated row, the
corresponding READINGS column MAY be omitted; if it is present, every value in
that column MUST be empty. `NA` is not an empty value and therefore MUST NOT be
used in a READINGS column for a completely unannotated LAYOUT row.

example 1:
```text
well_loc	type        	isolate 	phage 	MOI 	sm       	conc_uM 	replicate
A1      	Treatment_1 	ISO_1   	ph_1  	0.1 	         	        	1
A2      	Treatment_2 	ISO_1   	ph_1  	0.1 	SM_MOL_1 	5.0     	1
A3      	Isolate_ctrl	ISO_1   	      	    	         	        	1
A4      	            	        	      	    	         	        	
A5      	Treatment_1 	ISO_2   	ph_1  	0.1 	         	        	1
A6      	Treatment_2 	ISO_2   	ph_1  	0.1 	SM_MOL_1 	5.0     	1
A7      	Isolate_ctrl	ISO_2   	      	    	         	        	1
A8      	            	        	      	    	         	        	
A9      	Blank       	        	      	    	        	        	1
...
```

example 2:
isolate column is repeated for each applicable well

```text
well_loc	type         	isolate      	phage_1 	MOI_1 	phage_2 	MOI_2
A1      	Treatment    	test_isolate 	ph_1    	0.1   	ph_2    	0.1
A2      	Treatment    	test_isolate 	ph_1    	0.1   	ph_2    	0.01
A3      	Isolate_ctrl 	test_isolate 	        	      	        	
A4      	Treatment    	test_isolate 	ph_1    	0.01  	ph_2    	0.1
A5      	Treatment    	test_isolate 	ph_1    	0.01  	ph_2    	0.01
A6      	Isolate_ctrl 	test_isolate 	        	      	        	
A7      	Blank        	             	        	      	        	
...
```

example 3:
```text
<<<LAYOUT_READOUT readout_id=OD600_1 file=layout_00001.tsv
<<<LAYOUT_READOUT readout_id=OD600_2 file=layout_00002.tsv
<<<LAYOUT_READOUT readout_id=OD600_3 file=layout_00003.tsv
<<<LAYOUT_READOUT readout_id=OD600_4 file=layout_00004.tsv
```

example 4:
```text
curve_id    	type      	sample_id 	condition
growth_01   	Treatment 	S001      	drug
growth_ctrl 	Control   	S002      	vehicle
```

When curves were acquired on different days or require different METADATA or
ASSAY values, they MUST be represented in separate readouts. Each readout then
has its own METADATA, ASSAY, LAYOUT, and READINGS payload. Curves acquired
together with common metadata and assay settings MAY share a readout and appear
as separate READINGS columns.


```text
:::LAYOUT_END
```

### READINGS

```text
:::READINGS_START
```
tab separated wide table

The READINGS block is REQUIRED. Its payload MUST be encoded as a TAB-separated wide table when stored inline, or represented by permitted external link declarations when sourced externally.

The first cell of the first line MUST be "Time". Every READINGS column other
than `Time` MUST correspond exactly to a value in the applicable LAYOUT key
column, either `well_loc` or `curve_id`. Every applicable LAYOUT key value MUST
have a corresponding READINGS column.

Time column values MUST be numeric and MUST use the time_unit defined by the corresponding ASSAY block or ASSAY_READOUT for the same readout_id. Time values MUST be unique and strictly increasing within each READOUT.

Empty columns, such as example 1 column A4, represent wells for which no data was collected. Detection errors, instrument errors, or non-applicable values SHOULD be represented as NA, such as example 1 column A1.

In a curve-keyed payload, the columns after `Time` are curve identifiers rather
than well locations:

```text
Time 	growth_01 	growth_ctrl
0    	0.10      	0.09
600  	0.18      	0.11
```

Single-readout studies do not require a table delimiter or readout_id in READINGS. Multi-readout studies MUST represent each readout as a READOUT payload with a readout_id.

example 1:
```text
Time 	A1     	A2     	A3     	A4 	A5     	...
0    	NA     	0.3241 	0.2912 	   	0.2512 	...
600  	0.3211 	0.3352 	0.2989 	   	0.2552 	...
...
```

example 2:
```text
%%%READOUT_START readout_id=GFP
Time 	A1   	A2   	...
0    	0.11 	0.22 	...
...
%%%READOUT_END
%%%READOUT_START readout_id=OD600
Time 	A1   	A2   	...
0    	0.31 	0.34 	...
...
%%%READOUT_END
```

example 3:
```text
<<<READOUT readout_id=OD600_1 file=readings_00001.tsv
<<<READOUT readout_id=OD600_2 file=readings_00002.tsv
<<<READOUT readout_id=OD600_3 file=readings_00003.tsv
<<<READOUT readout_id=OD600_4 file=readings_00004.tsv
```

```text
:::READINGS_END

===FILE_END
```

## Reserved names and identifiers


Reserved names MAY be used only where explicitly defined by the ATST specification. User-defined identifiers, entity IDs, table names, column names, and readout IDs MUST NOT equal reserved names under case-insensitive comparison.

Reserved names:
```text
   readout_id
   Time
   type
   well_loc
   curve_id
   NA
   FILE_INFO
   STUDY
   READOUT_IDS
   METADATA
   METADATA_READOUT
   ASSAY
   ASSAY_READOUT
   ENTITIES
   LAYOUT
   LAYOUT_READOUT
   READINGS
   READOUT
```

## Field names


Field names MUST NOT contain reserved sigils, tabs, or newlines. snake_case SHOULD be used for all field names except fields in ENTITIES.TABLE payloads.

## Text values


Text values MUST NOT contain reserved sigils. Placeholder tokens for empty values MUST NOT be used. Empty values are allowed. Error values and non-applicable values SHOULD be represented as NA.

## Numeric values


Numeric values MUST use a period (.) as the decimal point. Scientific notation is allowed. Thousands separators are not allowed.

## Date and datetime values


All dates and datetimes MUST follow ISO 8601 format. Supported forms include:
```text
   YYYY-MM-DD
   YYYY-MM-DDThh:mm:ss
   YYYY-MM-DDThh:mm:ssZ
   YYYY-MM-DDThh:mm:ss+hh:mm
   YYYY-MM-DDThh:mm:ss-hh:mm
```

Date-times MAY include fractional seconds. A missing timezone means the source
did not supply a timezone; consumers MUST NOT assume UTC. The Python validator
checks the recognised fields created_on, date, date_start, date_end, and
date_export when populated. Producers remain responsible for date semantics in
user-defined fields; empty optional date fields are permitted.

## Whitespace and TAB handling


A single TAB separates fields and table row cells. Additional TAB characters MUST NOT be used for visual alignment. Leading and trailing spaces around keys and values are ignored. Spaces MAY be used for visual alignment only after field content, not as field delimiters.

```text
%%%LONGTABLE_START
longfield_name	value_1
field_name	value_2
longer_field_name	value_3
%%%LONGTABLE_END
```

and 

```text
%%%LONGTABLE_START
   long_field_name   	value_1
   field_name        	value_2
   longer_field_name 	value_3
%%%LONGTABLE_END
```

will be parsed the same.

## Linking policy


For multi-ASSAY, multi-LAYOUT, and multi-READINGS studies, all readout-specific payloads MAY be included in a single file. However, linked files are RECOMMENDED for per-readout values when this improves clarity or file size.

External linking is supported for the following fields:
```text
   READINGS.READOUT
   LAYOUT.LAYOUT_READOUT
   ASSAY.ASSAY_READOUT
   METADATA.METADATA_READOUT
   ENTITIES.TABLE
```

Within a block, the same linking policy MUST be followed for all fields of the same kind. Producers MUST NOT mix linked external payloads and encapsulated in-file payloads for the same field kind within the same block. A different block MAY use a different representation.

this is allowed:

```text
:::ASSAY_START
%%%ASSAY_READOUT_START readout_id=1
...
%%%ASSAY_READOUT_END
%%%ASSAY_READOUT_START readout_id=2
...
%%%ASSAY_READOUT_END
:::ASSAY_END

:::READINGS_START
<<<READOUT readout_id=1 file=...
<<<READOUT readout_id=2 file=...
:::READINGS_END
```

this is not allowed:

```text
:::ASSAY_START
<<<ASSAY_READOUT readout_id=1 file=...
%%%ASSAY_READOUT_START readout_id=2
...
%%%ASSAY_READOUT_END
:::ASSAY_END

:::READINGS_START
<<<READOUT readout_id=1 file=...
%%%READOUT_START readout_id=2
....
%%%READOUT_END
:::READINGS_END
```

Linked file paths MUST be relative to the directory containing the actual ATST container file. FILE_INFO.file_name is descriptive metadata and MUST NOT change link resolution. Absolute linked paths are not permitted.

Linked fields MUST include a readout_id value unless this specification
explicitly permits otherwise. `ENTITIES.TABLE` links are the exception: they
MUST include `name`, `pk`, and `file`, and MUST NOT include `readout_id`.

Linked files MUST contain only the payload for the linked field and MUST follow the format of that field without block markers or field delimiters.

accepted <<< READOUT payload example:
```text
Time  	A1   	A2
0     	0.11 	0.22
600   	0.33 	0.44
```


wrong <<< READOUT payload example:
```text
%%%READOUT_START readout_id=id1
Time 	A1   	A2
0    	0.11 	0.22
600  	0.33 	0.44
%%%READOUT_END
```

## Validation expectations

Consumers SHOULD report validation or parse errors for at least the following cases:

- The file does not start with `===FILE_START` or end with `===FILE_END`.
- A top-level block appears out of the required order.
- A required block or required block field is missing.
- The ATST container path or `FILE_INFO.file_name` does not end with `.atst.txt` or `.atst.tsv`.
- `READOUT_IDS` contains columns other than `readout_id` or contains duplicate values.
- A `readout_id` appears in a readout-specific field or linked field but is absent from `READOUT_IDS`.
- A block mixes linked external payloads and encapsulated in-file payloads for the same field kind.
- A linked payload contains ATST block delimiters or field delimiters.
- A LAYOUT payload contains neither or both of `well_loc` and `curve_id`.
- A LAYOUT key value is empty or duplicated.
- An annotated LAYOUT key value is missing from READINGS, or a non-`Time`
  READINGS column has no corresponding LAYOUT key value.
- A completely unannotated LAYOUT row has a corresponding READINGS column that
  contains any non-empty value, including `NA`.
- A `READINGS.Time` value is non-numeric, duplicated, or not strictly increasing within a readout.

## Implementation notes

The Python reader accepts all listed linked payload kinds, including entity
tables. Writers emit standalone inline files and validate the current object
before export. The numeric readings view retains source tokens for unchanged
values so that empty cells, NA, and original measurement precision survive a
read/write cycle; numeric analysis itself uses ordinary pandas precision.

## Examples

See [examples](examples/) for sample ATST files and linked readings layouts.
