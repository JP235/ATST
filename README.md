# Assay Time Series Tabular Format (ATST)

**File extension:** `.atst.txt`  
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

## Purpose and scope


Assay Time Series Tabular Format (ATST) is a TAB-delimited data-sharing format for assay time-series readouts. The format is intended to support interchange of assay readouts with sufficient structure for parsing, human inspection, and basic validation.

This specification defines the syntax, required blocks, optional blocks, field forms, linking behavior, and validation rules for .atst.txt files.

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
=== FILE_START
::: {block_name}_START
::: {block_name}_END
%%% {sub_field_name}_START
%%% {sub_field_name}_END
<<< {linked_field_name} readout_id={readout_id} file={relative_file_path.tsv}
=== FILE_END
```

The delimiter semantics are as follows:

```text
::: delimits top-level blocks.
%%% delimits in-file multi-line fields.
<<< declares an external linked field.
```

A %%% field MAY contain one of the following payload forms:
- a long two-column table
- a wide table
- a readout-specific in-file payload of one the previous two forms

A linked external field declared with <<< MUST refer to a file that contains only the field payload. Linked files MUST NOT contain block delimiters or field delimiters.

## Top-level block order


When present, top-level blocks MUST appear in the following order:

```text
FILE_INFO
   Contains ATST file metadata.
STUDY
   Contains study-level descriptive metadata, including authorship, provenance, purpose, funding, and related study information.
READOUT_MANIFEST (optional)
   Declares readout identifiers and, when applicable, file links for:
      - metadata_file,
      - assay_file,
      - layout_file, and 
      - data_file 
   for each readout_id in the study.
METADATA
   Contains instrument, acquisition, software, laboratory, and run-level metadata.
ASSAY
   Contains readout type, unit, time unit, plate format, and measurement setup information.
ENTITIES (optional)
   Contains centralized tables describing biological, chemical, or other entities used in the study.
LAYOUT_SCHEMA (optional)
   Contains validation rules for the LAYOUT block, including data types, constants, entity references, and type-specific column constraints.
LAYOUT
   Contains plate layout annotations keyed by well location.
DATA
   Contains assay time-series readout data.
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

```text
:::FILE_INFO_START
```

Long table
The FILE_INFO block is REQUIRED. It MUST be encoded as a long table and MUST contain the following fields:

```text
file_name       	{name}.atst.txt
format          	ATST
format_version  	0.1
created_on      	{created_on_date}
field_delimiter 	TAB
encoding        	UTF-8
```

The field_delimiter value MUST be TAB.
The encoding value MUST be UTF-8.
```text
:::FILE_INFO_END
```

```text
::: STUDY_START
```
Long table

The STUDY block is REQUIRED. It MUST be encoded as a long table. It SHOULD include a study title, a stable study_id, and any additional provenance, authorship, funding, purpose, or contextual fields needed to interpret the assay.

```text
title         	{title}
study_id      	{study_id}
...
```

```text
::: STUDY_END
```

```text
::: READOUT_MANIFEST_START
```
Wide table

The READOUT_MANIFEST block is OPTIONAL only for single-readout files that do not use readout_id anywhere in the file.

The READOUT_MANIFEST block, when present, MUST be encoded as a wide table. The readout_id column is REQUIRED. The metadata_file, assay_file, layout_file, and data_file columns are OPTIONAL.

Every readout_id used anywhere in the ATST file MUST appear in READOUT_MANIFEST. If READOUT_MANIFEST is omitted, all required content MUST be declared in-file and external linking MUST NOT be used.

Optional manifest file columns provide links to readout-specific block payloads:
```text
  data_file > DATA.READOUT
  layout_file > LAYOUT.LAYOUT_READOUT
  assay_file > ASSAY.ASSAY_READOUT
  metadata_file > METADATA.METADATA_READOUT
```

If an optional manifest file column is present and a readout does not use external linking for that column, the value MUST be NA.

For each manifest file column, linking policy MUST be consistent across all readouts. If any readout has a non-NA value in data_file, then every readout MUST have a non-NA value in data_file, and the DATA block MAY be omitted. If every value in data_file is NA, or if the data_file column is absent, DATA MUST be provided in-file. The same rule applies independently to metadata_file, assay_file, layout_file, and data_file.

If a file path for a readout is specified both in READOUT_MANIFEST and in the corresponding block-level external link, the paths MUST be identical.

example 1.1:
READOUT_MANIFEST not declared.
METADATA, ASSAY, LAYOUT, and DATA blocks MUST be defined in the file.
No linking blocks allowed.

example 1.2:
METADATA, ASSAY, LAYOUT, and DATA blocks MUST be defined in the file.
Linking blocks are allowed with readout_id=OD600

```text
readout_id
OD600
```

example 1.3:
METADATA, ASSAY, LAYOUT, and DATA blocks MUST be defined in the file.
Linking blocks are allowed with readout_id=OD600

```text
readout_id 	metadata_file 	assay_file 	layout_file 	data_file
OD600      	NA            	NA         	NA          	NA
```

example 2:
METADATA and DATA blocks MAY (and SHOULD) be omitted.
ASSAY and LAYOUT MUST be defined in the file.

```text
readout_id 	metadata_file 	assay_file 	layout_file 	data_file
GFP        	meta.tsv      	NA         	NA          	gfp_00001.tsv
OD600      	meta.tsv      	NA         	NA          	od600_00001.tsv
```

example 2.1:
NOT allowed
MUST NOT mix linking policy within a block

```text
           	              	wrong      	            	wrong
readout_id 	metadata_file 	assay_file 	layout_file 	data_file
GFP        	NA            	assay.tsv  	NA          	gfp_00001.tsv
OD600      	NA           	NA         	NA          	NA
```


example 3:
METADATA, ASSAY, LAYOUT, and DATA blocks MAY (and SHOULD) be omitted.
File could end after closing READOUT_MANIFEST

```text
readout_id 	metadata_file  	assay_file      	layout_file      	data_file
OD600_1    	meta_00001.tsv 	assay_00001.tsv 	layout_00001.tsv 	data_00001.tsv
OD600_2    	meta_00002.tsv 	assay_00002.tsv 	layout_00002.tsv 	data_00002.tsv
OD600_3    	meta_00003.tsv 	assay_00003.tsv 	layout_00003.tsv 	data_00003.tsv
OD600_4    	meta_00004.tsv 	assay_00004.tsv 	layout_00004.tsv 	data_00004.tsv
```

```text
::: READOUT_MANIFEST_END

```


```text
::: METADATA_START
```

Long table(s)
The METADATA block contains file-level, study-run, acquisition, instrument, software, operator, and laboratory metadata. It MAY contain a file-level long table, readout-specific in-file metadata payloads, linked metadata payloads, or a combination permitted by this specification's linking policy rules.

example 1:
```text
instrument   	SuperDuperReader
plate_type   	Corning 96 well for SuperDuperReader
date_start   	2026-01-01
operator     	OP1
```

example 2:
```text
<<< METADATA_READOUT file=meta.tsv readout_id=GFP
<<< METADATA_READOUT file=meta.tsv readout_id=OD600
```

example 3:
```text
<<< METADATA_READOUT readout_id=OD600_1 file=meta_00001.tsv
<<< METADATA_READOUT readout_id=OD600_2 file=meta_00002.tsv
<<< METADATA_READOUT readout_id=OD600_3 file=meta_00003.tsv
<<< METADATA_READOUT readout_id=OD600_4 file=meta_00004.tsv
```

```text
::: METADATA_END
```

```text
::: ASSAY_START
```
Long table(s)

The ASSAY block describes the measurement performed for a readout. It MUST contain the following fields for each applicable readout:

```text
readout_type   	string
readout_unit   	string
time_unit      	time_unit
plate_format   	string
```

Additional fields MAY be included to describe device configuration, environmental conditions, or measurement setup.

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
temperature       	37°C
shaking           	ON
shaking_frequency 	100rpm
```

example 2:
```text
%%% ASSAY_READOUT_START readout_id=GFP
readout_type         	GFP
readout_unit         	RFU
time_unit            	s
plate_format         	96_well
temperature_gradient 	ON
%%% ASSAY_READOUT_END

%%% ASSAY_READOUT_START readout_id=OD600
readout_type         	absorbance
readout_unit         	od600
time_unit            	s
plate_format         	96_well
temperature_gradient 	ON
%%% ASSAY_READOUT_END
```

example 3:
```text
<<< ASSAY_READOUT readout_id=OD600_1 file=assay_00001.tsv
<<< ASSAY_READOUT readout_id=OD600_2 file=assay_00002.tsv
<<< ASSAY_READOUT readout_id=OD600_3 file=assay_00003.tsv
<<< ASSAY_READOUT readout_id=OD600_4 file=assay_00004.tsv
```

```text
::: ASSAY_END
```

```text
::: ENTITIES_START
```
Wide table(s)

The ENTITIES block is OPTIONAL. When present, it SHOULD be used as the centralized location for describing entities referenced by the study, such as isolates, phages, small molecules, strains, media, reagents, or other experimental entities.

Each entity table MUST be declared as a TABLE field. Each TABLE declaration MUST include name and pk attributes. Each entity table MUST contain the declared primary key column, and primary key values MUST be unique within that table.

The table declaration forms are:
```text
%%% TABLE_START name={table_name} pk={pk_column}
<<< TABLE name={table_name} pk={pk_column} file=study_1_entities.tsv
```

example:
```text
%%% TABLE_START name=PHAGES pk=PHAGE_ID
PHAGE_ID 	source         	family         	genome
ph_1     	sputum_isolate 	Myoviridae     	phage_genes/ph_1.fasta
ph_2     	engineered     	Bruynoghevirus 	phage_genes/ph_2.fasta
%%% TABLE_END

%%% TABLE_START name=ISOLATES pk=ISOLATE_ID
ISOLATE_ID
ISO_1
ISO_2
%%% TABLE_END

%%% TABLE_START name=SMALL_MOLECULE pk=SMALL_MOLECULE_ID
SMALL_MOLECULE_ID 	pubchem_id
SM_MOL_1          	0001
%%% TABLE_END
```

```text
::: ENTITIES_END
```

```text
::: LAYOUT_SCHEMA_START
```
(optional, used to validate LAYOUT data types and references at read-time)

The LAYOUT_SCHEMA block is OPTIONAL. When present, it defines data types, constants, entity references, and row-type constraints for the LAYOUT block.

The following layout value data types are recognized:
```text
- string
- integer
- float
- numeric
- boolean
- CATEGORICAL({comma separated values})
- CONSTANT("value")
- ENTITY_REF({table_name}.{pk_column})
```

```text
%%% TYPE_DEFINITIONS_START
```
Long table

TYPE_DEFINITIONS is a REQUIRED field when LAYOUT_SCHEMA is present. It MUST be encoded as a long table.

The first two rows MUST define well_loc and type. well_loc MUST be defined as string. type MUST be defined as CATEGORICAL(...).

Rows after well_loc and type define study-specific layout columns. These field names MAY be chosen by the producer, but each declared field name MUST correspond to a column in LAYOUT unless the field is declared as CONSTANT and omitted as permitted below.

If a column is declared as CONSTANT in LAYOUT_SCHEMA, that column MAY be omitted from LAYOUT. A value within CONSTANT(...) MUST be double-quoted if it contains characters other than alphanumerics, underscores, dots, or hyphens, and SHOULD always be double-quoted. Values inside quotes follow the general text-value rules. If a CONSTANT column is present in LAYOUT, every non-empty row MUST contain the declared constant value.

ENTITY_REF validates values against the primary key column of an ENTITIES.TABLE. ENTITY_REF({table_name}) without a primary-key reference defaults to the primary key declared in %%% TABLE_START name={table_name} pk={...}. ENTITY_REF({table_name}.{pk_column}) is the explicit form. Both forms are valid. References to non-primary-key columns are not supported.

example 1:
```text
well_loc 	string
type     	CATEGORICAL(Treatment_1, Treatment_2, Isolate_ctrl, Blank)
isolate  	ENTITY_REF(ISOLATES.ISOLATE_ID)
phage    	ENTITY_REF(PHAGES.PHAGE_ID)
MOI      	float
sm       	ENTITY_REF(SMALL_MOLECULE.SMALL_MOLECULE_ID)
conc_uM  	float
replicate	integer
comments 	string
```

example 2:
```text
well_loc 	string
type     	CATEGORICAL(Treatment, Isolate_ctrl, Blank)
isolate  	CONSTANT("test_isolate")
phage_1  	ENTITY_REF(PHAGES.PHAGE_ID)
phage_2  	ENTITY_REF(PHAGES.PHAGE_ID)
MOI_1    	float
MOI_2    	float
```


example 3:
```text
well_loc 	string
type     	CATEGORICAL(treated, control, Blank)
phage    	ENTITY_REF(PHAGES.PHAGE_ID)
MOI      	float
```

```text
%%% TYPE_DEFINITIONS_END
```

```text
%%% TYPE_CONSTRAINTS_START
```
(optional)
Wide table

TYPE_CONSTRAINTS is OPTIONAL. When present, it MUST be encoded as a wide table with the following mandatory columns: type, REQUIRED_COLUMNS, and OPTIONAL_COLUMNS.

Values in the type column MUST match values declared in the CATEGORICAL(...) definition of the type row in TYPE_DEFINITIONS.

For each row, REQUIRED_COLUMNS and OPTIONAL_COLUMNS values are comma-separated lists of TYPE_DEFINITIONS field names. Whitespace around list items is ignored.

For a LAYOUT row with a type present in TYPE_CONSTRAINTS:
```text
   columns listed in REQUIRED_COLUMNS MUST contain a value
   columns listed in OPTIONAL_COLUMNS MAY contain a value
   columns not listed in REQUIRED_COLUMNS or OPTIONAL_COLUMNS MUST be empty
```

If a type is not present in TYPE_CONSTRAINTS, all columns are optional for rows of that type.

example 1:
```text
type        	REQUIRED_COLUMNS                            	OPTIONAL_COLUMNS
Treatment_1 	isolate, phage, MOI, replicate              	comments
Treatment_2 	isolate, phage, MOI, sm, conc_uM, replicate 	comments
Isolate_ctrl	isolate, replicate                          	comments
Blank       	replicate                                   	comments
```

example 2:
```text
type         	REQUIRED_COLUMNS 	OPTIONAL_COLUMNS
Treatment    	isolate          	phage_1, phage_2, MOI_1, MOI_2
Isolate_ctrl 	isolate          	
Blank        	                 	
```

example 3:
Empty TYPE_CONSTRAINTS table, same as not defining it
No LAYOUT required/optional column validation

```text
type 	REQUIRED_COLUMNS 	OPTIONAL_COLUMNS
			
```
```text
%%% TYPE_CONSTRAINTS_END
```
```text
::: LAYOUT_SCHEMA_END
```

```text
::: LAYOUT_START
```
Wide table

The LAYOUT block is REQUIRED unless all required layout payloads are supplied through permitted external links. It MUST be encoded as a wide table when provided in-file.

The well_loc column is REQUIRED.

If LAYOUT_SCHEMA is present, all columns listed in TYPE_DEFINITIONS are validated according to the schema, and columns not listed in TYPE_DEFINITIONS MUST NOT appear in LAYOUT. If LAYOUT_SCHEMA is absent, all non-well_loc values are interpreted as strings.

An empty cell means the column does not apply to that row's well_loc and type. Every well_loc value MUST have a corresponding column in DATA, even if all values in the corresponding DATA column are empty. A row MAY be empty except for well_loc when no data was collected for that well, but the corresponding DATA column MUST still be present and MUST contain only empty values.

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
isolate column is CONSTANT and could be omitted from the layout

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
<<< LAYOUT_READOUT readout_id=OD600_1 file=layout_00001.tsv
<<< LAYOUT_READOUT readout_id=OD600_2 file=layout_00002.tsv
<<< LAYOUT_READOUT readout_id=OD600_3 file=layout_00003.tsv
<<< LAYOUT_READOUT readout_id=OD600_4 file=layout_00004.tsv
```


```text
::: LAYOUT_END
```

```text
::: DATA_START
```
tab separated wide table

The DATA block is REQUIRED unless all required readout payloads are supplied through permitted external links. DATA MUST be encoded as a TAB-separated wide table when provided in-file.

The first cell of the first line MUST be "Time". Every DATA column other than Time MUST correspond to a well_loc value in LAYOUT.

Time column values MUST be numeric and MUST use the time_unit defined by the corresponding ASSAY block or ASSAY_READOUT for the same readout_id. Time values MUST be unique and strictly increasing within each READOUT.

Empty columns, such as example 1 column A4, represent wells for which no data was collected. Detection errors, instrument errors, or non-applicable values SHOULD be represented as NA, such as example 1 column A1.

Single-readout studies do not require a table delimiter or readout_id in DATA. Multi-readout studies MUST represent each readout as a READOUT payload with a readout_id.

example 1:
```text
Time 	A1     	A2     	A3     	A4 	A5     	...
0    	NA     	0.3241 	0.2912 	   	0.2512 	...
600  	0.3211 	0.3352 	0.2989 	   	0.2552 	...
...
```

example 2:
```text
%%% READOUT_START readout_id=GFP
Time 	A1   	A2   	...
0    	0.11 	0.22 	...
...
%%% READOUT_END
%%% READOUT_START readout_id=OD600
Time 	A1   	A2   	...
0    	0.31 	0.34 	...
...
%%% READOUT_END
```

example 3:
```text
<<< READOUT readout_id=OD600_1 file=data_00001.tsv
<<< READOUT readout_id=OD600_2 file=data_00002.tsv
<<< READOUT readout_id=OD600_3 file=data_00003.tsv
<<< READOUT readout_id=OD600_4 file=data_00004.tsv
```

```text
::: DATA_END

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
   NA
   FILE_INFO
   STUDY
   READOUT_MANIFEST
   METADATA
   METADATA_READOUT
   ASSAY
   ASSAY_READOUT
   ENTITIES
   LAYOUT_SCHEMA
   TYPE_DEFINITIONS
   TYPE_CONSTRAINTS
   LAYOUT
   LAYOUT_READOUT
   DATA
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
   YYYY-MM-DDThh:mm:ssZ
   YYYY-MM-DDThh:mm:ss+hh:mm
   YYYY-MM-DDThh:mm:ss-hh:mm
```

## Whitespace and TAB handling


A single TAB separates fields and table row cells. Additional TAB characters MUST NOT be used for visual alignment. Leading and trailing spaces around keys and values are ignored. Spaces MAY be used for visual alignment only after field content, not as field delimiters.

```text
%%% LONGTABLE_START
longfield_name	value_1
field_name	value_2
longer_field_name	value_3
%%% LONGTABLE_END
```

and 

```text
%%% LONGTABLE_START
   long_field_name   	value_1
   field_name        	value_2
   longer_field_name 	value_3
%%% LONGTABLE_END
```

will be parsed the same.

## Linking policy


For multi-ASSAY, multi-LAYOUT, and multi-DATA studies, all readout-specific payloads MAY be included in a single file. However, linked files are RECOMMENDED for per-readout values when this improves clarity or file size.

External linking is supported for the following fields:
```text
   DATA.READOUT
   LAYOUT.LAYOUT_READOUT
   ASSAY.ASSAY_READOUT
   METADATA.METADATA_READOUT
   ENTITIES.TABLE
```

Within a block, the same linking policy MUST be followed for all fields of the same kind. Producers MUST NOT mix linked external payloads and encapsulated in-file payloads for the same field kind within the same block. A different block MAY use a different representation.

this is allowed:

```text
:::ASSAY_START
%%% ASSAY_READOUT_START readout_id=1
...
%%% ASSAY_READOUT_END
%%% ASSAY_READOUT_START readout_id=2
...
%%% ASSAY_READOUT_END
:::ASSAY_END

:::DATA_START
<<<READOUT readout_id=1 file=...
<<<READOUT readout_id=2 file=...
:::DATA_END
```

this is not allowed:

```text
:::ASSAY_START
<<< ASSAY_READOUT readout_id=1 file=...
%%% ASSAY_READOUT_START readout_id=2
...
%%% ASSAY_READOUT_END
:::ASSAY_END

:::DATA_START
<<<READOUT readout_id=1 file=...
%%% READOUT_START readout_id=2
....
%%% READOUT_END
:::DATA_END
```

Linked file paths MUST be relative to the parent directory of FILE_INFO.{file_name}.

Linked fields MUST include a readout_id value unless this specification explicitly permits otherwise.

Linked files MUST contain only the payload for the linked field and MUST follow the format of that field without block markers or field delimiters.

accepted <<< READOUT payload example:
```text
Time  	A1   	A2
0     	0.11 	0.22
600   	0.33 	0.44
```


wrong <<< READOUT payload example:
```text
%%% READOUT_START readout_id=id1
Time 	A1   	A2
0    	0.11 	0.22
600  	0.33 	0.44
%%% READOUT_END
```

## Examples

See [examples](examples/) for sample ATST files and linked data layouts.
