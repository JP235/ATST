from pathlib import Path
from typing import Any, Literal, overload
import warnings

from ATST.ATSTFile.ATST import ATSTFile, MultiReadoutATST, validate_atst
from ATST.blocks import (
    ASSAY,
    ENTITIES,
    FILE_INFO,
    LAYOUT,
    METADATA,
    READINGS,
    READOUT_IDS,
    STUDY,
    Assay,
    BlockClass,
    Entities,
    FileMetadata,
    Layout,
    Metadata,
    Readings,
    ReadoutIds,
    Study,
)
from ATST.errors import ATSTParseError, ATSTValidationError
from ATST.parser.block_parser import parse_block
from ATST.parser.parser import parse_file
import pandas as pd


def _has_atst_extension(file_name: str) -> bool:
    return file_name.endswith((".atst.txt", ".atst.tsv"))


@overload
def read_atst(path: str | Path, multi_readouts: Literal[False] = False) -> ATSTFile: ...
@overload
def read_atst(
    path: str | Path, multi_readouts: Literal[True] = True
) -> MultiReadoutATST: ...
def read_atst(
    path: str | Path, multi_readouts: bool = False
) -> ATSTFile | MultiReadoutATST:
    """Read an ATST file into the ATST dataclass model.

    Linked payload files are resolved relative to the ATST file and loaded while
    parsing.

    Args:
        path: `.atst.txt` or `.atst.tsv` file to read.
        multi_readouts: Return a `MultiReadoutATST` when the file contains a
            `READOUT_IDS` with one or more readout IDs.
    """

    path = Path(path)
    if not _has_atst_extension(path.name):
        raise ATSTValidationError(
            "ATST files must use the .atst.txt or .atst.tsv extension"
        )

    base_dir = path.parent
    lines = path.read_text(encoding="utf-8").splitlines()
    parsed_blocks = {
        block_name: parse_block(block, base_dir=base_dir)
        for block_name, block in parse_file(lines).items()
    }

    def require_block(name: str) -> BlockClass:
        try:
            return parsed_blocks[name]
        except KeyError as exc:
            raise ATSTParseError(f"Missing required block {name!r}") from exc

    file_info = require_block(FILE_INFO)
    study = require_block(STUDY)
    if not isinstance(file_info, FileMetadata):
        raise ATSTParseError("FILE_INFO block did not parse as FileMetadata")
    if not isinstance(study, Study):
        raise ATSTParseError("STUDY block did not parse as Study")

    file_name = file_info.data["file_name"]
    if not _has_atst_extension(file_name):
        raise ATSTValidationError(
            "FILE_INFO.file_name must use the .atst.txt or .atst.tsv extension"
        )

    entities = parsed_blocks.get(ENTITIES, Entities())
    if not isinstance(entities, Entities):
        raise ATSTParseError("ENTITIES block did not parse as Entities")

    readout_ids_block = parsed_blocks.get(READOUT_IDS)
    if readout_ids_block is not None and not isinstance(
        readout_ids_block, ReadoutIds
    ):
        raise ATSTParseError("READOUT_IDS block did not parse as ReadoutIds")

    if readout_ids_block is None:
        if multi_readouts:
            raise ATSTValidationError(
                "multi_readouts=True requires a READOUT_IDS block"
            )

        metadata = require_block(METADATA)
        assay = require_block(ASSAY)
        layout = require_block(LAYOUT)
        readings = require_block(READINGS)

        if not isinstance(metadata, Metadata):
            raise ATSTParseError("METADATA block did not parse as Metadata")
        if not isinstance(assay, Assay):
            raise ATSTParseError("ASSAY block did not parse as Assay")
        if not isinstance(layout, Layout):
            raise ATSTParseError("LAYOUT block did not parse as Layout")
        if not isinstance(readings, Readings):
            raise ATSTParseError("READINGS block did not parse as Readings")

        for block_name, block in {
            METADATA: metadata,
            ASSAY: assay,
            LAYOUT: layout,
            READINGS: readings,
        }.items():
            if getattr(block, "per_readout_data", None):
                raise ATSTParseError(
                    f"{block_name} contains readout-specific data, but no "
                    "READOUT_IDS was declared"
                )

        return _build_atst_for_readout(
            readout_id=None,
            file_info=file_info,
            study=study,
            readout_ids=None,
            metadata=metadata,
            assay=assay,
            layout=layout,
            readings=readings,
            entities=entities,
        )

    readout_ids = readout_ids_block.data["readout_id"].tolist()

    if multi_readouts and len(readout_ids) == 1:
        warnings.warn(
            f"READOUT_IDS contains only one readout_id value: {readout_ids[0]}; "
            "returning MultiReadoutATST with a single readout",
            stacklevel=2,
        )

    if not multi_readouts and len(readout_ids) > 1:
        raise ATSTValidationError(
            f"READOUT_IDS contains more than one readout_id value: {', '.join(readout_ids)}"
        )

    metadata_by_id = _block_by_readout(
        parsed_blocks.get(METADATA),
        block_type=Metadata,
        readout_ids=readout_ids,
        allow_shared_leaf=True,
    )
    assay_by_id = _block_by_readout(
        parsed_blocks.get(ASSAY),
        block_type=Assay,
        readout_ids=readout_ids,
        allow_shared_leaf=True,
    )
    layout_by_id = _block_by_readout(
        parsed_blocks.get(LAYOUT),
        block_type=Layout,
        readout_ids=readout_ids,
        allow_shared_leaf=True,
    )
    readings_by_id = _block_by_readout(
        parsed_blocks.get(READINGS),
        block_type=Readings,
        readout_ids=readout_ids,
        allow_shared_leaf=False,
    )

    readouts = {
        readout_id: _build_atst_for_readout(
            readout_id=readout_id,
            file_info=file_info,
            study=study,
            readout_ids=readout_ids_block,
            metadata=metadata_by_id[readout_id],
            assay=assay_by_id[readout_id],
            layout=layout_by_id[readout_id],
            readings=readings_by_id[readout_id],
            entities=entities,
        )
        for readout_id in readout_ids
    }

    if len(readout_ids) == 1 and not multi_readouts:
        return readouts[readout_ids[0]]

    return MultiReadoutATST(
        file_info=file_info,
        study=study,
        readout_ids=readout_ids_block,
        readouts=readouts,
        entities=entities,
    )


def _block_by_readout(
    block: BlockClass | None,
    *,
    block_type: type,
    readout_ids: list[str],
    allow_shared_leaf: bool,
) -> dict[str, Any]:

    block_name = block_type.name

    if block is None:
        raise ATSTParseError(f"Missing required block {block_name!r}")

    if (
        isinstance(block, (Readings, Layout, Assay, Metadata))
        and block.per_readout_data
    ):
        readouts = dict(block.per_readout_data)
        _require_all_readout_ids(readouts, readout_ids, block_name)
        return {
            readout_id: _copy_leaf_block(readout, block_type, block_name)
            for readout_id, readout in readouts.items()
        }

    if not allow_shared_leaf and len(readout_ids) > 1:
        raise ATSTParseError(
            f"{block_name} block without readout_id cannot be shared across "
            "multiple readouts"
        )

    return {
        readout_id: _copy_leaf_block(block, block_type, block_name)
        for readout_id in readout_ids
    }


def _require_all_readout_ids(
    values: dict[str, Any],
    readout_ids: list[str],
    block_name: str,
) -> None:
    missing = set(readout_ids) - set(values)
    if missing:
        raise ATSTParseError(
            f"{block_name} is missing readout_id values: {', '.join(sorted(missing))}"
        )

    extra = set(values) - set(readout_ids)
    if extra:
        raise ATSTParseError(
            f"{block_name} has undeclared readout_id values: {', '.join(sorted(extra))}"
        )


def _copy_leaf_block(block: Any, block_type: type, block_name: str) -> Any:
    data = block.data
    if isinstance(data, pd.DataFrame):
        data = data.copy()
    else:
        data = dict(data)

    return block_type(name=block_name, data=data, linked_file=block.linked_file)


def _build_atst_for_readout(
    *,
    readout_id: str | None,
    file_info: FileMetadata,
    study: Study,
    readout_ids: ReadoutIds | None,
    metadata: Metadata,
    assay: Assay,
    layout: Layout,
    readings: Readings,
    entities: Entities,
) -> ATSTFile:
    atst = ATSTFile(
        file_info=file_info,
        study=study,
        readout_id=readout_id,
        readout_ids=readout_ids,
        metadata=metadata,
        assay=assay,
        entities=entities,
        layout=layout,
        readings=readings,
    )
    validate_atst(atst)
    return atst
