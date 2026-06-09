from dataclasses import dataclass
from pathlib import Path


from ATST.blocks import LAYOUT
from ATST.blocks.base_classes import Block, WideTableBlock


@dataclass
class Layout(WideTableBlock, Block):
    name: str = LAYOUT

    @classmethod
    def read_layout(cls, path: str | Path):
        import pandas as pd

        path = Path(path)
        separator = _infer_layout_table_separator(path)

        df = pd.read_csv(path, sep=separator, encoding="utf-8-sig")
        df = df.rename(columns={col: _canonical_column_name(col) for col in df.columns})

        return cls(data=df)


def _infer_layout_table_separator(path: Path) -> str:
    import csv

    suffix_separators = {
        ".csv": ",",
        ".tsv": "\t",
    }
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:8192]

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return suffix_separators.get(path.suffix.lower(), ",")


def _canonical_column_name(value) -> str:
    import re

    canonical_columns = {
        "well": "well_loc",
        "phage": "phage_id",
        "isolate": "isolate_id",
        "moi_level": "moi",
    }
    text = str(value).strip().lower()
    text = re.sub(r"[^0-9a-z]+", "_", text).strip("_")
    return canonical_columns.get(text, text)
