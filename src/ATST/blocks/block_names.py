from typing import Final, Literal, TypeAlias

ASSAY: Final = "ASSAY"
DATA: Final = "DATA"
ENTITIES: Final = "ENTITIES"
FILE_INFO: Final = "FILE_INFO"
LAYOUT: Final = "LAYOUT"
LAYOUT_SCHEMA: Final = "LAYOUT_SCHEMA"
METADATA: Final = "METADATA"
READOUT_MANIFEST: Final = "READOUT_MANIFEST"
STUDY: Final = "STUDY"

BlockName: TypeAlias = Literal[
    "ASSAY",
    "DATA",
    "ENTITIES",
    "FILE_INFO",
    "LAYOUT",
    "LAYOUT_SCHEMA",
    "METADATA",
    "READOUT_MANIFEST",
    "STUDY",
]

ALLOWED_BLOCK_NAMES: tuple[BlockName, ...] = (
    ASSAY,
    DATA,
    ENTITIES,
    FILE_INFO,
    LAYOUT,
    LAYOUT_SCHEMA,
    METADATA,
    READOUT_MANIFEST,
    STUDY,
)
