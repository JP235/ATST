from typing import Final, Literal, TypeAlias

ASSAY: Final = "ASSAY"
ENTITIES: Final = "ENTITIES"
FILE_INFO: Final = "FILE_INFO"
LAYOUT: Final = "LAYOUT"
METADATA: Final = "METADATA"
READINGS: Final = "READINGS"
READOUT_IDS: Final = "READOUT_IDS"
STUDY: Final = "STUDY"

BlockName: TypeAlias = Literal[
    "ASSAY",
    "ENTITIES",
    "FILE_INFO",
    "LAYOUT",
    "METADATA",
    "READINGS",
    "READOUT_IDS",
    "STUDY",
]

ALLOWED_BLOCK_NAMES: tuple[BlockName, ...] = (
    ASSAY,
    ENTITIES,
    FILE_INFO,
    LAYOUT,
    METADATA,
    READINGS,
    READOUT_IDS,
    STUDY,
)
