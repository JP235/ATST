from dataclasses import dataclass

from ATST.blocks import METADATA
from ATST.blocks.base_classes import LongTableBlock, Block


REQUIRED_FIELDS = {
    "instrument",
    "plate_type",
    "date_start",
    "operator",
}


@dataclass
class Metadata(LongTableBlock, Block):
    name: str = METADATA

    def __post_init__(self) -> None:
        super().__post_init__(REQUIRED_FIELDS)
