from dataclasses import dataclass

from ATST.blocks import METADATA
from ATST.blocks.base_classes import LongTableBlock


REQUIRED_FIELDS = set()


@dataclass
class Metadata(LongTableBlock):
    """Instrument, operator, plate, and acquisition metadata."""

    name: str = METADATA

    def __post_init__(self) -> None:
        super().__post_init__(REQUIRED_FIELDS)
