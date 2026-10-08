from collections.abc import Collection, Iterable
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from ATST.ATSTFile.ATST import ATSTFile, MultiReadoutATST, validate_atst
from ATST.blocks import (
    ASSAY,
    ENTITIES,
    FILE_INFO,
    LAYOUT,
    METADATA,
    READINGS,
    READOUT_IDS,
    STUDY,
    Metadata,
    Assay,
    Layout,
    Entities,
    Readings,
)
from ATST.errors import ATSTValidationError
from ATST.numeric import TOKENS, readings_text
from ATST.parser.string_parser import parse_identifier, parse_str


def _stringify_cell(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return parse_str(str(value))


def _has_atst_extension(path: Path) -> bool:
    return path.name.endswith((".atst.txt", ".atst.tsv"))


def _all_blocks_same(blocks: dict[str, Metadata | Assay]) -> bool:
    values = iter(blocks.values())
    first = next(values, None)
    return first is not None and all(block.data == first.data for block in values)


def format_table_rows(
    rows: list[list[str]],
    *,
    human_readable: bool = True,
    pad_first_column: bool = False,
) -> list[str]:
    """Format table rows for ATST text output.

    Args:
        rows: Already-stringified rows to join with TAB characters.
        human_readable: Pad columns for easy visual inspection in `.txt` files.
            This is mostly cosmetic and is not useful when exporting strict `.tsv`.
        pad_first_column: Add extra indentation before the first column to make
            long-table hierarchy easier to scan in human-readable `.txt` output.
    """

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
    """Convert a long-table block dictionary into ATST row text."""

    rows = [
        [
            parse_identifier(field, allow_reserved=allow_reserved_fields),
            _stringify_cell(value),
        ]
        for field, value in data.items()
    ]
    return format_table_rows(
        rows, human_readable=human_readable, pad_first_column=human_readable
    )


def write_wide_table(
    data: pd.DataFrame,
    *,
    allow_reserved_columns: Collection[str] = (),
    human_readable: bool = False,
) -> list[str]:
    """Convert a wide-table DataFrame into ATST row text."""

    if data.empty and len(data.columns) == 0:
        raise ATSTValidationError("Cannot write an empty wide table")

    data = readings_text(data) if TOKENS in data.attrs else data.copy()
    data.columns = [
        parse_identifier(column, allow_reserved=allow_reserved_columns)
        for column in data.columns
    ]

    rows = [list(map(str, data.columns))]
    for row in data.itertuples(index=False, name=None):
        rows.append([_stringify_cell(value) for value in row])

    return format_table_rows(rows, human_readable=human_readable)


def write_block(lines: list[str], block_name: str, payload: Iterable[str]) -> None:
    """Append a complete top-level ATST block to an output line buffer."""

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
    """Append a nested field block, optionally with ATST tag attributes."""

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


def entity_payload(
    entities: Entities | None, *, human_readable: bool = False
) -> list[str]:
    """Serialize all entity tables into nested `TABLE` field blocks."""

    if entities is None or not entities.tables:
        return []

    lines: list[str] = []
    for table in entities.tables.values():
        write_field(
            lines,
            "TABLE",
            write_wide_table(table.data, human_readable=human_readable),
            attrs={"name": table.table_name, "pk": table.pk},
        )
    return lines[:-1] if lines and lines[-1] == "" else lines


LINKABLE_BLOCKS = frozenset({METADATA, ASSAY, ENTITIES, LAYOUT, READINGS})


def _resolve_linked_blocks(
    linked_files: bool,
    linked_blocks: Collection[str] | None,
) -> set[str]:
    if not linked_files:
        if linked_blocks is not None:
            raise ValueError("linked_blocks requires linked_files=True")
        return set()

    requested = (
        set(LINKABLE_BLOCKS)
        if linked_blocks is None
        else ({linked_blocks} if isinstance(linked_blocks, str) else set(linked_blocks))
    )
    unknown = requested - LINKABLE_BLOCKS
    if unknown:
        expected = ", ".join(sorted(LINKABLE_BLOCKS))
        received = ", ".join(sorted(map(str, unknown)))
        raise ValueError(
            f"Unknown linked_blocks: {received}. Expected case-sensitive names: {expected}"
        )
    return requested


def _write_rows(path: Path, rows: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _linked_container_path(atst: ATSTFile | MultiReadoutATST, path: str | Path) -> Path:
    output_dir = Path(path)
    if output_dir.exists() and not output_dir.is_dir():
        raise ATSTValidationError("Linked ATST output path must be a directory")
    output_dir.mkdir(parents=True, exist_ok=True)

    container_name = str(atst.file_info.data.get("file_name", ""))
    if not _has_atst_extension(Path(container_name)):
        raise ATSTValidationError(
            "FILE_INFO.file_name must use the .atst.txt or .atst.tsv extension"
        )
    return output_dir / container_name


def _write_linked_entities_directory(
    lines: list[str],
    entities: Entities | None,
    output_dir: Path,
) -> None:
    if entities is None or not entities.tables:
        return

    links: list[str] = []
    relative_paths: set[str] = set()
    for table in entities.tables.values():
        table_name = parse_identifier(table.table_name)
        relative = f"entities/{table_name.lower()}.tsv"
        if relative in relative_paths:
            raise ATSTValidationError(
                "ENTITIES table names must remain unique when lowercased for filenames"
            )
        relative_paths.add(relative)
        _write_rows(
            output_dir / relative,
            write_wide_table(table.data, human_readable=False),
        )
        links.append(f"<<<TABLE name={table.table_name} pk={table.pk} file={relative}")
    write_block(lines, ENTITIES, links)


def _finish_container(lines: list[str], path: Path) -> Path:
    if lines and lines[-1] == "":
        lines.pop()
    lines.append("===FILE_END")
    _write_rows(path, lines)
    return path


def _write_single_linked_directory(
    atst: ATSTFile,
    path: str | Path,
    *,
    linked_blocks: set[str],
    human_readable: bool,
) -> Path:
    container_path = _linked_container_path(atst, path)
    output_dir = container_path.parent
    lines: list[str] = ["===FILE_START"]

    file_info = dict(atst.file_info.data)
    file_info["file_name"] = container_path.name
    write_block(lines, FILE_INFO, write_long_table(file_info, human_readable=human_readable))
    write_block(lines, STUDY, write_long_table(atst.study.data, human_readable=human_readable))

    long_blocks = (
        (METADATA, "METADATA_READOUT", "metadata/metadata.tsv", atst.metadata),
        (ASSAY, "ASSAY_READOUT", "assays/assay.tsv", atst.assay),
    )
    for block_name, field_name, relative, block_value in long_blocks:
        if block_name in linked_blocks:
            _write_rows(output_dir / relative, write_long_table(block_value.data))
            write_block(lines, block_name, [f"<<<{field_name} file={relative}"])
        else:
            write_block(
                lines,
                block_name,
                write_long_table(block_value.data, human_readable=human_readable),
            )

    if ENTITIES in linked_blocks:
        _write_linked_entities_directory(lines, atst.entities, output_dir)
    else:
        entity_lines = entity_payload(atst.entities, human_readable=human_readable)
        if entity_lines:
            write_block(lines, ENTITIES, entity_lines)

    wide_blocks = (
        (LAYOUT, "LAYOUT_READOUT", "layouts/layout.tsv", atst.layout, {"curve_id", "well_loc", "type"}),
        (READINGS, "READOUT", "readings/readings.tsv", atst.readings, {"Time"}),
    )
    for block_name, field_name, relative, block_value, allowed in wide_blocks:
        if block_name in linked_blocks:
            _write_rows(
                output_dir / relative,
                write_wide_table(block_value.data, allow_reserved_columns=allowed),
            )
            write_block(lines, block_name, [f"<<<{field_name} file={relative}"])
        else:
            write_block(
                lines,
                block_name,
                write_wide_table(
                    block_value.data,
                    allow_reserved_columns=allowed,
                    human_readable=human_readable,
                ),
            )

    return _finish_container(lines, container_path)


def write_atst(
    atst: ATSTFile,
    path: str | Path,
    *,
    human_readable: bool = True,
    linked_files: bool = False,
    linked_blocks: Collection[str] | None = None,
) -> Path:
    """Write a single-readout ATST file inline or as a linked directory.

    Args:
        atst: Single-readout ATST object to serialize.
        path: Output file path, or output directory when `linked_files=True`.
        human_readable: Pad columns to make `.txt` files easier to inspect by
            eye. Leave this off for machine-oriented `.tsv` output.
        linked_files: Write a container and linked payloads inside `path`.
        linked_blocks: Case-sensitive block names to link. Defaults to all of
            METADATA, ASSAY, ENTITIES, LAYOUT, and READINGS when linked output
            is enabled.
    """

    if isinstance(atst, MultiReadoutATST):
        raise TypeError("write_file expects an ATST object, not MultiReadoutATST")

    validate_atst(atst)
    resolved_links = _resolve_linked_blocks(linked_files, linked_blocks)
    if linked_files:
        return _write_single_linked_directory(
            atst,
            path,
            linked_blocks=resolved_links,
            human_readable=human_readable,
        )

    path = Path(path)
    if not _has_atst_extension(path):
        raise ATSTValidationError(
            "ATST files must use the .atst.txt or .atst.tsv extension"
        )

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

    write_block(
        lines,
        LAYOUT,
        write_wide_table(
            atst.layout.data,
            allow_reserved_columns={"curve_id", "well_loc", "type"},
            human_readable=human_readable,
        ),
    )
    write_block(
        lines,
        READINGS,
        write_wide_table(
            atst.readings.data,
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
    readout_blocks: dict[str, Layout | Readings],
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


def _write_multi_linked_directory(
    atst: MultiReadoutATST,
    path: str | Path,
    *,
    linked_blocks: set[str],
    human_readable: bool,
) -> Path:
    container_path = _linked_container_path(atst, path)
    output_dir = container_path.parent
    lines: list[str] = ["===FILE_START"]

    file_info = dict(atst.file_info.data)
    file_info["file_name"] = container_path.name
    write_block(lines, FILE_INFO, write_long_table(file_info, human_readable=human_readable))
    write_block(lines, STUDY, write_long_table(atst.study.data, human_readable=human_readable))
    write_block(
        lines,
        READOUT_IDS,
        write_wide_table(
            atst.readout_ids.data,
            allow_reserved_columns={"readout_id"},
            human_readable=human_readable,
        ),
    )

    for block_name, field_name, folder, prefix, attribute in (
        (METADATA, "METADATA_READOUT", "metadata", "meta", "metadata"),
        (ASSAY, "ASSAY_READOUT", "assays", "assay", "assay"),
    ):
        blocks = {
            readout_id: getattr(readout, attribute)
            for readout_id, readout in atst.readouts.items()
        }
        if block_name in linked_blocks:
            links = []
            shared_relative = f"{folder}/{prefix}.tsv" if _all_blocks_same(blocks) else None
            for readout_id, block_value in blocks.items():
                safe_id = parse_identifier(readout_id)
                relative = shared_relative or f"{folder}/{prefix}_{safe_id}.tsv"
                if shared_relative is None or not links:
                    _write_rows(output_dir / relative, write_long_table(block_value.data))
                links.append(
                    f"<<<{field_name} readout_id={readout_id} file={relative}"
                )
            write_block(lines, block_name, links)
        else:
            _write_per_readout_long_block(
                lines,
                block_name,
                field_name,
                blocks,
                human_readable=human_readable,
            )

    if ENTITIES in linked_blocks:
        _write_linked_entities_directory(lines, atst.entities, output_dir)
    else:
        entity_lines = entity_payload(atst.entities, human_readable=human_readable)
        if entity_lines:
            write_block(lines, ENTITIES, entity_lines)

    for block_name, field_name, folder, prefix, attribute, allowed in (
        (LAYOUT, "LAYOUT_READOUT", "layouts", "layout", "layout", {"curve_id", "well_loc", "type"}),
        (READINGS, "READOUT", "readings", "readings", "readings", {"Time"}),
    ):
        blocks = {
            readout_id: getattr(readout, attribute)
            for readout_id, readout in atst.readouts.items()
        }
        if block_name in linked_blocks:
            links = []
            for readout_id, block_value in blocks.items():
                safe_id = parse_identifier(readout_id)
                relative = f"{folder}/{prefix}_{safe_id}.tsv"
                _write_rows(
                    output_dir / relative,
                    write_wide_table(
                        block_value.data,
                        allow_reserved_columns=allowed,
                    ),
                )
                links.append(
                    f"<<<{field_name} readout_id={readout_id} file={relative}"
                )
            write_block(lines, block_name, links)
        else:
            _write_per_readout_wide_block(
                lines,
                block_name,
                field_name,
                blocks,
                human_readable=human_readable,
                allow_reserved_columns=allowed,
            )

    return _finish_container(lines, container_path)


def write_multi_readout_atst(
    atst: MultiReadoutATST,
    path: str | Path,
    *,
    human_readable: bool = True,
    linked_files: bool = False,
    linked_blocks: Collection[str] | None = None,
) :
    """Write a multi-readout ATST file inline or as a linked directory.

    Args:
        atst: Multi-readout ATST object with one `ATSTFile` per readout ID.
        path: Output file path, or output directory when `linked_files=True`.
        human_readable: Pad columns for visual review in `.txt` output. For
            `.tsv` exports, the compact default is usually the better fit.
        linked_files: Write a container and linked payloads inside `path`.
        linked_blocks: Case-sensitive block names to link. Defaults to all of
            METADATA, ASSAY, ENTITIES, LAYOUT, and READINGS when linked output
            is enabled.
    """

    validate_atst(atst)
    resolved_links = _resolve_linked_blocks(linked_files, linked_blocks)
    if linked_files:
        return _write_multi_linked_directory(
            atst,
            path,
            linked_blocks=resolved_links,
            human_readable=human_readable,
        )

    path = Path(path)
    if not _has_atst_extension(path):
        raise ATSTValidationError(
            "ATST files must use the .atst.txt or .atst.tsv extension"
        )

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
        READOUT_IDS,
        write_wide_table(
            atst.readout_ids.data,
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

    _write_per_readout_wide_block(
        lines,
        LAYOUT,
        "LAYOUT_READOUT",
        {readout_id: readout.layout for readout_id, readout in atst.readouts.items()},
        human_readable=human_readable,
        allow_reserved_columns={"curve_id", "well_loc", "type"},
    )
    _write_per_readout_wide_block(
        lines,
        READINGS,
        "READOUT",
        {readout_id: readout.readings for readout_id, readout in atst.readouts.items()},
        human_readable=human_readable,
        allow_reserved_columns={"Time"},
    )

    if lines and lines[-1] == "":
        lines.pop()
    lines.append("===FILE_END")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path.name


def _linked_entity_fields(
    lines: list[str], entities: Entities | None, payloads: dict[str, str]
) -> None:
    if entities is None or not entities.tables:
        return
    links: list[str] = []
    for table in entities.tables.values():
        table_key = parse_identifier(table.table_name)
        relative = f"entities/{table_key.lower()}.tsv"
        payloads[relative] = "\n".join(
            write_wide_table(table.data, human_readable=False)
        ) + "\n"
        links.append(
            f"<<<TABLE name={table.table_name} pk={table.pk} file={relative}"
        )
    write_block(lines, ENTITIES, links)


def write_linked_atst_bundle(
    atst: ATSTFile | MultiReadoutATST,
    path: str | Path,
    *,
    human_readable: bool = True,
) -> Path:
    """Write an ATST container and all payload tables as one ZIP archive.

    The archive contains a root `.atst.txt` container plus linked TSV files in
    `metadata/`, `assays/`, `layouts/`, `readings/`, and `entities/` folders.
    The resulting container can be read directly after extracting the archive.
    """

    validate_atst(atst)
    path = Path(path)
    if path.suffix.lower() != ".zip":
        raise ATSTValidationError("Linked ATST bundles must use the .zip extension")

    container_name = path.stem
    if not _has_atst_extension(Path(container_name)):
        container_name = f"{container_name}.atst.txt"

    lines: list[str] = ["===FILE_START"]
    payloads: dict[str, str] = {}

    file_info = dict(atst.file_info.data)
    file_info["file_name"] = container_name
    write_block(lines, FILE_INFO, write_long_table(file_info, human_readable=human_readable))
    write_block(lines, STUDY, write_long_table(atst.study.data, human_readable=human_readable))

    def add_linked_block(block_name: str, field_name: str, relative: str) -> None:
        write_block(lines, block_name, [f"<<<{field_name} file={relative}"])

    if isinstance(atst, MultiReadoutATST):
        write_block(
            lines,
            READOUT_IDS,
            write_wide_table(
                atst.readout_ids.data,
                allow_reserved_columns={"readout_id"},
                human_readable=human_readable,
            ),
        )
        linked_lines: dict[str, list[str]] = {METADATA: [], ASSAY: [], LAYOUT: [], READINGS: []}
        for block_name, field_name, folder, prefix, attribute in (
            (METADATA, "METADATA_READOUT", "metadata", "meta", "metadata"),
            (ASSAY, "ASSAY_READOUT", "assays", "assay", "assay"),
        ):
            blocks = {
                readout_id: getattr(readout, attribute)
                for readout_id, readout in atst.readouts.items()
            }
            shared_relative = f"{folder}/{prefix}.tsv" if _all_blocks_same(blocks) else None
            for readout_id, block_value in blocks.items():
                safe_id = parse_identifier(readout_id)
                relative = shared_relative or f"{folder}/{safe_id}.tsv"
                payloads[relative] = "\n".join(write_long_table(block_value.data)) + "\n"
                linked_lines[block_name].append(
                    f"<<<{field_name} readout_id={readout_id} file={relative}"
                )
            write_block(lines, block_name, linked_lines[block_name])
        _linked_entity_fields(lines, atst.entities, payloads)
        for readout_id, readout in atst.readouts.items():
            safe_id = parse_identifier(readout_id)
            for block_name, field_name, folder, rows in (
                (LAYOUT, "LAYOUT_READOUT", "layouts", write_wide_table(readout.layout.data, allow_reserved_columns={"curve_id", "well_loc", "type"}, human_readable=False)),
                (READINGS, "READOUT", "readings", write_wide_table(readout.readings.data, allow_reserved_columns={"Time"}, human_readable=False)),
            ):
                relative = f"{folder}/{safe_id}.tsv"
                payloads[relative] = "\n".join(rows) + "\n"
                linked_lines[block_name].append(
                    f"<<<{field_name} readout_id={readout_id} file={relative}"
                )
        for block_name in (LAYOUT, READINGS):
            write_block(lines, block_name, linked_lines[block_name])
    else:
        for block_name, field_name, folder, rows in (
            (METADATA, "METADATA_READOUT", "metadata", write_long_table(atst.metadata.data, human_readable=False)),
            (ASSAY, "ASSAY_READOUT", "assays", write_long_table(atst.assay.data, human_readable=False)),
        ):
            relative = f"{folder}/{folder}.tsv"
            payloads[relative] = "\n".join(rows) + "\n"
            add_linked_block(block_name, field_name, relative)
        _linked_entity_fields(lines, atst.entities, payloads)
        for block_name, field_name, folder, rows in (
            (LAYOUT, "LAYOUT_READOUT", "layouts", write_wide_table(atst.layout.data, allow_reserved_columns={"curve_id", "well_loc", "type"}, human_readable=False)),
            (READINGS, "READOUT", "readings", write_wide_table(atst.readings.data, allow_reserved_columns={"Time"}, human_readable=False)),
        ):
            relative = f"{folder}/{folder}.tsv"
            payloads[relative] = "\n".join(rows) + "\n"
            add_linked_block(block_name, field_name, relative)

    if lines and lines[-1] == "":
        lines.pop()
    lines.append("===FILE_END")
    container_text = "\n".join(lines) + "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(container_name, container_text)
        for relative, text in payloads.items():
            archive.writestr(relative, text)
    return path
