from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pandas as pd


@dataclass(frozen=True)
class DeviceOutput:
    """Parsed device output ready to use when building an ATST file."""

    file_name: str
    metadata: dict[str, str]
    assay: dict[str, str]
    readings: pd.DataFrame
    layout: pd.DataFrame | None = None


@runtime_checkable
class DeviceReader(Protocol):
    """Contract implemented by ATST device-output readers."""

    def read(
        self,
        raw: bytes | str,
        *,
        filename: str = "",
    ) -> DeviceOutput: ...
