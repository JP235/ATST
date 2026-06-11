from pathlib import Path
from typing import Any, Literal, overload

from ATST.ATSTFile.ATST import ATSTFile, MultiReadoutATST
from ATST.blocks import (
    ASSAY,
    DATA,
    ENTITIES,
    FILE_INFO,
    LAYOUT,
    LAYOUT_SCHEMA,
    METADATA,
    READOUT_MANIFEST,
    STUDY,
    Assay,
    BlockClass,
    Data,
    Entities,
    FileMetadata,
    Layout,
    LayoutSchema,
    Metadata,
    ReadoutManifest,
    Study,
)
from ATST.errors import ATSTParseError, ATSTValidationError
from ATST.parser.block_parser import (
    assay_from_link,
    data_from_link,
    layout_from_link,
    metadata_from_link,
    parse_block,
)
from ATST.parser.parser import parse_file
import pandas as pd


@overload
def read_atst(path: str | Path, allow_multi: Literal[False] = False) -> ATSTFile: ...
@overload
def read_atst(
    path: str | Path, allow_multi: Literal[True] = True
) -> ATSTFile | MultiReadoutATST: ...
def read_atst(
    path: str | Path, allow_multi: bool = False
) -> ATSTFile | MultiReadoutATST:
    """Read an ATST file into the ATST dataclass model.

    Linked payload files are recognized during parsing but are not loaded by this
    function yet. Linked readout-dependent sections are represented by dummy
    section objects.
    """

    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    parsed_blocks = {
        block_name: parse_block(block)
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

    layout_schema = parsed_blocks.get(LAYOUT_SCHEMA, LayoutSchema())

    entities = parsed_blocks.get(ENTITIES, Entities())
    if not isinstance(entities, Entities):
        raise ATSTParseError("ENTITIES block did not parse as Entities")
    if not isinstance(layout_schema, LayoutSchema):
        raise ATSTParseError("LAYOUT_SCHEMA block did not parse as LayoutSchema")

    readout_manifest = parsed_blocks.get(READOUT_MANIFEST)
    if readout_manifest is not None and not isinstance(
        readout_manifest, ReadoutManifest
    ):
        raise ATSTParseError("READOUT_MANIFEST block did not parse as ReadoutManifest")

    if readout_manifest is None:
        metadata = require_block(METADATA)
        assay = require_block(ASSAY)
        layout = require_block(LAYOUT)
        data = require_block(DATA)

        if not isinstance(metadata, Metadata):
            raise ATSTParseError("METADATA block did not parse as Metadata")
        if not isinstance(assay, Assay):
            raise ATSTParseError("ASSAY block did not parse as Assay")
        if not isinstance(layout, Layout):
            raise ATSTParseError("LAYOUT block did not parse as Layout")
        if not isinstance(data, Data):
            raise ATSTParseError("DATA block did not parse as Data")

        for block_name, block in {
            METADATA: metadata,
            ASSAY: assay,
            LAYOUT: layout,
            DATA: data,
        }.items():
            if getattr(block, "per_readout_id", False):
                raise ATSTParseError(
                    f"{block_name} contains readout-specific data, but no "
                    "READOUT_MANIFEST was declared"
                )

        return _build_atst_for_readout(
            readout_id=None,
            file_info=file_info,
            study=study,
            readout_manifest=None,
            metadata=metadata,
            assay=assay,
            layout=layout,
            data=data,
            entities=entities,
            layout_schema=layout_schema,
        )

    readout_ids = readout_manifest.data["readout_id"].tolist()
    if not readout_ids:
        raise ATSTValidationError(
            "READOUT_MANIFEST must contain at least one readout_id"
        )
    if len(readout_ids) != len(set(readout_ids)):
        raise ATSTValidationError(
            f"READOUT_MANIFEST contains duplicate readout_id values: {', '.join(readout_ids)}"
        )

    if not allow_multi and len(readout_ids) > 1:
        raise ATSTValidationError(
            f"READOUT_MANIFEST contains more than one readout_id value: {', '.join(readout_ids)}"
        )

    metadata_by_id = _block_by_readout(
        parsed_blocks.get(METADATA),
        block_type=Metadata,
        readout_ids=readout_ids,
        readout_manifest=readout_manifest,
        manifest_file_column="metadata_file",
        from_link=metadata_from_link,
        allow_shared_leaf=True,
    )
    assay_by_id = _block_by_readout(
        parsed_blocks.get(ASSAY),
        block_type=Assay,
        readout_ids=readout_ids,
        readout_manifest=readout_manifest,
        manifest_file_column="assay_file",
        from_link=assay_from_link,
        allow_shared_leaf=True,
    )
    layout_by_id = _block_by_readout(
        parsed_blocks.get(LAYOUT),
        block_type=Layout,
        readout_ids=readout_ids,
        readout_manifest=readout_manifest,
        manifest_file_column="layout_file",
        from_link=layout_from_link,
        allow_shared_leaf=True,
    )
    data_by_id = _block_by_readout(
        parsed_blocks.get(DATA),
        block_type=Data,
        readout_ids=readout_ids,
        readout_manifest=readout_manifest,
        manifest_file_column="data_file",
        from_link=data_from_link,
        allow_shared_leaf=False,
    )

    readouts = {
        readout_id: _build_atst_for_readout(
            readout_id=readout_id,
            file_info=file_info,
            study=study,
            readout_manifest=readout_manifest,
            metadata=metadata_by_id[readout_id],
            assay=assay_by_id[readout_id],
            layout=layout_by_id[readout_id],
            data=data_by_id[readout_id],
            entities=entities,
            layout_schema=layout_schema,
        )
        for readout_id in readout_ids
    }

    if len(readout_ids) == 1:
        return readouts[readout_ids[0]]

    return MultiReadoutATST(
        file_info=file_info,
        study=study,
        readout_manifest=readout_manifest,
        readouts=readouts,
        entities=entities,
        layout_schema=layout_schema,
    )


def _block_by_readout(
    block: BlockClass | None,
    *,
    block_type: type,
    readout_ids: list[str],
    readout_manifest: ReadoutManifest,
    manifest_file_column: str,
    from_link: Any,
    allow_shared_leaf: bool,
) -> dict[str, Any]:

    block_name = block_type.name
    if block is None:
        links = _manifest_links(readout_manifest, manifest_file_column)
        _require_all_readout_ids(links, readout_ids, block_name)
        return {
            readout_id: from_link(file_path) for readout_id, file_path in links.items()
        }

    if (
        isinstance(block, (Data, Layout, Assay, Metadata))
        and block.per_readout_data is not None
    ):
        readouts = dict(block.per_readout_data)
        _require_all_readout_ids(readouts, readout_ids, block_name)
        return readouts

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


def _manifest_links(
    readout_manifest: ReadoutManifest,
    file_column: str,
) -> dict[str, str]:
    if file_column not in readout_manifest.data.columns:
        return {}

    links: dict[str, str] = {}
    for _, row in readout_manifest.data.iterrows():
        file_path = row[file_column]
        if file_path and file_path.casefold() != "na":
            links[row["readout_id"]] = file_path

    return links


def _build_atst_for_readout(
    *,
    readout_id: str | None,
    file_info: FileMetadata,
    study: Study,
    readout_manifest: ReadoutManifest | None,
    metadata: Metadata,
    assay: Assay,
    layout: Layout,
    data: Data,
    entities: Entities,
    layout_schema: LayoutSchema,
) -> ATSTFile:
    return ATSTFile(
        file_info=file_info,
        study=study,
        readout_id=readout_id,
        readout_manifest=readout_manifest,
        metadata=metadata,
        assay=assay,
        entities=entities,
        layout_schema=layout_schema,
        layout=layout,
        data=data,
    )
