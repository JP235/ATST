from __future__ import annotations

from datetime import date
from pathlib import Path

from ATST import ATSTFile, MultiReadoutATST
from ATST.blocks import (
    Assay,
    Entities,
    EntityTable,
    FileMetadata,
    Layout,
    Metadata,
    Readings,
    ReadoutIds,
    Study,
)
from ATST.errors import ATSTValidationError
from ATST.numeric import TOKENS, readings_text
import pandas as pd

from streamlit_app.tables.layout import sort_layout_rows
from streamlit_app.tables.uploads import sort_readings_columns


ATST_EXTENSIONS = (".atst.txt", ".atst.tsv")


def prepare_wide_table(
    df: pd.DataFrame,
    *,
    block_name: str,
    plate_format: str | None = None,
) -> pd.DataFrame:
    """Clean an uploaded/editor wide table before building an ATST block.

    Args:
        df: Source table from an upload or Streamlit editor.
        block_name: Name used in validation error messages.
    """

    df = readings_text(df) if TOKENS in df.attrs else df.copy()
    df.columns = [str(column).strip() for column in df.columns]
    df = df.fillna("")
    df = df.map(lambda value: "" if pd.isna(value) else str(value).strip())

    if block_name == "LAYOUT":
        df = sort_layout_rows(df, plate_format=plate_format)

    empty_rows = df.apply(
        lambda row: all(str(value).strip() == "" for value in row), axis=1
    )
    df = df.loc[~empty_rows].copy()

    if df.empty:
        raise ValueError(f"{block_name} table is empty.")

    if block_name == "READINGS":
        df = sort_readings_columns(df, plate_format=plate_format)

    return df


def layout_download_file_name(file_name: str) -> str:
    """Derive a layout TSV filename from an ATST output filename."""

    name = Path(file_name).name
    for suffix in (".atst.txt", ".atst.tsv", ".txt", ".tsv", ".csv"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return f"{name or 'layout'}_layout.tsv"


def normalize_atst_file_name(file_name: str) -> str:
    """Return a safe ATST filename, adding `.atst.txt` when needed."""

    name = Path(file_name).name.strip()
    if not name:
        return "new_assay.atst.txt"
    if name.endswith(ATST_EXTENSIONS):
        return name
    for suffix in (".txt", ".tsv", ".csv"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return f"{name}.atst.txt"


def make_atst(
    *,
    file_name: str,
    study_data: dict[str, str],
    metadata_data: dict[str, str],
    assay_data: dict[str, str],
    layout_df: pd.DataFrame,
    readings_df: pd.DataFrame,
    entities: Entities | None,
) -> ATSTFile:
    """Build a single-readout `ATSTFile` from Streamlit form data.

    Args:
        file_name: Output ATST filename stored in `FILE_INFO`.
        study_data: Field/value data for the `STUDY` block.
        metadata_data: Field/value data for the `METADATA` block.
        assay_data: Field/value data for the `ASSAY` block.
        layout_df: Cleaned `LAYOUT` table.
        readings_df: Cleaned `READINGS` table.
        entities: Optional entity tables to include.
    """

    return ATSTFile(
        file_info=FileMetadata(
            data={
                "file_name": file_name,
                "format": "ATST",
                "format_version": "0.1",
                "created_on": date.today().isoformat(),
                "field_delimiter": "TAB",
                "encoding": "UTF-8",
            },
        ),
        study=Study(data=study_data),
        metadata=Metadata(data=metadata_data),
        assay=Assay(data=assay_data),
        layout=Layout(data=layout_df),
        readings=Readings(data=readings_df),
        entities=entities,
        readout_ids=None,
    )


def entities_from_tables(tables: dict[str, pd.DataFrame]) -> Entities:
    """Convert uploaded entity DataFrames into an `Entities` block."""

    entity_tables = {}
    for table_name, table_data in tables.items():
        df = prepare_wide_table(table_data, block_name=f"ENTITIES.{table_name}")
        if len(df.columns) == 0:
            continue
        pk = str(df.columns[0])
        entity_tables[table_name] = EntityTable(
            name="ENTITIES",
            table_name=table_name,
            pk=pk,
            data=df,
        )
    return Entities(tables=entity_tables)


def make_multi_readout_atst(
    *,
    file_name: str,
    study_data: dict[str, str],
    readout_data: list[
        tuple[
            str,
            dict[str, str],
            dict[str, str],
            pd.DataFrame,
            pd.DataFrame,
        ]
    ],
    entities: Entities,
) -> MultiReadoutATST:
    """Build a multi-readout file, validating its ID registry first."""

    readout_ids = ReadoutIds(
        data=pd.DataFrame({"readout_id": [item[0] for item in readout_data]})
    )
    if any(not str(value).strip() for value in readout_ids.data["readout_id"]):
        raise ATSTValidationError("READOUT_IDS contains a blank readout_id value")
    readouts: dict[str, ATSTFile] = {}
    for readout_id, metadata, assay, layout, readings in readout_data:
        child = make_atst(
            file_name=file_name,
            study_data=study_data,
            metadata_data=metadata,
            assay_data=assay,
            layout_df=layout,
            readings_df=readings,
            entities=entities,
        )
        child.readout_id = readout_id
        child.readout_ids = readout_ids
        readouts[readout_id] = child

    first = next(iter(readouts.values()))
    return MultiReadoutATST(
        file_info=first.file_info,
        study=first.study,
        readout_ids=readout_ids,
        readouts=readouts,
        entities=entities,
    )
