from ATST.blocks import FILE_INFO
from ATST.blocks.base_classes import Block, LongTableBlock, dataclass


REQUIRED_FIELDS = {
    "file_name",
    "format",
    "format_version",
    "created_on",
    "field_delimiter",
    "encoding",
}


@dataclass
class FileMetadata(LongTableBlock, Block):
    name: str = FILE_INFO

    def __post_init__(self):
        super().__post_init__(REQUIRED_FIELDS)
