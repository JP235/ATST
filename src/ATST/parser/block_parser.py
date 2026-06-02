from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Collection, Iterable, cast

import pandas as pd

from ATST.blocks import (
    ALLOWED_BLOCK_NAMES,
    ASSAY,
    DATA,
    ENTITIES,
    FILE_INFO,
    LAYOUT,
    LAYOUT_SCHEMA,
    METADATA,
    READOUT_MANIFEST,
    STUDY,
    Assay,
    BlockClass,
    BlockName,
    Entities,
    EntityTable,
    FileMetadata,
    Layout,
    LayoutSchema,
    Metadata,
    ReadoutManifest,
    Study,
    Data,
)
from ATST.blocks.base_classes import (
    Block,
    LongTable,
    LongTableBlock,
    WideTable,
    WideTableBlock,
)
from ATST.errors import (
    ATSTError,
    ATSTParseError,
    ATSTValidationError,
)
from ATST.parser.string_parser import (
    RESERVED_NAMES,
    parse_identifier,
    parse_str,
    parse_tag,
)


@dataclass
class FieldBlock:
    name: str
    attrs: dict[str, str]
    lines: list[str]


@dataclass
class LinkedField:
    name: str
    file_path: str
    readout_id: str
    attrs: dict[str, str]


_LONG_BLOCKS = {
    ASSAY: Assay,
    FILE_INFO: FileMetadata,
    METADATA: Metadata,
    STUDY: Study,
}
_WIDE_BLOCKS = {
    DATA: Data,
    LAYOUT: Layout,
    READOUT_MANIFEST: ReadoutManifest,
}
_READOUT_FIELD_NAMES = {
    ASSAY: "ASSAY_READOUT",
    DATA: "READOUT",
    LAYOUT: "LAYOUT_READOUT",
    METADATA: "METADATA_READOUT",
}
_WIDE_ALLOW_RESERVED = {
    DATA: {"Time"},
    LAYOUT: {"well_loc", "type"},
    READOUT_MANIFEST: {"readout_id"},
}


def _as_lines(text_or_lines: str | Iterable[str]) -> list[str]:
    if isinstance(text_or_lines, str):
        return text_or_lines.splitlines()

    return [line.rstrip("\r\n") for line in text_or_lines]


def read_long_table(
    text_or_lines: str | Iterable[str],
    *,
    allow_reserved_fields: Collection[str] = (),
    required_fields: Collection[str] | None = None,
) -> dict[str, str]:
    """Read ATST long-table text as field-name/value pairs."""

    rows = [line for line in _as_lines(text_or_lines) if line.strip()]
    data: dict[str, str] = {}

    for row_number, line in enumerate(rows, start=1):
        cells = line.split("\t")
        if len(cells) != 2:
            raise ATSTParseError(
                f"Long table row {row_number} must contain exactly two TAB-separated cells"
            )

        field_name = parse_identifier(cells[0], allow_reserved=allow_reserved_fields)
        value = parse_str(cells[1])

        if field_name in data:
            raise ATSTParseError(f"Duplicate long-table field: {field_name!r}")

        data[field_name] = value

    if required_fields:
        required = {
            parse_str(field, allow_reserved=allow_reserved_fields)
            for field in required_fields
        }
        missing = required - set(data)
        if missing:
            raise ATSTValidationError(
                f"Missing required fields: {', '.join(sorted(missing))}"
            )

    return data


def read_wide_table(
    text_or_lines: str | Iterable[str],
    required_columns: Collection[str] | None = None,
    *,
    allow_reserved_columns: Collection[str] = (),
):
    """Read ATST wide-table text as a pandas DataFrame."""

    lines = [line for line in _as_lines(text_or_lines) if line.strip()]

    if not lines:
        raise ATSTParseError("Wide table is empty")

    text = "\n".join(lines)

    try:
        df = pd.read_csv(
            StringIO(text),
            sep="\t",
            dtype=str,
            keep_default_na=False,
            na_filter=False,
        )
    except Exception as exc:
        raise ATSTParseError(f"Could not parse wide table: {exc}") from exc

    columns = [
        parse_identifier(column, allow_reserved=allow_reserved_columns)
        for column in df.columns
    ]

    if len(columns) != len(set(columns)):
        duplicates = sorted({column for column in columns if columns.count(column) > 1})
        raise ATSTParseError(f"Duplicate wide-table columns: {', '.join(duplicates)}")

    df.columns = columns
    df = df.map(parse_str)

    if required_columns:
        required = {
            parse_identifier(column, allow_reserved=allow_reserved_columns)
            for column in required_columns
        }
        missing = required - set(df.columns)
        if missing:
            raise ATSTValidationError(
                f"Missing required columns: {', '.join(sorted(missing))}"
            )

    return df


def parse_block(block: Block) -> BlockClass:
    block_name = block.name

    if block_name not in ALLOWED_BLOCK_NAMES:
        raise ATSTParseError(f"Unknown block name: {block_name!r}")

    first_line = block.lines[0]

    lines, fields, links = _parse_field_blocks(block.lines)

    if block_name == ENTITIES:
        if links:
            raise ATSTParseError("ENTITIES linked TABLE fields are not supported here")
        return _parse_entities(lines, fields)

    if block_name == LAYOUT_SCHEMA:
        if links:
            raise ATSTParseError("LAYOUT_SCHEMA does not accept linked fields")
        return _parse_layout_schema(lines, fields)

    if links:
        return _parse_linked_block(block_name, lines, fields, links)

    if not first_line.startswith("%%%"):
        if block_name in _LONG_BLOCKS:
            return _LONG_BLOCKS[block_name](
                name=block_name,
                data=read_long_table(lines),
            )

        if block_name in _WIDE_BLOCKS:
            return _WIDE_BLOCKS[block_name](
                name=block_name,
                data=read_wide_table(
                    lines,
                    allow_reserved_columns=_WIDE_ALLOW_RESERVED.get(block_name, set()),
                ),
            )

    readout_data = _read_per_readout_data(block_name, lines, fields)
    if readout_data is None:
        raise ATSTParseError("Per-readout data is empty")

    if block_name in _LONG_BLOCKS:
        return _LONG_BLOCKS[block_name].per_readout(
            name=block_name,
            data=cast(dict[str, dict[str, str]], readout_data),
        )
    if block_name in _WIDE_BLOCKS:
        return _WIDE_BLOCKS[block_name].per_readout(
            name=block_name,
            data=cast(dict[str, pd.DataFrame], readout_data),
        )

    raise ATSTParseError(f"Unknown block type: {block_name!r}")


def _parse_field_start(line: str) -> tuple[str, dict[str, str]]:
    name, attrs = parse_tag(line, "%%%")
    if not name.endswith("_START"):
        raise ATSTParseError(f"Expected field start tag, got {line!r}")

    field_name = parse_identifier(name[: -len("_START")], allow_reserved=RESERVED_NAMES)
    return field_name, attrs


def _parse_field_end(line: str) -> str:
    name, attrs = parse_tag(line, "%%%")
    if attrs:
        raise ATSTParseError(f"Field end tags do not accept attributes: {line!r}")
    if not name.endswith("_END"):
        raise ATSTParseError(f"Expected field end tag, got {line!r}")

    return parse_identifier(name[: -len("_END")], allow_reserved=RESERVED_NAMES)


def _parse_link(line: str) -> LinkedField:
    name, attrs = parse_tag(line, "<<<")
    field_name = parse_identifier(name, allow_reserved=RESERVED_NAMES)

    if "file" not in attrs:
        raise ATSTParseError(f"Linked field is missing file attribute: {line!r}")

    file_path = attrs.pop("file")
    readout_id = attrs.pop("readout_id", "")

    return LinkedField(
        name=field_name,
        file_path=file_path,
        readout_id=readout_id,
        attrs=attrs,
    )


def _parse_field_blocks(
    lines: list[str],
) -> tuple[list[str], list[FieldBlock], list[LinkedField]]:
    block_lines: list[str] = []
    fields: list[FieldBlock] = []
    links: list[LinkedField] = []
    current_field_name: str | None = None
    current_field_attrs: dict[str, str] = {}
    current_field_lines: list[str] = []

    for line_number, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        try:
            if stripped.startswith("%%%") and stripped.endswith("_END"):
                if current_field_name is None:
                    raise ATSTParseError(
                        f"Field end {stripped!r} found before field start"
                    )

                field_name = _parse_field_end(stripped)
                if field_name != current_field_name:
                    raise ATSTParseError(
                        f"Field end {stripped!r} does not match open field: {current_field_name!r}"
                    )

                fields.append(
                    FieldBlock(
                        name=current_field_name,
                        attrs=current_field_attrs,
                        lines=current_field_lines,
                    )
                )
                current_field_name = None
                current_field_attrs = {}
                current_field_lines = []
                continue

            if current_field_name is None:
                if stripped.startswith("<<<"):
                    links.append(_parse_link(stripped))
                    continue

                if stripped.startswith("%%%"):
                    current_field_name, current_field_attrs = _parse_field_start(
                        stripped
                    )
                    continue

                block_lines.append(line)
                continue

            if stripped.startswith("%%%"):
                raise ATSTParseError("Nested %%% fields are not supported")

            if stripped.startswith("<<<"):
                raise ATSTParseError(
                    "Linked fields are not supported inside %%% fields"
                )

            current_field_lines.append(line)

        except ATSTError as exc:
            raise type(exc)(f"Line {line_number}: {exc}") from exc

    if current_field_name is not None:
        raise ATSTParseError(f"Field {current_field_name!r} was not closed")

    return block_lines, fields, links


def _read_linked_lines(file_path: str) -> list[str]:
    try:
        return Path(file_path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ATSTParseError(
            f"Could not read linked file {file_path!r}: {exc.strerror or exc}"
        ) from exc


def metadata_from_link(file_path: str) -> Metadata:
    return Metadata(
        name=METADATA,
        data=read_long_table(_read_linked_lines(file_path)),
        linked_file=file_path,
    )


def assay_from_link(file_path: str) -> Assay:
    return Assay(
        name=ASSAY,
        data=read_long_table(_read_linked_lines(file_path)),
        linked_file=file_path,
    )


def layout_from_link(file_path: str) -> Layout:
    return Layout(
        name=LAYOUT,
        data=read_wide_table(
            _read_linked_lines(file_path),
            allow_reserved_columns=_WIDE_ALLOW_RESERVED.get(LAYOUT, set()),
        ),
        linked_file=file_path,
    )


def data_from_link(file_path: str) -> Data:
    return Data(
        name=DATA,
        data=read_wide_table(
            _read_linked_lines(file_path),
            allow_reserved_columns=_WIDE_ALLOW_RESERVED.get(DATA, set()),
        ),
        linked_file=file_path,
    )


def _parse_linked_block(
    block_name: BlockName,
    lines: list[str],
    fields: list[FieldBlock],
    links: list[LinkedField],
) -> BlockClass:
    if lines or fields:
        raise ATSTParseError(f"{block_name} block cannot mix links with in-file data")

    expected_field_name = _READOUT_FIELD_NAMES.get(block_name)
    if expected_field_name is None:
        raise ATSTParseError(f"{block_name} does not accept linked fields")

    linked_files: dict[str, str] = {}
    for link in links:
        if link.name != expected_field_name:
            raise ATSTParseError(
                f"Unexpected {block_name} linked field {link.name!r}; "
                f"expected {expected_field_name!r}"
            )
        if link.attrs:
            raise ATSTParseError(
                f"{link.name} link has unsupported attributes: "
                f"{', '.join(sorted(link.attrs))}"
            )
        if not link.readout_id:
            raise ATSTParseError(f"{link.name} link is missing readout_id")
        if link.readout_id in linked_files:
            raise ATSTParseError(f"Duplicate readout_id {link.readout_id!r}")

        linked_files[link.readout_id] = link.file_path

    if block_name == METADATA:
        return Metadata(
            name=block_name,
            per_readout_data={
                readout_id: metadata_from_link(file_path)
                for readout_id, file_path in linked_files.items()
            },
        )
    if block_name == ASSAY:
        return Assay(
            name=block_name,
            per_readout_data={
                readout_id: assay_from_link(file_path)
                for readout_id, file_path in linked_files.items()
            },
        )
    if block_name == LAYOUT:
        return Layout(
            name=block_name,
            per_readout_data={
                readout_id: layout_from_link(file_path)
                for readout_id, file_path in linked_files.items()
            },
        )
    if block_name == DATA:
        return Data(
            name=block_name,
            per_readout_data={
                readout_id: data_from_link(file_path)
                for readout_id, file_path in linked_files.items()
            },
        )

    raise ATSTParseError(f"{block_name} does not accept linked fields")


def _read_per_readout_data(
    block_name: BlockName,
    lines: list[str],
    fields: list[FieldBlock],
) -> dict[str, dict[str, str] | pd.DataFrame] | None:
    if lines:
        raise ATSTParseError(f"Unexpected data in {block_name!r}:\n{lines!r}")

    expected_field_name = _READOUT_FIELD_NAMES[block_name]
    values: dict[str, dict[str, str] | pd.DataFrame] = {}

    for field in fields:
        if field.name != expected_field_name:
            raise ATSTParseError(
                f"Unexpected {block_name} per-readout field {field.name!r}; "
                f"expected {expected_field_name!r}"
            )
        extra_attrs = set(field.attrs) - {"readout_id"}
        if extra_attrs:
            raise ATSTParseError(
                f"{field.name} field has unsupported attributes: "
                f"{', '.join(sorted(extra_attrs))}"
            )

        readout_id = field.attrs["readout_id"]
        if readout_id in values:
            raise ATSTParseError(f"Duplicate readout_id {readout_id!r}")

        if block_name in _LONG_BLOCKS:
            values[readout_id] = read_long_table(field.lines)
        else:
            values[readout_id] = read_wide_table(
                field.lines,
                allow_reserved_columns=_WIDE_ALLOW_RESERVED.get(block_name, set()),
            )

    return values


def _parse_entities(lines: list[str], fields: list[FieldBlock]) -> Entities:
    if any(line.strip() for line in lines):
        raise ATSTParseError("ENTITIES block only accepts TABLE fields")

    tables: dict[str, EntityTable] = {}

    for field in fields:
        if field.name != "TABLE":
            raise ATSTParseError(f"Unexpected ENTITIES field {field.name!r}")

        table_name = field.attrs.get("name")
        pk = field.attrs.get("pk")
        if not table_name or not pk:
            raise ATSTParseError("TABLE field requires name and pk attributes")

        extra_attrs = set(field.attrs) - {"name", "pk"}
        if extra_attrs:
            raise ATSTParseError(
                f"TABLE field has unsupported attributes: {', '.join(sorted(extra_attrs))}"
            )
        if table_name in tables:
            raise ATSTParseError(f"Duplicate entity table {table_name!r}")

        df = read_wide_table(field.lines, required_columns={pk})
        if df[pk].duplicated().any():
            raise ATSTValidationError(
                f"Entity table {table_name!r} has duplicate primary key values"
            )

        table = EntityTable(name=table_name, data=df)
        table.table_name = table_name
        table.pk = pk
        tables[table_name] = table

    return Entities(tables=tables)


def _parse_layout_schema(
    lines: list[str],
    fields: list[FieldBlock],
) -> LayoutSchema:
    if any(line.strip() for line in lines):
        raise ATSTParseError(
            "LAYOUT_SCHEMA only accepts TYPE_DEFINITIONS and TYPE_CONSTRAINTS fields"
        )

    type_definitions: LongTable | None = None
    type_constraints: WideTable | None = None

    for field in fields:
        if field.attrs:
            raise ATSTParseError(f"{field.name} field does not accept attributes")

        if field.name == "TYPE_DEFINITIONS":
            if type_definitions is not None:
                raise ATSTParseError("Duplicate TYPE_DEFINITIONS field")

            type_definitions = LongTableBlock(
                name=LAYOUT_SCHEMA,
                data=read_long_table(
                    field.lines,
                    allow_reserved_fields={"well_loc", "type"},
                    required_fields={"well_loc", "type"},
                ),
            )
        elif field.name == "TYPE_CONSTRAINTS":
            if type_constraints is not None:
                raise ATSTParseError("Duplicate TYPE_CONSTRAINTS field")

            type_constraints = WideTableBlock(
                name=LAYOUT_SCHEMA,
                data=read_wide_table(
                    field.lines,
                    required_columns={"type", "REQUIRED_COLUMNS", "OPTIONAL_COLUMNS"},
                    allow_reserved_columns={"type"},
                ),
            )
        else:
            raise ATSTParseError(f"Unexpected LAYOUT_SCHEMA field {field.name!r}")

    return LayoutSchema(
        type_definitions=type_definitions,
        type_constraints=type_constraints,
    )
