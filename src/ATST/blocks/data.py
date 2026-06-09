from dataclasses import dataclass

from ATST.blocks import DATA
from ATST.blocks.base_classes import Block, WideTableBlock


@dataclass
class Data(WideTableBlock, Block):
    name: str = DATA
    
    
    def __post_init__(self):
        self.data = self.data.astype(float)