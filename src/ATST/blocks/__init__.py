from ATST.blocks.block_names import (
    ALLOWED_BLOCK_NAMES,
    ASSAY,
    ENTITIES,
    FILE_INFO,
    LAYOUT,
    METADATA,
    READINGS,
    READOUT_IDS,
    STUDY,
    BlockName,
)
from ATST.blocks.assay import Assay
from ATST.blocks.entities import Entities, EntityTable
from ATST.blocks.file_metadata import FileMetadata
from ATST.blocks.layout import Layout
from ATST.blocks.metadata import Metadata
from ATST.blocks.readings import Readings
from ATST.blocks.readout_ids import ReadoutIds
from ATST.blocks.study import Study


BlockClass = (
    Assay
    | Entities
    | FileMetadata
    | Layout
    | Metadata
    | Readings
    | ReadoutIds
    | Study
)

__all__ = [
    "ASSAY",
    "ENTITIES",
    "FILE_INFO",
    "LAYOUT",
    "METADATA",
    "READINGS",
    "READOUT_IDS",
    "STUDY",
    "ALLOWED_BLOCK_NAMES",
    "BlockClass",
    "BlockName",
    "Assay",
    "Entities",
    "EntityTable",
    "FileMetadata",
    "Layout",
    "Metadata",
    "Readings",
    "ReadoutIds",
    "Study",
]
