from dataclasses import dataclass

from ATST.blocks import LAYOUT
from ATST.blocks.base_classes import Block, WideTableBlock


@dataclass
class Layout(WideTableBlock, Block):
    name: str = LAYOUT
