"""Permissive parsing for ATST files used as generator templates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ATST.blocks import (
    ASSAY,
    ENTITIES,
    FILE_INFO,
    LAYOUT,
    METADATA,
    READOUT_IDS,
    STUDY,
    Entities,
)
from ATST.blocks.base_classes import LongTable, WideTable
from ATST.parser.block_parser import (
    parse_block,
    parse_field_blocks,
    read_long_table,
    read_wide_table,
)
from ATST.parser.parser import parse_file


LAYOUT_RESERVED_COLUMNS = {"curve_id", "well_loc", "type"}


@dataclass
class TemplateATST:
    """ATST data recovered from a possibly incomplete template."""

    file_info: LongTable
    study: LongTable
    metadata: LongTable
    assay: LongTable
    layout: WideTable
    entities: Entities
    readout_id: str | None = None
    multi_readout_file: bool = False
    readouts: dict[str, TemplateReadout] | None = None
    shared_blocks: dict[str, bool] | None = None


@dataclass
class TemplateReadout:
    metadata: dict[str, str]
    assay: dict[str, str]
    layout: pd.DataFrame


def read_atst_lax(path: str | Path) -> TemplateATST:
    """Read available template blocks without enforcing required content."""

    path = Path(path)
    blocks = parse_file(path.read_text(encoding="utf-8").splitlines())
    readout_ids_block = blocks.get(READOUT_IDS)
    multi_readout_file = False
    readout_ids: list[str] = []
    if readout_ids_block is not None:
        multi_readout_file = True
        readout_ids_table = read_wide_table(
            readout_ids_block.lines,
            allow_reserved_columns={"readout_id"},
        )
        if "readout_id" in readout_ids_table and not readout_ids_table.empty:
            readout_ids = [
                str(value) for value in readout_ids_table["readout_id"]
            ]
    readout_id = readout_ids[0] if readout_ids else None

    def select_field(fields):
        if readout_id is not None:
            for field in fields:
                if field.attrs.get("readout_id") == readout_id:
                    return field
        return fields[0] if fields else None

    def long_data(block_name: str) -> dict[str, str]:
        block = blocks.get(block_name)
        if block is None:
            return {}

        lines, fields, _ = parse_field_blocks(block.lines)
        if lines:
            return read_long_table(lines)

        field = select_field(fields)
        return read_long_table(field.lines) if field is not None else {}

    def wide_data(block_name: str) -> pd.DataFrame:
        block = blocks.get(block_name)
        if block is None:
            return pd.DataFrame()

        lines, fields, _ = parse_field_blocks(block.lines)
        field = None if lines else select_field(fields)
        selected_lines = lines if lines else field.lines if field is not None else []
        if not selected_lines:
            return pd.DataFrame()
        data = read_wide_table(
            selected_lines,
            allow_reserved_columns=LAYOUT_RESERVED_COLUMNS
            if block_name == LAYOUT
            else (),
        )
        return _streamlit_supported_layout(data) if block_name == LAYOUT else data

    def all_long_data(block_name: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
        block = blocks.get(block_name)
        if block is None:
            return {}, {}
        lines, fields, _ = parse_field_blocks(block.lines)
        shared = read_long_table(lines) if lines else {}
        per_readout = {
            str(field.attrs["readout_id"]): read_long_table(field.lines)
            for field in fields
            if field.attrs.get("readout_id") is not None
        }
        return shared, per_readout

    def all_wide_data(block_name: str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
        block = blocks.get(block_name)
        if block is None:
            return pd.DataFrame(), {}
        lines, fields, _ = parse_field_blocks(block.lines)

        def read(lines_to_read) -> pd.DataFrame:
            if not lines_to_read:
                return pd.DataFrame()
            data = read_wide_table(
                lines_to_read,
                allow_reserved_columns=LAYOUT_RESERVED_COLUMNS,
            )
            return _streamlit_supported_layout(data)

        shared = read(lines)
        per_readout = {
            str(field.attrs["readout_id"]): read(field.lines)
            for field in fields
            if field.attrs.get("readout_id") is not None
        }
        return shared, per_readout

    entities = Entities()
    if ENTITIES in blocks:
        parsed_entities = parse_block(blocks[ENTITIES], base_dir=path.parent)
        if isinstance(parsed_entities, Entities):
            entities = parsed_entities

    metadata_shared, metadata_by_id = all_long_data(METADATA)
    assay_shared, assay_by_id = all_long_data(ASSAY)
    layout_shared, layout_by_id = all_wide_data(LAYOUT)
    template_readouts = None
    shared_blocks = None
    if readout_ids:
        template_readouts = {
            identifier: TemplateReadout(
                metadata=dict(metadata_shared or metadata_by_id.get(identifier, {})),
                assay=dict(assay_shared or assay_by_id.get(identifier, {})),
                layout=(
                    layout_shared.copy()
                    if not layout_shared.empty
                    else layout_by_id.get(identifier, pd.DataFrame()).copy()
                ),
            )
            for identifier in readout_ids
        }
        shared_blocks = {
            "metadata": bool(metadata_shared),
            "assay": bool(assay_shared),
            "layout": not layout_shared.empty,
        }

    return TemplateATST(
        file_info=LongTable(FILE_INFO, long_data(FILE_INFO)),
        study=LongTable(STUDY, long_data(STUDY)),
        metadata=LongTable(METADATA, long_data(METADATA)),
        assay=LongTable(ASSAY, long_data(ASSAY)),
        layout=WideTable(LAYOUT, wide_data(LAYOUT)),
        entities=entities,
        readout_id=readout_id,
        multi_readout_file=multi_readout_file,
        readouts=template_readouts,
        shared_blocks=shared_blocks,
    )


def _streamlit_supported_layout(data: pd.DataFrame) -> pd.DataFrame:
    """Skip curve-keyed layouts while retaining the rest of a template."""

    if "curve_id" in data.columns and "well_loc" not in data.columns:
        return pd.DataFrame()
    return data
