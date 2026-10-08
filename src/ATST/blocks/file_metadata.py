from ATST.blocks import FILE_INFO
from ATST.blocks.base_classes import LongTableBlock, dataclass


REQUIRED_FIELDS = {
    "file_name",
    "format",
    "format_version",
    "created_on",
    "field_delimiter",
    "encoding",
}


@dataclass
class FileMetadata(LongTableBlock):
    """Required file-level ATST metadata block."""

    name: str = FILE_INFO

    def __post_init__(self):
        self.data = {
            **self.data,
            "format": "ATST",
            "format_version": "0.1",
            "field_delimiter": "TAB",
            "encoding": "UTF-8",
        }
        super().__post_init__(REQUIRED_FIELDS)
