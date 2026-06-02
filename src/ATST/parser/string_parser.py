from typing import Collection

from ATST.errors import (
    ATSTParseError,
    ATSTReservedNameError,
)

RESERVED_SIGILS = ("===", ":::", "%%%", "<<<", "_START", "_END")

RESERVED_NAMES = {
    "readout_id",
    "time",
    "type",
    "well_loc",
    "na",
    "file_header",
    "study",
    "readout_manifest",
    "metadata",
    "metadata_readout",
    "assay",
    "assay_readout",
    "entities",
    "layout_schema",
    "type_definitions",
    "type_constraints",
    "layout",
    "layout_readout",
    "data",
    "readout",
}


def _validate_not_reserved(value: str, *, allow_reserved: Collection[str] = ()) -> None:
    allowed = {name.casefold() for name in allow_reserved}
    folded = value.casefold()

    if folded in RESERVED_NAMES and folded not in allowed:
        raise ATSTReservedNameError(f"Reserved name cannot be used here: {value!r}")


def parse_str(
    s: str,
    *,
    allow_reserved: Collection[str] = (),
    check_reserved: bool = False,
) -> str:
    """Normalize an ATST cell value.

    Leading and trailing spaces are ignored by the ATST spec. Tabs and newlines
    are delimiters, so they are rejected inside individual parsed values.
    """

    if not isinstance(s, str):
        raise TypeError(f"ATST values must be strings, got {type(s).__name__}")

    value = s.strip()

    if "\t" in value or "\n" in value or "\r" in value:
        raise ATSTParseError("Values must not contain tabs or newlines")

    for sigil in RESERVED_SIGILS:
        if sigil in value:
            raise ATSTParseError(
                f"Values can't contain reserved sigil {sigil!r}"
            )

    if check_reserved:
        _validate_not_reserved(value, allow_reserved=allow_reserved)

    return value


def parse_identifier(
    s: str,
    *,
    allow_reserved: Collection[str] = (),
) -> str:
    """Normalize and validate a user-defined identifier."""

    return parse_str(s, allow_reserved=allow_reserved, check_reserved=True)


def parse_tag(line: str, prefix: str) -> tuple[str, dict[str, str]]:
    raw = line.strip()
    if not raw.startswith(prefix):
        raise ATSTParseError(f"Expected {prefix!r} tag, got {line!r}")

    body = raw[len(prefix) :].strip()
    if not body:
        raise ATSTParseError(f"Empty {prefix!r} tag")

    parts = body.split()
    name = parts[0]
    attrs: dict[str, str] = {}

    for part in parts[1:]:
        if "=" not in part:
            raise ATSTParseError(f"Malformed tag attribute {part!r} in {line!r}")
        key, value = part.split("=", 1)
        attrs[parse_identifier(key, allow_reserved={"readout_id"})] = parse_str(value)

    return name, attrs
