from dataclasses import dataclass

from ATST.blocks import (
    Assay,
    Data,
    Entities,
    FileMetadata,
    Layout,
    LayoutSchema,
    Metadata,
    ReadoutManifest,
    Study,
)


@dataclass
class ATSTFile:
    file_info: FileMetadata
    study: Study
    data: Data
    metadata: Metadata
    assay: Assay
    layout: Layout
    entities: Entities
    layout_schema: LayoutSchema
    readout_manifest: ReadoutManifest | None
    readout_id: str | None = None


@dataclass
class MultiReadoutATST:
    file_info: FileMetadata
    study: Study
    readout_manifest: ReadoutManifest
    readouts: dict[str, ATSTFile]
    entities: Entities
    layout_schema: LayoutSchema

    def __post_init__(self) -> None:
        for readout_id, atst in self.readouts.items():
            atst.readout_id = readout_id

    def __getattr__(self, name: str) -> ATSTFile:
        if name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )

        if name in self.readouts:
            return self.readouts[name]

        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(self.readouts.keys()))
