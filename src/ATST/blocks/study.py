from dataclasses import dataclass

from ATST.blocks.base_classes import Block, LongTableBlock
from ATST.blocks import STUDY

REQUIRED_FIELDS = {"title", "study_id"}


@dataclass
class Study(LongTableBlock, Block):
    name: str = STUDY

    def __post_init__(self):
        return super().__post_init__(REQUIRED_FIELDS)
