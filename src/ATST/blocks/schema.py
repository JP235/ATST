

from dataclasses import dataclass

from ATST.blocks import LAYOUT_SCHEMA
from ATST.blocks.base_classes import LongTableBlock, WideTableBlock


@dataclass
class LayoutSchema:
    name: str = LAYOUT_SCHEMA
    type_definitions: LongTableBlock | None = None
    type_constraints: WideTableBlock | None = None
