from dataclasses import dataclass

import pandas as pd

from ATST.blocks import READOUT_IDS
from ATST.blocks.base_classes import WideTableBlock
from ATST.errors import ATSTValidationError
from ATST.validation import validate_readout_registry


@dataclass
class ReadoutIds(WideTableBlock):
    """Registry of readout IDs used by a multi-readout ATST file."""

    name: str = READOUT_IDS

    def __post_init__(self) -> None:
        if not isinstance(self.data, pd.DataFrame):
            raise TypeError("READOUT_IDS cannot be per-readout/nested")

        super().__post_init__(required_fields={"readout_id"})
        if list(self.data.columns) != ["readout_id"]:
            raise ATSTValidationError(
                "READOUT_IDS must contain only the readout_id column"
            )

        validate_readout_registry(self)
        readout_ids = self.data["readout_id"].tolist()
        if not readout_ids:
            raise ATSTValidationError(
                "READOUT_IDS must contain at least one readout_id"
            )
        if len(readout_ids) != len(set(readout_ids)):
            raise ATSTValidationError(
                "READOUT_IDS contains duplicate readout_id values"
            )


__all__ = ["ReadoutIds"]
