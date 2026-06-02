from dataclasses import dataclass

from ATST.blocks import ASSAY
from ATST.blocks.base_classes import LongTableBlock, Block

REQUIRED_FIELDS = {
    "readout_type",
    "readout_unit",
    "time_unit",
    "plate_format",
}


@dataclass
class Assay(LongTableBlock, Block):
    name: str = ASSAY

    def __post_init__(self) -> None:
        super().__post_init__(REQUIRED_FIELDS)
