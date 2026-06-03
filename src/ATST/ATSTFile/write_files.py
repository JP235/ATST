from collections.abc import Collection, Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from ATST.ATSTFile.ATST import ATSTFile, MultiReadoutATST
from ATST.blocks import (
    ASSAY,
    DATA,
    ENTITIES,
    FILE_INFO,
    LAYOUT,
    LAYOUT_SCHEMA,
    METADATA,
    READOUT_MANIFEST,
    STUDY,
    Metadata,
    Assay,
    Layout,
    Entities,
    LayoutSchema,
    Data,
)
from ATST.errors import ATSTValidationError
from ATST.parser.string_parser import parse_identifier, parse_str


def _stringify_cell(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError, ValueError:
        pass
    return parse_str(str(value))


def _format_table_rows(
    rows: list[list[str]],
    *,
    human_readable: bool = True,
    pad_first_column: bool = False,
) -> list[str]:
    if not rows:
        return []

    if not human_readable:
        return ["\t".join(row) for row in rows]

    column_count = max(len(row) for row in rows)
    padded_rows = [row + [""] * (column_count - len(row)) for row in rows]
    widths = [
        max(len(row[column_index]) for row in padded_rows)
        for column_index in range(column_count)
    ]

    out_rows = []
    for row in padded_rows:
        row_cells = []
        for column_index, cell in enumerate(row):
            if column_index == 0 and pad_first_column:
                row_cells.append("   " + cell.ljust(widths[column_index] + 1))
            elif column_index == column_count - 1:
                row_cells.append(cell)
            else:
                row_cells.append(cell.ljust(widths[column_index] + 1))

        out_rows.append("\t".join(row_cells))

    return out_rows


def write_long_table(
    data: dict[str, str],
    *,
    allow_reserved_fields: Collection[str] = (),
    human_readable: bool = False,
) -> list[str]:
    rows = [
        [
            parse_identifier(field, allow_reserved=allow_reserved_fields),
            _stringify_cell(value),
        ]
        for field, value in data.items()
    ]
    return _format_table_rows(
        rows, human_readable=human_readable, pad_first_column=True
    )


def write_wide_table(
    data: pd.DataFrame,
    *,
    allow_reserved_columns: Collection[str] = (),
    human_readable: bool = False,
) -> list[str]:
    if data.empty and len(data.columns) == 0:
        raise ATSTValidationError("Cannot write an empty wide table")

    data = data.copy()
    data.columns = [
        parse_identifier(column, allow_reserved=allow_reserved_columns)
        for column in data.columns
    ]

    rows = [list(map(str, data.columns))]
    for row in data.itertuples(index=False, name=None):
        rows.append([_stringify_cell(value) for value in row])

    return _format_table_rows(rows, human_readable=human_readable)


def write_block(lines: list[str], block_name: str, payload: Iterable[str]) -> None:
    lines.append(f":::{block_name}_START")
    lines.extend(payload)
    lines.append(f":::{block_name}_END")
    lines.append("")


def write_field(
    lines: list[str],
    field_name: str,
    payload: Iterable[str],
    *,
    attrs: dict[str, str] | None = None,
) -> None:
    attr_text = ""
    if attrs:
        attr_text = " " + " ".join(
            f"{parse_identifier(key, allow_reserved={'readout_id'})}={_stringify_cell(value)}"
            for key, value in attrs.items()
        )

    lines.append(f"%%%{field_name}_START{attr_text}")
    lines.extend(payload)
    lines.append(f"%%%{field_name}_END")
    lines.append("")


def entity_payload(entities: Entities, *, human_readable: bool = False) -> list[str]:
    lines: list[str] = []
    for table in entities.tables.values():
        write_field(
            lines,
            "TABLE",
            write_wide_table(table.data, human_readable=human_readable),
            attrs={"name": table.table_name, "pk": table.pk},
        )
    return lines[:-1] if lines and lines[-1] == "" else lines


def layout_schema_payload(
    layout_schema: LayoutSchema,
    *,
    human_readable: bool = False,
) -> list[str]:
    lines: list[str] = []
    if layout_schema.type_definitions is not None:
        write_field(
            lines,
            "TYPE_DEFINITIONS",
            write_long_table(
                layout_schema.type_definitions.data,
                allow_reserved_fields={"well_loc", "type"},
                human_readable=human_readable,
            ),
        )
    if layout_schema.type_constraints is not None:
        write_field(
            lines,
            "TYPE_CONSTRAINTS",
            write_wide_table(
                layout_schema.type_constraints.data,
                allow_reserved_columns={"type"},
                human_readable=human_readable,
            ),
        )
    return lines[:-1] if lines and lines[-1] == "" else lines


def write_atst(
    atst: ATSTFile, path: str | Path, *, human_readable: bool = False
) -> Path:
    """Write a standalone single-readout ATST file."""

    if isinstance(atst, MultiReadoutATST):
        raise TypeError("write_file expects an ATST object, not MultiReadoutATST")

    path = Path(path)
    if path.suffix != ".txt" or not path.name.endswith(".atst.txt"):
        raise ATSTValidationError("ATST files must use the .atst.txt extension")

    file_info = dict(atst.file_info.data)
    file_info["file_name"] = path.name

    lines: list[str] = ["===FILE_START"]
    write_block(
        lines,
        FILE_INFO,
        write_long_table(file_info, human_readable=human_readable),
    )
    write_block(
        lines,
        STUDY,
        write_long_table(atst.study.data, human_readable=human_readable),
    )
    write_block(
        lines,
        METADATA,
        write_long_table(atst.metadata.data, human_readable=human_readable),
    )
    write_block(
        lines,
        ASSAY,
        write_long_table(atst.assay.data, human_readable=human_readable),
    )

    entity_lines = entity_payload(atst.entities, human_readable=human_readable)
    if entity_lines:
        write_block(lines, ENTITIES, entity_lines)

    layout_schema_lines = layout_schema_payload(
        atst.layout_schema,
        human_readable=human_readable,
    )
    if layout_schema_lines:
        write_block(lines, LAYOUT_SCHEMA, layout_schema_lines)

    write_block(
        lines,
        LAYOUT,
        write_wide_table(
            atst.layout.data,
            allow_reserved_columns={"well_loc", "type"},
            human_readable=human_readable,
        ),
    )
    write_block(
        lines,
        DATA,
        write_wide_table(
            atst.data.data,
            allow_reserved_columns={"Time"},
            human_readable=human_readable,
        ),
    )

    if lines and lines[-1] == "":
        lines.pop()
    lines.append("===FILE_END")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_per_readout_long_block(
    lines: list[str],
    block_name: str,
    field_name: str,
    readout_blocks: dict[str, Metadata | Assay],
    *,
    human_readable: bool,
) -> None:
    field_lines: list[str] = []
    for readout_id, block in readout_blocks.items():
        write_field(
            field_lines,
            field_name,
            write_long_table(block.data, human_readable=human_readable),
            attrs={"readout_id": readout_id},
        )

    write_block(lines, block_name, field_lines[:-1])


def _write_per_readout_wide_block(
    lines: list[str],
    block_name: str,
    field_name: str,
    readout_blocks: dict[str, Layout | Data],
    *,
    human_readable: bool,
    allow_reserved_columns: set[str],
) -> None:
    field_lines: list[str] = []
    for readout_id, block in readout_blocks.items():
        write_field(
            field_lines,
            field_name,
            write_wide_table(
                block.data,
                allow_reserved_columns=allow_reserved_columns,
                human_readable=human_readable,
            ),
            attrs={"readout_id": readout_id},
        )

    write_block(lines, block_name, field_lines[:-1])


def write_multi_readout_atst(
    atst: MultiReadoutATST,
    path: str | Path,
    *,
    human_readable: bool = False,
) -> Path:
    """Write a multi-readout ATST file with in-file readout payloads."""

    path = Path(path)
    file_info = dict(atst.file_info.data)
    file_info["file_name"] = path.name

    lines: list[str] = ["===FILE_START"]
    write_block(
        lines,
        FILE_INFO,
        write_long_table(file_info, human_readable=human_readable),
    )
    write_block(
        lines,
        STUDY,
        write_long_table(atst.study.data, human_readable=human_readable),
    )
    write_block(
        lines,
        READOUT_MANIFEST,
        write_wide_table(
            atst.readout_manifest.data,
            allow_reserved_columns={"readout_id"},
            human_readable=human_readable,
        ),
    )

    _write_per_readout_long_block(
        lines,
        METADATA,
        "METADATA_READOUT",
        {readout_id: readout.metadata for readout_id, readout in atst.readouts.items()},
        human_readable=human_readable,
    )
    _write_per_readout_long_block(
        lines,
        ASSAY,
        "ASSAY_READOUT",
        {readout_id: readout.assay for readout_id, readout in atst.readouts.items()},
        human_readable=human_readable,
    )

    entity_lines = entity_payload(atst.entities, human_readable=human_readable)
    if entity_lines:
        write_block(lines, ENTITIES, entity_lines)

    layout_schema_lines = layout_schema_payload(
        atst.layout_schema,
        human_readable=human_readable,
    )
    if layout_schema_lines:
        write_block(lines, LAYOUT_SCHEMA, layout_schema_lines)

    _write_per_readout_wide_block(
        lines,
        LAYOUT,
        "LAYOUT_READOUT",
        {readout_id: readout.layout for readout_id, readout in atst.readouts.items()},
        human_readable=human_readable,
        allow_reserved_columns={"well_loc", "type"},
    )
    _write_per_readout_wide_block(
        lines,
        DATA,
        "READOUT",
        {readout_id: readout.data for readout_id, readout in atst.readouts.items()},
        human_readable=human_readable,
        allow_reserved_columns={"Time"},
    )

    if lines and lines[-1] == "":
        lines.pop()
    lines.append("===FILE_END")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
