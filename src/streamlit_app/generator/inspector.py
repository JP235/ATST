from __future__ import annotations

from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from ATST import ATSTFile, MultiReadoutATST, read_atst
from ATST.blocks import READOUT_IDS
from ATST.parser.parser import parse_file


def read_uploaded_atst(uploaded_file) -> ATSTFile | MultiReadoutATST:
    """Parse and validate one uploaded standalone ATST file or linked ZIP."""

    file_name = Path(uploaded_file.name).name
    with TemporaryDirectory(prefix="atst-inspect-") as directory:
        uploaded_path = Path(directory) / file_name
        contents = uploaded_file.getvalue()
        uploaded_path.write_bytes(contents)

        if uploaded_path.suffix.lower() == ".zip":
            with ZipFile(uploaded_path) as archive:
                members = [PurePosixPath(info.filename) for info in archive.infolist()]
                if any(path.is_absolute() or ".." in path.parts for path in members):
                    raise ValueError("ZIP contains an unsafe path")
                archive.extractall(directory)

            containers = [
                path
                for path in members
                if len(path.parts) <= 2
                and path.name.endswith((".atst.txt", ".atst.tsv"))
            ]
            roots = [path for path in containers if len(path.parts) == 1]
            if len(roots) > 1:
                raise ValueError("ZIP must contain exactly one root ATST file")
            if not roots and not containers:
                raise ValueError("ZIP does not contain an ATST file at depth 0 or 1")
            uploaded_path = Path(directory) / (roots[0] if roots else containers[0])

        text = uploaded_path.read_text(encoding="utf-8")
        blocks = parse_file(text.splitlines())
        return read_atst(uploaded_path, multi_readouts=READOUT_IDS in blocks)
