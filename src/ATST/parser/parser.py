from typing import Iterable


from ATST.blocks import (
    ALLOWED_BLOCK_NAMES,
    ASSAY,
    ENTITIES,
    FILE_INFO,
    LAYOUT,
    METADATA,
    READINGS,
    READOUT_IDS,
    STUDY,
    BlockName,
)
from ATST.blocks.base_classes import Block
from ATST.errors import (
    ATSTError,
    ATSTParseError,
)
from ATST.parser.string_parser import RESERVED_NAMES, parse_identifier, parse_tag


TOP_LEVEL_BLOCK_ORDER = (
    FILE_INFO,
    STUDY,
    READOUT_IDS,
    METADATA,
    ASSAY,
    ENTITIES,
    LAYOUT,
    READINGS,
)


def parse_block_start(line: str):
    """Parse a top-level `:::BLOCK_START` line and return the block name."""

    name, attrs = parse_tag(line, ":::")
    if attrs:
        raise ATSTParseError(f"Top-level block tags do not accept attributes: {line!r}")
    if not name.endswith("_START"):
        raise ATSTParseError(f"Expected block start tag, got {line!r}")

    block_name = parse_identifier(
        name[: -len("_START")],
        allow_reserved=RESERVED_NAMES,
    )
    if block_name not in ALLOWED_BLOCK_NAMES:
        raise ATSTParseError(f"Unknown block name: {block_name!r}")

    return block_name


def parse_block_end(line: str) -> str:
    """Parse a top-level `:::BLOCK_END` line and return the block name."""

    name, attrs = parse_tag(line, ":::")
    if attrs:
        raise ATSTParseError(f"Top-level block tags do not accept attributes: {line!r}")
    if not name.endswith("_END"):
        raise ATSTParseError(f"Expected block end tag, got {line!r}")

    block_name = parse_identifier(
        name[: -len("_END")],
        allow_reserved=RESERVED_NAMES,
    )
    if block_name not in ALLOWED_BLOCK_NAMES:
        raise ATSTParseError(f"Unknown block name: {block_name!r}")

    return block_name


def parse_file(lines: Iterable[str]) -> dict[str, Block]:
    """Split ATST file text into raw top-level blocks.

    Args:
        lines: Iterable of file lines, usually from `Path.read_text().splitlines()`.
    """

    cleaned = [line.rstrip("\r\n") for line in lines]
    non_empty = [line.strip() for line in cleaned if len(line.strip()) > 0]

    if len(non_empty) < 2:
        raise ATSTParseError("ATST file is empty")

    first_valid_line = non_empty.pop(0)
    last_valid_line = non_empty.pop()

    if not non_empty:
        raise ATSTParseError("ATST file is empty")
    if first_valid_line != "===FILE_START":
        raise ATSTParseError("ATST file must start with ===FILE_START")
    if last_valid_line != "===FILE_END":
        raise ATSTParseError("ATST file must end with ===FILE_END")

    if sum(line.strip() == "===FILE_START" for line in cleaned) != 1 or sum(
        line.strip() == "===FILE_END" for line in cleaned
    ) != 1:
        raise ATSTParseError("ATST must contain exactly one FILE_START and FILE_END")

    blocks: dict[str, Block] = {}
    current_block_name: BlockName | None = None
    current_block_lines = []
    last_block_index = -1

    for line_number, line in enumerate(cleaned):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            if stripped in {"===FILE_START", "===FILE_END"}:
                continue

            if stripped.startswith(":::") and stripped.endswith("_END"):
                if current_block_name is None:
                    raise ATSTParseError(
                        f"Block end {stripped!r} found before block start"
                    )

                if parse_block_end(stripped) != current_block_name:
                    raise ATSTParseError(
                        f"Block end {stripped!r} does not match open block: {current_block_name!r}"
                    )

                blocks[current_block_name] = Block(
                    name=current_block_name, lines=current_block_lines
                )
                current_block_name = None
                current_block_lines = []
                continue

            if current_block_name is None:
                current_block_name = parse_block_start(stripped)
                if current_block_name in blocks:
                    raise ATSTParseError(f"Duplicate block {current_block_name!r}")

                block_index = TOP_LEVEL_BLOCK_ORDER.index(current_block_name)
                if block_index <= last_block_index:
                    raise ATSTParseError(
                        f"Block {current_block_name!r} appears out of order"
                    )
                last_block_index = block_index

                continue

            current_block_lines.append(line)

        except ATSTError as exc:
            raise type(exc)(f"Line {line_number}: {exc}") from exc

    if current_block_name is not None:
        raise ATSTParseError(f"Block {current_block_name!r} was not closed")

    return blocks
