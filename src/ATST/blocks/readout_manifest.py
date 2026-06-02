from dataclasses import dataclass

import pandas as pd

from ATST.blocks import READOUT_MANIFEST
from ATST.blocks.base_classes import Block, WideTableBlock

REQUIRED_FIELDS = {"readout_id"}
READOUT_MANIFEST_REQUIRED_EXTRA_FIELDS = {
    "readout_id",
    "metadata_file",
    "assay_file",
    "layout_file",
    "data_file",
}


@dataclass
class ReadoutManifest(WideTableBlock, Block):
    name: str = READOUT_MANIFEST

    def __post_init__(self):
        if not isinstance(self.data, pd.DataFrame):
            raise TypeError("READOUT_MANIFEST cannot be per-readout/nested")

        super().__post_init__(
            required_fields=REQUIRED_FIELDS,
        )
        if len(self.data) > 1:
            assert set(self.data.columns) == READOUT_MANIFEST_REQUIRED_EXTRA_FIELDS


__all__ = ["ReadoutManifest"]
