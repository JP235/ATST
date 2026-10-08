from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import re
from uuid import uuid4

import pandas as pd

from ATST.device_readers import DeviceOutput


@dataclass
class ReadoutDraft:
    """Editable state for one readout, keyed independently of its display ID."""

    key: str
    readout_id: str
    upload_order: int
    source_name: str
    metadata: dict[str, str] = field(default_factory=dict)
    assay: dict[str, str] = field(default_factory=dict)
    layout: pd.DataFrame = field(default_factory=pd.DataFrame)
    readings: pd.DataFrame = field(default_factory=pd.DataFrame)
    versions: dict[str, int] = field(
        default_factory=lambda: {"metadata": 0, "assay": 0, "layout": 0}
    )

    def copy_block_from(self, other: ReadoutDraft, block_name: str) -> None:
        """Replace one editable block with a detached copy of another draft."""

        name = block_name.lower()
        value = getattr(other, name)
        setattr(self, name, value.copy() if isinstance(value, pd.DataFrame) else deepcopy(value))
        self.versions[name] = self.versions.get(name, 0) + 1


def new_readout_draft(
    output: DeviceOutput,
    *,
    upload_order: int,
    source_name: str,
) -> ReadoutDraft:
    return ReadoutDraft(
        key=uuid4().hex,
        readout_id=infer_readout_id(output, source_name),
        upload_order=upload_order,
        source_name=source_name,
        metadata=dict(output.metadata),
        assay=dict(output.assay),
        layout=(output.layout.copy() if output.layout is not None else pd.DataFrame()),
        readings=output.readings.copy(),
    )


def infer_readout_id(output: DeviceOutput, filename: str) -> str:
    """Infer a useful editable readout ID from parsed device metadata."""

    for values in (output.metadata, output.assay):
        plate_id = str(values.get("plate_id", "")).strip()
        if plate_id:
            return plate_id

    combined = {**output.assay, **output.metadata}
    parts = [
        str(combined.get(name, "")).strip()
        for name in ("date_start", "operator", "experiment_type", "isolate_id")
    ]
    if parts[0] and parts[2] and parts[3]:
        return "_".join(part for part in parts if part)

    return _filename_stem(filename) or "readout"


def ordered_readouts(readouts: dict[str, ReadoutDraft]) -> list[ReadoutDraft]:
    """Order numbered plates first, otherwise retain upload/template order."""

    def key(draft: ReadoutDraft) -> tuple[int, int, int]:
        number = _plate_number(draft)
        return (0, number, draft.upload_order) if number is not None else (
            1,
            draft.upload_order,
            draft.upload_order,
        )

    return sorted(readouts.values(), key=key)


def copy_shared_block(
    readouts: dict[str, ReadoutDraft], block_name: str
) -> ReadoutDraft | None:
    """Copy the first ordered draft's block into every other draft immediately."""

    ordered = ordered_readouts(readouts)
    if not ordered:
        return None
    canonical = ordered[0]
    for draft in ordered[1:]:
        draft.copy_block_from(canonical, block_name)
    return canonical


def _plate_number(draft: ReadoutDraft) -> int | None:
    for name in ("plate_num", "plate_number", "device_plate_number"):
        for values in (draft.assay, draft.metadata):
            match = re.search(r"\d+", str(values.get(name, "")))
            if match:
                return int(match.group())
    return None


def _filename_stem(filename: str) -> str:
    name = Path(filename).name
    for suffix in (".atst.txt", ".atst.tsv", ".xlsx", ".csv", ".tsv", ".txt"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return Path(name).stem
