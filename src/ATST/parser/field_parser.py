

from ATST.errors import (
    ATSTParseError,
)

from parser.string_parser import parse_identifier, parse_tag, RESERVED_NAMES



class Field:
    def __init__(
        self,
        name: str,
        line: list[str],
        value: str | list[Field],
    ):
        self.name = name
        self.line = line

        if isinstance(value, str):
            self.value = value
            self.is_nested = False
        else:
            self.is_nested = True
            self.subfields = {subfield.name: subfield for subfield in value}

    def __getattribute__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )

        if name in self.subfields:
            return self.subfields[name].value

        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __dir__(self) -> list[str]:
        if self.is_nested:
            return list(self.subfields.keys())

        return [self.name]


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
        field_name=field_name,
        file_path=file_path,
        readout_id=readout_id,
        attrs=attrs,
    )


class LinkedField:
    def __init__(
        self,
        field_name: str,
        file_path: str,
        readout_id: str,
        attrs: dict[str, str] | None = None,
    ):
        self.field_name = field_name
        self.file_path = file_path
        self.readout_id = readout_id
        self.attrs = attrs or {}
