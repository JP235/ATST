from dataclasses import dataclass

from ATST.blocks import ASSAY
from ATST.blocks.base_classes import LongTableBlock

REQUIRED_FIELDS = {
    "readout_type",
    "readout_unit",
    "time_unit",
}


@dataclass
class Assay(LongTableBlock):
    """Assay readout type, units, time unit, and measurement settings."""

    name: str = ASSAY

    def __post_init__(self) -> None:
        super().__post_init__(REQUIRED_FIELDS)
